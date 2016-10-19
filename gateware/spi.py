# -*- coding: utf-8 -*-
#
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
from misoc.interconnect.stream import Endpoint, EndpointDescription


class DecimatingSynchronizer(Module):
    """This synchronizer detects deglitched clock edges
    (defined as an n-stable change of the input clock) and exposes data and
    clock at that edge"""
    def __init__(self, width, n=2, odomain="sys"):
        self.i = Signal(width)
        self.i_clk = Signal()
        self.o = Signal(width)
        self.stb_rise = Signal()
        self.stb_fall = Signal()
        self.latency = n + 1

        ###

        data_r = [Signal(width) for i in range(n)]
        clk_r = [Signal() for i in range(n)]
        clk_next = Signal(reset=1)
        stb = Signal()
        self.specials += [
            MultiReg(self.i, data_r[0], odomain),
            MultiReg(self.i_clk, clk_r[0], odomain),
        ]
        self.comb += [
            stb.eq(Cat(*clk_r) == Replicate(clk_next, n)),
            self.stb_rise.eq(stb & clk_next),
            self.stb_fall.eq(stb & ~clk_next),
            self.o.eq(data_r[-1]),  # oldest
        ]
        sync = getattr(self.sync, odomain)
        sync += [
            [clk_r[i + 1].eq(clk_r[i]) for i in range(n - 1)],
            [data_r[i + 1].eq(data_r[i]) for i in range(n - 1)],
            If(stb,
                clk_next.eq(~clk_next),
            ),
        ]


class ShiftRegister(Module):
    def __init__(self, width):
        self.i = Signal()
        self.o = Signal()
        self.data = Signal(width)
        self.next = Signal(width)
        self.stb = Signal()  # width bits available in next

        ###

        n = Signal(max=width)
        self.comb += [
            self.o.eq(self.data[-1]),
            self.next.eq(Cat(self.i, self.data)),
            self.stb.eq(n == width - 1),
        ]
        self.sync += [
            n.eq(n + 1),
            If(self.stb,
                n.eq(0),
            ).Else(
                self.data.eq(self.next),
            ),
        ]


spi_layout = [
    ("cs_n", 1, DIR_M_TO_S),
    ("clk", 1, DIR_M_TO_S),
    ("mosi", 1, DIR_M_TO_S),
    ("miso", 1, DIR_S_TO_M),
]


class SpiSlave(Module):
    def __init__(self, width=8):
        self.spi = spi = Record(spi_layout)
        self.mosi = mosi = Endpoint(EndpointDescription(
            [("data", width)]))
        self.miso = miso = Endpoint(EndpointDescription(
            [("data", width)]))
        self.cs = Signal()

        ###

        inp = DecimatingSynchronizer(width=2, n=2)
        sr = ResetInserter()(CEInserter()(ShiftRegister))(width)
        self.submodules += inp, sr
        self.comb += [
            inp.i_clk.eq(spi.clk),
            inp.i.eq(Cat(spi.cs_n, spi.mosi)),
            Cat(sr.reset, sr.i).eq(inp.o),
            sr.ce.eq(inp.stb_rise),
            mosi.data.eq(sr.next),
            mosi.stb.eq(sr.ce & sr.stb),
            miso.ack.eq(mosi.stb),
            self.cs.eq(~sr.reset),
        ]
        self.sync += [
            If(inp.stb_fall,
                spi.miso.eq(sr.o),
            ),
            If(sr.ce & sr.stb,
                mosi.stb.eq(1),
                sr.data[-width:].eq(miso.data),
            ),
        ]


class ClockGen(Module):
    def __init__(self, div=4):
        self.o = Signal()
        self.stb_rise = Signal()
        self.stb_fall = Signal()

        ###

        n = Signal(max=div)
        self.comb += [
            self.stb_rise.eq(n == div//2 - 1),
            self.stb_fall.eq(n == div - 1),
        ]
        self.sync += [
            n.eq(n + 1),
            If(self.stb_rise,
                self.o.eq(1),
            ).Elif(self.stb_fall,
                self.o.eq(0),
                n.eq(0),
            ),
        ]


class SpiMaster(Module):
    def __init__(self, width=8, div=20):
        self.spi = spi = Record(spi_layout)
        self.mosi = mosi = Endpoint(EndpointDescription(
            [("data", width)], packetized=True))
        self.miso = miso = Endpoint(EndpointDescription(
            [("data", width)], packetized=True))

        ###

        spi.cs_n.reset = 1
        cg = ResetInserter()(CEInserter()(ClockGen))(div)
        sr = ResetInserter()(CEInserter()(ShiftRegister))(width)
        self.submodules += cg, sr
        spi_miso_i = Signal()
        self.specials += MultiReg(spi.miso, spi_miso_i)
        cs = Signal()
        self.comb += [
            cg.reset.eq(~cs),
            sr.reset.eq(cg.reset & ~mosi.stb),
            sr.ce.eq(cg.stb_fall),
            spi.cs_n.eq(cg.reset),
            spi.clk.eq(cg.o),
            spi.mosi.eq(sr.o),
            miso.stb.eq(sr.stb & sr.ce),
            mosi.ack.eq(cg.reset | miso.stb),
            miso.data.eq(sr.next),
        ]
        self.sync += [
            If(cg.stb_rise,
                sr.i.eq(spi_miso_i),
            ),
            If(miso.stb,
                cg.ce.eq(0),
                If(miso.eop,
                    cs.eq(0),
                ),
            ),
            If(mosi.stb,
                cs.eq(1),
                If(mosi.ack,
                    cg.ce.eq(1),
                    sr.data.eq(mosi.data),
                    miso.eop.eq(mosi.eop),
                ),
            ),
        ]


class TB(Module):
    def __init__(self):
        self.submodules.m = m = SpiMaster()
        self.submodules.s = s = SpiSlave()
        self.comb += m.spi.connect(s.spi)

    def mosi(self, m, s):
        for i in range(1000):
            if (yield self.m.mosi.ack) and m:
                yield self.m.mosi.stb.eq(bool(m))
                p = m.pop(0)
                yield self.m.mosi.data.eq(p)
                yield self.m.mosi.eop.eq(not m)
                print("mosi tx", p)
            if (yield self.s.mosi.stb):
                p = (yield self.s.mosi.data)
                print("mosi rx", p)
                s.append(p | (p << 2))
            if (yield self.s.miso.ack) and s:
                p = s.pop(0)
                yield self.s.miso.data.eq(p)
                print("miso tx", p)
            if (yield self.m.miso.stb):
                p = (yield self.m.miso.data)
                print("miso rx", p)
                m.append(p | (p << 4))
            yield

    def run(self, data):
        yield
        yield
        yield from self.mosi(data, [])


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s.%(funcName)s:%(lineno)d] %(message)s")
    from migen.fhdl import verilog
    # print(verilog.convert(SpiSlave()))
    print(verilog.convert(TB()))
    tb = TB()
    data = [1, 2]
    run_simulation(tb, tb.run(data), vcd_name="spi.vcd")
