"""Patcher containing wrapper and override functions
for better feature control and compatibility.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import classic as _

ROOT_PATH: Path = Path()
ROOT_LOOK_FOR: list[str] = [
    "BombSquad.exe",
    "libvorbis.dll",
    "ogg.dll",
    "OpenAL32.dll",
    "ba_data",
    "DLLs",
    "lib",
]


def _find_root() -> Path:
    file_path = Path(os.path.abspath(__file__))
    fpath = _scan_path_for_root(file_path)
    if fpath is not None:
        return fpath
    raise FileNotFoundError('"root parent folder could not be found.')


def _scan_path_for_root(path: Path) -> Path | None:
    to_match = len(ROOT_LOOK_FOR)
    tom = 0
    # scan all parents in hopes of finding the root game folder
    for p in path.parents:
        tom = 0
        for f in os.listdir(p):
            # we scan all files for matches in 'ROOT_LOOK_FOR'.
            # if this directory has all files we are looking for, we
            # can determine this is the root.
            if f.lower() in (t.lower() for t in ROOT_LOOK_FOR):
                tom += 1
                if tom == to_match:
                    return Path(p, "ba_data")
    return None


def patch_base_files():
    """Patch all necessary base game files to make us run correctly."""


if __name__ == "__main__":
    ROOT_PATH = _find_root()
    print(ROOT_PATH)
    patch_base_files()
