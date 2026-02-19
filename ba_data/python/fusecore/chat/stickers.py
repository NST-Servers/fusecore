"""Gameplay stickers executable via 'ChatIntercept'."""

from __future__ import annotations

import random
import logging
from typing import Optional, Type, cast, override

import bauiv1 as bui
import bascenev1 as bs

from bascenev1lib.actor.spaz import Spaz

from fusecore.chat import ChatIntercept
from fusecore.chat.utils import are_we_host, get_players_from_client_id

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
        message = msg.split(" ")
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

    callout = StickerCallout(sticker)

    client_players = get_players_from_client_id(client_id)

    with activity.context:
        # Do a character sticker pop-up if we're on a game activity
        # and this client has players attached to it.
        if isinstance(activity, bs.GameActivity) and client_players:
            for player in client_players:
                spaz: Optional[Spaz] = cast(Spaz, player.actor)
                if spaz:
                    callout.perform_in_game(spaz)
        # Display our sticker at UI level if we don't have any
        # players available, but are on an activity.
        else:
            callout.perform_ui(client_id)

    sticker().on_usage(client_id, activity)


class StickerCallout:
    """Callout class to display stickers in multiple ways."""

    def __init__(self, sticker_type: Type[ChatSticker]) -> None:
        self.sticker = sticker_type

    def perform_in_game(self, spaz: Spaz) -> None:
        """Show the provided sticker as a billboard."""
        if not spaz.node:
            return

        spaz.node.billboard_texture = bs.gettexture(self.sticker.texture_name)
        spaz.node.billboard_cross_out = False

        sticker_time = max(1000, self.sticker.duration_ms) / 1000

        # Do a cool animation!
        bs.animate(
            spaz.node,
            "billboard_opacity",
            self.sticker.spaz_billboard_animation_dict
            or {
                0.0: 0.0,
                0.08: SPAZ_STICKER_SCALE * 1.075,
                0.12: SPAZ_STICKER_SCALE,
                sticker_time: SPAZ_STICKER_SCALE,
                sticker_time + 0.1: 0.0,
            },
        )

        if self.sticker.sound_name:
            bs.getsound(self.sticker.sound_name).play()

    def perform_ui(self, client_id: int) -> None:
        """A sticker shown in the user interface.

        Usually pops up when using stickers while outside
        of a game activity or while a player is spectating.
        """
        _fallback_name = "Player"  # TODO: bs.Lstr this!
        _screen_distance = 3.8
        _on_top = True

        # get tex & sound from source sticker
        sticker_time = self.sticker.duration_ms * 0.75 / 1000
        tex = bs.gettexture(self.sticker.texture_name)
        snd = None
        if self.sticker.sound_name:
            snd = bui.getsound(self.sticker.sound_name)

        _screen_distance = sticker_time / _screen_distance

        plus = bui.app.plus
        assert plus is not None

        display_name: str | bui.Lstr
        roster = bs.get_game_roster()
        # if we don't have a roster, we're probably playing local...
        # display our account name or "Player" if we somehow manage
        # to send this sticker outside of our host client id.
        if not roster:
            assert bs.app.plus
            display_name = (
                bs.app.plus.get_v1_account_display_string()
                if client_id == -1
                else _fallback_name
            )
        # Fetch names when playing online.
        else:
            # look around out roster, get an entry matching
            # the client id and borrow the display string!
            pdict: dict = [
                n for n in roster if n.get("client_id", 0) == client_id
            ][0]
            display_name = pdict.get("display_string", _fallback_name)

        # Create our widgets!
        y = 45 + (15 if display_name else 0)
        random_x = random.choice(
            [random.uniform(-450, -170), random.uniform(170, 450)]
        )
        scale = 80
        image = bs.newnode(
            "image",
            attrs={
                "texture": tex,
                "position": (random_x, y),
                "vr_depth": -10,
                "color": (3, 3, 3),
                "scale": (0, 0),
                "opacity": 0,
                "absolute_scale": True,
                "attach": "bottomCenter",
                "front": _on_top,
            },
        )
        bs.animate(
            image,
            "opacity",
            {
                0.00: 0,
                0.07: 1,
                max(0.8, sticker_time - 0.8): 1,
                max(1, sticker_time): 0,
            },
        )
        bs.animate_array(
            image,
            "scale",
            2,
            {
                0.00: tuple(scale for _ in range(2)),
                0.07: tuple(scale * 1.17 for _ in range(2)),
                0.09: tuple(scale * 1.17 for _ in range(2)),
                0.14: tuple(scale for _ in range(2)),
            },
        )
        bs.animate_array(
            image,
            "position",
            2,
            {
                0.0: (random_x, y),
                0.02: (random_x, y + 9),
                0.04: (random_x, y + 15),
                0.06: (random_x, y + 18),
                max(0.08, sticker_time): (
                    random_x,
                    y + (scale * _screen_distance),
                ),
            },
        )
        bs.animate_array(
            image,
            "color",
            3,
            {
                0.00: tuple(2.33 for _ in range(3)),
                0.12: tuple(1 for _ in range(3)),
            },
        )
        y -= scale - 10
        text = bs.newnode(
            "text",
            attrs={
                "text": display_name,
                "color": (1, 1, 1),
                "position": (random_x, y),
                "vr_depth": -12,
                "h_align": "center",
                "v_align": "bottom",
                "h_attach": "center",
                "v_attach": "bottom",
                "shadow": 1,
                "flatness": 0.66,
                "maxwidth": 80,
                "front": _on_top,
            },
        )
        bs.animate(
            text,
            "opacity",
            {
                0.00: 0,
                0.11: 1,
                max(0.8, sticker_time - 0.8): 1,
                max(1, sticker_time): 0,
            },
        )
        bs.animate_array(
            text,
            "position",
            2,
            {
                0.0: (random_x, y),
                0.02: (random_x, y + 9),
                0.04: (random_x, y + 15),
                0.06: (random_x, y + 18),
                max(0.08, sticker_time): (
                    random_x,
                    y + (scale * _screen_distance),
                ),
            },
        )

        if snd:
            snd.play(0.77)
