"""
Agente 3: Fundamental Analyst
PER y dividendo solo cuando el activo los admite.
"""
import math
from typing import Any, Dict, Optional

from core.assets import NON_FUNDAMENTAL_TYPES, asset_type_label

_SKIP_SUMMARY = {
    "crypto": "Los múltiplos tipo PER no aplican a criptomonedas. El análisis fundamental contable se omite.",
    "futures": "Los futuros no tienen PER ni dividendo. El análisis fundamental contable se omite.",
    "forex": "Las divisas y los metales spot no tienen fundamentales tipo PER. Este bloque se omite.",
    "index": "Los índices no se valoran con el PER del propio ticker. El análisis fundamental contable se omite.",
}


def _number(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def dividend_yield_percent(info: Dict[str, Any]) -> Optional[float]:
    """Devuelve el yield en porcentaje (0.40 = 0,40 %)."""
    trailing = _number((info or {}).get("trailingAnnualDividendYield"))
    if trailing is not None and trailing >= 0:
        # Este campo llega como fracción (0.004 = 0,4 %).
        if trailing <= 0.25:
            return round(trailing * 100, 2)
        return round(trailing, 2)
    raw = _number((info or {}).get("dividendYield"))
    if raw is None or raw < 0:
        return None
    # yfinance reciente ya lo entrega en porcentaje (0.3 = 0,3 %). Las versiones
    # antiguas entregaban fracción (0.003). Por debajo de 0.2 se interpreta fracción.
    if raw <= 0.2:
        return round(raw * 100, 2)
    return round(raw, 2)


def _pe_comment(pe: float) -> str:
    if pe < 0:
        return "beneficios negativos"
    if pe < 12:
        return "valoración baja"
    if pe < 18:
        return "valoración moderada"
    if pe < 25:
        return "valoración razonable"
    if pe < 35:
        return "valoración exigente"
    return "valoración muy exigente"


def _format_market_cap(value, currency: str) -> Optional[str]:
    number = _number(value)
    if number is None:
        return None
    if number >= 1e12:
        text = f"{number / 1e12:.2f} billones"
    elif number >= 1e9:
        text = f"{number / 1e9:.2f} mil millones"
    elif number >= 1e6:
        text = f"{number / 1e6:.0f} millones"
    else:
        text = f"{number:.0f}"
    suffix = f" {currency}" if currency else ""
    return f"capitalización {text}{suffix}"


def _not_applicable(asset_type: str) -> Dict[str, Any]:
    summary = _SKIP_SUMMARY.get(
        asset_type,
        f"Los múltiplos tipo PER no aplican a este tipo de activo ({asset_type_label(asset_type)}).",
    )
    return {
        "applicable": False,
        "asset_type": asset_type,
        "summary": summary,
    }


def analyze_fundamental(raw_data: Dict[str, Any], asset_type: str = "stock") -> Dict[str, Any]:
    asset_type = asset_type or (raw_data or {}).get("asset_type") or "unknown"
    if asset_type in NON_FUNDAMENTAL_TYPES:
        return _not_applicable(asset_type)

    info = ((raw_data or {}).get("sources") or {}).get("yfinance", {}).get("info") or {}
    pe = _number(info.get("trailingPE"))
    forward_pe = _number(info.get("forwardPE"))
    market_cap = _number(info.get("marketCap"))
    dividend = dividend_yield_percent(info)
    name = info.get("shortName") or info.get("longName")
    currency = info.get("currency") or ""

    parts = []
    if pe is not None:
        label = "PER orientativo" if asset_type == "etf" else "PER"
        parts.append(f"{label} {pe:.2f} ({_pe_comment(pe)})")
    else:
        parts.append("sin PER disponible")
    if forward_pe is not None:
        parts.append(f"PER forward {forward_pe:.2f}")
    if dividend is not None:
        parts.append(f"rentabilidad por dividendo {dividend:.2f}%")
    market_cap_text = _format_market_cap(market_cap, currency)
    if market_cap_text:
        parts.append(market_cap_text)

    prefix = name or ("ETF" if asset_type == "etf" else "Acción")
    summary = f"{prefix}: " + "; ".join(parts) + "."

    return {
        "applicable": True,
        "asset_type": asset_type,
        "pe_ratio": round(pe, 2) if pe is not None else None,
        "forward_pe": round(forward_pe, 2) if forward_pe is not None else None,
        "market_cap": market_cap,
        "dividend_yield": dividend,
        "sector": info.get("sector"),
        "name": name,
        "summary": summary,
    }
