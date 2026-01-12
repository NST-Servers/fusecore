"""In-game commands executable via 'ChatIntercept'."""

from __future__ import annotations

from typing import Any, Callable, Type, override
import logging

import bascenev1 as bs

from fusecore.chat import ChatIntercept
from fusecore.chat.perms import is_admin_from_client_id
from fusecore.chat.utils import (
    broadcast_message_to_client,
    are_we_host,
)

COMMAND_ALTAS_CLIENT: set[Type[ChatCommand]] = set()
COMMAND_ALTAS_SERVER: set[Type[ChatCommand]] = set()
COMMAND_PREFIXES: list[str] = ["/"]


class CommandIntercept(ChatIntercept):
    """Chat interception for reading commands."""

    @override
    def intercept(self, msg: str, client_id: int) -> bool:
        """Check if this message starts with a command prefix.

        Returns False if we match a command to prevent this
        message from being sent if the message is a command.
        """
        for cmdprefix in COMMAND_PREFIXES:
            if msg.startswith(cmdprefix):
                return not self.cycle_thru_commands(msg, client_id, cmdprefix)
        return True

    def cycle_thru_commands(
        self, msg: str, client_id: int, command_prefix: str
    ) -> bool:
        """Match our message to an existing command and
        run it's 'execute' function.

        Returns success.
        """
        # FIXME: this code could benefit from a cleanup...
        message = msg.split(" ")
        command_query = message[0].removeprefix(command_prefix)

        # in case got a message with nothing but a prefix, ignore
        if not command_query:
            return False

        def run_command(call: Callable) -> bool:
            try:
                call()
            except Exception as e:
                logging.error("'%s' -> '%s'", msg, e, exc_info=True)
                broadcast_message_to_client(
                    client_id,
                    bs.Lstr(
                        resource="commands.error",
                        fallback_resource=(
                            "An error occurred while" " executing this command."
                        ),
                    ),
                )
            return True

        # check for client commands first
        for command in COMMAND_ALTAS_CLIENT:
            if (
                command_query == command.name
                or command_query in command.pseudos
            ):
                return run_command(lambda: command().execute(msg, client_id))
        # if we are not the host, immediately call it quits here
        if not are_we_host():
            return False

        # look for server commands if we're on the
        # hosting side of things.
        for command in COMMAND_ALTAS_SERVER:
            if command_query in command.pseudos:
                if not can_run_command(command, client_id):
                    # throw an error if we don't have
                    # enough permissions to run this command.
                    broadcast_message_to_client(
                        client_id,
                        bs.Lstr(
                            resource="commands.notperms",
                            fallback_resource=(
                                "You don't have the permissions"
                                " to run this command."
                            ),
                        ),
                        color=(1, 0.2, 0.2),
                    )
                    return True
                return run_command(lambda: command().execute(msg, client_id))

        # if we didnt find anything, we should land here
        broadcast_message_to_client(
            client_id,
            bs.Lstr(
                resource="commands.notfound",
                fallback_value='Command "${CMD}" not found.',
                subs=[("${CMD}", command_query)],
            ),
            (1, 0.1, 0.1),
        )
        return True


CommandIntercept.register()


class ChatCommand:
    """A command executable by sending its name in chat."""

    name: str = "Command Name"
    """Name of this command.
    
    This name is not used when checking for pseudos and
    is purely to give the command a display name.
    """
    description: str = "Describes what this command does."
    """A description of this command.
    
    Elaborates on what the command is meant to do.
    This is not used directly but rather stored for any
    command that might require it (eg. a help command.)
    """

    pseudos: list[str] = []
    """Names to check for to trigger this command."""

    # TODO: finish these docs
    admin_only: bool = False
    """Whether the command is exclusive to administrators.
    Admins can be set via --admin_toml_path--.
    """

    # TODO: docs & permissions implementation
    minimum_permission_level: int = -1
    """The minimum permission level needed to use this command.
    Check --perms_module-- to understand how permissions work.
    """

    whitelisted_roles: list[Any] = []

    blacklisted_roles: list[Any] = []

    @classmethod
    def _pseudos_check(cls) -> None:
        """Check if this command has pseudos to use.
        Log a warning if we don't.
        """
        if len(cls.pseudos) < 1:
            logging.warning(
                'no pseudos given to sticker "%s", so it can\'t be used!',
                cls.name,
            )

    @classmethod
    def register_client(cls) -> None:
        """Register this command under the client.

        Client commands are capable of being executed in any
        server, even if you don't have any operator permissions.
        This type of command can't mess with gameplay content.
        """
        cls._pseudos_check()
        COMMAND_ALTAS_CLIENT.add(cls)

    @classmethod
    def register_server(cls) -> None:
        """Register this commands under the server.

        Server commands are run by the server, meaning you can't
        execute them outside of your own game or someone else who
        is hosting the command.
        This type of command can do basically whatever!
        """
        cls._pseudos_check()
        COMMAND_ALTAS_SERVER.add(cls)

    def execute(self, msg: str, client_id: int) -> None:
        """Runs the command!

        Note that all argument and context handling has to be
        managed by you in this segment of code.

        Args:
            msg (str): The raw command message.
            client_id (int): The ID of the user who sent the message.
        """
        # FIXME: actually, we should pass the message split to make
        #        argument handling easier, delivering the entire
        #        message is silly and stupid!
        raise NotImplementedError("'execute' needs to be overriden by class.")


def can_run_command(cmd_cls: Type[ChatCommand], client_id: int) -> bool:
    if cmd_cls.admin_only and not is_admin_from_client_id(client_id):
        return False
    # FIXME: implement roles and permission levels
    return True


def server_command(cls):
    """Class decorator to register a command as server-side."""
    if cls in COMMAND_ALTAS_CLIENT:
        raise IndexError(f"{cls} already registered as a client command.")
    COMMAND_ALTAS_SERVER.add(cls)
    return cls


def client_command(cls):
    """Class decorator to register a command as client-side."""
    if cls in COMMAND_ALTAS_SERVER:
        raise IndexError(f"{cls} already registered as a server command.")
    COMMAND_ALTAS_CLIENT.add(cls)
    return cls
