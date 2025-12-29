from __future__ import annotations

from enum import Enum


class Level(str, Enum):
    STEREO_MADNESS = "stereo_madness"


def list_levels() -> list[str]:
    return [lvl.value for lvl in Level]


def is_known_level(level: str) -> bool:
    return level in set(list_levels())


