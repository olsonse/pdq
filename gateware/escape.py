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

from migen import *
from misoc.interconnect.stream import Endpoint, Demultiplexer


class Unescaper(Demultiplexer):
    """Split a data stream into an escaped low bandwidth command stream and an
    unescaped high bandwidth data stream.

    Items in the input stream that are escaped by being prefixed with the
    escape character, will be directed to the :attr:`source_b` output Endpoint.

    Items that are not escaped, and the escaped escape character itself are
    directed at the :attr:`source_a` output Endpoint.

    Args:
        layout (layout): Stream layout to split.
        escape (int): Escape character.

    Attributes:
        sink (Endpoint[layout]): Input stream.
        source0 (Endpoint[layout]): High bandwidth unescaped data Endpoint.
        source1 (Endpoint[layout]): Low bandwidth command Endpoint.
    """
    def __init__(self, layout, escape=0xa5):
        super(Unescaper, self).__init__(layout, 3)

        ###

        dump = self.source2
        del self.source2

        is_escape = Signal()
        was_escape = Signal()

        self.sync += [
                If(self.sink.ack & self.sink.stb,
                    was_escape.eq(is_escape & ~was_escape)
                )
        ]

        self.comb += [
                dump.ack.eq(1),
                is_escape.eq(self.sink.payload.raw_bits() == escape),
                If(is_escape == was_escape,  # data, source0
                    self.sel.eq(0),
                ).Elif(is_escape,  # swallow, dump
                    self.sel.eq(2),
                ).Else(  # command, source1
                    self.sel.eq(1),
                )
        ]
