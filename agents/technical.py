"""
Agente 2: Technical Analyst
Análisis técnico + escenarios con probabilidades + presión compradora.
Incluye Volume Profile y Net GEX (para ETFs).
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

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

def calculate_volume_profile(df: pd.DataFrame, bins: int = 100) -> Dict[str, Any]:
    """Volume Profile aproximado a partir de OHLCV.
    Distribuye el volumen de cada vela uniformemente en su rango High-Low.
    """
    if "Volume" not in df.columns or "High" not in df.columns or "Low" not in df.columns or len(df) < 20:
        return {}
    
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    volume = df["Volume"].astype(float)
    close = df["Close"].astype(float)
    
    price_min = float(low.min())
    price_max = float(high.max())
    if price_max <= price_min:
        return {}
    
    edges = np.linspace(price_min, price_max, bins + 1)
    vol_at_price = np.zeros(bins)
    
    for h, l, v in zip(high, low, volume):
        if pd.isna(h) or pd.isna(l) or pd.isna(v) or v <= 0 or h <= l:
            continue
        start_idx = np.searchsorted(edges, l, side="right") - 1
        end_idx = np.searchsorted(edges, h, side="left")
        start_idx = max(0, start_idx)
        end_idx = min(bins, end_idx)
        if end_idx > start_idx:
            vol_at_price[start_idx:end_idx] += v / (end_idx - start_idx)
    
    if vol_at_price.sum() == 0:
        return {}
    
    poc_idx = int(np.argmax(vol_at_price))
    poc_price = float((edges[poc_idx] + edges[poc_idx + 1]) / 2)
    
    total_vol = vol_at_price.sum()
    target = total_vol * 0.70
    sorted_idx = np.argsort(vol_at_price)[::-1]
    cum = 0.0
    va_indices = []
    for idx in sorted_idx:
        cum += vol_at_price[idx]
        va_indices.append(idx)
        if cum >= target:
            break
    va_low = float(edges[min(va_indices)])
    va_high = float(edges[max(va_indices) + 1])
    
    last_price = float(close.iloc[-1])
    position = "dentro del Value Area"
    if last_price > va_high:
        position = "por encima del Value Area"
    elif last_price < va_low:
        position = "por debajo del Value Area"
    
    return {
        "poc": round(poc_price, 2),
        "value_area_low": round(va_low, 2),
        "value_area_high": round(va_high, 2),
        "current_position": position,
        "volume_at_poc": round(float(vol_at_price[poc_idx]), 0)
    }

def calculate_approx_delta(df: pd.DataFrame, window: int = 20) -> Dict[str, Any]:
    """Delta aproximado usando tick rule simple (close vs previous close).
    NO es order flow real. Solo una estimación de presión compradora/vendedora.
    """
    if "Close" not in df.columns or "Volume" not in df.columns or len(df) < window + 1:
        return {"available": False, "note": "Datos insuficientes"}
    
    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float)
    
    direction = np.sign(close.diff())
    direction = direction.fillna(0)
    
    bar_delta = volume * direction
    
    recent_delta = float(bar_delta.tail(window).sum())
    recent_vol = float(volume.tail(window).sum())
    delta_pct = (recent_delta / recent_vol * 100) if recent_vol > 0 else 0
    
    if delta_pct > 15:
        bias = "Sesgo comprador (aprox.)"
        score = 1
    elif delta_pct < -15:
        bias = "Sesgo vendedor (aprox.)"
        score = -1
    else:
        bias = "Equilibrado (aprox.)"
        score = 0
    
    return {
        "available": True,
        "recent_delta": round(recent_delta, 0),
        "delta_pct": round(delta_pct, 1),
        "bias": bias,
        "score": score,
        "note": "Aproximación con tick rule. No es order flow real (falta lado del agresor)."
    }

def calculate_net_gex(ticker: str, spot: float) -> Dict[str, Any]:
    """Net Gamma Exposure mejorado para ETFs/acciones con opciones.
    Usa más expiraciones y calcula T real por cada vencimiento.
    """
    try:
        import yfinance as yf
        from scipy.stats import norm
        from datetime import datetime
    except ImportError:
        return {"available": False, "note": "Falta yfinance o scipy"}
    
    try:
        yf_ticker = yf.Ticker(ticker)
        expirations = yf_ticker.options
        if not expirations:
            return {"available": False, "note": "Sin cadena de opciones"}
        
        net_gex = 0.0
        call_wall = None
        put_wall = None
        max_call_gex = 0.0
        max_put_gex = 0.0
        today = datetime.now()
        
        for exp_str in expirations[:6]:
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d")
                T = max((exp_date - today).days / 365.0, 1/365.0)
            except Exception:
                T = 30 / 365.0
            
            chain = yf_ticker.option_chain(exp_str)
            for side, df, sign in [("call", chain.calls, 1), ("put", chain.puts, -1)]:
                if df.empty or "openInterest" not in df.columns or "impliedVolatility" not in df.columns:
                    continue
                for _, row in df.iterrows():
                    oi = float(row.get("openInterest", 0) or 0)
                    iv = float(row.get("impliedVolatility", 0) or 0)
                    strike = float(row.get("strike", 0) or 0)
                    if oi <= 0 or iv <= 0.01 or strike <= 0:
                        continue
                    if T <= 0 or spot <= 0:
                        continue
                    d1 = (np.log(spot / strike) + (0.5 * iv**2) * T) / (iv * np.sqrt(T))
                    gamma = norm.pdf(d1) / (spot * iv * np.sqrt(T))
                    gex = sign * gamma * oi * 100 * (spot ** 2) * 0.01
                    net_gex += gex
                    if side == "call" and abs(gex) > max_call_gex:
                        max_call_gex = abs(gex)
                        call_wall = strike
                    if side == "put" and abs(gex) > max_put_gex:
                        max_put_gex = abs(gex)
                        put_wall = strike
        
        regime = "Gamma positiva (estabilizadora)" if net_gex > 0 else "Gamma negativa (amplificadora)" if net_gex < 0 else "Neutra"
        
        return {
            "available": True,
            "net_gex": round(net_gex, 0),
            "regime": regime,
            "call_wall": round(call_wall, 2) if call_wall else None,
            "put_wall": round(put_wall, 2) if put_wall else None,
            "note": "Aproximación con hasta 6 expiraciones y T real. Útil para contexto de medio plazo en ETFs."
        }
    except Exception as e:
        return {"available": False, "note": f"Error GEX: {str(e)}"}

def analyze_buying_pressure(df: pd.DataFrame) -> Dict[str, Any]:
    """Analiza presión compradora con volumen y precio."""
    if "Volume" not in df.columns or "Close" not in df.columns or len(df) < 20:
        return {"level": "Sin datos de volumen", "description": "No hay volumen suficiente", "score": 0}
    
    volume = df["Volume"].astype(float)
    close = df["Close"].astype(float)
    
    vol_20 = volume.rolling(20).mean().iloc[-1]
    vol_50 = volume.rolling(50).mean().iloc[-1] if len(volume) >= 50 else vol_20
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
        "volume_profile": {},
        "net_gex": {},
        "approx_delta": {},
        "projection": "Base",
        "scenarios": {},
        "buying_pressure": {},
        "notes": []
    }

    yf_source = raw_data.get("sources", {}).get("yfinance", {})
    history = yf_source.get("history")
    ticker = raw_data.get("ticker", "")
    
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
        
        result["buying_pressure"] = analyze_buying_pressure(df)
        
        result["volume_profile"] = calculate_volume_profile(df, bins=100)
        
        result["approx_delta"] = calculate_approx_delta(df)
        
        is_etf_like = ticker.upper() in ["SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "TLT", "HYG", "LQD", "EEM", "XLF", "XLE", "XLK", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "VNQ", "ARKK"] or ticker.endswith("ETF") or "ETF" in ticker.upper()
        if is_etf_like or len(ticker) <= 5:
            last_price = float(close.iloc[-1])
            result["net_gex"] = calculate_net_gex(ticker, last_price)
        
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
        
        ad = result["approx_delta"]
        if ad.get("available") and ad.get("score", 0) != 0:
            signals.append(ad.get("bias", ""))
            score += ad.get("score", 0)
        
        vp = result["volume_profile"]
        if vp:
            pos = vp.get("current_position", "")
            if "por encima" in pos:
                signals.append("Precio por encima del Value Area")
                score += 1
            elif "por debajo" in pos:
                signals.append("Precio por debajo del Value Area")
                score -= 1
            signals.append(f"POC: {vp.get('poc')}")
        
        gex = result["net_gex"]
        if gex.get("available"):
            regime = gex.get("regime", "")
            if "positiva" in regime:
                signals.append(regime)
                score += 1
            elif "negativa" in regime:
                signals.append(regime)
                score -= 1
        
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
