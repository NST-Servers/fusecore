"""Defines our custom PlayerSpaz class."""

from __future__ import annotations
from typing import Any, override, Type

import bascenev1 as bs
from claymore._tools import obj_clone, obj_method_override
from bascenev1lib.actor import playerspaz
from bascenev1lib.actor.spaz import (
    PickupMessage,
    PunchHitMessage,
    # CurseExplodeMessage,
    # BombDiedMessage,
)

# clone spaz, we'll need to call his original functions
# over 'super()' because python doesn't like us messing
# with code this way.
MyPlayerSpaz: Type[playerspaz.PlayerSpaz] = obj_clone(playerspaz.PlayerSpaz)
# self.spaz_class: Type[PlayerSpaz] = PlayerSpaz ??


# TODO: replace all unused 'statstrack' functions!
class PlayerSpaz(playerspaz.Spaz):
    """Wrapper for our PlayerSpaz class."""

    @override
    def __init__(self, *args, **kwargs):
        MyPlayerSpaz.__init__(
            self, *args, **kwargs
        )  # FIXME: troubleshoot this line?
        # Stat tracking variables
        self._has_landed_punch: bool = False
        self._has_landed_grab: bool = False
        # Manual grab timer as, even though the grab function
        # has a timer itself, it's not accounted in the input.
        self.last_grab_time: float = -99999

    def handle_messagestat(self, msg: Any) -> None:
        """Reward a stat from an event message."""
        # TODO: Clean up this garbo
        if not self.node:
            return

        if isinstance(msg, bs.DieMessage):
            # Sometimes, the game sends several death
            # messages, only count those that actually kill us.
            if self.is_alive():
                ''''''
            # clay.statstrack.add_stat('player_death', 1)

        elif isinstance(msg, bs.PowerupMessage):
            ''''''
        # clay.statstrack.add_stat('player_powerup', 1)

        elif isinstance(msg, PunchHitMessage):
            # Only award a stat point per singular hit.
            node = bs.getcollision().opposingnode
            if node and (node not in self._punched_nodes):
                # clay.statstrack.add_stat('player_punch', 1)
                # Reduce our punch misses counter if we haven't.
                if not self._has_landed_punch:
                    # clay.statstrack.add_stat('player_punch_bad', -1)
                    self._has_landed_punch = True

        elif isinstance(msg, PickupMessage):
            # Couple'o error handlers.
            try:
                collision = bs.getcollision()
                opposingnode = collision.opposingnode
                # opposingbody = collision.opposingbody
            except bs.NotFoundError:
                return
            try:
                if opposingnode.invincible:
                    return
            except Exception:
                pass
            # TODO: tracking is flimsy and can go into negatives, please polish
            # clay.statstrack.add_stat('player_grab', 1)
            # Reduce our grab misses counter if we haven't.
            if not self._has_landed_grab:
                # clay.statstrack.add_stat('player_grab_bad', -1)
                self._has_landed_grab = True

    @override
    def handlemessage(self, msg: Any) -> Any:
        # Track stats
        assert not self.expired
        self.handle_messagestat(msg)
        # Do standard handling
        return MyPlayerSpaz.handlemessage(self, msg)  # FIXME: huh


# Overwrite the vanilla game's spaz init with our own
obj_method_override(playerspaz.PlayerSpaz, PlayerSpaz)
