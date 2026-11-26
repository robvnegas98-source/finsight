"""Plan de day trading con velas de 5 minutos. No es una orden."""

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf

from agents.technical import calculate_macd, calculate_rsi
from core.assets import normalize_crypto_symbol
from core.prices import ohlcv_to_frame

OPENING_BARS = 6  # 30 minutos en velas de 5 minutos


def fetch_intraday(ticker: str, asset_type: str = "") -> Tuple[Optional[pd.DataFrame], List[str]]:
    """Últimos días en velas de 5 minutos. Yahoo primero; en cripto, CCXT si Yahoo falla."""
    notes: List[str] = []
    frame = _download_yahoo(ticker, notes)
    if frame is None and asset_type == "crypto":
        frame = _download_ccxt(ticker, notes)
    return frame, notes


def _download_yahoo(ticker: str, notes: List[str]) -> Optional[pd.DataFrame]:
    try:
        history = yf.Ticker(ticker).history(period="5d", interval="5m", auto_adjust=True)
    except Exception as exc:
        notes.append(f"No se pudieron bajar velas de 5 minutos ({type(exc).__name__}).")
        return None
    if history is None or history.empty or "Close" not in history.columns:
        notes.append("Yahoo no devolvió velas de 5 minutos.")
        return None
    return history


def _download_ccxt(ticker: str, notes: List[str]) -> Optional[pd.DataFrame]:
    try:
        import ccxt

        symbol = normalize_crypto_symbol(ticker)
        exchange = ccxt.binance({"enableRateLimit": True, "timeout": 12000})
        candles = exchange.fetch_ohlcv(symbol, timeframe="5m", limit=500)
    except Exception as exc:
        notes.append(f"Tampoco hubo velas de 5 minutos en CCXT ({type(exc).__name__}).")
        return None
    if not candles:
        notes.append("CCXT no devolvió velas de 5 minutos.")
        return None
    return ohlcv_to_frame(candles)


def analyze_session(frame: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """Arma el plan del día a partir de velas ya descargadas."""
    empty = _empty("No hay velas de 5 minutos para armar el plan de hoy.")
    if frame is None or frame.empty or "Close" not in frame.columns:
        return empty

    data = frame.copy()
    if not isinstance(data.index, pd.DatetimeIndex):
        data.index = pd.to_datetime(data.index, errors="coerce")
    data = data[~data.index.isna()].sort_index()
    for column in ("Open", "High", "Low", "Close", "Volume"):
        if column not in data.columns:
            if column == "Volume":
                data[column] = 0.0
            else:
                return empty
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["Close"])
    if len(data) < OPENING_BARS:
        return _empty("Hay muy pocas velas de 5 minutos. Hace falta al menos media hora de sesión.")

    dates = pd.Series(data.index.date, index=data.index)
    sessions = list(dict.fromkeys(dates.tolist()))
    today = sessions[-1]
    session = data[dates == today]
    prior = data[dates == sessions[-2]] if len(sessions) > 1 else None
    if session.empty:
        return empty

    last = float(session["Close"].iloc[-1])
    or_bars = session.iloc[:OPENING_BARS]
    or_ready = len(session) >= OPENING_BARS
    or_high = float(or_bars["High"].max()) if or_ready else None
    or_low = float(or_bars["Low"].min()) if or_ready else None
    vwap = _session_vwap(session)
    ema9, ema21 = _emas(data["Close"])
    atr = _atr(data)
    pdh = float(prior["High"].max()) if prior is not None and not prior.empty else None
    pdl = float(prior["Low"].min()) if prior is not None and not prior.empty else None

    rsi = _last_indicator(calculate_rsi(data["Close"], 14))
    macd_line, macd_signal, _ = calculate_macd(data["Close"])
    macd_value = _last_indicator(macd_line)
    macd_signal_value = _last_indicator(macd_signal)
    plan = _decide(last, vwap, or_high, or_low, or_ready, ema9, ema21, atr)
    plan.update({
        "session": str(today),
        "price": _round_price(last),
        "vwap": _round_price(vwap),
        "opening_high": _round_price(or_high),
        "opening_low": _round_price(or_low),
        "previous_high": _round_price(pdh),
        "previous_low": _round_price(pdl),
        "ema9": _round_price(ema9),
        "ema21": _round_price(ema21),
        "atr": _round_price(atr),
        "rsi_14": None if rsi is None else round(rsi, 2),
        "macd": None if macd_value is None else round(macd_value, 4),
        "macd_signal": None if macd_signal_value is None else round(macd_signal_value, 4),
        "trend": _intraday_trend(last, ema9, ema21),
        "vwap_side": _vwap_side(last, vwap),
    })
    return plan


def _last_indicator(series: pd.Series) -> Optional[float]:
    if series is None or len(series) == 0:
        return None
    value = series.iloc[-1]
    if pd.isna(value):
        return None
    return float(value)


