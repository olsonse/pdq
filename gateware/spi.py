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


import logging

from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.misc import WaitTimer
from misoc.interconnect.stream import Endpoint
from misoc.cores.spi import SPIMachine


logger = logging.getLogger(__name__)


class Hysteresis(Module):
    def __init__(self, cycles=1):
        self.i = Signal()
        self.o = Signal()

        ###

        timer = WaitTimer(cycles - 1)
        self.submodules += timer
        new = Signal()
        self.sync += [
            If(timer.wait,
                If(timer.done,
                    timer.wait.eq(0),
                    new.eq(~new),
                ),
            ).Elif(self.i == new,
                timer.wait.eq(1),
            ),
        ]
        self.comb += [
            self.o.eq(Mux(timer.wait, new, self.i)),
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
    ("oe_m", 1, DIR_M_TO_S),
    ("oe_s", 1, DIR_S_TO_M),
]


class SpiSlave(Module):
    def __init__(self, width=8):
        self.spi = spi = Record(spi_layout)
        self.data = data = Endpoint([
            ("mosi", width, DIR_M_TO_S),
            ("miso", width, DIR_S_TO_M),
            ("oe", 1, DIR_S_TO_M)
        ])

        ###

        inp = Hysteresis(cycles=1)
        sr = ResetInserter()(CEInserter()(
            ShiftRegister(width)
        ))
        self.submodules += inp, sr
        self.specials += [
            MultiReg(self.spi.clk, inp.i),
            MultiReg(self.spi.cs_n, sr.reset),
            MultiReg(self.spi.mosi, sr.i),  # latency matching
        ]

        clk0 = Signal()
        edge = Signal()
        self.sync += [
            clk0.eq(inp.o),
            If(edge & ~inp.o,  # falling
                spi.miso.eq(sr.o),
            ),
            If(data.stb,
                sr.data.eq(data.miso),
                spi.oe_s.eq(data.oe & data.ack),
            ),
        ]
        self.comb += [
            edge.eq(clk0 != inp.o),
            sr.ce.eq(edge & inp.o),  # rising
            data.stb.eq(sr.stb & sr.ce),
            data.mosi.eq(sr.next),
            data.eop.eq(sr.reset),  # TODO
        ]


class TB(Module):
    def __init__(self):
        self.submodules.m = m = SPIMachine(data_width=16, clock_width=8,
                                           bits_width=6)
        self.submodules.s = s = SpiSlave()
        self.comb += [
            s.spi.cs_n.eq(~m.cs),
            s.spi.clk.eq(m.cg.clk),
            s.spi.mosi.eq(m.reg.o),
            m.reg.i.eq(s.spi.miso),
            s.spi.oe_m.eq(m.oe),
        ]

    def run_setup(self):
        yield self.m.clk_phase.eq(0)
        yield self.m.reg.lsb.eq(0)
        yield self.m.div_write.eq(5)
        yield self.m.div_read.eq(7)
        yield
        yield

    def run_master(self, write, read, warmup=15):
        for i in write:
            for _ in range(warmup):
                yield
            o = (yield from self.xfer_master(i))
            logger.info("master %s -> %s", i, o)
            read.append(o)

    def xfer_master(self, i):
        yield self.m.bits.n_write.eq(8)
        yield self.m.bits.n_read.eq(8)
        yield self.m.reg.data.eq(i << 8)
        yield self.m.start.eq(1)
        yield
        yield self.m.start.eq(0)
        while not (yield self.m.done):
            yield
        r = (yield self.m.reg.data) & 0xff
        yield
        return r

    def run_slave(self, write, read, warmup=15):
        for i in write:
            o = (yield from self.xfer_slave(i))
            logger.info("slave %s -> %s", i, o)
            read.append(o)

    def xfer_slave(self, i):
        yield self.s.data.miso.eq(i)
        yield self.s.data.ack.eq(1)
        while not (yield self.s.data.stb):
            yield
        r = (yield self.s.data.mosi), (yield self.s.data.eop)
        yield self.s.data.ack.eq(0)
        yield
        return r


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s.%(funcName)s:%(lineno)d] %(message)s")
    from migen.fhdl import verilog
    print(verilog.convert(SpiSlave()))
    # print(verilog.convert(TB()))
    tb = TB()
    mosi_write = [0xa5, 0x5a]
    miso_write = [0x81, 0, 0x83, 0]
    mosi_read = []
    miso_read = []
    run_simulation(tb, [
        tb.run_setup(),
        tb.run_master(mosi_write, miso_read),
        tb.run_slave(miso_write, mosi_read)
    ], vcd_name="spi.vcd")
    mosi_read, eop_read = zip(*mosi_read)
    mosi_read = list(mosi_read[::2])
    miso_write = list(miso_write[::2])
    assert mosi_write == mosi_read, (mosi_write, mosi_read)
    assert miso_write == miso_read, (miso_write, miso_read)
    #assert eop_read == [1, 1], (eop_read,)
