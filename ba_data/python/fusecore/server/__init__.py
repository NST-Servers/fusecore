"""Functionality for server-related content, such as
player managing, roles, bans and chat logs.
"""

from dataclasses import dataclass

import shutil
import logging
import tomllib
from pathlib import Path

import bascenev1 as bs

from fusecore.server.stats import StatsTracker

from ._schema import ServerTOML, parse_dict
from ..common import EXTERNAL_DATA_DIRECTORY

FILE_SOURCE_DIR = Path(__file__).parent.joinpath("src")

CONFIG_SERVER_TOML: str = "config/server.toml"
# CONFIG_GENERAL_TOML: str = "/config/config.toml"

ADMIN_TOML: str = "data/admins.toml"
BANLIST_TOML: str = "data/banlist.toml"
ROLES_TOML: str = "data/roles.toml"

MEMORY_DATABASE = True

DATABASE = Path(EXTERNAL_DATA_DIRECTORY, "data", "user_data.db")
# special case: allow for memory-allocated databases
# in case we want to do some debugging and not affect
# any existing databases.
if MEMORY_DATABASE:
    DATABASE = ":memory:"
    _WARN_MSG = (
        "MEMORY_DATABASE enabled.\n" "Any saved stats will be lost on shutdown."
    )
    bs.screenmessage(_WARN_MSG)
    print(_WARN_MSG)


def _log() -> logging.Logger:
    return logging.getLogger(__name__)


@dataclass
class UserServerData:
    """Server-related information of a user."""

    account_id: str
    ballistica_id: str
    role: str


class TOMLFile:
    """Class for '.toml' files with useful tools."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict = {}

    def reload_data(self) -> None:
        """Read data from the toml's path."""
        try:
            with open(self.path, "rb") as file:
                self.data = tomllib.load(file)
        except Exception as e:
            _log().warning(
                "could not load '.toml' data from \"%s\"!\n%s",
                self.path,
                e,
                stack_info=True,
            )
            # admittedly, overwriting any existing data
            # we have in case of failure might be a bad idea.
            # self.data = {}


class FCServerManager:
    """manager."""

    def __init__(self) -> None:
        self.user_data: dict[str, UserServerData] = {}
        self.stats_tracker = StatsTracker(DATABASE)
        self._config_server_toml = TOMLFile(
            Path(EXTERNAL_DATA_DIRECTORY, CONFIG_SERVER_TOML)
        )
        self._data_admin_toml = TOMLFile(
            Path(EXTERNAL_DATA_DIRECTORY, ADMIN_TOML)
        )
        self._data_bans_toml = TOMLFile(
            Path(EXTERNAL_DATA_DIRECTORY, BANLIST_TOML)
        )
        self._data_roles_toml = TOMLFile(
            Path(EXTERNAL_DATA_DIRECTORY, ROLES_TOML)
        )
        self.create_config_files()
        self._load_config_files()

    def _load_config_files(self) -> None:
        _log().info("loading config. files...")
        self._config_server_toml.reload_data()
        self._data_admin_toml.reload_data()
        self._data_bans_toml.reload_data()
        self._data_roles_toml.reload_data()

        a = ServerTOML()
        parse_dict(a, self._config_server_toml.data)

    def _export_default_configs(self) -> None:
        outpath = Path(EXTERNAL_DATA_DIRECTORY, "config_defaults.txt")
        outtxt: str = ""
        for tomlpath in [
            Path(FILE_SOURCE_DIR, "config", "server.toml"),
            Path(FILE_SOURCE_DIR, "data", "admins.toml"),
            Path(FILE_SOURCE_DIR, "data", "banlist.toml"),
            Path(FILE_SOURCE_DIR, "data", "roles.toml"),
        ]:
            with open(tomlpath, "rb") as tomlfile:
                outtxt += (
                    f"- - {tomlpath.name} default: - - -\n"
                    f"{tomllib.load(tomlfile)}\n"
                    f"- - - - - - - - - - - - - - - - - -\n\n"
                )

        with open(outpath, "w", encoding="utf-8") as outfile:
            outfile.write(outtxt)
        _log().info('wrote config. defaults at "%s".', outpath)

    def create_config_files(self) -> None:
        """Create template files in our external data directory."""
        if EXTERNAL_DATA_DIRECTORY.exists():
            return
        _log().info(
            'cloning preset files.\nfrom "%s" to "%s"',
            FILE_SOURCE_DIR,
            EXTERNAL_DATA_DIRECTORY,
        )
        shutil.copytree(
            FILE_SOURCE_DIR, EXTERNAL_DATA_DIRECTORY, dirs_exist_ok=True
        )
