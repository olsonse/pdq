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
from migen.sim import run_simulation

from gateware.escape import Unescaper


data_layout = [("data", 8)]


def _test_unescaper(dut, data, aout, bout):
    yield dut.source0.ack.eq(1)
    yield dut.source1.ack.eq(1)
    for i in data:
        yield dut.sink.data.eq(i)
        yield dut.sink.stb.eq(1)
        yield
        while True:
            if (yield dut.source0.stb):
                aout.append((yield dut.source0.data))
            if (yield dut.source1.stb):
                bout.append((yield dut.source1.data))
            if (yield dut.sink.ack):
                break
            yield
        yield dut.sink.stb.eq(0)


if __name__ == "__main__":
    data = [1, 2, 0xa5, 3, 4, 0xa5, 0xa5, 5, 6, 0xa5, 0xa5, 0xa5, 7, 8,
            0xa5, 0xa5, 0xa5, 0xa5, 9, 10]
    aexpect = [1, 2, 4, 0xa5, 5, 6, 0xa5, 8, 0xa5, 0xa5, 9, 10]
    bexpect = [3, 7]
    dut = Unescaper(data_layout)
    aout = []
    bout = []
    run_simulation(dut, _test_unescaper(dut, data, aout, bout),
                   vcd_name="escape.vcd")
    assert aout == aexpect, (aout, aexpect)
    assert bout == bexpect, (bout, bexpect)
