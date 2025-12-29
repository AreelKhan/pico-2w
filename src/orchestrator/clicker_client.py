from __future__ import annotations

from dataclasses import dataclass
import base64
import glob
import time
import uuid

import serial
import serial.tools.list_ports

from orchestrator.models import ScriptRecord

# TODO: this clicker client class feels like a mess.
# i dont understand it. i gave AI too much free reign

@dataclass(slots=True)
class ClickerClient:
    port: str | None = None
    baud: int = 115_200
    timeout_s: float = 3.0

    def run_script(self, script: ScriptRecord) -> None:
        port = self.port or self._auto_port()
        with serial.Serial(port, self.baud, timeout=self.timeout_s) as ser:
            time.sleep(1.8)
            self._drain(ser)

            self._sendline(ser, "PING")
            if self._readline(ser) != "PONG":
                raise RuntimeError("Pico did not respond to PING")

            script_id = script.script_id
            n = len(script.bins)

            self._sendline(ser, f"LOAD {script_id} {int(script.bin_ms)} {n}")
            if self._readline(ser) != f"LOADED {script_id}":
                raise RuntimeError("Unexpected response to LOAD")

            payload = self._encode_bins(script.bins)
            self._sendline(ser, f"DATA {script_id} {payload}")
            if self._readline(ser) != f"DATA_OK {script_id}":
                raise RuntimeError("Unexpected response to DATA")

            self._sendline(ser, f"START {script_id}")
            if self._readline(ser) != f"STARTED {script_id}":
                raise RuntimeError("Unexpected response to START")

            expected_run_s = (n * int(script.bin_ms)) / 1000.0
            old_timeout = ser.timeout
            ser.timeout = max(float(self.timeout_s), expected_run_s + 2.0)
            try:
                done = self._readline(ser)
            finally:
                ser.timeout = old_timeout
            if done != f"DONE {script_id}" and done != f"STOPPED {script_id}":
                raise RuntimeError(f"Unexpected completion response: {done!r}")

    def stop(self) -> str:
        port = self.port or self._auto_port()
        with serial.Serial(port, self.baud, timeout=self.timeout_s) as ser:
            time.sleep(0.5)
            self._drain(ser)
            self._sendline(ser, "STOP")
            return self._readline(ser)

    @staticmethod
    def _encode_bins(bins: list[int]) -> str:
        n = len(bins)
        nbytes = (n + 7) // 8
        buf = bytearray(nbytes)
        for i, b in enumerate(bins):
            if b:
                byte_i = i // 8
                bit = 7 - (i % 8)
                buf[byte_i] |= 1 << bit
        return base64.b64encode(bytes(buf)).decode("ascii")

    @staticmethod
    def _sendline(ser: serial.Serial, line: str) -> None:
        ser.write((line + "\n").encode("utf-8"))

    @staticmethod
    def _readline(ser: serial.Serial) -> str:
        line = ser.readline()
        if not line:
            raise TimeoutError("Timed out waiting for Pico response")
        return line.decode("utf-8", errors="replace").strip()

    @staticmethod
    def _drain(ser: serial.Serial) -> None:
        old_timeout = ser.timeout
        ser.timeout = 0.05
        while True:
            b = ser.readline()
            if not b:
                break
        ser.timeout = old_timeout

    @staticmethod
    def _auto_port() -> str:
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            if p.device and ("ttyACM" in p.device or "ttyUSB" in p.device):
                return p.device
        globs = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
        if globs:
            return globs[0]
        raise FileNotFoundError("No serial port found (tried /dev/ttyACM* and /dev/ttyUSB*)")
