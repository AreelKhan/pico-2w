from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TextIO


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class RunLogger:
    fh: TextIO

    def log(self, msg: str) -> None:
        self.fh.write(f"{_now_iso()} {msg}\n")
        self.fh.flush()
