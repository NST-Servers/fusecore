"""Default information classes for config. toml inputs."""

from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Union

# pylint: disable=missing-class-docstring


@dataclass
class ServerSettings:
    auth_players: bool = True
    party_size: int = 8
    max_players: int = 12
    rejoin_cooldown: float = 10.0
    protocol: int = 35
    enable_queue: bool = True


@dataclass
class ServerConfig:
    address_ipv4: Optional[str] = None
    address_ipv6: Optional[str] = None
    port: int = 43210
    settings: ServerSettings = field(default_factory=ServerSettings)


@dataclass
class PlaylistDaily:
    monday: Optional[int] = None
    tuesday: Optional[int] = None
    wednesday: Optional[int] = None
    thursday: Optional[int] = None
    friday: Optional[int] = None
    saturday: Optional[int] = None
    sunday: Optional[int] = None


@dataclass
class PlaylistSettings:
    show_tutorial: bool = False
    balance_team_joins: bool = True


@dataclass
class PlaylistTeams:
    series_length: int = 7
    team_names: Optional[tuple[str, str]] = None
    team_colors: Optional[
        tuple[tuple[float, float, float], tuple[float, float, float]]
    ] = None


@dataclass
class PlaylistFFA:
    series_length: int = 27


@dataclass
class PlaylistCoop:
    enabled: bool = False
    campaign: str = "Easy"
    level: str = "Onslaught Training"


@dataclass
class PlaylistConfig:
    default: Union[int, Literal["ffa", "teams"], dict[str, Any]] = "ffa"
    shuffle: bool = False
    playlist_mode: Literal["none", "daily", "random"] = "none"
    daily: PlaylistDaily = field(default_factory=PlaylistDaily)
    random: list[int | Literal["ffa", "teams"] | dict[str, Any]] = field(
        default_factory=list
    )
    settings: PlaylistSettings = field(default_factory=PlaylistSettings)
    teams: PlaylistTeams = field(default_factory=PlaylistTeams)
    ffa: PlaylistFFA = field(default_factory=PlaylistFFA)
    coop: PlaylistCoop = field(default_factory=PlaylistCoop)


@dataclass
class ShutdownConfig:
    clean_mins: int = 0
    force_mins: int = 0
    idle_mins: int = 0


@dataclass
class DebugConfig:
    enabled: bool = False
    no_bytecode: bool = False
    log_levels: dict[str, str] = field(default_factory=dict)


@dataclass
class ServerTOML:
    name: str = "My FuseCore Server"
    motd: str = "Welcome to my server!"
    stats_url: Optional[str] = None
    server: ServerConfig = field(default_factory=ServerConfig)
    playlist: PlaylistConfig = field(default_factory=PlaylistConfig)
    shutdown: ShutdownConfig = field(default_factory=ShutdownConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)


@dataclass
class AdminEntry:
    account_id: Optional[str] = None
    """Account ID of this user."""
    ballistica_id: Optional[str] = None
    """Ballistica ID of this user."""


@dataclass
class BanEntry:
    account_id: Optional[str] = None
    """Account ID of the blacklisted user."""
    ballistica_id: Optional[str] = None
    """Ballistica ID of the blacklister user."""
    address_ipv4: Optional[str] = None
    """IPv4 address to blacklist."""
    address_ipv6: Optional[str] = None
    """IPv6 address to blacklist."""
    reason: Optional[str] = None
    """Motive for the ban.
    Include offense and important notes of the user.
    """
    unix_start: int = 0
    """Unix timestamp of when the ban was applied."""
    unix_end: int = 0
    """Unix timestamp of when the ban will expire."""


class RoleEntry:
    name: str = "My Role"
