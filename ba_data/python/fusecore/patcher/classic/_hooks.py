import babase
from bascenev1 import _hooks


def filter_chat_message(msg: str, client_id: int) -> str | None:
    """Intercept/filter chat messages.

    Called for all chat messages while hosting.
    Messages originating from the host will have clientID -1.
    Should filter and return the string to be displayed, or return None
    to ignore the message.
    """
    from fusecore import chat
    return chat.chat_message_intercept(msg, client_id)

def local_chat_message(msg: str) -> None:
    """..."""
    classic = babase.app.classic
    assert classic is not None
    party_window = (
        None if classic.party_window is None else classic.party_window()
    )

    if party_window is not None:
        party_window.on_chat_message(msg)

# fun fact! we shouldn't be doing this
# but it's the only way we can get these to update.
# so please, to any modders looking at this: don't you even.
_hooks.filter_chat_message.__code__ = filter_chat_message.__code__
_hooks.local_chat_message.__code__ = local_chat_message.__code__
