"""Shared attributes."""

import os
import bascenev1 as bs
import _babase  # type: ignore

ENV_DIRECTORY: str = _babase.app.env.data_directory
"""Full environment path."""

PYTHON_MOD_DIRECTORY: str = os.path.join(
    bs.app.env.python_directory_app,
    'claymore',
)
"""Path to our mod's python folder."""

DATA_DIRECTORY: str = os.path.join(PYTHON_MOD_DIRECTORY, 'data')
"""Path to our mod's data folder."""

LIBS_DIRECTORY: str = os.path.join(PYTHON_MOD_DIRECTORY, 'libs')
"""Path to our mod's libraries folder."""
