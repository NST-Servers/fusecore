"""Discord Rich Presence module."""

import ast
from dataclasses import dataclass
import json
import time
import threading
import logging
from enum import Enum
from typing import Any, Callable, Literal, Type
from uuid import uuid4

from baclassic._appmode import ClassicAppMode
import bascenev1 as bs
from bascenev1 import (
    MultiTeamSession,
    DualTeamSession,
    FreeForAllSession,
    CoopSession,
)
from bascenev1._activitytypes import TransitionActivity
from bascenev1._net import HostInfo

from babase._appsubsystem import AppSubsystem
from bascenev1lib.mainmenu import MainMenuSession
from bascenev1lib import maps

from bascenev1lib.tutorial import TutorialActivity
from fusecore._tools import is_server
from fusecore.libs.discordrp import Presence
from fusecore.libs.discordrp.presence import _OpCode

from efro.dataclassio._api import dataclass_to_dict
from efro.dataclassio import ioprepped

import bauiv1 as bui
from bauiv1lib.play import PlayWindow
from bauiv1lib.watch import WatchWindow
from bauiv1lib.docui import DocUIWindow
from bauiv1lib.gather import GatherWindow
from bauiv1lib.coop.browser import CoopBrowserWindow
from bauiv1lib.profile.edit import EditProfileWindow
from bauiv1lib.inventory import InventoryUIController
from bauiv1lib.achievements import AchievementsWindow
from bauiv1lib.store.newstore import StoreUIController
from bauiv1lib.gather.publictab import AddrFetchThread
from bauiv1lib.league.rankwindow import LeagueRankWindow
from bauiv1lib.playlist.browser import PlaylistBrowserWindow
from bauiv1lib.league.presidency import LeaguePresidencyUIController
from bauiv1lib.settings import (
    advanced as bscfgm0,
    allsettings as bscfgm1,
    audio as bscfgm2,
    benchmarks as bscfgm3,
    controls as bscfgm4,
    devtools as bscfgm5,
    gamepad as bscfgm6,
    gamepadadvanced as bscfgm7,
    gamepadselect as bscfgm8,
    graphics as bscfgm9,
    keyboard as bscfgmA,
    nettesting as bscfgmB,
    plugins as bscfgmC,
    pluginsettings as bscfgmD,
    remoteapp as bscfgmE,
    testing as bscfgmF,
    touchscreen as bscfgmG,
    vrtesting as bscfgmH,
)


# sorry pylint! big file.
# pylint: disable=too-many-lines

APP_CLIENT_ID = "1439177584993894460"
"""https://discord.com/developers/applications"""
AUTO_START = True
PRIVATE_PRESENCE = False

STATUS_UPDATE_RATE_LIMIT_SECS = 1.5
SERVER_FETCH_SECS = 240.0

EVENT_CALLS_SET: dict[str, set[Callable]] = {}


def _log(
    subname: Literal["subsystem", "thread"],
) -> logging.Logger:  # This thing is awesome.
    # TODO: get the subname to return a different logger
    del subname
    return logging.getLogger(__name__)


class StatusType(Enum):
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


class StatusDisplayType(Enum):
    """Status display types."""

    # https://discord.com/developers/docs/events/gateway-events#activity-object-status-display-types
    NAME = 0
    STATE = 1
    DETAILS = 2


@ioprepped
@dataclass
class StatusTimestamps:
    """Activity timestamps."""

    # https://discord.com/developers/docs/events/gateway-events#activity-object-activity-timestamps
    start: int | None = None
    """Unix time (in milliseconds) of when the activity started."""
    end: int | None = None
    """Unix time (in milliseconds) of when the activity ends."""


@ioprepped
@dataclass
class StatusEmoji:
    """Activity emoji."""

    # https://discord.com/developers/docs/events/gateway-events#activity-object-activity-emoji
    name: str
    """Name of the emoji."""
    id: str | None = None
    """ID of the emoji."""
    animated: bool = False
    """Whether the emoji is animated."""


@ioprepped
@dataclass
class StatusParty:
    """Activity party."""

    # https://discord.com/developers/docs/events/gateway-events#activity-object-activity-party
    id: str = ""
    """ID of the party."""
    size: tuple[int, int] | None = None
    """Used to show the party's current and maximum size."""


@ioprepped
@dataclass
class StatusAssets:
    """Activity assets."""

    # https://discord.com/developers/docs/events/gateway-events#activity-object-activity-assets
    # https://discord.com/developers/docs/events/gateway-events#activity-object-activity-asset-image
    large_image: str | None = None
    """See "Activity Asset Image"."""
    large_text: str | None = None
    """Text displayed when hovering over the large image of the activity."""
    large_url: str | None = None
    """URL that is opened when clicking on the large image."""

    small_image: str | None = None
    """See "Activity Asset Image"."""
    small_text: str | None = None
    """Text displayed when hovering over the small image of the activity."""
    small_url: str | None = None
    """URL that is opened when clicking on the small image."""

    invite_cover_image: str | None = None
    """See "Activity Asset Image". Displayed as a banner on a Game Invite."""


