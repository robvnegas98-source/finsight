"""Cliente MLB: Stats API (calendario/form) + ESPN (lesiones)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from .http import FetchError, get_json
from .types import GameSnapshot, Injury, RecentGame, SportBundle, TeamSnapshot

MLB_STATS = "https://statsapi.mlb.com/api/v1"
ESPN_MLB = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        for key in ("value", "displayValue"):
            if key in value:
                return _safe_float(value.get(key))
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compute_avgs(recent: list[RecentGame]) -> tuple[Optional[float], Optional[float], int, int]:
    scored: list[float] = []
    allowed: list[float] = []
    wins = losses = 0
    for g in recent:
        if not g.final:
            continue
        if g.team_score is not None:
            scored.append(g.team_score)
        if g.opp_score is not None:
            allowed.append(g.opp_score)
        if g.won is True:
            wins += 1
        elif g.won is False:
            losses += 1
    avg_s = sum(scored) / len(scored) if scored else None
    avg_a = sum(allowed) / len(allowed) if allowed else None
    return avg_s, avg_a, wins, losses


def _fetch_espn_injuries() -> tuple[dict[str, list[Injury]], list[str]]:
    try:
        data = get_json(f"{ESPN_MLB}/injuries")
    except FetchError as exc:
        return {}, [f"Lesiones MLB (ESPN): {exc}"]

    by_team: dict[str, list[Injury]] = {}
    for block in data.get("injuries") or []:
        team_name = block.get("displayName") or ""
        team_id = str(block.get("id") or "")
        items: list[Injury] = []
        for raw in block.get("injuries") or []:
            athlete = raw.get("athlete") or {}
            pos = (athlete.get("position") or {}).get("abbreviation") or ""
            items.append(
                Injury(
                    player=athlete.get("displayName") or "?",
                    team_id=team_id,
                    team_name=team_name,
                    status=raw.get("status") or "",
                    position=pos,
                    detail=raw.get("shortComment") or raw.get("longComment") or "",
                )
            )
        by_team[team_name.lower()] = items
        if team_id:
            by_team[team_id] = items
    return by_team, []


def _match_injuries(team_name: str, injuries_index: dict[str, list[Injury]]) -> list[Injury]:
    key = team_name.lower()
    if key in injuries_index:
        return injuries_index[key]
    for k, v in injuries_index.items():
        if not k.isdigit() and (k in key or key in k):
            return v
    return []


def _fetch_stats_teams(season: int) -> tuple[list[dict], list[str]]:
    try:
        data = get_json(f"{MLB_STATS}/teams", params={"sportId": 1, "season": season})
        return list(data.get("teams") or []), []
    except FetchError as exc:
        return [], [f"Equipos MLB (Stats API): {exc}"]


def fetch_team_form(team_id: str, *, end: Optional[date] = None, lookback_days: int = 45) -> tuple[TeamSnapshot, list[str]]:
    """Forma reciente de un equipo (últimos finales en la ventana)."""
    end = end or date.today()
    errors: list[str] = []
    start = end - timedelta(days=lookback_days)
    try:
        meta = get_json(f"{MLB_STATS}/teams/{team_id}")
        t = (meta.get("teams") or [{}])[0]
        name = t.get("name") or "?"
        abbr = t.get("abbreviation") or ""
    except FetchError as exc:
        return TeamSnapshot(id=str(team_id), name=f"Equipo {team_id}", abbreviation=""), [
            f"Meta equipo {team_id}: {exc}"
        ]

    try:
        data = get_json(
            f"{MLB_STATS}/schedule",
            params={
                "sportId": 1,
                "teamId": team_id,
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
            },
        )
    except FetchError as exc:
        return TeamSnapshot(id=str(team_id), name=name, abbreviation=abbr), [f"Forma {name}: {exc}"]

    tid_int = int(team_id)
    recent: list[RecentGame] = []
    for day in data.get("dates") or []:
        for g in day.get("games") or []:
            status = (g.get("status") or {}).get("abstractGameState") or ""
            teams = g.get("teams") or {}
            home = teams.get("home") or {}
            away = teams.get("away") or {}
            home_id = (home.get("team") or {}).get("id")
            is_home = home_id == tid_int
            me = home if is_home else away
            opp = away if is_home else home
            final = status == "Final"
            recent.append(
                RecentGame(
                    date=g.get("officialDate") or day.get("date") or "",
                    opponent=(opp.get("team") or {}).get("name") or "?",
                    is_home=is_home,
                    won=me.get("isWinner") if final else None,
                    team_score=_safe_float(me.get("score")),
                    opp_score=_safe_float(opp.get("score")),
                    final=final,
                )
            )
    finals = [r for r in recent if r.final][-10:]
    avg_s, avg_a, wins, losses = _compute_avgs(finals)
    return (
        TeamSnapshot(
            id=str(team_id),
            name=name,
            abbreviation=abbr,
            recent=finals,
            avg_scored=avg_s,
            avg_allowed=avg_a,
            wins=wins,
            losses=losses,
        ),
        errors,
    )


def _schedule_window(start: date, end: date) -> tuple[list[dict], list[str]]:
    try:
        data = get_json(
            f"{MLB_STATS}/schedule",
            params={
                "sportId": 1,
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "hydrate": "probablePitcher,venue,team",
            },
        )
        games: list[dict] = []
        for day in data.get("dates") or []:
            games.extend(day.get("games") or [])
        return games, []
    except FetchError as exc:
        return [], [f"Calendario MLB: {exc}"]


def _game_status(raw: dict) -> tuple[str, str]:
    status = raw.get("status") or {}
    abstract = (status.get("abstractGameState") or "").lower()
    detail = status.get("detailedState") or status.get("abstractGameState") or ""
    if abstract == "live":
        return "in", detail
    if abstract == "final":
        return "post", detail
    return "pre", detail


def fetch_mlb_bundle(*, today: Optional[date] = None, upcoming_days: int = 2) -> SportBundle:
    """Partidos de hoy/próximos + forma solo de equipos en cartelera."""
    today = today or date.today()
    errors: list[str] = []
    season = today.year if today.month >= 3 else today.year - 1

    injuries_index, inj_err = _fetch_espn_injuries()
    errors.extend(inj_err)

    raw_teams, team_err = _fetch_stats_teams(season)
    if not raw_teams:
        raw_teams, team_err2 = _fetch_stats_teams(season + 1)
        errors.extend(team_err2)
    errors.extend(team_err)

    roster: list[TeamSnapshot] = []
    for t in raw_teams:
        name = t.get("name") or "?"
        roster.append(
            TeamSnapshot(
                id=str(t.get("id")),
                name=name,
                abbreviation=t.get("abbreviation") or "",
                injuries=_match_injuries(name, injuries_index),
            )
        )

    raw_games, sched_err = _schedule_window(today, today + timedelta(days=upcoming_days))
    errors.extend(sched_err)

    needed_ids: set[str] = set()
    for g in raw_games:
        teams = g.get("teams") or {}
        for side in ("home", "away"):
            tid = str(((teams.get(side) or {}).get("team") or {}).get("id") or "")
            if tid:
                needed_ids.add(tid)

    team_cache: dict[str, TeamSnapshot] = {t.id: t for t in roster}
    for tid in needed_ids:
        snap, form_err = fetch_team_form(tid, end=today)
        errors.extend(form_err)
        base = team_cache.get(tid)
        snap.injuries = (base.injuries if base else []) or _match_injuries(snap.name, injuries_index)
        if not snap.abbreviation and base:
            snap.abbreviation = base.abbreviation
        team_cache[tid] = snap

    games: list[GameSnapshot] = []
    for g in raw_games:
        teams = g.get("teams") or {}
        home_raw = teams.get("home") or {}
        away_raw = teams.get("away") or {}
        home_id = str((home_raw.get("team") or {}).get("id") or "")
        away_id = str((away_raw.get("team") or {}).get("id") or "")
        home = team_cache.get(home_id) or TeamSnapshot(
            id=home_id,
            name=(home_raw.get("team") or {}).get("name") or "Local",
            abbreviation="",
            injuries=_match_injuries((home_raw.get("team") or {}).get("name") or "", injuries_index),
        )
        away = team_cache.get(away_id) or TeamSnapshot(
            id=away_id,
            name=(away_raw.get("team") or {}).get("name") or "Visitante",
            abbreviation="",
            injuries=_match_injuries((away_raw.get("team") or {}).get("name") or "", injuries_index),
        )
        status, detail = _game_status(g)
        notes: list[str] = []
        for side, label in ((home_raw, "Local"), (away_raw, "Visitante")):
            pp = side.get("probablePitcher") or {}
            if pp.get("fullName"):
                notes.append(f"Pitcher probable {label}: {pp['fullName']}")
        venue = (g.get("venue") or {}).get("name") or "Sede no disponible"
        games.append(
            GameSnapshot(
                id=str(g.get("gamePk") or ""),
                sport="mlb",
                start_time=g.get("gameDate") or "",
                status=status,
                status_detail=detail,
                venue=venue,
                home=home,
                away=away,
                home_score=_safe_float(home_raw.get("score")),
                away_score=_safe_float(away_raw.get("score")),
                notes=notes,
            )
        )

    # Roster con lesiones actualizadas
    roster = [team_cache.get(t.id, t) for t in roster]

    return SportBundle(
        sport="mlb",
        games=games,
        teams=team_cache,
        fetched_at=_now_iso(),
        errors=errors,
        roster_teams=roster,
    )
