"""Ready-up module.
Loads multiple modules and prepares them for usage.
"""

import bascenev1 as bs
import babase

from claymore._tools import obj_method_override

# misc. imports, possibly utilized by our '__init__' script
from claymore import (
    core,
    discordrp,
)

from claymore._language import ExternalLanguageSubsystem

# patch our language class and re-set our language to execute our changes.
obj_method_override(babase.LanguageSubsystem, ExternalLanguageSubsystem)
bs.app.lang.setlanguage(
    bs.app.lang.language,
    print_change=True,
    store_to_config=False,
    ignore_redundant=False,
)
