"""Queue servers in the background."""

# FIXME: Unfinished module

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, override
from babase._appsubsystem import AppSubsystem

import bascenev1 as bs
import bauiv1 as bui

from bascenev1lib.mainmenu import MainMenuActivity
from bauiv1lib.gather.publictab import PartyEntry

from fusecore.utils import NodeAlignment
from fusecore._tools import is_server

from .common import CORE_FOLDER_NAME

PERSISTENCY_CHECK_TIME: float = 0.012

NO_QUEUE_CONNECTION_ATTEMPTS: int = 24

CUSTOMDATA_UI_ENTRY = "fuse:_serverqueueuielement"
"""Name ID to use when injecting our UI element in an activity."""
PRESERVE_UI = False
"""Do we show the queue UI on replays?"""

ASSET_PATH: str = f"{CORE_FOLDER_NAME}/serverqueue"


@dataclass
class NoActivityMsg: ...


@dataclass
class ServerInfo:
    """Minimal server info. to serve our UI with."""

    name: str
    queue: str | None


class QueueStatus(Enum):
    """Queue status."""

    NONE = 0
    IN_QUEUE = 1
    JOINING = 2
    NO_QUEUE = 3


class QuitReason(Enum):
    """Reasons we stopped our queue process."""

    UNKNOWN = 0
    STOPPED = 1
    FAILED = 2
    QUIT = 3


class ServerQueueSubsystem(AppSubsystem):
    """Our subsystem to manage joining."""

    def __init__(self) -> None:
        self.server_info: ServerInfo | None = None
        self.status: QueueStatus = QueueStatus.NONE

        self._activity_hash: str = ""
        self._session_hash: str = ""
        self.persistency_check_timer: bs.AppTimer | None = None

    @override
    def on_app_running(self) -> None:
        # don't bother if we're running in a server environment.
        # fun fact! servers *usually* cannot queue to other servers.
        if is_server():
            return

        self.server_info = ServerInfo("Public Party", None)

    @override
    def on_app_shutdown(self) -> None:
        self.queue_leave(reason=QuitReason.QUIT)

    def _active_queue(self) -> bool:
        return (
            not self.status is QueueStatus.NONE and self.server_info is not None
        )

    def persistency_check(self) -> None:
        """Check if our activity and session have changed by hashing them repeatedly."""
        if self.status is QueueStatus.NONE:
            return

        # TODO: kind of afraid that this might affect
        # performance, even if just a little...
        ui_element = self._get_ui_element()

        if isinstance(ui_element, NoActivityMsg) or ui_element is not None:
            return

        if self._active_queue():
            self.ui_update()

    def queue_join(self) -> None:
        """Queue ourselves into a server and show a pretty interface for it."""
        # some old and special servers don't allow for queues, create a
        # timer of our own and attempt connection a couple times for those.
        self.status = QueueStatus.IN_QUEUE

        self.persistency_check_timer = bs.AppTimer(
            PERSISTENCY_CHECK_TIME,
            bs.CallPartial(self.persistency_check),
            repeat=True,
        )

        self.ui_create(do_intro=True)

    def queue_leave(
        self,
        reason: QuitReason | None = QuitReason.STOPPED,
    ) -> None:
        """Leave our active queue and remove our pretty interface.

        The reason will default to 'ServerQueueQuitReason.STOPPED' under the
        assumption that this function is called by the user with the intent
        of cancelling queueing.
        Errors should provide a unique reason enum.

        The reason can be set to 'None' and will not show a message if so.
        This should only be done with debugging tools or in very specific
        circumstances where you don't want to bother the user with a message.
        """
        self.server_info = None
        self.status = QueueStatus.NONE
        self.persistency_check_timer = None

        silent = reason is QuitReason.QUIT
        if reason is not None and not silent:
            self.show_quit_reason(reason)

        self.ui_delete(silent=silent)

    def show_quit_reason(self, reason: QuitReason | None) -> None:
        """Show a message with the reason we stopped queuing."""
        r = "serverqueue.messages.quit_by"
        lstr: bs.Lstr = bs.Lstr(resource=f"{r}.other")

        match reason:
            case QuitReason.UNKNOWN:
                ...
            case QuitReason.STOPPED:
                lstr = bs.Lstr(resource=f"{r}.cancel")
            case QuitReason.FAILED:
                lstr = bs.Lstr(resource=f"{r}.failure")

        bui.screenmessage(lstr, color=(1, 0.15, 0.15))

    def ui_create(self, do_intro: bool = False) -> None:
        """Create our pop-up display.

        This is called when our system first starts and
        when changing activities to keep it as up-to-date as possible.
        """
        activity: bs.Activity | None = bs.get_foreground_host_activity()

        if activity is None or self.server_info is None:
            return

        with activity.context:
            activity.customdata[CUSTOMDATA_UI_ENTRY] = ServerQueueUIElement(
                self.server_info,
                (-145, 50),
                NodeAlignment.BOTTOM_RIGHT,
                queue_status=self.status,
                do_intro=do_intro,
            )

        self.ui_update()

    def ui_update(self) -> None:
        """Update our pop-up display."""
        if not self._active_queue():
            raise RuntimeError("'ui_update' called with no active queue.")
        assert self.server_info

        ui_element = self._get_ui_element()

        if isinstance(ui_element, NoActivityMsg):
            return

        if ui_element is None:
            # this will set our UI element with
            # the proper server queue information
            return self.ui_create()

        return ui_element.update(self.server_info, self.status)

    def ui_animate(self) -> None:
        """Miscelaneous."""

    def ui_delete(self, silent: bool = False) -> None:
        """Delete our pop-up display."""
        activity = bs.get_foreground_host_activity()
        if activity is None:
            return

        ui_element = self._get_ui_element()
        if isinstance(ui_element, ServerQueueUIElement):
            activity.customdata[CUSTOMDATA_UI_ENTRY].delete(silent=silent)
            activity.customdata[CUSTOMDATA_UI_ENTRY] = None

    def _get_ui_element(self) -> ServerQueueUIElement | NoActivityMsg | None:
        activity = bs.get_foreground_host_activity()
        if activity is None:
            return NoActivityMsg()

        return activity.customdata.get(CUSTOMDATA_UI_ENTRY, None)

    def _on_server_queue_response(self, response) -> None: ...


