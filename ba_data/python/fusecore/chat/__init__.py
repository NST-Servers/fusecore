"""Chat interceptors allowing for message reading and function executing."""

from __future__ import annotations

from abc import abstractmethod
from typing import Type

CHAT_INTERCEPTS_SET: list[Type[ChatIntercept]] = []


class ChatIntercept:
    """Chat interception that does nifty stuff."""

    @classmethod
    def register(cls, idx: int | None = None) -> None:
        """Register this class into our intercepts set."""
        if idx:
            CHAT_INTERCEPTS_SET.insert(idx, cls)
        else:
            CHAT_INTERCEPTS_SET.append(cls)

    @abstractmethod
    def intercept(self, msg: str, client_id: int) -> bool:
        """returns whether we want to deliver this message."""
        raise RuntimeError("'intercept()' function has to be overriden.")


def chat_message_intercept(msg: str, client_id: int) -> str | None:
    """Chat message function interception to read sent
    messages and run whatever functions and code we want.
    """
    for intercept in CHAT_INTERCEPTS_SET:
        if not intercept().intercept(msg, client_id):
            return None

    return msg
