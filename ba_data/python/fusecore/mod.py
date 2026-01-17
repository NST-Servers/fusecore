"""Mod related stuff."""

import inspect
from pathlib import Path
from typing import Literal, Optional, Union

import bascenev1 as bs
import bauiv1 as bui

from ._modloader import ModEntry, ModLoaderInstance, get_mods_resource_dir


def get_mod_entry(file_path: Union[Path, str, None] = None) -> ModEntry:
    """Return a mod entry by providing a python script's path."""

    def scan_path(path: Path) -> Optional[ModEntry]:
        module_path = Path(path).resolve()
        if not module_path.exists():
            return None

        all_mods = ModLoaderInstance.get_mod_entries()
        for mod in all_mods.values():
            # return a mod entry if the module path is relative
            # to the registered mod's general path.
            if module_path.is_relative_to(mod.path):
                return mod
        return None

    if file_path is None:
        stack_inspect = inspect.stack().copy()
        stack_inspect.reverse()
        for stackinfo in stack_inspect:
            mod_entry = scan_path(Path(str(stackinfo.filename)).resolve())
            if mod_entry:
                return mod_entry
        raise LookupError(
            "could not match a mod entry path in the inspect stack."
        )

    mod_entry = scan_path(Path(file_path).resolve())
    if mod_entry:
        return mod_entry
    raise LookupError(
        f'path "{file_path}" could not be matched to any mod entry.'
    )


def get_id(file_path: Union[Path, str, None] = None) -> str:
    """Return a mod's ID by providing a python script's path.
    If no path is provided, an attempt at getting the requesting
    file's path via `inspect` will be made.
    """
    mod_entry = get_mod_entry(file_path)
    return mod_entry.id


def _assmodpath(
    mod_entry: ModEntry,
    asstype: Literal["textures", "audio", "meshes"],
) -> Path:
    if mod_entry.manifest is None:
        raise ValueError(f'mod entry "{mod_entry}" has no manifest.')

    manifest = mod_entry.manifest
    src_tex_path = Path(get_mods_resource_dir(asstype))
    return Path(src_tex_path, manifest.id).relative_to(
        src_tex_path.parent.parent.parent
    )


def gettexture(tex_name: str) -> bs.Texture:
    """Get a `bs.Texture` from this mod."""
    mod_entry = get_mod_entry()
    asset_path = _assmodpath(mod_entry, "textures")
    return bs.gettexture(f"{Path(asset_path, tex_name)}")


def getmesh(tex_name: str) -> bs.Mesh:
    """Get a `bs.Mesh` from this mod."""
    mod_entry = get_mod_entry()
    asset_path = _assmodpath(mod_entry, "meshes")
    return bs.getmesh(f"{Path(asset_path, tex_name)}")


def getsound(tex_name: str) -> bs.Sound:
    """Get a `bs.Sound` from this mod."""
    mod_entry = get_mod_entry()
    asset_path = _assmodpath(mod_entry, "audio")
    return bs.getsound(f"{Path(asset_path, tex_name)}")


def getuitexture(tex_name: str) -> bui.Texture:
    """Get a `bui.Texture` from this mod."""
    mod_entry = get_mod_entry()
    asset_path = _assmodpath(mod_entry, "textures")
    return bui.gettexture(f"{Path(asset_path, tex_name)}")


def getuimesh(tex_name: str) -> bui.Mesh:
    """Get a `bui.Mesh` from this mod."""
    mod_entry = get_mod_entry()
    asset_path = _assmodpath(mod_entry, "meshes")
    return bui.getmesh(f"{Path(asset_path, tex_name)}")


def getuisound(tex_name: str) -> bui.Sound:
    """Get a `bui.Sound` from this mod."""
    mod_entry = get_mod_entry()
    asset_path = _assmodpath(mod_entry, "audio")
    return bui.getsound(f"{Path(asset_path, tex_name)}")
