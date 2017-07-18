import logging
from migen import *

from misoc.cores.liteeth_mini.mac.crc import LiteEthMACCRCEngine
from pdq.host.pdq import crc8

logger = logging.getLogger(__name__)


class TB(Module):
    def __init__(self, polynom=0x07):
        self.submodules.crc = LiteEthMACCRCEngine(
            data_width=8, width=8, polynom=polynom)
        self.din = Signal(8)
        self.comb += self.crc.data.eq(self.din[::-1])
        self.sync += self.crc.last.eq(self.crc.next)

    def run_data(self, data, out):
        yield self.crc.last.eq(0)
        for i in data:
            yield self.din.eq(i)
            yield
            out.append((yield self.crc.next))


def test():
    from migen.fhdl import verilog
    tb = TB(0x07)
    out = []
    m = b"123456789"
    run_simulation(tb, tb.run_data(m, out), vcd_name="crc.vcd")
    assert out[-1] == crc8(m)


if __name__ == "__main__":
    test()
