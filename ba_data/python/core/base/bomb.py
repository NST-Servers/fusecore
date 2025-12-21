"""Customizable bombs from core."""

from __future__ import annotations
from typing import override, Any, Sequence, Callable, Type

import random
import logging

import bascenev1 as bs
from bascenev1lib.gameutils import SharedObjects
from bascenev1lib.actor.bomb import (
    SplatMessage,
    ExplodeMessage,
    ImpactMessage,
    ArmMessage,
    WarnMessage,
)

from ..base.blast import (
    Blast,
    IceBlast,
    ImpactBlast,
    StickyBlast,
    LandMineBlast,
    TNTBlast,
)
from ..base.factory import (
    Factory,
    FactoryActor,
    FactoryTexture,
    FactoryMesh,
    FactorySound,
)

# pylint: disable=attribute-defined-outside-init
# caused by 'attributes()' function

BOMB_SET: set[Type[Bomb]] = set()
FUSE_WARNING: set[str] = set()


class BombFactory(Factory):
    """Library class containing shared bomb
    data to prevent gameplay hiccups."""

    IDENTIFIER = "_bomb_factory"

    def __init__(self) -> None:
        super().__init__()

        shared = SharedObjects.get()

        # Set up our material so new bombs don't collide with objects
        # that they are initially overlapping.
        self.bomb_material = bs.Material()
        self.normal_sound_material = bs.Material()
        self.sticky_material = bs.Material()

        self.bomb_material.add_actions(
            conditions=(
                (
                    ("we_are_younger_than", 100),
                    "or",
                    ("they_are_younger_than", 100),
                ),
                "and",
                ("they_have_material", shared.object_material),
            ),
            actions=("modify_node_collision", "collide", False),
        )

        # We want pickup materials to always hit us even if we're currently
        # not colliding with their node. (generally due to the above rule)
        self.bomb_material.add_actions(
            conditions=("they_have_material", shared.pickup_material),
            actions=("modify_part_collision", "use_node_collide", False),
        )

        self.bomb_material.add_actions(
            actions=("modify_part_collision", "friction", 0.3)
        )

        self.land_mine_no_explode_material = bs.Material()
        self.land_mine_blast_material = bs.Material()
        self.land_mine_blast_material.add_actions(
            conditions=(
                ("we_are_older_than", 200),
                "and",
                ("they_are_older_than", 200),
                "and",
                ("eval_colliding",),
                "and",
                (
                    (
                        "they_dont_have_material",
                        self.land_mine_no_explode_material,
                    ),
                    "and",
                    (
                        ("they_have_material", shared.object_material),
                        "or",
                        ("they_have_material", shared.player_material),
                    ),
                ),
            ),
            actions=("message", "our_node", "at_connect", ImpactMessage()),
        )

        self.impact_blast_material = bs.Material()
        self.impact_blast_material.add_actions(
            conditions=(
                ("we_are_older_than", 200),
                "and",
                ("they_are_older_than", 200),
                "and",
                ("eval_colliding",),
                "and",
                (
                    ("they_have_material", shared.footing_material),
                    "or",
                    ("they_have_material", shared.object_material),
                ),
            ),
            actions=("message", "our_node", "at_connect", ImpactMessage()),
        )

        self.dink_sounds = (
            bs.getsound("bombDrop01"),
            bs.getsound("bombDrop02"),
        )
        self.roll_sound = bs.getsound("bombRoll01")

        # Collision sounds.
        self.normal_sound_material.add_actions(
            conditions=("they_have_material", shared.footing_material),
            actions=(
                ("impact_sound", self.dink_sounds, 2, 0.8),
                ("roll_sound", self.roll_sound, 3, 6),
            ),
        )

        self.sticky_material.add_actions(
            actions=(
                ("modify_part_collision", "stiffness", 0.1),
                ("modify_part_collision", "damping", 1.0),
            )
        )

        self.sticky_material.add_actions(
            conditions=(
                ("they_have_material", shared.player_material),
                "or",
                ("they_have_material", shared.footing_material),
            ),
            actions=("message", "our_node", "at_connect", SplatMessage()),
        )


