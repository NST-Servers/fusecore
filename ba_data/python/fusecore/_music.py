"""Module to inject our own music entries into base BombSquad."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any, Optional, Type, Union

import babase
import bascenev1 as bs

from baclassic._music import (
    ASSET_SOUNDTRACK_ENTRIES,
    AssetSoundtrackEntry,
    MusicPlayMode,
    MusicSubsystem,
)
from bascenev1._music import MusicType

# FIXME: improve docs


@dataclass
class MusicEntry:
    """A music entry applicable to an enum."""

    name: str
    soundtrack_entry: AssetSoundtrackEntry

    def __post_init__(self) -> None:
        self._id = f"{__file__}:{self.name}"

    def get_internal_id(self) -> str:
        """Return this track's ID."""
        return self._id


class FuseMusicType(Enum):
    """FuseCore base music type."""

    MY_TRACK = MusicEntry(
        "MyTrack", AssetSoundtrackEntry("spazScream01", loop=False)
    )
    MY_SECOND_TRACK = MusicEntry(
        "MySecondTrack", AssetSoundtrackEntry("spazScream01")
    )


# We'd register this enum like this:
# register_musicentry_enum(FuseMusicType)


class MusicActions:
    """System to call for music.

    Similar to ``bs.setmusic``, we instance this class
    in the core of our module to call for music changes quickly.
    """

    @staticmethod
    def setmusic(
        musictype: Union[MusicType, FuseMusicType, Any, None],
        continuous: bool = False,
    ) -> None:
        """Set the app to play (or stop playing) a certain type of music.

        This function will handle loading and playing sound assets as
        necessary, and also supports custom user soundtracks on specific
        platforms so the user can override particular game music with their
        own.

        Pass ``None`` to stop music.

        if ``continuous`` is True and musictype is the same as what is
        already playing, the playing track will not be restarted.
        """
        # All we do here now is set a few music attrs on the current globals
        # node. The foreground globals' current playing music then gets fed to
        # the do_play_music call in our music controller. This way we can
        # seamlessly support custom soundtracks in replays/etc since we're being
        # driven purely by node data.
        title: str = ""
        if isinstance(musictype, FuseMusicType):
            title = musictype.value.get_internal_id()
        elif isinstance(musictype, MusicType):
            title = musictype.value

        gnode = bs.getactivity().globalsnode
        gnode.music_continuous = continuous
        gnode.music = title
        gnode.music_count += 1


class FuseCoreMusicSubsystemPatch(MusicSubsystem):
    """FuseCore music subsystem branch."""

    def do_play_music(
        self: MusicSubsystem,
        musictype: Union[MusicType, FuseMusicType, MusicEntry, str, None],
        continuous: bool = False,
        mode: MusicPlayMode = MusicPlayMode.REGULAR,
        testsoundtrack: Optional[dict[str, Any]] = None,
    ) -> None:
        """Plays the requested music type/mode.

        For most cases, setmusic() is the proper call to use, which itself
        calls this. Certain cases, however, such as soundtrack testing, may
        require calling this directly.
        """

        if musictype is not None:
            # patch happens here!
            validated = False
            if isinstance(musictype, str):
                # if we got a string, look for any tracks matching
                # the string provided.
                musictype = _find_track_by_name(musictype)
                validated = True
            elif isinstance(musictype, Enum):
                validated = True
            if not validated:
                logging.warning("hm", exc_info=True)
                musictype = None

        with babase.ContextRef.empty():
            # If they don't want to restart music and we're already
            # playing what's requested, we're done.
            if continuous and self.music_types[mode] is musictype:
                return
            assert isinstance(musictype, MusicType)  # lying
            self.music_types[mode] = musictype

            # If the OS tells us there's currently music playing,
            # all our operations default to playing nothing.
            if babase.is_os_playing_music():
                musictype = None

            # If we're not in the mode this music is being set for,
            # don't actually change what's playing.
            if mode != self._music_mode:
                return

            # Some platforms have a special music-player for things like iTunes
            # soundtracks, mp3s, etc. if this is the case, attempt to grab an
            # entry for this music-type, and if we have one, have the
            # music-player play it.  If not, we'll play game music ourself.
            if musictype is not None and self._music_player_type is not None:
                if testsoundtrack is not None:
                    soundtrack = testsoundtrack
                else:
                    soundtrack = self._get_user_soundtrack()
                # FIXME: implement soundtrack support for musicentry enums
                entry = soundtrack.get(musictype.value)
            else:
                entry = None

            # Go through music-player.
            if entry is not None:
                self._play_music_player_music(entry)

            # Handle via internal music.
            else:
                self._play_internal_music(musictype)


def register_musicentry_enum(cls: Type[Enum]) -> None:
    """Register a MusicEntry enum into the game's soundtrack dict."""
    for e in cls:
        # ignore enum entries with no set "MusicEntry"
        if not hasattr(e, "value") or not isinstance(e.value, MusicEntry):
            print(f"ig {e}")
            continue
        enum_entry = e
        assert isinstance(enum_entry, MusicType)
        ASSET_SOUNDTRACK_ENTRIES[enum_entry] = e.value.soundtrack_entry


def test_music() -> None:
    """Test custom music."""
    register_musicentry_enum(FuseMusicType)
    MusicActions.setmusic(FuseMusicType.MY_TRACK)


def _find_track_by_name(t: str) -> Union[MusicType, FuseMusicType, None]:
    # try getting from our vanilla list
    try:
        return MusicType(t)
    except ValueError:
        ...
    # fetch from our fusecore list
    for ftrack in FuseMusicType:
        if t == ftrack.value.get_internal_id() or t == ftrack.value.name:
            return ftrack
    logging.warning('invalid music type name: "%s"', t, stack_info=True)
    return None


MusicSubsystem.do_play_music = FuseCoreMusicSubsystemPatch.do_play_music
