"""Module to control custom config. sub-sections easily."""

import logging
from typing import Any

import bascenev1 as bs


def _log() -> logging.Logger:
    return logging.getLogger(__name__)


class ConfigSystem:
    """Config instance.

    Facilitates writing custom config. and account
    values using the provided 'section_name'.
    """

    section_name: str = "fusecore_cfg"

    def __repr__(self) -> str:
        """When printing this class, return our config. section instead."""
        return repr(bs.app.config.get(self.section_name, {}))

    def write(self, directory: str, value: Any) -> None:
        """Write to a specific directory within our config. dict.
        Applies and commit automatically.

        Args:
            directory (str): Dict path to store our information at.
            value (Any): Value to write to the target variable.

        Example:
            ,,write('foo.bar', 'my_val'),, will write to the config as
            bs.app.config[self.section_name]['foo']['bar'] = 'my_val'

        Raises:
            KeyError: The provided directory is not a valid path.
            Commonly happens when trying to access a directory that
            already has a value rather than a nested dict.
        """
        dir_subs = directory.split(".")

        bs.app.config.setdefault(self.section_name, {})
        root_path: dict = bs.app.config[self.section_name]

        active_path = root_path
        done_subs_str: str = ""

        for i, sub in enumerate(dir_subs[:-1]):
            done_subs_str += f".{sub}"
            _log().debug(
                'write: accessing "%s%s"', self.section_name, done_subs_str
            )
            # create a dict per sub in our directory, raise an error
            # if we're trying to create a dict on an active value.
            active_path.setdefault(sub, {})
            if not isinstance(active_path.get(sub, None), dict):
                raise KeyError(
                    f'Config path: "{".".join(list(dir_subs[:i+1]))}"'
                    "is not valid!\n"
                    f"config['{self.section_name}']"
                    f'{[f"[{key}]" for key in dir_subs[:i+1]]} = {active_path[sub]}\n\n'
                    f'Caused when trying to access "{sub}".'
                )
            active_path = active_path[sub]

        done_subs_str += f".{dir_subs[-1]}"
        # write to our final path.
        active_path[dir_subs[-1]] = value
        _log().info(
            'write: writing "%s" to "%s%s"',
            value,
            self.section_name,
            done_subs_str,
        )
        self._apply_and_commit()

    def fetch(
        self,
        directory: str,
        fallback: Any = None,
        create_if_missing: bool = False,
    ) -> Any:
        """Look for a specific path in our config. and return its value.

        Args:
            directory (str): Dict path to look our information for on.
            fallback (Any): Value provided if such variable doesn't exist.
            create_if_missing (bool): Create the path with our fallback value
            if it doesn't exist.

        Example:
            ,,fetch('foo.bar', None, True),, will attempt to get a value from
            bs.app.config[self.section_name]['foo']['bar'], or return
            'None' if it doesn't exist.
            If so, it will also create said path and set its value to 'None'.

        Raises:
            KeyError: The provided directory is not a valid path.
            Commonly happens when trying to access a directory that
            already has a value rather than a nested dict.

        Returns:
            Any: Value of the provided config. path, or our fallback value.
        """
        dir_subs = directory.split(".")

        bs.app.config.setdefault(self.section_name, {})
        root_path: dict = bs.app.config[self.section_name]

        active_path = root_path
        done_subs_str: str = ""

        for i, sub in enumerate(dir_subs[:-1]):
            done_subs_str += f".{sub}"
            _log().debug(
                'fetch: accessing "%s%s"', self.section_name, done_subs_str
            )
            # we also create dicts per sub to prevent ourselves from
            # crashing, and to set a value if we're told to do so.
            active_path.setdefault(sub, {})
            if not isinstance(active_path[sub], dict):
                raise KeyError(
                    f'Config path: "{".".join(list(dir_subs[:i+1]))}"'
                    "is not a valid subkey!\n\n"
                    f'Caused when trying to access "{sub}".'
                )
            active_path = active_path[sub]

        done_subs_str += f".{dir_subs[-1]}"
        # return & create the value, saving only if we we're assigned
        # to create data if there was none.
        to_sender = active_path.setdefault(dir_subs[-1], fallback)
        _log().info(
            'fetch: got "%s" from "%s%s"',
            to_sender,
            self.section_name,
            done_subs_str,
        )
        if create_if_missing:
            self._apply_and_commit()
        return to_sender  # parry.

    def write_to_account_v1(self, key: str, value: Any) -> None:
        """Write a value directly to our v1 account.

        Unlike config. values, these persist across devices, so this
        is more aimed towards story progression variables, or other
        stuff you might want to stick onto the user.

        Also, instead of storing this request into nested dicts, our
        requested name is conformed by our 'section_name' followed by
        the provided 'key', which means rather than a directory,
        it's an identifier for the value you want to write.
        Example:
            ,,write_to_account('foo.bar', 'my_val'),, will make
            a request to write to "{self.section_name}:foo.bar"

        Args:
            key (str): Identifier to store our information at.
            value (Any): Value to write to the target variable.
        """
        # NOTE: no clue what efro's plans for v1 are, but hopefully
        # this function won't be obsolete by the time v2 is fully out?
        assert bs.app.plus
        if not _is_v1_logged_in():
            _log().warning(
                "v1_write: couldn't write; not logged in.",
            )
            return

        bs.app.plus.add_v1_account_transaction(
            {
                "type": "SET_MISC_VAL",
                "name": f"{self.section_name}:{key}",
                "value": value,
            }
        )
        _log().info(
            'v1_write: writing "%s" to "%s:%s"', value, self.section_name, key
        )
        bs.app.plus.run_v1_account_transactions()

    def fetch_from_account_v1(
        self, key: str, fallback: Any = None, create_if_missing: bool = False
    ) -> Any:
        """Fetch a value directly from our v1 account.

        Unlike config. values, these persist across devices, so this
        is more aimed towards story progression variables, or other
        stuff you might want to stick onto the user.

        Args:
            key (str): Identifier to fetch our information from.
            value (Any): Value to write to the target variable.
            create_if_missing (bool): Create the key with our fallback value

        Returns:
            Any: Value of the provided account key, or our fallback.
            Retuns 'None' if we are not logged into a v1 account.
        """
        assert bs.app.plus
        if not _is_v1_logged_in():
            _log().warning(
                "v1_write: couldn't fetch; not logged in.",
            )
            return None

        v = bs.app.plus.get_v1_account_misc_val(
            f"{self.section_name}:{key}", fallback
        )
        _log().info(
            'v1_fetch: got "%s" from "%s:%s"', v, self.section_name, key
        )
        if create_if_missing:
            self.write_to_account_v1(key, fallback)
        return v

    def wipe_config_data(self) -> None:
        """Delete our entire config. root path.

        This **NUKES** all config. data, fully wiping
        any and all information that has been stored.
        Note that this doesn't remove data appended to the account
        via 'write_to_account_v1', as that is stored server-side.

        To confirm, you have to manually commit this change.

        Pretty spooky...
        """
        # scary!
        bs.app.config[self.section_name] = {}

    # bs.app.config 'forks'
    def _commit(self) -> None:
        bs.app.config.commit()

    def _apply(self) -> None:
        bs.app.config.apply()

    def _apply_and_commit(self) -> None:
        bs.app.config.apply_and_commit()


def _is_v1_logged_in() -> bool:
    return not (
        bs.app.plus is None or bs.app.plus.get_v1_account_state() != "signed_in"
    )
