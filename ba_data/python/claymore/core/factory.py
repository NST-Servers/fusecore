"""
Module containing factories - classes that hold all sorts of data
shared in multiple parts of code and/or used often in runtime.
"""

from __future__ import annotations
from typing import Any, Dict, Callable, Self, Type

import bascenev1 as bs
from claymore._tools import send

FACTORY_ATLAS: dict[str, Dict[str, Any]] = {}
VERBOSE = False


class Empty:
    """
    Connotates pure nothingness.
    Prevents us from using "None" as reference that there's nothing defined.
    """


class Resource:
    """A factory resource."""

    def __init__(self, arg: str) -> None:
        self.call: Callable = lambda: None
        self.arg = arg

    def get(self) -> Any:
        return self.call(self.arg)


class FactoryTexture(Resource):
    """A texture factory resource."""

    def __init__(self, arg: str) -> None:
        super().__init__(arg)
        self.call = bs.gettexture


class FactoryMesh(Resource):
    """A mesh factory resource."""

    def __init__(self, arg: str) -> None:
        super().__init__(arg)
        self.call = bs.getmesh


class FactorySound(Resource):
    """A sound factory resource."""

    def __init__(self, arg: str) -> None:
        super().__init__(arg)
        self.call = bs.getsound


class Factory:
    """Collection of shared resources."""

    IDENTIFIER = 'default_factory'

    @classmethod
    def _get_factory_dict(cls) -> dict:
        """Get this factory's resource dict. from the factory atlas."""
        return FACTORY_ATLAS.get(cls.IDENTIFIER, {})

    @classmethod
    def does_resource_exists(cls, name: str) -> bool:
        """Return whether this resource's name already exists."""
        return not isinstance(cls._get_factory_dict().get(name, Empty()), Empty)

    @classmethod
    def register_resource(cls, name, res: Resource) -> None:
        """Register a resource class to this factory."""
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
        """Get/create a shared factory object."""
        activity: bs.Activity = bs.getactivity()
        factory = activity.customdata.get(cls.IDENTIFIER)
        if factory is None:
            factory = cls()
            activity.customdata[cls.IDENTIFIER] = factory
        assert isinstance(factory, cls)
        return factory

    @classmethod
    def is_running(cls) -> bool:
        """Return if an instance of this factory is available."""
        activity: bs.Activity | None = bs.get_foreground_host_activity()
        if not isinstance(activity, bs.Activity):
            return False
        return bool(activity.customdata.get(cls.IDENTIFIER, None))

    def __init__(self) -> None:
        """Transform our registered data into variables."""
        for name, res in self._get_factory_dict().items():
            send(f'"{self}" loading "{name}, {res}".', VERBOSE)
            setattr(
                self,
                name,
                # Load up if we're a resource, else, save raw
                self._load_resource(res) if isinstance(res, Resource) else res,
            )

    def _load_resource(self, res: Resource) -> Any:
        """Transform a resource into an active object."""
        result = res.arg
        # If our resource contains a callable, call and store
        if res.call:
            result = res.get()
        return result

    def fetch(self, name: str) -> Any:
        """Get a resource from this factory."""
        v = getattr(self, name, Empty)
        # Raise an exception if the variable doesn't exist.
        if v is Empty:  # Funny
            raise ValueError(f'"{name}" does not exist in "{self}".')
        send(f'Fetching "{name}" from "{self}".', VERBOSE)
        return v


class FactoryClass:
    """A class with factory-related functions bundled with it."""

    factory_class: Type[Factory]
    groupset: set | None = None

    @classmethod
    def _register_resources(cls) -> None:
        """Register resources used by this actor."""
        ls = cls.resources() or {}
        for name, resource in ls.items():
            cls.factory_class.register_resource(name, resource)

    @classmethod
    def register(cls) -> None:
        """Register this actor's resources and sign them up to their group."""
        if not (isinstance(cls.groupset, set) or cls.groupset is None):
            raise TypeError('"groupset" only accepts set() or "None".')
        # Add our resources and append to our group list.
        send(
            f'Registering "{cls.__qualname__}"'
            f' with factory "{cls.factory_class}"'
            f' ({"contains" if cls.groupset is not None else "no"} group)',
            VERBOSE,
        )
        cls._register_resources()
        if cls.groupset is not None:
            cls.groupset.add(cls)

    @staticmethod
    def resources() -> dict:
        """Get a dict with resources."""
        return {}

    def __init__(self) -> None:
        """Instance our factory."""
        super().__init__()
        self.factory: Factory | Any = self.factory_class.instance()


class FactoryActor(FactoryClass, bs.Actor):
    """A bs.Actor with factory-related functions bundled with it."""
