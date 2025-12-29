from __future__ import annotations

from dataclasses import dataclass
import subprocess
import sys
import tempfile
from pathlib import Path

from orchestrator.models import ScriptRecord


@dataclass(slots=True)
class ClickerClient:
    connect: str = "auto"
    servo_pin: int = 16
    base_angle: int = 150
    click_angle: int = 180
    tick_sleep_ms: int = 1
    timeout_s: float = 60.0

    def run_script(self, script: ScriptRecord) -> None:
        code = (
            "import time\n"
            "try:\n"
            "    from servo import Servo\n"
            "except ImportError:\n"
            "    from clicker.servo import Servo\n"
            "try:\n"
            "    from clicker import Clicker\n"
            "except ImportError:\n"
            "    from clicker.clicker import Clicker\n"
            f"SERVO_PIN={self.servo_pin}\n"
            f"BASE_ANGLE={self.base_angle}\n"
            f"CLICK_ANGLE={self.click_angle}\n"
            f"BIN_MS={int(script.bin_ms)}\n"
            f"script={script.bins!r}\n"
            "servo=Servo(SERVO_PIN)\n"
            "clicker=Clicker(servo, base_angle=BASE_ANGLE, click_angle=CLICK_ANGLE)\n"
            "clicker.load(script, bin_ms=BIN_MS)\n"
            "clicker.start()\n"
            "while clicker.is_running():\n"
            "    clicker.tick()\n"
            f"    time.sleep_ms({self.tick_sleep_ms})\n"
        )

        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp:
                tmp.write(code)
                tmp_path = Path(tmp.name)

            cmd = [
                sys.executable,
                "-m",
                "mpremote",
                "connect",
                self.connect,
                "execfile",
                str(tmp_path),
            ]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
            if res.returncode != 0:
                raise RuntimeError(
                    "mpremote failed\n"
                    f"returncode={res.returncode}\n"
                    f"stdout={res.stdout}\n"
                    f"stderr={res.stderr}"
                )
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
