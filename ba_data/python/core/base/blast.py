"""Custom explosions that are easier to create and manage."""

from dataclasses import dataclass
from typing import override, Any, Sequence

import random

import bascenev1 as bs
from bascenev1lib.gameutils import SharedObjects

from ..base.factory import (
    Factory,
    FactoryActor,
    FactoryTexture,
    FactoryMesh,
    FactorySound,
)


BLAST_SET = set()


@dataclass
class ExplodeHitMessage:
    """Tell an object it was hit by an explosion."""


class BlastFactory(Factory):
    """Library containing shared blast data
    to prevent gameplay hiccups."""

    IDENTIFIER = '_blast_factory'

    def __init__(self) -> None:
        super().__init__()

        shared = SharedObjects.get()

        self.explode_sounds = (
            bs.getsound('explosion01'),
            bs.getsound('explosion02'),
            bs.getsound('explosion03'),
            bs.getsound('explosion04'),
            bs.getsound('explosion05'),
        )

        self.blast_material = bs.Material()
        self.blast_material.add_actions(
            conditions=('they_have_material', shared.object_material),
            actions=(
                ('modify_part_collision', 'collide', True),
                ('modify_part_collision', 'physical', False),
                ('message', 'our_node', 'at_connect', ExplodeHitMessage()),
            ),
        )

    def random_explode_sound(self) -> bs.Sound:
        """Return a random explosion bs.Sound from the factory."""
        return self.explode_sounds[random.randrange(len(self.explode_sounds))]


