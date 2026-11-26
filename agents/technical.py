"""
Agente 2: Technical Analyst
Análisis técnico + escenarios con probabilidades + presión compradora.
"""
import math
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from core.prices import history_to_frame

SCENARIO_KEYS = ("optimistic", "base", "pessimistic")


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    # loss == 0 no puede dividir. Con ganancias el RSI es 100; si no hay movimiento, NaN.
    rs = gain / loss.where(loss > 0)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.mask((loss == 0) & (gain > 0), 100.0)
    rsi = rsi.mask((gain == 0) & (loss == 0), np.nan)
    return rsi


def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line, macd - signal_line


def normalize_probabilities(probs: Dict[str, float]) -> Dict[str, int]:
    """Reparte 100 puntos enteros. El redondeo independiente no siempre suma 100."""
    values = [max(0.0, float(probs.get(key, 0.0))) for key in SCENARIO_KEYS]
    total = sum(values)
    if total <= 0:
        return {"optimistic": 25, "base": 50, "pessimistic": 25}
    raw = [value / total * 100 for value in values]
    floors = [math.floor(value + 1e-9) for value in raw]
    remainder = 100 - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: (raw[i] - floors[i], raw[i]), reverse=True)
    step = 1 if remainder >= 0 else -1
    for offset in range(abs(remainder)):
        floors[order[offset % len(floors)]] += step
    return {key: int(floors[index]) for index, key in enumerate(SCENARIO_KEYS)}


def analyze_buying_pressure(df: pd.DataFrame) -> Dict[str, Any]:
    """Analiza presión compradora con volumen y precio."""
    if "Volume" not in df.columns or "Close" not in df.columns or len(df) < 20:
        return {"level": "Sin datos de volumen", "description": "No hay volumen suficiente", "score": 0}

    volume = df["Volume"].astype(float)
    close = df["Close"].astype(float)

    vol_20 = volume.rolling(20).mean().iloc[-1]
    last_vol = volume.iloc[-1]

    vol_ratio = last_vol / vol_20 if vol_20 > 0 else 1

    recent_vol = volume.tail(10).mean()
    older_vol = volume.tail(30).head(20).mean() if len(volume) >= 30 else recent_vol
    vol_trend = recent_vol / older_vol if older_vol > 0 else 1

    price_change_5d = (close.iloc[-1] / close.iloc[-5] - 1) if len(close) >= 5 else 0

    if vol_ratio > 1.8 and price_change_5d > 0.01:
        level = "Se está comprando mucho"
        desc = "Volumen muy alto y precio subiendo"
        score = 3
    elif vol_ratio > 1.3 and price_change_5d > 0:
        level = "Compra regular"
        desc = "Volumen por encima del promedio con precio positivo"
        score = 2
    elif vol_ratio > 0.8 and abs(price_change_5d) < 0.015:
        level = "Compradores manteniéndose"
        desc = "Volumen estable y precio lateral (posible acumulación)"
        score = 1
    elif vol_ratio < 0.6:
        level = "Compra muy baja"
        desc = "Volumen muy por debajo del promedio"
        score = -2
    elif vol_ratio < 0.85:
        level = "Compra baja"
        desc = "Volumen inferior al promedio"
        score = -1
    else:
        level = "Compra regular"
        desc = "Actividad de volumen normal"
        score = 1

    return {
        "level": level,
        "description": desc,
        "score": score,
        "volume_ratio": round(float(vol_ratio), 2),
        "volume_trend": round(float(vol_trend), 2),
    }


