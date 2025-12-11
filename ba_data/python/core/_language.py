"""Custom language manager for easier langfile entry insertion."""

from __future__ import annotations

import os
import logging
import json
from typing import Any, override

import bascenev1 as bs
import _babase  # type: ignore # pylint: disable=import-error
from babase._language import (
    LanguageSubsystem,
    Lstr,
    AttrDict,
    _add_to_attr_dict,
)
from babase._logging import applog

from core.common import DATA_DIRECTORY

LANG_FOLDERS: list[str] = [
    os.path.join(DATA_DIRECTORY, 'lang'),
]


def _log() -> logging.Logger:
    return logging.getLogger(__name__)


class ExternalLanguageSubsystem(LanguageSubsystem):
    """A patch improvement to 'LanguageSubsystem'.

    Allows us to load multiple '.json' files assigned
    to a language and stack its language data to it.
    """

    def _get_custom_language_files_list(
        self, folder_path: str, language: str
    ) -> list:
        """Fetch our custom '.json' language files via language name."""
        if not os.path.exists(folder_path):
            _log().warning(
                "Provided folder path does not exist!\n'%s'", folder_path
            )
            return []

        path = os.path.join(folder_path, language)

        if not os.path.exists(path):
            _log().info(
                "Provided language does not have a lang folder!\n"
                "(%s @ '%s')\n"
                "Support for this language is limited and will fallback to English.",
                language,
                path,
            )
            return []

        return os.listdir(path)

    def read_language_file(self, file_path: str) -> dict | Any:
        """Load a '.json' language file.
        Returns output, usually desired to be a dict.
        """
        with open(file_path, encoding='utf-8') as infile:
            return json.loads(infile.read())

    def read_custom_language_files(
        self, lang_folder_path: list | str, language: str
    ) -> list[dict | Any]:
        """Read custom '.json' files from a language folder.

        'lang_folder_path' should contain a subfolder named as the provided language, and
        said subfolder should contain '.json' files to be scanned.

        Returns output, usually desired to be a list containing dicts only.
        """
        outcome: list[Any] = []

        if isinstance(lang_folder_path, str):
            lang_folder_path = [lang_folder_path]

        for folder in lang_folder_path:
            for langfile in self._get_custom_language_files_list(
                folder, language
            ):
                path = os.path.join(folder, language, langfile)
                with open(path, encoding='utf-8') as langfile:
                    out: Any = {}
                    try:
                        out = json.loads(langfile.read())
                        outcome.append(out)
                    except json.JSONDecodeError:
                        # in case the json is malformed or empty, we don't want
                        # to halt loading our other jsons, so log and dismiss it
                        warning_text = (
                            f"Malformed '.json' file @ '{langfile.name}'"
                        )
                        _log().warning(warning_text)
                        # NOTE: we should keep track of the files do and dont load...
                        continue
        return outcome

    @override
    def setlanguage(
        self,
        language: str | dict,
        *,
        print_change: bool = True,
        store_to_config: bool = True,
        ignore_redundant: bool = False,
    ) -> None:
        """Set the active app language.

        Note that this only applies to the legacy language system and
        should not be used directly these days.
        """

        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements
        assert _babase.in_logic_thread()

        cfg = _babase.app.config
        cur_language = cfg.get('Lang', None)

        if ignore_redundant and language == self._language:
            return

        english_langfile_path = os.path.join(
            _babase.app.env.data_directory,
            'ba_data',
            'data',
            'languages',
            'english.json',
        )
        # import our language data
        lenglishvalues = self.read_language_file(english_langfile_path)
        lenglishcoutput = self.read_custom_language_files(
            LANG_FOLDERS, 'english'
        )
        lmodcoutput = []

        # Special case - passing a complete dict for testing.
        if isinstance(language, dict):
            self._language = 'Custom'
            lmodvalues = language
            switched = False
            print_change = False
            store_to_config = False
        else:
            # Ok, we're setting a real language.

            # Store this in the config if its changing.
            if language != cur_language and store_to_config:
                # if language is None:
                #     if 'Lang' in cfg:
                #         del cfg['Lang']  # Clear it out for default.
                # else:
                cfg['Lang'] = language
                cfg.commit()
                switched = True
            else:
                switched = False

            # None implies default.
            # if language is None:
            #     language = self.default_language
            try:
                if language == 'English':
                    lmodvalues = None
                else:
                    lmodfile = os.path.join(
                        _babase.app.env.data_directory,
                        'ba_data',
                        'data',
                        'languages',
                        language.lower() + '.json',
                    )
                    lmodvalues = self.read_language_file(lmodfile)

                    lmodcoutput = self.read_custom_language_files(
                        LANG_FOLDERS,
                        language.lower(),
                    )

            except Exception:  # pylint: disable=broad-exception-caught
                applog.exception("Error importing language '%s'.", language)
                _babase.screenmessage(
                    f"Error setting language to '{language}';"
                    f' see log for details.',
                    color=(1, 0, 0),
                )
                switched = False
                lmodvalues = None

            self._language = language

        # Create an attrdict of *just* our target language.
        self._language_target = AttrDict()
        langtarget = self._language_target
        assert langtarget is not None
        _add_to_attr_dict(
            langtarget, lmodvalues if lmodvalues is not None else lenglishvalues
        )
        # our customs!
        for v in lmodcoutput:
            _add_to_attr_dict(langtarget, v)

        # Create an attrdict of our target language overlaid on our base
        # (english).
        languages = [lenglishvalues]
        if lmodvalues is not None:
            languages.append(lmodvalues)
        lfull = AttrDict()
        for lmod in languages:
            _add_to_attr_dict(lfull, lmod)
        self._language_merged = lfull
        # our customs!
        for v in lenglishcoutput:
            _add_to_attr_dict(lfull, v)

        # Pass some keys/values in for low level code to use; start with
        # everything in their 'internal' section.
        internal_vals = [
            v for v in list(lfull['internal'].items()) if isinstance(v[1], str)
        ]

        # Cherry-pick various other values to include.
        # (should probably get rid of the 'internal' section
        # and do everything this way)
        for value in [
            'replayNameDefaultText',
            'replayWriteErrorText',
            'replayVersionErrorText',
            'replayReadErrorText',
        ]:
            internal_vals.append((value, lfull[value]))
        internal_vals.append(
            ('axisText', lfull['configGamepadWindow']['axisText'])
        )
        internal_vals.append(('buttonText', lfull['buttonText']))
        lmerged = self._language_merged
        assert lmerged is not None
        random_names = [
            n.strip() for n in lmerged['randomPlayerNamesText'].split(',')
        ]
        random_names = [n for n in random_names if n != '']
        _babase.set_internal_language_keys(internal_vals, random_names)

        if switched and print_change:
            assert isinstance(language, str)
            _babase.screenmessage(
                Lstr(
                    resource='languageSetText',
                    subs=[
                        ('${LANGUAGE}', Lstr(translate=('languages', language)))
                    ],
                ),
                color=(0, 1, 0),
            )


def reload_language() -> None:
    """Reloads the active language."""
    bs.app.lang.setlanguage(
        bs.app.lang.language,
        print_change=False,
        store_to_config=False,
        ignore_redundant=False,
    )
