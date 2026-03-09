"""Miscelaneous classes appliable to any prop class
to indicate various custom statuses.
"""

from __future__ import annotations

from abc import abstractmethod
import logging
import time
from typing import Any, Optional, Type, TypeVar, override
import weakref

import bascenev1 as bs


class ObjectComponent:
    """A class defining a component.

    Any object that supports components can only have
    one of them at all times.
    """

    # NOTE: was thinking of standardizing component
    # initial calls, but its better to not do that
    # because of components taking unique parameters.
    # should reconsider with a fallback call, maybe?

    def __init__(self, parent: Any) -> None:
        if not isinstance(parent, ComponentReadyCls):
            # FIXME: use custom logging entry
            # and should probably not even allow this in
            # the first place...
            logging.warning(
                "Component instanced into class '%s', but it doesn't"
                " derivate from 'ComponentReadyCls'."
                " This might cause issues!\n"
                "To prepare a class for components, please make sure"
                " it iterates itself from 'ComponentReadyCls' too.",
                stack_info=True,
            )
        self._parent_ref: weakref.ref[Any] = weakref.ref(parent)
        self.creation_time = bs.time()
        self.creation_time_real = time.time()

    def get_parent(self) -> Any | None:
        """Return this component's parent."""
        return self._parent_ref()

    def remove(self) -> None:
        """Remove this component from it's parent."""
        _p = self.get_parent()
        if _p:
            assert isinstance(_p, ComponentReadyCls)
            _p.objcom_remove(type(self))

    def expire(self) -> None:
        """Remove this component from it's parent.

        Structually similar to `remove`, with the difference
        that no additional behavior should queue here and instead
        should immediately delete ourselves.
        """
        _p = self.get_parent()
        if _p:
            assert isinstance(_p, ComponentReadyCls)
            _p.objcom_remove(type(self))

    def dereference_parent(self) -> None:
        """Reference our parent.
        Don't call this unless we're cleaning up.
        """
        self._parent_ref = weakref.ref(None)


class ActorComponent(ObjectComponent):
    """An ObjectComponent designed to be used
    with `bs.Actor` classes.
    """

    ignore_dead: bool = True
    """Whether we don't apply ourselves into dead actors."""
    remove_on_actor_death: bool = True
    """Delete this component as soon as our parent dies?"""

    def __init__(self, parent: Any) -> None:
        super().__init__(parent)
        # don't apply ourselves onto death actors
        if not self._parent_exists() and self.ignore_dead:
            self._expire_hollow()

        self._is_active: bool = True
        self._remove_on_death_timer: Optional[bs.Timer] = None
        # keep track of our parent being alive and yoink ourselves
        # if they happen to die at some point.
        if self.remove_on_actor_death:
            self._remove_on_death_timer = bs.Timer(
                0.022, self.__remove_on_parent_death, repeat=True
            )

    def is_active(self) -> bool:
        """Returns if this component is still active."""
        return self._is_active

    @override
    def get_parent(self) -> bs.Actor | None:
        """Return this component's parent."""
        return self._parent_ref()

    @override
    def remove(self) -> None:
        self._is_active = False
        self._cleanup()
        return super().remove()

    @override
    def expire(self) -> None:
        self._is_active = False
        self._cleanup(instant=True)
        return super().expire()

    def _expire_hollow(self) -> None:
        # expiring before we even got the chance of existing!
        self._is_active = False
        self._remove_on_death_timer = None
        return super().expire()

    @abstractmethod
    def _cleanup(self, instant: bool = False) -> None:
        """Clean any variables that might be holding references.

        You're allowed to add fade-out animations to anything that
        might've been created by the component, unless `instant` is True.
        `instant` is passed whenever a cleanup is called when we expire.
        When this is the case, make sure to not create any further references.
        """
        self._remove_on_death_timer = None

    def _parent_exists(self) -> bool:
        _p = self.get_parent()
        if _p is None:
            return False

        return bool(
            _p.exists()
            and _p.is_alive()
            and not _p.expired
            and _p.node.exists()  # type: ignore
        )

    def __remove_on_parent_death(self) -> None:
        if not self._parent_exists():
            self._remove_on_death_timer = None
            self.remove()


T = TypeVar("T", bound=ObjectComponent)


class ComponentVault(dict[Type[T], T]):
    """A custom dict. subclass with component related functions."""

    def clear(self) -> None:
        for objc in self.values():
            objc.dereference_parent()
        return super().clear()


class ComponentReadyCls:
    """Subclass to prepare any other classes to receive components."""

    def __init__(self) -> None:
        self._components = ComponentVault()
        """Object components for this class."""

    def __init_subclass__(cls, **kwargs) -> None:
        # run our init as a subclass
        super().__init_subclass__(**kwargs)
        # only wrap if this class defines its own `__init__`
        if "__init__" in cls.__dict__:
            _init = cls.__init__

            def new_init(self, *args, **kwargs):
                ComponentReadyCls.__init__(self)
                _init(self, *args, **kwargs)

            cls.__init__ = new_init

        # wrap `on_expire` to reset components on quit
        # and prevent any held references
        if "on_expire" in cls.__dict__:
            _on_expire = cls.on_expire

            def new_on_expire(self) -> None:
                self.objcom_clear_components(immediate=True)
                _on_expire(self)

            cls.on_expire = new_on_expire

    def objcom_fetch(self, component: Type[T]) -> Optional[T]:
        """Return the specified component object, if any."""
        return self._components.get(component, None)

    def objcom_instance(self, component: Type[T]) -> T:
        """Apply a component to this object class.
        Returns the inserted component (or existing one.)
        """
        ex = self._components.get(component, None)
        if ex is not None:
            return ex
        n = component(self)
        self._components[component] = n
        return n

    def objcom_remove(self, component: Type[T]) -> bool:
        """Remove a component from this object class.
        Returns if we removed successfully or failed (likely due
        to this spaz not having said component.)
        """
        if self._components.get(component, None) is None:
            return False
        self._components.pop(component)
        return True

    def objcom_clear_components(self, immediate: bool = False) -> None:
        """Clears all components from this object."""
        for _c in list(self._components.values()):
            assert isinstance(_c, ObjectComponent)
            if immediate:
                _c.expire()
            else:
                _c.remove()

    def objcom_get_component_list(self) -> list[ObjectComponent]:
        """Returns the list of components this class currently has."""
        return list(self._components.values())


def inherit_components(
    src: ComponentReadyCls, to: ComponentReadyCls, additive: bool = True
) -> None:
    """Create all components from one instance to another.

    Note that this doesn't move any variables from the source
    components to the other, nor does it execute the component.
    This simply makes it so both classes have the same component list.

    If `additive` is True, the source components will be
    added to whatever components the target class already has.
    Otherwise, the target's component list will be wiped before
    the operation.
    """
    if not additive:
        # NOTE: could cause issues under specific circumstances.
        for _c in to.objcom_get_component_list():
            _c.remove()

    component_types = [type(c) for c in src.objcom_get_component_list()]
    _norep_components = [type(c) for c in to.objcom_get_component_list()]
    for _c in component_types:
        # don't re-instantiate any existing components.
        if _c in _norep_components:
            continue
        to.objcom_instance(_c)
