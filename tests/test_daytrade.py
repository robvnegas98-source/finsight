import pandas as pd

from agents.daytrade import analyze_session


def _session(second_day):
    rows = []
    index = []
    for day, closes in (("2024-01-02", [100.0] * 20), ("2024-01-03", second_day)):
        start = pd.Timestamp(day)
        for i, close in enumerate(closes):
            index.append(start + pd.Timedelta(minutes=5 * i))
            rows.append({
                "Open": close,
                "High": close + 0.3,
                "Low": close - 0.3,
                "Close": close,
                "Volume": 1000,
            })
    return pd.DataFrame(rows, index=pd.DatetimeIndex(index))


def test_flat_session_says_stay_out():
    plan = analyze_session(_session([100.0] * 30))
    assert plan["action"] == "esperar"
    assert "no entres" in plan["title"].lower()


def test_breakout_above_vwap_is_a_day_buy():
    climb = [100.0] * 6 + [101, 102, 103, 104, 105, 106, 107, 108]
    plan = analyze_session(_session(climb))
    assert plan["action"] == "compra"
    assert plan["trend"] == "Alcista"
    assert plan["vwap_side"] == "Por encima"
    assert plan["rsi_14"] is not None
    assert plan["macd"] is not None
    assert plan["stop"] < plan["entry"] < plan["target"]
    risk = plan["entry"] - plan["stop"]
    reward = plan["target"] - plan["entry"]
    assert abs(reward - 2 * risk) < 0.05
    assert risk < 5


def test_breakdown_below_vwap_is_a_day_sell():
    drop = [100.0] * 6 + [99, 98, 97, 96, 95, 94, 93, 92]
    plan = analyze_session(_session(drop))
    assert plan["action"] == "venta"
    assert plan["target"] < plan["entry"] < plan["stop"]


def test_short_session_waits_for_the_opening_range():
    plan = analyze_session(_session([100.0] * 3))
    assert plan["action"] == "esperar"
    assert "30 minutos" in plan["title"]
