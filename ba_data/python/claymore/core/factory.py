"""
Module containing factories - classes that hold all sorts of data
shared in multiple parts of code and/or used often in runtime.
"""

from __future__ import annotations
from abc import abstractmethod
from typing import Any, Dict, Callable, Self, Type

import bascenev1 as bs
from claymore._tools import send

FACTORY_ATLAS: dict[str, Dict[str, Any]] = {}
VERBOSE = False


class Empty:
    """Connotates emptiness. Used as a placeholder for typechecking if 'None' is an acceptable outcome."""


class Resource:
    """Resource instanced to be stored in a factory."""

    def __init__(self, arg: str) -> None:
        self.call: Callable = lambda: None
        self.arg = arg

    def get(self) -> Any:
        return self.call(self.arg)


class FactoryTexture(Resource):
    """A texture-type factory resource."""

    def __init__(self, arg: str) -> None:
        super().__init__(arg)
        self.call = bs.gettexture


class FactoryMesh(Resource):
    """A mesh-type factory resource."""

    def __init__(self, arg: str) -> None:
        super().__init__(arg)
        self.call = bs.getmesh


class FactorySound(Resource):
    """A sound-type factory resource."""

    def __init__(self, arg: str) -> None:
        super().__init__(arg)
        self.call = bs.getsound


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
        send(
            f'Creating attribute "{name}" in "{cls}" via "{res}".'
            f'{" (overwrite)" if cls.does_resource_exists(name) else ""}',
            VERBOSE,
        )
        FACTORY_ATLAS.setdefault(cls.IDENTIFIER, {})[name] = res
        # If we have an active instance, immediately load this resource
        if cls.is_running():
            instance = cls.instance()
            print(cls)
            print(instance)
            setattr(instance, name, instance._load_resource(res))

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
            send(f'"{self}" preparing "{name}, {res}".', VERBOSE)
            setattr(
                self,
                name,
                (
                    self._load_resource(res)
                    if isinstance(res, Resource)
                    # if we're preparing a non-resource, store it's raw input
                    else res
                ),
            )

    def _load_resource(self, res: Resource) -> Any:
        """'Activate' the resource provided for usage."""
        result = res.arg
        # resources with an assigned call (eg. Textures
        # with 'bs.gettexture', meshes with 'bs.getmesh'...)
        # are to be processed before returning their pointer.
        if res.call:
            try:
                result = res.get()
            except Exception as exc:
                send(f'An error occurred: {exc}', VERBOSE)
                return None
        return result

    def fetch(self, name: str) -> Any:
        """Get a resource from this factory."""
        v: Empty | Any = getattr(self, name, Empty)
        if v is Empty:  # fetched resource doesn't exist...
            raise ValueError(f'"{name}" does not exist in "{self}".')

        send(f'Fetching "{name}" from "{self}".', VERBOSE)
        return v


class FactoryClass:
    """A generic class with factory-related functions bundled with it."""

    my_factory: Type[Factory]
    """Factory used by this FactoryClass instance."""
    group_set: set | None = None
    """Set to register this FactoryClass under."""

    @classmethod
    def _register_resources(cls) -> None:
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
        send(
            f'Registering "{cls.__qualname__}"'
            f' with factory "{cls.my_factory}"'
            f' ({"contains" if cls.group_set is not None else "no"} group)',
            VERBOSE,
        )
        cls._register_resources()
        if cls.group_set is not None:
            cls.group_set.add(cls)

    @staticmethod
    @abstractmethod
    def resources() -> dict:
        """
        Register resources used by this class.

        Due to how mesh, sound, texture calls are handled,
        you'll need to use FactoryMesh, FactorySound and
        FactoryTexture respectively for the factory to be
        able to call assets in runtime properly.
        """
        # function has to be overriden by subclasses.

    def __init__(self) -> None:
        """Instance our factory."""
        self.factory: Factory | Any = self.my_factory.instance()
        super().__init__()  # for multi-inheritance subclasses


class FactoryActor(FactoryClass, bs.Actor):
    """A 'bs.Actor' inheriting from 'FactoryClass' and its functions."""
