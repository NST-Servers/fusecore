"""DeathType."""

from abc import abstractmethod
from dataclasses import dataclass

import bascenev1 as bs

# NOTE: do better docstrings?


@dataclass
class DeathType:
    """Custom FuseCore DeathType.

    Controls general behavior, like the message on death and
    additional functions after the deathtype is called.
    """

    name: str
    """Name to reference this DeathType by."""
    death_text: bs.Lstr | str | None = None
    """Message displayed when dying with this death type.
    
    `None` by default. Will display a generic
    death message if not provided.
    """

    @abstractmethod
    def on_trigger_call(self) -> None:
        """Action to perform when this DeathType is triggered.

        Note that this is only called when an actor dies while
        referencing this type, not to the act of receiving the message.
        """


def handle_death_type(dt: DeathType) -> None: ...
