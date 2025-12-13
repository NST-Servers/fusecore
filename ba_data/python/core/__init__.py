"""Core module; calls bootstrap, makes other modules more accessible
and does nothing else aside from asking for more info.
"""

from . import _bootstrap as _
from . import discordrp
from . import _config

DiscordRP = discordrp.DiscordRPSubsystem()
# DiscordRP.start()

config = _config.ConfigSystem()
