"""Defines our custom Spaz class."""

from __future__ import annotations
import random
from typing import (
    Optional,
    Type,
    cast,
    override,
    Callable,
    Any,
    TYPE_CHECKING,
)

import logging

import bascenev1 as bs

from bascenev1lib.actor import spaz
from bascenev1lib.actor.spaz import BombDiedMessage
from bascenev1lib.actor.bomb import Bomb as VanillaBomb
from bascenev1lib.actor.spazfactory import SpazFactory as VanillaSpazFactory

from ..base.spazfactory import (
    SpazPowerupSlot,
    SpazComponent,
    SPAZ_COMPONENTS,
)
from ..base.bomb import Bomb, LandMine, BOMB_SET
from ..base.powerupbox import PowerupBoxMessage, POWERUPBOX_SET
from ..base.shared import PowerupSlotType

if TYPE_CHECKING:
    from ..base.powerup import SpazPowerup

# this a chunky boy, pylint, and it's
# not like I can do something about it.
# pylint: disable=too-many-lines


class Spaz(spaz.Spaz):
    """Wrapper for our actor Spaz class."""

    default_bomb_class: Type[Bomb] = Bomb

    @override
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hitpoints = 1000

        self._has_set_components: bool = False
        self.components: dict[Type[SpazComponent], SpazComponent] = {}
        # NOTE: ^ still thinking about this...
        self._apply_components()

        self.active_bomb_class: Type[Bomb] = self.default_bomb_class

        self._powerup_wearoff_time_ms: int = 2000
        """For how long the powerup wearoff alert
        is displayed for (in milliseconds.)
        """

        # Slots to hold powerups in
        self._powerup_slots: dict[PowerupSlotType, SpazPowerupSlot] = {
            PowerupSlotType.BUFF: SpazPowerupSlot(self),
            PowerupSlotType.BOMB: SpazPowerupSlot(self),
            PowerupSlotType.GLOVES: SpazPowerupSlot(self),
            # ... (Append more 'PowerupSlotType' entries here!)
        }

        self._cb_wrapped_methods: set[str] = set()
        self._cb_wrap_calls: dict[str, list[Callable]] = {}
        self._cb_raw_wrap_calls: dict[str, list[Callable]] = {}
        self._cb_overwrite_calls: dict[str, Callable | None] = {}

        self.spaz_factory = VanillaSpazFactory.get()

        # We callback wrap these on creation as the engine
        # clones these, so they won't be able to be updated later.

        # FIXME: This causes issues.
        # Instead, we should make a class entry to allow people to
        # wrap their own functions organically without having to rely
        # on this monolith of a function.
        # self._callback_wrap("on_punch_press")
        # self._callback_wrap("on_bomb_press")
        # self._callback_wrap("on_jump_press")
        # self._callback_wrap("on_pickup_press")

        # for name in dir(self):
        #    if name.startswith('__'):
        #        continue
        #    v = getattr(self, name, None)
        #    if callable(v) or isinstance(v, (staticmethod, classmethod)):
        #        self._callback_wrap(name)

        self.default_bomb_type: str
        self._str_bomb_type: str = (
            self.default_bomb_type or self.bomb_type or "normal"
        )
        self._compat_bomb_update(check_default=True)

    def _apply_components(self) -> None:
        """Give this spaz all available components."""
        if not self.node or self._has_set_components:
            return

        for component in SPAZ_COMPONENTS:
            self.components[component] = component(self)

        self._has_set_components = True

    def get_component(self, component: Type[SpazComponent]) -> Any:
        """Return the active component object, provided by the type."""
        return self.components[component]

    def assign_bomb_class(self, bomb: Type[Bomb]) -> None:
        """Set a bomb type for this spaz to use."""
        self.active_bomb_class = bomb

    def reset_bomb_class(self) -> None:
        """Reset our bomb type back to our default type."""
        self.active_bomb_class = self.default_bomb_class

    def drop_bomb_class(self) -> Bomb | None:
        """Tell the spaz to drop one of his bombs, and returns
        the resulting bomb object.

        If the spaz has no bombs or is otherwise unable to
        drop a bomb, returns None.
        """
        # TODO: Migrate the landmine counter into
        #       a proper class for flexible usage
        if (self.land_mine_count <= 0 and self.bomb_count <= 0) or self.frozen:
            return None
        assert self.node
        pos = self.node.position_forward
        vel = self.node.velocity

        bomb_type: Type[Bomb] = self.active_bomb_class
        is_external = False
        # TODO: Migrate the landmine counter into
        #       a proper class for flexible usage
        if self.land_mine_count > 0:
            is_external = True
            self.set_land_mine_count(self.land_mine_count - 1)
            bomb_type = LandMine

        bomb = bomb_type(
            position=(pos[0], pos[1] - 0.0, pos[2]),
            velocity=(vel[0], vel[1], vel[2]),
            source_player=self.source_player,
            owner=self.node,
        ).autoretain()

        assert bomb.node
        if not is_external:
            self.bomb_count -= 1
            bomb.node.add_death_action(
                bs.WeakCallPartial(self.handlemessage, BombDiedMessage())
            )
        self._pick_up(bomb.node)

        for clb in self._dropped_bomb_callbacks:
            clb(self, bomb)

        return bomb

    def heal(self) -> None:
        """Heal our spaz."""
        if self._cursed:
            self._cursed = False

            # Remove cursed material.
            for attr in ["materials", "roller_materials"]:
                materials = getattr(self.node, attr)
                if self.spaz_factory.curse_material in materials:
                    setattr(
                        self.node,
                        attr,
                        tuple(
                            m
                            for m in materials
                            if m != self.spaz_factory.curse_material
                        ),
                    )
            self.node.curse_death_time = 0
        self.hitpoints = self.hitpoints_max
        self.node.hurt = 0
        self._last_hit_time = None
        self._num_times_hit = 0

    def add_bomb_count(self, count: int) -> None:
        """Increase the bomb limit this Spaz has.

        Use responsibly -- if you're using this for a powerup, make
        sure the *unequip* method has an *add_bomb_count* that
        deducts the given bombs!
        """
        self._max_bomb_count += count
        self.bomb_count += count

    def add_method_callback(self, method_name: str, callback: Callable) -> None:
        """Add a callback to any function.

        Once the base method is executed, all callbacks will be
        executed, containing ourselves as an argument.

        Args:
            method_name (str): Name of the method to receive the callback
            callback (Callable): Function to be linked to the target method
        """
        method = getattr(self, method_name, None)
        if not isinstance(method, Callable):
            raise RuntimeError(f"Method {method_name} does not exist.")
        if not method_name in self._cb_wrapped_methods:
            self._callback_wrap(method_name)

        self._cb_wrap_calls[method_name] = self._cb_wrap_calls.get(
            method_name, []
        ) + [callback]

    def add_method_callback_raw(
        self, method_name: str, callback: Callable
    ) -> None:
        """Add a callback to any function.

        Once the base method is executed, all callbacks will be executed.
        Unlike 'add_method_callback', it will not contain additional arguments.

        Args:
            method_name (str):
                Name of the method to receive the callback.

            callback (Callable):
                Function to be linked to the target method.

        """
        method = getattr(self, method_name, None)
        if not isinstance(method, Callable):
            raise RuntimeError(f"Method {method_name} does not exist.")
        if not method_name in self._cb_wrapped_methods:
            self._callback_wrap(method_name)

        self._cb_raw_wrap_calls[method_name] = self._cb_raw_wrap_calls.get(
            method_name, []
        ) + [callback]

    def remove_method_callback(
        self, method_name: str, callback: Callable
    ) -> None:
        """Remove a callback from any function.

        Args:
            method_name (str):
                Name of the method to remove the callback from.

            callback (Callable):
                Function to be removed.
        """
        method = getattr(self, method_name, None)
        if not isinstance(method, Callable):
            raise RuntimeError(f"Method {method_name} does not exist.")
        if not method_name in self._cb_wrapped_methods:
            raise RuntimeError(
                "Can't remove callbacks from a method with no callback wrap."
                "\nHas this method been assigned a callback at all?"
            )
        self._cb_wrap_calls[method_name].remove(callback)

    def set_method_override(
        self, method_name: str, override_func: Callable
    ) -> None:
        """Replace a spaz method temporarily with a custom one.

        When the override function is executed, it will receive
        this spaz as an argument along with the arguments it would've
        gotten.

        eg. Overriding ``self.add_bomb_count(1)`` would return
        ``self.override_func(spaz, 1)``, having both spaz
        and the number as arguments.

        Args:
            method_name (str): Name of the method to override.
            override_func (Callable): Function to override with.
        """
        method = getattr(self, method_name, None)
        if not isinstance(method, Callable):
            raise RuntimeError(f"Method {method_name} does not exist.")
        if not method_name in self._cb_wrapped_methods:
            self._callback_wrap(method_name)
        self._cb_overwrite_calls[method_name] = override_func

    def reset_method_override(self, method_name: str) -> None:
        """Remove all callable overrides on the specified
        method (as a name), returning it to its default behavior.
        """
        method = getattr(self, method_name, None)
        if not isinstance(method, Callable):
            raise RuntimeError(f"Method {method_name} does not exist.")
        if not method_name in self._cb_wrapped_methods:
            return
        self._cb_overwrite_calls.pop(method_name, None)

    def _callback_wrap(self, method_name: str) -> None:
        method = getattr(self, method_name)
        if method in [
            self.exists,
            self._callback_wrap,
            self._callbacks_at_method,
        ]:
            return
        if not isinstance(method, Callable):
            raise ValueError(f"self.{method_name} is not a callable function.")

        def cbwrap(func):
            def w(*args, **kwargs):
                v = self._call_override(
                    method_name, func, args, kwargs
                )  # FIXME: Look into this...
                self._callbacks_at_method(method_name)
                return v

            return w

        setattr(self, method_name, cbwrap(method))
        self._cb_wrapped_methods.add(method_name)

    def _callbacks_at_method(self, method_name: str) -> None:
        if self.exists():
            for call in self._cb_wrap_calls.get(method_name, []):
                bs.CallPartial(call, self)()
            for call in self._cb_raw_wrap_calls.get(method_name, []):
                bs.CallPartial(call)()

    def _call_override(
        self, method_name: str, method: Callable, args: tuple, kwargs: dict
    ) -> Callable:
        if self.exists():
            override_call: Callable | None = self._cb_overwrite_calls.get(
                method_name, None
            )
            if isinstance(override_call, Callable):
                return override_call(self, *args, **kwargs)
            else:
                return method(*args, **kwargs)
        return lambda: None

    @override
    def handlemessage(self, msg: Any) -> Any:
        # in the off-chance an external mode uses 'bs.PowerupMessage',
        # let's add a compatibility layer to prevent us from breaking.
        if isinstance(msg, (bs.PowerupMessage, PowerupBoxMessage)):
            return self._handle_powerupmsg(msg)
        if isinstance(msg, bs.HitMessage):
            return self._handle_hitmsg(msg)

        # return to standard handling
        return super().handlemessage(msg)

    def _handle_powerupmsg(
        self, msg: bs.PowerupMessage | PowerupBoxMessage
    ) -> bool:
        """Handle modern powerup and legacy powerup messages.
        Returns success.
        """

        def powerup_signaling(success: bool, source: bs.Node | None) -> bool:
            # success should be the result of a handle function,
            # and we use it's result to refer whether we tell our
            # possibly existent source node that we got the powerup.
            if success and source:
                source.handlemessage(bs.PowerupAcceptMessage())
            return success

        if isinstance(msg, PowerupBoxMessage):
            # fusecore powerup handling
            return powerup_signaling(
                self._handle_powerups(msg), msg.source_node
            )
        if isinstance(msg, bs.PowerupMessage):
            # legacy powerup handling
            return powerup_signaling(
                self._handle_powerups_classic(msg), msg.sourcenode
            )

        return False

    def _handle_hitmsg(self, msg: bs.HitMessage) -> Any:
        if not self.node:
            return None
        if self.node.invincible:
            self.spaz_factory.block_sound.play(
                1.0,
                position=self.node.position,
            )
            return True

        # If we were recently hit, don't count this as another.
        # (so punch flurries and bomb pileups essentially count as 1 hit).
        local_time = int(bs.time() * 1000.0)
        assert isinstance(local_time, int)
        if (
            self._last_hit_time is None
            or local_time - self._last_hit_time > 1000
        ):
            self._num_times_hit += 1
            self._last_hit_time = local_time

        def fx_shield_particles():
            # Emit some cool looking sparks on shield hit.
            assert msg.force_direction is not None
            bs.emitfx(
                position=msg.pos,
                velocity=(
                    msg.force_direction[0] * 1.0,
                    msg.force_direction[1] * 1.0,
                    msg.force_direction[2] * 1.0,
                ),
                count=min(30, 5 + int(damage * 0.005)),
                scale=0.5,
                spread=0.3,
                chunk_type="spark",
            )

        def fx_punch_sound_effects():
            # Let's always add in a super-punch sound with boxing
            # gloves just to differentiate them.
            if msg.hit_subtype == "super_punch":
                self.spaz_factory.punch_sound_stronger.play(
                    1.0,
                    position=self.node.position,
                )
            if damage >= 500:
                sounds = self.spaz_factory.punch_sound_strong
                sound = sounds[random.randrange(len(sounds))]
            elif damage >= 100:
                sound = self.spaz_factory.punch_sound
            else:
                sound = self.spaz_factory.punch_sound_weak
            sound.play(1.0, position=self.node.position)

        def fx_punch_particles():
            # Throw up some chunks.
            assert msg.force_direction is not None
            bs.emitfx(
                position=msg.pos,
                velocity=(
                    msg.force_direction[0] * 0.5,
                    msg.force_direction[1] * 0.5,
                    msg.force_direction[2] * 0.5,
                ),
                count=min(10, 1 + int(damage * 0.0025)),
                scale=0.3,
                spread=0.03,
            )

            bs.emitfx(
                position=msg.pos,
                chunk_type="sweat",
                velocity=(
                    msg.force_direction[0] * 1.3,
                    msg.force_direction[1] * 1.3 + 5.0,
                    msg.force_direction[2] * 1.3,
                ),
                count=min(30, 1 + int(damage * 0.04)),
                scale=0.9,
                spread=0.28,
            )

            # Momentary flash.
            hurtiness = damage * 0.003
            punchpos = (
                msg.pos[0] + msg.force_direction[0] * 0.02,
                msg.pos[1] + msg.force_direction[1] * 0.02,
                msg.pos[2] + msg.force_direction[2] * 0.02,
            )
            flash_color = (1.0, 0.8, 0.4)
            light = bs.newnode(
                "light",
                attrs={
                    "position": punchpos,
                    "radius": 0.12 + hurtiness * 0.12,
                    "intensity": 0.3 * (1.0 + 1.0 * hurtiness),
                    "height_attenuated": False,
                    "color": flash_color,
                },
            )
            bs.timer(0.06, light.delete)

            flash = bs.newnode(
                "flash",
                attrs={
                    "position": punchpos,
                    "size": 0.17 + 0.17 * hurtiness,
                    "color": flash_color,
                },
            )
            bs.timer(0.06, flash.delete)

        def fx_impact_particles():
            assert msg.force_direction is not None
            bs.emitfx(
                position=msg.pos,
                velocity=(
                    msg.force_direction[0] * 2.0,
                    msg.force_direction[1] * 2.0,
                    msg.force_direction[2] * 2.0,
                ),
                count=min(10, 1 + int(damage * 0.01)),
                scale=0.4,
                spread=0.1,
            )

        spillover_ratio = 1.0
        if self.shield:
            # v result includes 'damage_scale' for calculation
            # unused value is for 'damage_smoothed'
            damage, _ = (
                (msg.flat_damage * self.impact_scale, 0)
                if msg.flat_damage
                else self.hit_message_impulse(msg, placebo=True)
            )

            spillover_damage = self.do_damage_shield(damage)
            fx_shield_particles()
            if not spillover_damage:
                return  # Good job shield!
            spillover_ratio = spillover_damage / damage
            # scale down variables for the following impulse
            msg.magnitude *= spillover_ratio
            msg.velocity_magnitude *= spillover_ratio
        # now we're gonna deal damage to spaz if we don't
        # have a shield or if we got some spillover damage.

        # v result includes 'damage_scale' for calculation
        damage, damage_smoothed = (
            (msg.flat_damage * self.impact_scale * spillover_ratio, 0)
            if msg.flat_damage
            else self.hit_message_impulse(msg, placebo=False)
        )
        damage = int(damage)
        self.node.handlemessage("hurt_sound")

        if msg.hit_type == "punch":
            # call our generic punched function
            self.on_punched(damage)
            # If damage was significant, lets show it.
            if damage >= 350:
                assert msg.force_direction is not None
                bs.show_damage_count(
                    "-" + str(int(damage / 10)) + "%",
                    msg.pos,
                    msg.force_direction,
                    self._dead,
                )
            # pizzazz
            fx_punch_sound_effects()
            fx_punch_particles()

        if msg.hit_type == "impact":
            fx_impact_particles()

        # It's kinda crappy to die from impacts, so lets reduce
        # impact damage by a reasonable amount *if* it'll keep us alive.
        if msg.hit_type == "impact" and damage >= self.hitpoints:
            # Drop damage to whatever puts us at 10 hit points,
            # or 200 less than it used to be whichever is greater
            # (so it *can* still kill us if its high enough).
            newdamage = max(damage - 200, self.hitpoints - 10)
            damage = newdamage

        self.node.handlemessage("flash")

        # If we're holding something, drop it.
        if damage > 0.0 and self.node.hold_node:
            self.node.hold_node = None

        self.do_damage(damage, death_type=bs.DeathType.IMPACT)

        # If we're dead, take a look at the smoothed damage value
        # (which gives us a smoothed average of recent damage) and shatter
        # us if its grown high enough.
        if self.hitpoints <= 0:
            if damage_smoothed >= 1000:
                self.shatter()
            return

        # If we're cursed, *any* damage blows us up.
        if self._cursed and damage > 0:
            bs.timer(
                0.05,
                bs.WeakCallStrict(
                    self.curse_explode, msg.get_source_player(bs.Player)
                ),
            )

        # If we're frozen, shatter.. otherwise die if we hit zero
        if self.frozen and (damage > 200 or self.hitpoints <= 0):
            self.shatter()

    def hit_message_impulse(
        self, msg: bs.HitMessage, placebo: bool
    ) -> tuple[float, float]:
        """Apply an impulse to this spaz using ``bs.HitMessage``."""
        # unfortunately, intellisense accepts this only!
        # pylint: disable=unidiomatic-typecheck
        assert type(msg.pos) is tuple[float, float, float]
        assert type(msg.velocity) is tuple[float, float, float]
        assert type(msg.force_direction) is tuple[float, float, float]
        return self.do_impulse(
            msg.pos,
            msg.velocity,
            msg.magnitude,
            msg.velocity_magnitude,
            msg.radius,
            placebo,
            msg.force_direction,
            apply_impact_scale=True,
        )

    def do_impulse(
        self,
        position: tuple[float, float, float],
        velocity: tuple[float, float, float],
        magnitude: float,
        velocity_magnitude: float,
        radius: float,
        placebo: bool,
        force_direction: tuple[float, float, float],
        apply_impact_scale: bool = True,
        pure: bool = False,
    ) -> tuple[float, float]:
        """Executes an impulse on this spaz and
        returns a damage value as the result of it.

        Args:
            position (tuple[float, float, float]):
                Place the impulse originates from.

            velocity (tuple[float, float, float]):
                Velocity of the impulse.

            magnitude (float):
                Magnitude of the impulse.

            velocity_magnitude (float):
                Velocity magnitude of the impulse.

            radius (float):
                Radial scale of the impulse.
                Useful for stabilizing push forces.

            placebo (bool):
                If ``True``, the impulse logic is ran but
                no actual impulse force is applied to the node.

            force_direction (tuple[float, float, float]):
                The positional direction this impulse has.

                e.g. An impulse with ``velocity (0, 1, 0)`` and
                ``force_direction (0, -1, 0)`` will perform an impulse
                that pushes downwards when it usually have pushed upwards.

            apply_impact_scale (bool, optional):
                If ``False``, values will not be adjusted with
                spaz's ``self.impact_scale`` variable.
                Defaults to True.

            pure (bool, optional):
                If ``True``, the impulse will return the pure
                damage value it dealt without applying a 0.22
                engine compensation multiplier to it.
                Use this exclusively if you need a more precise
                return on the damage's value.
                Defaults to False.

        Returns:
            tuple[float, float]:
                1. The damage dealt by this impulse.
                2. A smoothed variant of the damage dealt.
        """
        # pylint: disable=too-many-positional-arguments
        impact_scale = 1.0 if not apply_impact_scale else self.impact_scale

        self.node.handlemessage(
            "impulse",
            position[0],
            position[1],
            position[2],
            velocity[0],
            velocity[1],
            velocity[2],
            magnitude * impact_scale,
            velocity_magnitude * impact_scale,
            radius,
            placebo,
            force_direction[0],
            force_direction[1],
            force_direction[2],
        )
        dmg_scale = 1.0 if pure else 0.22
        return (
            self.node.damage * dmg_scale,
            self.node.damage_smoothed * dmg_scale,
        )

    def do_damage_shield(
        self, damage: float, ignore_invincibility: bool = False
    ) -> float:
        """Damage this spaz's shield if it exists.
        If the damage is large enough, it will destroy the shield
        entity and return the amount of leftover damage we have.

        This function should be called before dealing damage to
        spaz's themselves.

        Args:
            damage (float):
                Damage to apply to spaz's shield.

            ignore_invincibility (bool, optional):
                If ``True``, deal damage to the shield even if
                we're currently immune to damage.
                Defaults to False.
        Returns:
            float:
                Spillover damage if we dealt more damage than
                we applied to the shield.

                If we're immune to damage or dead, it always returns ``0.0``.

                If we don't have a shield, it returns
                the provided ``damage`` back.
        """
        if not self.node:
            return 0.0
        if self.node.invincible and not ignore_invincibility:
            self.spaz_factory.block_sound.play(
                1.0,
                position=self.node.position,
            )
            return 0.0
        if not self.shield:
            return damage

        assert self.shield_hitpoints
        max_spillover = self.spaz_factory.max_shield_spillover_damage
        # deal damage & update healthbar
        self.shield_hitpoints -= int(damage)
        self.shield.hurt = (
            1.0 - float(self.shield_hitpoints) / self.shield_hitpoints_max
        )
        if self.shield_hitpoints <= 0:
            self.kill_shield()
        else:
            self.spaz_factory.shield_hit_sound.play(
                0.5,
                position=self.node.position,
            )

        # If they passed our spillover threshold,
        # pass damage along to spaz.
        if self.shield_hitpoints <= -max_spillover:
            return -max_spillover - self.shield_hitpoints
        return 0.0  # Good job shield!

    def kill_shield(self) -> None:
        """Execute this spaz's shield."""
        if not self.shield or not self.shield_hitpoints:
            logging.warning(
                '"self.kill_shield()" called while shield'
                "doesn't properly exist.",
                stack_info=True,
            )
            return

        self.shield.delete()
        self.shield = None

        self.spaz_factory.shield_down_sound.play(
            1.0,
            position=self.node.position,
        )
        x, y, z = self.node.position
        fx_count = random.randrange(20, 30)
        bs.emitfx(
            position=(x, y + 0.9, z),
            velocity=self.node.velocity,
            count=fx_count,
            scale=1.0,
            spread=0.6,
            chunk_type="spark",
        )

    def do_damage(
        self,
        damage: float | int,
        ignore_invincibility: bool = False,
        fatal: bool = True,
        death_type: bs.DeathType = bs.DeathType.GENERIC,
    ) -> None | bool:
        """Deal damage to this spaz.
        This handles minor updates like updating the health bar
        to match current health, and whether we die if our
        health goes to zero or under.

        This function does NOT handle shields at all, to deal
        damage to shields, check ``self.do_damage_shield()``.

        Args:
            damage (float):
                Damage to apply to spaz's shield.

            ignore_invincibility (bool, optional):
                If ``True``, deal damage to the shield even if
                we're currently immune to damage.
                Defaults to False.

            fatal (bool, optional):
                If ``False``, the damage will not be able to
                kill spaz, no matter the value.
                Defaults to True.
        """
        if not self.node:
            return None
        if self.node.invincible and not ignore_invincibility:
            self.spaz_factory.block_sound.play(
                1.0,
                position=self.node.position,
            )
            return True

        # we continue with full damage or any spillover
        # shield damage we're about to receive.
        self.hitpoints -= int(damage)
        self.node.hurt = 1.0 - float(self.hitpoints) / self.hitpoints_max

        if not fatal and self.hitpoints < 1:
            self.hitpoints = 1
        self.update_healthbar()
        if self.hitpoints <= 0:
            self.node.handlemessage(bs.DieMessage(how=death_type))

    def update_healthbar(self) -> None:
        """Update "*self.node.hurt*" to display our current health."""
        self.node.hurt = 1.0 - float(self.hitpoints) / self.hitpoints_max

    def _handle_powerups(self, msg: PowerupBoxMessage) -> bool:
        """Handle incoming powerups.
        Manages powerup assigning and success return.
        """
        if not self.is_alive():
            return False

        if msg.grants_powerup:
            # instantiate our powerup type here!
            self.equip_powerup(msg.grants_powerup(self))
            return True

        return False

    def equip_powerup(self, powerup: SpazPowerup) -> None:
        """Equip a powerup in a specific slot.

        This handles equipping as well
        as warning, wearoff timers and billboards.
        """
        # if we have a NONE slot type, apply and forget about it
        if powerup.slot is PowerupSlotType.NONE:
            self._equip_orphan_powerup(powerup)
        # else, assign our incoming powerup to a 'PowerupSlot'
        # that holds its slot type
        else:
            powerup_slot: SpazPowerupSlot | None = self._powerup_slots.get(
                powerup.slot, None
            )
            if (
                powerup_slot is None
            ):  # missing slots require special handling...
                # ...for now, we'll fallback into creating a unique
                # slot for these with no additional handling.
                powerup_slot = self._powerup_slots[powerup.slot] = (
                    SpazPowerupSlot(self)
                )
                # the proper way would be to create these slots as
                # soon as we spawn, as we might create performance issues
                # at larger scales and messier code if we create on demand.
                logging.warning(
                    '"SpazPowerupSlot" created for %s as there was '
                    "no previous instance of one existing;"
                    " please dont do this!",
                    type(powerup.slot),
                    stack_info=True,
                )
            # our powerup slot will take it from here
            powerup_slot.apply_powerup(powerup)

    def _equip_orphan_powerup(self, powerup: SpazPowerup) -> None:
        """Equip a powerup that does not belong in any slot."""
        if powerup.texture_name != "empty":
            self._flash_billboard(bs.gettexture(powerup.texture_name))
        self.node.handlemessage("flash")
        powerup.equip()

    def powerup_billboard_slot(self, powerup: SpazPowerup) -> None:
        """Animate our powerup billboard properly."""
        slot: int = powerup.slot.value
        if not 3 >= slot >= 1:  # node only have 3 slots
            return

        tex_name: str = powerup.texture_name
        t_ms = int(bs.time() * 1000.0)

        # don't use 'setattr' unless it is absolutely necessary, kids.
        setattr(  # texture
            self.node,
            f"mini_billboard_{slot}_texture",
            bs.gettexture(tex_name),
        )
        setattr(  # initial time
            self.node,
            f"mini_billboard_{slot}_start_time",
            t_ms,
        )
        setattr(  # end time
            self.node,
            f"mini_billboard_{slot}_end_time",
            t_ms + powerup.duration_ms,
        )

    def powerup_warn(self, tex: str) -> None:
        """Show a billboard warning us of a powerup running out of time."""
        if not self.node or tex == "empty":
            return

        self.node.billboard_texture = bs.gettexture(tex)
        self.node.billboard_opacity = 1.0
        self.node.billboard_cross_out = True

    def powerup_unwarn(self) -> None:
        """Hide our billboard warning."""
        if not self.node:
            return

        self.node.billboard_opacity = 0.0
        self.node.billboard_cross_out = False

    def unequip_boxing_gloves(self) -> None:
        """Remove gloves without doing the previously
        hardcoded powerdown sound.
        """
        if self._demo_mode:  # Preserve old behavior.
            self._punch_power_scale = 1.2
            self._punch_cooldown = spaz.BASE_PUNCH_COOLDOWN
        else:
            self._punch_power_scale = self.spaz_factory.punch_power_scale
            self._punch_cooldown = self.spaz_factory.punch_cooldown
        self._has_boxing_gloves = False
        if self.node:
            self.node.boxing_gloves_flashing = False
            self.node.boxing_gloves = False

    @override
    def on_expire(self) -> None:
        """Prevent from hanging onto the activity
        by cleaning after ourselves.
        """
        # because components and powerups depend on spaz themselves,
        # we need to remove them on expire to keep the gc happy.
        self.components = {}
        self._powerup_slots = {}
        # these don't cause as many issues if left unbothered, but
        # it's still a good idea to take care of these containers.
        self._cb_wrapped_methods = set()
        self._cb_wrap_calls = {}
        self._cb_raw_wrap_calls = {}
        self._cb_overwrite_calls = {}

    ### vvv THEY'RE ONLY HERE FOR RETROCOMPATIBILITY! vvv
    ### vvv             LEGACY FUNCTIONS              vvv
    ### vvv             DON'T USE THOSE!              vvv
    ### vvv THEY'RE ONLY HERE FOR RETROCOMPATIBILITY! vvv

    @property
    def bomb_type(self) -> str:
        """### Don't use this!
        We keep this for the sake of retrocompat.
        Use ``self.active_bomb_class`` instead.
        """
        return self._str_bomb_type

    @bomb_type.setter
    def bomb_type(self, btype: str) -> None:
        """### Don't use this!
        We keep this for the sake of retrocompat.
        Use ``self.active_bomb_class`` instead.
        """
        self._str_bomb_type = btype
        self._compat_bomb_update()

    @override
    def drop_bomb(self):
        """### Don't use this!
        We keep this for the sake of retrocompat.
        Use ``self.drop_bomb_class()`` instead.
        """
        # NOTE: Bombs have the same methods as the vanilla ones, but it could
        # cause issues in particular circumstances... Keep that in mind!
        return cast(VanillaBomb, self.drop_bomb_class())

    def _compat_bomb_update(self, check_default: bool = False) -> None:
        """transform our ``self.default_bomb_type`` into a
        ``self.default_bomb`` class.

        ### This function is here for compatibility reasons, don't use this!
        """

        str_type = (
            self.default_bomb_type if check_default else self._str_bomb_type
        )
        bomb_class: Optional[Type[Bomb]] = None
        for bomb in BOMB_SET:
            if str_type == bomb.bomb_type:
                bomb_class = bomb
        if bomb_class is None:
            logging.warning(
                "spaz: '_compat_bomb_update' was called with"
                " invalid bomb_type: '%s'",
                str_type,
                stack_info=True,
            )
            return
        self.active_bomb_class = bomb_class

    def _handle_powerups_classic(self, msg: bs.PowerupMessage) -> bool:
        """Old-school handling for 'bs.PowerupMessage'."""
        if not self.is_alive():
            return False

        powerup: Optional[Type[SpazPowerup]] = None
        # get the proper powerup via powerupbox name
        for pb in POWERUPBOX_SET:
            if msg.poweruptype == pb.name:
                powerup = pb.powerup_to_grant
        if powerup is None:
            logging.warning(
                "spaz: '_handle_powerups_classic' called"
                "  with an invalid value: '%s'",
                msg.poweruptype,
                stack_info=True,
            )
            return False

        return self._handle_powerups(
            PowerupBoxMessage(
                grants_powerup=powerup, source_node=msg.sourcenode
            )
        )


# Overwrite the vanilla game's spaz init with our own
spaz.Spaz = Spaz
