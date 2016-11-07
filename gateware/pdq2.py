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
from migen.genlib.record import Record
from migen.genlib.resetsync import AsyncResetSynchronizer

from .dac import Dac
from .comm import Comm
from .ft245r import Ft245r_rx  # , SimFt245r_rx


class Pdq2Base(Module):
    """PDQ2 Base configuration.

    Used both in functional simulation and final gateware.

    Holds the three :mod:`gateware.dac.Dac` and the communication handler
    :mod:`gateware.comm.Comm`.

    Args:
        ctrl_pads (Record): Control pads for :mod:`gateware.comm.Comm`.
        mem_depth (list[int]): Memory depths for the DAC channels.

    Attributes:
        dacs (list): List of :mod:`gateware.dac.Dac`.
        comm (Module): :mod:`gateware.comm.Comm`.
    """
    def __init__(self, ctrl_pads, mem_depths=(1 << 13, 1 << 13, 1 << 12)):
        self.dacs = []
        for i, depth in enumerate(mem_depths):
            dac = Dac(mem_depth=depth)
            setattr(self.submodules, "dac{}".format(i), dac)
            self.dacs.append(dac)
        self.submodules.comm = Comm(ctrl_pads, self.dacs)


class Pdq2Sim(Module):
    ctrl_layout = [
        ("board", 4),
        ("aux", 1),
        ("frame", 3),
        ("trigger", 1),
        ("reset", 1),
        ("g2_in", 1),
        ("g2_out", 1),
    ]

    def __init__(self, **kwargs):
        self.ctrl_pads = Record(self.ctrl_layout)
        self.ctrl_pads.board.reset = 0b1111  # board-inverted
        self.ctrl_pads.frame.reset = 0b111  # pullup on cs_n
        self.ctrl_pads.trigger.reset = 1
        self.submodules.dut = ResetInserter(["sys"])(
            Pdq2Base(self.ctrl_pads, **kwargs))
        # self.comb += self.dut.reset_sys.eq(self.dut.comm.rg.reset)
        self.outputs = []
        self.aux = []

    def write(self, mem):
        b = self.dut.comm.ftdi_bus
        yield
        for m in mem:
            yield b.data.eq(m)
            yield b.stb.eq(1)
            yield
            while not (yield b.ack):
                yield
            yield b.stb.eq(0)

    @passive
    def record(self):
        while True:
            yield
            self.outputs.append((yield from [(yield dac.out.data)
                                             for dac in self.dut.dacs]))
            self.aux.append((yield self.ctrl_pads.aux))


class CRG(Module):
    """PDQ2 Clock and Reset generator.

    Args:
        platform (Platform): PDQ2 Platform.

    Attributes:
        rst (Signal): Reset input.
        dcm_sel (Signal): Select doubled clock. Input.
        dcm_locked (Signal): DCM locked. Output.
        cd_sys (ClockDomain): System clock domain driven.
        cd_sys_n (ClockDomain): Inverted system clock domain driven.
    """
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys_n = ClockDomain(reset_less=True)
        self.rst = Signal()
        self.dcm_locked = Signal()
        self.dcm_sel = Signal()

        clkin = platform.request("clk50")
        clkin_period = 20.

        clkin_sdr = Signal()
        self.specials += Instance("IBUFG", i_I=clkin, o_O=clkin_sdr)

        dcm_clk2x = Signal()
        dcm_clk2x180 = Signal()
        self.specials += Instance("DCM_SP",
                p_CLKDV_DIVIDE=2,
                p_CLKFX_DIVIDE=1,
                p_CLKFX_MULTIPLY=2,
                p_CLKIN_DIVIDE_BY_2="FALSE",
                p_CLKIN_PERIOD=clkin_period,
                #p_CLK_FEEDBACK="2X",
                p_CLK_FEEDBACK="NONE",
                p_DLL_FREQUENCY_MODE="LOW",
                p_DFS_FREQUENCY_MODE="LOW",
                p_STARTUP_WAIT="TRUE",
                p_CLKOUT_PHASE_SHIFT="NONE",
                p_PHASE_SHIFT=0,
                p_DUTY_CYCLE_CORRECTION="TRUE",
                i_RST=0,
                i_PSEN=0,
                i_PSINCDEC=0,
                i_PSCLK=0,
                i_CLKIN=clkin_sdr,
                o_LOCKED=self.dcm_locked,
                #o_CLK2X=dcm_clk2x,
                #o_CLK2X180=dcm_clk2x180,
                o_CLKFX=dcm_clk2x,
                o_CLKFX180=dcm_clk2x180,
                #i_CLKFB=clk_p,
                i_CLKFB=0,
                )
        self.specials += Instance("BUFGMUX",
                i_I0=clkin_sdr, i_I1=dcm_clk2x, i_S=self.dcm_sel,
                o_O=self.cd_sys.clk)
        self.specials += Instance("BUFGMUX",
                i_I0=~clkin_sdr, i_I1=dcm_clk2x180, i_S=self.dcm_sel,
                o_O=self.cd_sys_n.clk)
        self.specials += AsyncResetSynchronizer(
            self.cd_sys, ~self.dcm_locked | self.rst)


