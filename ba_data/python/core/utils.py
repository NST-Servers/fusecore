"""Utilities library."""

from enum import Enum


class NodeAlignment(Enum):
    """Node alignment enum."""

    TOP_LEFT = ('topLeft', 'top', 'left')
    TOP_MIDDLE = ('topCenter', 'top', 'center')
    TOP_RIGHT = ('topRight', 'top', 'right')
    CENTER_LEFT = ('left', 'center', 'left')
    CENTER_MIDDLE = ('center', 'center', 'center')
    CENTER_RIGHT = ('right', 'center', 'right')
    BOTTOM_LEFT = ('bottomLeft', 'bottom', 'left')
    BOTTOM_MIDDLE = ('bottomCenter', 'bottom', 'center')
    BOTTOM_RIGHT = ('bottomRight', 'bottom', 'right')

    def get_attach(self) -> str:
        """Get a proper 'align' value."""
        return self.value[0]

    def get_h_attach(self) -> str:
        """Get a proper 'h_align' value."""
        return self.value[2]

    def get_v_attach(self) -> str:
        """Get a proper 'v_align' value."""
        return self.value[1]
