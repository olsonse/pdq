class PDQ2SPI(EnvExperiment):
    """
    Example experiment controling a PDQ board stack from ARTIQ over SPI.

    This assumes a working ARTIQ installation (see the ARTIQ manual), working
    and configured core device (e.g. KC705), and a hardware adapter with
    an RTIO SPI master connected to the PDQ's SPI bus (see the PDQ or ARTIQ
    manual).
    After building the desired PDQ bitstream flash that bitstream to the
    boards (see the PDQ manual).

    Add a device_db entry for the pdq on spi to along the lines
    (a dapt to your specific setup):

    "pdq0": {
        "type": "local",
        "module": "artiq.coredevice.pdq",
        "class": "PDQ",
        "arguments": {"spi_device": "spi_sma", "chip_select": 1}
    }
    """
    def build(self):
	self.setattr_device("core")
	self.setattr_device("pdq0")
	self.setattr_device("led")

    @kernel
    def run(self):
	self.core.reset()
	self.core.break_realtime()
	self.pdq0.setup_bus(write_div=50, read_div=50)
	self.pdq0.write_config(reset=1)

	for i in range(100):
	    delay(80*us)
	    self.led.on()
	    self.pdq0.write_config(clk2x=1, trigger=0, enable=0, aux_miso=1)
	    self.pdq0.write_crc(0)
	    self.pdq0.write_frame(0)
	    self.led.off()
