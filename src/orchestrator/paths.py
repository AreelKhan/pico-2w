from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_root() -> Path:
    return repo_root() / "data"


def level_dir(level: str) -> Path:
    return data_root() / "levels" / level


def scripts_dir(level: str) -> Path:
    return level_dir(level) / "scripts"


def logs_dir(level: str) -> Path:
    return level_dir(level) / "logs"


def runs_path(level: str) -> Path:
    return level_dir(level) / "runs.jsonl"
