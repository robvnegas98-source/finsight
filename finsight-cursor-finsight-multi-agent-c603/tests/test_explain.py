from core.explain import (
    explain_fundamental,
    explain_recommendation,
    explain_sentiment,
    explain_technical,
)


def _assert_prose(paragraphs):
    assert paragraphs
    blob = " ".join(paragraphs)
    assert "{" not in blob
    assert "[" not in blob
    for paragraph in paragraphs:
        assert paragraph.endswith(".")
        assert not paragraph.strip().startswith("{")


def test_technical_detail_is_an_explanation():
    text = explain_technical({
        "signal": "NEUTRAL",
        "confidence": 0.55,
        "projection": "Bajista",
        "indicators": {
            "price": 60000.0,
            "rsi_14": 22.05,
            "macd": -4554.0327,
            "macd_signal": -4000.0,
            "sma_50": 74680.19,
            "sma_200": 71919.66,
        },
        "support_resistance": {"support": 58806.3, "resistance": 86510.4, "current": 60000.0},
        "buying_pressure": {
            "level": "Compra muy baja",
            "description": "Volumen muy por debajo del promedio",
            "volume_ratio": 0.52,
        },
        "scenarios": {
            "probabilities": {"optimistic": 20, "base": 50, "pessimistic": 30},
            "best_scenario": "base",
        },
        "notes": ["RSI sobrevendido"],
    })
    _assert_prose(text)
    joined = " ".join(text)
    assert "22.05" in joined
    assert "sobreventa" in joined
    assert "50 %" in joined or "50%" in joined


def test_fundamental_crypto_does_not_dump_fields():
    text = explain_fundamental({
        "applicable": False,
        "summary": "Los múltiplos tipo PER no aplican a criptomonedas. El análisis fundamental contable se omite.",
    })
    _assert_prose(text)
    assert "PER" in " ".join(text)
    assert "pe_ratio" not in " ".join(text)


def test_recommendation_explains_a_disagreement():
    text = explain_recommendation(
        {
            "signal": "SELL",
            "signal_label": "Venta",
            "confidence": 0.59,
            "asset_type": "crypto",
            "components": {
                "technical": {"signal": "NEUTRAL", "score": 0.0, "weight": 0.55, "applied": True},
                "fundamental": {"score": None, "weight": 0.0, "applied": False},
                "sentiment": {"label": "Bajista", "score": -0.58, "weight": 0.45, "applied": True},
            },
        },
        "crypto",
    )
    _assert_prose(text)
    joined = " ".join(text)
    assert "Venta" in joined
    assert "Neutral" in joined
    assert "no copia" in joined
