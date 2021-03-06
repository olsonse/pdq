# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

import unittest
import os
import io

from migen import run_simulation

try:
    from artiq.wavesynth.compute_samples import Synthesizer
except ImportError:
    Synthesizer = None

from ..gateware.pdq import PdqSim
from ..host.usb import PDQ


@unittest.skipUnless(Synthesizer, "no artiq found")
class TestPdq(unittest.TestCase):
    def setUp(self):
        self.dev = PDQ(dev=io.BytesIO())
        self.synth = Synthesizer(3, _test_program)

    def test_reset(self):
        self.dev.set_config(reset=True)
        buf = self.dev.dev.getvalue()
        self.assertEqual(buf, b"\xa5\x02\xf8\xe5\xa5\x03")

    def test_program(self):
        # about 0.14 ms
        self.dev.program(_test_program)

    def test_cmd_program(self):
        self.dev.set_config(enable=False)
        self.dev.program(_test_program)
        self.dev.set_config(enable=True, trigger=True)
        return self.dev.dev.getvalue()

    def test_synth(self):
        s = self.synth
        s.select(0)
        y = s.trigger()
        return list(zip(*y))

    def run_gateware(self):

        def ncycles(n):
            for i in range(n):
                yield

        buf = self.test_cmd_program()
        tb = PdqSim()
        tb.ctrl_pads.trigger.reset = 1
        delays = 11, 14, 34
        run_simulation(tb, [
            tb.write(buf),
            tb.record(),
            ncycles(len(buf) + 80 + max(delays)),
        ])
        y = list(zip(*tb.outputs[len(buf):]))
        y = list(zip(*(yi[di:] for yi, di in zip(y, delays))))
        self.assertGreaterEqual(len(y), 80)
        self.assertEqual(len(y[0]), 3)
        return y

    def test_run_compare(self):
        y_ref = self.test_synth()
        y = self.run_gateware()

        for i, (yi, yi_ref) in enumerate(zip(y, y_ref)):
            for j, (yij, yij_ref) in enumerate(zip(yi, yi_ref)):
                yij = yij*20./2**16
                if yij > 10:
                    yij -= 20
                self.assertAlmostEqual(yij, yij_ref, 2, "disagreement at "
                                       "t={}, c={}".format(i, j))

    @unittest.skip("manual/visual test")
    def test_run_plot(self):
        from matplotlib import pyplot as plt
        import numpy as np
        y_ref = self.test_synth()
        y_ref = np.array(y_ref)
        y = self.run_gateware()
        y = np.array(y, dtype=np.uint16).view(np.int16)
        y = y*20./2**16
        plt.step(np.arange(len(y)), y)
        plt.step(np.arange(len(y_ref)), y_ref, linestyle="dotted")
        plt.show()


_test_program = [
    [
        {
            "trigger": True,
            "duration": 20,
            "channel_data": [
                {"bias": {"amplitude": [0, 0, 2e-3]}},
                {"bias": {"amplitude": [1, 0, -7.5e-3, 7.5e-4]}},
                {"dds": {
                    "amplitude": [0, 0, 4e-3, 0],
                    "phase": [.25, .025],
                }},
            ],
        },
        {
            "duration": 40,
            "channel_data": [
                {"bias": {"amplitude": [.4, .04, -2e-3]}},
                {
                    "bias": {"amplitude": [.5]},
                    "silence": True,
                },
                {"dds": {
                    "amplitude": [.8, .08, -4e-3, 0],
                    "phase": [.25, .025, .02/40],
                    "clear": True,
                }},
            ],
        },
        {
            "duration": 20,
            "channel_data": [
                {"bias": {"amplitude": [.4, -.04, 2e-3]}},
                {"bias": {"amplitude": [.5, 0, -7.5e-3, 7.5e-4]}},
                {"dds": {
                    "amplitude": [.8, -.08, 4e-3, 0],
                    "phase": [-.25],
                }},
            ],
        },
    ]
]
