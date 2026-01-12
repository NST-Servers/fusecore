"""Module for custom mod loading and management.

Mods are a successor to plugins designed to work
in sync with our new core's subsystems and functions.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Literal, Optional, TypedDict, Union, override

import os
import sys
import time
import json
import shutil
import logging
import hashlib
import threading

import importlib

# import importlib.util
# from importlib.abc import MetaPathFinder, Loader

import bascenev1 as bs
import bauiv1 as bui

from babase._appsubsystem import AppSubsystem
from fusecore.utils import parse_dict

from ._tools import is_server
from .common import CORE_DIR_NAME, MODS_DIRECTORY


def _log() -> logging.Logger:
    return logging.getLogger(__name__)


VALID_MANIFESTS: list[str] = [
    "mod.json",
]


# TODO: implement this
# # https://docs.python.org/3/library/importlib.html#module-importlib
# # https://docs.python.org/3/reference/import.html#finders-and-loaders
# class ModloadImportLoader(Loader):
#     # https://docs.python.org/3/glossary.html#term-loader
#     # https://docs.python.org/3/library/importlib.html#importlib.abc.Loader

#     def create_module(self, spec):
#         return None

#     def exec_module(self, module): ...


# class ModloadFinder(MetaPathFinder):
#     """Custom ``MetaPathFinder`` to load mods."""

#     # https://docs.python.org/3/glossary.html#term-finder

#     def find_spec(self, fullname, path, target=None):
#         if not fullname.startswith("mod:"):
#             return None

#         for mod_dir_path in ModLoaderInstance.dirs_to_scan:
#             print(mod_dir_path)

#         return importlib.util.spec_from_loader(
#           fullname, ModloadImportLoader()
#     )

# sys.meta_path.insert(0, ModloadFinder())


def get_mods_resource_dir(
    resource: Literal["textures", "audio", "meshes"],
) -> Path:
    """Get our BombSquad dirs for mod assets."""
    return Path(
        os.path.join(
            os.path.abspath(bs.app.env.data_directory),
            "ba_data",
            f"{resource}2",
            CORE_DIR_NAME,
            "mods",
            "ext",
        )
    )


class ModType(Enum):
    """A mod's type.

    This type will determine how we'll load
    this mod (and it's assets) and whether we
    recurrently check if it changes or not.
    """

    NONE = None
    PLUGIN = "plugin"
    DIRECTORY = "dir"
    PACKED = "packed"
    COMPRESSED = "zip"


@dataclass
class _FuseVersion(TypedDict):
    version: list[str]
    api: int


@dataclass
class _BSVersion(TypedDict):
    version: list[str]
    build: list[int]
    api: int


@dataclass
class ModManifest:
    """Mod manifest data."""

    id: str = ""
    name: str = "Ballistica Mod"
    authors: list[str] = field(default_factory=list)
    version: str = "1.0"

    fusecore: str = "1.0"
    assets: dict[str, str] = field(default_factory=dict)


class _ModStatus(Enum):
    NEW = "!"
    ACTIVE = True
    OFFLINE = None


@dataclass
class ModEntry:
    """An entry for a mod.

    Used for working with the modloader, but can
    also be used for information displaying as long
    as the class is not tinkered with too much.
    """

    # NOTE: Should probably make a class exclusive for
    # displaying (e.g. mod menus) to prevent silly mishaps.

    id: str
    path: Path
    type: ModType
    manifest: Optional[ModManifest]

    _status: _ModStatus = _ModStatus.NEW
    _last_time: int = -9999

    def exists(self) -> bool:
        """Return if this mod's main path still exists."""
        return self.path.exists()

    def _is_mutable(self) -> bool:
        return self.type is ModType.DIRECTORY

    def _pop_new_status(self) -> bool:
        """Return if our status is ``ModStatus.NEW`` or not.

        If we are new, immediately transform our mod status
        into ``ModStatus.ACTIVE``, disallowing this function from
        returning ``True`` again.
        """
        out = self._status is _ModStatus.NEW
        if out:
            self._status = _ModStatus.ACTIVE
        return out

    def _get_latest_time(self) -> int:
        """Return the latest time a file has been changed.

        We use this to quickly check if files have possibly changed
        and do any reloading if necessary. There is a possibility this
        system fails if the user goes out of his way to change files
        without updating their timestamp, but if so, it's well deserved.
        """
        latest: int = 0

        if self.path.is_dir():
            # walk through dirs and check if any
            # files have had their timestamps updated
            # (which usually means they changed)
            for p, _, fl in os.walk(self.path):
                for f in sorted(fl):
                    try:
                        file = Path(os.path.join(p, f))
                        mtime = file.stat().st_mtime_ns
                        latest = max(latest, mtime)
                    except OSError:
                        continue
        else:
            latest = self.path.stat().st_mtime_ns

        return latest

    def _get_authors_string_from_manifest(self) -> str:
        if self.manifest is None:
            raise RuntimeError(
                "_get_authors_string_from_manifest called with no manifest."
            )
        authors = self.manifest.authors
        # return one or no author if len is under 2
        if len(authors) < 1:
            return "no author"
        if len(authors) < 2:
            return authors[0]

        text = ""
        # construct an author string if we have multiple authors
        for i, author in enumerate(authors):
            last_i = len(authors) - 1
            # last author line
            if i == last_i:
                text += f"{author}"
                continue
            # one before our last author
            if i == last_i - 1:
                text += f"{author} & "
                continue
            # any other authors
            text += f"{author}, "
        return text

    def _announce_mod_loaded(self) -> None:
        name: str = (
            self.path.name if self.manifest is None else self.manifest.name
        )
        authors: str = (
            "a creator"
            if self.manifest is None
            else self._get_authors_string_from_manifest()
        )
        text = bs.Lstr(
            resource="modLoadedText",
            subs=[("${MODNAME}", name), ("${AUTHORS}", authors)],
        )
        # server prints to console, client shows a message.
        print(text.evaluate())

    def load(self, main_subsystem: ModLoaderSubsystem) -> bool:
        """Returns success."""
        # don't load if we ceased to exist...
        if not self.exists():
            return False
        # don't load if we've loaded before and aren't mutable
        if not self._is_mutable() and self._status is _ModStatus.ACTIVE:
            return False
        # don't load if no files have changed
        _new_time = self._get_latest_time()
        if _new_time == self._last_time:
            return False
        self._last_time = _new_time

        loaded: bool = False
        match self.type:
            # load mod depending on type
            case ModType.DIRECTORY:
                loaded = self._load_as_directory(main_subsystem)
        # announce we loaded the mod and return if we did so.
        if loaded:
            self._announce_mod_loaded()
        return loaded

    def _load_as_directory(self, main_subsystem: ModLoaderSubsystem) -> bool:
        assert self.manifest
        is_new = self._pop_new_status()

        asset_paths: Optional[dict[str, str]] = self.manifest.assets
        path_main: Optional[Path] = None
        path_tex: Optional[Path] = None
        path_audio: Optional[Path] = None
        path_mesh: Optional[Path] = None
        if asset_paths is None:
            # can't load modules if we don't have asset paths!
            return False

        def safe_path(source_dir: Optional[str]) -> Optional[Path]:
            if source_dir is None:
                return None
            # dir_path from source call
            dst_path = get_abspath(source_dir, self.path)
            # only set path if it actually exists.
            if dst_path.exists():
                return dst_path
            return None

        path_main = safe_path(asset_paths.get("main", None))
        path_tex = safe_path(asset_paths.get("textures", None))
        path_audio = safe_path(asset_paths.get("audio", None))
        path_mesh = safe_path(asset_paths.get("meshes", None))

        # servers don't care about texture or audio files
        if is_server() is False:

            img_ext = [".dds", ".ktx"]
            # desktop platforms require '.dds' files while
            # mobile ones use '.ktx' instead; make sure we
            # get the proper files.
            if bs.app.classic is None:
                # if classic isn't running somehow... awkward!
                ...
            else:
                # do out platform matching checks if it is running.
                # if we are somehow playing in the ouya, we'll
                # make sure to pull both file types.
                match bs.app.classic.platform:
                    case "windows" | "linux" | "mac":
                        img_ext = [".dds"]
                    case "android" | "ios":
                        img_ext = [".ktx"]
            # finally migrate textures!
            # FIXME: Doing this successfully triggers our asset reloader
            # after a couple of seconds, not world-shattering but is pretty
            # annoying; we should make a special case to only reload assets
            # if any existing ones are getting replaced.
            if path_tex:
                main_subsystem.migrate_files(
                    path_tex,
                    get_mods_resource_dir("textures"),
                    self.id,
                    img_ext,
                )
            # migrate audio files.
            if path_audio:
                main_subsystem.migrate_files(
                    path_audio,
                    get_mods_resource_dir("audio"),
                    self.id,
                    [".ogg"],
                )
        # migrate meshes.
        if path_mesh:
            main_subsystem.migrate_files(
                path_mesh,
                get_mods_resource_dir("meshes"),
                self.id,
                [".bob", ".cob"],
            )
        # load the main script.
        if not path_main:
            return False
        if not path_main.is_file() or path_main.suffix != ".py":
            return False

        if is_new:
            # append the mod's parent dir into our sys.path
            # the first time we load it.
            main_parent = path_main.parent
            if main_parent not in sys.path:
                sys.path.append(str(main_parent))
        # restructured module 'path', should look like "dir.file_name"
        module_import: str = (
            f"{self.path.name}.{path_main.name[: -len(path_main.suffix)]}"
        )
        imported_module: Optional[ModuleType] = sys.modules.get(module_import)
        if imported_module:
            # if the module is already loaded, reload it respectfully.
            importlib.reload(imported_module)
        else:
            # rev up the module!
            importlib.import_module(module_import)

        return is_new


class ReadExitStatus(Enum):
    """Exit status when reading mods.

    CLEAN will play a gun cocking sound while ERROR plays
    an evil and honestly infuriating beep.
    """

    CLEAN = "win"
    ERROR = "loss"


class ModLoaderSubsystem(AppSubsystem):
    """Subsystem in charge of reading, categorizing
    and readying custom-made mods.
    """

    def __init__(self) -> None:
        self.dirs_to_scan: list[Path] = [Path(MODS_DIRECTORY)]
        self._scan_paths: list[Path] = []
        self._last_scan_paths: list[Path] = []

        # we don't want vanilla to load our plugins...
        # FIXME: for now, we DO want vanilla to load plugins
        # as we don't keep track of enabled or disabled ones...
        # bs.app.plugins._load_plugins = lambda: None
        self._mod_entries: dict[str, ModEntry] = {}

        self._lock = threading.Lock()
        self._scan_thread: threading.Thread | None = None
        self._scan_thread_wait_time: float = 8.0
        self._scan_finished = False
        self._load_timer = bui.AppTimer(0.4, self._post_scan_load, repeat=True)

        # make sure these exist before we start our jobs
        if is_server() is False:
            # servers don't care about textures or audio assets
            # only meshes are relevant.
            os.makedirs(get_mods_resource_dir("textures"), exist_ok=True)
            os.makedirs(get_mods_resource_dir("audio"), exist_ok=True)
        os.makedirs(get_mods_resource_dir("meshes"), exist_ok=True)

    def get_mod_entries(self) -> dict[str, ModEntry]:
        """Returns all known mod entries."""
        return self._mod_entries

    def add_dir_to_scan(self, path: Path) -> None:
        """Add a new mod path to scan mods from."""
        if path in self.dirs_to_scan:
            return
        # make sure we're adding an actual directory
        if not path.exists():
            raise FileNotFoundError(f'path "{path}" does not exist.')
        if not path.is_dir():
            raise NotADirectoryError(f'path "{path}" is not a directory.')

        self.dirs_to_scan.append(path)
        self._update_sys_paths()

    def _update_sys_paths(self) -> None:
        for path in self.dirs_to_scan:
            if path in sys.path:
                continue
            sys.path.append(str(path))

    @override
    def on_app_running(self) -> None:
        self._update_sys_paths()
        self.scan_for_mods()
        self._read_mod_entries()
        # TODO: We could make the time dynamic depending on the activity;
        #       we'd check for changes faster while in the main menu or paused,
        #       while checking sporadically when actively playing.
        assert bs.app.classic
        if bs.app.classic.platform in ["windows", "linux", "mac"]:
            # run periodic scan slightly faster on desktop devices
            self._scan_thread_wait_time = 0.66
        self._scan_thread = threading.Thread(target=self._thread_scan)
        self._scan_thread.start()

    @override
    def on_app_unsuspend(self) -> None:
        # on mobile, if we 'tab' right back into the game, do a quick
        # mod scan, as the user could've gone and gotten new mods.
        self.scan_for_mods()

    def add_scan_path(self, path: str) -> None:
        """Add a path to our paths to scan our mods at."""
        if not os.path.exists(path):
            raise FileNotFoundError(f'"{path}" doesn\'t exist.')
        if not os.path.isdir(path):
            raise NotADirectoryError(f'"{path}" is not a valid path.')

        self.dirs_to_scan.append(Path(path))

    def _thread_scan(self) -> None:
        while True:
            time.sleep(self._scan_thread_wait_time)
            self.scan_for_mods()

    def _post_scan_load(self) -> None:
        with self._lock:
            if self._scan_finished:
                self._scan_finished = False
                self._read_mod_entries()

    def _is_path_valid_for_scan(self, path: Path) -> bool:
        _name_blacklist = ["__pycache__"]
        _ext_blacklist = [".pyc", ".exe"]

        if path.name in _name_blacklist or path.suffix in _ext_blacklist:
            return False
        return True

    def _get_valid_scan_list(self, path: Path) -> list[Path]:
        valid_list: list[Path] = []
        # get every subpath from the provided path and filter out
        # any invalid subpaths that we might not wanna scan.
        for subpath in os.listdir(path):
            full_path = Path(path, subpath).absolute()
            if self._is_path_valid_for_scan(full_path):
                valid_list.append(full_path)

        valid_list.sort()
        return valid_list

    def _look_for_dir_manifest(self, dir_path: Path) -> Optional[ModManifest]:
        if not dir_path.exists() or not dir_path.is_dir():
            raise NotADirectoryError(f'path "{dir_path}" is invalid.')

        found_manifests: list[Path] = []

        # find and list all manifests found in a folder
        for infile in os.listdir(dir_path):
            file_path = Path(dir_path, infile)
            if file_path.name in VALID_MANIFESTS:
                found_manifests.append(file_path)
        # realistically, there shouldn't be more than one manifest
        # in a mod folder at any moment. In case such case occurs,
        # announce so in the console and explain our further operation.
        if len(found_manifests) > 1:
            _log().warning(
                'multiple manifests found in "%s"!'
                " loading first in alphabetical order and ignoring"
                " remaining manifests.\n"
                "Please remove any additional files named %s to"
                " prevent manifest overlap.",
                dir_path,
                VALID_MANIFESTS,
            )
        # alternatively, we quit with none if no manifests were found.
        elif len(found_manifests) < 1:
            return None

        found_manifests.sort()
        manifest_path = found_manifests[0]
        try:
            with open(manifest_path, "r", encoding="utf-8") as jsonfile:
                manifest = ModManifest()
                parse_dict(manifest, json.loads(jsonfile.read()))
                return manifest
        except Exception:
            _log().warning(
                'manifest load "%s" failed.', manifest_path, exc_info=True
            )

        return None

    def scan_for_mods(self, dir_path: Optional[Path] = None) -> None:
        """Scan our paths and register new mods."""

        _paths_to_scan: list[Path] = []
        _is_global_scan = False

        if dir_path and (not dir_path.exists() or not dir_path.is_dir()):
            raise NotADirectoryError(f'path "{dir_path}" is invalid.')

        if dir_path is None:
            _log().debug(
                "mod scan called w/no path; scanning all mod dirs!"
                "dir paths registered are: %s",
                self.dirs_to_scan,
            )
            # we reset paths here and track any we scan; we'll compare
            # these with 'self._last_paths_scanned' to prevent ourselves
            # from scanning paths we've already loaded, but eventually
            # removing paths that disappear so we can reload them.
            _is_global_scan = True
            self._scan_paths = []
            # get all files from every dir in our self.dirs_to_scan var
            for mod_path in self.dirs_to_scan:
                _paths_to_scan.extend(self._get_valid_scan_list(mod_path))
        else:
            # provide all paths from our provided dir
            _log().debug('mod scan called w/path "%s".', dir_path)
            _paths_to_scan = self._get_valid_scan_list(dir_path)

        for path in _paths_to_scan:
            self._scan_paths.append(path)
            # don't scan the path if we already did previously
            if path in self._last_scan_paths:
                _log().debug('ignoring "%s"; previously scanned.', path)
                continue

            if path.is_dir():
                # check for a manifest file.
                manifest = self._look_for_dir_manifest(path)
                if manifest:
                    _log().info(
                        'manifest file found in "%s",'
                        " registering as directory mod.",
                        path,
                    )
                    self._add_mod_entry(
                        ModEntry(
                            id=manifest.id,
                            path=path,
                            type=ModType.DIRECTORY,
                            manifest=manifest,
                        )
                    )
                    continue
                # if there's no manifest, do a recursion scan
                self.scan_for_mods(path)
                # actually, because we are doing a recursive scan here, we
                # might want to check this dir constantly, so let's remove
                # this path from the scan paths to prevent it from getting
                # logged as scanned.
                self._scan_paths.remove(path)
                continue

            if path.is_file():
                if path.suffix == ".py":
                    _log().info(
                        'stray python file at "%s" registering as plugin.',
                        path,
                    )
                    self._add_mod_entry(
                        ModEntry(
                            id=path.name,
                            path=path,
                            type=ModType.PLUGIN,
                            manifest=None,
                        )
                    )
                    continue

        if _is_global_scan:
            if self._last_scan_paths != self._scan_paths:
                with self._lock:
                    self._scan_finished = True
            self._last_scan_paths = self._scan_paths

    def _add_mod_entry(self, entry: ModEntry) -> None:
        _prev_entry = self._mod_entries.get(entry.id, None)
        if _prev_entry:
            if _prev_entry.path != entry.path:
                # we can't append different paths under the same mod
                # name for obvious reasons, but we raise a warning
                # over an exception to not prevent other mods from loading.
                _log().warning(
                    'tried to re-append mod entry "%s", but an'
                    " entry with a different path already exists!",
                    entry.id,
                    stack_info=True,
                )
                return
            _log().debug('re-appending "%s"', entry.id)
            return

        self._mod_entries[entry.id] = entry

    def _read_mod_entries(self) -> None:
        _log().info("reading mod entries...")
        _read_exit = ReadExitStatus.CLEAN
        i = False  # mods loaded?

        for mod_entry in self._mod_entries.values():
            try:
                load_output = mod_entry.load(self)
                if load_output:
                    # we did load a mod after all!
                    i = True
            except Exception as e:
                self._handle_load_exception(mod_entry, e)
                _read_exit = ReadExitStatus.ERROR

        # don't bother with the sfx if no media went through
        if not i:
            return
        sfx = "gunCocking" if _read_exit is ReadExitStatus.CLEAN else "error"
        bui.getsound(sfx).play()

    def _handle_load_exception(self, mod_entry: ModEntry, e: Exception) -> None:
        _log().error(
            'error loading mod "%s": "%s"', mod_entry, e, exc_info=True
        )

    def _read_mod_manifest(self, path: Path) -> Optional[dict]:
        for fname in ["manifest", "mod", "metadata"]:
            manifest_path = Path(os.path.join(path, f"{fname}.json"))
            if not (manifest_path.exists() and manifest_path.is_file()):
                continue

            with open(manifest_path, encoding="utf-8") as f:
                try:
                    return json.loads(f.read())
                except json.JSONDecodeError:
                    _log().warning(
                        'erroneous manifest at "%s"',
                        manifest_path,
                        exc_info=True,
                    )
        return None

    def migrate_files(
        self,
        source: Path,
        destination: Path,
        hashname: str,
        allowed_filetypes: list[str] | None = None,
    ):
        """Move files of a specific type from a dir to another."""
        if allowed_filetypes is None:
            allowed_filetypes = []

        if source.exists():
            to_path = get_abspath(
                hashname,
                destination,
            )
            os.makedirs(to_path, exist_ok=True)
            for filename in os.listdir(source):
                filepath = get_abspath(filename, source)
                if filepath.suffix in allowed_filetypes:
                    shutil.copy(filepath, to_path)

    def _generate_package_name(self, manifest: dict) -> str:
        safety_hash = hashlib.md5(f"{manifest}".encode()).hexdigest()

        def built_str(text: str) -> str:
            text = text.strip()
            text = "".join([c for c in text if c.isascii()])
            text = text.replace(" ", "_")
            text = text.lower()
            return text

        mod_name: str = (
            built_str(manifest.get("name", "")) or f"fcmod_{safety_hash}"
        )
        mod_author: str = built_str(manifest.get("author", "")) or "no_author"

        return f"{mod_name}.{mod_author}"


def get_abspath(rel: Union[Path, str], main: Union[Path, str]) -> Path:
    """Get the absolute path of a mix of main and relative path."""
    return Path(os.path.join(main, rel)).absolute()


ModLoaderInstance = bs.app.register_subsystem(ModLoaderSubsystem())
