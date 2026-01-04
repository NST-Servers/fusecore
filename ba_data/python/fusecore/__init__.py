"""Core module; calls bootstrap, makes other modules more accessible
and does nothing else aside from asking for more info.
"""

import gc

import bascenev1 as bs

from . import common

from ._bootstrap import (
    _PreloadManager,
    ServerManager,
    DiscordRPC,
    ModLoader,
    ServerQueue,
    config,
)

# hot code above; ballistica's py gc funnel doesn't like that.
# specifically: some of our own packages and libraries get
# some references going, we gotta clean those to prevent errors.
gc.collect()
gc.garbage.clear()
