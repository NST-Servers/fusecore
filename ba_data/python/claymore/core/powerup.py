from __future__ import annotations
from abc import abstractmethod
from enum import Enum
from typing import Type, override, TYPE_CHECKING

from bascenev1lib.actor.spaz import SpazFactory

from claymore.core.factory import Factory, FactoryTexture, FactoryClass
from claymore.core.shared import PowerupSlotType

if TYPE_CHECKING:
    import bascenev1 as bs
    from claymore.core.spaz import Spaz

POWERUP_SET: set[Type[SpazPowerup]] = set()
DEFAULT_POWERUP_DURATION: int = 20000


class PowerupFactory(Factory):
    """Library class containing shared powerup
    data to prevent gameplay hiccups."""

    IDENTIFIER = '_powerup_factory'


class SpazPowerup(FactoryClass):
    """ """

    my_factory = PowerupFactory
    """Factory used by this FactoryClass instance."""
    group_set = POWERUP_SET
    """Set to register this FactoryClass under."""

    name: str = 'powerup'
    """Name of this powerup."""

    slot: PowerupSlotType = PowerupSlotType.NONE
    """Slot used by this powerup. (Default: 0)

    This can be assigned 1, 2, 3 for a powerup slot in our spaz,
    or 0 to discard the slot usage.

    Leaving this as 0 will make the powerup not occupy a slot,
    but will instead be treated as a one-use power with no duration
    and won't run its warning or unequip functions.
    """

    duration_ms: int = DEFAULT_POWERUP_DURATION
    """The integer duration of this powerup in milliseconds.
    (Default: 20000 [20 secs.])
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
    def __init__(self) -> None:
        """Initialize our powerup."""
        super().__init__()
        self.factory: PowerupFactory

        # Adjust powerup duration to clay's ruleset system
        # TODO: todo
        self.duration_ms = self.duration_ms

    @abstractmethod
    def equip(self, spaz: Spaz) -> None:
        """Method called to spaz when this powerup is equipped."""

    @abstractmethod
    def warning(self, spaz: Spaz) -> None:
        """Method called 3 seconds before this powerup is unequipped.

        ### WARNING:
        This method is called ONLY when the powerup runs out naturally,
        meaning it does NOT get called when another powerup overrides
        it or the player dies.

        This function should be reserved to non-critical powerup
        logic such as visual indicators or effects.
        """

    @abstractmethod
    def unequip(self, spaz: Spaz, overwrite: bool, clone: bool) -> None:
        """Method called when this powerup is unequipped.

        This includes when the powerup is overwritten by another
        powerup, including the same type.
        """

    def get_texture(self) -> bs.Texture:
        """Return the factory texture of this powerup."""
        return self.factory.instance().fetch(self.texture_name)


class TripleBombsPowerup(SpazPowerup):
    """A powerup that allows spazzes to throw up to three bombs."""

    name = 'triple_bombs'
    slot = PowerupSlotType.BUFF
    texture_name = 'powerupBomb'

    def equip(self, spaz: Spaz) -> None:
        # Because "unequip()" will run each time we equip
        # this powerup, we won't be able to stack bombs, so
        # we don't have to worry about making checks about it.
        spaz.add_bomb_count(2)

    def unequip(self, spaz: Spaz, overwrite: bool, clone: bool) -> None:
        spaz.add_bomb_count(-2)


TripleBombsPowerup.register()


class BombPowerup(SpazPowerup):
    """A powerup that grants the provided bomb type."""

    name = 'empty bomb powerup'
    slot = PowerupSlotType.BOMB

    bomb_type: str = 'normal'
    """Bomb type to assign when this powerup is picked up."""

    def equip(self, spaz: Spaz) -> None:
        spaz.set_bomb_type(self.bomb_type)

    def unequip(self, spaz: Spaz, overwrite: bool, clone: bool) -> None:
        spaz.reset_bomb_type()


class StickyBombsPowerup(BombPowerup):
    name = 'sticky_bombs'
    bomb_type = 'sticky'
    texture_name = 'powerupStickyBombs'


StickyBombsPowerup.register()


class IceBombsPowerup(BombPowerup):
    name = 'ice_bombs'
    bomb_type = 'ice'
    texture_name = 'powerupIceBombs'


IceBombsPowerup.register()


class ImpactBombsPowerup(BombPowerup):
    name = 'impact_bombs'
    bomb_type = 'impact'
    texture_name = 'powerupImpactBombs'


ImpactBombsPowerup.register()


class LandMinesPowerup(SpazPowerup):
    name = 'land_mines'
    texture_name = 'empty'

    def equip(self, spaz: Spaz) -> None:
        spaz.set_land_mine_count(min(spaz.land_mine_count + 3, 3))


LandMinesPowerup.register()


class PunchPowerup(SpazPowerup):
    """A powerup which grants boxing gloves to a spaz."""

    name = 'punch'
    slot = PowerupSlotType.GLOVES
    texture_name = 'powerupPunch'

    # This powerup has some built-in functions; don't have to do much about it.
    def equip(self, spaz: Spaz) -> None:
        spaz.equip_boxing_gloves()

    def warning(self, spaz: Spaz) -> None:
        spaz.node.boxing_gloves_flashing = True

    def unequip(self, spaz: Spaz, overwrite: bool, clone: bool) -> None:
        # Custom Claypocalypse function that removes gloves without
        # forcefully playing the "powerdown" sound and
        # sets "spaz.node.boxing_gloves_flashing" to False.
        spaz.gloves_silent_unequip()


PunchPowerup.register()


class ShieldPowerup(SpazPowerup):
    name = 'shield'
    texture_name = 'empty'

    def equip(self, spaz: Spaz) -> None:
        spaz.equip_shields(decay=SpazFactory.get().shield_decay_rate > 0)


ShieldPowerup.register()


class HealthPowerup(SpazPowerup):
    name = 'health'
    texture_name = 'powerupHealth'

    def equip(self, spaz: Spaz) -> None:
        spaz.heal()


HealthPowerup.register()


class CursePowerup(SpazPowerup):
    name = 'curse'
    texture_name = 'empty'

    def equip(self, spaz: Spaz) -> None:
        spaz.curse()


CursePowerup.register()
