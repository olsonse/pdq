# Copyright 2013-2015 Robert Jordens <jordens@gmail.com>
#
# This file is part of pdq2.
#
# pdq2 is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pdq2 is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pdq2.  If not, see <http://www.gnu.org/licenses/>.

from migen import *
from migen.genlib.cdc import MultiReg
from misoc.interconnect.stream import Endpoint
from misoc.cores.liteeth_mini.mac.crc import LiteEthMACCRCEngine

from .ft245r import bus_layout
from .escape import Unescaper
from .spi import spi_data_layout, SPISlave


mem_layout = [("data", 16)]


class ResetGen(Module):
    """Reset generator.

    Asserts :attr:`reset` for a given number of cycles when triggered.

    Args:
        n (int): number of cycles.

    Attributes:
        trigger (Signal): Trigger input.
        reset (Signal): Reset output. Active high.
    """
    def __init__(self, n=1<<7):
        self.trigger = Signal()
        self.reset = Signal()

        ###

        self.clock_domains.cd_no_rst = ClockDomain(reset_less=True)
        counter = Signal(max=n)
        self.comb += [
                self.cd_no_rst.clk.eq(ClockSignal()),
                self.reset.eq(counter != n - 1)
        ]
        self.sync.no_rst += [
                If(self.trigger,
                    counter.eq(0)
                ).Elif(self.reset,
                    counter.eq(counter + 1)
                ),
        ]



class FTDI2SPI(Module):
    def __init__(self):
        self.sink = Endpoint(bus_layout)
        self.source = Endpoint(spi_data_layout(width=8))
        self.eop = Signal(reset=1)

        ###

        unesc = Unescaper(bus_layout)
        self.submodules += unesc
        self.sync += [
            If(unesc.source1.stb,
                Case(unesc.source1.data, {
                    0x02: self.eop.eq(0),
                    0x03: self.eop.eq(1),
                }),
            )
        ]
        self.comb += [
            self.sink.connect(unesc.sink),
            self.source.mosi.eq(unesc.source0.data),
            self.source.stb.eq(unesc.source0.stb),
            unesc.source0.ack.eq(1),
        ]


class Protocol(Module):
    """Handles the memory write protocol and writes data to the channel
    memories.

    Args:
        board (Value): Address of this board.
        dacs (list): List of :mod:`gateware.dac.Dac`.

    Attributes:
        sink (Endpoint[mem_layout]): 16 bit data sink.
    """
    def __init__(self, mems):
        self.sink = Endpoint(spi_data_layout(width=8))
        self.eop = Signal()
        self.board = Signal(4)

        # mapped registers
        self.config = Record([
            ("reset", 1),
            ("clk2x", 1),
            ("enable", 1),
            ("trigger", 1),
            ("aux_miso", 1),
            ("aux_dac", 3),
        ])
        self.checksum = Signal(8)
        self.frame = Signal(max=32)

        ###

        # CRC8-CCIT
        crc = LiteEthMACCRCEngine(data_width=8, width=8, polynom=0x07)
        self.submodules += crc

        self.comb += [
            crc.data.eq(self.sink.mosi),
            crc.last.eq(self.checksum),
        ]
        self.sync += [
            If(self.sink.stb & ~self.eop,
                self.checksum.eq(crc.next),
            ),
        ]

        cmd_layout = [
            ("adr", 2),     # reg or mem
            ("is_mem", 1),  # is_mem/is_reg_n
            ("board", 4),   # 0xf: broadcast
            ("we", 1),      # write/read_n
        ]
        cmd_cur = Record(cmd_layout)
        self.comb += cmd_cur.raw_bits().eq(self.sink.mosi)
        cmd = Record(cmd_layout)

        reg_map = Array([self.config.raw_bits(), self.checksum, self.frame])
        reg_we = Signal()
        self.sync += [
            If(reg_we,
                reg_map[cmd.adr].eq(self.sink.mosi),
            )
        ]

        mems = [mem.get_port(write_capable=True)
                for mem in mems]
        self.specials += mems
        mem_adr = Signal(16)
        mem_we = Signal()
        mem_dat_wh = Signal(8)
        mem_dat_r = Signal(16)
        self.comb += [
            [[
                mem.adr.eq(mem_adr),
                mem.dat_w.eq(Cat(self.sink.mosi, mem_dat_wh))
            ] for mem in mems],
            Array([mem.we for mem in mems])[cmd.adr].eq(mem_we),
            mem_dat_r.eq(Array([mem.dat_r for mem in mems])[cmd.adr]),
        ]

        fsm = ResetInserter()(CEInserter()(FSM(reset_state="CMD")))
        self.submodules += fsm
        self.comb += [
            fsm.reset.eq(self.eop),
            fsm.ce.eq(self.sink.stb),
        ]

        fsm.act("CMD",
            NextValue(cmd.raw_bits(), cmd_cur.raw_bits()),
            If((cmd_cur.board == self.board) | (cmd_cur.board == 0xf),
                If(cmd_cur.is_mem,
                    NextState("MEM_ADRH"),
                ).Else(
                    If(cmd_cur.we,
                        NextState("REG_WRITE"),
                    ).Else(
                        NextState("REG_READ"),
                    ),
                ),
            ).Else(
                NextState("IGNORE"),
            ),
        )
        fsm.act("IGNORE")
        fsm.act("REG_WRITE",
            reg_we.eq(self.sink.stb),
        )
        fsm.act("REG_READ",
            self.sink.ack.eq(1),  # drive miso
            self.sink.miso.eq(reg_map[cmd.adr]),
        )
        fsm.act("MEM_ADRH",
            NextValue(mem_adr[8:], self.sink.mosi),
            NextState("MEM_ADRL"),
        )
        fsm.act("MEM_ADRL",
            NextValue(mem_adr[:8], self.sink.mosi),
            If(cmd.we,
                NextState("MEM_WRITEH"),
            ).Else(
                NextState("MEM_READH"),
            ),
        )
        fsm.act("MEM_WRITEH",
            NextValue(mem_dat_wh, self.sink.mosi),
            NextState("MEM_WRITEL"),
        )
        fsm.act("MEM_WRITEL",
            mem_we.eq(self.sink.stb),
            NextValue(mem_adr, mem_adr + 1),
            NextState("MEM_WRITEH"),
        )
        fsm.act("MEM_READH",
            self.sink.ack.eq(1),  # drive miso
            self.sink.miso.eq(mem_dat_r[8:]),
            NextState("MEM_READL"),
        )
        fsm.act("MEM_READL",
            self.sink.ack.eq(1),  # drive miso
            self.sink.miso.eq(mem_dat_r[:8]),
            NextValue(mem_adr, mem_adr + 1),
            NextState("MEM_READH"),
        )


