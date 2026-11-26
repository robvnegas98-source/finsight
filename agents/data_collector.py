"""
Agente 1: Data Collector
Responsable de obtener datos de múltiples fuentes.
Fácil de ampliar: solo agrega nuevas fuentes en get_data().
"""
import yfinance as yf
import ccxt
import pandas as pd
from typing import Dict, Any

def collect_data(ticker: str) -> Dict[str, Any]:
    data = {"ticker": ticker, "sources": {}}
    
    # Yahoo Finance (acciones y ETFs)
    try:
        yf_ticker = yf.Ticker(ticker)
        hist = yf_ticker.history(period="1y")
        data["sources"]["yfinance"] = {
            "history": hist.to_dict() if not hist.empty else None,
            "info": yf_ticker.info
        }
    except Exception as e:
        data["sources"]["yfinance"] = {"error": str(e)}
    
    # CCXT (cripto) - ejemplo con Binance
    try:
        exchange = ccxt.binance()
        if "/" in ticker or ticker.endswith("USDT") or ticker.endswith("USD"):
            ohlcv = exchange.fetch_ohlcv(ticker, timeframe="1d", limit=365)
            data["sources"]["ccxt"] = {"ohlcv": ohlcv}
    except Exception as e:
        data["sources"]["ccxt"] = {"error": str(e)}
    
    return data
