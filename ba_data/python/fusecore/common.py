"""Shared attributes."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import bascenev1 as bs

CORE_DIR_NAME: str = "fusecore"

ENV_DIRECTORY = Path(bs.app.env.data_directory)

assert bs.app.env.python_directory_user
MODS_DIRECTORY = Path(bs.app.env.python_directory_user)

assert bs.app.env.python_directory_app
PYTHON_CORE_DIRECTORY = Path(
    bs.app.env.python_directory_app,
    CORE_DIR_NAME,
)
"""Path to our modded python core directory."""

DATA_DIRECTORY = Path(PYTHON_CORE_DIRECTORY, "data")
"""Path to our modded core data directory."""

REPLAYS_DIRECTORY = Path(DATA_DIRECTORY, "replays")
"""Path to our modded core's replays directory."""

LIBS_DIRECTORY = Path(PYTHON_CORE_DIRECTORY, "libs")
"""Path to our modded core libraries directory."""

EXTERNAL_DATA_DIRECTORY = Path(MODS_DIRECTORY).parent.joinpath(CORE_DIR_NAME)
"""External directory for configurations and other data."""

sys.path += [str(LIBS_DIRECTORY)]


def init_dirs():
    """initialize important directories."""
    for path in [EXTERNAL_DATA_DIRECTORY]:
        os.makedirs(path, exist_ok=True)


# def vector3_spread(
#     vector: tuple[float, float, float],
#     spread_min: float = 1.0,
#     spread_max: float = 1.0,
# ) -> tuple[float, float, float]:
#     """Spread a Vector3 using a Fibonnaci Sphere.
#     Used for spreading multiple objects around a specific area.
#     """
#     # FIXME: implement me!
#     raise RuntimeError("not implemented.")

#     import math, random

#     # generate fibonnaci

#     # spread randomly

#     return (1, 1, 1)


def vector3_multfactor(
    vector: tuple[float, float, float],
    factor_min: float = 1.0,
    factor_max: float = 1.0,
) -> tuple[float, float, float]:
    """Randomize a vector3 within a specific multiplication range."""

    def _randmult() -> float:
        from random import uniform as ru

        return 1.0 * ru(factor_min, factor_max)

    return (
        vector[0] * _randmult(),
        vector[1] * _randmult(),
        vector[2] * _randmult(),
    )
