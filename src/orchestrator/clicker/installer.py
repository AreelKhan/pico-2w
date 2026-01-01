from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from orchestrator.clicker.serial_ports import auto_port


@dataclass(slots=True)
class PicoInstaller:
    port: str | None = None

    def install(self) -> None:
        port = self.port or auto_port()
        root = Path(__file__).resolve().parents[3]
        src_clicker = root / "src" / "clicker"

        self._cp(port, src_clicker / "main.py", ":main.py")
        self._cp(port, src_clicker / "clicker.py", ":clicker.py")
        self._cp(port, src_clicker / "servo.py", ":servo.py")
        self._reset(port)

    @staticmethod
    def _cp(port: str, src: Path, dest: str) -> None:
        cmd = [
            sys.executable,
            "-m",
            "mpremote",
            "connect",
            port,
            "fs",
            "cp",
            str(src),
            dest,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(
                "mpremote fs cp failed\n"
                f"cmd={' '.join(cmd)}\n"
                f"stdout={res.stdout}\n"
                f"stderr={res.stderr}"
            )

    @staticmethod
    def _reset(port: str) -> None:
        cmd = [sys.executable, "-m", "mpremote", "connect", port, "reset"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(
                "mpremote reset failed\n"
                f"cmd={' '.join(cmd)}\n"
                f"stdout={res.stdout}\n"
                f"stderr={res.stderr}"
            )
