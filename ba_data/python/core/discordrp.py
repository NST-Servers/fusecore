"""Discord Rich Presence module."""

from dataclasses import dataclass
import time
import random
import threading
import logging
import hashlib
from enum import Enum
from typing import Any

import babase
import babase._hooks
import bascenev1 as bs
from babase._appsubsystem import AppSubsystem
from bascenev1lib.mainmenu import MainMenuActivity
from bauiv1lib.gather.publictab import PartyEntry

from core.libs.discordrp import Presence

# General data
APP_CLIENT_ID = "1439177584993894460"
TIME_UPDATE: int = 1
TIME_WAIT: float = 0.33
IDLE_TIME: int = 15
HIDE_ONLINE: bool = False
# Reconnection retry attributes
AUTO_START = False
RETRY_ON_DISCONNECT = True
RETRY_ON_BOOT_FAIL = True
RETRY_TIME_START: float = 8
RETRY_TIME_MULT: float = 1.2
RETRY_TIME_MAX: int = 20
RETRY_ATTEMPTS: int = 15

DISPLAY_TIME_IS_RUNTIME = False
"""Is our display time how long we've been playing the game?

if False, the time will display time remaining in our game activity,
otherwise, our game runtime since launch will be displayed.
"""
DATA_PERSISTENT = False
"""Do we send duplicate info. when updating our status?

Makes reconnecting faster but is more resource intensive
and could slow down the game on weaker devices.
"""  # TODO: Maybe we can improve on this?
SERVER_LISTING_UPDATE: float = 8.0
"""Seconds between listing fetch.

The smaller the number, the more we fetch our servers,
but the more bandwidth we occupy.
"""

MAPICON_PRE = 'map_'
MAPICON_STR: dict = {
    'Big G': 'bigg',
    'Bridgit': 'bridgit',
    'Courtyard': 'courtyard',
    'Crag Castle': 'cragcastle',
    'Doom Shroom': 'doomshroom',
    'Football Stadium': 'footballstadium',
    'Hockey Stadium': 'hockeystadium',
    'Happy Thoughts': 'happythoughts',
    'Lake Frigid': 'lakefrigid',
    'Monkey Face': 'monkeyface',
    'Rampage': 'rampage',
    'Roundabout': 'roundabout',
    'Step Right Up': 'steprightup',
    'The Pad': 'thepad',
    'Tip Top': 'tiptop',
    'Tower D': 'towerd',
    'Zigzag': 'zigzag',
}


def _log() -> logging.Logger:  # This thing is awesome.
    return logging.getLogger(__name__)


class RPStatusType(Enum):
    """Rich Presence state type.
    This type is related to how our Rich Presence is
    displayed on discord.

    e.g. 'RPStatusType.PLAYING' will display "Playing BombSquad"
    while 'RPStatusType.WATCHING' will show "Watching BombSquad"

    NOTE: Status type 'WATCHING' is hardcoded and does not work!
    """

    # https://discord.com/developers/docs/events/gateway-events#activity-object-activity-types
    PLAYING = 0
    STREAMING = 1
    LISTENING = 2
    WATCHING = 3
    CUSTOM = 4
    COMPETING = 5


class RPDisplayType(Enum):
    # https://discord.com/developers/docs/events/gateway-events#activity-object-status-display-types
    NAME = 0
    STATE = 1
    DETAILS = 2


@dataclass
class RPTimestamps:
    """Rich Presence timestamps collection."""

    # https://discord.com/developers/docs/events/gateway-events#activity-object-activity-timestamps
    start: int
    end: int

    def to_dict(self) -> dict:
        return {
            'start': self.start,
            'end': self.end,
        }


@dataclass
class RPEmoji:
    # https://discord.com/developers/docs/events/gateway-events#activity-object-activity-emoji
    # FIXME: is this even needed in this context?
    name: str
    id: str = ''
    animated: bool = False


