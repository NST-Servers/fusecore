from __future__ import annotations

import os
import logging
import json
from typing import override

import bascenev1 as bs
import _babase  # type: ignore
from babase._language import (
    LanguageSubsystem,
    Lstr,
    AttrDict,
    _add_to_attr_dict,
)
from babase._logging import applog

from claymore.common import DATA_DIRECTORY

LANG_DIRECTORY = os.path.join(DATA_DIRECTORY, 'lang')


def _log() -> logging.Logger:
    return logging.getLogger(__name__)


def get_custom_language_files_list(language: str) -> list:
    """Fetch our custom '.json' language files via language name."""
    path = os.path.join(LANG_DIRECTORY, language)

    if not os.path.exists(path):
        _log().info(
            "Provided language does not have a lang folder!\n"
            f"({language} @ '{path}')\n"
            f"Support for this language is limited and will fallback to English."
        )
        return []

    return os.listdir(path)


class ExternalLanguageSubsystem(LanguageSubsystem):
    """A patch improvement to 'LanguageSubsystem'.

    Allows us to load multiple '.json' files assigned
    to a language and stack its language data to it.
    """

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

        with open(
            os.path.join(
                _babase.app.env.data_directory,
                'ba_data',
                'data',
                'languages',
                'english.json',
            ),
            encoding='utf-8',
        ) as infile:
            lenglishvalues = json.loads(infile.read())

        # import our custom json files
        for langfile in get_custom_language_files_list('english'):
            path = os.path.join(LANG_DIRECTORY, 'english', langfile)
            with open(path) as langfile:
                out = json.loads(langfile.read())
                lenglishvalues.update(out)

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
                    with open(lmodfile, encoding='utf-8') as infile:
                        lmodvalues = json.loads(infile.read())

                    malformed_note: bool = False
                    # import our custom json files
                    langpath = os.path.join(LANG_DIRECTORY, language.lower())
                    for langfile in get_custom_language_files_list(
                        language.lower()
                    ):
                        try:
                            path = os.path.join(langpath, langfile)
                            with open(path) as langfile:
                                out = json.loads(langfile.read())
                                lmodvalues.update(out)
                        except json.JSONDecodeError:  # skip malformed files
                            warning_text = (
                                f"Malformed '.json' file @ '{langfile.name}'"
                            )
                            if not malformed_note:
                                warning_text += "\nThis language's compatibility will be greatly reduced until this is fixed."
                                malformed_note = True
                            _log().warning(warning_text)
                            continue

            except Exception:
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

        # Create an attrdict of our target language overlaid on our base
        # (english).
        languages = [lenglishvalues]
        if lmodvalues is not None:
            languages.append(lmodvalues)
        lfull = AttrDict()
        for lmod in languages:
            _add_to_attr_dict(lfull, lmod)
        self._language_merged = lfull

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
