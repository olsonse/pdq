import logging
from itertools import count
from io import BytesIO

from migen import *
from misoc.cores.spi import SPIMachine

from gateware.pdq2 import Pdq2Sim
from host import cli
from host.pdq2 import crc8


logger = logging.getLogger(__name__)


class TB(Module):
    def __init__(self):
        self.submodules.m = m = SPIMachine(data_width=32, clock_width=8,
                                           bits_width=6)
        self.submodules.p = p = Pdq2Sim(mem_depths=[128, 128])
        self.comb += [
            p.ctrl_pads.frame[0].eq(~m.cs),
            p.ctrl_pads.frame[1].eq(m.cg.clk),
            p.ctrl_pads.frame[2].eq(m.reg.o),
            m.reg.i.eq(p.ctrl_pads.aux),
        ]
        self.checksum = 0

    def crc(self, m):
        self.checksum = crc8(m, self.checksum)
        logger.debug("crc %#4x", self.checksum)
        return self.checksum

    @passive
    def watch_oe(self):
        for i in count():
            if (yield self.m.oe) and \
                    (yield self.p.dut.comm.spi.spi.oe_s):
                logger.error("miso/mosi doubly driven %d", i)
            yield

    @passive
    def log_xfers(self, xfers):
        cs = self.m.cs
        clk = self.m.cg.clk
        mosi = self.m.reg.o
        miso = self.m.reg.i
        clk1 = 0
        while True:
            yield
            clk0, clk1 = clk1, (yield clk)
            if not (yield cs):
                bit = b_mosi = b_miso = 0
                packet = []
                continue
            if not (clk1 and not clk0):
                continue
            b_mosi = (b_mosi << 1) | (yield mosi)
            b_miso = (b_miso << 1) | (yield miso)
            bit += 1
            if bit == 8:
                if not packet:
                    xfers.append(packet)
                    logger.info("new xfer")
                logger.info("xfer byte %#04x %#04x", b_mosi, b_miso)
                packet.append((b_mosi, b_miso))
                bit = b_mosi = b_miso = 0

    def run_setup(self):
        yield self.m.clk_phase.eq(0)
        yield self.m.reg.lsb.eq(0)
        yield self.m.div_write.eq(2)
        yield self.m.div_read.eq(5)
        yield

    def _cmd(self, board, is_mem, adr, we):
        return (adr << 0) | (is_mem << 2) | (board << 3) | (we << 7)

    def xfer(self, wdata, wlen=8, rlen=0):
        yield self.m.bits.n_write.eq(wlen)
        yield self.m.bits.n_read.eq(rlen)
        yield self.m.reg.data.eq(wdata)
        yield self.m.start.eq(1)
        yield
        yield self.m.start.eq(0)
        while not (yield self.m.done):
            yield
        return (yield self.m.reg.data)

    def write_reg(self, adr, data, board=0xf):
        cmd = self._cmd(board, False, adr, True)
        yield from self.xfer((cmd << 24) | (data << 16), 16)
        self.crc([cmd, data])
        logger.info("reg[%#04x] <- %#04x", adr, data)
        for i in range(6):
            yield

    def read_reg(self, adr, board=0xf):
        cmd = self._cmd(board, False, adr, False)
        data = (yield from self.xfer((cmd << 24), 16, 8)) & 0xff
        self.checksum_read = self.crc([cmd])
        self.crc([0])
        logger.info("reg[%#04x] -> %#04x", adr, data)
        for i in range(10):
            yield
        return data

    def write_mem(self, mem, adr, data, board=0xf):
        cmd = self._cmd(board, True, mem, True)
        yield from self.xfer((cmd << 24) | (adr << 8), 24)
        self.crc([cmd, adr])
        logger.info("mem[%#04x][%#04x]:", mem, adr)
        for i in data:
            yield
            yield from self.xfer(i << 24, 8, 0)
            logger.info("  <- %#04x", i)
        self.crc(list(data))
        for i in range(6):
            yield

    def read_mem(self, mem, adr, len, board=0xf):
        cmd = self._cmd(board, True, mem, False)
        yield from self.xfer((cmd << 24) | (adr << 8), 24)
        self.crc([0])
        logger.info("mem[%#04x][%#04x]:", mem, adr)
        data = []
        for i in range(len):
            yield
            data.append((yield from self.xfer(0, 0, 8)))
            logger.info("  -> %#04x", data[-1])
        for i in range(10):
            yield
        return data

    def _config(self, reset=False, clk2x=False, enable=True,
                trigger=False, aux_miso=False, aux_dac=0b111):
        return ((reset << 0) | (clk2x << 1) | (enable << 2) |
                (trigger << 3) | (aux_miso << 4) | (aux_dac << 5))

    def test(self):
        for i in range(20):
            yield

        if False:
            adr = 0
            data = self._config(aux_miso=True)
            yield from self.write_reg(adr, data)
            r = (yield self.p.dut.comm.proto.config.raw_bits())
            assert r == data, (r, data)
            r = (yield from self.read_reg(adr))
            assert r == data, (r, data)

            adr = 1
            data = 0xa5
            yield from self.write_reg(adr, data)
            r = (yield self.p.dut.comm.proto.checksum)
            assert r == data, (r, data)
            self.checksum = data
            r = (yield from self.read_reg(adr))
            assert r == self.checksum_read, (r, self.checksum_read)

            adr = 2
            data = 0x1a
            yield from self.write_reg(adr, data)
            r = (yield self.p.dut.comm.proto.frame)
            assert r == data, (r, data)
            r = (yield from self.read_reg(adr))
            assert r == data, (r, data)

            adr = 1
            r = (yield from self.read_reg(adr))
            assert r == self.checksum_read, (r, self.checksum_read)

        mem = 1
        adr = 2
        data = (yield from self.read_mem(mem, adr, 3))

        mem = 1
        adr = 2
        data = [0x12, 0x93, 0x99]
        yield from self.write_mem(mem, adr, data)
        datar = (yield from self.read_mem(mem, adr, len(data)))
        assert data == datar, (data, datar)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s.%(funcName)s:%(lineno)d] %(message)s")

    buf = BytesIO()
    # cli.main(buf)
    tb = TB()

    xfers = []
    run_simulation(tb, [
        tb.run_setup(),
        tb.watch_oe(),
        tb.log_xfers(xfers),
        tb.test(),
        # tb.p.write(buf.getvalue()),
    ], vcd_name="spi_pdq2.vcd")
    # out = np.array(tb.outputs, np.uint16).view(np.int16)
    # plt.plot(out)
    print(xfers)
