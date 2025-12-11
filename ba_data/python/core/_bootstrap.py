"""Ready-up module.
Loads multiple modules and prepares them for usage.
"""

# pylint: disable=unused-import

import bascenev1 as bs
import babase

from core._tools import toolsTab, add_devconsole_tab, obj_method_override

from core import (
    base,
    discordrp,
    _cloudsafety,
)

from . import chat as _
from .chat import (
    commands as _,
    stickers as _,
)
from ._language import ExternalLanguageSubsystem, reload_language


add_devconsole_tab('Core Tools', toolsTab)


# patch our language class and re-set our language to execute our changes.
obj_method_override(babase.LanguageSubsystem, ExternalLanguageSubsystem)
reload_language()
