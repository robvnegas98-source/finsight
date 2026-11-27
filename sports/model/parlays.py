"""Construcción de parlays con filtro estricto ≥ 80% (producto de piernas)."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from sports.data.types import GameSnapshot
from sports.model.scoring import LegCandidate, legs_for_game

PARLAY_THRESHOLD = 0.80
MAX_PARLAYS = 8
MAX_LEGS = 2  # MVP: 1–2 piernas (3+ casi nunca pasa el umbral 80%)


@dataclass
class ParlayLeg:
    label: str
    probability: float
    reason: str
    game_id: str
    kind: str


@dataclass
class ParlaySuggestion:
    legs: list[ParlayLeg]
    combined_probability: float
    sport: str


def _compatible(a: LegCandidate, b: LegCandidate) -> bool:
    """Evita piernas contradictorias del mismo partido (mismo mutex o ML+ML)."""
    if a.game_id == b.game_id:
        # Mismo partido: permitir moneyline + total, no dos moneylines
        if a.kind == "moneyline" and b.kind == "moneyline":
            return False
        if a.mutex_key == b.mutex_key:
            return False
        # Dos totales de equipo del mismo lado chocan poco; permitir ML+total o total partido
        return True
    return True


def _to_parlay(legs: Iterable[LegCandidate], sport: str) -> ParlaySuggestion:
    legs_list = list(legs)
    combined = 1.0
    for leg in legs_list:
        combined *= leg.probability
    return ParlaySuggestion(
        legs=[
            ParlayLeg(
                label=L.label,
                probability=L.probability,
                reason=L.reason,
                game_id=L.game_id,
                kind=L.kind,
            )
            for L in legs_list
        ],
        combined_probability=combined,
        sport=sport,
    )


def build_parlays(games: list[GameSnapshot], *, threshold: float = PARLAY_THRESHOLD) -> list[ParlaySuggestion]:
    """Solo devuelve parlays con probabilidad combinada estimada ≥ threshold."""
    open_games = [g for g in games if g.status in {"pre", "in"}]
    if not open_games:
        return []

    all_legs: list[LegCandidate] = []
    sport = open_games[0].sport
    for g in open_games:
        all_legs.extend(legs_for_game(g))

    # Ordenar piernas fuertes primero
    all_legs.sort(key=lambda L: L.probability, reverse=True)

    suggestions: list[ParlaySuggestion] = []
    seen: set[tuple[str, ...]] = set()

    # 1 pierna (single de alta confianza)
    for leg in all_legs:
        if leg.probability >= threshold:
            key = (leg.mutex_key,)
            if key in seen:
                continue
            seen.add(key)
            suggestions.append(_to_parlay([leg], sport))

    # 2 piernas
    top = all_legs[:24]
    for a, b in combinations(top, 2):
        if not _compatible(a, b):
            continue
        combined = a.probability * b.probability
        if combined < threshold:
            continue
        key = tuple(sorted((a.mutex_key, b.mutex_key)))
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(_to_parlay([a, b], sport))

    suggestions.sort(key=lambda p: p.combined_probability, reverse=True)
    return suggestions[:MAX_PARLAYS]
