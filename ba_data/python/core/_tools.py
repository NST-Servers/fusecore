from typing import Any, Type, override

import bascenev1 as bs
import inspect
import ctypes
import os

import babase
from babase._devconsole import DevConsoleTab, DevConsoleTabEntry


def send(msg: str, condition: bool = True) -> None:
    """Show a message on-screen and log it simultaneously.

    DEPRECATED: Only keeping this here to make code rewriting
    a bit easier; use a proper logging system for more
    efficient debugging.
    """
    if not condition:
        return

    i_am: str
    try:  # get a dirty string path to this script.
        i_am = inspect.getmodule(inspect.stack()[1][0]).__name__  # type: ignore
    except:
        i_am = 'file'
    i_am += '.py'

    bs.screenmessage(f'{msg}')
    print(f'[{i_am}]: {msg}')


def obj_clone(cls) -> Type[Any]:
    """Clone and return a pure object type with no references.

    Returns:
        Type[object]: Object to clone
    """ """"""
    return type(cls.__name__, cls.__bases__, dict(cls.__dict__))


def obj_method_override(obj_to_override: object, obj_source: object) -> None:
    """Override all of a object's methods with another one's.

    Args:
        obj_to_override (object): Object whose methods will get overriden
        obj_source (object): Object with methods we want to override with
    """ """"""
    for name, v in obj_source.__dict__.items():
        if callable(v) or isinstance(v, (staticmethod, classmethod)):
            setattr(obj_to_override, name, v)


def is_admin() -> bool:
    """Check if we are running this program as administrator / with sudo.
    Returns:
        bool: Whether operator privileges are enabled
    """
    platform: str = bs.app.classic.platform  # type: ignore
    try:
        if platform in ['windows', 'win32']:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        if platform == 'linux':
            return os.getpid() == 0
        # couldn't care less about mac tbh :p
        return False
    except Exception:  # don't crash over a failure
        return False


def is_server() -> bool:
    """Return whether we're running as a server or not."""
    classic = bs.app.classic
    if classic is None:
        raise RuntimeError('classic is unexpectedly none')

    return not classic.server is None


PLAYLIST_NAME_BLACKLIST = ['__default__', '__playlist_create__']


def playlist_cleanse() -> None:
    """Check for and remove any playlists with troublesome names."""
    if bs.app.plus is None:
        return

    # Check all available playlist lists.
    for group in ['Free-for-All', 'Team Tournament']:
        for name, _ in bs.app.config.get(f'{group} Playlists', {}).items():
            # If a playlist name is in the list of
            # faulty names, remove it.
            if name in PLAYLIST_NAME_BLACKLIST:
                bs.app.plus.add_v1_account_transaction(
                    {
                        'type': 'REMOVE_PLAYLIST',
                        'playlistType': group,
                        'playlistName': name,
                    }
                )
    # Run all transactions.
    bs.app.plus.run_v1_account_transactions()


DISCORD_SM_COLOR = (0.44, 0.53, 0.85)


class toolsTab(DevConsoleTab):

    @override
    def refresh(self) -> None:

        x, y = (0, 40)
        btn_size_x, btn_size_y = (175, 40)

        self.discordrp_button = self.button(
            self._get_discordrp_btn_label(),
            pos=(x - (btn_size_x / 2), y - (btn_size_y / 2)),
            size=(btn_size_x, btn_size_y),
            label_scale=0.75,
            call=self.toggle_discordrp,
        )

    def _get_discordrp_btn_label(self) -> str:
        import core

        drp = core.DiscordRP

        return 'Disable DiscordRP' if drp._is_active() else 'Enable DiscordRP'

    def toggle_discordrp(self) -> None:
        import core

        drp = core.DiscordRP
        msg: str = ''

        if drp._is_active():
            msg = 'DiscordRP stopped.'
            drp.stop()
        else:
            msg = 'Starting up DiscordRP...'
            drp.start()
        bs.screenmessage(msg, DISCORD_SM_COLOR)

        self.request_refresh()


def add_devconsole_tab(name: str, console_tab: Type[DevConsoleTab]) -> None:
    babase.app.devconsole.tabs.append(DevConsoleTabEntry(name, console_tab))
