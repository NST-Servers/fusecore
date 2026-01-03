"""Core module; calls bootstrap, makes other modules more accessible
and does nothing else aside from asking for more info.
"""

import gc

import bascenev1 as bs

from . import (
    common,
    _bootstrap as _,
    _config,
    discordrpc,
)

# hot code above; ballistica's py gc funnel doesn't like that.
# specifically: some of our own packages and libraries get
# some references going, we gotta clean those to prevent errors.
gc.collect()

common.init_dirs()

DiscordRPC = bs.app.register_subsystem(
    discordrpc.DiscordRichPresenceSubsystem()
)
# DiscordRP.start()

config = _config.ConfigSystem()
