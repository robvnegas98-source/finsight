"""Tests unitarios del filtro de parlays (sin red)."""

from sports.data.types import GameSnapshot, RecentGame, TeamSnapshot
from sports.model.parlays import PARLAY_THRESHOLD, build_parlays


def _team(tid: str, name: str, wins: int, losses: int, scored: float, allowed: float) -> TeamSnapshot:
    recent = []
    for i in range(wins + losses):
        won = i < wins
        recent.append(
            RecentGame(
                date=f"2026-11-{i+1:02d}",
                opponent="Opp",
                is_home=True,
                won=won,
                team_score=scored if won else scored - 7,
                opp_score=allowed if not won else allowed + 3,
                final=True,
            )
        )
    return TeamSnapshot(
        id=tid,
        name=name,
        abbreviation=name[:3].upper(),
        recent=recent,
        avg_scored=scored,
        avg_allowed=allowed,
        wins=wins,
        losses=losses,
    )


def test_threshold_constant():
    assert PARLAY_THRESHOLD == 0.80


def test_build_parlays_respects_threshold():
    strong = _team("1", "Jaguares", 9, 1, 30.0, 16.0)
    weak = _team("2", "Titánicos", 1, 9, 14.0, 30.0)
    game = GameSnapshot(
        id="g1",
        sport="nfl",
        start_time="2026-11-29T18:00Z",
        status="pre",
        status_detail="Scheduled",
        venue="Stadium",
        home=strong,
        away=weak,
    )
    parlays = build_parlays([game])
    assert parlays, "se esperaba al menos un parlay con favorito claro"
    assert all(p.combined_probability >= PARLAY_THRESHOLD for p in parlays)


def test_no_parlays_for_final_games_only():
    a = _team("1", "A", 5, 5, 22.0, 22.0)
    b = _team("2", "B", 5, 5, 22.0, 22.0)
    game = GameSnapshot(
        id="g2",
        sport="nfl",
        start_time="2026-11-26T18:00Z",
        status="post",
        status_detail="Final",
        venue="Stadium",
        home=a,
        away=b,
    )
    assert build_parlays([game]) == []
