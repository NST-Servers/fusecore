"""Modding utilities."""

from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any, Callable, Optional


def _log() -> logging.Logger:
    return logging.getLogger(__name__)


# TODO: better docstrings


class _WrapperInfo:
    def __init__(self) -> None:
        self.wrapped_funcs: dict[Callable, _WrapMain] = {}


WRAPPERINFO = _WrapperInfo()


def _safe_call(call: Callable, *a, **kw) -> Any:
    try:
        return call(*a, **kw)
    except Exception as err:
        _log().warning("wrapcall stack fail @ %s: %s", call, err, exc_info=True)
    return None


class WrapCallArgType(Enum):
    """Argument types for calls."""

    NONE = "none"
    """Requires no arguments."""

    DEFAULT = "default"
    """Requires all arguments from the main call."""

    MAIN = "main"
    """Requires the output of main as an argument.

    Calls with this arg. type need to be appended AFTER
    the main call, and main call needs to be enabled.
    """


@dataclass
class _WrapCall:
    call: Callable
    is_main: bool = False
    arg_type: WrapCallArgType = WrapCallArgType.DEFAULT


class _WrapMain:
    def __init__(self) -> None:
        self._calls: list[_WrapCall] = []
        self._main_call: Optional[Callable] = None
        self._main_enabled: bool = True
        self._returns: Any = None

    def _log_wrapcall(self, wrapcall: _WrapCall, *args, **kwargs) -> None:
        _log().debug(
            "%s: exec %s\nargs: %s\nkwargs: %s",
            self._main_call,
            wrapcall,
            args,
            kwargs,
        )

    def do_wrap_call(self, *args, **kwargs) -> Any:
        """Execute all calls attached to this `_WrapMain` in order."""
        _log().debug(
            "calling wrapmain for %s with stack: %s",
            self._main_call,
            self._calls,
        )
        last_output: Any = None
        main_output: Any = None
        _main_has_out = False

        for wrapcall in self._calls:

            if wrapcall.call is self._main_call:
                # ignore main if we've disabled it.
                if self._main_enabled:
                    self._log_wrapcall(wrapcall, args, kwargs)
                    main_output = _safe_call(wrapcall.call, *args, **kwargs)
                    _main_has_out = True
                else:
                    _log().debug("%s: ignoring main.", self._main_call)
                continue

            # run call
            match wrapcall.arg_type:

                case WrapCallArgType.NONE:
                    # no arguments
                    self._log_wrapcall(wrapcall)
                    last_output = _safe_call(wrapcall.call)

                case WrapCallArgType.MAIN:
                    if not _main_has_out:
                        # log a simple error if we're running a function that
                        # requires our main output, but is running before
                        # main is executed.
                        _log().warning(
                            'call %s has arg type "%s", but is'
                            " called before main call has executed.",
                            wrapcall.call,
                            wrapcall.arg_type,
                            exc_info=True,
                        )
                    self._log_wrapcall(wrapcall, main_output)
                    last_output = _safe_call(wrapcall.call, main_output)

                case _:
                    # use the same arguments from the main call
                    self._log_wrapcall(wrapcall, args, kwargs)
                    last_output = _safe_call(wrapcall.call, *args, **kwargs)

        _log().debug("%s: returning '%s'.", self._main_call, main_output)
        return main_output if _main_has_out else last_output

    def _main_is_init(self) -> bool:
        if self._main_call is None:
            return False
        return self._main_call.__name__ == "__init__"

    def register_main_call(self, call: Callable, is_enabled: bool) -> None:
        """Register a main call to this WrapMain."""
        if self._main_call is not None:
            raise KeyError("this _WrapMain already registered a main call.")

        self._main_call = call
        self._returns = call.__annotations__.get("return", None)
        self._main_enabled = is_enabled

        wcall = _WrapCall(call, is_main=True)
        self._calls.insert(0, wcall)

    def add_call(self, wrap_call: _WrapCall, index: Optional[int]) -> None:
        """Add a new call to this WrapMain's call tree."""
        if index:
            self._calls.insert(index, wrap_call)
        else:
            self._calls.append(wrap_call)


def _callwrap(wrapmain: _WrapMain) -> Callable:
    def wrapper(*args, **kwargs):
        return wrapmain.do_wrap_call(*args, **kwargs)

    return wrapper


def wrap_callable(
    src_call: Callable,
    wrap_call: Optional[Callable],
    *,
    call_arg_type: WrapCallArgType = WrapCallArgType.DEFAULT,
    index: Optional[int] = None,
    disable_src: bool = False,
) -> Callable:
    """Wrap a Callable with another function."""
    wrap_info = WRAPPERINFO.wrapped_funcs.get(src_call, None)

    if wrap_info is None:
        # if we don't have a wrapperinfo entry, create a wrapmain.
        wrapmain = _WrapMain()
        wrapmain.register_main_call(src_call, is_enabled=not disable_src)
        src_call = _callwrap(wrapmain)
        WRAPPERINFO.wrapped_funcs[src_call] = wrapmain
        wrap_info = wrapmain

    if wrap_call:
        wrap_info.add_call(_WrapCall(wrap_call, arg_type=call_arg_type), index)

    return src_call


def get_wrap_info(call: Callable) -> Optional[_WrapMain]:
    """Debug util: Get a WrapMain class from a wrapped callable."""
    return WRAPPERINFO.wrapped_funcs.get(call, None)
