from __future__ import annotations

from dataclasses import dataclass

from orchestrator.models import ScriptRecord


@dataclass(slots=True)
class ClickerClient:
    def run_script(self, script: ScriptRecord) -> None:
        raise NotImplementedError("USB serial clicker client not implemented yet.")


