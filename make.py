#!/usr/bin/python3
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

import os
import argparse

from gateware.platform import Platform
from gateware.pdq2 import Pdq2



def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-x", "--xilinx", default=None)
    parser.add_argument("-c", "--config", default=[], type=int, action="append")
    args = parser.parse_args()

    if not args.config:
        args.config = [3, 2, 1]
    for config in args.config:
        mems = [None, (20,), (10, 10), (8, 6, 6)][config]
        platform = Platform()
        pdq = Pdq2(platform, mem_depths=[i << 10 for i in mems])
        platform.build(pdq, build_name="pdq2_{}ch".format(config),
                       toolchain_path=args.xilinx)


if __name__ == "__main__":
    _main()
