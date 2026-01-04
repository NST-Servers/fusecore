"""Ready-up module.
Loads multiple modules and prepares them for usage.
"""

import bascenev1 as bs
import babase

from fusecore._tools import (
    FuseToolsDevTab,
    add_devconsole_tab,
    obj_method_override,
)

# load order is important!
from fusecore import (
    common,
    _preload,
    _config,
    _stats,
    patcher as _,
    _cloudsafety as _,
    base as _,
    chat as _,
    serverqueue,
    discordrpc,
    server,
    _modloader,
)
from .chat import (
    commands as _,
    stickers as _,
)

from ._language import ExternalLanguageSubsystem, reload_language

common.init_dirs()

_PreloadManager = _preload.AssetLoadManager()
config = _config.ConfigSystem()
stats = _stats.StatsSystem()
ServerQueue = bs.app.register_subsystem(serverqueue.ServerQueueSubsystem())
DiscordRPC = bs.app.register_subsystem(
    discordrpc.DiscordRichPresenceSubsystem()
)
ServerManager = server.FCServerManager()
ModLoader = bs.app.register_subsystem(_modloader.ModLoaderSubsystem())


add_devconsole_tab("Core Tools", FuseToolsDevTab)
# patch our language class and re-set our language to execute our changes.
obj_method_override(babase.LanguageSubsystem, ExternalLanguageSubsystem)
reload_language()
