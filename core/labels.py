"""Textos compartidos por el Chief y la interfaz, para que muestren las mismas cifras."""

DISCLAIMER = (
    "Aviso: las señales, escenarios y textos de La Bobina Bursátil son informativos "
    "y no constituyen asesoramiento de inversión ni una recomendación de compra o venta."
)

SIGNAL_LABELS = {
    "BUY": "Compra",
    "SELL": "Venta",
    "NEUTRAL": "Neutral",
}

SCENARIO_LABELS = {
    "optimistic": "Optimista",
    "base": "Base",
    "pessimistic": "Pesimista",
}


def signal_label(signal: str) -> str:
    return SIGNAL_LABELS.get((signal or "").upper(), signal or "—")


def scenario_label(name: str) -> str:
    return SCENARIO_LABELS.get(name or "", name or "—")


def format_number(value, digits: int = 2) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{number:.{digits}f}"


def price_source_label(source: str, symbol: str = "", exchange: str = "") -> str:
    if source == "ccxt":
        venue = exchange.capitalize() if exchange else "CCXT"
        pair = f" ({symbol})" if symbol else ""
        return f"{venue} vía CCXT{pair}"
    if source == "yfinance":
        return "Yahoo Finance"
    return "—"
