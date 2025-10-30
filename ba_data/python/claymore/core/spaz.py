"""Defines our Claypocalypse Spaz modified class."""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import (
    Type,
    cast,
    override,
    Callable,
    Any,
    TYPE_CHECKING,
    overload,
)

import bascenev1 as bs

from bascenev1lib.actor import spaz
from bascenev1lib.actor.spaz import BombDiedMessage
from bascenev1lib.actor.bomb import Bomb as DeprecatedBomb


from claymore._tools import obj_clone, obj_method_override
from claymore.core.bomb import (
    Bomb,
    LandMine,
)
from claymore.core.powerupbox import PowerupBoxMessage
from claymore.core.shared import PowerupSlotType

import logging

if TYPE_CHECKING:
    from claymore.core.powerup import SpazPowerup

# Clone our vanilla spaz class
# We'll be calling this over "super()" to prevent the code
# from falling apart because the engine is like that. :p
VanillaSpaz: Type[spaz.Spaz] = obj_clone(spaz.Spaz)

POWERUP_WARNING = set()


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
        powerup.equip(self.owner)

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

        self.active_powerup.warning(self.owner)
        self.owner._powerup_warn(self.active_powerup.texture_name)

    def _unequip(self, overwrite: bool = False, clone: bool = False) -> None:
        if not self.active_powerup or not self.owner.exists():
            return

        self.owner._powerup_unwarn()
        self.active_powerup.unequip(
            self.owner, overwrite=overwrite, clone=clone
        )
        self.active_powerup = None
        self.timer_warning = None
        self.timer_wearoff = None


