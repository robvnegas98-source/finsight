import pandas as pd

from agents.ownership import load_ownership, _situation, _holders_table, _trades_table


def test_situation_splits_buys_sells_and_holders():
    major = pd.DataFrame({"Value": [0.02, 0.60]}, index=["insidersPercentHeld", "institutionsPercentHeld"])
    trades = pd.DataFrame({
        "Text": ["Purchase at price 10", "Sale at price 12"],
        "Shares": [100, 40],
        "Value": [1000, 480],
        "Insider": ["ANA", "LUIS"],
        "Start Date": ["2026-01-01", "2026-01-02"],
    })
    table = _situation(major, trades, {"volume_ratio": 1.8, "level": "Se está comprando mucho"})
    assert table.loc[table["Situación"] == "Compra declarada por directivos", "Dato"].item() == "100"
    assert table.loc[table["Situación"] == "Venta declarada por directivos", "Dato"].item() == "40"
    assert "60.00 %" in table.loc[table["Situación"] == "Instituciones que mantienen", "Dato"].item()


def test_holders_and_trades_keep_quantities():
    holders = pd.DataFrame({
        "Holder": ["Fondo Uno"],
        "Shares": [1500],
        "Value": [90000],
        "pctHeld": [0.05],
    })
    shown = _holders_table(holders)
    assert shown.loc[0, "Tenedor"] == "Fondo Uno"
    assert shown.loc[0, "Acciones"] == "1,500"
    trades = _trades_table(pd.DataFrame({
        "Text": ["Sale at price 3"],
        "Shares": [10],
        "Value": [30],
        "Insider": ["MARIO"],
        "Start Date": ["2026-02-01"],
    }))
    assert trades.loc[0, "Operación"] == "Venta"
    assert trades.loc[0, "Acciones"] == "10"


def test_crypto_does_not_invent_people():
    result = load_ownership("BTC-USD", "crypto", {})
    assert result["holders"].empty
    assert "no se muestran cantidades inventadas" in result["note"]
