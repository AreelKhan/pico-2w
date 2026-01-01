from __future__ import annotations

import glob

import serial.tools.list_ports


def auto_port() -> str:
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if p.device and ("ttyACM" in p.device or "ttyUSB" in p.device):
            return p.device
    globs = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
    if globs:
        return globs[0]
    raise FileNotFoundError(
        "No serial port found (tried /dev/ttyACM* and /dev/ttyUSB*)"
    )
