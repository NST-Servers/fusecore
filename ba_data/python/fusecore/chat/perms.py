"""Utilities for user permissions."""

from typing import Any

import bascenev1 as bs
from fusecore.chat.utils import get_user_from_client_id


def get_perms_from_client_id(client_id: int) -> Any:
    """Get a user's permissions via 'client_id'."""
    if client_id == -1:
        return True
    return client_id


def is_admin_from_client_id(client_id: int) -> bool:
    """Return if the user behind a 'client_id' is an administrator or not."""
    if client_id == -1:
        # client_id '-1' is the host, and
        # the host is always an admin!
        return True
    # if we have server information, pull the admin list and
    # confirm if the user's account id is in said list.
    # pylint: disable=protected-access
    if (
        bs.app.classic
        and bs.app.classic.server
        and bs.app.classic.server._config
    ):
        info = get_user_from_client_id(client_id)
        if (
            info
            and info.get("account_id", "")
            in bs.app.classic.server._config.admins
        ):
            return True
    return False
