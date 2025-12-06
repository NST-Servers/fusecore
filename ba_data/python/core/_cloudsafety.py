"""Wrapper for cloud console code execution
to make sure players are ok with it.
"""

from baplus import _cloud
import bascenev1 as bs

import logging

HAS_WARNED: bool = False
"""Pointer to make sure we only show the warning once per session."""
HAS_ACCEPTED: bool | None = None
"""Pointer of user knowledge."""
CODE_BUFFER: list = []
"""Store all cloud code here while we make sure the user consents of it."""


def run_code_buffer() -> None:
    """Execute all stored code."""
    for i, code in enumerate(CODE_BUFFER.copy()):
        activity = bs.get_foreground_host_activity()
        with activity.context if activity else bs.ContextRef.empty():
            bs.apptimer(0.1 * i, bs.CallStrict(_cloud.cloud_console_exec, code))

    CODE_BUFFER.clear()


def _activity_pause(do_pause: bool = True) -> None:
    """Try and pause the current activity."""
    activity: bs.Activity | None = bs.get_foreground_host_activity()
    ba_classic = bs.app.classic

    if activity is None or ba_classic is None:
        return

    with activity.context:
        globs = activity.globalsnode
        if not globs.paused and do_pause:
            ba_classic.pause()
        elif not do_pause:
            ba_classic.resume()


def user_allowed_remote_code() -> None:
    """Function to tell us if the user allowed for remote code."""
    _activity_pause(False)  # resume

    global HAS_ACCEPTED
    HAS_ACCEPTED = True

    logging.debug(
        'Cloud Console allowed! (temporarily)\n'
        'Executing all previously sent commands.'
    )

    run_code_buffer()


def cloud_wrap(cloud_func):
    # NOTE: It would be really cool if this could be handled
    # on a device basis; it's impossible to do so currently
    # as remote methods don't seem to store the source device
    # in any way.
    def wrapper(code: str):
        cfg = bs.app.config
        # TODO: hmm, we need a way to allow for this to be toggled easily...
        if cfg.get('Allow Cloud Console', False) or HAS_ACCEPTED:
            return cloud_func(code)
        else:
            if HAS_ACCEPTED is None:
                # If we haven't consented yet and we do want to
                # be notified about it, show the warning and buffer
                # all incoming commands
                global HAS_WARNED
                if not HAS_WARNED:
                    _activity_pause(True)
                    logging.warning('Awaiting for Cloud Console permission...')
                    from bauiv1lib.confirm import ConfirmWindow

                    with bs.ContextRef.empty():
                        # TODO: We need a Lstr!
                        ConfirmWindow(
                            bs.Lstr(
                                resource='remoteCodeWarning',
                                fallback_value=(
                                    'Heads up! Someone tried to run remote code\n'
                                    'via the "ballistica.net/devices" website.\n\n'
                                    'Press "Allow" if you\'re the one using the\n'
                                    'Cloud Console and know what you\'re doing.'
                                ),
                            ),
                            ok_text=bs.Lstr(resource="allowText"),
                            cancel_text=bs.Lstr(resource="noWayText"),
                            cancel_is_selected=True,
                            action=user_allowed_remote_code,
                            height=260,
                            width=612,
                        )
                    HAS_WARNED = True

                CODE_BUFFER.append(code)
            else:
                # Don't execute anything then
                # TODO: As of currently, this can't be reached due to
                # ConfirmWindow not accepting a "deny" action.
                # Fix that when we get our own window
                return None
        return None

    return wrapper


_cloud.cloud_console_exec = cloud_wrap(_cloud.cloud_console_exec)
