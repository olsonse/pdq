import logging
import struct

import serial

from .protocol import PDQBase, crc8, PDQ_CMD


logger = logging.getLogger(__name__)


class PDQ(PDQBase):
    def __init__(self, url=None, dev=None, **kwargs):
        """Initialize PDQ USB/Parallel device stack.

        .. note:: This device should only be used if the PDQ is intended to be
           configured using the USB connection and **not** via SPI.

        Args:
            url (str): Pyserial device URL. Can be ``hwgrep://`` style
                (search for serial number, bus topology, USB VID:PID
                combination), ``COM15`` for a Windows COM port number,
                ``/dev/ttyUSB0`` for a Linux serial port.
            dev (file-like): File handle to use as device. If passed, ``url``
                is ignored.
            **kwargs: See :class:`PDQBase` .
        """
        if dev is None:
            dev = serial.serial_for_url(url)
        self.dev = dev
        PDQBase.__init__(self, **kwargs)

    def write(self, data):
        """Write data to the PDQ board over USB/parallel.

        SOF/EOF control sequences are appended/prepended to
        the (escaped) data. The running checksum is updated.

        Args:
            data (bytes): Data to write.
        """
        logger.debug("> %r", data)
        msg = b"\xa5\x02" + data.replace(b"\xa5", b"\xa5\xa5") + b"\xa5\x03"
        written = self.dev.write(msg)
        if isinstance(written, int):
            assert written == len(msg), (written, len(msg))
        self.checksum = crc8(data, self.checksum)

    def set_reg(self, adr, data, board):
        self.write(bytes([PDQ_CMD(board, 0, adr, 1), data]))

    def write_mem(self, mem, adr, data, board=0xf):
        self.write(bytes([PDQ_CMD(board, 1, mem, 1), adr & 0xff, adr >> 8]) +
                data)

    def close(self):
        """Close the USB device handle."""
        self.dev.close()
        del self.dev

    def flush(self):
        """Flush pending data."""
        self.dev.flush()
