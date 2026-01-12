"""General commands."""

from typing import override
from fusecore.chat.commands import (
    COMMAND_ALTAS_SERVER,
    ChatCommand,
    can_run_command,
    server_command,
)
from fusecore.chat.utils import send_custom_host_message


@server_command
class HelpCommand(ChatCommand):
    """Help command."""

    name = "Help"
    description = "Show all available commands."

    pseudos = ["help", "?"]

    @override
    def execute(self, msg: str, client_id: int) -> None:
        del msg  # not needed

        t_bar = "- " * 21
        text: str = f"- {t_bar} [ Command List ] {t_bar}-"

        send_custom_host_message(text, clients=[client_id])

        # list all available commands
        for cmd in set().union(COMMAND_ALTAS_SERVER):
            # ignore commands with no pseudos
            if not cmd.pseudos:
                continue
            # ignore commands we dont have the permissions for
            if not can_run_command(cmd, client_id):
                continue

            t = f"{cmd.name} (/{cmd.pseudos[0]}): {cmd.description}\n"

            send_custom_host_message(t, clients=[client_id])
