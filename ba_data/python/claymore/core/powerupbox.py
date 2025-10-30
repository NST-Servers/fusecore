"""Custom powerups that are easier to create and manage."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Type, cast, override, Any, Sequence
from bascenev1lib.gameutils import SharedObjects
import bascenev1 as bs

from bascenev1lib.actor import powerupbox

from claymore.core.factory import (
    Factory,
    FactoryActor,
    FactoryTexture,
    FactoryMesh,
    FactorySound,
)
from claymore.core.powerup import (
    SpazPowerup,
    TripleBombsPowerup,
    StickyBombsPowerup,
    IceBombsPowerup,
    ImpactBombsPowerup,
    LandMinesPowerup,
    PunchPowerup,
    ShieldPowerup,
    HealthPowerup,
    CursePowerup,
)

POWERUPBOX_SET: set[Type[PowerupBox]] = set()


@dataclass
class TouchedMessage: ...


@dataclass
class PowerupBoxMessage:
    grants_powerup: Type[SpazPowerup] | None
    source_node: bs.Node | None = None


class PowerupBoxFactory(Factory):
    """Library class containing shared powerup
    data to prevent gameplay hiccups."""

    IDENTIFIER = '_powerup_box_factory'

    def __init__(self) -> None:
        super().__init__()

        self.last_poweruptype: Type[PowerupBox] | None = None

        from bascenev1 import get_default_powerup_distribution

        self.drop_sound = bs.getsound('boxDrop')
        self.powerdown_sound = bs.getsound('powerdown01')

        shared = SharedObjects.get()
        # Material for powerups.
        self.powerup_material = bs.Material()

        # Material for anyone wanting to accept powerups.
        # TODO: We shouldn't do this...
        from bascenev1lib.actor.powerupbox import PowerupBoxFactory

        self.powerup_accept_material = (
            PowerupBoxFactory.get().powerup_accept_material
        )

        # Pass a powerup-touched message to applicable stuff.
        self.powerup_material.add_actions(
            conditions=('they_have_material', self.powerup_accept_material),
            actions=(
                ('modify_part_collision', 'collide', True),
                ('modify_part_collision', 'physical', False),
                ('message', 'our_node', 'at_connect', TouchedMessage()),
            ),
        )

        # We don't wanna be picked up.
        self.powerup_material.add_actions(
            conditions=('they_have_material', shared.pickup_material),
            actions=('modify_part_collision', 'collide', False),
        )

        # NOTE: Currently engine broken
        self.powerup_material.add_actions(
            conditions=('they_have_material', shared.footing_material),
            actions=('impact_sound', self.drop_sound, 0.5, 0.1),
        )

        self._powerupdist: list[str] = []
        for powerup, freq in get_default_powerup_distribution():
            for _i in range(int(freq)):
                self._powerupdist.append(powerup)

    def get_powerup_box_distribution(self) -> dict[Type[PowerupBox], float]:
        """Return the **default** weight of all powerup boxes.

        To get the *active* powerup distribution, consult rulesets.
        """
        distribution: dict[Type[PowerupBox], float] = {}

        for powerupbox in POWERUPBOX_SET:
            distribution[powerupbox] = powerupbox.weight
        return distribution

    def get_random_powerup_box(
        self, exclude: list[PowerupBox] = [], weightless: bool = False
    ) -> Type[PowerupBox]:
        """
        Return a random powerup box type.

        Excludes powerups if their name is in the provided *exclude* list.
        Please note that *exclude* names are **CaSe SeNsItIvE**!

        This uses PowerupBoxes' *weight* value to calculate chance.
        To disable this, set *weightless* to *True*.
        """
        import random

        if weightless:
            # Choose equally if we're weightless
            viable_powerups = [
                p for p in POWERUPBOX_SET if not p in exclude and p.weight > 0
            ]
            return random.choice(viable_powerups)

        # Special rule: if our last powerup was a curse, always
        # follow up with a healthpack.
        if self.last_poweruptype == CursePowerupBox:
            powerup: Type[PowerupBox] = HealthPowerupBox
            self.last_poweruptype = powerup
            return powerup
        # Do random number assignation if we use weight
        # TODO: Would be better if we calculated the pool on each
        # powerupbox register over every time this function runs...
        powerup_pool: list[dict] = []
        latest_float: float = 0.0
        for powerup_i in [
            p for p in POWERUPBOX_SET if not p in exclude and p.weight > 0
        ]:
            powerup_pool.append(
                {
                    'powerup': powerup_i,
                    'min': latest_float,
                    'max': latest_float + powerup_i.weight,
                }
            )
            latest_float += powerup_i.weight
        # Roll a number and pick our powerup!
        roll = random.uniform(0, latest_float)
        for pwpdict in powerup_pool:
            # Check if we're within range of this powerup
            # if true, return this one!
            if pwpdict['max'] > roll >= pwpdict['min']:
                self.last_poweruptype = pwpdict['powerup']
                return pwpdict['powerup']

        # Shouldn't get here.
        raise RuntimeError('Unable to return random powerup.')


class PowerupBox(FactoryActor):
    """A box-type node which gives a specific
    powerup to whoever player picks it up.

    Category: **Gameplay Classes**
    """

    my_factory = PowerupBoxFactory
    """Factory used by this FactoryClass instance."""
    group_set = POWERUPBOX_SET
    """Set to register this FactoryClass under."""

    texture: str = 'cl_powerup_empty'
    """Texture name applied to the box.
    
    Transformed into 'FactoryTexture', then 'bs.Texture' in runtime.
    """

    powerup_to_grant: Type[SpazPowerup] | None = None
    """SpazPowerup class this powerup grants when picked up.

    Can be set to **None** to disable powerup functionality.
    You should only ever do this if the relevant methods are contained
    within the powerup box itself.
    """

    weight: float = 1.0
    """float number marking how likely is this powerup to spawn.
    The larger this number is, the more likely it is for it to appear.

    A value equal or under zero will make it unable to spawn.
    """

    @classmethod
    def _register_texture(cls) -> None:
        """Register our texture as a 'FactoryTexture' instance."""
        cls.my_factory.register_resource(
            f'{cls.texture}', FactoryTexture(cls.texture)
        )

    @classmethod
    def register(cls) -> None:
        cls._register_texture()
        return super().register()

    @staticmethod
    def resources() -> dict:
        """Register resources used by this bomb actor.
        Models, sounds and textures included here are
        preloaded on game launch to prevent hiccups while
        you play!

        Due to how mesh, sound, texture calls are handled,
        you'll need to use FactoryMesh, FactorySound and
        FactoryTexture respectively for the factory to be
        able to call assets in runtime properly.
        """
        return {
            'mesh': FactoryMesh('powerup'),
            'mesh_simple': FactoryMesh('powerupSimple'),
            'powerup_sound': FactorySound('powerup01'),
            'drop_sound': FactorySound('boxDrop'),
        }

    def __init__(
        self,
        position: Sequence[float] = (0, 0, 0),
        velocity: Sequence[float] = (0, 0, 0),
        expire: bool = True,
    ) -> None:
        super().__init__()
        self.factory: PowerupBoxFactory
        # Prepping stuff
        self.shared = SharedObjects.get()
        self._expire = expire

        self.initial_position = position
        self.initial_velocity = velocity

        # Proceed with our powerupa
        self.attributes()
        self.create_box()

    def attributes(self) -> None:
        """Define base variables and attributes."""
        self.mesh: bs.Mesh = self.factory.fetch('mesh')
        self.tex: bs.Texture = self.factory.fetch(f'{self.texture}')
        self.light_mesh: bs.Mesh | bool = self.factory.fetch('mesh_simple')

        self.body: str = 'box'
        self.scale: float = 1.0
        self.mesh_scale: float = 1.0
        self.rtype: str = 'powerup'
        self.rscale: float = 1.0
        self.shadow_size: float = 0.5

        self.materials: tuple[bs.Material, ...] = (
            self.factory.powerup_material,
            self.shared.object_material,
        )
        self.sticky: bool = False

        self.used: bool = False
        # TODO: Make box time auto-adjust to rulesets
        self.time: float = -1 if not self._expire else 8.0

    def create_box(self) -> None:
        """Create our bomb and do some bomb logic."""
        # Create the bomb node itself
        attrs = {
            'position': self.initial_position,
            'velocity': self.initial_velocity,
            'mesh': self.mesh,
            'mesh_scale': self.mesh_scale,
            'body': self.body,
            'body_scale': self.scale,
            'shadow_size': self.shadow_size,
            'color_texture': self.tex,
            'sticky': self.sticky,
            'reflection': self.rtype,
            'reflection_scale': [self.rscale],
            'materials': self.materials,
        }
        if self.light_mesh:
            attrs['light_mesh'] = (
                self.mesh if self.light_mesh is True else self.light_mesh
            )

        # Create the node
        self.node = bs.newnode(
            'prop',
            delegate=self,
            attrs=attrs,
        )

        # Animate in.
        curve = bs.animate(self.node, 'mesh_scale', {0: 0, 0.14: 1.6, 0.2: 1})
        bs.timer(0.2, curve.delete)

        # Do timer flash and death
        if self.time and self.time > 0.0:
            bs.timer(
                max(0, self.time - 2.5),
                bs.WeakCallPartial(self.do_flash),
            )
            bs.timer(
                max(0, self.time - 1.0),
                bs.WeakCallPartial(self.handlemessage, bs.DieMessage()),
            )

    def do_flash(self) -> None:
        """Tell our node to start flashing."""
        if self.node:
            self.node.flashing = True

    def handle_touch(self) -> None:
        """Tell our target node to handle this powerup.
        Called when touched by a node.
        """
        if self.used:
            return

        node = bs.getcollision().opposingnode
        node.handlemessage(
            PowerupBoxMessage(
                grants_powerup=self.powerup_to_grant, source_node=self.node
            )
        )

    def handle_accept(self) -> None:
        """Play a sound and disappear.
        Called when processed by a node (via *handle_touch*) successfully.
        """
        assert self.node
        self.used = True
        # Play the sound and die
        self.factory.fetch('powerup_sound').play(3, position=self.node.position)
        self.handlemessage(bs.DieMessage())

    def handle_die(self, immediate: bool = False) -> None:
        """Animate a fade out, then kill our node."""
        if not self.node:
            return

        if immediate:
            self.node.delete()
        else:
            bs.animate(self.node, 'mesh_scale', {0: 1, 0.1: 0})
            bs.timer(0.1, self.node.delete)

    def handle_hit(self, msg: bs.HitMessage) -> None:
        """Handle a hit to our node."""
        # We die if we get hit by anything other than a punch.
        if msg.hit_type != 'punch':
            self.handlemessage(bs.DieMessage())

    @override
    def handlemessage(self, msg: Any) -> Any:
        assert not self.expired
        if isinstance(msg, TouchedMessage):
            self.handle_touch()
        elif isinstance(msg, bs.PowerupAcceptMessage):
            self.handle_accept()
        elif isinstance(msg, bs.DieMessage):
            self.handle_die(immediate=msg.immediate)
        elif isinstance(msg, bs.OutOfBoundsMessage):
            self.handlemessage(bs.DieMessage(immediate=True))
        elif isinstance(msg, bs.HitMessage):
            self.handle_hit(msg)
        else:
            return super().handlemessage(msg)
        return None


# We don't want to register the base as an actor, but we
# do wanna register the resources it occupies for instancing.
PowerupBox._register_resources()


class TripleBombsPowerupBox(PowerupBox):
    texture = 'powerupBomb'
    powerup_to_grant = TripleBombsPowerup
    weight = 3.0


TripleBombsPowerupBox.register()
# Look how easy it is to register powerup boxes now oml -T


class StickyBombsPowerupBox(PowerupBox):
    texture = 'powerupStickyBombs'
    powerup_to_grant = StickyBombsPowerup
    weight = 3.0


StickyBombsPowerupBox.register()


class IceBombsPowerupBox(PowerupBox):
    texture = 'powerupIceBombs'
    powerup_to_grant = IceBombsPowerup
    weight = 3.0


IceBombsPowerupBox.register()


class ImpactBombsPowerupBox(PowerupBox):
    texture = 'powerupImpactBombs'
    powerup_to_grant = ImpactBombsPowerup
    weight = 3.0


ImpactBombsPowerupBox.register()


class LandMinesPowerupBox(PowerupBox):
    texture = 'powerupLandMines'
    powerup_to_grant = LandMinesPowerup
    weight = 2.0


LandMinesPowerupBox.register()


class PunchPowerupBox(PowerupBox):
    texture = 'powerupPunch'
    powerup_to_grant = PunchPowerup
    weight = 3.0


PunchPowerupBox.register()


class ShieldPowerupBox(PowerupBox):
    texture = 'powerupShield'
    powerup_to_grant = ShieldPowerup
    weight = 2.0


ShieldPowerupBox.register()


class HealthPowerupBox(PowerupBox):
    texture = 'powerupHealth'
    powerup_to_grant = HealthPowerup
    weight = 1.0


HealthPowerupBox.register()


class CursePowerupBox(PowerupBox):
    texture = 'powerupCurse'
    powerup_to_grant = CursePowerup
    weight = 1.0


CursePowerupBox.register()


def _retro_translate_args(
    position: Sequence[float] = (0.0, 1.0, 0.0),
    poweruptype: str = 'triple_bombs',
    expire: bool = True,
):
    del poweruptype
    return {'position': position, 'velocity': (0, 0, 0), 'expire': expire}


# TODO: This is not working for co-op modes and it's making me cry please help
def PowerupWrap(powerup_classtype: Type[powerupbox.PowerupBox]):
    """Wrapper to keep old PowerupBox code working."""

    def wrapper(*args, **kwargs):
        # Try getting our own powerupboxes in there.
        # If we fail, rather than crushing this innocent player's dreams...
        # ...very awkwardly return the default function instead.
        try:
            # Check if we're in an activity that has excluded powerups
            activity = bs.getactivity()
            excluded_powerups = (
                getattr(activity, '_excluded_powerups', []) or []
            )

            # Get the powerup type from kwargs or args
            powerup_type = kwargs.get('poweruptype', None)
            if powerup_type is None and args:
                # If it's in args, it should be the second argument based on the function signature
                if len(args) > 1:
                    powerup_type = args[1]

            # If this powerup type is excluded, use the original function
            if powerup_type is not None and powerup_type in excluded_powerups:
                return powerup_classtype(*args, **kwargs)

            pwpclass: Type[
                PowerupBox
            ] = PowerupBoxFactory.instance().get_random_powerup_box(
                exclude=excluded_powerups
            )
        except (ValueError, AttributeError):
            return powerup_classtype(*args, **kwargs)
        return pwpclass(**_retro_translate_args(*args, **kwargs))

    return wrapper


powerupbox.PowerupBox = PowerupWrap(powerupbox.PowerupBox)
