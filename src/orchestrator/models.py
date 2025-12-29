from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class ScriptRecord:
    level: str
    script_id: str
    bin_ms: int
    bins: list[int]
    score: float = 0.0

    def to_json(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "script_id": self.script_id,
            "bin_ms": self.bin_ms,
            "bins": self.bins,
            "score": self.score,
        }

    @staticmethod
    def from_json(data: dict[str, Any]) -> ScriptRecord:
        return ScriptRecord(
            level=str(data["level"]),
            script_id=str(data["script_id"]),
            bin_ms=int(data["bin_ms"]),
            bins=[int(x) for x in data["bins"]],
            score=float(data.get("score", 0.0)),
        )


EndReason = Literal["monitor_end", "timeout", "manual_stop", "unknown"]


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    level: str
    script_id: str
    score: float

    def to_json(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "level": self.level,
            "script_id": self.script_id,
            "score": self.score,
        }
