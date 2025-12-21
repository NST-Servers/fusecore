"""Module for loading and playing replays from set directories."""

import os
import random
import logging

import bauiv1 as bui
import bascenev1 as bs

from .common import DATA_DIRECTORY


REPLAY_FOLDERS: list[str] = [os.path.join(DATA_DIRECTORY, 'replays')]


def _get_replays_dir_from_path(path: str) -> list[str]:
    output: list[str] = []

    if not (os.path.exists(path) and os.path.isdir(path)):
        raise FileNotFoundError(f"invalid path: '{path}'")

    for filename in os.listdir(path):
        if os.path.splitext(filename)[1].lower() == ".brp":
            output.append(os.path.join(path, filename))

    return output


def get_user_replays() -> list[str]:
    """Get all saved replays from the user's replay folder."""
    return _get_replays_dir_from_path(bui.get_replays_dir())


def get_demo_replays() -> list[str]:
    """Get all replays from the 'REPLAY_FOLDERS' list."""
    replays: list[str] = []
    for folder_path in REPLAY_FOLDERS:
        _get_replays_dir_from_path(folder_path)

    return replays


def launch_replay_from_list(replay_path_list: list[str]) -> None:
    """Read a random replay file from the provided list
    and launch a replay activity using it.
    """
    if len(replay_path_list) < 1:
        return

    path = random.choice(replay_path_list)

    def do_it() -> None:  # efro code :]
        try:
            # Reset to normal speed.
            bs.set_replay_speed_exponent(0)
            bui.fade_screen(True)
            bs.new_replay_session(path)
        except RuntimeError:
            logging.exception('Error running replay session.')

            # Drop back into a fresh main menu session
            # in case we half-launched or something.
            from bascenev1lib import (
                mainmenu,
            )

            bs.new_host_session(mainmenu.MainMenuSession)

    bui.fade_screen(False, endcall=bui.CallStrict(bui.pushcall, do_it))
