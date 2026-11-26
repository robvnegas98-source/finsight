"""
Agente 5: Chief Analyst
Sintetiza técnico, fundamental y sentimiento en la señal y la confianza finales.
La justificación usa las mismas cifras que pinta la interfaz.
"""
from typing import Any, Dict, List, Optional, Tuple

from core.assets import NON_FUNDAMENTAL_TYPES
from core.labels import format_number, scenario_label, signal_label

WEIGHTS = {
    "stock": {"technical": 0.45, "fundamental": 0.30, "sentiment": 0.25},
    "etf": {"technical": 0.50, "fundamental": 0.20, "sentiment": 0.30},
    "crypto": {"technical": 0.55, "fundamental": 0.0, "sentiment": 0.45},
    "futures": {"technical": 0.70, "fundamental": 0.0, "sentiment": 0.30},
    "forex": {"technical": 0.70, "fundamental": 0.0, "sentiment": 0.30},
    "index": {"technical": 0.65, "fundamental": 0.0, "sentiment": 0.35},
    "unknown": {"technical": 0.55, "fundamental": 0.20, "sentiment": 0.25},
}

BUY_LEVEL = 0.2
SELL_LEVEL = -0.2


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _technical_score(tech: Dict[str, Any]) -> Optional[float]:
    if not tech or not tech.get("signal"):
        return None
    notes = " ".join(tech.get("notes") or []).lower()
    if not tech.get("indicators") and ("insuficiente" in notes or "no hay datos" in notes):
        return None
    direction = {"BUY": 1.0, "SELL": -1.0, "NEUTRAL": 0.0}.get(tech.get("signal"))
    if direction is None:
        return None
    try:
        confidence = float(tech.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    return direction * _clamp(confidence, 0.0, 1.0)


def _fundamental_score(fund: Dict[str, Any], asset_type: str) -> Optional[float]:
    if asset_type in NON_FUNDAMENTAL_TYPES:
        return None
    if not fund or fund.get("applicable") is False:
        return None
    pe = fund.get("pe_ratio")
    forward = fund.get("forward_pe")
    try:
        pe = float(pe) if pe is not None else None
    except (TypeError, ValueError):
        pe = None
    try:
        forward = float(forward) if forward is not None else None
    except (TypeError, ValueError):
        forward = None
    anchor = pe if pe is not None else forward
    if anchor is None:
        dividend = fund.get("dividend_yield")
        try:
            dividend = float(dividend) if dividend is not None else None
        except (TypeError, ValueError):
            dividend = None
        if dividend is None:
            return None
        if dividend >= 3:
            return 0.15
        if dividend > 0:
            return 0.05
        return 0.0
    if anchor < 0:
        score = -0.7
    elif anchor < 12:
        score = 0.55
    elif anchor < 18:
        score = 0.3
    elif anchor < 25:
        score = 0.1
    elif anchor < 35:
        score = -0.15
    elif anchor < 50:
        score = -0.35
    else:
        score = -0.55
    if pe is not None and pe > 0 and forward is not None and forward > 0:
        if forward < pe * 0.9:
            score += 0.1
        elif forward > pe * 1.15:
            score -= 0.1
    return _clamp(score)


def _sentiment_score(sent: Dict[str, Any]) -> Optional[float]:
    if not sent or sent.get("available") is False or sent.get("sentiment_score") is None:
        return None
    try:
        score = float(sent["sentiment_score"])
    except (TypeError, ValueError):
        return None
    return _clamp((score - 0.5) * 2)


def _confidence(signal: str, combined: float, scores: List[float]) -> float:
    usable = [score for score in scores if score is not None]
    if signal == "NEUTRAL":
        disagreement = max((abs(score) for score in usable), default=0.0)
        value = 0.65 - 0.3 * disagreement
        return round(min(0.7, max(0.35, value)), 2)
    direction = 1.0 if signal == "BUY" else -1.0
    magnitude = min(1.0, abs(combined))
    aligned = sum(1 for score in usable if score * direction > 0.05)
    opposed = sum(1 for score in usable if score * direction < -0.15)
    value = 0.45 + 0.35 * magnitude + 0.05 * aligned - 0.1 * opposed
    return round(min(0.9, max(0.3, value)), 2)


def _indicator_sentence(tech: Dict[str, Any]) -> str:
    indicators = tech.get("indicators") or {}
    bits = []
    if indicators.get("rsi_14") is not None:
        bits.append(f"RSI (14): {format_number(indicators.get('rsi_14'), 2)}")
    if indicators.get("macd") is not None:
        bits.append(f"MACD: {format_number(indicators.get('macd'), 4)}")
    if indicators.get("sma_50") is not None:
        bits.append(f"SMA 50: {format_number(indicators.get('sma_50'), 2)}")
    if indicators.get("sma_200") is not None:
        bits.append(f"SMA 200: {format_number(indicators.get('sma_200'), 2)}")
    return ". ".join(bits)


def _pressure_sentence(tech: Dict[str, Any]) -> str:
    pressure = tech.get("buying_pressure") or {}
    if not pressure or not pressure.get("level"):
        return ""
    ratio = pressure.get("volume_ratio")
    if ratio is None:
        return f"Presión compradora: {pressure['level']}."
    return (
        f"Presión compradora: {pressure['level']}. "
        f"Ratio volumen vs promedio 20d: {format_number(ratio, 2)}x."
    )


def _scenario_sentence(tech: Dict[str, Any]) -> str:
    scenarios = tech.get("scenarios") or {}
    probs = scenarios.get("probabilities") or {}
    if not probs:
        return ""
    optimistic = int(probs.get("optimistic", 0))
    base = int(probs.get("base", 0))
    pessimistic = int(probs.get("pessimistic", 0))
    best = scenarios.get("best_scenario") or "base"
    best_prob = int(probs.get(best, 0))
    return (
        f"Escenarios: optimista {optimistic}%, base {base}%, pesimista {pessimistic}%. "
        f"Más probable: {scenario_label(best)} ({best_prob}%)."
    )


def generate_recommendation(state: Dict[str, Any]) -> Dict[str, Any]:
    tech = state.get("technical") or {}
    fund = state.get("fundamental") or {}
    sent = state.get("sentiment") or {}
    asset_type = state.get("asset_type") or (state.get("raw_data") or {}).get("asset_type") or "unknown"
    base_weights = WEIGHTS.get(asset_type, WEIGHTS["unknown"])

    technical = _technical_score(tech)
    fundamental = _fundamental_score(fund, asset_type)
    sentiment = _sentiment_score(sent)
    named_scores = {
        "technical": technical,
        "fundamental": fundamental,
        "sentiment": sentiment,
    }
    active: List[Tuple[str, float, float]] = [
        (name, score, base_weights.get(name, 0.0))
        for name, score in named_scores.items()
        if score is not None and base_weights.get(name, 0.0) > 0
    ]

    if not active:
        return {
            "signal": "NEUTRAL",
            "signal_label": "Neutral",
            "confidence": 0.35,
            "reasoning": "Sin datos suficientes para sintetizar una señal.",
            "projection": tech.get("projection") or "—",
            "scenarios": tech.get("scenarios") or {},
            "asset_type": asset_type,
            "components": {
                name: {"score": None, "weight": 0.0, "applied": False}
                for name in ("technical", "fundamental", "sentiment")
            },
        }

    weight_sum = sum(weight for _, _, weight in active)
    weights = {name: weight / weight_sum for name, _, weight in active}
    combined = sum(score * weights[name] for name, score, _ in active)

    if combined >= BUY_LEVEL:
        signal = "BUY"
    elif combined <= SELL_LEVEL:
        signal = "SELL"
    else:
        signal = "NEUTRAL"
    confidence = _confidence(signal, combined, [score for _, score, _ in active])

    components = {}
    for name in ("technical", "fundamental", "sentiment"):
        applied = name in weights
        components[name] = {
            "score": None if named_scores[name] is None else round(named_scores[name], 4),
            "weight": round(weights.get(name, 0.0), 4),
            "applied": applied,
        }
    components["technical"]["signal"] = tech.get("signal")
    components["sentiment"]["label"] = sent.get("label")

    projection = tech.get("projection") or "—"
    scenarios = tech.get("scenarios") or {}
    fund_summary = (fund.get("summary") or "Sin análisis fundamental.").strip()
    if sentiment is None:
        sent_summary = (sent.get("summary") or "Sentimiento no disponible; no entra en la ponderación.").strip()
    else:
        sent_summary = (sent.get("summary") or "Sin resumen de sentimiento.").strip()

    def _finish(text: str) -> str:
        text = " ".join(text.split())
        if text and text[-1] not in ".!?":
            return text + "."
        return text

    sentences = [
        (
            f"Señal final {signal_label(signal)} con confianza {confidence:.0%}. "
            f"Señal técnica: {signal_label(tech.get('signal') or 'NEUTRAL')}. "
            f"Proyección: {projection}."
        ),
        _indicator_sentence(tech),
        _pressure_sentence(tech),
        _scenario_sentence(tech),
        fund_summary,
        sent_summary,
        (
            "Ponderación efectiva: "
            f"técnico {weights.get('technical', 0):.0%}, "
            f"fundamental {weights.get('fundamental', 0):.0%}, "
            f"sentimiento {weights.get('sentiment', 0):.0%}."
        ),
    ]
    reasoning = " ".join(_finish(sentence) for sentence in sentences if sentence and sentence.strip())

    return {
        "signal": signal,
        "signal_label": signal_label(signal),
        "confidence": confidence,
        "reasoning": reasoning,
        "projection": projection,
        "scenarios": scenarios,
        "asset_type": asset_type,
        "combined_score": round(combined, 4),
        "components": components,
    }
