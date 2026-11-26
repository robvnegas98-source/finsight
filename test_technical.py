import numpy as np
import pandas as pd

from agents.technical import (
    analyze_technical,
    calculate_rsi,
    normalize_probabilities,
    project_scenarios,
    score_technical,
)


def _raw_from_prices(prices, volumes=None):
    index = pd.date_range("2022-01-03", periods=len(prices), freq="B")
    volume = volumes if volumes is not None else [1_000_000.0] * len(prices)
    frame = pd.DataFrame(
        {
            "Open": prices,
            "High": [price * 1.01 for price in prices],
            "Low": [price * 0.99 for price in prices],
            "Close": prices,
            "Volume": volume,
        },
        index=index,
    )
    return {"history": frame.to_dict()}


def test_rsi_extremes_on_monotone_series():
    rising = pd.Series([float(i) for i in range(1, 40)])
    falling = pd.Series([float(40 - i) for i in range(40)])
    assert calculate_rsi(rising).iloc[-1] == 100.0
    assert calculate_rsi(falling).iloc[-1] == 0.0


def test_rsi_zero_is_kept_and_counts_as_oversold():
    prices = [80 - i * 0.4 for i in range(60)]
    result = analyze_technical(_raw_from_prices(prices))
    assert result["indicators"]["rsi_14"] == 0.0
    assert "RSI sobrevendido" in result["notes"]
    assert sum(result["scenarios"]["probabilities"].values()) == 100

    decision = score_technical(0.0, 10.0, None, None, None, None, 0, None)
    assert "RSI sobrevendido" in decision["notes"]
    assert decision["score"] == 2


def test_macd_zero_is_a_real_reading():
    decision = score_technical(50.0, 10.0, None, None, 0.0, 1.0, 0, None)
    assert "MACD bajista" in decision["notes"]


def test_buy_and_sell_signals_from_indicators():
    buy = score_technical(50.0, 120.0, 100.0, 80.0, 1.0, 0.2, 2, "Compra regular")
    assert buy["signal"] == "BUY"
    assert buy["confidence"] == 0.75
    assert buy["projection"] == "Alcista"

    sell = score_technical(50.0, 70.0, 90.0, 110.0, -0.5, 0.2, -2, "Compra muy baja")
    assert sell["signal"] == "SELL"
    assert sell["confidence"] == 0.75
    assert sell["projection"] == "Bajista"

    neutral = score_technical(None, None, None, None, None, None, 0, None)
    assert neutral["signal"] == "NEUTRAL"
    assert neutral["confidence"] == 0.5


def test_analyze_technical_signal_matches_scorer():
    prices = [50 + i * 0.4 for i in range(220)]
    volumes = [1_000_000.0] * 219 + [4_000_000.0]
    result = analyze_technical(_raw_from_prices(prices, volumes))
    indicators = result["indicators"]
    decision = score_technical(
        indicators.get("rsi_14"),
        indicators.get("price"),
        indicators.get("sma_50"),
        indicators.get("sma_200"),
        indicators.get("macd"),
        indicators.get("macd_signal"),
        result["buying_pressure"].get("score", 0),
        result["buying_pressure"].get("level"),
    )
    assert result["signal"] == decision["signal"]
    assert result["signal"] in {"BUY", "SELL", "NEUTRAL"}
    assert sum(result["scenarios"]["probabilities"].values()) == 100


def test_probabilities_always_sum_to_100():
    awkward = normalize_probabilities({"optimistic": 1, "base": 1, "pessimistic": 1})
    assert sum(awkward.values()) == 100
    capped = normalize_probabilities({"optimistic": 55, "base": 35, "pessimistic": 15})
    assert sum(capped.values()) == 100

    index = pd.date_range("2023-01-02", periods=80, freq="B")
    rising = pd.Series([100 + i * 0.4 for i in range(80)], index=index)
    falling = pd.Series([180 - i * 0.5 for i in range(80)], index=index)
    for score in (-6, -3, 0, 2, 3, 8):
        for series in (rising, falling):
            scenarios = project_scenarios(series, days=30, score=score)
            assert sum(scenarios["probabilities"].values()) == 100
            assert set(scenarios["probabilities"]) == {"optimistic", "base", "pessimistic"}


def test_scenario_cone_does_not_compound_daily_volatility():
    rng = np.random.default_rng(0)
    returns = rng.normal(0.0005, 0.02, 120)
    prices = 100 * np.cumprod(1 + returns)
    index = pd.date_range("2023-01-02", periods=len(prices), freq="B")
    close = pd.Series(prices, index=index)
    scenarios = project_scenarios(close, days=90, score=3)
    last = float(close.iloc[-1])
    assert scenarios["optimistic"][-1] > scenarios["base"][-1] > scenarios["pessimistic"][-1]
    assert scenarios["optimistic"][-1] < last * 2
    assert scenarios["pessimistic"][-1] > last * 0.4
