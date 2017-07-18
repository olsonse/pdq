#!/usr/bin/env python3

from setuptools import setup, find_packages
import sys

import versioneer

if not (3, 5, 3) <= sys.version_info[:3] < (3, 6, 0):
    raise Exception("You need Python 3.5.3+ (but not 3.6+)")


setup(
    name="pdq",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    author="NIST/M-Labs",
    author_email="artiq@lists.m-labs.hk",
    url="https://github.com/m-labs/pdq",
    description="Pretty darn quick arbitrary waveform generator",
    long_description=open("README.rst", encoding="utf-8").read(),
    license="GPLv3+",
    classifiers="""\
Development Status :: 5 - Production/Stable
Environment :: Console
Intended Audience :: Science/Research
License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)
Operating System :: Microsoft :: Windows
Operating System :: POSIX :: Linux
Programming Language :: Python :: 3.5
Topic :: Scientific/Engineering :: Physics
Topic :: System :: Hardware
""".splitlines(),
    install_requires=[
        "migen", "misoc", "scipy", "numpy", "artiq>=3.0",
    ],
    extras_require={},
    dependency_links=[
        "git+https://github.com/m-labs/migen.git@develop#egg=migen",
        "git+https://github.com/m-labs/misoc.git@develop#egg=misoc",
        "git+https://github.com/m-labs/asyncserial.git@develop#egg=asyncserial",
    ],
    packages=find_packages(),
    namespace_packages=[],
    include_package_data=True,
    ext_modules=[],
    entry_points={
        "console_scripts": [
            "pdq = pdq.host.cli:main",
            "pdq_make = pdq.gateware.make:main",
            "aqctl_pdq = pdq.aqctl_pdq:main",
            ],
    }
)
