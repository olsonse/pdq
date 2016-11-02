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

from gateware.platform import Platform
from gateware.pdq2 import Pdq2


def _main():
    for mems in (8, 6, 6), (10, 10), (20,):
        platform = Platform()
        pdq = Pdq2(platform, mem_depths=[i << 10 for i in mems])
        platform.build(pdq, build_name="pdq2_{}ch".format(len(mems)),
                       toolchain_path=os.environ.get("XILINX_PATH"))


if __name__ == "__main__":
    _main()
