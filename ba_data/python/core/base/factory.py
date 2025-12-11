"""Module containing factories -- classes that hold all sorts of data
shared in multiple parts of code and/or used often in runtime.
"""

from __future__ import annotations
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Callable, Self, Type

import logging

import bascenev1 as bs

FACTORY_ATLAS: dict[str, Dict[str, Any]] = {}
VERBOSE = False


@dataclass
class Empty:
    """Connotates emptiness.
    Used as a placeholder for typechecking if 'None' is an acceptable outcome.
    """


def _log() -> logging.Logger:
    return logging.getLogger(__name__)


class Resource:
    """Resource instanced to be stored in a factory."""

    _call: Callable | None = None

    def __init__(self, *args) -> None:
        self._args: tuple[Any, ...] = args

    def get(self) -> Any:
        """Return our executed call."""
        if self._call is not None:
            return self._call(*self._args)
        if len(self._args) > 1:
            return self._args
        if len(self._args) == 1:
            return self._args[0]
        return None


class FactoryTexture(Resource):
    """A texture-type factory resource."""

    _call = bs.gettexture

    def __init__(self, texture_name: str) -> None:
        super().__init__(texture_name)


class FactoryMesh(Resource):
    """A mesh-type factory resource."""

    _call = bs.getmesh

    def __init__(self, mesh_name: str) -> None:
        super().__init__(mesh_name)


class FactorySound(Resource):
    """A sound-type factory resource."""

    _call = bs.getsound

    def __init__(self, sound_name: str) -> None:
        super().__init__(sound_name)


class Factory:
    """A collection of instanced resources.

    This class stores multiple 'Resource' classes within, which
    contain references to assets that are to be used multiple times
    with the purpose of decreasing memory usage and have cleaner
    game performance by having a single pointer to every asset needed.
    """

    IDENTIFIER: str = 'default_factory'
    """Unique identifier for this factory.
    
    Any object to use a factory will require this
    identifier to access it effectively.
    """

    @classmethod
    def _get_factory_dict(cls) -> dict:
        """Return this factory's asset dict."""
        return FACTORY_ATLAS.get(cls.IDENTIFIER, {})

    @classmethod
    def does_resource_exists(cls, name: str) -> bool:
        """Return whether this resource's name already exists."""
        return not isinstance(cls._get_factory_dict().get(name, Empty()), Empty)

    @classmethod
    def register_resource(cls, name, res: Resource) -> None:
        """Append a resource to this factory."""
        _log().debug(
            'Creating attribute "%s" in "%s" via "%s"%s.',
            name,
            cls,
            res,
            ' as overwrite' if cls.does_resource_exists(name) else '',
        )
        FACTORY_ATLAS.setdefault(cls.IDENTIFIER, {})[name] = res
        # If we have an active instance, immediately load this resource
        if cls.is_running():
            instance = cls.instance()
            print(cls)
            print(instance)
            setattr(instance, name, instance.load_resource(res))

    @classmethod
    def instance(cls) -> Self:
        """Instantiate this factory to be used.

        This will create a factory object to the active session or
        return an already active object if it has been created already.
        """
        activity: bs.Activity = bs.getactivity()
        factory = activity.customdata.get(cls.IDENTIFIER)
        if factory is None:
            factory = cls()
            activity.customdata[cls.IDENTIFIER] = factory
        assert isinstance(factory, cls)
        return factory

    @classmethod
    def is_running(cls) -> bool:
        """Return whether this factory has been instanced already."""
        activity: bs.Activity | None = bs.get_foreground_host_activity()
        if not isinstance(activity, bs.Activity):
            return False
        return bool(activity.customdata.get(cls.IDENTIFIER, None))

    def __init__(self) -> None:
        """Prepare this factory; convert all our resource
        references into object pointers for usage.
        """
        for name, res in self._get_factory_dict().items():
            _log().debug('"%s" preparing "%s, %s".', self, name, res)
            setattr(
                self,
                name,
                (
                    self.load_resource(res)
                    if isinstance(res, Resource)
                    # if we're preparing a non-resource, store it's raw input
                    else res
                ),
            )

    def load_resource(self, res: Resource) -> Any:
        """'Activate' the resource provided for usage."""
        # resources with an assigned call (eg. Textures
        # with 'bs.gettexture', meshes with 'bs.getmesh'...)
        # are to be processed before returning their pointer.
        return res.get()

    def fetch(self, name: str) -> Any:
        """Get a resource from this factory."""
        v: Empty | Any = getattr(self, name, Empty)
        if v is Empty:  # fetched resource doesn't exist...
            raise ValueError(f'"{name}" does not exist in "{self}".')

        _log().debug('Fetching "%s" from "%s".', name, self)
        return v


class FactoryClass:
    """A generic class with factory-related functions bundled with it."""

    my_factory: Type[Factory]
    """Factory used by this FactoryClass instance."""
    group_set: set | None = None
    """Set to register this FactoryClass under."""

    @classmethod
    def register_resources(cls) -> None:
        """Register resources used by this actor."""
        ls = cls.resources() or {}
        for name, resource in ls.items():
            cls.my_factory.register_resource(name, resource)

    @classmethod
    def register(cls) -> None:
        """Register this actor's resources and sign them up to their group."""
        if not (isinstance(cls.group_set, set) or cls.group_set is None):
            raise TypeError(
                f"invalid groupset:{cls.group_set}\nshould be 'set' or 'None'."
            )
        # Add our resources and append to our group list.
        _log().debug(
            'Registering "%s" with factory "%s" %s',
            {cls.__qualname__},
            {cls.my_factory},
            'with group' if cls.group_set is not None else 'no group',
        )
        cls.register_resources()
        if cls.group_set is not None:
            cls.group_set.add(cls)

    @staticmethod
    def resources() -> dict:
        """
        Register resources used by this class.

        Due to how mesh, sound, texture calls are handled,
        you'll need to use FactoryMesh, FactorySound and
        FactoryTexture respectively for the factory to be
        able to call assets in runtime properly.
        """
        return {}

    def __init__(self) -> None:
        """Instance our factory."""
        self.factory: Factory | Any = self.my_factory.instance()
        super().__init__()  # for multi-inheritance subclasses


class FactoryActor(FactoryClass, bs.Actor):
    """A 'bs.Actor' inheriting from 'FactoryClass' and its functions."""

    @staticmethod
    def resources() -> dict:
        return {}
