#!/usr/bin/env python3
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


import sys

if __name__ == "__main__":
    from os.path import join as path_join, dirname, pardir
    sys.path.insert(0, path_join( dirname(__file__), pardir, pardir ) )
    import pdq.host.cli
    pdq.host.cli.main()
    sys.exit()


import pprint
import logging
import numpy as np
try:
    from scipy import interpolate
except ImportError:
    import warnings
    warnings.warn("no scipy found, will not inteprolate")
    interpolate = None

from .usb import PDQ

import argparse
import time


def get_argparser():
    parser = argparse.ArgumentParser(description="""PDQ frontend.
            Evaluates times and voltages, interpolates and uploads
            them.""")
    parser.add_argument("-s", "--serial", default="hwgrep://",
                        help="device url [%(default)s]")
    parser.add_argument("-c", "--channel", default=0, type=int,
                        help="channel: 3*board_num+dac_num [%(default)s]")
    parser.add_argument("-f", "--frame", default=0, type=int,
                        help="frame [%(default)s]")
    parser.add_argument("-t", "--times", default="np.arange(5)*1e-6",
                        help="sample times (s) [%(default)s]")
    parser.add_argument("-v", "--voltages",
                        default="(1-np.cos(t/t[-1]*2*np.pi))/2",
                        help="sample voltages (V) [%(default)s]")
    parser.add_argument("-o", "--order", default=3, type=int,
                        help="interpolation (0: const, 1: lin, 2: quad,"
                        " 3: cubic) [%(default)s]")
    parser.add_argument("-a", "--aux-miso", default=False, action="store_true",
                        help="route MISO to AUX/F5 TTL output [%(default)s]")
    parser.add_argument("-k", "--aux-dac", default=0b111, type=int,
                        help="DAC channel OR mask to AUX/F5 TTL output "
                        "[%(default)#x]")
    parser.add_argument("-u", "--dump", help="dump to file [%(default)s]")
    parser.add_argument("-p", "--print",
                        help="print program to file.  '-' means stdout "
                             "[%(default)s]")
    parser.add_argument("-r", "--reset", default=False,
                        action="store_true", help="do reset before")
    parser.add_argument("-m", "--multiplier", default=False,
                        action="store_true", help="100MHz clock [%(default)s]")
    parser.add_argument("-n", "--disarm", default=False, action="store_true",
                        help="disarm group [%(default)s]")
    parser.add_argument("-e", "--free", default=False, action="store_true",
                        help="software trigger [%(default)s]")
    parser.add_argument("-d", "--debug", default=False,
                        action="store_true", help="debug communications")
    return parser


def main(dev=None, args=None):
    """Test a PDQ stack.

    Parse command line arguments, configures PDQ stack, interpolate the
    time/voltage data using a spline, generate a wavesynth program from the
    data and upload it to the specified channel. Then perform the desired
    arming/triggering/starting functions on the stack.
    """
    parser = get_argparser()
    args = parser.parse_args(args=args)

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    if args.dump:
        dev = open(args.dump, "wb")
    dev = PDQ(args.serial, dev)

    if args.reset:
        dev.write(b"")  # flush eop
        dev.set_config(reset=True)
        time.sleep(.1)

    dev.set_crc(0)
    dev.checksum = 0

    freq = 50e6
    if args.multiplier:
        freq *= 2

    times = np.around(eval(args.times, globals(), {})*freq)
    voltages = eval(args.voltages, globals(), dict(t=times/freq))

    dev.set_config(reset=False, clk2x=args.multiplier, enable=False,
                   trigger=False, aux_miso=args.aux_miso,
                   aux_dac=args.aux_dac, board=0xf)

    dt = np.diff(times.astype(np.int))
    if args.order and interpolate:
        tck = interpolate.splrep(times, voltages, k=args.order, s=0)
        u = interpolate.spalde(times, tck)
    else:
        u = voltages[:, None]
    segment = []
    for dti, ui in zip(dt, u):
        segment.append({
            "duration": int(dti),
            "channel_data": [{
                "bias": {
                    "amplitude": [float(uij) for uij in ui]
                }
            }]
        })
    program = [[] for i in range(dev.channels[args.channel].num_frames)]
    program[args.frame] = segment
    if args.print:
        if args.print == '-':
            f = sys.stdout
        else:
            f = open(args.print, 'w')
        print('# Generated WaveSynth program\n\nprogram = \\', file=f)
        pprint.pprint(program, f)
    dev.program(program, [args.channel])

    dev.set_frame(args.frame)
    dev.set_config(reset=False, clk2x=args.multiplier, enable=not args.disarm,
                   trigger=args.free, aux_miso=args.aux_miso,
                   aux_dac=args.aux_dac, board=0xf)
