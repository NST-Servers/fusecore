"""UI-related utilities from FuseCore."""

from typing import Any, Callable
from babase._language import Lstr

import bauiv1 as bui


class CheckBox:
    """A standard checkbox *not* wired to a config. entry."""

    def __init__(
        self,
        parent: bui.Widget,
        position: tuple[float, float],
        size: tuple[float, float],
        *,
        default_value: bool = False,
        displayname: str | Lstr | None = None,
        scale: float | None = None,
        maxwidth: float | None = None,
        autoselect: bool = True,
        value_change_call: Callable[[Any], Any] | None = None,
        check_box_id: str | None = None,
    ):
        if displayname is None:
            displayname = ""
        self._value_change_call = value_change_call
        self.widget = bui.checkboxwidget(
            parent=parent,
            id=check_box_id,
            autoselect=autoselect,
            position=position,
            size=size,
            text=displayname,
            textcolor=(0.8, 0.8, 0.8),
            value=default_value,
            on_value_change_call=self._value_changed,
            scale=scale,
            maxwidth=maxwidth,
        )
        # Complain if we outlive our checkbox.
        bui.app.ui_v1.add_ui_cleanup_check(self, self.widget)

    def _value_changed(self, val: bool) -> None:
        if self._value_change_call:
            self._value_change_call(val)