class Bomb(FactoryActor):
    """An explosive bomb actor that blows up after 3 seconds,
    creating a blast that damages anyone nearby.

    Category: **Gameplay Classes**
    """

    my_factory = BombFactory
    """Factory used by this FactoryClass instance."""
    group_set = BOMB_SET
    """Set to register this FactoryClass under."""

    bomb_type = "normal"
    """Name of this bomb. Must be unique."""

    @staticmethod
    def resources() -> dict:
        """
        Register resources used by this bomb actor.
        Models, sounds and textures included here are
        preloaded on game launch to prevent hiccups while
        you play!

        Due to how mesh, sound, texture calls are handled,
        you'll need to use FactoryMesh, FactorySound and
        FactoryTexture respectively for the factory to be
        able to call assets in runtime properly.
        """
        return {
            "bomb_mesh": FactoryMesh("bomb"),
            "bomb_tex": FactoryTexture("bombColor"),
            "fuse_sound": FactorySound("fuse01"),
        }

    def __init__(
        self,
        position: Sequence[float] = (0, 0, 0),
        velocity: Sequence[float] = (0, 0, 0),
        source_player: bs.Player | None = None,
        owner: bs.Node | None = None,
    ) -> None:
        super().__init__()
        self.factory: BombFactory
        # Prepping stuff
        self.shared = SharedObjects.get()
        self.owner = owner
        self._source_player = source_player

        self.initial_position = position
        self.initial_velocity = velocity

        self._exploded = False
        self._explode_callbacks: list[Callable[[Bomb, Blast], Any]] = []
        # Proceed with our bomba
        self.attributes()
        self.create_bomb()
        self.do_fuse()

    def attributes(self) -> None:
        """Define base attributes."""
        self.mesh: bs.Mesh = self.factory.fetch("bomb_mesh")
        self.tex: bs.Texture = self.factory.fetch("bomb_tex")
        self.light_mesh: bs.Mesh | bool = False

        self.body: str | None = None
        self.scale: float = 1.0
        self.mesh_scale: float = 1.0
        self.rtype: str = "sharper"
        self.rscale: float = 1.8
        self.shadow_size: float = 0.3

        self.materials: tuple[bs.Material, ...] = (
            self.factory.fetch("bomb_material"),
            self.factory.fetch("normal_sound_material"),
            self.shared.object_material,
        )
        self.sticky: bool = False

        # A bit hacky: "1" automatically handles visible fuses depending
        # on the node type we're handling - changing it to "True" and trying
        # to run a node with a "prop" type will warn the user that
        # the engine doesn't really work like that.
        self.visible_fuse: bool | int = 1
        self.fuse_sound: bs.Sound | None = self.factory.fetch("fuse_sound")
        self.fuse_time: float | None = 3.0
        self.blast_class: Type[Blast] = Blast

    def create_bomb(self) -> None:
        """Create our bomb and do some bomb logic."""
        # Create the bomb node itself
        attrs = {
            "position": self.initial_position,
            "velocity": self.initial_velocity,
            "mesh": self.mesh,
            "mesh_scale": self.mesh_scale,
            "body_scale": self.scale,
            "shadow_size": self.shadow_size,
            "color_texture": self.tex,
            "sticky": self.sticky,
            "owner": self.owner,
            "reflection": self.rtype,
            "reflection_scale": [self.rscale],
            "materials": self.materials,
        }
        if self.light_mesh:
            attrs["light_mesh"] = (
                self.mesh if self.light_mesh is True else self.light_mesh
            )
        if self.body:
            attrs["body"] = self.body

        self.node = bs.newnode(
            "bomb" if not self.body else "prop",
            delegate=self,
            attrs=attrs,
        )

        # Do a neat pop-in animation
        bs.animate(
            self.node,
            "mesh_scale",
            {0: 0, 0.2: 1.3 * self.scale, 0.26: self.scale},
        )
        # If assigned, attach a fuse sound to the bomb node
        if self.fuse_sound:
            sound = bs.newnode(
                "sound",
                owner=self.node,
                attrs={"sound": self.fuse_sound, "volume": 0.25},
            )
            self.node.connectattr("position", sound, "position")

    def do_fuse(self) -> None:
        """Create a fuse and an explosion timer."""
        if not self.node:
            return

        # Light the fuse! (if assigned)
        if self.body and self.visible_fuse not in [1, False]:
            # prop-type bombs can't have fuses
            if not self.bomb_type in FUSE_WARNING:
                logging.warning(
                    "WARNING: Bombs that a body attribute"
                    ' assigned cannot have a fuse. ("%s")',
                    self.bomb_type,
                    stack_info=True,
                )
                FUSE_WARNING.add(self.bomb_type)
        elif not self.body:
            # adjust accordingly
            self.node.fuse_length = 1.0 if self.visible_fuse else 0.0
            if self.fuse_time and self.fuse_time > 0:
                bs.animate(
                    self.node, "fuse_length", {0.0: 1.0, self.fuse_time: 0.0}
                )

        if self.fuse_time and self.fuse_time >= 0:
            bs.timer(
                self.fuse_time,
                bs.WeakCallPartial(self.handlemessage, ExplodeMessage()),
            )

    def explode(self) -> None:
        """Tell the bomb to explode if it hasn't done so."""
        if self._exploded:
            return
        self._exploded = True
        if self.node and self.blast_class:
            blast = self.blast_class(
                position=self.node.position,
                velocity=self.node.velocity,
                source_player=bs.existing(self._source_player),
            ).autoretain()
            for callback in self._explode_callbacks:
                callback(self, blast)

        # We blew up so we need to go away.
        self.handlemessage(bs.DieMessage())

    def add_material(self, material: bs.Material) -> None:
        """Add a new material to our active bomb node."""
        if not self.node:
            return

        materials = self.node.materials
        if material not in materials:
            assert isinstance(materials, tuple)
            self.node.materials = materials + (material,)

    def handle_hit(self, msg: bs.HitMessage) -> None:
        """We got hit by something!"""
        # We want to explode to anything that is not a punch.
        ispunched = msg.srcnode and msg.srcnode.getnodetype() == "spaz"
        noexplode = msg.hit_subtype == "noexplode"
        if not self._exploded and not (ispunched or noexplode):
            # Also lets change the owner of the bomb to whoever is setting
            # us off. (this way points for big chain reactions go to the
            # person causing them).
            source_player = msg.get_source_player(bs.Player)
            if source_player is not None:
                self._source_player = source_player
            # Do a kaboom!
            bs.timer(
                0.1 + random.random() * 0.1,
                bs.WeakCallPartial(self.handlemessage, ExplodeMessage()),
            )

    def handle_impulse(self, msg: bs.HitMessage) -> None:
        """Move us around with using HitMessage info."""
        assert self.node
        self.node.handlemessage(
            "impulse",
            msg.pos[0],
            msg.pos[1],
            msg.pos[2],
            msg.velocity[0],
            msg.velocity[1],
            msg.velocity[2],
            msg.magnitude,
            msg.velocity_magnitude,
            msg.radius,
            0,
            msg.velocity[0],
            msg.velocity[1],
            msg.velocity[2],
        )

    def die(self) -> None:
        """Kills this bomb."""
        if self.node:
            self.node.delete()

    @override
    def handlemessage(self, msg: Any) -> None:
        """Handle messages regarding our node."""
        if isinstance(msg, ExplodeMessage):
            self.explode()
        elif isinstance(msg, bs.PickedUpMessage):
            # Change our source to whoever just picked us up *only* if it
            # is None. This way we can get points for killing bots with their
            # own bombs. Hmm would there be a downside to this?
            if self._source_player is None:
                self._source_player = msg.node.source_player
        elif isinstance(msg, bs.HitMessage):
            # We handle hits and impulse separately now!
            self.handle_hit(msg)
            self.handle_impulse(msg)
        elif isinstance(msg, (bs.DieMessage, bs.OutOfBoundsMessage)):
            self.die()
        else:
            super().handlemessage(msg)


