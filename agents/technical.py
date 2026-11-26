"""
Agente 2: Technical Analyst
Análisis técnico + escenarios con probabilidades + presión compradora.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line, macd - signal_line

def analyze_buying_pressure(df: pd.DataFrame) -> Dict[str, Any]:
    """Analiza presión compradora con volumen y precio."""
    if "Volume" not in df.columns or "Close" not in df.columns or len(df) < 20:
        return {"level": "Sin datos de volumen", "description": "No hay volumen suficiente", "score": 0}
    
    volume = df["Volume"].astype(float)
    close = df["Close"].astype(float)
    
    # Volumen promedio 20 y 50 días
    vol_20 = volume.rolling(20).mean().iloc[-1]
    vol_50 = volume.rolling(50).mean().iloc[-1] if len(volume) >= 50 else vol_20
    last_vol = volume.iloc[-1]
    
    # Ratio de volumen reciente
    vol_ratio = last_vol / vol_20 if vol_20 > 0 else 1
    
    # Tendencia de volumen (últimos 10 días vs anteriores)
    recent_vol = volume.tail(10).mean()
    older_vol = volume.tail(30).head(20).mean() if len(volume) >= 30 else recent_vol
    vol_trend = recent_vol / older_vol if older_vol > 0 else 1
    
    # Precio subiendo con volumen alto = compra fuerte
    price_change_5d = (close.iloc[-1] / close.iloc[-5] - 1) if len(close) >= 5 else 0
    
    # Clasificación
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
        "volume_ratio": round(vol_ratio, 2),
        "volume_trend": round(vol_trend, 2)
    }

def project_scenarios(close: pd.Series, days: int = 90, score: int = 0) -> Dict[str, Any]:
    if len(close) < 30:
        return {}
    
    last_price = float(close.iloc[-1])
    returns = close.pct_change().dropna()
    vol = float(returns.std()) if len(returns) > 0 else 0.01
    recent_trend = (close.iloc[-1] / close.iloc[-30] - 1) / 30 if len(close) >= 30 else 0
    
    future_dates = pd.date_range(start=close.index[-1], periods=days+1, freq="B")[1:]
    
    optimistic = [last_price]
    base = [last_price]
    pessimistic = [last_price]
    
    for _ in range(days):
        optimistic.append(optimistic[-1] * (1 + recent_trend + vol * 0.9))
        base.append(base[-1] * (1 + recent_trend * 0.25))
        pessimistic.append(pessimistic[-1] * (1 + recent_trend - vol * 0.9))
    
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
    
    total = sum(probs.values())
    probs = {k: round(v / total * 100) for k, v in probs.items()}
    
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in future_dates],
        "optimistic": [round(x, 2) for x in optimistic[1:]],
        "base": [round(x, 2) for x in base[1:]],
        "pessimistic": [round(x, 2) for x in pessimistic[1:]],
        "probabilities": probs,
        "best_scenario": max(probs, key=probs.get)
    }

def analyze_technical(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "signal": "NEUTRAL",
        "confidence": 0.5,
        "indicators": {},
        "support_resistance": {},
        "projection": "Base",
        "scenarios": {},
        "buying_pressure": {},
        "notes": []
    }

    yf_source = raw_data.get("sources", {}).get("yfinance", {})
    history = yf_source.get("history")
    
    if not history or not isinstance(history, dict):
        result["notes"].append("No hay datos históricos suficientes")
        return result

    try:
        df = pd.DataFrame(history)
        if "Close" not in df.columns or len(df) < 50:
            result["notes"].append("Datos insuficientes para análisis técnico")
            return result

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        close = df["Close"].astype(float)
        
        # Presión compradora
        result["buying_pressure"] = analyze_buying_pressure(df)
        
        sma_20 = close.rolling(20).mean()
        sma_50 = close.rolling(50).mean()
        sma_200 = close.rolling(200).mean()
        rsi = calculate_rsi(close, 14)
        macd, signal_line, _ = calculate_macd(close)
        
        last_close = float(close.iloc[-1])
        last_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
        last_macd = float(macd.iloc[-1]) if not pd.isna(macd.iloc[-1]) else None
        last_signal = float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else None
        last_sma50 = float(sma_50.iloc[-1]) if not pd.isna(sma_50.iloc[-1]) else None
        last_sma200 = float(sma_200.iloc[-1]) if not pd.isna(sma_200.iloc[-1]) else None
        
        result["indicators"] = {
            "price": round(last_close, 2),
            "rsi_14": round(last_rsi, 2) if last_rsi else None,
            "macd": round(last_macd, 4) if last_macd else None,
            "macd_signal": round(last_signal, 4) if last_signal else None,
            "sma_20": round(float(sma_20.iloc[-1]), 2) if not pd.isna(sma_20.iloc[-1]) else None,
            "sma_50": round(last_sma50, 2) if last_sma50 else None,
            "sma_200": round(last_sma200, 2) if last_sma200 else None,
        }
        
        recent = close.tail(60)
        result["support_resistance"] = {
            "support": round(float(recent.min()), 2),
            "resistance": round(float(recent.max()), 2),
            "current": round(last_close, 2)
        }
        
        signals = []
        score = 0
        
        if last_rsi:
            if last_rsi < 30:
                signals.append("RSI sobrevendido")
                score += 2
            elif last_rsi > 70:
                signals.append("RSI sobrecomprado")
                score -= 2
        
        if last_sma50 and last_sma200:
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
        
        # Incorporar presión compradora al score
        bp_score = result["buying_pressure"].get("score", 0)
        score += bp_score
        if bp_score != 0:
            signals.append(result["buying_pressure"]["level"])
        
        if score >= 3:
            result["signal"] = "BUY"
            result["confidence"] = min(0.85, 0.55 + score * 0.04)
        elif score <= -3:
            result["signal"] = "SELL"
            result["confidence"] = min(0.85, 0.55 + abs(score) * 0.04)
        else:
            result["signal"] = "NEUTRAL"
            result["confidence"] = 0.5
        
        result["notes"] = signals
        
        if score > 0:
            result["projection"] = "Alcista"
        elif score < 0:
            result["projection"] = "Bajista"
        else:
            result["projection"] = "Lateral"
        
        result["scenarios"] = project_scenarios(close, days=90, score=score)
            
    except Exception as e:
        result["notes"].append(f"Error en cálculo técnico: {str(e)}")
    
    return result