class Arbiter(Module):
    def __init__(self, width=8):
        self.eop0 = Signal()
        self.eop1 = Signal()
        self.sink0 = Endpoint(spi_data_layout(width))
        self.sink1 = Endpoint(spi_data_layout(width))
        self.eop = Signal(reset=1)
        self.source = Endpoint(spi_data_layout(width))

        ###

        self.comb += [
            If(self.eop0,
                self.eop.eq(self.eop0),
                self.sink0.connect(self.source),
            ).Else(
                self.eop.eq(self.eop1),
                self.sink1.connect(self.source),
            )
        ]


class Comm(Module):
    """USB Protocol handler.

    Args:
        ctrl_pads (Record): Control signal pads.
        dacs (list): List of :mod:`gateware.dac.Dac`.

    Attributes:
        sink (Endpoint[bus_layout]): 8 bit data sink containing both the control
            sequencences and the data stream.

    Control command handler.

    Controls the input and output TTL signals, handles the excaped control
    commands.

    Args:
        pads (Record): Pads containing the TTL input and output control signals
        dacs (list): List of :mod:`gateware.dac.Dac`.

    Attributes:
        reset (Signal): Reset output from :class:`ResetGen`. Active high.
        dcm_sel (Signal): DCM slock select. Enable clock doubler. Output.
        sink (Endpoint[bus_layout]): 8 bit control data sink. Input.
    """
    def __init__(self, ctrl_pads, dacs):
        rg = ResetGen()
        spi = SPISlave(width=8)
        f2s = FTDI2SPI()
        arb = Arbiter()
        proto = Protocol([dac.parser.mem for dac in dacs])
        self.submodules += proto, rg, spi, f2s, arb
        self.proto = proto
        self.ftdi_bus = f2s.sink

        self.comb += [
            spi.spi.cs_n.eq(ctrl_pads.frame[0]),
            spi.spi.clk.eq(ctrl_pads.frame[1]),
            spi.spi.mosi.eq(ctrl_pads.frame[2]),
            spi.data.connect(arb.sink0),
            arb.eop0.eq(spi.cs_n),
            spi.reset.eq(spi.cs_n),
            f2s.source.connect(arb.sink1),
            arb.eop1.eq(f2s.eop),
            arb.source.connect(proto.sink),
            proto.eop.eq(arb.eop),
        ]

        trigger = Signal()
        self.specials += MultiReg(ctrl_pads.trigger, trigger)

        aux_dac = Signal()

        self.comb += [
            proto.board.eq(~ctrl_pads.board),  # pcb inverted
            ctrl_pads.reset.eq(ResetSignal()),
            rg.trigger.eq(proto.config.reset),
            ctrl_pads.aux.eq(Mux(proto.config.aux_miso,
                                 spi.spi.miso, aux_dac)),
        ]

        self.sync += [
            aux_dac.eq(proto.config.aux_dac &
                       Cat([dac.out.aux for dac in dacs]) != 0),
        ]

        for dac in dacs:
            self.comb += [
                    dac.parser.frame.eq(proto.frame),
                    dac.out.trigger.eq(proto.config.enable &
                                       (trigger | proto.config.trigger)),
                    dac.out.arm.eq(proto.config.enable),
                    dac.parser.arm.eq(proto.config.enable),
                    dac.parser.start.eq(proto.config.enable),
            ]
