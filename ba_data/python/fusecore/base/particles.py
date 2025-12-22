"""System for custom particles and particle management."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, Self, Type, override

import random

import bascenev1 as bs
from bascenev1lib.gameutils import SharedObjects
from bascenev1lib.mainmenu import MainMenuActivity

from fusecore.common import vector3_multfactor

from .factory import (
    Factory,
    FactoryActor,
    FactoryTexture,
    FactoryMesh,
)

MAX_PARTICLES_ATLAS: dict[Type[bs.Activity], int] = {
    MainMenuActivity: 90,
}
"""Particle limits correlated to the provided activity types."""
MAX_PARTICLES_DEFAULT: int = 70
"""Particle limit to return if active activity doesn't match any previously provided ones."""

PARTICLE_SET: set[Type[Particle]] = set()


class ParticleLimitMode(Enum):
    """Ways to handle having too many particles."""

    # TODO: figure out if we can find device specs to switch between these?
    #       pc = overcharge, android = dynamic / dismiss / overwrite
    DISABLED = -1
    """Ignore the particle limit cap and spawn
    as many particles as we please.
    
    ## NOT RECOMMENDED FOR OBVIOUS REASONS.
    Don't even think about it unless you are troubleshooting!
    """
    DISMISS = 0
    """Don't spawn any particles if we're at the particle limit.
    This is our default behaviour.
    """
    OVERWRITE = 1
    """Remove the oldest particles as we spawn newer ones.
    Might look ugly with a low particle limit.
    """
    OVERCHARGE = 2
    """Allow spawn calls to go over the particle limit in
    reduced quantities and at a relaxed pace.
    Might cause performance issues on weaker devices.
    
    Not implemented.
    """
    DYNAMIC = 3
    """The particle limit will change dynamically depending
    on how many nodes and effects are currently active.
    
    Not implemented.
    """


class ParticleFactory(Factory):
    """Factory to quickly access our particles."""

    IDENTIFIER = "_particle_factory"

    def __init__(self) -> None:
        super().__init__()
        self.shared = SharedObjects.get()

        self.material = self.get_particle_material()

    def get_particle_material(
        self,
        friction: float = 1,
        damping: float = 0,
        stiffness: float = 0,
    ) -> bs.Material:
        """Return a particle material with the provided attributes.

        Args:
            friction (float, optional): _description_. Defaults to 1.
            damping (float, optional): _description_. Defaults to 0.
            stiffness (float, optional): _description_. Defaults to 0.
        """
        m = bs.Material()
        m.add_actions(("modify_part_collision", "collide", False))
        m.add_actions(("modify_part_collision", "damping", damping))
        m.add_actions(("modify_part_collision", "stiffness", stiffness))
        m.add_actions(  # map collision
            conditions=("they_have_material", self.shared.footing_material),
            actions=(
                ("modify_part_collision", "collide", True),
                ("modify_part_collision", "friction", friction),
            ),
        )
        return m


@dataclass
class DirectorKillMessage:
    """A message from our 'ParticleDirector' telling a particle to die."""


