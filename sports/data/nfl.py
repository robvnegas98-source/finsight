"""Cliente NFL vía endpoints públicos ESPN (scoreboard, schedule, lesiones)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .http import FetchError, get_json
from .types import GameSnapshot, Injury, RecentGame, SportBundle, TeamSnapshot

ESPN_NFL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"


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


def _fetch_injuries() -> tuple[dict[str, list[Injury]], list[str]]:
    try:
        data = get_json(f"{ESPN_NFL}/injuries")
    except FetchError as exc:
        return {}, [f"Lesiones NFL (ESPN): {exc}"]

    by_key: dict[str, list[Injury]] = {}
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
        if team_id:
            by_key[team_id] = items
        by_key[team_name.lower()] = items
    return by_key, []


def _injuries_for(team_id: str, team_name: str, index: dict[str, list[Injury]]) -> list[Injury]:
    if team_id in index:
        return index[team_id]
    return index.get(team_name.lower(), [])


def fetch_team_form(team_id: str, *, injuries: Optional[list[Injury]] = None) -> tuple[TeamSnapshot, list[str]]:
    """Últimos partidos finales del equipo vía ESPN schedule."""
    errors: list[str] = []
    try:
        data = get_json(f"{ESPN_NFL}/teams/{team_id}/schedule")
    except FetchError as exc:
        return TeamSnapshot(id=str(team_id), name=f"Equipo {team_id}", abbreviation=""), [
            f"Calendario equipo {team_id}: {exc}"
        ]

    team_meta = data.get("team") or {}
    name = team_meta.get("displayName") or team_meta.get("name") or f"Equipo {team_id}"
    abbr = team_meta.get("abbreviation") or ""

    recent: list[RecentGame] = []
    for event in data.get("events") or []:
        comps = (event.get("competitions") or [{}])[0]
        status_type = (comps.get("status") or {}).get("type") or {}
        state = status_type.get("state") or ""
        final = bool(status_type.get("completed")) or state == "post"
        competitors = comps.get("competitors") or []
        me = next((c for c in competitors if str((c.get("team") or {}).get("id")) == str(team_id)), None)
        opp = next((c for c in competitors if c is not me), None)
        if me is None:
            continue
        is_home = (me.get("homeAway") or "") == "home"
        me_score = _safe_float(me.get("score"))
        opp_score = _safe_float((opp or {}).get("score")) if opp else None
        won: Optional[bool] = None
        if final and me_score is not None and opp_score is not None:
            won = me_score > opp_score
        elif final and me.get("winner") is not None:
            won = bool(me.get("winner"))
        recent.append(
            RecentGame(
                date=(event.get("date") or "")[:10],
                opponent=((opp or {}).get("team") or {}).get("displayName") or "?",
                is_home=is_home,
                won=won,
                team_score=me_score,
                opp_score=opp_score,
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
            injuries=list(injuries or []),
            avg_scored=avg_s,
            avg_allowed=avg_a,
            wins=wins,
            losses=losses,
        ),
        errors,
    )


def _list_teams(injuries_index: dict[str, list[Injury]]) -> tuple[list[TeamSnapshot], list[str]]:
    try:
        data = get_json(f"{ESPN_NFL}/teams")
    except FetchError as exc:
        return [], [f"Equipos NFL: {exc}"]

    roster: list[TeamSnapshot] = []
    leagues = ((data.get("sports") or [{}])[0].get("leagues") or [{}])
    for entry in leagues[0].get("teams") or []:
        t = entry.get("team") or {}
        tid = str(t.get("id") or "")
        name = t.get("displayName") or t.get("name") or "?"
        roster.append(
            TeamSnapshot(
                id=tid,
                name=name,
                abbreviation=t.get("abbreviation") or "",
                injuries=_injuries_for(tid, name, injuries_index),
            )
        )
    return roster, []


def fetch_nfl_bundle() -> SportBundle:
    """Scoreboard de la jornada + forma de equipos que aparecen en cartelera."""
    errors: list[str] = []
    injuries_index, inj_err = _fetch_injuries()
    errors.extend(inj_err)

    roster, roster_err = _list_teams(injuries_index)
    errors.extend(roster_err)
    team_cache: dict[str, TeamSnapshot] = {t.id: t for t in roster}

    try:
        data = get_json(f"{ESPN_NFL}/scoreboard")
    except FetchError as exc:
        return SportBundle(
            sport="nfl",
            games=[],
            teams=team_cache,
            fetched_at=_now_iso(),
            errors=errors + [f"Scoreboard NFL: {exc}"],
            roster_teams=roster,
        )

    needed: set[str] = set()
    raw_events = data.get("events") or []
    for event in raw_events:
        comps = (event.get("competitions") or [{}])[0]
        for c in comps.get("competitors") or []:
            tid = str((c.get("team") or {}).get("id") or "")
            if tid:
                needed.add(tid)

    for tid in needed:
        base = team_cache.get(tid)
        inj = base.injuries if base else injuries_index.get(tid, [])
        snap, form_err = fetch_team_form(tid, injuries=inj)
        errors.extend(form_err)
        if base and not snap.abbreviation:
            snap.abbreviation = base.abbreviation
        team_cache[tid] = snap

    games: list[GameSnapshot] = []
    for event in raw_events:
        comps = (event.get("competitions") or [{}])[0]
        status_type = (comps.get("status") or {}).get("type") or {}
        state = status_type.get("state") or "pre"
        detail = status_type.get("shortDetail") or status_type.get("detail") or ""
        venue = (comps.get("venue") or {}).get("fullName") or "Sede no disponible"
        competitors = comps.get("competitors") or []
        home_c = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away_c = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home_c or not away_c:
            continue

        def _resolve(comp: dict) -> TeamSnapshot:
            t = comp.get("team") or {}
            tid = str(t.get("id") or "")
            if tid in team_cache and team_cache[tid].recent:
                return team_cache[tid]
            name = t.get("displayName") or "?"
            return TeamSnapshot(
                id=tid,
                name=name,
                abbreviation=t.get("abbreviation") or "",
                injuries=_injuries_for(tid, name, injuries_index),
            )

        home = _resolve(home_c)
        away = _resolve(away_c)
        notes: list[str] = []
        for comp, label in ((home_c, "Local"), (away_c, "Visitante")):
            for lead in comp.get("leaders") or []:
                lname = (lead.get("name") or lead.get("displayName") or "").lower()
                if "pass" in lname:
                    athletes = lead.get("leaders") or []
                    if athletes:
                        aname = ((athletes[0].get("athlete") or {}).get("displayName")) or ""
                        if aname:
                            notes.append(f"Líder de pase {label}: {aname}")

        games.append(
            GameSnapshot(
                id=str(event.get("id") or ""),
                sport="nfl",
                start_time=event.get("date") or "",
                status=state,
                status_detail=detail,
                venue=venue,
                home=home,
                away=away,
                home_score=_safe_float(home_c.get("score")),
                away_score=_safe_float(away_c.get("score")),
                notes=notes,
            )
        )

    roster = [team_cache.get(t.id, t) for t in roster]
    return SportBundle(
        sport="nfl",
        games=games,
        teams=team_cache,
        fetched_at=_now_iso(),
        errors=errors,
        roster_teams=roster,
    )
