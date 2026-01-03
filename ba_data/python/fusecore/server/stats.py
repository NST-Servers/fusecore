"""Statistics tracking into a database using SQLite."""

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import time
from typing import Any, Literal, Union

from efro.dataclassio._api import dataclass_from_json
from fusecore._tools import is_server


@dataclass
class UserModel:
    """User entry in our database."""

    id: str
    username: str
    created_at: int
    last_seen: int = -1


class StatsTracker:
    """Track user's stats."""

    def __init__(self, dbpath: Union[Path, Literal[":memory:"]]) -> None:
        print("stats tracker initiated!")
        self._db = sqlite3.connect(dbpath)
        self.c = self._db.cursor()

        self.create_tables()
        # when not running in a server environment, register
        # ourselves into our own database to keep track of our moves.
        if is_server() is False:
            self.register_user(
                UserModel(
                    id="pb-ND0oS0VbA0ZAXl5EDRQDUlVfEUEKQEwSVVQWRlVLSA5fFEJDUwBXEQ==",
                    username="temp",
                    created_at=time.time_ns(),
                    last_seen=time.time_ns(),
                )
            )

    def create_tables(self) -> None:
        """Initialize all tables for this database."""
        with self._db:
            self.c.execute(
                """
                    CREATE TABLE IF NOT EXISTS users (
                      id TEXT PRIMARY KEY,
                      username TEXT NOT NULL,
                      created_at INTEGER NOT NULL,
                      last_seen INTEGER
                    );
                """
            )

    def register_user(self, user: UserModel) -> None:
        """Register a user on our user table.
        We require of this entry to allow linking tracked stats
        to a specific user.
        """
        with self._db:
            self.c.execute(
                """
                    INSERT INTO users (id, username, created_at, last_seen) VALUES
                    (:id, :name, :created_at, :last_seen);
                """,
                {
                    "id": user.id,
                    "name": user.username,
                    "created_at": user.created_at,
                    "last_seen": user.last_seen,
                },
            )

    def reset_stats(self) -> None:
        """v"""

    def get_table(self, table: str) -> list[Any]:
        self.c.execute("SELECT * FROM users;")
        return self.c.fetchall()
