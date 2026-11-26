"""Plan de day trading con velas de 5 minutos. No es una orden."""

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
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


def normalize_intraday(history: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """Acepta el formato de Yahoo, incluso si las columnas vienen en dos niveles."""
    if history is None or len(history) == 0:
        return None
    frame = history.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    renamed = {}
    for column in frame.columns:
        key = str(column).lower().replace(" ", "")
        if key in {"open", "high", "low", "close", "volume"}:
            renamed[column] = "Volume" if key == "volume" else key.capitalize()
    frame = frame.rename(columns=renamed)
    if "Close" not in frame.columns:
        return None
    keep = [column for column in ("Open", "High", "Low", "Close", "Volume") if column in frame.columns]
    frame = frame[keep].dropna(subset=["Close"])
    if frame.empty:
        return None
    if not isinstance(frame.index, pd.DatetimeIndex):
        frame.index = pd.to_datetime(frame.index, errors="coerce")
        frame = frame[~frame.index.isna()]
    return frame.sort_index()


def _download_yahoo(ticker: str, notes: List[str]) -> Optional[pd.DataFrame]:
    attempts = (
        ("historial", lambda: yf.Ticker(ticker).history(period="5d", interval="5m", auto_adjust=False)),
        ("descarga", lambda: yf.download(ticker, period="5d", interval="5m", auto_adjust=False, progress=False, threads=False)),
        ("un día", lambda: yf.Ticker(ticker).history(period="1d", interval="5m", auto_adjust=False)),
    )
    for name, load in attempts:
        try:
            frame = normalize_intraday(load())
        except Exception as exc:
            notes.append(f"Yahoo ({name}) no dio velas de 5 minutos ({type(exc).__name__}).")
            continue
        if frame is not None:
            return frame
    notes.append("Yahoo no devolvió velas de 5 minutos.")
    return None


def _download_ccxt(ticker: str, notes: List[str]) -> Optional[pd.DataFrame]:
    try:
        import ccxt
    except Exception as exc:
        notes.append(f"CCXT no está disponible ({type(exc).__name__}).")
        return None
    symbol = normalize_crypto_symbol(ticker)
    base = symbol.split("/")[0] if "/" in symbol else symbol
    attempts = (
        ("binance", f"{base}/USDT"),
        ("kraken", f"{base}/USD"),
        ("coinbase", f"{base}/USD"),
    )
    for exchange_id, pair in attempts:
        try:
            exchange = getattr(ccxt, exchange_id)({"enableRateLimit": True, "timeout": 12000})
            candles = exchange.fetch_ohlcv(pair, timeframe="5m", limit=500)
        except Exception as exc:
            notes.append(f"{exchange_id} no dio velas de 5 minutos ({type(exc).__name__}).")
            continue
        frame = ohlcv_to_frame(candles) if candles else None
        if frame is not None and not frame.empty:
            return frame
    notes.append("Ningún exchange devolvió velas de 5 minutos.")
    return None


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
        "volume_ratio": _volume_pace(session, data),
    })
    return plan


def _volume_pace(session: pd.DataFrame, data: pd.DataFrame) -> Optional[float]:
    """Volumen de las últimas velas contra el promedio. Los foros lo usan para ver si la tendencia tiene respaldo."""
    baseline = float(data["Volume"].fillna(0).mean()) if len(data) else 0.0
    recent = session["Volume"].fillna(0).tail(6)
    if baseline <= 0 or recent.empty:
        return None
    return round(float(recent.mean()) / baseline, 2)


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
    entry_r = _round_price(entry)
    stop_r = _round_price(stop)
    target_r = _round_price(target)
    prices = _entry_exit_sentence(action, entry_r, stop_r, target_r)
    text = f"{prices} {detail}".strip() if prices else detail
    return {
        "action": action,
        "title": title,
        "detail": text + " No es una orden ni un consejo de inversión personal.",
        "label": labels[action],
        "entry": entry_r,
        "stop": stop_r,
        "target": target_r,
        "risk": _round_price(risk),
    }


def _entry_exit_sentence(action, entry, stop, target) -> str:
    if action == "esperar" or entry is None or stop is None or target is None:
        return ""
    if action == "compra":
        return (
            f"Entrada: compras cerca de {entry}. "
            f"Salida con ganancia: vendes si llega a {target}. "
            f"Salida con pérdida: vendes si cae a {stop}."
        )
    return (
        f"Entrada: vendes cerca de {entry}. "
        f"Salida con ganancia: recompras si baja a {target}. "
        f"Salida con pérdida: cierras si sube a {stop}."
    )


