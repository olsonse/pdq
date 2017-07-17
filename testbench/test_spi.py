# Copyright 2016-2017 Robert Jordens <jordens@gmail.com>
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


import logging
from migen import *
from misoc.cores.spi import SPIMachine

from gateware.spi import SPISlave

logger = logging.getLogger(__name__)


class TB(Module):
    def __init__(self):
        self.submodules.m = m = SPIMachine(data_width=16, clock_width=8,
                                           bits_width=6)
        self.submodules.s = s = SPISlave()
        self.comb += [
            s.reset.eq(s.cs_n),
            s.spi.cs_n.eq(~m.cs),
            s.spi.clk.eq(m.cg.clk),
            s.spi.mosi.eq(m.reg.o),
            m.reg.i.eq(s.spi.miso),
            s.spi.oe_m.eq(m.oe),
        ]

    def run_setup(self):
        yield self.m.clk_phase.eq(0)
        yield self.m.reg.lsb.eq(0)
        yield self.m.div_write.eq(2)
        yield self.m.div_read.eq(5)
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
        yield self.s.miso.data.eq(i)
        yield self.s.miso.stb.eq(1)
        while not (yield self.s.mosi.stb):
            yield
        r = (yield self.s.mosi.data), (yield self.s.mosi.eop)
        yield self.s.miso.stb.eq(0)
        yield
        return r


def test():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s.%(funcName)s:%(lineno)d] %(message)s")
    from migen.fhdl import verilog
    print(verilog.convert(SPISlave()))
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


if __name__ == "__main__":
    test()
