"""Defines our custom SpazBot class."""

from __future__ import annotations
from typing import Type, override

import bascenev1 as bs
from claymore._tools import obj_clone, obj_method_override
import bascenev1lib.actor.spazbot as vanilla_spazbot

# Clone our vanilla spaz class
# We'll be calling this over "super()" to prevent the code
# from falling apart because the engine is like that.
SpazClass: Type[vanilla_spazbot.SpazBot] = obj_clone(vanilla_spazbot.SpazBot)


class SpazBot(vanilla_spazbot.SpazBot):
    """Wrapper for our actor Spaz class."""

    @override
    def __init__(self, *args, **kwargs):
        SpazClass.__init__(
            self, *args, **kwargs
        )  # FIXME: Troubleshoot this line?

    def get_ruleset_dict(self) -> dict:
        """Default SpazBot will ALWAYS get the vanilla BombSquad ruleset."""
        return {}  # clay.ruleset.get_vanilla_ruleset_dict()


# Overwrite the vanilla game's spaz init with our own
obj_method_override(vanilla_spazbot.SpazBot, SpazBot)
