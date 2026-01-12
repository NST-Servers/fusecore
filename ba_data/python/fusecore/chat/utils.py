"""Shared utilities for chat related functions."""

from typing import Optional, TypedDict

import bascenev1 as bs
from bascenev1._hooks import local_chat_message
import bauiv1 as bui

SENDER_OVERRIDE_DEFAULT: str = f"{bui.charstr(bui.SpecialChar.LOGO_FLAT)}"


def are_we_host() -> bool:
    """Return whether this action is being passed by the host or not."""
    return bs.get_foreground_host_session() is not None


class _UserPlayers(TypedDict):
    name: str
    name_full: str
    id: int


class UserRosterInfo(TypedDict):
    """Dict. containing in-game user information
    based on ``bs.get_game_roster``'s entries.
    """

    display_string: str
    spec_string: str
    players: list[_UserPlayers]
    client_id: int
    account_id: str


def get_user_from_client_id(client_id: int) -> Optional[UserRosterInfo]:
    """Get user information attached to a 'client_id'."""
    roster: list[dict] = bs.get_game_roster()
    if not roster:
        return None
    for player in roster:
        assert player is UserRosterInfo
        if client_id == player.get("client_id", None):
            return player
    return None


def get_players_from_client_id(client_id: int) -> list[bs.Player]:
    """Get a list of in-game spazzes related to a 'client_id'."""
    activity: bs.Activity | None = bs.get_foreground_host_activity()
    if activity is None:
        return []

    player_list: list[bs.Player] = []

    for player in activity.players:
        if player.sessionplayer.inputdevice.client_id == client_id:
            player_list.append(player)

    return player_list


def broadcast_message_to_client(
    client_id: int,
    message: str | bs.Lstr,
    color: tuple[float, float, float] = (1, 1, 1),
) -> None:
    """Pass a broadcast message to a specific client."""

    bs.broadcastmessage(
        message,
        clients=[client_id],
        color=color,
        transient=True,
    )


def send_custom_host_message(
    text: str,
    clients: Optional[list[int]] = None,
    sender: Optional[str] = None,
) -> None:
    """Customized ``bs.chatmessage``.

    Can only be used in server-side commands, usage on
    client commands will result in an ignored function.

    Args:
        text (str): Message to send
        clients (Optional[list[int]], optional):
            IDs of the clients to send this message to.
        sender (Optional[str], optional):
            Custom sender name. If not provided, the
            ``SENDER_OVERRIDE_DEFAULT`` string will be used instead.

            Defaults to None.
    """
    if not are_we_host():
        return

    if sender is None:
        sender = SENDER_OVERRIDE_DEFAULT

    if clients and -1 in clients:
        # FIXME: while this works, the message immediately vanishes once
        # the party window is closed, which is pretty silly.
        for t in text.splitlines():
            local_chat_message(f"{sender}: {t}")
        clients.remove(-1)

    bs.chatmessage(text, clients=clients, sender_override=sender)
