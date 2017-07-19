device_db = {
    "core": {
        "type": "local",
        "module": "artiq.coredevice.core",
        "class": "Core",
        "arguments": {
            "host": "abby",
            "ref_period": 1e-9,
            "ref_multiplier": 8
        }
    },
    "core_log": {
        "type": "controller",
        "host": "::1",
        "port": 1068,
        "command": "aqctl_corelog -p {port} --bind {bind} abby"
    },
    "core_cache": {
        "type": "local",
        "module": "artiq.coredevice.cache",
        "class": "CoreCache"
    },
    "core_dma": {
        "type": "local",
        "module": "artiq.coredevice.dma",
        "class": "CoreDMA"
    },
    "led": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 0}
    },
    "ams101_ldac": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 1}
    },
    "ams101_spi": {
        "type": "local",
        "module": "artiq.coredevice.spi",
        "class": "SPIMaster",
        "arguments": {"channel": 2}
    },
    "spi_sma": {
        "type": "local",
        "module": "artiq.coredevice.spi",
        "class": "SPIMaster",
        "arguments": {"channel": 3}
    },
    "pdq_spi": {
        "type": "local",
        "module": "pdq.artiq.spi",
        "class": "PDQ",
        "arguments": {"spi_device": "spi_sma", "chip_select": 1}
    },
    "pdq": "pdq_spi",
    "pdq_usb1": {
        "type": "controller",
        "host": "::1",
        "port": 4000,
        "command": "aqctl_pdq -p {port} --bind {bind} --simulation --dump qc_q1_0.bin"
    },
    "pdq_usb": {
        "type": "local",
        "module": "artiq.devices.pdq",
        "class": "CompoundPDQ",
        "arguments": {
            "pdq_devices": ["pdq_usb1"],
            "trigger_device": "ams101_ldac",
        }
    }
}
