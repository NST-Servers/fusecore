"""Ready-up module.
Loads multiple modules and prepares them for usage.
"""

# pylint: disable=unused-import

# FIXME: some imports generate gc issues and the gc refuses to elaborate
# it's not an issue at all due to it only happening at
# launch, and the end user can't even see it happening
# unless they have garbage-gollection set to 'leak-debug'
# but holy folk is it super annoying...

import bascenev1 as bs
import babase

from fusecore._tools import (
    FuseToolsDevTab,
    add_devconsole_tab,
    obj_method_override,
)

from fusecore import (
    patcher as _,
    _modloader as _ml,
    discordrpc as _,
    serverqueue as sq,
    base as _,
    _cloudsafety as _,
    chat as _,
)


from .chat import (
    commands as _,
    stickers as _,
)
from ._language import ExternalLanguageSubsystem, reload_language


modloader = bs.app.register_subsystem(_ml.ModLoaderSubsystem())
serverqueue = bs.app.register_subsystem(sq.ServerQueueSubsystem())

add_devconsole_tab("Core Tools", FuseToolsDevTab)


# patch our language class and re-set our language to execute our changes.
obj_method_override(babase.LanguageSubsystem, ExternalLanguageSubsystem)
reload_language()
