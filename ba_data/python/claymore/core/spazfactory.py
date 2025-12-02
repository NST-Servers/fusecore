"""Defines our custom SpazFactory class."""

from __future__ import annotations
from typing import TYPE_CHECKING, Type, override

import bascenev1 as bs
from bascenev1lib.actor import spazfactory

from bascenev1lib.actor.powerupbox import PowerupBoxFactory
from claymore._tools import obj_clone, obj_method_override, send

# clone original to use functions later on
VanillaSpazFactory: Type[spazfactory.SpazFactory] = obj_clone(
    spazfactory.SpazFactory
)

if TYPE_CHECKING:
    from claymore.core.spaz import Spaz, SpazPowerup

VERBOSE: bool = False


class SpazPowerupSlot:

    def __init__(self, owner: Spaz) -> None:
        self.owner = owner

        self.active_powerup: SpazPowerup | None = None
        self.timer_warning: bs.Timer | None = None
        self.timer_wearoff: bs.Timer | None = None

    def apply_powerup(self, powerup: SpazPowerup) -> None:
        """Give the spaz the provided powerup."""
        if not self.owner.exists():
            return

        if self.active_powerup:  # unequip previous powerup
            self._unequip(overwrite=True, clone=self.active_powerup is powerup)
        self.active_powerup = powerup

        self._do_powerup()
        self._do_spaz_billboard_and_animate()
        # previous functions should never fail unless the
        # powerup's parameters are faulty; ez troubleshooting
        powerup.equip()

    def _do_powerup(self) -> None:
        """Arm this powerup's wearoff and unequip timers."""
        if not self.active_powerup or not self.owner.exists():
            return

        self.timer_warning = bs.Timer(
            max(
                0,
                (
                    self.active_powerup.duration_ms
                    - self.owner._powerup_wearoff_time_ms
                )
                / 1000,
            ),
            self._warn,
        )
        self.timer_wearoff = bs.Timer(
            self.active_powerup.duration_ms / 1000,
            self._unequip,
        )
        if self.active_powerup.texture_name != 'empty':
            self.owner._flash_billboard(
                bs.gettexture(self.active_powerup.texture_name)
            )

    def _do_spaz_billboard_and_animate(self) -> None:
        if not self.active_powerup or not self.owner.exists():
            return

        self.owner.node.handlemessage('flash')
        self.owner._powerup_billboard_slot(self.active_powerup)

    def _warn(self) -> None:
        if not self.active_powerup or not self.owner.exists():
            return

        self.active_powerup.warning()
        self.owner._powerup_warn(self.active_powerup.texture_name)

    def _unequip(self, overwrite: bool = False, clone: bool = False) -> None:
        if not self.active_powerup or not self.owner.exists():
            return

        self.owner._powerup_unwarn()
        PowerupBoxFactory.get().powerdown_sound.play(
            position=self.owner.node.position,
        )  # TODO: replace this for a sound from OUR PowerupFactory
        self.active_powerup.unequip(overwrite=overwrite, clone=clone)
        self.active_powerup = None
        self.timer_warning = None
        self.timer_wearoff = None


SPAZ_COMPONENTS: set[Type[SpazComponent]] = set()


class SpazComponent:
    """Components are a collection of attributes to be
    added to our spaz class.
    They provide an easy and compatible way of adding custom
    behavior to characters without having to inject code into
    functions while remaining compatible with other components.
    """

    def __init__(self, spaz: Spaz) -> None:
        self.spaz: Spaz = spaz

    @classmethod
    def register(cls) -> None:
        """Register this component to our spaz component set."""
        SPAZ_COMPONENTS.add(cls)


class SpazFactory(spazfactory.SpazFactory):
    """New SpazFactory that replaces some files."""

    @override
    def __init__(self, *args, **kwargs):
        VanillaSpazFactory.__init__(self, *args, **kwargs)


# Overwrite the vanilla game's spaz init with our own
obj_method_override(spazfactory.SpazFactory, SpazFactory)
