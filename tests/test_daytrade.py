import pandas as pd

from agents.daytrade import analyze_session, normalize_intraday, swing_entry_exit


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
    assert "Entrada:" in plan["detail"]
    assert "Salida con ganancia" in plan["detail"]
    assert "Salida con pérdida" in plan["detail"]
    assert plan["trend"] == "Alcista"
    assert plan["vwap_side"] == "Por encima"
    assert plan["rsi_14"] is not None
    assert plan["volume_ratio"] == 1.0
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


def test_swing_buy_marks_entry_stop_and_target():
    levels = swing_entry_exit(
        {
            "indicators": {"price": 100},
            "support_resistance": {"support": 95, "resistance": 110},
        },
        "BUY",
    )
    assert levels["entry"] == 100
    assert levels["stop"] == 95
    assert levels["target"] == 110
    assert "compras cerca de 100" in levels["detail"]


def test_normalize_intraday_accepts_yahoo_multilevel_columns():
    index = pd.date_range("2024-01-02 09:30", periods=4, freq="5min")
    raw = pd.DataFrame(
        {
            ("Close", "AAPL"): [10, 11, 12, 13],
            ("Open", "AAPL"): [10, 11, 12, 13],
            ("High", "AAPL"): [10.2, 11.2, 12.2, 13.2],
            ("Low", "AAPL"): [9.8, 10.8, 11.8, 12.8],
            ("Volume", "AAPL"): [100, 100, 100, 100],
        },
        index=index,
    )
    raw.columns = pd.MultiIndex.from_tuples(raw.columns)
    frame = normalize_intraday(raw)
    assert list(frame["Close"]) == [10, 11, 12, 13]


def test_short_session_waits_for_the_opening_range():
    plan = analyze_session(_session([100.0] * 3))
    assert plan["action"] == "esperar"
    assert "30 minutos" in plan["title"]
