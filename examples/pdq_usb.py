import numpy as np

from artiq.experiment import *
from artiq.wavesynth.coefficients import build_segment


class PDQ2Simple(EnvExperiment):
    """PDQ example using both the USB and SPI connections.

    The example ``device_db.py`` contains several PDQ entries. One for SPI from
    the core device (RTIO) that is used to perform trigger and frame selection
    commands in this example.
    The other entry covers a USB connected PDQ (but could equally cover
    multiple USB connected PDQs). It's used to write to the memory and owns the
    hardware trigger channel.

    .. note:: The ``pdq_usb`` controler needs to be started (either using
              ``artiq_ctlmgr`` or manually with the correct options).
    """
    def build(self):
        self.setattr_device("core")
        self.setattr_device("led")
        self.setattr_device("pdq_usb")
        self.setattr_device("pdq_spi")

        # 1 device, 3 board each, 3 dacs each
        self.u = np.arange(4*3)[None, :, None]*.1

    def setup(self, offset):
        self.pdq_usb.disarm()
        self.load = self.pdq_usb.create_frame()
        segment = self.load.create_segment()
        for line in build_segment([100], self.u + offset):
            segment.add_line(**line)
        self.detect = self.pdq_usb.create_frame()
        segment = self.detect.create_segment()
        for line in build_segment([100], -self.u + offset):
            segment.add_line(**line)
        self.pdq_usb.arm()

    @kernel
    def one(self):
        self.core.break_realtime()
        self.pdq.setup_bus()
        delay(1*ms)
        self.pdq_spi.set_frame(self.load.frame_number)
        self.pdq_usb.trigger.pulse(1*us)
        delay(1*ms)
        self.pdq_spi.set_frame(self.detect.frame_number)
        self.pdq_usb.trigger.pulse(1*us)
        delay(1*ms)

    def run(self):
        self.core.reset()
        offsets = np.arange(0, 3)
        for o in offsets:
            self.setup(o)
            self.one()