class ParticleDirector:
    """Class that keeps track of how many particles we spawn.

    Assists on actor management and particle limits, keeping
    our particle collection under the cap while keeping things
    looking pretty.
    """

    IDENTIFIER = "_particle_director"

    def __init__(self) -> None:
        self._particle_pool: OrderedDict[int, Particle] = OrderedDict()
        self._inum: int = 0

        self.limit_mode: ParticleLimitMode = ParticleLimitMode.OVERWRITE
        self.particle_limit: int = self._get_activity_particle_limit()

    def _get_activity_particle_limit(self) -> int:
        """Get the proper particle limit accord to the active activity type."""
        activity = bs.getactivity()

        for a, value in MAX_PARTICLES_ATLAS.items():
            if isinstance(activity, a):
                return value

        return MAX_PARTICLES_DEFAULT

    def perform(
        self,
        particle_type: Type[Particle],
        position: tuple[float, float, float],
        velocity: tuple[float, float, float],
    ) -> bool:
        """Ask the director if we can spawn this particle
        in the provided position w/ velocity.

        Returns whether we did spawn the particle or not.
        """
        if len(self._particle_pool) >= self.particle_limit:
            match self.limit_mode:
                case ParticleLimitMode.DISABLED:
                    pass
                case ParticleLimitMode.DISMISS:
                    return False
                case ParticleLimitMode.OVERWRITE:
                    # order oldest to die and remove
                    _, particle = self._particle_pool.popitem(last=False)
                    particle.handlemessage(DirectorKillMessage())

        self._inum += 1

        self._particle_pool[self._inum] = particle_type(
            position, velocity, self._inum
        )
        return True

    def remove_particle(self, did: int) -> None:
        """Removes a particle from our particle pool using their ID."""
        try:
            self._particle_pool.pop(did)
        except KeyError:
            pass

    @classmethod
    def instance(cls) -> Self:
        """Instantiate this factory to be used.

        This will create a factory object to the active session or
        return an already active object if it has been created already.
        """
        activity: bs.Activity = bs.getactivity()
        factory = activity.customdata.get(cls.IDENTIFIER)
        if factory is None:
            factory = cls()
            activity.customdata[cls.IDENTIFIER] = factory
        assert isinstance(factory, cls)
        return factory


