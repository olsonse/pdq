# Copyright 2016 Robert Jordens <jordens@gmail.com>
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
from migen.sim import run_simulation
from migen.fhdl import verilog
from gateware.comm import Protocol


class TB(Module):
    def __init__(self):
        self.mems = [Memory(16, 4, init=[i]) for i in range(3)]
        self.specials += self.mems
        self.submodules.proto = Protocol(self.mems)
        self.comb += self.proto.board.eq(0b0101)

    def test(self):
        for i in range(10):
            yield

        # test broadcast
        yield from self.seq([(1 << 7) | (0b1111 << 3) | (0 << 2) | (0 << 0),
                             0x5a])
        r = (yield self.proto.config.raw_bits())
        assert r == 0x5a, r

        # test wrong board/ignore
        yield from self.seq([(1 << 7) | (0b1000 << 3) | (0 << 2) | (0 << 0),
                             0xa5])
        r = (yield self.proto.config.raw_bits())
        assert r == 0x5a, r

        # test reg write
        yield from self.seq([(1 << 7) | (0b0101 << 3) | (0 << 2) | (0 << 0),
                             0xa5])
        r = (yield self.proto.config.raw_bits())
        assert r == 0xa5, r

        # test reg read
        r = (yield from self.seq([
            (0 << 7) | (0b0101 << 3) | (0 << 2) | (0 << 0),
            0x00]))
        assert r == [0xa5], r

        # test write
        yield from self.seq([
            (1 << 7) | (0b0101 << 3) | (1 << 2) | (0 << 0),
            0x00, 0x10, 0x01, 0x00])
        r = (yield self.mems[0][0])
        assert r == 0x0001, hex(r)
        yield from self.seq([
            (1 << 7) | (0b0101 << 3) | (1 << 2) | (0 << 0),
            0x02, 0x20, 0x02, 0x00])
        r = (yield self.mems[0][1])
        assert r == 0x0002, hex(r)
        yield from self.seq([
            (1 << 7) | (0b0101 << 3) | (1 << 2) | (2 << 0),
            0x04, 0x30, 0x0f, 0x10])
        r = (yield self.mems[2][2])
        assert r == 0x100f, hex(r)

        # test read
        r = (yield from self.seq([
            (0 << 7) | (0b0101 << 3) | (1 << 2) | (2 << 0),
            0x04, 0x30, 0x00, 0x00]))
        assert r == [0x0f, 0x10], r

        # test multi write
        yield from self.seq([
            (1 << 7) | (0b0101 << 3) | (1 << 2) | (0 << 0),
            0x02, 0x00, 0x01, 0x10, 0x02, 0x20, 0x03, 0x30])
        r = yield from [(yield self.mems[0][i]) for i in range(1, 4)]
        assert r == [0x1001, 0x2002, 0x3003], r

        # test multi read
        r = yield from self.seq([
            (0 << 7) | (0b0101 << 3) | (1 << 2) | (0 << 0),
            0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        assert r == [0x01, 0x10, 0x02, 0x20, 0x03, 0x30], r


    def seq(self, seq):
        yield self.proto.sink.eop.eq(0)
        yield
        r = []
        for d in seq:
            yield
            yield self.proto.sink.data.eq(d)
            yield self.proto.sink.stb.eq(1)
            yield
            print("mosi {:#02x}".format(d))
            if (yield self.proto.source.stb):
                d = (yield self.proto.source.data)
                r.append(d)
                print("miso {:#02x}".format(d))
            yield self.proto.sink.stb.eq(0)
            yield
        yield self.proto.sink.eop.eq(1)
        yield
        return r


if __name__ == "__main__":
    # print(verilog.convert(TB()))
    tb = TB()
    run_simulation(tb, tb.test(),
                   vcd_name="protocol.vcd")
