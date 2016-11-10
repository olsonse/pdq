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
from .spi import SPISlave


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
    """Converts parallel data stream from FTDI chip into framed
    SPI-like data.
    """
    def __init__(self):
        self.sink = Endpoint(bus_layout)
        self.source = Endpoint(bus_layout)
        self.source.eop.reset = 1

        ###

        unesc = Unescaper(bus_layout)
        self.submodules += unesc
        self.sync += [
            If(unesc.source1.stb,
                Case(unesc.source1.data, {
                    0x02: self.source.eop.eq(0),
                    0x03: self.source.eop.eq(1),
                }),
            )
        ]
        self.comb += [
            self.sink.connect(unesc.sink),
            self.source.data.eq(unesc.source0.data),
            self.source.stb.eq(unesc.source0.stb),
            unesc.source0.ack.eq(self.source.ack),
            unesc.source1.ack.eq(1),
        ]


class Arbiter(Module):
    def __init__(self, width=8):
        self.sink0 = Endpoint(bus_layout)
        self.sink1 = Endpoint(bus_layout)
        self.source = Endpoint(bus_layout)

        ###

        self.comb += [
            If(~self.sink0.eop,  # has priority
                self.sink0.connect(self.source),
            ).Else(
                self.sink1.connect(self.source),
            )
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
        self.sink = Endpoint(bus_layout)
        self.source = Endpoint(bus_layout)
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
            crc.data.eq(self.sink.data[::-1]),
            crc.last.eq(self.checksum),
        ]
        self.sync += [
            If(self.sink.stb & ~self.sink.eop & ~self.source.stb,
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
        self.comb += cmd_cur.raw_bits().eq(self.sink.data)
        cmd = Record(cmd_layout)

        reg_map = Array([self.config.raw_bits(), self.checksum, self.frame])
        reg_we = Signal()
        self.sync += [
            If(reg_we,
                reg_map[cmd.adr].eq(self.sink.data),
            )
        ]

        mems = [mem.get_port(write_capable=True, we_granularity=8)
                for mem in mems]
        self.specials += mems
        mem_adr = Signal(16)
        mem_we = Signal()
        mem_dat_r = Signal(16)
        self.comb += [
            self.sink.ack.eq(1),
            [[
                mem.adr.eq(mem_adr[1:]),
                mem.dat_w.eq(Replicate(self.sink.data, 2)),
            ] for mem in mems],
            If(mem_we,
                Array([mem.we for mem in mems])[cmd.adr].eq(
                    Mux(mem_adr[0], 0b10, 0b01)),
            ),
            mem_dat_r.eq(Array([mem.dat_r for mem in mems])[cmd.adr]),
        ]

        fsm = ResetInserter()(CEInserter()(FSM(reset_state="CMD")))
        self.submodules += fsm
        self.comb += [
            fsm.reset.eq(self.sink.eop),
            fsm.ce.eq(self.sink.stb),
        ]

        fsm.act("CMD",
            If((cmd_cur.board == self.board) | (cmd_cur.board == 0xf),
                If(cmd_cur.is_mem,
                    NextState("MEM_ADRL"),
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
        fsm.act("IGNORE",
            NextState("IGNORE"))
        fsm.act("REG_WRITE",
            reg_we.eq(self.sink.stb),
            NextState("IGNORE"),
        )
        fsm.act("REG_READ",
            self.source.stb.eq(self.sink.stb),
            self.source.data.eq(reg_map[cmd.adr]),
            NextState("IGNORE"),
        )
        fsm.act("MEM_ADRL",
            NextState("MEM_ADRH"),
        )
        fsm.act("MEM_ADRH",
            NextState("MEM_DO"),
        )
        fsm.act("MEM_DO",
            If(self.sink.stb,
                If(cmd.we,
                    mem_we.eq(1),
                ).Else(
                    self.source.stb.eq(1),
                ),
            ),
            self.source.data.eq(Mux(mem_adr[0],
                                    mem_dat_r[8:], mem_dat_r[:8])),
        )
        self.sync += [
            If(fsm.before_leaving("CMD"),
                cmd.raw_bits().eq(self.sink.data),
            ),
            If(fsm.before_leaving("MEM_ADRL"),
                mem_adr[:8].eq(self.sink.data),
            ),
            If(fsm.before_leaving("MEM_ADRH"),
                mem_adr[8:].eq(self.sink.data),
            ),
            If(fsm.ongoing("MEM_DO") & self.sink.stb,
                mem_adr.eq(mem_adr + 1),
            ),
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
        self.spi = spi
        self.proto = proto
        self.rg = rg
        self.ftdi_bus = f2s.sink

        self.comb += [
            spi.spi.cs_n.eq(ctrl_pads.frame[0]),
            spi.spi.clk.eq(ctrl_pads.frame[1]),
            spi.spi.mosi.eq(ctrl_pads.frame[2]),
            spi.mosi.connect(arb.sink0),
            proto.source.connect(spi.miso),
            spi.reset.eq(spi.cs_n),
            f2s.source.connect(arb.sink1),
            arb.source.connect(proto.sink),
        ]

        trigger = Signal()
        self.specials += MultiReg(ctrl_pads.trigger, trigger)

        aux_dac = Signal()

        self.comb += [
            proto.board.eq(~ctrl_pads.board),  # pcb inverted
            rg.trigger.eq(proto.config.reset),
            ctrl_pads.aux.eq(Mux(proto.config.aux_miso,
                                 spi.spi.miso, aux_dac)),
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