def project_scenarios(close: pd.Series, days: int = 90, score: int = 0) -> Dict[str, Any]:
    if len(close) < 30:
        return {}

    last_price = float(close.iloc[-1])
    returns = close.pct_change().dropna()
    vol = float(returns.std()) if len(returns) > 0 else 0.01
    if not math.isfinite(vol) or vol <= 0:
        vol = 0.01
    # Un tope evita que un activo muy nervioso dibuje un cono de varios múltiplos.
    vol = min(vol, 0.08)
    recent_trend = (close.iloc[-1] / close.iloc[-30] - 1) / 30 if len(close) >= 30 else 0.0
    if not math.isfinite(recent_trend):
        recent_trend = 0.0
    # El drift diario se acota: sumarlo sin límite durante 90 sesiones no es una proyección.
    drift = max(-0.004, min(0.004, recent_trend))

    future_dates = pd.date_range(start=close.index[-1], periods=days + 1, freq="B")[1:]

    optimistic = []
    base = []
    pessimistic = []
    for step in range(1, days + 1):
        center = last_price * math.exp(drift * 0.5 * step)
        # La banda crece con la raíz del tiempo, no componiendo la volatilidad cada día.
        spread = vol * math.sqrt(step) * 0.9
        optimistic.append(center * math.exp(spread))
        base.append(center)
        pessimistic.append(center * math.exp(-spread))

    if score >= 3:
        probs = {"optimistic": 45, "base": 35, "pessimistic": 20}
    elif score <= -3:
        probs = {"optimistic": 20, "base": 35, "pessimistic": 45}
    else:
        probs = {"optimistic": 25, "base": 50, "pessimistic": 25}

    if recent_trend > 0.001:
        probs["optimistic"] = min(55, probs["optimistic"] + 5)
        probs["pessimistic"] = max(15, probs["pessimistic"] - 5)
    elif recent_trend < -0.001:
        probs["pessimistic"] = min(55, probs["pessimistic"] + 5)
        probs["optimistic"] = max(15, probs["optimistic"] - 5)

    probs = normalize_probabilities(probs)

    return {
        "dates": [d.strftime("%Y-%m-%d") for d in future_dates],
        "optimistic": [round(x, 2) for x in optimistic],
        "base": [round(x, 2) for x in base],
        "pessimistic": [round(x, 2) for x in pessimistic],
        "probabilities": probs,
        "best_scenario": max(probs, key=probs.get),
    }


def score_technical(
    last_rsi: Optional[float],
    last_close: Optional[float],
    last_sma50: Optional[float],
    last_sma200: Optional[float],
    last_macd: Optional[float],
    last_signal: Optional[float],
    bp_score: int = 0,
    bp_level: Optional[str] = None,
) -> Dict[str, Any]:
    """Convierte indicadores ya calculados en señal. RSI 0.0 cuenta como sobreventa."""
    signals = []
    score = 0

    if last_rsi is not None:
        if last_rsi < 30:
            signals.append("RSI sobrevendido")
            score += 2
        elif last_rsi > 70:
            signals.append("RSI sobrecomprado")
            score -= 2

    if last_sma50 is not None and last_sma200 is not None and last_close is not None:
        if last_close > last_sma50 > last_sma200:
            signals.append("Tendencia alcista")
            score += 2
        elif last_close < last_sma50 < last_sma200:
            signals.append("Tendencia bajista")
            score -= 2

    if last_macd is not None and last_signal is not None:
        if last_macd > last_signal:
            signals.append("MACD alcista")
            score += 1
        else:
            signals.append("MACD bajista")
            score -= 1

    try:
        bp_score = int(bp_score or 0)
    except (TypeError, ValueError):
        bp_score = 0
    if bp_score != 0:
        score += bp_score
        if bp_level:
            signals.append(bp_level)

    if score >= 3:
        signal = "BUY"
        confidence = min(0.85, 0.55 + score * 0.04)
        projection = "Alcista"
    elif score <= -3:
        signal = "SELL"
        confidence = min(0.85, 0.55 + abs(score) * 0.04)
        projection = "Bajista"
    else:
        signal = "NEUTRAL"
        confidence = 0.5
        if score > 0:
            projection = "Alcista"
        elif score < 0:
            projection = "Bajista"
        else:
            projection = "Lateral"

    return {
        "score": score,
        "signal": signal,
        "confidence": round(float(confidence), 2),
        "notes": signals,
        "projection": projection,
    }


