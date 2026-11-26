"""Compra, venta y tenedores publicados. No inventa carteras de personas."""

from typing import Any, Dict, Optional

import pandas as pd


def load_ownership(ticker: str, asset_type: str, pressure: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Solo acciones y ETFs publican tenedores. Si la fuente falla, las tablas quedan vacías."""
    if asset_type not in {"stock", "etf"}:
        return {
            "situation": _situation(None, None, pressure),
            "holders": pd.DataFrame(),
            "trades": pd.DataFrame(),
            "note": (
                "En cripto, futuros y divisas no existe una lista pública de quién mantiene el activo. "
                "Las carteras personales de economistas y políticos tampoco tienen un feed en vivo verificable, "
                "así que no se muestran cantidades inventadas."
            ),
        }
    major, holders, trades = _download(ticker)
    return {
        "situation": _situation(major, trades, pressure),
        "holders": _holders_table(holders),
        "trades": _trades_table(trades),
        "note": (
            "Los diez nombres son los mayores tenedores institucionales declarados, con sus acciones. "
            "Las compras y ventas son las de directivos que presentaron el formulario. "
            "No hay una fuente pública en vivo de lo que tienen en cartera economistas o políticos, "
            "y por eso esa lista no se rellena con cifras supuestas."
        ),
    }


def _download(ticker: str):
    try:
        import yfinance as yf

        instrument = yf.Ticker(ticker)
        return instrument.major_holders, instrument.institutional_holders, instrument.insider_transactions
    except Exception:
        return None, None, None


def _percent_held(major: Optional[pd.DataFrame], key: str) -> Optional[float]:
    if major is None or getattr(major, "empty", True):
        return None
    if key not in major.index or "Value" not in major.columns:
        return None
    try:
        return round(float(major.loc[key, "Value"]) * 100, 2)
    except (TypeError, ValueError, KeyError):
        return None


def _kind(text: str) -> str:
    lowered = (text or "").lower()
    if "purchase" in lowered or "buy" in lowered:
        return "Compra"
    if "sale" in lowered or "sold" in lowered:
        return "Venta"
    return "Otro"


def _shares(frame: Optional[pd.DataFrame], kind: str) -> Optional[float]:
    if frame is None or getattr(frame, "empty", True) or "Text" not in frame.columns or "Shares" not in frame.columns:
        return None
    chosen = frame[frame["Text"].fillna("").map(_kind) == kind]
    if chosen.empty:
        return None
    try:
        return float(chosen["Shares"].fillna(0).sum())
    except (TypeError, ValueError):
        return None


def _situation(major, trades, pressure: Optional[Dict[str, Any]]) -> pd.DataFrame:
    pressure = pressure or {}
    ratio = pressure.get("volume_ratio")
    ratio_text = "—" if ratio is None else f"{float(ratio):.2f}x"
    level = pressure.get("level") or "Sin lectura de volumen"
    insider_pct = _percent_held(major, "insidersPercentHeld")
    institution_pct = _percent_held(major, "institutionsPercentHeld")
    bought = _shares(trades, "Compra")
    sold = _shares(trades, "Venta")
    rows = [
        ["Compra en el mercado", ratio_text, level],
        ["Venta declarada por directivos", _whole(sold), "Acciones vendidas en los formularios recientes"],
        ["Compra declarada por directivos", _whole(bought), "Acciones compradas en los formularios recientes"],
        ["Instituciones que mantienen", _pct(institution_pct), "Porcentaje del papel en manos de fondos"],
        ["Directivos que mantienen", _pct(insider_pct), "Porcentaje en manos de quienes dirigen la empresa"],
    ]
    return pd.DataFrame(rows, columns=["Situación", "Dato", "Lectura"])


def _holders_table(holders: Optional[pd.DataFrame]) -> pd.DataFrame:
    if holders is None or getattr(holders, "empty", True):
        return pd.DataFrame(columns=["Tenedor", "Acciones", "Valor", "% del papel"])
    rows = []
    for _, row in holders.head(10).iterrows():
        percent = row.get("pctHeld")
        try:
            percent_text = f"{float(percent) * 100:.2f} %"
        except (TypeError, ValueError):
            percent_text = "—"
        rows.append([
            row.get("Holder") or "—",
            _whole(row.get("Shares")),
            _whole(row.get("Value")),
            percent_text,
        ])
    return pd.DataFrame(rows, columns=["Tenedor", "Acciones", "Valor", "% del papel"])


def _trades_table(trades: Optional[pd.DataFrame]) -> pd.DataFrame:
    if trades is None or getattr(trades, "empty", True) or "Text" not in trades.columns:
        return pd.DataFrame(columns=["Persona", "Operación", "Acciones", "Valor", "Fecha"])
    rows = []
    for _, row in trades.head(12).iterrows():
        kind = _kind(str(row.get("Text") or ""))
        if kind == "Otro":
            continue
        rows.append([
            row.get("Insider") or "—",
            kind,
            _whole(row.get("Shares")),
            _whole(row.get("Value")),
            str(row.get("Start Date") or "—")[:10],
        ])
        if len(rows) == 10:
            break
    return pd.DataFrame(rows, columns=["Persona", "Operación", "Acciones", "Valor", "Fecha"])


def _whole(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:.2f} %"
