from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import serial


@dataclass(slots=True)
class SerialTransport:
    port: str
    baud: int
    timeout_s: float

    def open(self) -> serial.Serial:
        return serial.Serial(self.port, self.baud, timeout=self.timeout_s)

    @staticmethod
    def sendline(ser: serial.Serial, line: str) -> None:
        ser.write((line + "\n").encode("utf-8"))

    @staticmethod
    def readline(ser: serial.Serial, *, stage: str) -> str:
        line = ser.readline()
        if not line:
            raise TimeoutError(f"Timed out waiting for Pico response during {stage}")
        return line.decode("utf-8", errors="replace").strip()

    @staticmethod
    def drain(ser: serial.Serial) -> None:
        old_timeout = ser.timeout
        ser.timeout = 0.05
        try:
            while True:
                b = ser.readline()
                if not b:
                    break
        finally:
            ser.timeout = old_timeout

    @staticmethod
    def set_timeout(ser: serial.Serial, timeout_s: float) -> None:
        ser.timeout = timeout_s

    @staticmethod
    def drain_lines(ser: serial.Serial, *, max_lines: int = 50) -> list[str]:
        lines: list[str] = []
        old_timeout = ser.timeout
        ser.timeout = 0.05
        try:
            for _ in range(max_lines):
                b = ser.readline()
                if not b:
                    break
                lines.append(b.decode("utf-8", errors="replace").strip())
        finally:
            ser.timeout = old_timeout
        return lines

    @staticmethod
    def expect_one_of(value: str, allowed: Iterable[str], *, stage: str) -> None:
        if value not in set(allowed):
            raise RuntimeError(f"Unexpected response during {stage}: {value!r}")
