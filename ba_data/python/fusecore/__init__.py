"""Core module; calls bootstrap, makes other modules more accessible
and does nothing else aside from asking for more info.
"""

import gc

import bascenev1 as bs

from . import (
    common,
    _preload as pre,
    _bootstrap as boots,
    _modloader,
    serverqueue,
    _config,
    discordrpc,
    server,
)

# hot code above; ballistica's py gc funnel doesn't like that.
# specifically: some of our own packages and libraries get
# some references going, we gotta clean those to prevent errors.
gc.collect()

common.init_dirs()

ServerManager = server.FCServerManager()
DiscordRPC = bs.app.register_subsystem(
    discordrpc.DiscordRichPresenceSubsystem()
)
ModLoader = bs.app.register_subsystem(_modloader.ModLoaderSubsystem())
ServerQueue = bs.app.register_subsystem(serverqueue.ServerQueueSubsystem())


config = _config.ConfigSystem()