class Particle(FactoryActor):
    """A particle actor to add *custom* sass to in-game actions.

    Unlike engine particles, these ones use actors to
    render themselves, which unfortunately means the game
    runs more checks in them - even if we're not using them
    as standard actors, which could cause some performance
    issues when spawned in bulk; use these sparingly!
    """

    my_factory = ParticleFactory
    group_set = PARTICLE_SET

    @staticmethod
    def resources() -> dict:
        """Register resources used by this particle.
        Models, sounds and textures included here are
        preloaded on game launch to prevent hiccups while
        you play!

        Due to how mesh, sound, texture calls are handled,
        you'll need to use FactoryMesh, FactorySound and
        FactoryTexture respectively for the factory to be
        able to call assets in runtime properly.
        """
        return {
            "mesh": FactoryMesh("bomb"),
            "tex": FactoryTexture("bombColor"),
        }

    def attributes(self) -> None:
        """Define the attributes of this particle actor."""
        self.factory: ParticleFactory  # set via 'my_factory'
        particle_material = self.factory.get_particle_material()
        # alternatively, you can do:
        # 'material = self.factory.material'
        # if you don't care about it having custom
        # friction, dampingand stiffness qualities.

        self.mesh: bs.Mesh = self.factory.fetch("mesh")
        self.light_mesh: bs.Mesh = self.mesh
        self.body: Literal[
            "landMine", "crate", "sphere", "box", "capsule", "puck"
        ] = "landMine"
        self.body_scale: float = 1.0
        self.mesh_scale: float = 1.0
        self.shadow_size: float = 0.3
        self.color_texture: bs.Texture = self.factory.fetch("tex")
        self.reflection: Literal["soft", "char", "powerup"] = "soft"
        self.reflection_scale: list[float] = [1.0]
        self.gravity_scale: float = 1.0
        self.materials: list[bs.Material] = [particle_material]

        self.t_fade_in: float = 0.13
        self.t_fade_out: float = 0.13
        self.lifespan: float = 3.0

    def __init__(
        self,
        position: tuple[float, float, float],
        velocity: tuple[float, float, float] = (0, 0, 0),
        director_id: int | None = None,
    ) -> None:
        super().__init__()
        self.did = director_id

        self._ready_to_die: bool = False
        self._dying: bool = False

        self._animation_node: bs.Node | None = None
        self._death_timer: bs.Timer | None = None

        self.attributes()

        self._initialize(position, velocity)

    def _initialize(
        self,
        position: tuple[float, float, float],
        velocity: tuple[float, float, float],
    ) -> None:
        """Create our node."""
        self.node: bs.Node | None = bs.newnode(
            "prop",
            delegate=self,
            attrs={
                "position": position,
                "velocity": velocity,
                "mesh": self.mesh,
                "light_mesh": self.light_mesh,
                "body": self.body,
                "body_scale": self.body_scale,
                "mesh_scale": self.mesh_scale,
                "shadow_size": self.shadow_size,
                "color_texture": self.color_texture,
                "reflection": self.reflection,
                "reflection_scale": self.reflection_scale,
                "gravity_scale": self.gravity_scale,
                "materials": self.materials,
            },
        )

        self.animate()

    def animate(self) -> None:
        """Perform our life cycle.

        This includes fade in & fade out animations, alongside
        calling for our deletion once we're done doing so.
        """
        t_in = self.t_fade_in
        t_ls = self.t_fade_in + self.lifespan
        t_total = self.t_fade_in + self.lifespan + self.t_fade_out

        self._animation_node = bs.animate(
            self.node,
            "mesh_scale",
            {
                0: 0,
                t_in: self.mesh_scale,
                t_ls: self.mesh_scale,
                t_total: 0,
            },
        )
        self._death_timer = bs.Timer(t_total, self._die_gracefully)

    def _die_gracefully(self) -> None:
        if self._dying or not self.node:
            return

        self._ready_to_die = True
        self.die()

    def die(self) -> None:
        """Remove ourselves.

        This function can be called directly by 'ParticleDirector' when
        clearing up particle excess, on which we'll animate a fade-out.
        """
        if self._dying or not self.node:
            return
        self._dying = True

        if self.did is not None:
            ParticleDirector.instance().remove_particle(self.did)

        if not self._ready_to_die:
            # if we got this function called earlier than intended, we're
            # very likely getting cleaned away!
            # make sure to pack up all our data and make a swift getaway
            self._death_timer = None
            if self.node:
                self._animation_node = bs.animate(
                    self.node,
                    "mesh_scale",
                    {
                        0: self.node.mesh_scale,
                        self.t_fade_out: 0,
                    },
                )
                bs.timer(self.t_fade_out, self.node.delete)
            return

        self.node.delete()

    def _handle_oob(self) -> None:
        self._ready_to_die = True
        self.die()

    def _handle_director_kill(self) -> None:
        self.did = None
        self.die()

    @override
    def handlemessage(self, msg: Any) -> Any:
        if isinstance(msg, bs.DieMessage):
            self.die()
        elif isinstance(msg, DirectorKillMessage):
            self._handle_director_kill()
        elif isinstance(msg, bs.OutOfBoundsMessage):
            self._handle_oob()

    @classmethod
    def summon(
        cls,
        position: tuple[float, float, float],
        velocity: tuple[float, float, float] = (0, 0, 0),
    ) -> None:
        """Spawn a preset of this particle in the current activity."""
        # If you want multiple summon presets of a single
        # particle, you can append more '@classmethod' functions
        # like this one as long as they're uniquely named.

        # the director is in charge of managing particles, we
        # spawn them via it to mantain ourselves under the particle limit
        director: ParticleDirector = ParticleDirector.instance()

        position_spread: float = 2.0
        velocity_spread: float = 1.25

        for _ in range(7):
            # add some randomness to our position and
            # velocity to get some visual variety going
            # TODO: implement 'vector3_spread' from 'core/common.py'
            #       over whatever this sludge of code is

            p = (
                position[0] + (position_spread * random.uniform(-1, 1)),
                position[1] + (position_spread * random.uniform(-1, 1)),
                position[2] + (position_spread * random.uniform(-1, 1)),
            )
            v = vector3_multfactor(
                velocity,  # random velocity multiplier
                factor_min=1.0 / velocity_spread,
                factor_max=1.0 * velocity_spread,
            )
            director.perform(cls, p, v)


Particle.register()