@ioprepped
@dataclass
class StatusSecrets:
    """Activity secrets."""

    # https://discord.com/developers/docs/events/gateway-events#activity-object-activity-secrets
    join: str | None = None
    """Secret for joining a party."""
    spectate: str | None = None
    """	Secret for spectating a game."""
    match: str | None = None
    """	Secret for a specific instanced match."""


@ioprepped
@dataclass
class StatusButton:
    """Activity button.
    ### Note: These don't work as of 12/23/25.
    """

    # https://discord.com/developers/docs/events/gateway-events#activity-object-activity-buttons
    label: str
    """Text shown on the button (1-32 characters.)"""
    url: str
    """	URL opened when clicking the button (1-512 characters.)"""


class StatusResources(Enum):
    """Image resources to use in our activity assets."""

    # pylint: disable=line-too-long
    # main
    LOGO = "https://files.ballistica.net/bombsquad/promo/BombSquadLogo.png"
    COVER = "https://files.ballistica.net/bombsquad/promo/bombsquadBanner_732_480.png"
    # large images
    LOBBY = "https://i.postimg.cc/XvszMjB5/lobby.png"
    POTATO = "https://i.postimg.cc/kGvrG23F/void-potato.gif"
    REPLAY = "https://i.postimg.cc/Kc9GkQ2s/watch.png"
    # small images
    COOP = "https://i.postimg.cc/ZK6n2pNX/coop.png"
    FFA = "https://i.postimg.cc/c4CPd8B5/ffa.png"
    TEAMS = "https://i.postimg.cc/qq9bWWPz/teams.png"


# FIXME: normalize a resource class
# FIXME 2: don't rely on postimg, use discord's api instead
# postimg should only be used on dynamic assets or modded elements
MAP_THUMBNAIL_DEFAULT: str = "https://i.postimg.cc/52qwtk0L/map_unknown.png"
MAP_THUMBNAIL_DICT: dict[Type[bs.Map], str] = {
    maps.HockeyStadium: "https://i.postimg.cc/y8XFNrdK/map_hockey.png",
    maps.FootballStadium: "https://i.postimg.cc/CxHjK61Y/map_football.png",
    maps.Bridgit: "https://i.postimg.cc/jSrHtrsj/map_bridgit.png",
    maps.BigG: "https://i.postimg.cc/QdrQhrXx/map_bigg.png",
    maps.Roundabout: "https://i.postimg.cc/9QtGfNMQ/map_roundabout.png",
    maps.MonkeyFace: "https://i.postimg.cc/nhYvLwzV/map_monkeyface.png",
    maps.ZigZag: "https://i.postimg.cc/RZQc0bFw/map_zigzag.png",
    maps.ThePad: "https://i.postimg.cc/FHgjKnR7/map_thepad.png",
    maps.DoomShroom: "https://i.postimg.cc/VkcqmcY5/map_doomshroom.png",
    maps.LakeFrigid: "https://i.postimg.cc/jSQzjk5d/map_lakefrigid.png",
    maps.TipTop: "https://i.postimg.cc/qvX87ZRg/map_tiptop.png",
    maps.CragCastle: "https://i.postimg.cc/fRhcDhwz/map_cragcastle.png",
    maps.TowerD: "https://i.postimg.cc/P5zmqFxp/map_towerd.png",
    maps.HappyThoughts: "https://i.postimg.cc/CxVGSVFz/map_happythoughts.png",
    maps.StepRightUp: "https://i.postimg.cc/bwHQvFJS/map_steprightup.png",
    maps.Courtyard: "https://i.postimg.cc/T3XVfXR2/map_courtyard.png",
    maps.Rampage: "https://i.postimg.cc/fRjxbgLw/map_rampage.png",
}


@ioprepped
@dataclass
class ActivityStatus:
    """Discord Activity Status."""

    # https://discord.com/developers/docs/events/gateway-events#activity-object-activity-structure
    name: str
    """Activity's name."""
    type: StatusType
    """Activity type."""
    created_at: int | None = None
    """Unix timestamp (in milliseconds) of when
    the activity was added to the user's session.
    """

    url: str | None = None
    """Stream URL, is validated when type is 1."""
    timestamps: StatusTimestamps | None = None
    """Start and end times of our activity, displayed as a timer."""
    application_id: str = "<application-id>"
    """Application ID for the game."""
    status_display_type: StatusDisplayType = StatusDisplayType.NAME
    """Status display type; controls which field is displayed
    in the user's status text in the member list.
    """

    details: str | None = None
    """What the player is currently doing."""
    details_url: str | None = None
    """URL that is linked when clicking on the details text."""
    state: str | None = None
    """User's current party status, or text used for a custom status."""
    state_url: str | None = None
    """URL that is linked when clicking on the state text."""

    emoji: StatusEmoji | None = None
    """Emoji used for a custom status.
    ### Note: Seems to be unused as of 12/23/25.
    """

    party: StatusParty | None = None
    """Information for the current party of the player."""
    assets: StatusAssets | None = None
    """Images for the presence and their hover texts."""
    secrets: StatusSecrets | None = None
    """Secrets for Rich Presence joining and spectating."""
    instance: bool | None = None
    """Whether or not the activity is an instanced game session."""
    flags: int | None = None
    # https://discord.com/developers/docs/events/gateway-events#activity-object-activity-flags
    """Activity flags OR d together, describes what the payload includes."""
    buttons: None = None
    """Custom buttons shown in the Rich Presence (max 2.)
    ### Note: These don't work as of 12/23/25.
    """