UI_ICON_LAST_FRAME: int = 0


class ServerQueueUIElement(bs.Actor):
    """An in-game display about our current queue."""

    def __init__(
        self,
        server_info: ServerInfo,
        position: tuple[float, float] = (0, 0),
        align: NodeAlignment = NodeAlignment.BOTTOM_RIGHT,
        queue_status: QueueStatus = QueueStatus.NONE,
        do_intro: bool = False,
    ) -> None:
        self.node_elements: dict[str, bs.NodeActor] = {}
        self.node_defaults: dict[str, dict[str, Any]] = {}
        self.misc_elements: dict[str, Any] = {}
        self.position = position
        self.align = align

        self.sound_start: bui.Sound = bui.getsound(f"{ASSET_PATH}/start_queue")
        self.sound_join: bui.Sound = bui.getsound(f"{ASSET_PATH}/join_attempt")
        self.sound_leave: bui.Sound = bui.getsound("shieldDown")
        self.icon_tex: list[bs.Texture] | None = [
            bs.gettexture(f"spinner{i}") for i in range(12)
        ]
        self.icon_frame: int = UI_ICON_LAST_FRAME

        self.server_info = server_info
        self.queue_status = queue_status

        super().__init__()
        self._create(do_intro)
        if do_intro:
            self._animate_intro()
            if isinstance(self.activity, MainMenuActivity):
                bs.apptimer(3, self._animate_hide)

    def _create(self, intro: bool = False) -> None:
        def e_scale(scale: float) -> tuple[float, float]:
            return (1 * scale, 1 * scale)

        host_only = not PRESERVE_UI

        assert self.icon_tex
        x, y = self.position
        self.node_defaults["backdrop"] = d = {
            "position": (x, y - 2),
            "opacity": 0.65,
        }
        self.node_elements["backdrop"] = bs.NodeActor(
            bs.newnode(
                "image",
                attrs={
                    "host_only": host_only,
                    "texture": bs.gettexture("clayStroke"),
                    "position": (x, y - 2),
                    "scale": (280, 125),
                    "rotate": -1.23,
                    "color": (0, 0, 0),
                    "opacity": 0 if intro else d["opacity"],
                    "front": True,
                    "attach": self.align.get_attach(),
                },
            )
        )
        self.node_defaults["spinner"] = d = {
            "position": (x - 100, y),
            "opacity": 1,
        }
        self.node_elements["spinner"] = bs.NodeActor(
            bs.newnode(
                "image",
                attrs={
                    "host_only": host_only,
                    "texture": self.icon_tex[self.icon_frame],
                    "position": (x - 100, y),
                    "scale": e_scale(40),
                    "color": (1, 1, 1),
                    "opacity": 0 if intro else d["opacity"],
                    "front": True,
                    "attach": self.align.get_attach(),
                },
            )
        )
        # Use a weak callback so the timer does not keep a strong
        # reference to this UI element and prevent it from dying.
        self.misc_elements["spinner_anim"] = bui.AppTimer(
            1 / 16, bui.WeakCallStrict(self._do_icon_spin), repeat=True
        )
        self.node_defaults["label_server"] = d = {
            "position": (x - 75, y + 8),
            "opacity": 1,
        }
        self.node_elements["label_server"] = bs.NodeActor(
            bs.newnode(
                "text",
                attrs={
                    "host_only": host_only,
                    "text": self.server_info.name,
                    "position": (x - 75, y + 8),
                    "scale": 0.9,
                    "maxwidth": 175,
                    "flatness": 0.0,
                    "color": (1, 1, 1, 1),
                    "opacity": 0 if intro else d["opacity"],
                    "shadow": 1.0,
                    "front": True,
                    "h_align": "left",
                    "v_align": "center",
                    "h_attach": self.align.get_h_attach(),
                    "v_attach": self.align.get_v_attach(),
                },
            )
        )
        self.node_defaults["label_status"] = d = {
            "position": (x - 75, y - 12),
            "opacity": 1,
        }
        self.node_elements["label_status"] = bs.NodeActor(
            bs.newnode(
                "text",
                attrs={
                    "host_only": host_only,
                    "text": "Waiting in queue... (2/12)",
                    "position": (x - 75, y - 12),
                    "scale": 0.65,
                    "maxwidth": 250,
                    "flatness": 0.0,
                    "color": (1, 1, 1, 1),
                    "opacity": 0 if intro else d["opacity"],
                    "shadow": 1.0,
                    "front": True,
                    "h_align": "left",
                    "v_align": "center",
                    "h_attach": self.align.get_h_attach(),
                    "v_attach": self.align.get_v_attach(),
                },
            )
        )

    def _animate_intro(self) -> None:
        self.sound_start.play()
        # animate a quick fade-in for all node actors we created.
        for name, actor in self.node_elements.items():
            if not isinstance(actor, bs.NodeActor):
                continue
            if not actor.node:
                continue
            default_opacity = self.node_defaults.get(name, {}).get("opacity", 1)
            bs.animate(
                actor.node,
                "opacity",
                {0.0: 0.0, 0.2: 0.0, 0.75: default_opacity},
            )

    def _animate_hide(self) -> None:
        for name, element in self.node_elements.items():
            if not isinstance(element, bs.NodeActor):
                continue
            node = element.node
            if not node:
                continue
            x, y = self.node_defaults.get(name, {}).get(
                "position", (self.position)
            )
            bs.animate_array(
                node,
                "position",
                2,
                {
                    0.0: (x, y),
                    0.2: (x + 65, y),
                    0.4: (x + 175, y),
                    0.6: (x + 350, y),
                },
            )

    def _animate_show(self) -> None:
        for name, element in self.node_elements.items():
            if not isinstance(element, bs.NodeActor):
                continue
            node = element.node
            if not node:
                continue
            x, y = self.node_defaults.get(name, {}).get(
                "position", (self.position)
            )
            bs.animate_array(
                node,
                "position",
                2,
                {0.0: (x + 350, y), 0.3: (x + 175, y), 0.5: (x, y)},
            )

    def _do_icon_spin(self) -> None:
        if (
            self.icon_tex is None
            or self.node_elements.get("spinner", None) is None
        ):
            return

        frame = (self.icon_frame + 1) % len(self.icon_tex)
        self.node_elements["spinner"].node.texture = self.icon_tex[frame]

        global UI_ICON_LAST_FRAME  # pylint: disable=global-statement
        UI_ICON_LAST_FRAME = self.icon_frame = frame

    def update(self, server_info: ServerInfo, status: QueueStatus) -> None:
        """Update our server info and queue status data."""
        self.server_info = server_info
        self.queue_status = status

        self._update_text()

    def _update_text(self) -> None:
        self.node_elements["label_server"].node.text = self.server_info.name
        self.node_elements["label_status"].node.text = self._get_status_text()

    def _get_status_text(self) -> bs.Lstr | str:
        return bs.Lstr(resource="serverqueue.status.in_queue")

    def delete(self, silent: bool = False) -> None:
        """Delete the node contents of this actor."""
        if not silent:
            self.sound_leave.play()
        self.on_expire()

    @override
    def on_expire(self) -> None:
        self.node_elements.clear()
        self.icon_tex = None
        self.sound_start = None
        self.sound_join = None
        self.sound_leave = None
