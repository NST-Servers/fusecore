"""Module for loading and playing replays from set directories."""

from pathlib import Path
from typing import Union

import os
import random
import logging

import bauiv1 as bui
import bascenev1 as bs


def get_replays_from_dir(dir_path: Union[Path, str]) -> list[Path]:
    """Get all replay files from a specific directory."""
    # transform strings into proper paths
    if isinstance(dir_path, str):
        dir_path = Path(dir_path)

    if not dir_path.exists() or not dir_path.is_dir():
        raise FileNotFoundError(f"invalid path: '{dir_path}'")

    output: list[Path] = []
    # look for any files with a '.brp' extension and send
    # it to our output list.
    for file_path in [Path(f) for f in os.scandir(dir_path)]:
        if file_path.suffix.lower() == ".brp":
            output.append(file_path)
    # export it once we're done.
    return output


def get_user_replays() -> list[Path]:
    """Get all saved replays from the user's replay folder."""
    return get_replays_from_dir(bui.get_replays_dir())


def launch_replay(replay_path: Union[Path, list[Path]]) -> None:
    """Read a random replay file from the provided list
    and launch a replay activity using it.
    """
    path: Path
    if isinstance(replay_path, Path):
        path = replay_path
    else:
        if len(replay_path) < 1:
            raise ValueError("empty path list provided.")
        # choose a random replay
        path = random.choice(replay_path)

    def do_it() -> None:  # efro code :]
        try:
            # Reset to normal speed.
            bs.set_replay_speed_exponent(0)
            bui.fade_screen(True)
            bs.new_replay_session(str(path))
        except RuntimeError:
            logging.exception("Error running replay session.")

            # Drop back into a fresh main menu session
            # in case we half-launched or something.
            from bascenev1lib import (
                mainmenu,
            )

            bs.new_host_session(mainmenu.MainMenuSession)

    bui.fade_screen(False, endcall=bui.CallStrict(bui.pushcall, do_it))
