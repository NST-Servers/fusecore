"""Module to track player statistics."""

import time

import bascenev1 as bs

from fusecore._config import ConfigSystem

_config = ConfigSystem()

CONFIG_ENTRY = "stats"


class StatsSystem:
    """Subsystem to track player statistics."""

    def __init__(self) -> None:
        self._stats: dict = self.fetch_stats() or {}
        # FIXME: This is pretty flawed; if we were to log out and
        # logged into another account, not only would we not load
        # info from the new account, but we would overwrite all it's
        # data with our current stats.
        # Add checks to assure we retain stats consistent between accounts.
        bs.apptimer(4.0, self._fetch_acc_stats)
        self._account_fetch_timer: bs.AppTimer | None = bs.AppTimer(
            24.0, self._fetch_acc_stats
        )

    def stat_add(self, stat_name: str, value: int) -> None:
        """Perform an integer addition to a stat key."""
        self._stats.setdefault(stat_name, 0)
        self._stats[stat_name] += value
        self._generate_stat_timestamp(stat_name)

    def stat_set(self, stat_name: str, value: int) -> None:
        """Set a provided integer to a stat key."""
        self._stats[stat_name] = value
        self._generate_stat_timestamp(stat_name)

    def _generate_stat_timestamp(self, stat_name: str) -> None:
        self._stats.setdefault("timestamps", {})[stat_name] = time.time()

    def fetch_stats(self) -> dict | None:
        """Retrieve stats from config.
        Creates stats entry if it doesn't exist.
        """
        return _config.fetch("statistics", None)

    def save_stats(self) -> None:
        """Write statistics to our config. file."""
        _config.write("statistics", self._stats)

    def fetch_from_account(self) -> dict | None:
        """Retrieve stats from the user's account."""
        return _config.fetch_from_account_v1("statistics", None)

    def save_to_account(self) -> None:
        """Write statistics to the user's account."""
        _config.write_to_account_v1("statistics", self._stats)

    def _fetch_acc_stats(self) -> None:
        account_stats = self.fetch_from_account()

        if account_stats:
            self._account_fetch_timer = None
            # if we have both, compare timestamps and generate
            # a new dict with the latest stats info.
            for stat, acc_timestamp in account_stats.get(
                "timestamps", {}
            ).items():
                local_timestamp = self._stats.get("timestamps", {}).get(stat, 0)
                # if the account's timestamp is more recent, fetch it.
                if acc_timestamp > local_timestamp:
                    acc_stat = account_stats.get(stat, 0)
                    self._stats.get("timestamps", {})[stat] = acc_timestamp
                    self._stats[stat] = acc_stat
