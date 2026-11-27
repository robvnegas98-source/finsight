"""Scoring transparente: forma, local/visitante y lesiones clave.

Las probabilidades son estimaciones del modelo, no cuotas de mercado ni garantías.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sports.data.types import GameSnapshot, Injury, TeamSnapshot

# Ajuste local típico (puntos porcentuales sobre el logit/prob lineal simple)
HOME_EDGE = {
    "mlb": 0.04,
    "nfl": 0.03,
}

# Penalización por lesión según estado (sobre el equipo afectado)
_STATUS_PENALTY = {
    "out": 0.04,
    "injured reserve": 0.04,
    "ir": 0.04,
    "doubtful": 0.03,
    "questionable": 0.015,
    "day-to-day": 0.01,
    "day to day": 0.01,
}

# Multiplicador si la posición es crítica
_KEY_POS_NFL = {"QB": 2.5, "WR": 1.2, "RB": 1.2, "TE": 1.1, "LT": 1.3, "RT": 1.2, "CB": 1.1}
_KEY_POS_MLB = {"SP": 2.0, "P": 1.6, "C": 1.2, "SS": 1.2, "CF": 1.1}


@dataclass
class WinEstimate:
    home_win_pct: float
    away_win_pct: float
    reasons_home: list[str]
    reasons_away: list[str]
    projected_home_score: float
    projected_away_score: float
    score_low: float
    score_high: float
    unit: str  # "carreras" | "puntos"


@dataclass
class LegCandidate:
    game_id: str
    sport: str
    label: str
    probability: float
    reason: str
    kind: str  # moneyline | team_total
    # Para evitar piernas contradictorias del mismo partido
    mutex_key: str


def _clamp(p: float, lo: float = 0.08, hi: float = 0.92) -> float:
    return max(lo, min(hi, p))


def _form_rate(team: TeamSnapshot) -> tuple[Optional[float], int]:
    finals = [g for g in team.recent if g.final and g.won is not None]
    if not finals:
        return None, 0
    wins = sum(1 for g in finals if g.won)
    return wins / len(finals), len(finals)


def _injury_penalty(team: TeamSnapshot, sport: str) -> tuple[float, list[str]]:
    key_map = _KEY_POS_NFL if sport == "nfl" else _KEY_POS_MLB
    penalty = 0.0
    notes: list[str] = []
    # Solo las más graves / posiciones clave, máximo ~3 menciones
    ranked: list[tuple[float, Injury]] = []
    for inj in team.injuries:
        status_l = (inj.status or "").lower()
        base = 0.0
        for needle, val in _STATUS_PENALTY.items():
            if needle in status_l:
                base = val
                break
        if base <= 0:
            continue
        mult = key_map.get((inj.position or "").upper(), 1.0)
        # QB/SP out pesa más
        ranked.append((base * mult, inj))
    ranked.sort(key=lambda x: x[0], reverse=True)
    for weight, inj in ranked[:4]:
        penalty += weight
        notes.append(f"{inj.player} ({inj.position or '?'}: {inj.status})")
    return min(penalty, 0.18), notes


def _projected_scores(home: TeamSnapshot, away: TeamSnapshot, sport: str) -> tuple[float, float, str]:
    if sport == "mlb":
        default_off, default_def = 4.5, 4.5
        unit = "carreras"
    else:
        default_off, default_def = 22.0, 22.0
        unit = "puntos"

    home_off = home.avg_scored if home.avg_scored is not None else default_off
    home_def = home.avg_allowed if home.avg_allowed is not None else default_def
    away_off = away.avg_scored if away.avg_scored is not None else default_off
    away_def = away.avg_allowed if away.avg_allowed is not None else default_def

    # Blend ofensa propia y defensa rival
    proj_home = 0.55 * home_off + 0.45 * away_def
    proj_away = 0.55 * away_off + 0.45 * home_def
    # Ligero boost local al marcador
    edge = 0.15 if sport == "mlb" else 1.5
    proj_home += edge
    return proj_home, proj_away, unit


def estimate_matchup(game: GameSnapshot) -> WinEstimate:
    """Estima % de victoria y rango de puntos/carreras para un partido."""
    sport = game.sport
    home, away = game.home, game.away
    reasons_h: list[str] = []
    reasons_a: list[str] = []

    home_form, home_n = _form_rate(home)
    away_form, away_n = _form_rate(away)

    # Base 50/50 + forma relativa + diferencial de puntos/carreras
    p_home = 0.50
    if home_form is not None and away_form is not None:
        delta = (home_form - away_form) * 0.45
        p_home += delta
        reasons_h.append(f"Forma reciente {home_form:.0%} en {home_n} partidos ({home.wins}-{home.losses})")
        reasons_a.append(f"Forma reciente {away_form:.0%} en {away_n} partidos ({away.wins}-{away.losses})")
    elif home_form is not None:
        p_home += (home_form - 0.5) * 0.35
        reasons_h.append(f"Forma reciente {home_form:.0%} en {home_n} partidos ({home.wins}-{home.losses})")
    elif away_form is not None:
        p_home -= (away_form - 0.5) * 0.35
        reasons_a.append(f"Forma reciente {away_form:.0%} en {away_n} partidos ({away.wins}-{away.losses})")
    else:
        reasons_h.append("Sin suficientes partidos finales recientes para forma")
        reasons_a.append("Sin suficientes partidos finales recientes para forma")

    # Diferencial ofensivo/defensivo reciente (datos reales cuando existen)
    if home.avg_scored is not None and away.avg_scored is not None:
        if sport == "nfl":
            margin = (home.avg_scored - (home.avg_allowed or home.avg_scored)) - (
                away.avg_scored - (away.avg_allowed or away.avg_scored)
            )
            p_home += max(-0.20, min(0.20, margin * 0.012))
            reasons_h.append(
                f"Net pts recientes: local {home.avg_scored:.1f}/{home.avg_allowed or 0:.1f} vs "
                f"visitante {away.avg_scored:.1f}/{away.avg_allowed or 0:.1f}"
            )
        else:
            margin = (home.avg_scored - (home.avg_allowed or home.avg_scored)) - (
                away.avg_scored - (away.avg_allowed or away.avg_scored)
            )
            p_home += max(-0.18, min(0.18, margin * 0.04))
            reasons_h.append(
                f"Net carreras recientes: local {home.avg_scored:.1f}/{home.avg_allowed or 0:.1f} vs "
                f"visitante {away.avg_scored:.1f}/{away.avg_allowed or 0:.1f}"
            )

    home_edge = HOME_EDGE.get(sport, 0.03)
    p_home += home_edge
    reasons_h.append(f"Ventaja de local (+{home_edge:.0%})")

    pen_h, notes_h = _injury_penalty(home, sport)
    pen_a, notes_a = _injury_penalty(away, sport)
    p_home -= pen_h
    p_home += pen_a
    if notes_h:
        reasons_h.append("Lesiones clave: " + "; ".join(notes_h[:3]))
    if notes_a:
        reasons_a.append("Lesiones clave: " + "; ".join(notes_a[:3]))

    if game.venue:
        reasons_h.append(f"Sede: {game.venue}")

    for note in game.notes:
        reasons_h.append(note)

    p_home = _clamp(p_home)
    p_away = 1.0 - p_home

    proj_h, proj_a, unit = _projected_scores(home, away, sport)
    total = proj_h + proj_a
    # Rango ±15% del total proyectado
    low = round(total * 0.85, 1)
    high = round(total * 1.15, 1)

    return WinEstimate(
        home_win_pct=p_home,
        away_win_pct=p_away,
        reasons_home=reasons_h,
        reasons_away=reasons_a,
        projected_home_score=round(proj_h, 1),
        projected_away_score=round(proj_a, 1),
        score_low=low,
        score_high=high,
        unit=unit,
    )


def estimate_pair(team_a: TeamSnapshot, team_b: TeamSnapshot, sport: str, *, a_is_home: bool = True) -> WinEstimate:
    """Cara a cara entre dos equipos (A como local por defecto)."""
    if a_is_home:
        game = GameSnapshot(
            id="h2h",
            sport=sport,
            start_time="",
            status="pre",
            status_detail="Cara a cara",
            venue="Local: " + team_a.name,
            home=team_a,
            away=team_b,
        )
    else:
        game = GameSnapshot(
            id="h2h",
            sport=sport,
            start_time="",
            status="pre",
            status_detail="Cara a cara",
            venue="Local: " + team_b.name,
            home=team_b,
            away=team_a,
        )
        est = estimate_matchup(game)
        # Invertir para que A/B coincidan con la selección del usuario
        return WinEstimate(
            home_win_pct=est.away_win_pct,
            away_win_pct=est.home_win_pct,
            reasons_home=est.reasons_away,
            reasons_away=est.reasons_home,
            projected_home_score=est.projected_away_score,
            projected_away_score=est.projected_home_score,
            score_low=est.score_low,
            score_high=est.score_high,
            unit=est.unit,
        )
    return estimate_matchup(game)


def score_unit() -> str:
    return "modelo_v1"


def _team_total_leg(
    game: GameSnapshot,
    side: str,
    estimate: WinEstimate,
) -> Optional[LegCandidate]:
    """Piernas de total de equipo basadas en proyección vs umbral redondeado."""
    sport = game.sport
    if sport == "mlb":
        team = game.home if side == "home" else game.away
        proj = estimate.projected_home_score if side == "home" else estimate.projected_away_score
        # Umbral: floor de proyección - 0.5 → "anota al menos N carreras" si proj es alta
        threshold = max(2, int(proj) - 1)
        gap = proj - threshold
        p = _clamp(0.58 + gap * 0.14, 0.40, 0.90)
        label = f"{team.name} anota ≥ {threshold} carreras"
        reason = f"Proyección ~{proj:.1f} carreras (forma ofensiva reciente)"
        kind = "team_total"
        mutex = f"{game.id}:runs:{team.id}:{threshold}"
    else:
        team = game.home if side == "home" else game.away
        proj = estimate.projected_home_score if side == "home" else estimate.projected_away_score
        # Umbral bajo la proyección, pero no trivial (≥17 pts)
        threshold = max(17, int(round(proj)) - 5)
        gap = proj - threshold
        p = _clamp(0.52 + gap * 0.04, 0.40, 0.90)
        label = f"{team.name} anota ≥ {threshold} puntos"
        reason = f"Proyección ~{proj:.1f} puntos (ofensiva/defensa reciente)"
        kind = "team_total"
        mutex = f"{game.id}:pts:{team.id}:{threshold}"

    return LegCandidate(
        game_id=game.id,
        sport=sport,
        label=label,
        probability=p,
        reason=reason,
        kind=kind,
        mutex_key=mutex,
    )


def legs_for_game(game: GameSnapshot) -> list[LegCandidate]:
    """Genera piernas candidatas (ganador + totales de equipo) para un partido no finalizado."""
    if game.status == "post":
        return []
    est = estimate_matchup(game)
    legs: list[LegCandidate] = []

    # Moneyline favorito
    if est.home_win_pct >= est.away_win_pct:
        fav, p, why = game.home, est.home_win_pct, est.reasons_home
    else:
        fav, p, why = game.away, est.away_win_pct, est.reasons_away
    legs.append(
        LegCandidate(
            game_id=game.id,
            sport=game.sport,
            label=f"Gana {fav.name}",
            probability=p,
            reason="; ".join(why[:2]) if why else "Estimación del modelo",
            kind="moneyline",
            mutex_key=f"{game.id}:ml",
        )
    )
    # También el underdog no se añade (baja probabilidad)

    for s in ("home", "away"):
        leg = _team_total_leg(game, s, est)
        if leg is not None:
            legs.append(leg)

    # Total combinado del partido (over suave del total proyectado)
    total_proj = est.projected_home_score + est.projected_away_score
    if game.sport == "mlb":
        line = max(5, int(total_proj) - 2)
        gap = total_proj - line
        p_tot = _clamp(0.55 + gap * 0.12, 0.40, 0.90)
        legs.append(
            LegCandidate(
                game_id=game.id,
                sport=game.sport,
                label=f"Más de {line} carreras en el partido",
                probability=p_tot,
                reason=f"Total proyectado ~{total_proj:.1f} carreras",
                kind="game_total",
                mutex_key=f"{game.id}:total",
            )
        )
    else:
        line = max(35, int(total_proj) - 7)
        gap = total_proj - line
        p_tot = _clamp(0.52 + gap * 0.03, 0.40, 0.90)
        legs.append(
            LegCandidate(
                game_id=game.id,
                sport=game.sport,
                label=f"Más de {line} puntos en el partido",
                probability=p_tot,
                reason=f"Total proyectado ~{total_proj:.1f} puntos",
                kind="game_total",
                mutex_key=f"{game.id}:total",
            )
        )

    return legs
