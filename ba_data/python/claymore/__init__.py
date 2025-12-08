# append ourselves @ file:///./../bascenev1lib/__init__.py
# TODO: ^ i dont like that, we should have a way
#         for core to load us automatically.
import os

from .common import DATA_DIRECTORY

from core import _language

# append our language dir and reload lang to apply changes
_language.LANG_FOLDERS.append(
    os.path.join(
        DATA_DIRECTORY,
        'lang',
    )
)
_language.reload_language()
