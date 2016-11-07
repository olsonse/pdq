import logging
from io import BytesIO

from migen import *
from misoc.cores.spi import SPIMachine

from gateware.pdq2 import Pdq2Sim
from host import cli


logger = logging.getLogger(__name__)


class TB(Module):
    def __init__(self):
        self.submodules.m = m = SPIMachine(data_width=16, clock_width=8,
                                           bits_width=6)
        self.submodules.p = p = Pdq2Sim(mem_depths=[128, 128])
        self.comb += [
            p.ctrl_pads.frame[0].eq(~m.cs),
            p.ctrl_pads.frame[1].eq(m.cg.clk),
            p.ctrl_pads.frame[2].eq(m.reg.o),
            m.reg.i.eq(p.ctrl_pads.aux),
        ]

    @passive
    def watch_oe(self):
        while True:
            if (yield self.m.oe) and \
                    (yield self.p.dut.comm.spi.spi.oe_s):
                raise ValueError("doubly driven")
            yield

    def run_setup(self):
        yield self.m.clk_phase.eq(0)
        yield self.m.reg.lsb.eq(0)
        yield self.m.div_write.eq(2)
        yield self.m.div_read.eq(5)
        yield

    def _cmd(self, board, is_mem, adr, we):
        return (adr << 0) | (is_mem << 2) | (board << 3) | (we << 7)

    def write_reg(self, adr, data, board=0xf):
        yield self.m.bits.n_write.eq(16)
        yield self.m.bits.n_read.eq(0)
        yield self.m.reg.data.eq(
            (self._cmd(board, False, adr, True) << 8) | data)
        yield self.m.start.eq(1)
        yield
        yield self.m.start.eq(0)
        while not (yield self.m.done):
            yield
        for i in range(3):
            yield
        logger.info("[%s] <- %s", adr, data)

    def read_reg(self, adr, board=0xf):
        yield self.m.bits.n_write.eq(16)
        yield self.m.bits.n_read.eq(8)
        yield self.m.reg.data.eq(self._cmd(board, False, adr, False) << 8)
        yield self.m.start.eq(1)
        yield
        yield self.m.start.eq(0)
        while not (yield self.m.done):
            yield
        r = (yield self.m.reg.data) & 0xff
        for i in range(3):
            yield
        logger.info("[%s] -> %s", adr, r)
        return r

    def _config(self, reset=False, clk2x=False, enable=True,
                trigger=False, aux_miso=False, aux_dac=0b111):
        return ((reset << 0) | (clk2x << 1) | (enable << 2) |
                (trigger << 3) | (aux_miso << 4) | (aux_dac << 5))

    def test(self):
        for i in range(20):
            yield
        adr = 0
        data = self._config(reset=False, clk2x=False, enable=True,
                            trigger=False, aux_miso=True, aux_dac=0b111)
        board = 0xf
        yield from self.write_reg(adr, data, board)
        r = (yield from self.read_reg(adr, board))
        assert r == data, (r, data)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s.%(funcName)s:%(lineno)d] %(message)s")

    buf = BytesIO()
    # cli.main(buf)
    tb = TB()

    run_simulation(tb, [
        tb.run_setup(),
        tb.watch_oe(),
        tb.test(),
        # tb.p.write(buf.getvalue()),
    ], vcd_name="spi_pdq2.vcd")
    # out = np.array(tb.outputs, np.uint16).view(np.int16)
    # plt.plot(out)
