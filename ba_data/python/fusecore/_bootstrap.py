"""Ready-up module.
Loads multiple modules and prepares them for usage.
"""

# load order is important!
# pylint: disable=wrong-import-order
# pylint: disable=wrong-import-position

import bascenev1 as bs
import babase

from fusecore._tools import (
    FuseToolsDevTab,
    add_devconsole_tab,
    obj_method_override,
)

from ._language import ExternalLanguageSubsystem, reload_language

# patch our language class and re-set our language to execute our changes.
obj_method_override(babase.LanguageSubsystem, ExternalLanguageSubsystem)
reload_language()

from fusecore import (
    common,
    _music,
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

from .chat import commands as _
from .chat.commands import general as _
from .chat import (
    stickers as _,
)


common.init_dirs()

_PreloadManager = _preload.AssetLoadManager()
config = _config.ConfigSystem()
stats = _stats.StatsSystem()
ServerQueue = bs.app.register_subsystem(serverqueue.ServerQueueSubsystem())
DiscordRPC = bs.app.register_subsystem(
    discordrpc.DiscordRichPresenceSubsystem()
)
ServerManager = server.FCServerManager()
ModLoader = _modloader.ModLoaderInstance

setmusic = _music.MusicActions.setmusic


add_devconsole_tab("FuseCore", FuseToolsDevTab)
