"""
Agente 1: Data Collector
Clasifica el activo, descarga OHLCV y solo pide fundamentales cuando aplican.
"""
from typing import Any, Dict, List, Optional, Tuple

import ccxt
import pandas as pd
import yfinance as yf

from core.assets import (
    classify_asset,
    is_gold_ticker,
    market_ticker,
    normalize_crypto_symbol,
    refine_asset_type,
    should_request_fundamentals,
)
from core.prices import frame_to_history, ohlcv_to_frame

_IDENTITY_KEYS = ("quoteType", "shortName", "longName", "currency", "symbol", "exchange")


def _identity_info(info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Quita múltiplos tipo PER si el activo no los admite."""
    if not info:
        return {}
    cleaned = {}
    for key in _IDENTITY_KEYS:
        value = info.get(key)
        if value not in (None, ""):
            cleaned[key] = value
    return cleaned


def _download_yfinance(ticker: str, with_info: bool) -> Tuple[Optional[pd.DataFrame], Optional[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    frame = None
    info = None
    try:
        instrument = yf.Ticker(ticker)
    except Exception as exc:
        return None, None, [f"Yahoo Finance: {exc}"]

    try:
        history = instrument.history(period="1y", auto_adjust=True)
        if history is not None and not history.empty:
            frame = history
        else:
            errors.append("Yahoo Finance no devolvió histórico de precios.")
    except Exception as exc:
        errors.append(f"Yahoo Finance (precios): {exc}")

    if with_info:
        try:
            info = instrument.info or {}
        except Exception as exc:
            errors.append(f"Yahoo Finance (fundamentales): {exc}")
            info = {}
    return frame, info, errors


def _brief_error(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    cut = text.find("{")
    if cut > 0:
        text = text[:cut].strip()
    if len(text) > 160:
        text = text[:160].rstrip() + "…"
    return text or exc.__class__.__name__


def _fetch_ccxt_market(symbol: str):
    """Velas diarias sin clave. Binance (USDT) primero; Kraken y Coinbase si no responde."""
    base = symbol.split("/")[0] if symbol and "/" in symbol else symbol
    attempts = []
    if symbol and "/" in symbol:
        attempts.append(("binance", symbol))
    attempts.extend((
        ("binance", f"{base}/USDT"),
        ("kraken", f"{base}/USD"),
        ("coinbase", f"{base}/USD"),
    ))
    failures = []
    seen = set()
    for exchange_id, pair in attempts:
        key = (exchange_id, pair)
        if not pair or key in seen:
            continue
        seen.add(key)
        try:
            exchange = getattr(ccxt, exchange_id)({"enableRateLimit": True, "timeout": 12000})
            ohlcv = exchange.fetch_ohlcv(pair, timeframe="1d", limit=365)
            if ohlcv:
                return ohlcv, pair, exchange_id
            failures.append(f"{exchange_id} {pair}: sin velas")
        except Exception as exc:
            failures.append(f"{exchange_id} {pair}: {_brief_error(exc)}")
    detail = "; ".join(failures)[:300] or "sin velas de CCXT"
    raise RuntimeError(detail)


def _load_ccxt(symbol: str, errors: List[str], sources: Dict[str, Any]):
    try:
        ohlcv, used_symbol, exchange_id = _fetch_ccxt_market(symbol)
    except Exception as exc:
        sources["ccxt"] = {"symbol": symbol, "error": _brief_error(exc)}
        errors.append(f"CCXT ({symbol}): {_brief_error(exc)}")
        return None, None, None
    sources["ccxt"] = {
        "symbol": used_symbol,
        "exchange": exchange_id,
        "candles": len(ohlcv),
    }
    if not ohlcv:
        errors.append(f"CCXT no devolvió velas para {symbol}.")
        return None, used_symbol, exchange_id
    return ohlcv_to_frame(ohlcv), used_symbol, exchange_id


def collect_data(ticker: str) -> Dict[str, Any]:
    requested = (ticker or "").strip().upper()
    symbol = market_ticker(requested)
    asset_type = classify_asset(symbol)
    errors: List[str] = []
    if symbol != requested and is_gold_ticker(requested):
        errors.append(
            f"{requested} ya no trae precios en Yahoo. Se usa {symbol}, el futuro del oro, que sí tiene velas."
        )
    sources: Dict[str, Any] = {}
    history_df = None
    price_source = None
    ccxt_symbol = None
    info: Optional[Dict[str, Any]] = None
    yf_df = None
    tried_ccxt = False

    ccxt_exchange = None

    if asset_type == "crypto":
        ccxt_symbol = normalize_crypto_symbol(symbol)
        tried_ccxt = True
        ccxt_frame, ccxt_symbol, ccxt_exchange = _load_ccxt(ccxt_symbol, errors, sources)
        if ccxt_frame is not None:
            history_df = ccxt_frame
            price_source = "ccxt"

        if history_df is None:
            yf_df, _, yf_errors = _download_yfinance(symbol, with_info=False)
            errors.extend(yf_errors)
            if yf_df is not None:
                history_df = yf_df
                price_source = "yfinance"
                errors.append("Se usan precios de Yahoo Finance como respaldo.")
    else:
        yf_df, info, yf_errors = _download_yfinance(
            symbol,
            with_info=should_request_fundamentals(asset_type),
        )
        errors.extend(yf_errors)
        if info:
            asset_type = refine_asset_type(asset_type, info)
            if not should_request_fundamentals(asset_type):
                info = _identity_info(info)
        if yf_df is not None:
            history_df = yf_df
            price_source = "yfinance"

    # Un símbolo que parecía acción puede ser cripto según quoteType. CCXT pasa a ser la fuente.
    if asset_type == "crypto" and not tried_ccxt:
        ccxt_symbol = normalize_crypto_symbol(symbol)
        ccxt_frame, ccxt_symbol, ccxt_exchange = _load_ccxt(ccxt_symbol, errors, sources)
        if ccxt_frame is not None:
            history_df = ccxt_frame
            price_source = "ccxt"

    if info is None:
        info = {}
    elif not should_request_fundamentals(asset_type):
        info = _identity_info(info)

    history = frame_to_history(history_df)
    sources["yfinance"] = {
        "history": history if price_source == "yfinance" else None,
        "info": info,
    }
    if history is None:
        errors.append("No se obtuvieron precios de ninguna fuente.")

    return {
        "ticker": symbol,
        "asset_type": asset_type,
        "history": history,
        "price_source": price_source,
        "ccxt_symbol": ccxt_symbol if price_source == "ccxt" else None,
        "ccxt_exchange": ccxt_exchange if price_source == "ccxt" else None,
        "sources": sources,
        "errors": errors,
    }
