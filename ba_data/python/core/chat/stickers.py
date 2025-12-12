"""Gameplay stickers executable via 'ChatIntercept'."""

from __future__ import annotations

import logging
from typing import Type, cast, override

import bascenev1 as bs
from bascenev1lib.actor.spaz import Spaz

from core.chat import ChatIntercept, get_players_from_client_id, are_we_host

STICKER_ATLAS: set[Type[ChatSticker]] = set()
STICKER_DEFAULT: Type[ChatSticker] | None = None

STICKER_PREFIXES: list[str] = [";"]

SPAZ_STICKER_SCALE: float = 2.75


class StickerIntercept(ChatIntercept):
    """Chat interception for reading stickers."""

    @override
    def intercept(self, msg: str, client_id: int) -> bool:
        if not are_we_host():
            return True

        for stkprefix in STICKER_PREFIXES:
            if msg.startswith(stkprefix):
                return not self.cycle_thru_stickers(msg, client_id, stkprefix)
        return True

    def cycle_thru_stickers(
        self, msg: str, client_id: int, command_prefix: str
    ) -> bool:
        """Match a message to any available sticker and run it.

        Returns success.
        """
        message = msg.split(' ')
        sticker_entry = message[0].removeprefix(command_prefix)
        del message

        # in case got a message with nothing but a prefix, ignore
        if not sticker_entry:
            return False

        for sticker in STICKER_ATLAS:
            if sticker_entry in sticker.pseudos:
                run_sticker(client_id, sticker)
                return True

        return False


StickerIntercept.register()


class ChatSticker:
    """A sticker that can be triggered via chat messages."""

    name: str = "Sticker Name"
    """Name of this sticker.
    
    This name is not used when checking for pseudos and
    is purely to give the sticker a display name.
    """
    pseudos: list[str] = []
    """Command names to use the sticker."""

    texture_name: str
    """Name of the texture this sticker uses."""
    sound_name: str | None = None
    """Name of the sound effect to play when using the sticker."""

    duration_ms: int = 3000
    spaz_billboard_animation_dict: dict[float, float] = {}

    @classmethod
    def register(cls) -> None:
        """Add this sticker into our sticker set for usage."""
        if len(cls.pseudos) < 1:
            logging.warning(
                'no pseudos given to sticker "%s", so it can\'t be used!',
                cls.name,
            )
        STICKER_ATLAS.add(cls)

    @classmethod
    def on_usage(
        cls, client_id: int, activity: bs.Activity | None = None
    ) -> None:
        """Action to perform when this sticker is used."""


def run_sticker(client_id: int, sticker: Type[ChatSticker]) -> None:
    """Display the provided sticker depending on current context."""
    activity: bs.Activity | None = bs.get_foreground_host_activity()
    if activity is None:
        return

    client_players = get_players_from_client_id(client_id)

    if isinstance(activity, bs.GameActivity) and client_players:
        # if a player runs a sticker while they have a spaz in-game
        for player in client_players:
            spaz: Spaz | None = cast(Spaz, player.actor)

            if spaz:
                with activity.context:
                    SpazStickerCallout.show_sticker_billboard(spaz, sticker)  # type: ignore
    else:
        pass

    sticker().on_usage(client_id, activity)


class SpazStickerCallout(Spaz):
    """Class function wrap to act in a spaz's behalf."""

    def show_sticker_billboard(self, sticker: Type[ChatSticker]) -> None:
        """Show the provided sticker as a billboard."""
        if not self.node:
            return

        self.node.billboard_texture = bs.gettexture(sticker.texture_name)
        self.node.billboard_cross_out = False

        sticker_time = max(1000, sticker.duration_ms) / 1000

        # Do a cool animation!
        bs.animate(
            self.node,
            'billboard_opacity',
            sticker.spaz_billboard_animation_dict
            or {
                0.0: 0.0,
                0.08: SPAZ_STICKER_SCALE * 1.075,
                0.12: SPAZ_STICKER_SCALE,
                sticker_time: SPAZ_STICKER_SCALE,
                sticker_time + 0.1: 0.0,
            },
        )

        if sticker.sound_name:
            bs.getsound(sticker.sound_name).play()