Bomb.register()


class StickyBomb(Bomb):
    """A green, gooey bomb that sticks to entities."""

    bomb_type = "sticky"

    @staticmethod
    def resources() -> dict:
        """Resources used by this bomb instance."""
        return {
            "sticky_bomb_mesh": FactoryMesh("bombSticky"),
            "sticky_tex": FactoryTexture("bombStickyColor"),
            "sticky_impact_sound": FactorySound("stickyImpact"),
        }

    def attributes(self) -> None:
        """Define base attributes."""
        # Load default attributes
        super().attributes()
        # Set our own
        self.mesh: bs.Mesh = self.factory.fetch("sticky_bomb_mesh")
        self.tex: bs.Texture = self.factory.fetch("sticky_tex")

        self.sticky = True

        self.materials: tuple = (
            self.factory.fetch("bomb_material"),
            self.factory.fetch("sticky_material"),
            self.shared.object_material,
        )
        self.blast_class = StickyBlast

        # Some more attributes
        self._last_sticky_sound_time: int = -9999

    def handle_dropped(self) -> None:
        """We've been dropped!"""

        def sticky(node: bs.Node) -> None:
            if node:
                node.stick_to_owner = True

        # Become sticky to the owner after a brief moment
        bs.timer(0.25, lambda: sticky(self.node))

    def handle_splat(self) -> None:
        """Play a splat sound on collision."""
        node = bs.getcollision().opposingnode
        if (
            node is not self.owner
            and bs.time() - self._last_sticky_sound_time > 1.0
        ):
            self._last_sticky_sound_time = bs.time()
            assert self.node
            self.factory.fetch("sticky_impact_sound").play(
                2.0,
                position=self.node.position,
            )

    def handlemessage(self, msg: Any) -> None:
        if isinstance(msg, bs.DroppedMessage):
            self.handle_dropped()
        elif isinstance(msg, SplatMessage):
            self.handle_splat()
        return super().handlemessage(msg)


