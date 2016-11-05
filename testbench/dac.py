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

from io import BytesIO

from migen import *

from matplotlib import pyplot as plt
import numpy as np

from gateware.dac import Dac
from host import pdq2


class TB(Module):
    def __init__(self, mem=None):
        self.submodules.dac = Dac()
        if mem is not None:
            self.dac.parser.mem.init = [int(i) for i in mem]
        self.outputs = []
        self.dac.parser.frame.reset = 0

    def run(self, ncycles):
        for i in range(ncycles):
            self.outputs.append((yield self.dac.out.data))
            if i == 5:
                yield self.dac.parser.start.eq(1)
                yield self.dac.parser.arm.eq(1)
                yield self.dac.out.arm.eq(1)
            elif i == 20:
                yield self.dac.out.trigger.eq(1)
            elif i == 21:
                yield self.dac.out.trigger.eq(0)
            yield
            if (yield self.dac.out.sink.ack) and \
                    (yield self.dac.out.sink.stb):
                print("cycle {} data {}".format(
                    i, (yield self.dac.out.data)))


_test_program = [
    [
        {
            "trigger": True,
            "duration": 20,
            "channel_data": [
                {"bias": {"amplitude": [0, 0, 2e-3]}},
                {"bias": {"amplitude": [1, 0, -7.5e-3, 7.5e-4]}},
                {"dds": {
                    "amplitude": [0, 0, 4e-3, 0],
                    "phase": [.25, .025],
                }},
            ],
        },
        {
            "duration": 40,
            "channel_data": [
                {"bias": {"amplitude": [.4, .04, -2e-3]}},
                {
                    "bias": {"amplitude": [.5]},
                    "silence": True,
                },
                {"dds": {
                    "amplitude": [.8, .08, -4e-3, 0],
                    "phase": [.25, .025, .02/40],
                    "clear": True,
                }},
            ],
        },
        {
            "duration": 20,
            "channel_data": [
                {"bias": {"amplitude": [.4, -.04, 2e-3]}},
                {"bias": {"amplitude": [.5, 0, -7.5e-3, 7.5e-4]}},
                {"dds": {
                    "amplitude": [.8, -.08, 4e-3, 0],
                    "phase": [-.25],
                }},
            ],
        },
    ]
]


def _main():
    import logging
    logging.basicConfig(level=logging.DEBUG)

    # from migen.fhdl import verilog
    # print(verilog.convert(Dac()))

    p = pdq2.Pdq2(dev=BytesIO())
    p.program(_test_program)
    mem = p.channels[0].serialize()
    tb = TB(list(np.fromstring(mem, "<u2")))
    run_simulation(tb, tb.run(400), vcd_name="dac.vcd")

    out = np.array(tb.outputs, np.uint16).view(np.int16)
    plt.step(np.arange(len(out)) - 22, out, "-r")
    plt.show()


if __name__ == "__main__":
    _main()
