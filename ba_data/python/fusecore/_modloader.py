"""Module for custom mod loading and management.

Mods are a successor to plugins designed to work
with our new core system.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import json
import logging
import os
import hashlib
import importlib
from pathlib import Path
import shutil
import sys
from typing import Any, Literal, override

import bascenev1 as bs
import bauiv1 as bui

from babase._appsubsystem import AppSubsystem

from .common import CORE_FOLDER_NAME

MOD_PATHS: list[Path] = [
    Path(bs.app.env.python_directory_user),
]
"""DO NOT MODIFY - Use 'ModLoaderSubsystem.add_scan_path' instead!"""


def _log() -> logging.Logger:
    return logging.getLogger(__name__)


def get_mods_resource_folder(
    resource: Literal["textures", "audio", "meshes"],
) -> Path:
    """Get our BombSquad folders for mod assets."""
    return Path(
        os.path.join(
            os.path.abspath(bs.app.env.data_directory),
            "ba_data",
            f"{resource}2",
            CORE_FOLDER_NAME,
            "mods",
            "ext",
        )
    )


class ModEntryType(Enum):
    """A mod's type.

    This type will determine how we'll load
    this mod (and it's assets) and whether we
    recurrently check if it changes or not.
    """

    PLUGIN = -1
    FOLDER = 0
    PACKED = 1
    COMPRESSED = 2


@dataclass(frozen=True)
class ModEntry:
    """Info. about an instanced mod."""

    path: Path
    type: ModEntryType

    def get_filetree_time_hash(self) -> str:
        """Return a hash string of this mod's file timestamps.

        We use this to quickly check if files have possibly changed
        and do any reloading if necessary. There is a possibility this
        system fails if the user goes out of his way to change files
        without updating their timestamp, but if so, it's well deserved.
        """
        hasher = hashlib.sha1()

        if self.path.is_dir():
            # walk through folders and check if any
            # files have had their timestamps updated
            # (which usually means they changed)
            for p, _, fl in os.walk(self.path):
                for f in sorted(fl):
                    try:
                        file = Path(os.path.join(p, f))
                        hasher.update(f"{file.stat().st_mtime_ns}".encode())
                    except OSError:
                        continue
        else:
            hasher.update(f"{self.path.stat().st_mtime_ns}".encode())

        return hasher.hexdigest()


class ModLoaderSubsystem(AppSubsystem):
    """Subsystem in charge of reading, categorizing
    and readying custom-made mods.
    """

    def __init__(self) -> None:
        self._mod_path_set: set[Path] = set()
        self._mod_entries: set[ModEntry] = set()
        self._mod_entry_hashes: dict[ModEntry, str] = {}
        self.paths_to_scan: list[Path] = MOD_PATHS
        # we don't want vanilla to load our plugins...
        # bs.app.plugins._load_plugins = lambda: None

        self._scan_timer: bs.AppTimer | None = None

        # make sure these exist before we start our jobs
        os.makedirs(get_mods_resource_folder("textures"), exist_ok=True)
        os.makedirs(get_mods_resource_folder("audio"), exist_ok=True)
        os.makedirs(get_mods_resource_folder("meshes"), exist_ok=True)

    @override
    def on_app_running(self) -> None:
        self.scan_for_mods()
        # TODO: We could make the time dynamic depending on the activity;
        #       we'd check for changes faster while in the main menu or paused,
        #       while checking sporadically when actively playing.
        self._scan_timer = bs.AppTimer(0.25, self.scan_for_mods, repeat=True)

    def add_scan_path(self, path: str) -> None:
        """Add a path to our paths to scan our mods at."""
        if not os.path.exists(path):
            raise FileNotFoundError(f'"{path}" doesn\'t exist.')
        if not os.path.isdir(path):
            raise NotADirectoryError(f'"{path}" is not a valid path.')

        self.paths_to_scan.append(Path(path))

    def scan_for_mods(self) -> None:
        """Scan our paths and register new mods."""

        for path in self.paths_to_scan:

            if not path.exists() or not path.is_dir():
                continue

            for file in os.listdir(path):
                # TODO: optimize this; prevent ourselves from
                # reading the same paths over and over again.
                filepath = Path(os.path.join(path, file))

                entry: ModEntry | None = None

                if filepath.is_dir():
                    # possibly an uncompressed mod.
                    entry = ModEntry(filepath, type=ModEntryType.FOLDER)

                elif filepath.is_file():
                    ext = filepath.suffix
                    match ext:
                        case ".py":
                            entry = ModEntry(filepath, type=ModEntryType.PLUGIN)
                        # TODO: '.bsmod' compressed mods will have their own
                        # file structure and we want to compensate for that...
                        case ".bsmod":
                            entry = ModEntry(filepath, type=ModEntryType.PACKED)
                        case ".zip" | ".rar":
                            entry = ModEntry(
                                filepath, type=ModEntryType.COMPRESSED
                            )
                        case _:
                            _log().debug(
                                'no assignable filetype: "%s"', filepath
                            )

                if entry is not None:
                    self._mod_entries.add(entry)

        self.read_mod_entries()

    def read_mod_entries(self) -> None:
        """Read all entries from our 'self._mod_entries' set.

        We run this function repeatedly to check if any of our
        already registered mods have been changed.
        """
        for entry in self._mod_entries.copy():

            if not entry.path.exists():

                self._mod_entries.remove(entry)
                continue

            lasthash = self._mod_entry_hashes.setdefault(entry, "")
            first_update = not lasthash
            newhash = entry.get_filetree_time_hash()
            updateable = entry.type in [
                ModEntryType.PLUGIN,
                ModEntryType.FOLDER,
            ]
            if (  # check periodically for updateables, once for nons.
                # FIXME: it shouldn't be like this? only LOAD nons once.
                (lasthash != newhash and updateable)
                or (not updateable and first_update)
            ):
                self._mod_entry_hashes[entry] = newhash
                path = entry.path

                match entry.type:
                    case ModEntryType.PLUGIN:
                        self._load_file_as_plugin(path)
                    case ModEntryType.PACKED:
                        self._load_compressed_mod_file(path)
                    case ModEntryType.FOLDER:
                        self._load_folder_as_mod(path, first_update)

    def _add_mod_to_pathlist(self, path: Path) -> None:
        if path.exists() and path not in self._mod_path_set:
            self._mod_path_set.add(path)

    def _load_file_as_plugin(self, path: Path) -> None: ...

    def _load_compressed_mod_file(self, path: Path) -> None: ...

    def _load_folder_as_mod(
        self, folder_path: Path, first_update: bool = False
    ) -> None:
        if not folder_path.is_dir():
            raise TypeError(f'"{folder_path}" is not a folder.')

        manifest_data = self._get_manifest_data(folder_path)

        if manifest_data is None:
            return

        hashname = self._generate_mod_name_hash(manifest_data)

        main_script_path = self._get_abspath(
            manifest_data["assets"]["main"], folder_path
        )
        textures_path = self._get_abspath(
            manifest_data["assets"]["textures"], folder_path
        )
        audio_path = self._get_abspath(
            manifest_data["assets"]["audio"], folder_path
        )
        meshes_path = self._get_abspath(
            manifest_data["assets"]["meshes"], folder_path
        )

        # TODO: folder mods should have their .pngs automatically
        #       converted to .dds or .ktx.
        # then, we'd build a folder with each respective extension on export.
        self._migrate_files(
            textures_path,
            get_mods_resource_folder("textures"),
            hashname,
            [".png", ".dds", ".ktx"],
        )
        # TODO: convert .mp3 files, maybe?
        self._migrate_files(
            audio_path, get_mods_resource_folder("audio"), hashname, [".ogg"]
        )
        # TODO: convert .glb files, maybe?
        self._migrate_files(
            meshes_path,
            get_mods_resource_folder("meshes"),
            hashname,
            [".bob", ".cob"],
        )

        if (
            main_script_path.exists()
            and main_script_path.is_file()
            and main_script_path.suffix == ".py"
        ):
            # FIXME: We don't want to be doing ANY of this repeatedly.
            # 'sys.path.append'ing the same path... importing multiple times...
            sys.path.append(str(folder_path))
            ext = main_script_path.suffix
            filename = main_script_path.name[: -len(ext)]
            if first_update:
                importlib.import_module(filename)
            else:
                importlib.reload(importlib.import_module(filename))

        state = "loaded" if first_update else "reloaded"
        sfx = (
            "gunCocking"
            if first_update
            else f"{CORE_FOLDER_NAME}/misc/mod_update"
        )
        bui.screenmessage(
            f'"{manifest_data['name']}" by "{manifest_data['author']}" {state}!',
            (0.3, 0.45, 0.8),
        )
        bui.getsound(sfx).play()

    def _get_manifest_data(self, path: Path) -> Any | None:
        manifest_path = Path(os.path.join(path, "manifest.json"))

        if manifest_path.exists() and manifest_path.is_file():
            with open(manifest_path, encoding="utf-8") as f:
                try:
                    return json.loads(f.read())
                except json.JSONDecodeError:
                    _log().warning(
                        'erroneous manifest at "%s"',
                        manifest_path,
                        exc_info=True,
                    )

    def _migrate_files(
        self,
        source: Path,
        destination: Path,
        hashname: str,
        allowed_filetypes: list[str] | None = None,
    ):
        if allowed_filetypes is None:
            allowed_filetypes = []

        if source.exists():
            to_path = self._get_abspath(
                hashname,
                destination,
            )
            os.makedirs(to_path, exist_ok=True)
            for filename in os.listdir(source):
                filepath = self._get_abspath(filename, source)
                if filepath.suffix in allowed_filetypes:
                    shutil.copy(filepath, to_path)

    def _generate_mod_name_hash(self, metadata: dict) -> str:
        n, a = metadata["name"], metadata["author"]
        encoded_title = f"{n}&{a}".encode()

        return hashlib.sha256(encoded_title).hexdigest()

    def _get_abspath(self, rel: str | Path, main: str | Path) -> Path:
        return Path(os.path.join(main, rel)).absolute()