def _last_number(series: pd.Series) -> Optional[float]:
    if series is None or len(series) == 0:
        return None
    value = series.iloc[-1]
    if pd.isna(value):
        return None
    return float(value)


def _load_price_frame(raw_data: Dict[str, Any]) -> Optional[pd.DataFrame]:
    frame = history_to_frame((raw_data or {}).get("history"))
    if frame is not None:
        return frame
    yf_history = ((raw_data or {}).get("sources") or {}).get("yfinance", {}).get("history")
    return history_to_frame(yf_history)


def _trend_label(price, sma50, sma200) -> str:
    if price is None:
        return "Sin dato"
    if sma50 is not None and sma200 is not None:
        if price > sma50 > sma200:
            return "Alcista"
        if price < sma50 < sma200:
            return "Bajista"
        return "Lateral"
    if sma50 is not None and price > sma50:
        return "Alcista"
    if sma50 is not None and price < sma50:
        return "Bajista"
    return "Lateral"


def analyze_technical(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "signal": "NEUTRAL",
        "confidence": 0.5,
        "indicators": {},
        "support_resistance": {},
        "projection": "Lateral",
        "scenarios": {},
        "buying_pressure": {},
        "notes": [],
    }

    frame = _load_price_frame(raw_data or {})
    if frame is None:
        result["notes"].append("No hay datos históricos suficientes")
        return result

    try:
        if "Close" not in frame.columns or len(frame) < 50:
            result["notes"].append("Datos insuficientes para análisis técnico")
            return result

        close = frame["Close"].astype(float)
        result["buying_pressure"] = analyze_buying_pressure(frame)

        sma_20 = close.rolling(20).mean()
        sma_50 = close.rolling(50).mean()
        sma_200 = close.rolling(200).mean()
        rsi = calculate_rsi(close, 14)
        macd, signal_line, _ = calculate_macd(close)

        last_close = _last_number(close)
        last_rsi = _last_number(rsi)
        last_macd = _last_number(macd)
        last_signal = _last_number(signal_line)
        last_sma20 = _last_number(sma_20)
        last_sma50 = _last_number(sma_50)
        last_sma200 = _last_number(sma_200)

        # 0.0 es un RSI válido (sobreventa extrema); no tratarlo como vacío.
        distance = None
        if last_close not in (None, 0) and last_sma50 not in (None, 0):
            distance = round((last_close / last_sma50 - 1) * 100, 2)
        result["indicators"] = {
            "price": round(last_close, 2) if last_close is not None else None,
            "rsi_14": round(last_rsi, 2) if last_rsi is not None else None,
            "macd": round(last_macd, 4) if last_macd is not None else None,
            "macd_signal": round(last_signal, 4) if last_signal is not None else None,
            "sma_20": round(last_sma20, 2) if last_sma20 is not None else None,
            "sma_50": round(last_sma50, 2) if last_sma50 is not None else None,
            "sma_200": round(last_sma200, 2) if last_sma200 is not None else None,
            "trend": _trend_label(last_close, last_sma50, last_sma200),
            "distance_sma50_pct": distance,
        }

        recent = close.tail(60)
        result["support_resistance"] = {
            "support": round(float(recent.min()), 2),
            "resistance": round(float(recent.max()), 2),
            "current": round(last_close, 2) if last_close is not None else None,
        }

        bp = result["buying_pressure"]
        # La señal usa las cifras ya redondeadas: son las que ve la interfaz.
        shown = result["indicators"]
        decision = score_technical(
            shown["rsi_14"],
            shown["price"],
            shown["sma_50"],
            shown["sma_200"],
            shown["macd"],
            shown["macd_signal"],
            bp.get("score", 0),
            bp.get("level"),
        )
        result["signal"] = decision["signal"]
        result["confidence"] = decision["confidence"]
        result["notes"] = decision["notes"]
        result["projection"] = decision["projection"]
        result["scenarios"] = project_scenarios(close, days=90, score=decision["score"])
    except Exception as exc:
        result["notes"].append(f"Error en cálculo técnico: {exc}")

    return result