def _intraday_trend(price: float, ema9: Optional[float], ema21: Optional[float]) -> str:
    if ema9 is None or ema21 is None:
        return "Sin dato"
    if ema9 > ema21 and price > ema21:
        return "Alcista"
    if ema9 < ema21 and price < ema21:
        return "Bajista"
    return "Lateral"


def _vwap_side(price: float, vwap: Optional[float]) -> str:
    if vwap is None:
        return "Sin dato"
    if price > vwap:
        return "Por encima"
    if price < vwap:
        return "Por debajo"
    return "En el VWAP"


def _session_vwap(session: pd.DataFrame) -> Optional[float]:
    typical = (session["High"] + session["Low"] + session["Close"]) / 3
    volume = session["Volume"].fillna(0).clip(lower=0)
    if float(volume.sum()) <= 0:
        return float(session["Close"].mean())
    weighted = (typical * volume).cumsum() / volume.cumsum().replace(0, pd.NA)
    value = weighted.iloc[-1]
    if pd.isna(value):
        return float(session["Close"].iloc[-1])
    return float(value)


def _emas(close: pd.Series) -> Tuple[Optional[float], Optional[float]]:
    ema9 = close.ewm(span=9, adjust=False).mean().iloc[-1]
    ema21 = close.ewm(span=21, adjust=False).mean().iloc[-1]
    return float(ema9), float(ema21)


def _atr(data: pd.DataFrame) -> float:
    high = data["High"]
    low = data["Low"]
    close = data["Close"]
    previous = close.shift()
    true_range = pd.concat([
        high - low,
        (high - previous).abs(),
        (low - previous).abs(),
    ], axis=1).max(axis=1)
    value = true_range.rolling(14).mean().iloc[-1]
    if pd.isna(value) or float(value) <= 0:
        return max(float(close.iloc[-1]) * 0.002, 0.01)
    return float(value)


def _decide(last, vwap, or_high, or_low, or_ready, ema9, ema21, atr) -> Dict[str, Any]:
    if not or_ready or or_high is None or or_low is None or vwap is None:
        return _empty(
            "Espera a que pasen los primeros 30 minutos.",
            "El rango de apertura se marca con las primeras seis velas de 5 minutos. Todavía no entres.",
        )

    buy = last > vwap and last > or_high and ema9 > ema21
    sell = last < vwap and last < or_low and ema9 < ema21
    if buy:
        stop, target, risk = _bracket(last, min(or_low, vwap), atr, side="buy")
        return _plan(
            "compra",
            "Sí, para hoy puedes buscar una compra intradía.",
            (
                "El precio está por encima del VWAP y ya salió del rango de apertura al alza, "
                "con la media corta por encima de la media de 21. "
                "El stop queda debajo de ese nivel y el objetivo es el doble de lo que arriesgas. "
                "Cierra la operación antes del cierre: esto no se deja para mañana."
            ),
            last, stop, target, risk,
        )
    if sell:
        stop, target, risk = _bracket(last, max(or_high, vwap), atr, side="sell")
        return _plan(
            "venta",
            "Sí, para hoy puedes buscar una venta intradía, o no comprar si no operas en corto.",
            (
                "El precio está por debajo del VWAP y ya salió del rango de apertura a la baja, "
                "con la media corta por debajo de la media de 21. "
                "Si no vendes en corto, la decisión de hoy es quedarte fuera. "
                "Cierra la operación antes del cierre."
            ),
            last, stop, target, risk,
        )
    return _plan(
        "esperar",
        "Hoy no entres: el precio no tiene un lado claro.",
        (
            "Para un day trade quiero ver el precio del mismo lado del VWAP y fuera del rango "
            "de apertura, con las medias de 9 y 21 de acuerdo. Ahora mismo eso no se cumple. "
            "Operar en el medio del rango es donde más se pierde por comisiones y por el ruido."
        ),
        last, None, None, None,
    )


def _bracket(last: float, structural: float, atr: float, side: str):
    """El stop no se aleja más de 1,5 veces el ATR: si no, el día se vuelve una apuesta."""
    max_risk = max(atr * 1.5, abs(last) * 0.003, 0.01)
    if side == "buy":
        distance = last - structural
        risk = distance if 0 < distance <= max_risk else max_risk
        return last - risk, last + 2 * risk, risk
    distance = structural - last
    risk = distance if 0 < distance <= max_risk else max_risk
    return last + risk, last - 2 * risk, risk


def _plan(action, title, detail, entry, stop, target, risk) -> Dict[str, Any]:
    labels = {
        "compra": "Entrar en compra hoy",
        "venta": "Entrar en venta hoy",
        "esperar": "No operar hoy",
    }
    return {
        "action": action,
        "title": title,
        "detail": detail + " No es una orden ni un consejo de inversión personal.",
        "label": labels[action],
        "entry": _round_price(entry),
        "stop": _round_price(stop),
        "target": _round_price(target),
        "risk": _round_price(risk),
    }


