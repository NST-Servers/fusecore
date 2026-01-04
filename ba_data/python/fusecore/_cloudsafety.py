"""Wrapper for cloud console code execution
to make sure players are ok with it.
"""

import logging
from typing import Any, Callable, Union

import babase
import bascenev1 as bs
from baplus import _cloud

from bauiv1lib.confirm import ConfirmWindow
from fusecore.ui.utils import CheckBox

AckType = Union[bool, None]


class CloudConfirmWindow(ConfirmWindow):
    """Custom ``ConfirmWindow`` for our cloud stuff."""

    def __init__(
        self,
        text: str | babase.Lstr | None = None,
        action: Callable[[], Any] | None = None,
        cancel_action: Callable[[], Any] | None = None,
        width: float = 360,
        height: float = 100,
        *,
        checkbox_call: Callable | None = None,
        cancel_button: bool = True,
        cancel_is_selected: bool = False,
        color: tuple[float, float, float] = (1, 1, 1),
        text_scale: float = 1,
        ok_text: str | babase.Lstr | None = None,
        cancel_text: str | babase.Lstr | None = None,
        origin_widget: Any | None = None,
        permanent_ok_fade: bool = False,
    ):
        super().__init__(
            text,
            action,
            width,
            height,
            cancel_button=cancel_button,
            cancel_is_selected=cancel_is_selected,
            color=color,
            text_scale=text_scale,
            ok_text=ok_text,
            cancel_text=cancel_text,
            origin_widget=origin_widget,
            permanent_ok_fade=permanent_ok_fade,
        )
        self._cancel_action = cancel_action
        self.checkbox_call = checkbox_call
        self.dont_show_again_checkbox = CheckBox(
            self.root_widget,
            ((width / 4) + 10, 82),
            (50, 50),
            displayname=bs.Lstr(resource="dontShowAgainText"),
            value_change_call=bs.WeakCallPartial(self._checkbox_value_changed),
        )

    def _cancel(self) -> None:
        if self._cancel_action:
            self._cancel_action()
        return super()._cancel()

    def _checkbox_value_changed(self, val: bool) -> None:
        if self.checkbox_call:
            self.checkbox_call(val)


class CloudControl:
    """Utils for cloud control."""

    def __init__(self) -> None:
        self.cfg_entry: str = "Allow Cloud Console"

        self.has_warned = False
        self._dsa_check: bool = False
        self._accepted: AckType = None
        self._code_buffer: list[str] = []

    @property
    def has_accepted(self) -> AckType:
        """User acknowledgement property."""
        return self._accepted

    @has_accepted.setter
    def has_accepted(self, user_ack: AckType) -> None:
        match user_ack:
            case False:
                self.discard_buffer()
            case True:
                self.run_buffer()
        self._accepted = user_ack

    def add_exec(self, code: str) -> None:
        """Add an execution command to our buffer.

        All buffered commands will be executed once the user
        acknowledges our warning, or discarded if he denies it.
        """
        if self.has_accepted is False:
            return
        self._code_buffer.append(code)

    def discard_buffer(self) -> None:
        """Called when user denies our warning, or after
        running all commands in our buffer.
        """
        self._code_buffer.clear()

    def run_buffer(self) -> None:
        """Called when user acknowledges our warning."""
        with bs.ContextRef.empty():
            for i, code in enumerate(self._code_buffer):
                bs.apptimer(
                    0.12 * i, bs.CallStrict(_cloud.cloud_console_exec, code)
                )
        self.discard_buffer()

    def show_warning(self) -> None:
        """Show our big, spooky warning if we haven't."""
        if CC.has_warned:
            return
        self._activity_pause(True)
        logging.warning("Awaiting for Cloud Console acknowledgement...")

        fallback_warning = (
            "Heads up! Someone tried to run remote code\n"
            'via the "ballistica.net/devices" website.\n\n'
            'Press "Allow" if you\'re the one using the\n'
            "Cloud Console and know what you're doing."
        )
        warning_lstr = bs.Lstr(
            resource="remoteCodeWarning",
            fallback_value=fallback_warning,
        )

        # give some time for the user to react to the
        # sudden pop-up and prevent any misinputs.
        babase.lock_all_input()
        bs.apptimer(2, babase.unlock_all_input)

        with bs.ContextRef.empty():
            w, h = (615, 300)
            CloudConfirmWindow(
                bs.Lstr(
                    value="${A}\n",
                    subs=[("${A}", warning_lstr)],
                ),
                ok_text=bs.Lstr(resource="allowText"),
                cancel_text=bs.Lstr(resource="noWayText"),
                cancel_is_selected=True,
                action=self._user_acknowledged,
                cancel_action=self._user_denied,
                checkbox_call=self._dont_show_again_check,
                width=w,
                height=h,
            )
        CC.has_warned = True

    def _dont_show_again_check(self, val: bool) -> None:
        self._dsa_check = val

    def _user_acknowledged(self) -> None:
        logging.warning("Cloud Console allowed; executing requested code.")
        self._activity_pause(False)
        self.has_accepted = True
        self._write_to_config(True)

    def _user_denied(self) -> None:
        logging.warning("Cloud Console denied.")
        self.has_accepted = False
        self._write_to_config(False)

    def _write_to_config(self, v: bool) -> None:
        if not self._dsa_check:
            return
        cfg = bs.app.config
        cfg[CC.cfg_entry] = v
        cfg.apply()

    def _activity_pause(self, do_pause: bool) -> None:
        activity: bs.Activity | None = bs.get_foreground_host_activity()
        ba_classic = bs.app.classic

        if activity is None or ba_classic is None:
            return
        # hmm, this is an important pop-up, but if we
        # ignore being able to pause, it might get abused...
        if not activity.allow_pausing:
            return

        with activity.context:
            globs = activity.globalsnode
            if not globs.paused and do_pause:
                ba_classic.pause()
            elif not do_pause:
                ba_classic.resume()


CC = CloudControl()


def cloud_wrap(cloud_func):
    """Wrap around our cloud exec. function to show
    a warning before running any remote commands."""

    # TODO: It would be really cool if this could be handled
    # on a device basis; it's impossible to do so currently
    # as remote methods don't seem to store the source device
    # in any way.
    def wrapper(code: str) -> Any:
        cfg = bs.app.config
        cfg_entry = cfg.get(CC.cfg_entry, None)

        # TODO: hmm, we need a way to allow for this to be toggled easily...
        if CC.has_accepted is True or cfg_entry is True:
            return cloud_func(code)

        if CC.has_accepted is False or cfg_entry is False:
            # ignore all incoming commands if we denied.
            return None

        # show a pretty warning otherwise and
        # buffer all incoming commands for later.
        CC.show_warning()
        CC.add_exec(code)
        return None

    return wrapper


def _reset_config():
    cfg = bs.app.config
    cfg[CC.cfg_entry] = None
    cfg.apply()


_cloud.cloud_console_exec = cloud_wrap(_cloud.cloud_console_exec)