@dataclass
class RichPresenceStatus:
    """Discord Activity Status."""

    # https://discord.com/developers/docs/events/gateway-events#activity-object-activity-structure
    name: str
    type: RPStatusType
    created_at: int

    url = None
    """Used for streams, goes unused here."""
    timestamps: RPTimestamps | None = None
    """Start and end times of our activity, displayed as a timer."""
    application_id: str = ''
    status_display_type: RPDisplayType = RPDisplayType.NAME

    details: str = ''
    details_url: str = ''
    state: str = ''
    state_url: str = ''

    # FIXME: is this even needed in this context?
    emoji: RPEmoji | None = None

    # TODO: implement me!
    party = None
    assets = None
    secrets = None
    instance = None
    flags = None
    buttons = None


class ThreadState(Enum):
    INACTIVE = 0
    ACTIVE = 1
    STOPPED = -1


class RichPresenceThread(threading.Thread):
    def __init__(self):
        """Create a thread to dynamically change
        our Discord Rich Presence status between activities.
        """
        super().__init__()
        self.presence: Presence | None = None
        self.status: ThreadState = ThreadState.INACTIVE
        self._should_stop = threading.Event()

    def _handle_error(self, exc: Exception) -> None:
        """Handle not being able to send a Rich Presence request."""
        self.status = ThreadState.STOPPED
        # If we OSError, we probably lost connection.
        # Don't make a fuss about it.
        if isinstance(exc, OSError) and not isinstance(exc, FileNotFoundError):
            return
        _log().error(
            'Something wrong occurred while handling a rich presence request.\n'
            f'ThreadState: {self.status}',
            exc_info=exc,
        )

    def _start_presence(self) -> None:
        """Try executing our presence."""
        # Start running and mantain our presence.
        try:
            _log().info('Starting \'RichPresenceThread\'...')
            with Presence(APP_CLIENT_ID) as presence:
                self.presence = presence
                presence.set(
                    {
                        "assets": {
                            "large_image": "claypocalypse_logo_final",
                        }
                    }
                )
                self.status = ThreadState.ACTIVE
                _log().info(
                    '\'RichPresenceThread\' started successfully!\n'
                    'Waiting for our DiscordRPSubsystem to link...'
                )
                # Keep it running!
                while not self._should_stop.is_set():
                    time.sleep(0.1)
                self.status = ThreadState.STOPPED
                _log().info('\'RichPresenceThread\' stopped.')

        except Exception as e:
            self._handle_error(e)

    def set(self, data: dict) -> None:
        """Set our presence."""
        # https://discord.com/developers/docs/topics/gateway-events#activity-object-activity-structure
        if self.presence is None:
            _log().warning(
                'No DiscordRPSubsystem linked while tying to set presence status?',
                stack_info=True,
            )
            return

        _log().info('Set our Discord Presence Status.\n' f'Provided: {data}')

        try:
            self.presence.set(data)
        except Exception as e:
            self._handle_error(e)

    def stop(self) -> None:
        """Stop our presence."""
        self._should_stop.set()

    def run(self):
        self._should_stop = threading.Event()
        self._start_presence()


