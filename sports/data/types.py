"""Tipos compartidos para partidos, equipos y lesiones."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Injury:
    player: str
    team_id: str
    team_name: str
    status: str
    position: str = ""
    detail: str = ""


@dataclass
class RecentGame:
    date: str
    opponent: str
    is_home: bool
    won: Optional[bool]
    team_score: Optional[float]
    opp_score: Optional[float]
    final: bool


@dataclass
class TeamSnapshot:
    id: str
    name: str
    abbreviation: str
    recent: list[RecentGame] = field(default_factory=list)
    injuries: list[Injury] = field(default_factory=list)
    # Media de puntos/carreras anotados y recibidos en partidos finales recientes
    avg_scored: Optional[float] = None
    avg_allowed: Optional[float] = None
    wins: int = 0
    losses: int = 0
    fetch_errors: list[str] = field(default_factory=list)


@dataclass
class GameSnapshot:
    id: str
    sport: str  # "mlb" | "nfl"
    start_time: str  # ISO
    status: str  # pre | in | post
    status_detail: str
    venue: str
    home: TeamSnapshot
    away: TeamSnapshot
    home_score: Optional[float] = None
    away_score: Optional[float] = None
    # Contexto extra (pitchers, QBs, etc.)
    notes: list[str] = field(default_factory=list)


@dataclass
class SportBundle:
    sport: str
    games: list[GameSnapshot]
    teams: dict[str, TeamSnapshot]
    fetched_at: str
    errors: list[str] = field(default_factory=list)
    # Equipos disponibles para cara a cara (aunque no jueguen hoy)
    roster_teams: list[TeamSnapshot] = field(default_factory=list)
