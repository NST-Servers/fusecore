"""Miscelaneous classes appliable to any prop class
to indicate various custom statuses.
"""

import time
from typing import Any, Type, TypeVar

import bascenev1 as bs


class ObjectComponent:
    """A class defining a component.

    Any object that supports components can only have
    one of them at all times.
    """

    def __init__(self, parent: Any) -> None:
        self.parent = parent
        self.creation_time = bs.time()
        self.creation_time_real = time.time()

    def dereference_parent(self) -> None:
        """Reference our parent.
        Don't call this unless we're cleaning up.
        """
        self.parent = None


T = TypeVar("T", bound=ObjectComponent)


class ComponentVault(dict[Type[T], T]):
    """A custom dict. subclass with component related functions."""

    def clear(self) -> None:
        for objc in self.values():
            objc.dereference_parent()
        return super().clear()


def is_class_component_ready(cls: classmethod) -> bool:
    """Returns whether the provided class supports components."""
    i = 0
    must_have = [
        "_components",
        "component_get",
        "component_add",
        "component_remove",
    ]
    for v in must_have:
        if hasattr(cls, v):
            i += 1
    return i >= len(must_have)
