# Copyright 2013-2017 Robert Jordens <jordens@gmail.com>
#
# This file is part of pdq.
#
# pdq is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pdq is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pdq.  If not, see <http://www.gnu.org/licenses/>.

from math import ceil
import random

from migen import *
from migen.genlib.misc import timeline
from migen.genlib.record import Record
from migen.genlib.cdc import MultiReg
from misoc.interconnect.stream import Endpoint


class SimFt245r_rx_w(Module):
    t_fill = [0, 3]
    t_delay = [0, 1]
    t_setup = [0, 4]  # 5 - wr

    def __init__(self, pads, data):
        self.pads = pads
        self.data = data
        self.sync += pads.rd_in.eq(pads.rd_out)
        pads.rxfl.reset = 1
        self.dat = Signal.like(pads.data)
        self.comb += [
                If(~pads.rdl,
                    pads.data.eq(self.dat),
                ).Else(
                    pads.data.eq(0x55),
                )
        ]
        self.state = "fill"
        self.wait = 10

    def do_simulation(self, selfp):
        self.wait = max(0, self.wait - 1)
        if self.state == "fill":
            selfp.pads.rxfl = 1
            if self.data and self.wait == 0:
                selfp.pads.rxfl = 0
                self.state = "read"
        elif self.state == "read":
            if selfp.pads.rdl == 0:
                self.wait = random.choice(self.t_setup)
                self.state = "setup"
        elif self.state == "setup":
            if self.wait == 0:
                selfp.dat = self.data.pop(0)
                self.state = "wait"
            if selfp.pads.rdl == 1:
                self.wait = random.choice(self.t_delay)
                self.state = "delay"
        elif self.state == "wait":
            if selfp.pads.rdl == 1:
                self.wait = random.choice(self.t_delay)
                self.state = "delay"
        elif self.state == "delay":
            if self.wait == 0:
                self.wait = random.choice(self.t_fill)
                self.state = "fill"


bus_layout = [("data", 8)]


class Ft245r_rx(Module):
    """FTDI FT345R synchronous reader.

    Args:
        pads (Record[ft345r_layout]): Pads to the FT245R.
        clk (float): Clock period in ns.

    Attributes:
        source (Endpoint[bus_layout]): 8 bit data source. Output.
        busy (Signal): Data available but not acknowledged by sink. Output.
    """
    def __init__(self, pads, clk=10.):
        self.source = do = Endpoint(bus_layout)
        self.busy = Signal()

        # t_RDLl_Dv = 50 ns (setup)
        # t_RDLh_Di = 0ns (hold)
        # t_RDLl_RDLh = 50 ns (redundant, <= r_RDLl_Dv)
        # t_RDLh_RXFLh = 25ns (from FT245R) (redundant, <= t_RDLh_RDLl)
        # t_RXFLh_RXFLl = 80ns (from FT245R)
        # t_RDLh_RDLl = 50ns + t_RXh_RXl (we understand this as a
        #    conditional addition)

        # we read every t_hold + t_precharge + t_setup + 2 cycles
        # can only sustain 1MByte/s anyway at full speed USB
        # stb implicitly needs to be acked within a read cycle
        #clk /= 4 # slow it down
        t_latch = int(ceil(50/clk)) + 2 # t_RDLl_Dv + slave skew
        t_drop = t_latch + 2  # slave skew
        t_refill = t_drop + int(ceil(50/clk))  # t_RDLh_RDLl

        reading = Signal()
        rxfl = Signal()
        rd_in = Signal()
        # proxy rxfl to slaves, drive rdl
        self.comb += [
                pads.rdl.eq(~pads.g1_out),
                self.busy.eq(~do.stb | do.ack)
        ]
        self.specials += [
            MultiReg(pads.rxfl, rxfl),
            MultiReg(pads.g1_in, rd_in),
        ]
        self.sync += [
                If(~reading & ~rd_in,
                   pads.g1_out.eq(~rxfl),
                ),
                do.stb.eq(do.stb & ~do.ack),
                timeline(rd_in, [
                    (0, [reading.eq(1)]),
                    (t_latch, [do.stb.eq(1), do.payload.data.eq(pads.data)]),
                    (t_drop, [pads.g1_out.eq(0)]),
                    (t_refill, [reading.eq(0)]),
                ])
        ]


class SimFt245r_rx(Ft245r_rx):
    comm_layout = [
        ("rxfl", 1),
        ("rdl", 1),
        ("rd_in", 1),
        ("rd_out", 1),
        ("data", 8),
    ]

    def __init__(self, data):
        pads = Record(self.comm_layout)
        Ft245r_rx.__init__(self, pads)
        self.submodules.ft245r_w = SimFt245r_rx_w(pads, data)
