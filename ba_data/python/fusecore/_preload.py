"""Generic script to load custom assets."""

import os
from pathlib import Path
import threading
import time
import babase

import bascenev1 as bs

from .common import ENV_DIRECTORY

BA_DATA = Path(ENV_DIRECTORY, "ba_data")

ASSET_PATHS_TO_SCAN: list[Path] = [
    Path(BA_DATA, "meshes"),
    Path(BA_DATA, "meshes2"),
    Path(BA_DATA, "textures"),
    Path(BA_DATA, "textures2"),
    Path(BA_DATA, "audio"),
    Path(BA_DATA, "audio2"),
    Path(BA_DATA, "data"),
    Path(BA_DATA, "fonts"),
]

UPDATE_TIME: float = 7.5


class AssetLoadManager:
    """Loads and reloads assets."""

    def __init__(self) -> None:
        self._last_seen = ""
        self._reload_requested = False
        self._lock = threading.Lock()
        self._update_timer = bs.AppTimer(UPDATE_TIME, self._update, repeat=True)

        self._check_file_updates()  # silent update to generate hash
        threading.Thread(target=self._watch_loop, daemon=True).start()

    def _watch_loop(self):
        while True:
            if self._check_file_updates():
                with self._lock:
                    self._reload_requested = True
            time.sleep(UPDATE_TIME)

    def _update(self):
        with self._lock:
            if self._reload_requested:
                self._reload_requested = False
                babase.reload_media()

    def _check_file_updates(self) -> bool:
        latest = 0
        for path in ASSET_PATHS_TO_SCAN:
            if not path.is_dir():
                continue

            for dirpath, _, filenames in os.walk(path):
                for filename in filenames:
                    mtime = Path(dirpath, filename).stat().st_mtime_ns
                    latest = max(latest, mtime)
        if latest != self._last_seen:
            self._last_seen = latest
            return True

        return False