class Blast(FactoryActor):
    """An explosive blast that damages and knocks entities away."""

    my_factory = BlastFactory
    """Factory used by this FactoryClass instance."""
    group_set = BLAST_SET
    """Set to register this FactoryClass under."""

    blast_type = 'normal'
    hit_type = 'explosion'
    hit_subtype = 'normal'

    @staticmethod
    def resources() -> dict:
        """
        Resources used by this bomb instance.
        Models, sounds and textures included here are
        preloaded on game launch to prevent hiccups while
        you play!
        """
        return {
            'bomb_mesh': FactoryMesh('bomb'),
            'bomb_tex': FactoryTexture('bombColor'),
            'debris_fall_sound': FactorySound('debrisFall'),
        }

    def __init__(
        self,
        position: Sequence[float] = (0, 0, 0),
        velocity: Sequence[float] = (0, 0, 0),
        source_player: bs.Player | None = None,
    ) -> None:
        super().__init__()
        self.factory: BlastFactory  # Intellisense
        # Prepping stuff
        self.shared = SharedObjects.get()
        self._source_player = source_player

        self.position = position
        self.velocity = velocity

        self.attributes()
        # Proceed with our blast
        self.create_node()
        self.create_explosion()
        self.create_light()
        self.do_sounds()
        self.do_emit()
        # and a silly screenshake
        bs.camerashake(intensity=self.shake_strength)

    def attributes(self) -> None:
        """Define basic blast attributes."""
        # explosion attrs.
        self.magnitude: int = 2000
        self.materials: tuple[bs.Material, ...] = (
            self.factory.fetch('blast_material'),
            self.shared.attack_material,
        )
        # blast attrs.
        self.blast_radius: float = 2.0
        self.blast_color: tuple[float, float, float] | None = None
        # light attrs.
        self.light_color: tuple[float, float, float] = (1, 0.3, 0.1)
        self.light_radius: float = self.blast_radius
        self.light_intensity: float = 1.6
        # scorch attrs.
        self.scorch_color: tuple[float, float, float] | None = None
        self.scorch_radius: float = self.blast_radius
        self.scorch_duration: float = 13.0
        # light random scale mult.
        self.scale_mult: float = random.uniform(0.6, 0.9)
        # additional settings
        self.shake_strength: float = 1.0
        self.spark_chance: float = 10.0
        self.is_big: bool = False

    def create_node(self) -> None:
        """Create the node that handles dealing blows."""
        # Set our position a bit lower so we throw more things upward.
        self.node = bs.newnode(
            'region',
            delegate=self,
            attrs={
                'position': (
                    self.position[0],
                    self.position[1] - 0.1,
                    self.position[2],
                ),
                'scale': tuple([self.blast_radius for _ in range(3)]),
                'type': 'sphere',
                'materials': self.materials,
            },
        )
        bs.timer(0.05, self.node.delete)

    def create_explosion(self) -> None:
        """Create the explosion particle node."""
        # Throw in an explosion and flash.
        evel = (self.velocity[0], max(-1.0, self.velocity[1]), self.velocity[2])
        self.explosion = bs.newnode(
            'explosion',
            attrs={
                'position': self.position,
                'velocity': evel,
                'radius': self.blast_radius,
                'big': self.is_big,
            },
        )
        if self.blast_color:
            self.explosion.color = self.blast_color
        bs.timer(1.0, self.explosion.delete)

    def create_light(self) -> None:
        """Create a shining light to enhance our explosion."""
        self.light = bs.newnode(
            'light',
            attrs={
                'position': self.position,
                'volume_intensity_scale': 10.0,
                'color': self.light_color,
            },
        )
        iscale = self.light_intensity
        lradius = self.light_radius
        scl = self.scale_mult
        bs.animate(
            self.light,
            'intensity',
            {
                0: 2.0 * iscale,
                scl * 0.02: 0.1 * iscale,
                scl * 0.025: 0.2 * iscale,
                scl * 0.05: 17.0 * iscale,
                scl * 0.06: 5.0 * iscale,
                scl * 0.08: 4.0 * iscale,
                scl * 0.2: 0.6 * iscale,
                scl * 2.0: 0.00 * iscale,
                scl * 3.0: 0.0,
            },
        )
        bs.animate(
            self.light,
            'radius',
            {
                0: lradius * 0.2,
                scl * 0.05: lradius * 0.55,
                scl * 0.1: lradius * 0.3,
                scl * 0.3: lradius * 0.15,
                scl * 1.0: lradius * 0.05,
            },
        )
        bs.timer(scl * 3.0, self.light.delete)

    def create_scorch(self) -> None:
        """Create a scorch mark that fades over time."""
        # pylint: disable=attribute-defined-outside-init
        self.scorch = bs.newnode(
            'scorch',
            attrs={
                'position': self.position,
                'size': self.scorch_radius * 0.5,
                'big': self.is_big,
            },
        )
        if self.scorch_color:
            self.scorch.color = self.scorch_color

        bs.animate(
            self.scorch,
            'presence',
            {
                self.scorch_duration * 0.23076923076923078: 1,  # 3.0 from 13.0
                self.scorch_duration: 0,
            },
        )
        bs.timer(self.scorch_duration, self.scorch.delete)

    def do_sounds(self) -> None:
        """Play some sounds."""
        self.factory.random_explode_sound().play(position=self.position)
        self.factory.fetch('debris_fall_sound').play(position=self.position)

    def do_emit(self) -> None:
        """Play some particle related functions."""
        self.do_effects()
        self.do_particles()

        if random.random() < (self.spark_chance / 100):
            self.do_sparks()

    def do_effects(self) -> None:
        """Do our tendrils & distortion effects."""
        bs.emitfx(
            position=self.position,
            velocity=self.velocity,
            count=int(4.0 + random.random() * 4),
            emit_type='tendrils',
            tendril_type='smoke',
        )
        bs.emitfx(
            position=self.position,
            emit_type='distortion',
            spread=2.0,
        )

    def do_particles(self) -> None:
        """Show off some particles."""

        def emit() -> None:
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=30,
                scale=0.7,
                chunk_type='spark',
                emit_type='stickers',
            )
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=int(18.0 + random.random() * 20),
                scale=0.8,
                spread=1.5,
                chunk_type='spark',
            )

        # It looks better if we delay a bit.
        bs.timer(0.05, emit)

    def do_sparks(self) -> None:
        """Show off rare spicy particles."""

        def emit_extra_sparks() -> None:
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=int(10.0 + random.random() * 20),
                scale=0.8,
                spread=1.5,
                chunk_type='spark',
            )

        bs.timer(0.07, emit_extra_sparks)

    def die(self) -> None:
        """Kills this blast."""
        if self.node:
            self.node.delete()

    def handle_explode_hit(self) -> None:
        """The explosion hit something, push it!"""
        node = bs.getcollision().opposingnode
        node.handlemessage(
            bs.HitMessage(
                pos=self.node.position,
                velocity=(0, 0, 0),
                magnitude=self.magnitude,
                hit_type=self.hit_type,
                hit_subtype=self.hit_subtype,
                radius=self.blast_radius,
                source_player=bs.existing(self._source_player),
            )
        )

    @override
    def handlemessage(self, msg: Any) -> Any:
        """Handle messages regarding our node."""
        assert not self.expired
        if isinstance(msg, bs.DieMessage):
            self.die()
        elif isinstance(msg, ExplodeHitMessage):
            self.handle_explode_hit()
        else:
            return super().handlemessage(msg)
        return None


