"""Core module; calls bootstrap, makes other modules more accessible
and does nothing else aside from asking for more info.
"""

import bascenev1 as bs

from . import (
    _bootstrap as _,
    _config,
    discordrpc,
)

DiscordRPC = bs.app.register_subsystem(
    discordrpc.DiscordRichPresenceSubsystem()
)
# DiscordRP.start()

config = _config.ConfigSystem()
