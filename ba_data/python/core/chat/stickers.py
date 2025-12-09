from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Type

STICKER_ATLAS: set[Type[ChatSticker]] = set()
STICKER_DEFAULT: Type[ChatSticker] | None = None


class ChatSticker:
    name: str

    texture_name: str
    sound_name: str

    @classmethod
    def register(cls) -> None:
        """Add this sticker into our sticker pool for usage."""
        STICKER_ATLAS.add(cls)

    def on_usage(self) -> None:
        """Actions to perform when this sticker is used."""
