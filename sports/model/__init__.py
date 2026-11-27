"""Modelo de probabilidad transparente para parlays y cara a cara."""

from .parlays import PARLAY_THRESHOLD, build_parlays
from .scoring import estimate_matchup, estimate_pair

__all__ = ["PARLAY_THRESHOLD", "build_parlays", "estimate_matchup", "estimate_pair"]