@SplitMemory()
class Pdq2(Pdq2Base):
    """PDQ2 Top module.

    Wires up USB FIFO reader :mod:`gateware.ft245r.Ft345r_rx`, clock and reset
    generator :mod:`CRG`, and the DAC output signals.
    Delegates the wiring of the remaining modules to :mod:`Pdq2Base`.

    ``pads.g2_out`` is assigned the DCM locked signal.

    Args:
        platform (Platform): PDQ2 platform.
    """
    def __init__(self, platform, **kwargs):
        self.platform = platform
        ctrl_pads = platform.request("ctrl")
        Pdq2Base.__init__(self, ctrl_pads, **kwargs)
        self.submodules.crg = CRG(platform)
        comm_pads = platform.request("comm")
        self.submodules.reader = Ft245r_rx(comm_pads)
        self.comb += [
                self.reader.source.connect(self.comm.ftdi_bus),
                self.crg.rst.eq(self.comm.rg.reset),
                ctrl_pads.g2_out.eq(self.crg.dcm_locked),
                self.crg.dcm_sel.eq(self.comm.proto.config.clk2x),
                ctrl_pads.reset.eq(ResetSignal()),
        ]

        sys_p, sys_n = ClockSignal("sys"), ClockSignal("sys_n")
        for i, dac in enumerate(self.dacs):
            pads = platform.request("dac", i)
            # inverted clocks ensure setup and hold times of data
            ce = Signal()
            d = Signal.like(dac.out.data)
            self.comb += [
                    ce.eq(~dac.out.silence),
                    d.eq(~dac.out.data),  # pcb inversion
            ]

            self.specials += Instance("ODDR2",
                    i_C0=sys_p, i_C1=sys_n, i_CE=ce,
                    i_D0=0, i_D1=1, i_R=0, i_S=0, o_Q=pads.clk_p)
            self.specials += Instance("ODDR2",
                    i_C0=sys_p, i_C1=sys_n, i_CE=ce,
                    i_D0=1, i_D1=0, i_R=0, i_S=0, o_Q=pads.clk_n)
            dclk = Signal()
            self.specials += Instance("ODDR2",
                    i_C0=sys_p, i_C1=sys_n, i_CE=ce,
                    i_D0=0, i_D1=1, i_R=0, i_S=0, o_Q=dclk)
            self.specials += Instance("OBUFDS",
                    i_I=dclk, o_O=pads.data_clk_p, o_OB=pads.data_clk_n)
            for i in range(16):
                self.specials += Instance("OBUFDS",
                        i_I=d[i], o_O=pads.data_p[i], o_OB=pads.data_n[i])