def swing_entry_exit(tech: Optional[Dict[str, Any]], signal: str) -> Dict[str, Any]:
    """Entrada y salida para el análisis de varias semanas, usando precio, soporte y resistencia."""
    tech = tech or {}
    indicators = tech.get("indicators") or {}
    levels = tech.get("support_resistance") or {}
    price = indicators.get("price")
    support = levels.get("support")
    resistance = levels.get("resistance")
    base_path = (tech.get("scenarios") or {}).get("base") or []
    base = base_path[-1] if base_path else None
    if price is None or signal not in {"BUY", "SELL"}:
        return {
            "action": "esperar",
            "entry": None,
            "stop": None,
            "target": None,
            "detail": "No marco entrada ni salida: la señal de varias semanas no es ni compra ni venta.",
        }
    price = float(price)
    if signal == "BUY":
        stop = float(support) if support is not None and float(support) < price else round(price * 0.97, 2)
        target = float(resistance) if resistance is not None and float(resistance) > price else None
        if target is None or target <= price:
            target = float(base) if base is not None and float(base) > price else price + 2 * (price - stop)
        action = "compra"
    else:
        stop = float(resistance) if resistance is not None and float(resistance) > price else round(price * 1.03, 2)
        target = float(support) if support is not None and float(support) < price else None
        if target is None or target >= price:
            target = float(base) if base is not None and float(base) < price else price - 2 * (stop - price)
        action = "venta"
    entry_r, stop_r, target_r = _round_price(price), _round_price(stop), _round_price(target)
    return {
        "action": action,
        "entry": entry_r,
        "stop": stop_r,
        "target": target_r,
        "detail": _entry_exit_sentence(action, entry_r, stop_r, target_r),
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


def entry_exit_table(levels: Optional[Dict[str, Any]]) -> pd.DataFrame:
    levels = levels or {}
    if levels.get("entry") is None:
        return pd.DataFrame(columns=["Paso", "Precio"])
    return pd.DataFrame([
        ["Entrada", levels.get("entry")],
        ["Salida con ganancia", levels.get("target")],
        ["Salida con pérdida", levels.get("stop")],
    ], columns=["Paso", "Precio"])


def add_entry_exit_lines(fig: go.Figure, levels: Optional[Dict[str, Any]]) -> go.Figure:
    levels = levels or {}
    if levels.get("entry") is None:
        return fig
    for key, color, name, position in (
        ("entry", "#2563eb", "Entrada", "right"),
        ("target", "#047857", "Salida con ganancia", "top right"),
        ("stop", "#b91c1c", "Salida con pérdida", "bottom right"),
    ):
        value = levels.get(key)
        if value is None:
            continue
        fig.add_hline(
            y=float(value),
            line_color=color,
            line_width=2,
            annotation_text=f"{name} {value}",
            annotation_position=position,
        )
    return fig


def intraday_entry_chart(frame: Optional[pd.DataFrame], plan: Optional[Dict[str, Any]] = None) -> Optional[go.Figure]:
    """Velas de 5 minutos. Si hay operación, marca la entrada y las dos salidas."""
    data = normalize_intraday(frame)
    if data is None or data.empty:
        return None
    for column in ("Open", "High", "Low"):
        if column not in data.columns:
            data[column] = data["Close"]
    dates = list(dict.fromkeys(data.index.date))
    visible = data[pd.Series(data.index.date, index=data.index).isin(dates[-2:])]
    figure = go.Figure()
    figure.add_trace(go.Candlestick(
        x=visible.index,
        open=visible["Open"],
        high=visible["High"],
        low=visible["Low"],
        close=visible["Close"],
        name="Velas de 5 minutos",
        increasing_line_color="#047857",
        decreasing_line_color="#b91c1c",
    ))
    if plan and plan.get("entry") is not None:
        add_entry_exit_lines(figure, plan)
    figure.update_layout(
        height=520,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        font=dict(color="#1e293b"),
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis_rangeslider_visible=False,
    )
    figure.update_xaxes(gridcolor="#e2e8f0")
    figure.update_yaxes(gridcolor="#e2e8f0")
    return figure


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
    volume_ratio = plan.get("volume_ratio")
    if volume_ratio is None:
        volume_text, volume_reading = "—", "Sin dato de volumen"
    elif volume_ratio >= 1.3:
        volume_text, volume_reading = f"{volume_ratio}x", "Volumen alto: la tendencia tiene respaldo"
    elif volume_ratio <= 0.7:
        volume_text, volume_reading = f"{volume_ratio}x", "Volumen bajo: la tendencia es débil"
    else:
        volume_text, volume_reading = f"{volume_ratio}x", "Volumen normal"
    rows = [
        ["1. VWAP", side, side_reading],
        ["2. Medias 9 y 21", trend, trend_reading],
        ["3. RSI", "—" if rsi is None else rsi, rsi_reading],
        ["4. MACD", "—" if macd is None else macd, macd_reading],
        ["5. Volumen", volume_text, volume_reading],
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
