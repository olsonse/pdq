#!/usr/bin/python3
# Copyright 2013-2015 Robert Jordens <jordens@gmail.com>
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

import argparse

from gateware.platform import Platform
from gateware.pdq import Pdq


def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-x", "--xilinx", default=None)
    parser.add_argument("-c", "--config", help="Configurations to build. "
            "The configuration is the number of DAC channels supported "
            "(1, 2, or 3). Can be specified multiple times to build multiple "
            "configurations. Default is to build all three configuations. "
            "Waveform memory is distributed among the channels.",
            default=[], type=int, action="append")
    args = parser.parse_args()

    if not args.config:
        args.config = [3, 2, 1]
    for config in args.config:
        mems = [None, (20,), (10, 10), (8, 6, 6)][config]
        platform = Platform()
        pdq = Pdq(platform, mem_depths=[i << 10 for i in mems])
        platform.build(pdq, build_name="pdq_{}ch".format(config),
                       toolchain_path=args.xilinx)


if __name__ == "__main__":
    _main()
