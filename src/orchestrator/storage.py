from __future__ import annotations

import json
from pathlib import Path
from typing import TextIO

from orchestrator.levels import is_known_level
from orchestrator.models import RunRecord, ScriptRecord
from orchestrator.paths import level_dir, logs_dir, runs_path, scripts_dir


class LevelNotFoundError(ValueError):
    pass


class ScriptNotFoundError(ValueError):
    pass


class Storage:
    def __init__(self) -> None:
        pass

    def assert_level_exists(self, level: str) -> None:
        if not is_known_level(level):
            raise LevelNotFoundError(f"Unknown level: '{level}'")
        level_dir(level).mkdir(parents=True, exist_ok=True)

    def load_script(self, level: str, script_id: str) -> ScriptRecord:
        self.assert_level_exists(level)
        path = scripts_dir(level) / f"{script_id}.json"
        if not path.exists():
            raise ScriptNotFoundError(
                f"Script '{script_id}' not found at {path}."
            )
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return ScriptRecord.from_json(data)

    def save_script(self, script: ScriptRecord) -> Path:
        self.assert_level_exists(script.level)
        scripts_dir(script.level).mkdir(parents=True, exist_ok=True)
        path = scripts_dir(script.level) / f"{script.script_id}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(script.to_json(), f, separators=(",", ":"), sort_keys=True)
            f.write("\n")
        return path

    def append_run(self, run: RunRecord) -> Path:
        self.assert_level_exists(run.level)
        path = runs_path(run.level)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(run.to_json(), separators=(",", ":"), sort_keys=True))
            f.write("\n")
        return path

    def open_run_log(self, level: str, run_id: str) -> tuple[Path, TextIO]:
        self.assert_level_exists(level)
        logs_dir(level).mkdir(parents=True, exist_ok=True)
        path = logs_dir(level) / f"{run_id}.log"
        fh = path.open("a", encoding="utf-8")
        return path, fh
