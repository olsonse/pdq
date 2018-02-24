from artiq.language.core import kernel, delay_mu
from artiq.coredevice import spi2 as spi

from ..host.protocol import PDQBase, PDQ_CMD


_PDQ_SPI_CONFIG = (
        0*spi.SPI_OFFLINE | 0*spi.SPI_END |
        0*spi.SPI_INPUT | 0*spi.SPI_CS_POLARITY |
        0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
        0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX
        )


class PDQ(PDQBase):
    """PDQ smart arbitrary waveform generator stack.

    Provides access to a stack of PDQ boards connected via SPI using PDQ
    gateware version 3 or later.

    The SPI bus is wired with ``CS_N`` from the core device connected to
    ``F2 IN`` on the master PDQ, ``CLK`` connected to ``F3 IN``, ``MOSI``
    connected to ``F4 IN`` and ``MISO`` (optionally) connected to ``F5 OUT``.
    ``F1 TTL Input Trigger`` remains as waveform trigger input.
    Due to hardware constraints, there can only be one board connected to the
    core device's MISO line and therefore there can only be SPI readback
    from one board at any time.

    :param spi_device: Name of the SPI bus this device is on.
    :param chip_select: Value to drive on the chip select lines of the SPI bus
        during transactions.
    :param write_div: Write clock divider.
    :param read_div: Read clock divider.
    """
    kernel_invariants = {"core", "chip_select", "bus",
                         "write_div", "read_div"}

    def __init__(self, dmgr, spi_device, chip_select=1, write_div=24,
            read_div=64, **kwargs):
        self.core = dmgr.get("core")
        self.bus = dmgr.get(spi_device)
        self.chip_select = chip_select
        # write: 4*8ns >= 20ns = 2*clk (clock de-glitching 50MHz)
        # read: 15*8*ns >= ~100ns = 5*clk (clk de-glitching latency + miso
        #   latency)
        self.write_div = write_div
        self.read_div = read_div
        PDQBase.__init__(self, **kwargs)

    @kernel
    def setup_bus(self):
        """Configure the SPI bus and the SPI transaction parameters
        for this device. This method has to be called before any other method
        if the bus has been used to access a different device in the meantime.
        """
        self.bus.set_config_mu(_PDQ_SPI_CONFIG | spi.SPI_END, 16,
                               self.write_div, self.chip_select)

    @kernel
    def set_reg(self, adr, data, board):
        """Set a PDQ register.

        :param adr: Address of the register (``_PDQ_ADR_CONFIG``,
            ``_PDQ_ADR_FRAME``, ``_PDQ_ADR_CRC``).
        :param data: Register data (8 bit).
        :param board: Board to access, ``0xf`` to write to all boards.
        """
        self.bus.write((PDQ_CMD(board, 0, adr, 1) << 24) | (data << 16))

    @kernel
    def get_reg(self, adr, board):
        """Get a PDQ register.

        :param adr: Address of the register (``_PDQ_ADR_CONFIG``,
          ``_PDQ_ADR_FRAME``, ``_PDQ_ADR_CRC``).
        :param board: Board to access, ``0xf`` to write to all boards.

        :return: Register data (8 bit).
        """
        self.bus.set_config_mu(_PDQ_SPI_CONFIG | spi.SPI_END | spi.SPI_INPUT,
                               24, self.read_div, self.chip_select)
        self.bus.write(PDQ_CMD(board, 0, adr, 0) << 24)
        self.setup_bus()
        return self.bus.read() & 0xff

    @kernel
    def write_mem(self, mem, adr, data, board=0xf):  # FIXME: m-labs/artiq#714
        """Write to DAC channel waveform data memory.

        :param mem: DAC channel memory to access (0 to 2).
        :param adr: Start address.
        :param data: Memory data. List of 16 bit integers. The data will be
            transferred little endian (low byte first).
        :param board: Board to access (0-15) with ``0xf = 15`` being broadcast
            to all boards.
        """
        n = len(data)
        if not n:
            return
        self.bus.set_config_mu(_PDQ_SPI_CONFIG,
                               24, self.write_div, self.chip_select)
        self.bus.write((PDQ_CMD(board, 1, mem, 1) << 24) |
                       ((adr & 0x00ff) << 16) | (adr & 0xff00))
        self.bus.set_config_mu(_PDQ_SPI_CONFIG,
                               16, self.write_div, self.chip_select)
        for i in range(n):
            if i == n - 1:
                self.bus.set_config_mu(_PDQ_SPI_CONFIG | spi.SPI_END,
                                       16, self.write_div, self.chip_select)
            v = data[i]
            v = ((v & 0xff00) >> 8) | ((v & 0x00ff) << 8)
            self.bus.write(v << 16)
        self.setup_bus()

    @kernel
    def read_mem(self, mem, adr, data, board=0xf, buffer=4):
        """Read from DAC channel waveform data memory.

        :param mem: DAC channel memory to access (0 to 2).
        :param adr: Start address.
        :param data: Memory data. List of 16 bit integers.
        :param board: Board to access (0-15) with ``0xf = 15`` being broadcast
            to all boards.
        """
        n = len(data)
        if not n:
            return
        self.bus.set_config_mu(_PDQ_SPI_CONFIG,
                               32, self.read_div, self.chip_select)
        self.bus.write((PDQ_CMD(board, 1, mem, 0) << 24) |
                       ((adr & 0x00ff) << 16) | (adr & 0xff00))
        self.bus.set_config_mu(_PDQ_SPI_CONFIG | spi.SPI_INPUT,
                               16, self.read_div, self.chip_select)
        for i in range(n):
            if i == n - 1:
                self.bus.set_config_mu(_PDQ_SPI_CONFIG | spi.SPI_INPUT |
                                       spi.SPI_END, 16, self.read_div,
                                       self.chip_select)
            self.bus.write(0)
            if i > buffer:
                v = self.bus.read()
                v = ((v & 0xff00) >> 8) | ((v & 0x00ff) << 8)
                data[i - buffer] = v
        for i in range(max(0, n - buffer), n):
            v = self.bus.read()
            v = ((v & 0xff00) >> 8) | ((v & 0x00ff) << 8)
            data[i] = v
        self.setup_bus()
