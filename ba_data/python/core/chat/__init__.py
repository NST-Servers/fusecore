"""Chat interceptors allowing for message reading and function executing."""

from __future__ import annotations

from abc import abstractmethod
from typing import Type

import bascenev1 as bs
import bauiv1 as bui

CHAT_INTERCEPTS_SET: set[Type[ChatIntercept]] = set()

SENDER_OVERRIDE_DEFAULT: str = f'{bui.charstr(bui.SpecialChar.LOGO_FLAT)}'


class ChatIntercept:
    """Chat interception that does nifty stuff."""

    @classmethod
    def register(cls) -> None:
        """Register this class into our intercepts set."""
        CHAT_INTERCEPTS_SET.add(cls)

    @abstractmethod
    def intercept(self, msg: str, client_id: int) -> bool:
        """returns whether we want to deliver this message."""
        raise RuntimeError("'interception' function has to be overriden.")


def chat_message_intercept(msg: str, client_id: int) -> str | None:
    """Chat message function interception to read sent
    messages and run whatever functions and code we want.
    """
    for intercept in CHAT_INTERCEPTS_SET:
        if not intercept().intercept(msg, client_id):
            return None

    return msg


def broadcast_message_to_client(
    client_id: int,
    message: str | bs.Lstr,
    color: tuple[float, float, float] = (1, 1, 1),
) -> None:
    """Send a broadcast message to a specific client."""

    bs.broadcastmessage(
        message,
        clients=[client_id],
        color=color,
        transient=True,
    )


def get_players_from_client_id(client_id: int) -> list[bs.Player]:
    """Get all in-game 'PlayerSpaz'es linked to the provided 'client_id'."""
    activity: bs.Activity | None = bs.get_foreground_host_activity()
    if activity is None:
        return []

    player_list: list[bs.Player] = []

    for player in activity.players:
        if player.sessionplayer.inputdevice.client_id == client_id:
            player_list.append(player)

    return player_list


def send_custom_chatmessage(
    text: str,
    clients: list | None = None,
    sender: str | None = None,
) -> None:
    """bs.chatmessage with an overriden sender.
    Default sender is a "host only" sender icon.
    """
    if sender is None:
        sender = SENDER_OVERRIDE_DEFAULT

    # FIXME: Sending a chatmessage with clients '-1'
    # (which would usually stand for the host) doesn't
    # do anything! Gotta figure out a way to store
    # messages locally.
    bs.chatmessage(text, clients=clients, sender_override=sender)


def are_we_host() -> bool:
    """Return whether we are hosting or not."""
    return bs.get_foreground_host_session() is not None