StickyBomb.register()


class IceBomb(Bomb):
    """An icey bomb that freezes players (and spazzes in general.)"""

    bomb_type = "ice"

    @staticmethod
    def resources() -> dict:
        """Resources used by this bomb instance."""
        return {
            "ice_tex": FactoryTexture("bombColorIce"),
        }

    def attributes(self) -> None:
        """Define base attributes."""
        # Load default attributes
        super().attributes()
        # Set our own
        self.tex = self.factory.fetch("ice_tex")

        self.blast_class = IceBlast


IceBomb.register()


class ImpactBomb(Bomb):
    """A sensitive bomb that explodes on impact."""

    bomb_type = "impact"

    @staticmethod
    def resources() -> dict:
        """Resources used by this bomb instance."""
        return {
            "impact_bomb_mesh": FactoryMesh("impactBomb"),
            "impact_tex": FactoryTexture("impactBombColor"),
            "impact_lit_tex": FactoryTexture("impactBombColorLit"),
            "activate_sound": FactorySound("activateBeep"),
            "warn_sound": FactorySound("warnBeep"),
        }

    def attributes(self) -> None:
        """Define base attributes."""
        # Load default attributes
        super().attributes()
        # Set our own
        self.tex_off: bs.Texture = self.factory.fetch("impact_tex")
        self.tex_on: bs.Texture = self.factory.fetch("impact_lit_tex")
        self.mesh = self.factory.fetch("impact_bomb_mesh")
        self.tex = self.tex_off

        self.body = "sphere"
        self.rtype = "powerup"
        self.rscale = 1.5

        self.materials = self.materials + (self.factory.impact_blast_material,)
        self.blast_class = ImpactBlast

        self.fuse_time = 20.0
        self.visible_fuse = False
        self.fuse_sound = None

        self.impact_timers: bool = True
        self.arm_timer: bs.Timer
        self.warn_timer: bs.Timer
        self.warn_sound: bs.Sound = self.factory.fetch("warn_sound")
        self.activate_sound: bs.Sound = self.factory.fetch("activate_sound")
        self.texture_sequence: bs.Node | None = None

    def create_bomb(self) -> None:
        """Create our bomb and do some bomb logic."""
        super().create_bomb()
        if self.impact_timers:
            self.create_timers()

    def create_timers(self) -> None:
        """Create some extra timers to fancify this bomb."""
        self.arm_timer = bs.Timer(
            0.2, bs.WeakCallPartial(self.handlemessage, ArmMessage())
        )
        if self.fuse_time and self.fuse_time >= 0:
            self.warn_timer = bs.Timer(
                max(0, self.fuse_time - 1.7),
                bs.WeakCallPartial(self.handlemessage, WarnMessage()),
            )

    def handle_arm(self) -> None:
        """Enable ourselves to explode."""
        if not self.node:
            return
        # Create a texture sequence and assign
        intex = (
            self.tex_on,
            self.tex_off,
            self.tex_off,
        )
        self.texture_sequence = bs.newnode(
            "texture_sequence",
            owner=self.node,
            attrs={"rate": 100, "input_textures": intex},
        )
        # Enable our explosive material with slight delay
        bs.timer(
            0.25,
            bs.WeakCallPartial(
                self.add_material,
                self.factory.fetch("land_mine_blast_material"),
            ),
        )
        self.texture_sequence.connectattr(  # type: ignore
            "output_texture", self.node, "color_texture"
        )
        self.activate_sound.play(position=self.node.position)

    def handle_warn(self) -> None:
        """Warn about our imminent explosion."""
        # Speed up our tex. sequence and play a sound
        if self.texture_sequence and self.node:
            self.texture_sequence.rate = 30
            self.warn_sound.play(0.5, position=self.node.position)

    def handle_impact(self) -> None:
        """We collisioned with something!"""
        node = bs.getcollision().opposingnode

        # If we're an impact bomb and we came from this node, don't explode.
        # (otherwise we blow up on our own head when jumping).
        # Alternately if we're hitting another impact-bomb from the same
        # source, don't explode. (can cause accidental explosions if rapidly
        # throwing/etc.)
        node_delegate = node.getdelegate(object)
        if node is self.owner or (
            isinstance(node_delegate, Bomb)
            and (
                node_delegate.bomb_type == "impact"
                or isinstance(node_delegate, ImpactBomb)
            )
            and node_delegate.owner is self.owner
        ):
            return
        self.handlemessage(ExplodeMessage())

    def handle_hit(self, msg: bs.HitMessage) -> None:
        """We got hit by something!"""
        # As an impact bomb, we explode by any hit towards us.
        if not self._exploded:
            # Also lets change the owner of the bomb to whoever is setting
            # us off. (this way points for big chain reactions go to the
            # person causing them).
            source_player = msg.get_source_player(bs.Player)
            if source_player is not None:
                self._source_player = source_player
            # Do a kaboom!
            bs.timer(
                0.1 + random.random() * 0.1,
                bs.WeakCallPartial(self.handlemessage, ExplodeMessage()),
            )

    def handlemessage(self, msg: Any) -> None:
        """Handle messages regarding our node."""
        if isinstance(msg, ArmMessage):
            self.handle_arm()
        elif isinstance(msg, WarnMessage):
            self.handle_warn()
        elif isinstance(msg, ImpactMessage):
            self.handle_impact()
        return super().handlemessage(msg)


