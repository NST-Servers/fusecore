"""Utilities library."""

from enum import Enum
from dataclasses import is_dataclass
from typing import Literal

import bascenev1 as bs

from fusecore._tools import is_server


class NodeAlignment(Enum):
    """Node alignment enum."""

    TOP_LEFT = ("topLeft", "top", "left")
    TOP_MIDDLE = ("topCenter", "top", "center")
    TOP_RIGHT = ("topRight", "top", "right")
    CENTER_LEFT = ("left", "center", "left")
    CENTER_MIDDLE = ("center", "center", "center")
    CENTER_RIGHT = ("right", "center", "right")
    BOTTOM_LEFT = ("bottomLeft", "bottom", "left")
    BOTTOM_MIDDLE = ("bottomCenter", "bottom", "center")
    BOTTOM_RIGHT = ("bottomRight", "bottom", "right")

    def get_attach(self) -> str:
        """Get a proper 'align' value."""
        return self.value[0]

    def get_h_attach(self) -> str:
        """Get a proper 'h_align' value."""
        return self.value[2]

    def get_v_attach(self) -> str:
        """Get a proper 'v_align' value."""
        return self.value[1]

RTYPES = Literal["soft", "char", "powerup", "sharper"]

def parse_dict(obj, data: dict):
    """Parse dictionary items as variables to a class
    if the keys of that dictionary match an existing variable name.
    """
    # NOTE: this is an awful approach, but I tried
    # using pydantic for a while before realizing embedded
    # python had no chance to get it fully working so I'll
    # have to bear with this solution for now.
    for k, v in data.items():
        if not hasattr(obj, k):
            continue

        current = getattr(obj, k)

        if is_dataclass(current) and isinstance(v, dict):
            parse_dict(current, v)
        else:
            setattr(obj, k, v)


def lstr_server(lstr: bs.Lstr) -> bs.Lstr | str:
    """Transforms an Lstr line into a string if we are
    running in a server environment.
    """
    if is_server():
        return lstr.evaluate()
    return lstr