class DiscordRPSubsystem(AppSubsystem):
    """System in charge of handling all things Discord Rich Presence.

    This subsystem manages Rich Presence data via 'RichPresenceThread',
    updating our status according to active game state and
    handles reconnection in case of connection failure.
    """

    def __init__(self) -> None:
        super().__init__()
        self._thread: RichPresenceThread | None = None
        self._creation_time: int = int(time.time() * 1000)

        self.rpstatus: RichPresenceStatus = RichPresenceStatus(
            name='BombSquad',
            type=RPStatusType.PLAYING,
            created_at=self._creation_time,
        )

        self.data: dict = {}
        self.latest_data: dict = {}

        self.time_start: int = 1
        self.time_end: int | None = 1

        self.activity_hash: int | None = None
        self.last_time_update: int = -9999
        self.update_timer: bs.AppTimer | None = None

        self.retry_timer: bs.AppTimer | None = None
        self.retry_time: float = RETRY_TIME_START
        self.retry_attempt: int = 0

        self.last_listing_fetch: float = 1
        self.current_server_data: PartyEntry | None = None
        self.server_listing: dict = {}
        self.server_entry: dict = {}

        self._party_id: str = ''
        self._join_secret: str = ''

        self.r = 'discordrp'

    def on_app_running(self) -> None:
        """Start automatically when our app reaches running state,
        making sure we don't load up when other subsystems are unavailable.
        """
        if AUTO_START:
            self.start()

    def _reset_variables(self) -> None:
        self.data = {}
        self.latest_data = {}
        self.time_start = 1
        self.time_end = 1
        self.activity_hash = None
        self.last_time_update = -9999
        self.retry_time = RETRY_TIME_START
        self.retry_attempt = 0
        # Generate secrets too
        self._party_id = ''
        self._join_secret = ''
        self.generate_secrets()

    def _update_status(self, data: dict) -> None:
        if self._thread and (data != self.latest_data or DATA_PERSISTENT):
            self._thread.set(data)
            self.latest_data = data

    def _get_start_time(self) -> int:
        if hash(bs.get_foreground_host_activity()) != self.activity_hash and (
            not DISPLAY_TIME_IS_RUNTIME or self.time_start == 1
        ):
            self.time_start = int(time.time())
        return self.time_start

    def _get_end_time(self) -> int | None:
        activity: bs.GameActivity = bs.get_foreground_host_activity()
        try:
            # Only update end time per activity change,
            # when we're paused and every 5 seconds
            # (to prevent major desyncs)
            if (
                hash(activity) != self.activity_hash
                or activity.globalsnode.paused
                or int(time.time()) > self.last_time_update
            ) and not activity.globalsnode.slow_motion:
                self.time_end = None
                if isinstance(activity, bs.GameActivity):
                    self.time_end = int(time.time()) + (
                        activity._standard_time_limit_time or 0
                    )
                    self.last_time_update = int(time.time()) + 5
            elif hash(activity) == self.activity_hash:
                pass
            else:
                self.time_end = None
        except Exception:
            self.time_end = None
        return self.time_end

    def _get_map_name(self, activity: bs.GameActivity) -> str:
        """Get our GameActivity's translated map name."""
        # Check and translate our current map's name.
        return bs.Lstr(
            translate=('mapsNames', activity.map.name),
        ).evaluate()

    def _get_map_large_image(self, activity: bs.GameActivity) -> str:
        """Return our large image asset for our GameActivity's map."""
        # Check and translate our current map's name.
        return f'{MAPICON_PRE}{MAPICON_STR.get(activity.map.name, "unknown")}'

    def _get_game_details(
        self, session: bs.Session, set_activity: bs.Lstr | str
    ) -> str:
        """Transform our session and active activity into a detail string.
        E.g. A 'FreeForAllSession' session and a
        'bs.Lstr(resource='discordrp.lobby')' activity should return
        "Free-For-All | Lobby" string after Lstr evaluation.

        Args:
            session (bs.Session): Our active session.
            set_activity (bs.Lstr | str): A specified activity.

        Returns:
            str: Our evaluated details string.
        """
        return 'hello!'

        session_name = f'{self.r}.session.'
        if isinstance(session, bs.CoopSession):
            if session.campaign is not None:
                session_name += f'coop.{session.campaign.name}'
            else:
                session_name += 'other'

        elif isinstance(session, bs.FreeForAllSession):
            session_name += 'ffa'

        elif isinstance(session, bs.FreeForAllSession):
            session_name += 'teams'

        else:
            session_name += 'other'

        return bs.Lstr(
            value='${SESSION} | ${ACTIVITY}',
            subs=[
                ('${SESSION}', bs.Lstr(resource=session_name)),
                ('${ACTIVITY}', set_activity),
            ],
        ).evaluate()

    def generate_secrets(self) -> None:
        """Get our online address, port and if we're accessible.
        Generate secrets out of that once fetched.
        """
        _log().info('Preparing to generate secrets...')
        if bs.app.classic is not None:
            bs.app.classic.master_server_v1_get(
                'bsAccessCheck',
                {'b': bs.app.env.engine_build_number},
                callback=bs.WeakCallPartial(self._actually_generate_secrets),
            )

    def _actually_generate_secrets(self, data: dict[str, Any] | None) -> None:
        """Generate secrets for handling discord join requests."""
        # Very lame case handler
        if data is None:
            _log().info('No data to generate secrets.')
            return
        elif not data.get('accessible', False):
            _log().info('Party is unjoinable, ignoring secrets.')
            return

        _log().info(f'Generating secrets\nData: {data}')

        address = data.get('address', None)
        port = data.get('port', None)

        def do_hash(v, algorithm: str = 'sha256') -> str:
            """Return a sha algorithm value."""
            hasher = hashlib.new(algorithm)
            hasher.update(str(v).encode('utf-8'))
            return hasher.hexdigest()

        # party_id is correlated to the validity of invites.
        # Uniqueness is important to prevent people from using
        # old invites to join your current party.
        self._party_id = do_hash(
            f'{address}{babase._hooks.get_v2_account_id()}'
            f'{time.time()*random.random()}'
        )

        # *sigh* The proper way to handle this would be by requesting
        # the master server for a unique key linked to our party.
        # Currently, nothing is stopping mods from hijacking and replacing
        # this secret to direct to their own servers, which is super lame.
        self._join_secret = f'a:{address},' f'p:{port}'
        # @efro Let us know if you'd plan on implementing a system
        # to solve this in the future!

    def _get_allow_joining(self) -> bool:
        """Return whether we allow joining via Rich Presence or not."""
        discord_ckey: str = bs.app.config.get('Allow Discord Joining', 'Allow')
        return (
            bs.get_public_party_enabled() and not discord_ckey == 'Never'
        ) or discord_ckey in 'Always'

    def _hide_local_party_status(self) -> None:
        """Hide our status if we're not in a party and don't allow joining."""
        if not bs.get_game_roster() and not self._get_allow_joining():
            self.data.pop('state', None)
            self.data.pop('party', None)

    def _get_process_status(self) -> ThreadState | None:
        """Get our DRPProcess' status."""
        if self._thread is None:
            return
        return self._thread.status

    def _is_active(self) -> bool:
        return bool(self.update_timer)

    def _process_stop(self) -> None:
        if self._thread is not None:
            self._thread.stop()
        self._thread = None

    def large_image_idle_text(
        self, active: bs.Lstr | str, idle: bs.Lstr | str | None = None
    ) -> str:
        """Return text for our large image.
        Returns "idle" or "bs.Lstr(resource=f'{self.r}.idle').evaluate()"
        in case our player has been gone for too long.
        Else, return our provided "active" text.
        """
        default = bs.Lstr(resource=f'{self.r}.idle').evaluate()
        return (
            (
                default
                if not idle
                else idle.evaluate() if isinstance(idle, bs.Lstr) else idle
            )
            if babase.get_input_idle_time() >= IDLE_TIME
            else active.evaluate() if isinstance(active, bs.Lstr) else active
        )

    def start(self, reconnect: bool = False) -> None:
        """Ready up our 'RichPresenceThread' and link to it
        once it enters an active state.
        """
        # The sole purpose for this empty context is so
        # running this via console inherits self.update_timer.
        with bs.ContextRef.empty():
            if bs.app.classic is None or (
                bs.app.classic.server is None
                and bs.app.classic.platform
                in ['windows', 'win32', 'mac', 'linux']
            ):
                # If we're already running something, don't do anything.
                # (don't mark it as an error as we might be trying to
                #  reconnect in case we lost connection to Discord.)
                if self._thread is not None:
                    _log().warning(
                        'Tried to start while already running?', stack_info=True
                    )
                    return

                self._thread = RichPresenceThread()
                self._thread.start()
                self.update_timer = bs.AppTimer(
                    TIME_WAIT,
                    bs.CallPartial(self.rp_wait_for, reconnect=reconnect),
                    repeat=True,
                )
            else:
                _log().warning(
                    'DiscordRPSubsystem won\'t start in '
                    'server mode or non-desktop environments.'
                )

    def stop(self, retry: bool = False) -> None:
        """Stop our Rich Presence process and subsystem.
        If specified to retry, attempt to reboot our DRPProcess.
        """
        self._process_stop()
        self.update_timer = None
        _log().info('DiscordRPSubsystem halted.')
        if retry:
            _log().info('Attempting Subsystem restart!')
            self.retry_timer = bs.AppTimer(
                self.retry_time, self.rp_reconnect, repeat=True
            )

    def rp_wait_for(self, reconnect: bool = False) -> None:
        """Wait for our DRPProcess to become active.
        Once active, start our standard update cycle.
        """
        if not self._thread:
            return

        # Switch our timer to updates once it activates.
        if self._thread.status is ThreadState.ACTIVE:
            _log().info('DiscordRPSubsystem up and running!')
            self.update_timer = bs.AppTimer(
                TIME_UPDATE, self.update, repeat=True
            )
            self.retry_timer = None
            self._reset_variables()
        # We lost connection...?
        elif self._thread.status is ThreadState.STOPPED:
            self.stop(retry=RETRY_ON_DISCONNECT and not reconnect)

    def rp_reconnect(self) -> None:
        """Attempt running back our RP process in case of a disconnection."""
        self.retry_time = min(RETRY_TIME_MAX, self.retry_time * RETRY_TIME_MULT)
        self.retry_attempt += 1
        if not self.retry_attempt > RETRY_ATTEMPTS and not RETRY_ATTEMPTS < 0:
            _log().info(
                'Attempting reconnection!' f'({self.retry_time} seconds)'
            )
            self.retry_timer = bs.AppTimer(
                self.retry_time, self.rp_reconnect, repeat=True
            )
            self.start(reconnect=True)
        else:
            _log().info('Reached reconnect attempt limit, stopping!')
            self.retry_timer = None

    def update(self) -> None:
        """Perform a Rich Presence status update."""
        if not self._thread:
            return

        _log().debug('DiscordRPSubsystem update cycle start')

        # Stop the subsystem if we lose connection.
        if self._thread.status is ThreadState.STOPPED:
            self.stop(retry=RETRY_ON_DISCONNECT)
            return

        activity: bs.Activity = bs.get_foreground_host_activity()
        session: bs.Session = bs.get_foreground_host_session()
        self.data = {}

        # Regardless of our current activity,
        # show our party size if we are in or hosting one.
        party = None if not bs.get_game_roster() else len(bs.get_game_roster())
        allow_joining = self._get_allow_joining()
        if party or allow_joining:
            self.data.update(
                {
                    'party': {
                        'id': self._party_id or '00',
                        'size': (party or 1, bs.get_public_party_max_size()),
                    }
                }
            )
        # Only generate secrets if we're allowing people to join
        # and are hosting our own party.
        if (
            allow_joining
            and not bs.get_connection_to_host_info_2()
            and self._join_secret
            and self._party_id
        ):
            self.data.update(
                {
                    'secrets': {
                        'join': self._join_secret,
                    },
                }
            )
        # If we're playing, show our crew status;
        # either if we're by ourselves, with friends locally or online.
        sessionplayers = 1
        if session is not None:
            sessionplayers = len(session.sessionplayers)
        self.data["state"] = bs.Lstr(
            resource=f'{self.r}.players.'
            + (
                'solo'
                if not party and sessionplayers < 2
                else (
                    'coop'
                    if not party and isinstance(session, bs.CoopSession)
                    else (
                        'multi'
                        if not party
                        else 'public' if allow_joining else 'private'
                    )
                )
            ),
        ).evaluate()

        # Online / Replay
        if activity is None:
            if bs.get_connection_to_host_info_2():
                self.set_presence_online()
            elif bs.is_in_replay():
                self.set_presence_replay()
            # If we reach this point, the player might be
            # presentiating a dark void as they broke the game
            # because this is not supposed to happen.
            # In this case, let's lie a little and say
            # our player is looking at the main menu.
            else:
                self.set_presence_main_menu()
        # Main Menu
        elif isinstance(activity, MainMenuActivity):
            self.set_presence_main_menu()
        # Generic Game
        elif isinstance(activity, bs.GameActivity):
            self.set_presence_in_game()
        # Joining Game
        elif isinstance(activity, bs.JoinActivity):
            self.set_presence_join()
        # Anything else (transitions, victory screens...)
        else:
            # We actually don't want to update here to make
            # transitions between activities smoother.
            return
        self.activity_hash = hash(activity)

        # Update presence with our active data!
        self._update_status(self.data)

    def find_and_get_server_data(self) -> None:
        """Find all available active server data."""
        # I couldn't find a better way to do this and this
        # method is REALLY ugly... We're gonna get a list
        # of all servers and then cherry-pick the one we're in.
        if bs.app.plus is None:
            logging.warning(
                '"find_and_get_server_data" requires plus features.'
            )
            return

        plus = bs.app.plus

        def got_results(results: dict) -> None:
            # Extract data from here.
            if not results:
                return

            _log().debug(
                'server data results:' f'{results}',
            )

            self.server_listing = results
            if self.current_server_data is not None:
                self.server_entry = (
                    [
                        entry
                        for entry in self.server_listing.get('l', [])
                        if entry.get('a', None)
                        == self.current_server_data.address
                        and entry.get('p', None)
                        == self.current_server_data.port
                    ]
                    or [{}]
                )[0]
            else:
                self.server_entry = {}

        # If we already did this earlier, use our previous results.
        if not time.time() > self.last_listing_fetch + SERVER_LISTING_UPDATE:
            got_results(self.server_listing)
        # Else... *gulp*... Call the list in.
        elif plus is not None:
            _log().info('Fetching server list (ugh) to cherry-pick.')
            plus.add_v1_account_transaction(
                {
                    'type': 'PUBLIC_PARTY_QUERY',
                    'proto': bs.protocol_version(),
                    'lang': bs.app.lang.language,
                },
                callback=bs.CallPartial(got_results),
            )
            self.last_listing_fetch = time.time() + SERVER_LISTING_UPDATE

    def set_presence_online(self) -> None:
        """Update our online game status."""
        import ast

        server: PartyEntry = bs.get_connection_to_host_info_2()
        # Get more server information if we haven't.
        if not self.current_server_data == server:
            self.server_entry = {}
            self.find_and_get_server_data()
        self.current_server_data = server

        name = None
        if hasattr(server, 'name') and not HIDE_ONLINE:
            name = server.name if len(server.name) > 2 else None
        details = bs.Lstr(
            value='${SERVER}',
            subs=[
                (
                    '${SERVER}',
                    name or (bs.Lstr(resource=f'{self.r}.session.private')),
                )
            ],
        ).evaluate()
        player_count = max(
            1,
            len(
                [
                    p
                    for p in bs.get_game_roster()
                    # Ignore the server by turning the "spec_string"
                    # string into a proper dict. and checking the "a" val.
                    if not (
                        ast.literal_eval(p['spec_string']).get('a', None)
                        == 'Server'
                    )
                ]
            ),
        )
        # For whom reads this... Yes.
        # We indeed just got a whole server listing
        # JUST to get an accurate max player number.
        player_limit = self.server_entry.get('sm', 8)

        self.data.update(
            {
                "details": details,
                "state": bs.Lstr(
                    resource=f'{self.r}.players.online'
                ).evaluate(),
                "timestamps": {
                    "start": self._get_start_time(),
                },
                "assets": {
                    "large_image": "claypocalypse_logo_final",
                    "large_text": self.large_image_idle_text(
                        active=bs.Lstr(resource=f'{self.r}.play'),
                        idle=bs.Lstr(resource=f'{self.r}.spectate'),
                    ),
                },
                "party": {
                    "size": (player_count, player_limit),
                },
                "instance": True,
            }
        )
        # Player numbers could hint to what server we're in.
        # If we have HIDE_ONLINE enabled, We don't want that!
        if HIDE_ONLINE:
            self.data.update(
                {
                    "party": {},
                }
            )

    def set_presence_replay(self) -> None:
        """Update our replay status."""
        details = bs.Lstr(resource=f'{self.r}.replay').evaluate()
        self.data.update(
            {
                "details": details,
                "timestamps": {
                    "start": self._get_start_time(),
                },
                "assets": {
                    "large_image": "replay",
                    "large_text": bs.Lstr(
                        resource=f'{self.r}.watch'
                    ).evaluate(),
                },
                "instance": False,
            }
        )
        # We don't want a state here unless we're in a party.
        self._hide_local_party_status()

    def set_presence_join(self) -> None:
        """Update our pre-game status."""
        session: bs.Session = bs.get_foreground_host_session()
        details = self._get_game_details(
            session, bs.Lstr(resource=f'{self.r}.lobby')
        )
        state = bs.Lstr(resource=f'{self.r}.players.wait').evaluate()

        self.data.update(
            {
                "details": details,
                "state": state,
                "timestamps": {
                    "start": self._get_start_time(),
                },
                "assets": {
                    "large_image": "claypocalypse_logo_final",
                    "large_text": state,
                },
                "instance": False,
            }
        )

    def set_presence_main_menu(self) -> None:
        """Update our main menu status."""
        self.data.update(
            {
                "details": bs.Lstr(resource=f'{self.r}.menu').evaluate(),
                "timestamps": {
                    "start": self._get_start_time(),
                },
                "assets": {
                    "large_image": "claypocalypse_logo_final",
                    "large_text": self.large_image_idle_text(
                        active=bs.Lstr(resource=f'{self.r}.navigate')
                    ),
                },
                "instance": False,
            }
        )
        # We don't want a state here unless we're in a party.
        self._hide_local_party_status()

    def set_presence_in_game(self) -> None:
        """Update our game status."""
        activity: bs.GameActivity = bs.get_foreground_host_activity()
        session: bs.Session = bs.get_foreground_host_session()
        end_time = self._get_end_time()
        activity_name = (
            activity.get_instance_scoreboard_display_string().evaluate()
        )
        details = self._get_game_details(
            session, bs.Lstr(translate=('gameNames', activity_name))
        )

        self.data.update(
            {
                "details": details,
                "timestamps": {
                    "start": self._get_start_time(),
                },
                "assets": {
                    "large_image": self._get_map_large_image(activity),
                    "large_text": self._get_map_name(activity),
                },
                "instance": False,
            }
        )
        # Add our end time if existing.
        if end_time:
            self.data["timestamps"]["end"] = end_time

    def on_presence_join(self, data: dict) -> None:
        """Join a game via Discord Rich Presence event."""

    def on_presence_join_request(self, data: dict) -> None:
        """Display a join request via Discord Rich Presence event."""

    def on_app_shutdown(self) -> None:
        """Stop our Rich Presence once the game goes into shutdown."""
        self.stop()
