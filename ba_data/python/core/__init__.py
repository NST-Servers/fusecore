"""Core module; calls bootstrap, makes other modules more accessible
and does nothing else aside from asking for more info.
"""

import bascenev1 as bs

from . import (
    _bootstrap as _,
    discordrp,
    _config,
)

DiscordRP = bs.app.register_subsystem(discordrp.DiscordRPSubsystem())
# DiscordRP.start()

config = _config.ConfigSystem()
