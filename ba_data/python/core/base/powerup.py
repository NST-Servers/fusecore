"""Customizable powerups from core."""

from __future__ import annotations
from abc import abstractmethod
from typing import Type, override, TYPE_CHECKING

from bascenev1lib.actor.spaz import SpazFactory

from ..base.factory import Factory, FactoryTexture, FactoryClass
from ..base.shared import PowerupSlotType
from ..base.bomb import (
    Bomb,
    IceBomb,
    StickyBomb,
    ImpactBomb,
)
from ..base.spazfactory import SpazComponent

if TYPE_CHECKING:
    import bascenev1 as bs
    from core.base.spaz import Spaz

POWERUP_SET: set[Type[SpazPowerup]] = set()
DEFAULT_POWERUP_DURATION: int = 20000

# These classes don't require much explanation, I think...
# pylint: disable=missing-class-docstring
# pylint: disable=too-few-public-methods


class PowerupFactory(Factory):
    """Library class containing shared powerup
    data to prevent gameplay hiccups."""

    IDENTIFIER = '_powerup_factory'


class SpazPowerup(FactoryClass):
    """A powerup assigned to a Spaz class that performs
    actions on their behalf.
    """

    my_factory = PowerupFactory
    """Factory used by this FactoryClass instance."""
    group_set = POWERUP_SET
    """Set to register this FactoryClass under."""

    slot: PowerupSlotType = PowerupSlotType.NONE
    """Slot used by this powerup.

    This can be assigned 1, 2, 3 for a powerup slot in our spaz,
    or 0 to discard the slot usage.

    Leaving this as 0 will make the powerup not occupy a slot,
    but will instead be treated as a one-use power with no duration
    and won't run its warning or unequip functions.
    """

    duration_ms: int = DEFAULT_POWERUP_DURATION
    """The integer duration of this powerup in milliseconds.
    (Default: 20000ms -> 20 secs.)
    """

    texture_name: str = 'empty'
    """A texture (as a string) assigned to this powerup. (Default: "empty")

    To make it invisible, set to 'empty' -- though it's not recommended to
    do this UNLESS the powerup doesn't use a slot (e.g. Shield, Curse.)
    """

    @classmethod
    def _register_texture(cls) -> None:
        """Register our unique texture."""
        cls.my_factory.register_resource(
            f'{cls.texture_name}', FactoryTexture(cls.texture_name)
        )

    @classmethod
    def register(cls) -> None:
        # Load up our unique texture and continue
        cls._register_texture()
        return super().register()

    @override
    def __init__(self, spaz: Spaz) -> None:
        """Initialize our powerup."""
        super().__init__()
        self.factory: PowerupFactory
        self.spaz = spaz

        self.duration_ms = self.duration_ms

    @abstractmethod
    def equip(self) -> None:
        """Method called to spaz when this powerup is equipped."""

    def warning(self) -> None:
        """Method called 3 seconds before this powerup is unequipped.

        ### WARNING:
        This method is called ONLY when the powerup runs out naturally,
        meaning it does NOT get called when another powerup overrides
        it or the player dies.

        This function should be reserved to non-critical powerup
        logic such as visual indicators or effects.
        """

    def unequip(self, overwrite: bool, clone: bool) -> None:
        """Method called when this powerup is unequipped.

        This includes when the powerup is overwritten by another
        powerup, including the same type.
        """
        del overwrite
        del clone

    def get_texture(self) -> bs.Texture:
        """Return the factory texture of this powerup."""
        return self.factory.instance().fetch(self.texture_name)


class TripleBombsPowerup(SpazPowerup):
    """A powerup that allows spazzes to throw up to three bombs."""

    slot = PowerupSlotType.BUFF
    texture_name = 'powerupBomb'

    @override
    def equip(self) -> None:
        # Because "unequip()" will run each time we equip
        # this powerup, we won't be able to stack bombs, so
        # we don't have to worry about making checks about it.
        self.spaz.add_bomb_count(2)

    @override
    def unequip(self, overwrite: bool, clone: bool) -> None:
        self.spaz.add_bomb_count(-2)


TripleBombsPowerup.register()


class BombPowerup(SpazPowerup):
    """A powerup that grants the provided bomb type."""

    slot = PowerupSlotType.BOMB

    bomb_type: Type[Bomb] = Bomb
    """Bomb type to assign when this powerup is picked up."""

    @override
    def equip(self) -> None:
        self.spaz.assign_bomb_type(self.bomb_type)

    @override
    def unequip(self, overwrite: bool, clone: bool) -> None:
        self.spaz.reset_bomb_type()


class StickyBombsPowerup(BombPowerup):
    texture_name = 'powerupStickyBombs'
    bomb_type = StickyBomb


StickyBombsPowerup.register()


class IceBombsPowerup(BombPowerup):
    texture_name = 'powerupIceBombs'
    bomb_type = IceBomb


IceBombsPowerup.register()


class ImpactBombsPowerup(BombPowerup):
    texture_name = 'powerupImpactBombs'
    bomb_type = ImpactBomb


ImpactBombsPowerup.register()


class LandMinesPowerup(SpazPowerup):
    texture_name = 'empty'

    @override
    def equip(self) -> None:
        self.spaz.set_land_mine_count(min(self.spaz.land_mine_count + 3, 3))


LandMinesPowerup.register()


class PunchPowerup(SpazPowerup):
    """A powerup which grants boxing gloves to a spaz."""

    slot = PowerupSlotType.GLOVES
    texture_name = 'powerupPunch'

    # This powerup has some built-in functions; don't have to do much about it.
    @override
    def equip(self) -> None:
        self.spaz.equip_boxing_gloves()

    @override
    def warning(self) -> None:
        self.spaz.node.boxing_gloves_flashing = True

    @override
    def unequip(self, overwrite: bool, clone: bool) -> None:
        # Custom function that removes gloves without
        # forcefully playing the "powerdown" sound and
        # sets "spaz.node.boxing_gloves_flashing" to False.
        self.spaz.unequip_boxing_gloves()


PunchPowerup.register()


class ShieldComponent(SpazComponent):
    """Spaz component to handle shields."""

    def activate(self) -> None:
        """Grant this spaz a shield."""
        # i was thinking of replacing the glove & shield system over components
        # to demonstrate how cool components are, but then i thought of the
        # billions of incompatibilities this would cause, so now the component
        # is a simple shield activation tunnel :p
        self.spaz.equip_shields(decay=SpazFactory.get().shield_decay_rate > 0)

    def on_damage(self) -> None:
        """Handle our damage function."""
        # unused as per stated above...

    def super_awesome_secret_method_that_makes_your_spaz_explode(self) -> None:
        "funny."
        self.spaz.curse_explode()


class ShieldPowerup(SpazPowerup):
    texture_name = 'empty'

    @override
    def equip(self) -> None:
        component: ShieldComponent = self.spaz.get_component(ShieldComponent)
        component.activate()


ShieldComponent.register()
ShieldPowerup.register()


class HealthPowerup(SpazPowerup):
    texture_name = 'powerupHealth'

    @override
    def equip(self) -> None:
        self.spaz.heal()


HealthPowerup.register()


class CursePowerup(SpazPowerup):
    texture_name = 'empty'

    @override
    def equip(self) -> None:
        self.spaz.curse()


CursePowerup.register()
