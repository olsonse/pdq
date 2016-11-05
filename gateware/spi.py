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
from migen.genlib.misc import WaitTimer
from misoc.interconnect.stream import Endpoint


class Debouncer(Module):
    """Debounce a signal.

    The initial change on input is passed through immediately. But
    further changes are suppressed for `cycles`.

    Args:
        cycles (int): Block furhter level changes for that many cycles
            after an initial change.

    Attributes:
        i (Signal): Input, needs a `MultiReg` in front of it
            if this is an asynchronous signal.
        o (Signal): Debounced output.
    """
    def __init__(self, cycles=1):
        self.i = Signal()
        self.o = Signal()

        ###

        timer = WaitTimer(cycles - 1)
        self.submodules += timer
        new = Signal()
        rst = Signal(reset=1)
        self.sync += [
            If(timer.wait,
                If(timer.done,
                    timer.wait.eq(0),
                    new.eq(~new),
                ),
            ).Elif(self.i == new,
                timer.wait.eq(1),
            ),
            If(rst,
                rst.eq(0),
                timer.wait.eq(0),
                new.eq(~self.i),
            ),
        ]
        self.comb += [
            self.o.eq(Mux(timer.wait, new, self.i)),
        ]


class ShiftRegister(Module):
    """Shift register for an SPI slave.

    Args:
        width (int): Register width in bits.

    Attributes:
        i (Signal): Serial input.
        o (Signal): Serial output.
        data (Signal(width)): Content of the shift register.
        next (Signal(width)): Combinatorial content of the
            register in the next cycle.
        stb (Signal): Strobe signal indicating that `width` bits have been
            shifted (in and out) and the register value can be swapped.
    """
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


def spi_data_layout(width):
    return [
        ("mosi", width, DIR_M_TO_S),
        ("miso", width, DIR_S_TO_M),
    ]


@ResetInserter()
class SPISlave(Module):
    """SPI slave.

        * CLK_PHA, CLK_POL = 0,0
        * MSB first

    Args:
        width (int): Shift register width in bits.

    Attributes:
        spi (Record): SPI bus record consisting of `cs_n`, `clk`, `mosi`,
            `miso`, `oe_s`, and `oe_m`. Use `oe_s` (driven by the slave) to
            wire up a tristate half-duplex data line. Use `oe_m` on the master
            side.
        data (Endpoint): SPI parallel communication stream.

            * `mosi`: `width` bits read on the mosi line in the previous clock
                cycles
            * `miso`: `width` bits to be written on miso line in the next
                cycles
            * `stb`: data available in mosi and data read from miso.
            * `ack`: in half-duplex mode, drive miso on the combined
                miso/mosi data line

        cs_n (Signal): use to `s.reset.eq(s.cs_n)` and for framing logic.
    """
    def __init__(self, width=8):
        self.spi = spi = Record(spi_layout)
        self.data = data = Endpoint(spi_data_layout(width))
        self.cs_n = Signal()

        ###

        inp = Debouncer(cycles=1)
        sr = CEInserter()(ShiftRegister(width))
        self.submodules += inp, sr
        self.specials += [
            MultiReg(self.spi.clk, inp.i),
            MultiReg(self.spi.cs_n, self.cs_n),
            MultiReg(self.spi.mosi, sr.i, n=3),  # latency matching
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
                spi.oe_s.eq(data.ack),
            ),
        ]
        self.comb += [
            edge.eq(clk0 != inp.o),
            sr.ce.eq(edge & inp.o),  # rising
            data.stb.eq(sr.stb & sr.ce),
            data.mosi.eq(sr.next),
        ]
