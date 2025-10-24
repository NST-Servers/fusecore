"""Defines our Claypocalypse SpazFactory modified class."""

from __future__ import annotations
from typing import Type, override

import bascenev1 as bs
from claymore._tools import obj_clone, obj_method_override
from bascenev1lib.actor import spazfactory

# clone original to use functions later on
VanillaSpazFactory: Type[spazfactory.SpazFactory] = obj_clone(
    spazfactory.SpazFactory
)


class SpazFactory(spazfactory.SpazFactory):
    """New SpazFactory that replaces some files."""

    @override
    def __init__(self, *args, **kwargs):
        VanillaSpazFactory.__init__(self, *args, **kwargs)


# Overwrite the vanilla game's spaz init with our own
obj_method_override(spazfactory.SpazFactory, SpazFactory)
