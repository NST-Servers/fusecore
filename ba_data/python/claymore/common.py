"""Shared attributes."""
from __future__ import annotations

import os
import bascenev1 as bs
import _babase  # type: ignore

ENV_DIRECTORY: str = _babase.app.env.data_directory
"""Full environment path."""
MOD_FOLDER_NAME: str = 'claymore'

PYTHON_MOD_DIRECTORY: str = os.path.join(
    bs.app.env.python_directory_app,
    MOD_FOLDER_NAME,
)
"""Path to our mod's python folder."""

DATA_DIRECTORY: str = os.path.join(PYTHON_MOD_DIRECTORY, 'data')
"""Path to our mod's data folder."""

LIBS_DIRECTORY: str = os.path.join(PYTHON_MOD_DIRECTORY, 'libs')
"""Path to our mod's libraries folder."""

def vector3_spread(
    vector: tuple[float, float, float],
    spread_min: float = 1.0,
    spread_max: float = 1.0,
) -> tuple[float, float, float]:
    """Spread a Vector3 using a Fibonnaci Sphere.
    Used for spreading multiple objects around a specific area.
    """
    raise RuntimeError("not implemented.")

    import math, random
    # generate fibonnaci
    
    # spread randomly
    
    return (1,1,1)

def vector3_multfactor(
    vector: tuple[float, float, float],
    factor_min: float = 1.0,
    factor_max: float = 1.0
) -> tuple[float, float, float]:
    """Spread a Vector3 using a Fibonnaci Sphere.
    Used for spreading multiple objects around a specific area.
    """
    def _randmult() -> float:
        from random import uniform as ru
        return 1.0 * ru(factor_min, factor_max)
    
    return (
        vector[0] * _randmult(),
        vector[1] * _randmult(),
        vector[2] * _randmult(),
    )