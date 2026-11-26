from agents.chief import generate_recommendation


def _tech(signal="BUY", confidence=0.8):
    return {
        "signal": signal,
        "confidence": confidence,
        "projection": "Alcista" if signal == "BUY" else "Bajista",
        "indicators": {
            "price": 160.0,
            "rsi_14": 45.0,
            "macd": 0.12,
            "macd_signal": 0.04,
            "sma_50": 150.0,
            "sma_200": 120.0,
        },
        "buying_pressure": {
            "level": "Compra regular",
            "description": "Volumen por encima del promedio",
            "volume_ratio": 1.4,
            "score": 2,
        },
        "scenarios": {
            "probabilities": {"optimistic": 40, "base": 35, "pessimistic": 25},
            "best_scenario": "optimistic",
        },
        "notes": ["Tendencia alcista"],
    }


def test_chief_does_not_copy_the_technical_signal():
    state = {
        "asset_type": "stock",
        "technical": _tech("BUY", 0.7),
        "fundamental": {
            "applicable": True,
            "pe_ratio": 60,
            "summary": "Test Inc: PER 60.00 (valoración muy exigente).",
        },
        "sentiment": {
            "available": True,
            "sentiment_score": 0.1,
            "label": "Bajista",
            "summary": "Sentimiento Bajista (0.10). VIX: 32.00.",
        },
    }
    rec = generate_recommendation(state)
    assert rec["signal"] == "NEUTRAL"
    assert rec["confidence"] != 0.6
    assert "+15% en 6 meses" not in rec["reasoning"]
    assert "Compra" in rec["reasoning"]
    assert "RSI (14): 45.00" in rec["reasoning"]
    assert "optimista 40%" in rec["reasoning"]
    assert "base 35%" in rec["reasoning"]
    assert "pesimista 25%" in rec["reasoning"]
    assert "1.40x" in rec["reasoning"]
    assert "PER 60.00" in rec["reasoning"]
    assert "Sentimiento Bajista (0.10)" in rec["reasoning"]


def test_aligned_inputs_produce_a_buy_with_real_confidence():
    state = {
        "asset_type": "stock",
        "technical": _tech("BUY", 0.8),
        "fundamental": {
            "applicable": True,
            "pe_ratio": 10,
            "summary": "Test Inc: PER 10.00 (valoración baja).",
        },
        "sentiment": {
            "available": True,
            "sentiment_score": 0.8,
            "label": "Alcista",
            "summary": "Sentimiento Alcista (0.80). Titulares (3): 3 positivos y 0 negativos.",
        },
    }
    rec = generate_recommendation(state)
    assert rec["signal"] == "BUY"
    assert rec["signal_label"] == "Compra"
    assert rec["confidence"] >= 0.75
    assert rec["confidence"] != 0.6
    assert rec["scenarios"]["probabilities"]["optimistic"] == 40


def test_crypto_ignores_pe_style_fundamentals():
    state = {
        "asset_type": "crypto",
        "technical": _tech("SELL", 0.3),
        "fundamental": {
            "applicable": True,
            "pe_ratio": 8,
            "summary": "Los múltiplos tipo PER no aplican a criptomonedas. El análisis fundamental contable se omite.",
        },
        "sentiment": {
            "available": True,
            "sentiment_score": 0.45,
            "label": "Neutral",
            "summary": "Sentimiento Neutral (0.45). Índice de miedo y codicia cripto: 48 (neutral).",
        },
    }
    rec = generate_recommendation(state)
    assert rec["signal"] == "SELL"
    assert rec["components"]["fundamental"]["applied"] is False
    assert rec["components"]["fundamental"]["weight"] == 0
    assert "no aplican" in rec["reasoning"]
