"""Shared methods across all base elements."""

from enum import Enum


class PowerupSlotType(Enum):
    """Slot type for powerups."""

    NONE = 0
    BUFF = 1
    BOMB = 2
    GLOVES = 3
