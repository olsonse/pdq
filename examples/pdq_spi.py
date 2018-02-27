from artiq.experiment import *


class PDQ2SPI(EnvExperiment):
    """
    Example experiment controling a PDQ board stack from ARTIQ over SPI.

    This assumes a working ARTIQ installation (see the ARTIQ manual), working
    and configured core device (e.g. KC705), and a hardware adapter with
    an RTIO SPI master connected to the PDQ's SPI bus (see the PDQ or ARTIQ
    manual).
    After building the desired PDQ bitstream flash that bitstream to the
    boards (see the PDQ manual).

    Example device_db entries are provided in device_db.pyon. Adapt them to
    your specific situation.
    """
    def build(self):
        self.setattr_device("core")
        self.setattr_device("pdq")
        self.setattr_device("led")

    @kernel
    def run(self):
        self.core.reset()
        self.core.break_realtime()
        self.pdq.setup_bus(write_div=50, read_div=50)
        self.pdq.set_config(reset=1)

        for i in range(100):
            delay(80*us)
            self.led.on()
            self.pdq.set_config(clk2x=1, trigger=0, enable=0, aux_miso=1)
            self.pdq.set_crc(0)
            self.pdq.set_frame(0)
            self.led.off()

        self.test_reg()
        self.test_mem()

    @kernel
    def trigger(self):
        """Example showing how to trigger a PDQ stack over SPI: set and clear
        the trigger flag in the configuration register"""
        self.pdq.set_config(clk2x=1, trigger=1, enable=0, aux_miso=1)
        delay(2*us)
        self.pdq.set_config(clk2x=1, trigger=0, enable=0, aux_miso=1)

    @kernel
    def test_reg(self):
        for i in range(100):
            self.pdq.set_config(reset=1)
            delay(100*us)
            self.led.on()
            self.pdq.set_config(clk2x=1, trigger=0, enable=0, aux_miso=1)
            delay(100*us)
            if self.pdq.get_config() != 242:
                raise ValueError("wrong config")
            delay(100*us)
            if self.pdq.get_frame() != 0:
                raise ValueError("wrong frame")
            delay(100*us)
            self.pdq.set_crc(0)
            if self.pdq.get_crc() != 104:
                raise ValueError("wrong crc")
            delay(100*us)
            self.pdq.set_frame(25)
            if self.pdq.get_frame() != 25:
                raise ValueError("wrong frame")
            delay(100*us)
            if self.pdq.get_crc() == 104:
                raise ValueError("wrong frame")
            delay(100*us)
            self.led.off()

    @kernel
    def test_mem(self):
        self.pdq.setup_bus(write_div=24, read_div=64)
        for i in range(100):
            self.pdq.set_config(reset=1)
            delay(100*us)
            self.led.on()
            self.pdq.set_config(clk2x=1, trigger=0, enable=0, aux_miso=1)
            delay(100*us)
            data_write = [1, 2, 3, 4, 5, 6, 7, 8]
            self.pdq.write_mem(0, 0, data_write)
            data_read = [0]*(len(data_write) + 1)
            self.pdq.read_mem(0, 0, data_read)
            for i in range(len(data_write)):
                if data_read[i] != data_write[i]:
                    print(data_read)
                    raise ValueError("wrong memory")
            delay(100*us)
            self.led.off()