Blast.register()


class StickyBlast(Blast):
    """A stickier explosion."""

    def do_particles(self) -> None:
        """Show off some particles."""

        def emit():
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=int(4.0 + random.random() * 8),
                spread=0.7,
                chunk_type='slime',
            )
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=int(4.0 + random.random() * 8),
                scale=0.5,
                spread=0.7,
                chunk_type='slime',
            )
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=15,
                scale=0.6,
                chunk_type='slime',
                emit_type='stickers',
            )
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=20,
                scale=0.7,
                chunk_type='spark',
                emit_type='stickers',
            )
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=int(6.0 + random.random() * 12),
                scale=0.8,
                spread=1.5,
                chunk_type='spark',
            )

        # It looks better if we delay a bit.
        bs.timer(0.05, emit)


StickyBlast.register()


class IceBlast(Blast):
    """An explosion that freezes spazzes in range."""

    @staticmethod
    def resources() -> dict:
        return {
            'freeze_sound': FactorySound('freeze'),
            'hiss_sound': FactorySound('hiss'),
        }

    def attributes(self) -> None:
        """Define basic blast attributes."""
        # Load default attributes
        super().attributes()
        # Set our own
        self.blast_radius = 2.0 * 1.2
        self.magnitude = int(2000.0 * 0.5)

        self.blast_color = (0, 0.05, 0.4)
        self.light_color = (0.6, 0.6, 1.0)
        self.scorch_color = (1, 1, 1.5)

    def do_sounds(self) -> None:
        """Play an extra hiss sound."""
        super().do_sounds()
        self.factory.fetch('hiss_sound').play(position=self.position)

    def do_effects(self) -> None:
        """Do our tendrils & distortion effects."""
        # Give ourselves some icy effects
        bs.emitfx(
            position=self.position,
            velocity=self.velocity,
            count=int(1.0 + random.random() * 4),
            emit_type='tendrils',
            tendril_type='thin_smoke',
        )
        bs.emitfx(
            position=self.position,
            velocity=self.velocity,
            count=int(4.0 + random.random() * 4),
            emit_type='tendrils',
            tendril_type='ice',
        )
        bs.emitfx(
            position=self.position,
            emit_type='distortion',
            spread=2.0,
        )

    def do_particles(self) -> None:
        """Show off some particles."""

        def emit():
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=30,
                spread=2.0,
                scale=0.4,
                chunk_type='ice',
                emit_type='stickers',
            )

        # It looks better if we delay a bit.
        bs.timer(0.05, emit)

    def handle_explode_hit(self) -> None:
        """Aside from pushing things, we freeze them."""
        # Do standard behavior
        super().handle_explode_hit()
        # Then kick 'em with a freeze!
        self.factory.fetch('freeze_sound').play(10, position=self.node.position)
        node = bs.getcollision().opposingnode
        node.handlemessage(bs.FreezeMessage())


