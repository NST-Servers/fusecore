"""Defines our Claypocalypse Spaz modified class."""

from __future__ import annotations
from typing import (
    Type,
    cast,
    override,
    Callable,
    Any,
    TYPE_CHECKING,
    TypedDict,
    overload,
)

import bascenev1 as bs
from claymore._tools import obj_clone, obj_method_override
from claymore.core.bomb import (
    BOMB_SET,
    Bomb,
)
from claymore.core.powerupbox import PowerupBox, PowerupBoxFactory
from bascenev1lib.actor import spaz
from bascenev1lib.actor.spaz import BombDiedMessage

import logging

if TYPE_CHECKING:
    from claymore.core.powerup import SpazPowerup

# Clone our vanilla spaz class
# We'll be calling this over "super()" to prevent the code
# from falling apart because the engine is like that. :p
VanillaSpaz: Type[spaz.Spaz] = obj_clone(spaz.Spaz)

POWERUP_WARNING = set()


class Spaz(spaz.Spaz):
    """Wrapper for our actor Spaz class."""

    @override
    def __init__(self, *args, **kwargs):
        VanillaSpaz.__init__(
            self, *args, **kwargs
        )  # FIXME: Troubleshoot this line?

        # ruleset overwrite
        self.hitpoints = 1000
        # self.hitpoints_max = int(
        #    clay.rulesets.get('player','health') * 10
        # )

        self._cb_wrapped_methods: set[str] = set()
        self._cb_wrap_calls: dict[str, list[Callable]] = {}
        self._cb_raw_wrap_calls: dict[str, list[Callable]] = {}
        self._cb_overwrite_calls: dict[str, Callable | None] = {}

        self.damage_scale = 0.22

        # Powerup class instances
        self._powerup_1: SpazPowerup | None = None
        self._powerup_2: SpazPowerup | None = None
        self._powerup_3: SpazPowerup | None = None
        # Wear-off function timers
        self._powerup_1_timer_a: bs.Timer | None = None
        self._powerup_2_timer_a: bs.Timer | None = None
        self._powerup_3_timer_a: bs.Timer | None = None
        # Warning function & visuals timers
        self._powerup_1_timer_b: bs.Timer | None = None
        self._powerup_2_timer_b: bs.Timer | None = None
        self._powerup_3_timer_b: bs.Timer | None = None

        # We callback wrap these on creation as the engine
        # clones these, so they won't be able to be updated later.
        self._callback_wrap('on_punch_press')
        self._callback_wrap('on_bomb_press')
        self._callback_wrap('on_jump_press')
        self._callback_wrap('on_pickup_press')

        # for name in dir(self):
        #    if name.startswith('__'):
        #        continue
        #    v = getattr(self, name, None)
        #    if callable(v) or isinstance(v, (staticmethod, classmethod)):
        #        self._callback_wrap(name)

    def get_active_ruleset(self) -> dict:
        """Get this session's current ruleset."""
        return {}

    @override
    def handlemessage(self, msg: Any) -> Any:
        # All some extra handlers
        if isinstance(msg, bs.PowerupMessage):
            powerup_result = self.handle_powerup_msg(msg)
            # Tell the source node we got the powerup
            if powerup_result and msg.sourcenode:
                msg.sourcenode.handlemessage(bs.PowerupAcceptMessage())
            return powerup_result

        # return to standard handling
        return VanillaSpaz.handlemessage(self, msg)

    def set_bomb_type(self, bomb_type: str) -> None:
        """Assign this spaz a bomb type."""
        # Make sure a bomb with this bomb_type exists
        any_bomb = [b for b in BOMB_SET if b.bomb_type == bomb_type]
        if not any_bomb:
            raise ValueError(f'No bomb with bomb_type "{bomb_type}" exists.')

        self.bomb_type = bomb_type

    def reset_bomb_type(self) -> None:
        """Reset this spaz's assigned bomb type."""
        self.bomb_type = self.bomb_type_default

    @override
    def drop_bomb(self) -> Bomb | None:
        """
        Tell the spaz to drop one of his bombs, and returns
        the resulting bomb object.

        If the spaz has no bombs or is otherwise unable to
        drop a bomb, returns None.
        """

        if (self.land_mine_count <= 0 and self.bomb_count <= 0) or self.frozen:
            return None
        assert self.node
        pos = self.node.position_forward
        vel = self.node.velocity

        if self.land_mine_count > 0:
            dropping_bomb = False
            self.set_land_mine_count(self.land_mine_count - 1)
            bomb_type = 'land_mine'
        else:
            dropping_bomb = True
            bomb_type = self.bomb_type

        # Get our custom bomb class type
        bomb_classtype: Type[Bomb] | None = (
            [b for b in BOMB_SET if b.bomb_type == bomb_type] or [None]
        )[0]
        if bomb_classtype is None:
            raise ValueError(f'No bombs with bomb_type "{bomb_type}".')

        bomb = bomb_classtype(
            position=(pos[0], pos[1] - 0.0, pos[2]),
            velocity=(vel[0], vel[1], vel[2]),
            source_player=self.source_player,
            owner=self.node,
        ).autoretain()

        assert bomb.node
        if dropping_bomb:
            self.bomb_count -= 1
            bomb.node.add_death_action(
                bs.WeakCall(self.handlemessage, BombDiedMessage())
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
            factory = spaz.SpazFactory.get()
            for attr in ['materials', 'roller_materials']:
                materials = getattr(self.node, attr)
                if factory.curse_material in materials:
                    setattr(
                        self.node,
                        attr,
                        tuple(
                            m for m in materials if m != factory.curse_material
                        ),
                    )
            self.node.curse_death_time = 0
        self.hitpoints = self.hitpoints_max
        self.node.hurt = 0
        self._last_hit_time = None
        self._num_times_hit = 0

    def add_bomb_count(self, count: int) -> None:
        """
        Increase the bomb limit this Spaz has.

        Use responsibly -- if you're using this for a powerup, make
        sure the *unequip* method has an *add_bomb_count* that
        deducts the given bombs!
        """
        self._max_bomb_count += count
        self.bomb_count += count

    def add_method_callback(self, method_name: str, callback: Callable) -> None:
        """
        Add a callback to any function.

        Once the base method is executed, all callbacks will be
        executed, containing ourselves as an argument.

        Args:
            method_name (str): Name of the method to receive the callback
            callback (Callable): Function to be linked to the target method
        """
        method = getattr(self, method_name, None)
        if not isinstance(method, Callable):
            raise RuntimeError(f'Method {method_name} does not exist.')
        if not method_name in self._cb_wrapped_methods:
            self._callback_wrap(method_name)

        self._cb_wrap_calls[method_name] = self._cb_wrap_calls.get(
            method_name, []
        ) + [callback]

    def add_method_callback_raw(
        self, method_name: str, callback: Callable
    ) -> None:
        """
        Add a callback to any function.

        Once the base method is executed, all callbacks will be executed.
        Unlike *add_callback*, it will not contain additional arguments.

        Args:
            method_name (str): Name of the method to receive the callback
            callback (Callable): Function to be linked to the target method
        """
        method = getattr(self, method_name, None)
        if not isinstance(method, Callable):
            raise RuntimeError(f'Method {method_name} does not exist.')
        if not method_name in self._cb_wrapped_methods:
            self._callback_wrap(method_name)

        self._cb_raw_wrap_calls[method_name] = self._cb_raw_wrap_calls.get(
            method_name, []
        ) + [callback]

    def remove_method_callback(
        self, method_name: str, callback: Callable
    ) -> None:
        """
        Remove a callback from any function.

        Args:
            method_name (str): Name of the method to remove the callback from
            callback (Callable): Function to be removed
        """
        method = getattr(self, method_name, None)
        if not isinstance(method, Callable):
            raise RuntimeError(f'Method {method_name} does not exist.')
        if not method_name in self._cb_wrapped_methods:
            raise RuntimeError(
                'Can\'t remove callbacks from a method with no callback wrap.'
                '\nHas this method been assigned a callback at all?'
            )
        self._cb_wrap_calls[method_name].remove(callback)

    def set_method_override(
        self, method_name: str, override_func: Callable
    ) -> None:
        """
        Replace a spaz method temporarily with a custom one.

        When the override function is executed, it will receive
        this spaz as an argument along with the arguments it would've
        gotten.

        E.g. Overriding "*add_bomb_count(1)*" would return
        "*override_func(spaz, 1)*", having both spaz
        and the number as arguments.

        Args:
            method_name (str): Name of the method to override
            override_func (Callable): Function to override with
        """
        method = getattr(self, method_name, None)
        if not isinstance(method, Callable):
            raise RuntimeError(f'Method {method_name} does not exist.')
        if not method_name in self._cb_wrapped_methods:
            self._callback_wrap(method_name)
        self._cb_overwrite_calls[method_name] = override_func

    def reset_method_override(self, method_name: str) -> None:
        """
        Reset a spaz method to it's default if it's been overriden.

        Args:
            method_name (str): Name of the method to reset
        """
        method = getattr(self, method_name, None)
        if not isinstance(method, Callable):
            raise RuntimeError(f'Method {method_name} does not exist.')
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
            raise ValueError(f'self.{method_name} is not a callable function.')

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
                bs.Call(call, self)()
            for call in self._cb_raw_wrap_calls.get(method_name, []):
                bs.Call(call)()

    def _call_override(
        self, method_name: str, method: Callable, args: list, kwargs: dict
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

    def handle_hit(self, msg: bs.HitMessage) -> float:
        """Handle getting hit."""
        return 0.0

    def do_damage(
        self,
        damage: int,
        srcnode: bs.Node | None = None,
        ignore_shield: bool = False,
        ignore_invincibility: bool = False,
        fatal: bool = True,
    ) -> None:
        """
        Make this spaz receive a determined amount of damage.

        You can determine if the damage can pierce shields and directly
        go to our spaz node, and if the damage can be fatal and kill in
        case our health goes below 1.

        Args:
            damage (float): Amount of damage to receive
            fatal (bool, optional): Whether the damage can kill. Defaults to True.
        """
        self.on_punched(damage)
        self.hitpoints -= damage

        if self.hitpoints <= 0 and fatal:
            self.node.handlemessage(bs.DieMessage(how=bs.DeathType.IMPACT))
        elif not fatal:
            self.hitpoints = max(1, self.hitpoints)

        self.update_healthbar()

    def do_damage_shield(self) -> float | None:
        """Apply damage to this spaz's shield. Returns spillover."""

    @overload
    def do_impulse(self, msg: bs.HitMessage) -> float: ...

    @overload
    def do_impulse(
        self,
        position: tuple[float, float, float],
        velocity: tuple[float, float, float] = (0, 0, 0),
        magnitude: float = 0.0,
        velocity_magnitude: float = 0.0,
        radius: float = 1.0,
        force_direction: tuple[float, float, float] = (0, 0, 0),
    ) -> float: ...

    def do_impulse(self, *args, **kwargs) -> float:
        """
        Applies a velocity impulse to this spaz.

        Returns the hypothetical damage this impulse would've dealt.
        """
        f: bs.HitMessage | tuple | None = args[0] or kwargs.get('msg', None)
        # do_impulse via hitmessage
        if isinstance(f, bs.HitMessage):
            position = f.pos
            velocity = f.velocity
            mag = f.magnitude
            vmag = f.velocity_magnitude or 0
            radius = f.radius
            forcedir = f.force_direction
        # do_impulse via arguments
        elif isinstance(f, tuple):
            position = args[0] or kwargs.get('position')
            velocity = args[1] or kwargs.get('velocity')
            mag = args[2] or kwargs.get('magnitude')
            vmag = args[3] or kwargs.get('velocity_magnitude', 0)
            radius = args[4] or kwargs.get('radius')
            forcedir = args[5] or kwargs.get('force_direction')
        else:
            return 0.0
        if position is None or velocity is None or forcedir is None:
            return 0.0

        x, y, z = position
        u, v, w = velocity
        i, j, k = forcedir

        if vmag > 0:  # We can't use this.
            logging.warn(
                'velocity_magnitude isn\'t supported yet.', stack_info=True
            )
            vmag = 0

        self.node.handlemessage(
            'impulse', x, y, z, u, v, w, mag, vmag, radius, 0, i, j, k
        )
        return int(self.damage_scale * self.node.damage)

    def update_healthbar(self) -> None:
        """Update "*self.node.hurt*" to display our current health."""
        self.node.hurt = 1.0 - float(self.hitpoints) / self.hitpoints_max

    def handle_powerup_msg(self, msg: bs.PowerupMessage) -> bool:
        """
        Handle incoming powerup messages.

        Control importing powerups, equipping them and
        unequipping any other powerup in the same slot.
        """
        if not self.is_alive():
            return False

        from claymore.core.powerup import POWERUP_SET

        powerup: SpazPowerup | None = None
        # Assign this powerup, throw an error if we can't do so.
        if msg.poweruptype is not None:
            for p in POWERUP_SET:
                if p.name == msg.poweruptype:
                    powerup = p()

            if powerup is None:
                # Warn our player if they're trying to get a powerup
                # that does not exist (only do once.)
                if not msg.poweruptype in POWERUP_WARNING:
                    boxdel = msg.sourcenode.getdelegate(PowerupBox, None)  # type: ignore
                    boxname = (
                        boxdel.name
                        if isinstance(boxdel, PowerupBox)
                        else "An unknown powerup box"
                    )
                    logging.warning(
                        f'WARNING: "{boxname}" has provided an'
                        f' undefined powerup type "{msg.poweruptype}"',
                        stack_info=True,
                    )
                    POWERUP_WARNING.add(msg.poweruptype)

        # Do our powerup shenanigans
        if powerup:
            slot = powerup.slot
            # Unequip previous powerup in slot if we have one
            if self._has_powerup_in_slot(slot):
                self._unequip_powerup(slot)
            self._equip_powerup(powerup, slot)

            if powerup.texture != 'empty':
                self.node.billboard_opacity = 1.0
                self.node.billboard_cross_out = False
                self._flash_billboard(powerup.get_texture())

        return True

    def _has_powerup_in_slot(self, slot: int) -> bool:
        """Return if we have a powerup in the specified slot."""
        return getattr(self, f'_powerup_{slot}', None) is not None

    def _get_powerup_slot_data(self, slot: int) -> powerup_ref_dict:
        """Return a dict with strings referencing powerup data in that slot."""
        # Raise an error if we receive an invalid slot
        if not 3 >= slot >= 1:
            raise ValueError(f'Slot {slot} does not exist.')

        return {
            'node_texture': f'mini_billboard_{slot}_texture',
            'node_start_time': f'mini_billboard_{slot}_start_time',
            'node_end_time': f'mini_billboard_{slot}_end_time',
            'powerup': f'_powerup_{slot}',
            'timer_wearoff': f'_powerup_{slot}_timer_a',
            'timer_warning': f'_powerup_{slot}_timer_b',
        }

    def _equip_powerup(
        self,
        powerup: SpazPowerup,
        slot: int,
    ):
        """
        Equip a powerup in a specific slot.

        This handles equipping as well
        as warning, wearoff timers and billboards.
        """
        powerup.equip(self)

        # We don't assign powerup to a slot if we're out of range.
        if not 3 >= slot >= 1:
            return
        # Get slot data names
        ref = self._get_powerup_slot_data(slot)
        setattr(self, ref['powerup'], powerup)
        setattr(
            self,
            ref['timer_warning'],
            bs.Timer(
                max(0, (powerup.duration / 1000) - 2),
                bs.WeakCall(self._warn_powerup, slot),
            ),
        )
        setattr(
            self,
            ref['timer_wearoff'],
            bs.Timer(
                powerup.duration / 1000,
                bs.WeakCall(self._unequip_powerup, slot, True),
            ),
        )

        if powerup.texture != 'empty' and self.exists():
            setattr(self.node, ref['node_texture'], powerup.get_texture())
            t_ms = int(bs.time() * 1000.0)
            setattr(self.node, ref['node_start_time'], t_ms)
            setattr(self.node, ref['node_end_time'], t_ms + powerup.duration)

    def _warn_powerup(self, slot: int) -> None:
        """"""
        # Ignore if we get an invalid slot or if we don't exist anymore
        if not 3 >= slot >= 1 or not self.exists():
            return
        # Get slot data names
        ref = self._get_powerup_slot_data(slot)
        powerup: SpazPowerup | None = getattr(self, ref['powerup'])
        # Don't do anything we don't have a powerup in this slot
        if powerup is None:
            return
        # Run the powerup's warning function
        powerup.warning(self)

        # Don't display anything if this powerup does not have a texture
        if powerup.texture == 'empty':
            return
        # Pull out the warning billboard
        self.node.billboard_texture = powerup.get_texture()
        self.node.billboard_opacity = 1.0
        self.node.billboard_cross_out = True

    def _unequip_powerup(
        self,
        slot: int,
        play_sound: bool = False,
    ) -> None:
        """
        Unequip a powerup via their powerup slot.

        Runs the proper unequip method and cleans up
        leftover billboards and timers.
        """
        # Ignore if we get an invalid slot or if we don't exist anymore
        if not 3 >= slot >= 1 or not self.exists():
            return

        # Get slot data names
        ref = self._get_powerup_slot_data(slot)
        powerup: SpazPowerup | None = getattr(self, ref['powerup'])
        # Don't do anything we don't have a powerup in this slot
        if powerup is None:
            return

        # Reset them variables
        ## Node times
        for vref in [ref['node_start_time'], ref['node_end_time']]:
            setattr(self.node, vref, -9999)
        ## Timers
        for vref in [ref['timer_warning'], ref['timer_wearoff']]:
            setattr(self, vref, None)
        # Finally, unequip.
        powerup.unequip(self)
        setattr(self, ref['powerup'], None)
        self.node.billboard_opacity = 0.0

        if play_sound:
            # Play the *blwom* sound
            pwpfact: PowerupBoxFactory = cast(
                PowerupBoxFactory, PowerupBoxFactory.instance()
            )
            pwpfact.powerdown_sound.play(position=self.node.position)

    def _unequip_gloves(self) -> None:
        """Remove gloves without doing the *blwom* sound and removing flash."""
        if self._demo_mode:  # Preserve old behavior.
            self._punch_power_scale = 1.2
            self._punch_cooldown = spaz.BASE_PUNCH_COOLDOWN
        else:
            factory = spaz.SpazFactory.get()
            self._punch_power_scale = factory.punch_power_scale
            self._punch_cooldown = factory.punch_cooldown
        self._has_boxing_gloves = False
        if self.node:
            self.node.boxing_gloves_flashing = False
            self.node.boxing_gloves = False


# Overwrite the vanilla game's spaz init with our own
obj_method_override(spaz.Spaz, Spaz)


# Auto-Fill badonk
class powerup_ref_dict(TypedDict):
    node_texture: str
    node_start_time: str
    node_end_time: str
    powerup: str
    timer_wearoff: str
    timer_warning: str