ImpactBomb.register()


class LandMine(ImpactBomb):
    """A pad-type explosive that blows up when touched."""

    bomb_type = "land_mine"

    @staticmethod
    def resources() -> dict:
        """Resources used by this bomb instance."""
        return {
            "land_mine_mesh": FactoryMesh("landMine"),
            "land_mine_tex": FactoryTexture("landMine"),
            "land_mine_lit_tex": FactoryTexture("landMineLit"),
        }

    def attributes(self) -> None:
        """Define base attributes."""
        # Load default attributes
        super().attributes()
        # Set our own
        self.tex_off = self.factory.fetch("land_mine_tex")
        self.tex_on = self.factory.fetch("land_mine_lit_tex")
        self.mesh = self.factory.fetch("land_mine_mesh")
        self.tex = self.tex_off
        self.light_mesh = True

        self.body = "landMine"
        self.rscale = 1.0
        self.shadow_size = 0.44

        self.materials = (
            self.factory.fetch("bomb_material"),
            self.factory.fetch("land_mine_no_explode_material"),
            self.shared.object_material,
        )
        self.blast_class = LandMineBlast

        self.fuse_time = None
        self.impact_timers = False

    def handle_dropped(self) -> None:
        """We've been dropped!"""
        # Arm ourselves
        self.arm_timer = bs.Timer(
            1.25, bs.WeakCallPartial(self.handlemessage, ArmMessage())
        )

    def handle_arm(self) -> None:
        """Enable ourselves to explode."""
        if not self.node:
            return
        # Create a texture sequence and assign
        intex = (self.tex_on, self.tex_off)
        self.texture_sequence = bs.newnode(
            "texture_sequence",
            owner=self.node,
            attrs={"rate": 30, "input_textures": intex},
        )
        bs.timer(0.5, self.texture_sequence.delete)  # type: ignore # intellisense issue

        # Make it explodable now
        bs.timer(
            0.25,
            bs.WeakCallPartial(
                self.add_material,
                self.factory.fetch("land_mine_blast_material"),
            ),
        )
        self.texture_sequence.connectattr(  # type: ignore # intellisense issue
            "output_texture", self.node, "color_texture"
        )
        self.activate_sound.play(position=self.node.position)

    def handle_impact(self) -> None:
        """We collisioned with something!"""
        node = bs.getcollision().opposingnode

        # As a landmine, we explode at anything regardless of what it is.
        if node:
            self.handlemessage(ExplodeMessage())

    def handlemessage(self, msg: Any) -> None:
        """Handle messages regarding our node."""
        if isinstance(msg, bs.DroppedMessage):
            self.handle_dropped()
        return super().handlemessage(msg)


LandMine.register()


class TNT(Bomb):
    """A crate packing a powerful explosion."""

    bomb_type = "tnt"

    @staticmethod
    def resources() -> dict:
        """Resources used by this bomb instance."""
        return {
            "tnt_mesh": FactoryMesh("tnt"),
            "tnt_tex": FactoryTexture("tnt"),
        }

    def attributes(self) -> None:
        """Define base attributes."""
        # Load default attributes
        super().attributes()
        # Set our own
        self.mesh = self.factory.fetch("tnt_mesh")
        self.tex = self.factory.fetch("tnt_tex")
        self.light_mesh = True

        self.body = "crate"
        self.rtype = "soft"
        self.rscale = 0.23
        self.shadow_size = 0.5

        self.materials = (
            self.factory.fetch("bomb_material"),
            self.shared.footing_material,
            self.shared.object_material,
        )
        self.blast_class = TNTBlast

        self.fuse_time = None


TNT.register()