class ThreadState(Enum):
    """The active state of a ``RichPresenceThread`` process.

    We use this enum to allow our thread to tell the
    ``DiscordRichPresenceSubsystem`` whether we're doing fine
    or have stopped for whatever reason.
    """

    INACTIVE = 0
    ACTIVE = 1
    STOPPED = -1


class RichPresenceThread(threading.Thread):
    """Thread in charge of running our Discord Rich Presence
    process and handling requests in and out from our subsystem.
    """

    def __init__(self):
        super().__init__()
        self.presence: Presence | None = None
        self.state: ThreadState = ThreadState.INACTIVE
        self._stop_event = threading.Event()

    def run(self):
        self._stop_event = threading.Event()
        self._start_thread()

    def _start_thread(self) -> None:
        """Try executing our presence."""
        # Start running and mantain our presence.
        try:
            _log("thread").info("Starting 'RichPresenceThread'...")
            with Presence(APP_CLIENT_ID) as presence:
                self.presence = presence
                self.state = ThreadState.ACTIVE
                _log("thread").info(
                    "'RichPresenceThread' started successfully!\n"
                    "Waiting for our DiscordRPSubsystem to link..."
                )
                # Keep it running!
                while not self._stop_event.is_set():
                    time.sleep(1)
                    # self._read_for_events()
                self.state = ThreadState.STOPPED
                _log("thread").info("'RichPresenceThread' stopped.")

        except Exception as e:
            self._handle_error(e)

    def stop(self) -> None:
        """Stop our presence."""
        self._stop_event.set()

    def _handle_error(self, exc: Exception) -> None:
        """Handle not being able to send a Rich Presence request."""
        if isinstance(exc, (OSError, FileNotFoundError)):
            # If we OSError, we probably lost connection.
            # Don't make a fuss about it.
            # If we FileNotFoundError, maybe we don't have
            # Discord in the first place?
            return

        _log("thread").error(
            "error while handling a rich presence request.\n%s",
            exc,
            exc_info=exc,
        )
        self.state = ThreadState.STOPPED

    def set(self, data: dict) -> None:
        """Update our presence status."""
        # https://discord.com/developers/docs/topics/gateway-events#activity-object-activity-structure
        if self.presence is None:
            _log("thread").warning(
                "thread uninitialized while trying to set status...\n"
                "are you running a 'DiscordRichPresenceSubsystem'?",
                stack_info=True,
            )
            return
        try:
            self.presence.set(data)
        except Exception as e:
            self._handle_error(e)
        _log("thread").info("thread presence update successful.")

    def send_payload(self, payload: dict[str, Any], op: _OpCode) -> None:
        """Tell our thread to send a payload request to Discord."""
        if self.presence is None:
            _log("thread").warning(
                "thread uninitialized while trying to set status...\n"
                "are you running a 'DiscordRichPresenceSubsystem'?",
                stack_info=True,
            )
            return
        try:
            # pylint: disable=protected-access
            self.presence._send(payload, op)
        except Exception as e:
            self._handle_error(e)

    @staticmethod
    def subscribe_event(event_name: str):
        """A ``RichPresenceThread`` decorator to store and call
        functions when receiving specific discord event requests.
        """

        def decorator(func):
            if EVENT_CALLS_SET.get(event_name, None) is None:
                EVENT_CALLS_SET[event_name] = set()
            EVENT_CALLS_SET[event_name].add(func)
            return func

        return decorator

    def _read_for_events(self) -> None:
        # pylint: disable=protected-access
        _log("thread").debug("thread read tick")
        read_result = self.presence._read()  # type: ignore
        funcset = EVENT_CALLS_SET.get(read_result.get("evt", ""), set())
        for event_call in funcset:
            event_call(read_result)


def ruuid() -> str:
    """ "Random Universally Unique ID"."""
    return str(uuid4())


def get_time() -> int:
    """Get the current time."""
    return int(time.time())


def get_raw_lstr(resource: str, fallback: str = "null") -> str:
    """Get an evaluated bs.Lstr string."""
    return bs.Lstr(resource=resource, fallback_value=fallback).evaluate()


def translate_campaignname(name: str) -> str:
    """Translate a provided campaign name."""
    return bs.Lstr(translate=("gameNames", name)).evaluate()


def translate_gamename(name: str) -> str:
    """Translate a provided game name."""
    return bs.Lstr(translate=("gameNames", name)).evaluate()


def translate_coop_levelname(name: str) -> str:
    """Translate a provided game name."""
    return bs.Lstr(translate=("coopLevelNames", name)).evaluate()


