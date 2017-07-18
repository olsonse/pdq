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
from io import BytesIO

from migen import run_simulation


from pdq.host import cli
from .test_spi_pdq import TB


logger = logging.getLogger(__name__)


def test():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s.%(funcName)s:%(lineno)d] %(message)s")

    buf = BytesIO()
    cli.main(buf, args=[])
    tb = TB()

    xfers = []
    cmds = []
    run_simulation(tb, [
        tb.watch_oe(),
        tb.log_xfers(xfers),
        tb.log_cmds(cmds),
        tb.write(buf.getvalue()),
    ], vcd_name="spi_pdq.vcd")
    # out = np.array(tb.outputs, np.uint16).view(np.int16)
    # plt.plot(out)
    # print(xfers)


if __name__ == "__main__":
    test()