def _empty(title: str, detail: str = "") -> Dict[str, Any]:
    text = detail or "Sin velas intradía no hay plan de day trading."
    return {
        "action": "esperar",
        "title": title,
        "detail": text + " No es una orden ni un consejo de inversión personal.",
        "label": "No operar hoy",
        "entry": None,
        "stop": None,
        "target": None,
        "risk": None,
        "session": None,
        "price": None,
        "vwap": None,
        "opening_high": None,
        "opening_low": None,
        "previous_high": None,
        "previous_low": None,
        "ema9": None,
        "ema21": None,
    }


def _round_price(value) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    digits = 2 if abs(number) >= 1 else 4
    return round(number, digits)


def daytrade_trend_table(plan: Dict[str, Any]) -> pd.DataFrame:
    plan = plan or {}
    macd = plan.get("macd")
    macd_signal = plan.get("macd_signal")
    if macd is None or macd_signal is None:
        macd_reading = "Sin dato"
    elif macd > macd_signal:
        macd_reading = "Por encima de su señal"
    elif macd < macd_signal:
        macd_reading = "Por debajo de su señal"
    else:
        macd_reading = "Junto a su señal"
    rsi = plan.get("rsi_14")
    if rsi is None:
        rsi_reading = "Sin dato"
    elif rsi < 30:
        rsi_reading = "Sobreventa en el día"
    elif rsi > 70:
        rsi_reading = "Sobrecompra en el día"
    else:
        rsi_reading = "Zona media"
    trend = plan.get("trend") or "Sin dato"
    trend_reading = {
        "Alcista": "La media de 9 va por encima de la de 21 y el precio las acompaña",
        "Bajista": "La media de 9 va por debajo de la de 21 y el precio las acompaña",
        "Lateral": "Las medias cortas no van en el mismo sentido",
    }.get(trend, "Sin dato")
    side = plan.get("vwap_side") or "Sin dato"
    side_reading = {
        "Por encima": "El día está del lado comprador",
        "Por debajo": "El día está del lado vendedor",
        "En el VWAP": "El precio está pegado al promedio del día",
    }.get(side, "Sin dato")
    rows = [
        ["Tendencia corta", trend, trend_reading],
        ["Precio contra el VWAP", side, side_reading],
        ["RSI 14 de 5 minutos", "—" if rsi is None else rsi, rsi_reading],
        ["MACD de 5 minutos", "—" if macd is None else macd, macd_reading],
        ["ATR 14", "—" if plan.get("atr") is None else plan.get("atr"), "Cuánto se mueve una vela típica"],
        ["Media de 9", "—" if plan.get("ema9") is None else plan.get("ema9"), "Media rápida"],
        ["Media de 21", "—" if plan.get("ema21") is None else plan.get("ema21"), "Media lenta del día"],
    ]
    return pd.DataFrame(rows, columns=["Indicador", "Valor", "Lectura"])


def daytrade_levels_table(plan: Dict[str, Any]) -> pd.DataFrame:
    def money(value):
        if value is None:
            return "—"
        return f"{value}"

    return pd.DataFrame([
        ["Sesión", plan.get("session") or "—"],
        ["Precio", money(plan.get("price"))],
        ["VWAP de hoy", money(plan.get("vwap"))],
        ["Rango de apertura, suelo", money(plan.get("opening_low"))],
        ["Rango de apertura, techo", money(plan.get("opening_high"))],
        ["Máximo de ayer", money(plan.get("previous_high"))],
        ["Mínimo de ayer", money(plan.get("previous_low"))],
        ["Media de 9 velas", money(plan.get("ema9"))],
        ["Media de 21 velas", money(plan.get("ema21"))],
        ["Entrada de referencia", money(plan.get("entry"))],
        ["Stop", money(plan.get("stop"))],
        ["Objetivo (el doble del riesgo)", money(plan.get("target"))],
        ["Riesgo por unidad", money(plan.get("risk"))],
    ], columns=["Concepto", "Valor"])


DAYTRADE_STEPS = [
    "Antes de abrir, anota el máximo, el mínimo y el cierre de ayer.",
    "Los primeros 30 minutos marcan el rango de apertura. No entres a ciegas en ese tramo.",
    "Compra solo si el precio queda por encima del VWAP. Vende solo si queda por debajo.",
    "El stop se escribe antes de entrar. Si el precio lo toca, se sale.",
    "El objetivo de este plan es ganar el doble de lo que arriesgas.",
    "Cierra la operación antes del cierre del mercado. Un day trade no se deja para mañana.",
    "Arriesga poco en cada intento. En cuentas de Estados Unidos con menos de 25.000 dólares el broker limita los day trades.",
]