def translate_mapname(name: str) -> str:
    """Translate a provided map name."""
    return bs.Lstr(translate=("mapsNames", name)).evaluate()


class DiscordRichPresenceSubsystem(AppSubsystem):
    """System in charge of handling all things Discord Rich Presence.

    This subsystem manages Rich Presence data via ``RichPresenceThread``,
    updating our status according to active game state and
    handles reconnection in case of connection failure.
    """

    def __init__(self) -> None:
        super().__init__()
        # FIXME: this subsystem collapses if we switch appmodes...
        # no one in their right mind would do such a thing but it's
        # still pretty upsetting to watch the console flood with
        # errors as you watch the purple "Potato!" spin around the screen.

        self._thread: RichPresenceThread = RichPresenceThread()
        self._thread_timer: bs.AppTimer | None = None
        self._update_timer: bs.AppTimer | None = None
        self._session_update_timer: bs.AppTimer | None = None

        self._last_session_context: str | None = None
        self._last_activity_status_data: str | None = None
        self._last_activity_status_time: float = 0.0

        self._launch_time: int = get_time()

        self.r = "discordrp"
        self.activity_status: ActivityStatus = (
            self.get_default_activity_status()
        )
        self._activity_assets: StatusAssets = StatusAssets(
            large_image=StatusResources.LOGO.value,
            invite_cover_image=StatusResources.COVER.value,
        )
        self._activity_secrets: StatusSecrets = StatusSecrets()
        self._activity_party: StatusParty = StatusParty()
        self._activity_timestamps: StatusTimestamps = StatusTimestamps(
            start=get_time()
        )
        self._regenerate_secrets()

        self.activity_status.assets = self._activity_assets
        self.activity_status.secrets = self._activity_secrets
        self.activity_status.party = self._activity_party
        self.activity_status.timestamps = self._activity_timestamps

        self.server_dict: dict[str, dict] = {}
        self._last_server_fetch_time: float = 0.0
        self._last_server_data: str | None = None
        self._server_info: dict | None = None
        self._server_list_update_timer: bs.AppTimer | None = None

    def get_default_activity_status(self) -> ActivityStatus:
        """Return a default presence status state."""
        return ActivityStatus(
            name=get_raw_lstr("titleText"),  # 'BombSquad'
            application_id=APP_CLIENT_ID,
            type=StatusType.PLAYING,
            created_at=self._launch_time,
        )

    def _regenerate_secrets(self) -> None:
        # generate new match and party secrets.
        # the match secret allows people to join via the
        # "Invite <---> to play 'BombSquad'" chat button,
        # while the party secret relates to direct join requests.

        self._match_id = ruuid()
        self._party_id = ruuid()
        # these should never persist for more than one session.
        self._activity_secrets.match = self._match_id
        self._activity_party.id = self._party_id

    def on_app_running(self) -> None:
        """Start automatically when our app reaches running state,
        making sure we don't load up when other subsystems are unavailable.
        """
        self._get_public_address()

        if AUTO_START:
            self.start()

    def start(self) -> None:
        """Start executing our Rich Presence thread."""
        if self._thread.state is ThreadState.ACTIVE:
            _log("subsystem").warning(
                '"start()" called while already running.', stack_info=True
            )
            return

        classic = bs.app.classic
        if classic is None:
            _log("subsystem").info(
                '"bs.app.classic" is None, can\'t launch Discord Rich Presence!'
            )
            return
        if is_server() is True:
            _log("subsystem").info(
                "Discord Rich Presence won't launch in server mode."
            )
            return
        if not classic.platform in ("windows", "mac", "linux"):
            _log("subsystem").info(
                "Discord Rich Presence can run in desktop platforms only."
            )
            return

        self._last_activity_status_data = None
        self._last_session_context = None
        self._last_activity_status_time = 0.0
        # NOTE: should we reset this? server fetching is pretty
        # unrelated to the rest of the subsystem...
        # self._last_server_fetch_time = 0.0

        with bs.ContextRef.empty():
            # threads can only be initiated once, so...
            self._thread = RichPresenceThread()
            self._thread.start()
            self._thread_timer = bs.AppTimer(
                0.33,
                bs.CallStrict(self._thread_init_check),
                repeat=True,
            )

    def stop(self) -> None:
        """Stop our Rich Presence thread."""
        if self._thread_timer is None:
            # trying to stop while stopped...
            # there's a chance this happens while quitting and
            # the thread is down, so no biggie.
            return

        self._thread_timer = None
        self._update_timer = None
        self._session_update_timer = None
        self._thread.stop()
        _log("subsystem").info("'DiscordRPSubsystem' & thread stopped.")

    def _reset_status(self) -> None:
        self.activity_status: ActivityStatus = (
            self.get_default_activity_status()
        )
        self._activity_party = StatusParty()
        self._activity_assets: StatusAssets = StatusAssets()
        # we preserve secrets and party data and re-apply them.
        self.activity_status.assets = self._activity_assets
        self.activity_status.secrets = self._activity_secrets
        self.activity_status.party = self._activity_party
        self.activity_status.timestamps = self._activity_timestamps
        _log("subsystem").debug("status has been reset")
        self.update_party_size()

    def tick(self) -> None:
        """Check for any changes and update whenever it is required."""
        session: bs.Session | None = bs.get_foreground_host_session()
        # only do a session check if our session has changed.
        if not self._session_has_changed(session):
            return

        self._reset_status()
        self._server_list_update_timer = bs.AppTimer(
            2.33, self._get_server_list
        )
        self._last_server_data = None
        self._server_info = None
        self._session_update_timer = None
        _log("subsystem").debug("subsystem tick update")

        if not isinstance(bs.app.mode, ClassicAppMode):
            self.in_some_session()
            return

        # TODO: make a dedicated data class and that allows users
        # to call their functions when a specific session is detected.
        match session:
            case MainMenuSession():
                self.in_main_menu_session()
            case CoopSession() | MultiTeamSession():
                # 'MultiTeamSession' accomodates for both FFA and Teams.
                self.in_game_session()
            case _:
                # not having a session means we're either
                # watching a replay, running a stress test
                # or at an online game...
                if bs.is_in_replay():
                    self.in_replay_session()
                elif bs.get_foreground_host_session() is not None:
                    self.in_benchmark_session()
                else:
                    self.in_online_session()

    def _session_has_changed(
        self, session: bs.Session | None, update_last: bool = True
    ) -> bool:
        has_changed: bool = False

        ctx: str = "None"
        if session is not None:
            ctx = str(session)
        if self._last_session_context != ctx:
            _log("subsystem").debug('"_session_has_changed()" pass')
            has_changed = True
        if update_last:
            self._last_session_context = ctx

        return has_changed

    def in_main_menu_session(self) -> None:
        """We're at the Main Menu, display relevant information."""
        self._create_session_timer(self.in_main_menu_session, 2.0)
        _log("subsystem").debug("main menu session tick")

        self.update_party_size()

        res_sub: str = "generic"
        main_window: bui.MainWindow | None = bs.app.ui_v1.get_main_window()
        # we have some special main menu descriptions depending
        # on what we're currently looking at.
        match main_window:
            case DocUIWindow():
                # i despise DocUI so much...
                match main_window.controller:
                    case StoreUIController():
                        res_sub = "store"
                    case LeaguePresidencyUIController():
                        res_sub = "ranking"
                    case InventoryUIController():
                        res_sub = "inventory"
            case PlayWindow():
                res_sub = "play"
            case CoopBrowserWindow():
                res_sub = "coop"
            case PlaylistBrowserWindow():
                # pylint: disable=protected-access
                res_sub = (
                    "teams"
                    if main_window._sessiontype
                    in [MultiTeamSession, DualTeamSession]
                    else (
                        "ffa"
                        if main_window._sessiontype == FreeForAllSession
                        else "generic"
                    )
                )
            case EditProfileWindow():
                # pylint: disable=protected-access
                res_sub = "profile_" + (
                    "edit"
                    if main_window._existing_profile is not None
                    else "new"
                )
            case GatherWindow():
                res_sub = "gather"
            case (  # holy behemoth of a case statement
                bscfgm0.AdvancedSettingsWindow()
                | bscfgm1.AllSettingsWindow()
                | bscfgm2.AudioSettingsWindow()
                | bscfgm3.BenchmarksAndStressTestsWindow()
                | bscfgm4.ControlsSettingsWindow()
                | bscfgm5.DevToolsWindow()
                | bscfgm6.GamepadSettingsWindow()
                | bscfgm6.AwaitGamepadInputWindow()
                | bscfgm7.GamepadAdvancedSettingsWindow()
                | bscfgm8.GamepadSelectWindow()
                | bscfgm9.GraphicsSettingsWindow()
                | bscfgmA.ConfigKeyboardWindow()
                | bscfgmA.AwaitKeyboardInputWindow()
                | bscfgmB.TestingWindow()
                | bscfgmB.NetTestingWindow()
                | bscfgmC.PluginWindow()
                | bscfgmD.PluginSettingsWindow()
                | bscfgmE.RemoteAppSettingsWindow()
                | bscfgmF.TestingWindow()
                | bscfgmG.TouchscreenSettingsWindow()
                | bscfgmH.TestingWindow()
                | bscfgmH.VRTestingWindow()
            ):
                res_sub = "settings"
            case WatchWindow():
                res_sub = "watch"
            case AchievementsWindow():
                res_sub = "achievements"
            case LeagueRankWindow():
                res_sub = "ranking"
        details_resource: str = f"{self.r}.details.main_menu.{res_sub}"

        self.activity_status.details = get_raw_lstr(details_resource)

        assert self.activity_status.assets
        self.activity_status.assets.large_image = StatusResources.LOGO.value

        self.update_status()

    def in_game_session(self) -> None:
        """Show relevant info. about our active game session.

        In this case, we'll show the current map we'll playing at, as well
        as the current mode / campaign level and activity type.
        """
        self._create_session_timer(self.in_game_session, 3.0)
        _log("subsystem").debug("game session tick")
        self.update_party_size()
        self.in_game_party_size()

        large_image: str = StatusResources.LOGO.value
        large_text: str | None = None
        details_text: str = get_raw_lstr(
            f"{self.r}.details.lobby"
        )  # Waiting in lobby

        small_image: str | None = None
        small_text: str | None = None

        is_lobby: bool = False

        def update():
            self.activity_status.details = details_text
            assert self.activity_status.assets
            self.activity_status.assets.large_image = large_image
            self.activity_status.assets.large_text = large_text
            self.activity_status.assets.small_image = small_image
            self.activity_status.assets.small_text = small_text
            self.update_status()

        activity: bs.Activity | None = bs.get_foreground_host_activity()
        session: bs.Session | None = bs.get_foreground_host_session()
        match activity:
            case bs.JoinActivity() | TutorialActivity():
                is_lobby = True
                large_image = StatusResources.LOBBY.value
                large_text = "Lobby"

            case bs.GameActivity():
                large_image = self.get_activity_map_thumbnail()
                large_text = translate_mapname(activity.map.name)
                details_text = translate_gamename(activity.getname())

            case TransitionActivity() | bs.ScoreScreenActivity():
                # if we're transitioning between activities, don't do nun'.
                return

        match session:
            case bs.CoopSession():
                small_image = StatusResources.COOP.value
                mode_name = get_raw_lstr(f"{self.r}.session.coop")
                # provide the mode & campaign names as small text
                if not is_lobby:
                    details_text = translate_coop_levelname(
                        session.campaign_level_name
                    )
                campaign = session.campaign
                if campaign:
                    mode_name = get_raw_lstr(f"{self.r}.session.coop_short")
                    campaign_name = translate_campaignname(campaign.name)
                    small_text = f"{mode_name}: {campaign_name}"
                else:
                    small_text = mode_name

            case bs.FreeForAllSession():
                small_image = StatusResources.FFA.value
                small_text = get_raw_lstr(f"{self.r}.session.ffa")

            case bs.DualTeamSession() | bs.MultiTeamSession():
                small_image = StatusResources.TEAMS.value
                small_text = get_raw_lstr(f"{self.r}.session.teams")

        update()

    # FIXME: these remain unused until we need to implement them, AKA
    # adding functions to allow for further function modifications.
    def in_coop_session(self) -> None:
        """Show relevant info. about our running coop game."""

    def in_ffa_session(self) -> None:
        """Show relevant info. about our running FFA game."""

    def in_teams_session(self) -> None:
        """Show relevant info. about our running teams game."""

    def in_replay_session(self) -> None:
        """Show relevant info. about the replay we're watching."""
        self._create_session_timer(self.in_replay_session, 4.0)
        _log("subsystem").debug("replay session tick")

        self.update_party_size()

        self.activity_status.details = get_raw_lstr(f"{self.r}.details.replay")
        assert self.activity_status.assets
        self.activity_status.assets.large_image = StatusResources.REPLAY.value

        self.update_status()

    def in_benchmark_session(self) -> None:
        """Benchmarking?"""
        self._create_session_timer(self.in_benchmark_session, 4.0)
        _log("subsystem").debug("benchmark session tick")

        self.update_party_size()

        self.update_status()

    def in_online_session(self) -> None:
        """Show information about the server we're in."""
        self._create_session_timer(self.in_online_session, 6.0)
        _log("subsystem").debug("online session tick")

        pubserver_str: str = get_raw_lstr(
            f"{self.r}.details.party.public"
        )  # 'Public Server'
        server_name: str = pubserver_str

        server_data: HostInfo | None = bs.get_connection_to_host_info_2()

        str_data = str(server_data)
        # note that the reason we do this check instead of just performing
        # this operation once is due to that slim chance the user has a
        # mod that allows them to switch servers without having to go back
        # to the main menu screen, voiding such system.
        if self._last_server_data == str_data:

            if self._server_info:
                # update player count constantly if the server is public
                party_min: int = max(1, self.get_player_count())
                party_max: int = max(1, self._server_info.get("sm", 0))
                self._activity_party.size = (party_min, party_max)

            self.update_status()
            return

        self._last_server_data = str_data

        if isinstance(server_data, HostInfo):
            _address: str = server_data.address or ""
            _port: int = server_data.port or -1
            entry = self.server_dict.get(f"{_address}&{_port}", None)
            # if we can't get this server from the public
            # server list... it is very likely private!
            if entry is None:
                # prevent ourselves from showing any more data.
                server_name = get_raw_lstr(
                    f"{self.r}.details.party.private"
                )  # 'Private Server'
            else:
                self._server_info = entry
                # show the relevant server's name and party size
                server_name = entry.get("n", pubserver_str)
                address: str = entry.get("a", "")
                port: int = entry.get("p", -1)
                party_min: int = max(1, self.get_player_count())
                party_max: int = max(1, entry.get("sm", 0))
                join_secret = str({"addr": address, "port": port})
                self._activity_secrets.join = join_secret
                self._activity_party.size = (party_min, party_max)

        self.activity_status.details = server_name
        self.activity_status.state = get_raw_lstr(
            f"{self.r}.state.online"
        )  # Online
        assert self.activity_status.assets
        self.activity_status.assets.large_image = StatusResources.LOGO.value
        self.update_status()

    def in_some_session(self) -> None:
        """We are sure in a session.
        Part of the awesome "Potato!" ``AppMode``.
        """
        self._create_session_timer(self.in_some_session, 3.0)
        _log("subsystem").debug("some session? tick")

        assert self.activity_status.assets
        self.activity_status.assets.large_image = StatusResources.POTATO.value
        self.activity_status.assets.large_text = get_raw_lstr(
            f"{self.r}.potato"
        )
        self.activity_status.details = get_raw_lstr(f"{self.r}.details.404")
        self.update_status()

    def _create_session_timer(self, call: Callable, t: float = 2.0) -> None:
        if self._session_update_timer is not None:
            return

        self._session_update_timer = bs.AppTimer(
            t,
            bs.CallPartial(self._session_persistance_before_call, call),
            repeat=True,
        )
        _log("subsystem").info(
            "session timer created for %s every %s secs.", call, t
        )

    def _session_persistance_before_call(self, call: Callable) -> None:
        # if we have changed session between update timers, quit it.
        if self._session_has_changed(
            bs.get_foreground_host_session(), update_last=False
        ):
            self._session_update_timer = None
            self.tick()
            return
        call()

    def get_player_count(self) -> int:
        """Get the player count of the current server.
        If we're not in a server, returns ``0``.
        """
        players: list[dict] = bs.get_game_roster()
        count = len(
            [
                p
                for p in players
                if
                # the spec string is stored as a string for
                # some reason; extract it into a proper dict.
                not json.loads(p.get("spec_string", "{}")).get("a", None)
                == "Server"
            ]
        )  # don't count the server itself as a player
        return count

    def update_party_size(self) -> None:
        """Update our activity status' party size."""
        if not isinstance(bs.app.mode, ClassicAppMode):
            self.update_status()
            return

        player_count = self.get_player_count()
        online = bs.get_public_party_enabled()

        # ignore this process if we're at another party
        if bs.get_connection_to_host_info_2() is not None:
            return

        if not online:
            status_text = get_raw_lstr(f"{self.r}.state.solo")
            if player_count > 1:
                # we might be doing a lan party if we have players
                # while offline, display that!
                status_text = get_raw_lstr(f"{self.r}.state.lan")
            self.activity_status.state = status_text
            self._activity_party.size = None
            return

        party_min = player_count
        party_max = bs.get_public_party_max_size()
        self.activity_status.state = get_raw_lstr(f"{self.r}.state.host")
        self._activity_party.size = (party_min, party_max)

    def in_game_party_size(self) -> None:
        """Additional party size checks when playing locally."""
        session: bs.Session | None = bs.get_foreground_host_session()

        if session is not None and len(session.sessionplayers) > 1:
            self.activity_status.state = get_raw_lstr(f"{self.r}.state.multi")

    def get_activity_map_thumbnail(self) -> str:
        """Get the thumbnail of the current game activity.

        If we're not in a ``bs.GameActivity`` or the current map has no
        assigned thumbnail, returns ``MAP_THUMBNAIL_DEFAULT``.
        """
        activity: bs.Activity | None = bs.get_foreground_host_activity()

        if isinstance(activity, bs.GameActivity):
            return (
                MAP_THUMBNAIL_DICT.get(type(activity.map), None)
                or MAP_THUMBNAIL_DEFAULT
            )
        return MAP_THUMBNAIL_DEFAULT

    def update_status(self) -> None:
        """Tell our thread to update our Rich Presence to our
        currently evaluated presence dataclass.
        """
        # we only push status updates if the data we have is
        # different to prevent ourselves from getting rate-limited.
        current_time = time.time()
        if (
            self._last_activity_status_data == str(self.activity_status)
            or self._last_activity_status_time > current_time
        ):
            return
        self._last_activity_status_time = (
            current_time + STATUS_UPDATE_RATE_LIMIT_SECS
        )
        self._last_activity_status_data = str(self.activity_status)

        data = unpack_dataclass(self.activity_status)
        _log("subsystem").debug('calling "update_status()" with %s', data)
        self._thread.set(data)

    def is_active(self) -> bool:
        """Return if our Discord Rich Presence support
        thread is currently running.
        """
        return self._thread.state is ThreadState.ACTIVE

    def _thread_init_check(self) -> None:
        """Check up on our newly created thread.
        Handles revving up our updates if the thread starts successfully
        and quitting gracefully if it fails to launch.
        """
        match self._thread.state:

            case ThreadState.ACTIVE:
                self.update_status()
                # calling "get_server_list" could cause issues with
                # the game's server list when leaving an online party
                # due to the server not liking this request being called
                # too often, so wait a little bit before asking!
                self._get_server_list()
                # FIXME: self._subscribe_to_join_events()
                self._thread_timer = bs.AppTimer(
                    0.33, self._thread_persistance_check, repeat=True
                )
                self._update_timer = bs.AppTimer(1, self.tick, repeat=True)
                _log("subsystem").info("'DiscordRPSubsystem' up and running!")

            case ThreadState.STOPPED:
                self.stop()

    def _thread_persistance_check(self) -> None:
        """Keep making sure our thread is still running.
        If the thread stops at any time, halt subsystem operations.
        """
        if self._thread.state is ThreadState.STOPPED:
            self.stop()

    def _subscribe_to_join_events(self) -> None:
        """Subscribe to discord 'events' to track
        if people request to join our party (or if they
        request to join theirs.)
        """
        # https://discord.com/developers/docs/topics/rpc#payloads
        # https://discord.com/developers/docs/topics/rpc#commands-and-events
        # FIXME: doing this hangs the main presence loop, gotta make
        # our own asynced event interceptors.
        for evt in ["ACTIVITY_JOIN", "ACTIVITY_JOIN_REQUEST"]:
            self._thread.send_payload(
                {
                    "nonce": ruuid(),
                    "cmd": "SUBSCRIBE",
                    "evt": evt,
                },
                _OpCode.FRAME,
            )

    @staticmethod
    # @RichPresenceThread.subscribe_event("ACTIVITY_JOIN_REQUEST")
    def on_presence_join_request(request: dict) -> None:
        """We got a request for someone to join our party."""
        # https://discord.com/developers/docs/topics/rpc#activityjoinrequest-example-activity-join-request-dispatch-payload

        # because this function gets called from the thread loop, we
        # cannot preserve our instance for variables, but it shouldn't
        # matter since it's a one-off trick.
        data = request.get("user", {})
        _uid = data.get("id", None)
        username = data.get("username", None)
        _discriminator = data.get("discriminator", None)
        _avatar = data.get("avatar", None)

        bs.screenmessage(f"{username} wants to join your game!")

    @staticmethod
    # @RichPresenceThread.subscribe_event("ACTIVITY_JOIN")
    def on_presence_join(request: dict) -> None:
        """We got a request to join someone's party."""
        # https://discord.com/developers/docs/topics/rpc#activityjoin-example-activity-join-dispatch-payload

        # because this function gets called from the thread loop, we
        # cannot preserve our instance for variables, but it shouldn't
        # matter since it's a one-off trick.
        secret = request.get("data", {}).get("secret", None)
        # FIXME: read ``cls._got_address()``'s fixme.
        info: dict = ast.literal_eval(secret)

        address = info.get("addr", None)
        port = info.get("port", None)
        if not address or not port:
            return

        bs.connect_to_party(
            address=address,
            port=port,
            print_progress=True,
        )

    def _get_public_address(self) -> None:
        AddrFetchThread(bs.WeakCallPartial(self._got_address)).start()

    def _got_address(self, ip: str) -> None:
        # FIXME: we're storing our address directly into the secret..
        # which we shouldn't do at all...
        # rewrite this chunk of code once we get a master server runnning.
        port = bs.get_game_port()
        if port == -1:
            # we get -1 if the engine hasn't decided the port, but
            # there's a likely chance it's gonna be 43210...
            port = 43210
        join_secret = str({"addr": ip, "port": port})
        self._activity_secrets.join = join_secret

    def _get_server_list(self) -> None:
        """Get the server list every now and then to provide
        accurate presence information about a server we're in.
        """
        t = get_time()
        if self._last_server_fetch_time > t:
            # don't fetch too often to avoid performance issues
            return
        self._last_server_fetch_time = t + SERVER_FETCH_SECS

        assert bs.app.plus
        bs.app.plus.add_v1_account_transaction(
            {
                "type": "PUBLIC_PARTY_QUERY",
                "proto": bs.protocol_version(),
                "lang": bui.app.lang.language,
            },
            callback=bs.CallPartial(self._on_server_list_fetch),
        )
        bs.app.plus.run_v1_account_transactions()
        _log("subsystem").debug("fetching server list...")

    def _on_server_list_fetch(self, data: dict) -> None:
        if data is None:
            return

        serverlist: list = data.get("l", [])
        servers: dict[str, dict] = {}
        # we reorganize the server list into a pretty dict we
        # can use to quickly get data from a server using
        # it's address and port.
        for entry in serverlist:
            entry: dict[str, Any]
            address = entry.get("a", None)
            port = entry.get("p", None)
            if address and port:
                servers[f"{address}&{port}"] = entry
        self.server_dict = servers.copy()
        _log("subsystem").debug(
            "server list got!\npassed with %s servers", len(servers)
        )

    def on_app_shutdown(self) -> None:
        """Stop our Rich Presence once the game goes into shutdown."""
        self.stop()


def unpack_dataclass(dclass: Any) -> dict[str, Any]:
    """Recursively transform dataclasses into dicts."""
    data = dataclass_to_dict(dclass)
    # remove empty dict entries
    # to appease discord's api
    return walk_dir_cleanse(data)


def walk_dir_cleanse(d: dict) -> dict:
    """Remove any empty values from a dict recursively."""
    for i, v in d.copy().items():
        if not v:
            d.pop(i)
        elif isinstance(v, dict):
            walk_dir_cleanse(v)
    return d