IceBlast.register()


class ImpactBlast(Blast):
    """A smaller metallic explosion."""

    def attributes(self) -> None:
        """Define basic blast attributes."""
        # Load default attributes
        super().attributes()
        # Set our own
        self.blast_radius = 2.0 * 0.7

    def do_particles(self) -> None:
        """Show off some particles."""

        def emit():
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=int(4.0 + random.random() * 8),
                scale=0.8,
                chunk_type='metal',
            )
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=int(4.0 + random.random() * 8),
                scale=0.4,
                chunk_type='metal',
            )
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=20,
                scale=0.7,
                chunk_type='spark',
                emit_type='stickers',
            )
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=int(8.0 + random.random() * 15),
                scale=0.8,
                spread=1.5,
                chunk_type='spark',
            )

        # It looks better if we delay a bit.
        bs.timer(0.05, emit)


ImpactBlast.register()


class LandMineBlast(Blast):
    """A small yet strong explosion."""

    def attributes(self) -> None:
        """Define basic blast attributes."""
        # Load default attributes
        super().attributes()
        # Set our own
        self.blast_radius = 2.0 * 0.7
        self.magnitude = int(2000.0 * 2.5)


LandMineBlast.register()


class TNTBlast(Blast):
    """A notoriously large explosion!"""

    @staticmethod
    def resources() -> dict:
        return {
            'wood_debris_fall_sound': FactorySound('woodDebrisFall'),
        }

    def attributes(self) -> None:
        """Define basic blast attributes."""
        # Load default attributes
        super().attributes()
        # Set our own
        self.blast_radius = 2.0 * 1.45
        self.magnitude = int(2000.0 * 2.0)

        self.spark_chance = 100

        self.light_radius = self.blast_radius * 1.4
        self.scorch_radius = self.blast_radius * 1.15
        self.scale_mult = random.uniform(0.6, 0.9) * 3.0

        self.shake_strength = 5.0
        self.is_big = True

    def do_sounds(self) -> None:
        """Play some extra sounds."""
        super().do_sounds()
        # TNT is more epic.
        self.factory.random_explode_sound().play(position=self.position)

        def extra_boom() -> None:
            self.factory.random_explode_sound().play(position=self.position)

        def extra_debris() -> None:
            self.factory.fetch('debris_fall_sound').play(position=self.position)
            self.factory.fetch('wood_debris_fall_sound').play(
                position=self.position
            )

        bs.timer(0.25, extra_boom)
        bs.timer(0.4, extra_debris)

    def do_effects(self) -> None:
        """Do our tendrils & distortion effects."""
        bs.emitfx(
            position=self.position,
            velocity=self.velocity,
            count=int(4.0 + random.random() * 4),
            emit_type='tendrils',
            tendril_type='smoke',
        )
        # Decrease spread to 1.0
        bs.emitfx(
            position=self.position,
            emit_type='distortion',
            spread=1.0,
        )

    def do_particles(self) -> None:
        """Show off some particles."""
        super().do_particles()

        # Add some rock particles on top
        def emit():
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=int(4.0 + random.random() * 8),
                chunk_type='rock',
            )
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=int(4.0 + random.random() * 8),
                scale=0.5,
                chunk_type='rock',
            )

        bs.timer(0.05, emit)

        # And some early splinters as well
        def emit_splinters() -> None:
            bs.emitfx(
                position=self.position,
                velocity=self.velocity,
                count=int(20.0 + random.random() * 25),
                scale=0.8,
                spread=1.0,
                chunk_type='splinter',
            )

        bs.timer(0.01, emit_splinters)


TNTBlast.register()