class Spaz(spaz.Spaz):
    """Wrapper for our actor Spaz class."""
    default_bomb: Type[Bomb] = Bomb

    @override
    def __init__(self, *args, **kwargs):
        VanillaSpaz.__init__(
            self, *args, **kwargs
        ) 

        self.hitpoints = 1000
        
        self.active_bomb: Type[Bomb] = self.default_bomb
        self._bomb_compat() # bot behavior & mod compatibility

        self._cb_wrapped_methods: set[str] = set()
        self._cb_wrap_calls: dict[str, list[Callable]] = {}
        self._cb_raw_wrap_calls: dict[str, list[Callable]] = {}
        self._cb_overwrite_calls: dict[str, Callable | None] = {}

        self.damage_scale = 0.22

        self._powerup_wearoff_time_ms: int = 2000
        """For how long the powerup wearoff alert is displayed for (in milliseconds.)"""

        # Slots to hold powerups in
        self._powerup_slots: dict[PowerupSlotType, SpazPowerupSlot] = {
            PowerupSlotType.BUFF: SpazPowerupSlot(self),
            PowerupSlotType.BOMB: SpazPowerupSlot(self),
            PowerupSlotType.GLOVES: SpazPowerupSlot(self),
            # ... (Append more 'PowerupSlotType' entries here!)
        }

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

    @override
    def handlemessage(self, msg: Any) -> Any:
        # in the off-chance an external mode uses 'bs.PowerupMessage',
        # let's add a compatibility layer to prevent us from breaking.
        if isinstance(msg, bs.PowerupMessage):
            success = self.handle_powerupmsg_compat(msg)
            if success and msg.sourcenode:
                msg.sourcenode.handlemessage(bs.PowerupAcceptMessage())
            return success

        # now, the NEW powerup handle function.
        elif isinstance(msg, PowerupBoxMessage):
            success: bool = self.handle_powerupmsg(msg)
            if success and msg.source_node:
                msg.source_node.handlemessage(bs.PowerupAcceptMessage())
            return success

        # return to standard handling
        return VanillaSpaz.handlemessage(self, msg)

    def apply_ruleset(self) -> None:
        ...
        # self.hitpoints_max = int(
        #    clay.rulesets.get('player','health') * 10
        # )

    def assign_bomb_type(self, bomb: Type[Bomb]) -> None:
        """Set a bomb type for this spaz to use."""
        self.active_bomb = bomb

    def reset_bomb_type(self) -> None:
        """Reset our bomb type back to our default type."""
        self.active_bomb = self.default_bomb

    def _bomb_compat(self) -> None:
        """DEPRECATED transform our 'self.default_bomb_type'
        into a 'self.default_bomb' class.
        """
        # nested import of humilliation
        # curse you, deprecation!
        from claymore.core.bomb import (
            IceBomb,
            ImpactBomb,
            StickyBomb,
            LandMine,
        )
        
        if self.default_bomb_type != 'normal':
            bomb_type: Type[Bomb] = Bomb
            match self.default_bomb_type:
                case 'ice':
                    bomb_type = IceBomb
                case 'land_mine':
                    bomb_type = LandMine
                case 'sticky':
                    bomb_type = StickyBomb
                case 'impact':
                    bomb_type = ImpactBomb
            self.active_bomb = bomb_type
        
        if self.bomb_type != 'normal':
            bomb_type: Type[Bomb] = Bomb
            match self.bomb_type:
                case 'ice':
                    bomb_type = IceBomb
                case 'land_mine':
                    bomb_type = LandMine
                case 'sticky':
                    bomb_type = StickyBomb
                case 'impact':
                    bomb_type = ImpactBomb
            self.active_bomb = bomb_type
        
    @override
    def drop_bomb(self):
        """DEPRECATED drop_bomb function."""
        # NOTE: Bombs have the same functions and calls as in vanilla, but
        # it could cause issues in particular circumstances... Keep that in mind!
        return cast(DeprecatedBomb, self.drop_bomb_type())

    def drop_bomb_type(self) -> Bomb | None:
        """Tell the spaz to drop one of his bombs, and returns
        the resulting bomb object.

        If the spaz has no bombs or is otherwise unable to
        drop a bomb, returns None.
        """
        # TODO: Migrate the landmine counter into a proper class for flexible usage
        if (self.land_mine_count <= 0 and self.bomb_count <= 0) or self.frozen:
            return None
        assert self.node
        pos = self.node.position_forward
        vel = self.node.velocity

        bomb_type: Type[Bomb] = self.active_bomb
        is_external = False
        # TODO: Migrate the landmine counter into a proper class for flexible usage
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
            raise RuntimeError(f'Method {method_name} does not exist.')
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
        """Remove a callback from any function.

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
        """Replace a spaz method temporarily with a custom one.

        When the override function is executed, it will receive
        this spaz as an argument along with the arguments it would've
        gotten.

        eg. Overriding "*add_bomb_count(1)*" would return
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
        """Remove all callable overrides on the specified
        method (as a name), returning it to its default behavior.
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
        """Make this spaz receive a determined amount of damage.

        You can determine if the damage can pierce shields and directly
        go to our spaz node, and if the damage can be fatal and kill in
        case our health goes below 1.

        Args:
            damage (float): Amount of damage to receive
            fatal (bool, optional): Whether the damage can kill. Defaults to True.
        """  # TODO: update docstring
        self.on_punched(damage)
        self.hitpoints -= damage

        if self.hitpoints <= 0 and fatal:
            self.node.handlemessage(bs.DieMessage(how=bs.DeathType.IMPACT))
        elif not fatal:
            self.hitpoints = max(1, self.hitpoints)

        self.update_healthbar()

    def do_damage_shield(self) -> int:
        """Apply damage to this spaz's shield. Returns spillover."""
        return 0

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
        """Applies a velocity impulse to this spaz.

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
            logging.warning(
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

    def handle_powerupmsg(self, msg: PowerupBoxMessage) -> bool:
        """Handle incoming powerups.

        Manages powerup assigning and success return.
        """
        if not self.is_alive():
            return False

        if msg.grants_powerup:
            # instantiate our powerup type here!
            self.equip_powerup(msg.grants_powerup())
            return True

        return False

    def handle_powerupmsg_compat(self, msg: bs.PowerupMessage) -> bool:
        """DEPRECATED handling for 'bs.PowerupMessage'."""
        if not self.is_alive():
            return False

        powerup: Type[SpazPowerup] | None = None

        # nested import of humilliation
        # curse you, deprecation!
        from claymore.core.powerup import (
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

        match msg.poweruptype:
            case 'triple_bombs':
                powerup = TripleBombsPowerup
            case 'land_mines':
                powerup = LandMinesPowerup
            case 'impact_bombs':
                powerup = ImpactBombsPowerup
            case 'sticky_bombs':
                powerup = StickyBombsPowerup
            case 'punch':
                powerup = PunchPowerup
            case 'shield':
                powerup = ShieldPowerup
            case 'curse':
                powerup = CursePowerup
            case 'ice_bombs':
                powerup = IceBombsPowerup
            case 'health':
                powerup = HealthPowerup

        return self.handle_powerupmsg(
            PowerupBoxMessage(
                grants_powerup=powerup, source_node=msg.sourcenode
            )
        )

    def equip_powerup(self, powerup: SpazPowerup) -> None:
        """Equip a powerup in a specific slot.

        This handles equipping as well
        as warning, wearoff timers and billboards.
        """
        # if we have a NONE slot type, apply and forget about it
        if powerup.slot is PowerupSlotType.NONE:
            self._orphan_powerup(powerup)
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
                    f'"SpazPowerupSlot" created for {type(powerup.slot)} as there was '
                    'no previous instance of one existing; please dont do this!',
                    stack_info=True,
                )
            # our powerup slot will take it from here
            powerup_slot.apply_powerup(powerup)

    def _orphan_powerup(self, powerup: SpazPowerup) -> None:
        """Equip a powerup that does not belong in any slot."""
        if powerup.texture_name != 'empty':
            self._flash_billboard(bs.gettexture(powerup.texture_name))
        self.node.handlemessage('flash')
        powerup.equip(self)

    def _powerup_billboard_slot(self, powerup: SpazPowerup) -> None:
        """Animate our powerup billboard properly."""
        slot: int = powerup.slot.value
        if not 3 >= slot >= 1:  # node only have 3 slots
            return

        tex_name: str = powerup.texture_name
        t_ms = int(bs.time() * 1000.0)

        # don't use 'setattr' unless it is absolutely necessary, kids.
        setattr(  # texture
            self.node,
            f'mini_billboard_{slot}_texture',
            bs.gettexture(tex_name),
        )
        setattr(  # initial time
            self.node,
            f'mini_billboard_{slot}_start_time',
            t_ms,
        )
        setattr(  # end time
            self.node,
            f'mini_billboard_{slot}_end_time',
            t_ms + powerup.duration_ms,
        )

    def _powerup_warn(self, tex: str) -> None:
        """Show a billboard warning us of a powerup running out of time."""
        if not self.node or tex == 'empty':
            return

        self.node.billboard_texture = bs.gettexture(tex)
        self.node.billboard_opacity = 1.0
        self.node.billboard_cross_out = True

    def _powerup_unwarn(self) -> None:
        """Hide our billboard warning."""
        if not self.node:
            return

        self.node.billboard_opacity = 0.0
        self.node.billboard_cross_out = False

    def gloves_silent_unequip(self) -> None:
        """Remove gloves without doing the *blwom* sound and removing flash."""
        # NOTE: Not sure if I should move this to the powerup file itself...
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
