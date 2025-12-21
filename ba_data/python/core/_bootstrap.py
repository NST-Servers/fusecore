"""Ready-up module.
Loads multiple modules and prepares them for usage.
"""

# pylint: disable=unused-import

import bascenev1 as bs
import babase

from core._tools import toolsTab, add_devconsole_tab, obj_method_override

from core import (
    _modloader as _ml,
    serverqueue as sq,
    base as _,
    discordrp as _,
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

add_devconsole_tab('Core Tools', toolsTab)


# patch our language class and re-set our language to execute our changes.
obj_method_override(babase.LanguageSubsystem, ExternalLanguageSubsystem)
reload_language()
