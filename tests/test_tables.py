from core.tables import (
    fundamental_table,
    indicators_table,
    scenarios_table,
    summary_table,
    weights_table,
)


def test_summary_and_indicators_are_tables():
    result = {
        "asset_type": "crypto",
        "final_recommendation": {"signal": "SELL", "confidence": 0.59},
        "technical": {
            "signal": "NEUTRAL",
            "projection": "Bajista",
            "indicators": {"price": 60000, "rsi_14": 22.05, "macd": -1.2, "macd_signal": -0.4, "sma_50": 10, "sma_200": 9},
            "support_resistance": {"support": 58000, "resistance": 86000},
            "scenarios": {
                "probabilities": {"optimistic": 20, "base": 50, "pessimistic": 30},
                "best_scenario": "base",
            },
        },
    }
    summary = summary_table(result, "Kraken vía CCXT (BTC/USD)")
    assert list(summary["Concepto"])[:2] == ["Consejo de entrada", "Señal final"]
    assert summary.loc[summary["Concepto"] == "Consejo de entrada", "Valor"].item() == "Entrar en venta"
    assert summary.loc[summary["Concepto"] == "Señal final", "Valor"].item() == "Venta"
    indicators = indicators_table(result["technical"])
    assert "Sobreventa" in indicators["Lectura"].tolist()
    scenarios = scenarios_table(result["technical"])
    assert scenarios["Probabilidad"].tolist() == ["20 %", "50 %", "30 %"]
    assert scenarios.loc[scenarios["Escenario"] == "Base", "Más probable"].item() == "Sí"


def test_fundamental_table_marks_crypto_as_not_applicable():
    table = fundamental_table({
        "applicable": False,
        "summary": "Los múltiplos tipo PER no aplican a criptomonedas.",
    })
    assert table.loc[table["Concepto"] == "¿Sirve el PER aquí?", "Valor"].item() == "No"


def test_weights_table_shows_parts():
    table = weights_table({
        "components": {
            "technical": {"weight": 0.55, "score": 0.0, "applied": True},
            "fundamental": {"weight": 0.0, "score": None, "applied": False},
            "sentiment": {"weight": 0.45, "score": -0.5, "applied": True},
        }
    })
    assert table["Parte"].tolist() == ["Precio y técnica", "Fundamental", "Sentimiento"]
    assert "No entra en la mezcla" in table["Qué hizo"].tolist()
