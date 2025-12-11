"""In-game commands executable via 'ChatIntercept'."""

from __future__ import annotations

from typing import Callable, Type, override
import logging

import bascenev1 as bs

from . import (
    ChatIntercept,
    broadcast_message_to_client,
    send_custom_chatmessage,
    are_we_host,
)

COMMAND_ALTAS_CLIENT: set[Type[ChatCommand]] = set()
COMMAND_ALTAS_SERVER: set[Type[ChatCommand]] = set()
COMMAND_PREFIXES: list[str] = ['/']


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
        message = msg.split(' ')
        command_entry = message[0].removeprefix(command_prefix)

        # in case got a message with nothing but a prefix, ignore
        if not command_entry:
            return False

        def run_command(call: Callable) -> bool:
            try:
                call()
            except Exception as e:  # pylint: disable=broad-exception-caught
                logging.error("'%s' -> '%s'", msg, e, exc_info=True)
                broadcast_message_to_client(
                    client_id, bs.Lstr(resource='commands.error')
                )
            return True

        # if we're hosting, load up our server commands
        # these commands function exclusively when hosting
        # as they could mess around with gmae logic and nodes
        for command in COMMAND_ALTAS_SERVER:
            if (
                command_entry == command.name
                or command_entry in command.pseudos
            ):
                if are_we_host():
                    # there is a chance a command could work for both clients
                    # and servers (such as '/help').
                    # let's make an exception for those.
                    return run_command(
                        lambda: command().execute(msg, client_id)
                    )
                # elif not are_we_host() and command in COMMAND_ALTAS_CLIENT:
                #     return False
                return False
                # NOTE: we were meant to show an error telling the user
                # the command they asked for is server-only, but that
                # nullifies server-side logic... maybe there's a way
                # for servers to communicate their command list so we
                # can do this only when it's necessary?
                # broadcast_message_to_client(
                #     client_id,
                #     bs.Lstr(
                #         resource='commands.serveronly',
                #         subs=[('${CMD}', command_entry)],
                #     ),
                # )

        for command in COMMAND_ALTAS_CLIENT:
            # afterwards, load up our client commands
            # these ones work anywhere, including other
            # servers that are not hosting with a modded core
            if (
                command_entry == command.name
                or command_entry in command.pseudos
            ):
                return run_command(lambda: command().execute(msg, client_id))

        if are_we_host():
            # we only show this as host to allow clients to
            # perform our server commands.
            # the server-side will catch to this anyways.
            broadcast_message_to_client(
                client_id,
                bs.Lstr(
                    resource='commands.notfound',
                    subs=[("${CMD}", command_entry)],
                ),
                (1, 0.1, 0.1),
            )
            return True
        return False


CommandIntercept.register()


class ChatCommand:
    """A command executable by sending its name in chat."""

    name: str
    pseudos: list[str] = []

    display_name: str = 'Command Name'
    description: str = 'Describes what this command does.'

    @classmethod
    def register_client(cls) -> None:
        """Register this command under the client.

        Client commands are capable of being executed in any
        server, even if you don't have any operator permissions.
        This type of command can't mess with gameplay content.
        """
        COMMAND_ALTAS_CLIENT.add(cls)

    @classmethod
    def register_server(cls) -> None:
        """Register this commands under the server.

        Server commands are run by the server, meaning you can't
        execute them outside of your own game or someone else who
        is hosting the command.
        This type of command can do basically whatever!
        """
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
        raise RuntimeError("'execute' function needs to be overriden.")


class HelpCommand(ChatCommand):
    """Help command."""

    name = 'help'
    pseudos = ['?']

    display_name = 'Help'
    description = 'Show all available commands.'

    @override
    def execute(self, msg: str, client_id: int) -> None:
        del msg  # not needed

        def host_send_custom_chatmessage(t: str):
            if are_we_host():
                send_custom_chatmessage(t)

        t_bar = '- ' * 18
        text: str = f'- {t_bar} Command List (0/0) {t_bar}-\n'

        host_send_custom_chatmessage(text)

        for cmd in set().union(COMMAND_ALTAS_SERVER):
            t = f'{cmd.display_name}: {cmd.description}\n'

            host_send_custom_chatmessage(t)


HelpCommand.register_server()
