"""Shared attributes."""

from __future__ import annotations

import os
import bascenev1 as bs

MOD_FOLDER_NAME: str = 'claymore'

PYTHON_MOD_DIRECTORY: str = os.path.join(
    bs.app.env.python_directory_app,
    MOD_FOLDER_NAME,
)
"""Path to our mod's python folder."""

DATA_DIRECTORY: str = os.path.join(PYTHON_MOD_DIRECTORY, 'data')
"""Path to our mod's data folder."""

# LIBS_DIRECTORY: str = os.path.join(PYTHON_MOD_DIRECTORY, 'libs')
# """Path to our mod's libraries folder."""
