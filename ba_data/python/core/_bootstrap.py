"""Ready-up module.
Loads multiple modules and prepares them for usage.
"""

import bascenev1 as bs
import babase

from core._tools import obj_method_override

# misc. imports, possibly utilized by our '__init__' script
from core import (
    base,
    discordrp,
    _cloudsafety,
)

from core._tools import toolsTab, add_devconsole_tab

add_devconsole_tab('Core Tools', toolsTab)

from ._language import ExternalLanguageSubsystem, reload_language

# patch our language class and re-set our language to execute our changes.
obj_method_override(babase.LanguageSubsystem, ExternalLanguageSubsystem)
reload_language()
