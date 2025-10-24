from __future__ import annotations
from typing import Type, override, TYPE_CHECKING

if TYPE_CHECKING:
    import bascenev1 as bs

from claymore.core.spaz import Spaz
from claymore.core.factory import Factory, FactoryTexture, FactoryClass

POWERUP_SET: set[Type[SpazPowerup]] = set()
DEFAULT_POWERUP_DURATION: int = 20000


class PowerupFactory(Factory):
    """Library class containing shared powerup
    data to prevent gameplay hiccups."""

    IDENTIFIER = '_powerup_factory'


class SpazPowerup(FactoryClass):
    """ """

    factory_class = PowerupFactory
    """***Factory used by this actor. Do not change.***"""
    groupset = POWERUP_SET
    """***Set to register this actor to. Do not change.***"""

    name: str = 'powerup'
    """*String* name of this powerup."""

    slot: int = 0
    """
    Slot *integer* used by this powerup. (Default: 0)

    This can be assigned 1, 2, 3 for a powerup slot in our spaz,
    or 0 to discard the slot usage.

    Leaving this as 0 will make the powerup not occupy a slot,
    but will instead be treated as a one-use power with no duration
    and won't run its warning or unequip functions.
    """

    duration: int = DEFAULT_POWERUP_DURATION
    """
    The *integer* duration of this powerup in milliseconds.
    (Default: 20000 [20 secs.])
    """

    texture: str = 'cl_powerup_empty'
    """
    A texture *string* assigned to this powerup. (Default: "cl_powerup_empty")

    To make it invisible, set to **"empty"** -- though it's not recommended to
    do this UNLESS the powerup doesn't use a slot *(e.g. Shield, Curse.)*
    """

    @classmethod
    def _reg_texture(cls) -> None:
        """Register our unique texture."""
        cls.factory_class.register_resource(
            f'{cls.texture}', FactoryTexture(cls.texture)
        )

    @classmethod
    def register(cls) -> None:
        # Load up our unique texture and continue
        cls._reg_texture()
        return super().register()

    @override
    def __init__(self) -> None:
        """Initialize our powerup."""
        super().__init__()
        self.factory: PowerupFactory
        # Let's run some integrity checks to make sure everything
        # starts up correctly.
        if not isinstance(self.slot, int):
            self.slot = 0
        elif not 3 >= self.slot >= 0:
            raise ValueError('Slot is out of range (Can only be 0, 1, 2 or 3.)')

        # Adjust powerup duration to clay's ruleset system
        # TODO: todo
        self.duration = self.duration

    def equip(self, spaz: Spaz) -> None:
        """Method called when this powerup is equipped."""

    def warning(self, spaz: Spaz) -> None:
        """
        Method called 3 seconds before this powerup is unequipped.

        This method is NOT called when the powerup is overwritten
        by another one, so it should only be used exclusively for
        timeout animations and other visual shebangs.
        """

    def unequip(self, spaz: Spaz) -> None:
        """
        Method called when this powerup is unequipped.

        This includes when the powerup is overwritten by another
        powerup taking up the same slot.
        """
        # TODO: Add a "is_overwrite" type argument

    def get_texture(self) -> bs.Texture:
        """Return the factory texture of this powerup."""
        return self.factory.instance().fetch(self.texture)


class TripleBombsPowerup(SpazPowerup):
    """A powerup that allows spazzes to throw up to three bombs."""

    name = 'triple_bombs'
    slot = 1
    texture = 'powerupBomb'

    def equip(self, spaz: Spaz) -> None:
        # Because "unequip()" will run each time we equip
        # this powerup, we won't be able to stack bombs, so
        # we don't have to worry about making checks about it.
        spaz.add_bomb_count(2)

    def unequip(self, spaz: Spaz) -> None:
        spaz.add_bomb_count(-2)


TripleBombsPowerup.register()


class BombPowerup(SpazPowerup):
    """A powerup that grants the provided bomb type."""

    name = 'empty bomb powerup'
    slot = 2

    bomb_type: str = 'normal'
    """Bomb type to assign when this powerup is picked up."""

    def equip(self, spaz: Spaz) -> None:
        spaz.set_bomb_type(self.bomb_type)

    def unequip(self, spaz: Spaz) -> None:
        spaz.reset_bomb_type()


class StickyBombsPowerup(BombPowerup):
    name = 'sticky_bombs'
    bomb_type = 'sticky'
    texture = 'powerupStickyBombs'


StickyBombsPowerup.register()


class IceBombsPowerup(BombPowerup):
    name = 'ice_bombs'
    bomb_type = 'ice'
    texture = 'powerupIceBombs'


IceBombsPowerup.register()


class ImpactBombsPowerup(BombPowerup):
    name = 'impact_bombs'
    bomb_type = 'impact'
    texture = 'powerupImpactBombs'


ImpactBombsPowerup.register()


class LandMinesPowerup(SpazPowerup):
    name = 'land_mines'
    texture = 'empty'

    def equip(self, spaz: Spaz) -> None:
        spaz.set_land_mine_count(min(spaz.land_mine_count + 3, 3))


LandMinesPowerup.register()


class PunchPowerup(SpazPowerup):
    """A powerup which grants boxing gloves to a spaz."""

    name = 'punch'
    slot = 3
    texture = 'powerupPunch'

    # This powerup has some built-in functions; don't have to do much about it.
    def equip(self, spaz: Spaz) -> None:
        spaz.equip_boxing_gloves()

    def warning(self, spaz: Spaz) -> None:
        spaz.node.boxing_gloves_flashing = True

    def unequip(self, spaz: Spaz) -> None:
        # Custom Claypocalypse function that removes gloves without
        # forcefully playing the "powerdown" sound and
        # sets "spaz.node.boxing_gloves_flashing" to False.
        spaz._unequip_gloves()


PunchPowerup.register()


class ShieldPowerup(SpazPowerup):
    name = 'shield'
    texture = 'empty'

    def equip(self, spaz: Spaz) -> None:
        spaz.equip_shields()


ShieldPowerup.register()


class HealthPowerup(SpazPowerup):
    name = 'health'
    texture = 'powerupHealth'

    def equip(self, spaz: Spaz) -> None:
        spaz.heal()


HealthPowerup.register()


class CursePowerup(SpazPowerup):
    name = 'curse'
    texture = 'empty'

    def equip(self, spaz: Spaz) -> None:
        spaz.curse()


CursePowerup.register()
