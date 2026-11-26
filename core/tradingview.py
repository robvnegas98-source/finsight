"""Símbolo y gráfico embebido de TradingView. No hace falta una clave."""

from core.assets import normalize_crypto_symbol

_FUTURES = {
    "GC": "COMEX:GC1!",
    "SI": "COMEX:SI1!",
    "CL": "NYMEX:CL1!",
    "ES": "CME_MINI:ES1!",
    "NQ": "CME_MINI:NQ1!",
    "YM": "CBOT_MINI:YM1!",
}

_INDEXES = {
    "^GSPC": "SP:SPX",
    "^DJI": "DJ:DJI",
    "^IXIC": "NASDAQ:IXIC",
    "^VIX": "CBOE:VIX",
}

_ETFS = {
    "SPY": "AMEX:SPY",
    "QQQ": "NASDAQ:QQQ",
    "IWM": "AMEX:IWM",
    "DIA": "AMEX:DIA",
    "GLD": "AMEX:GLD",
    "SLV": "AMEX:SLV",
    "TLT": "NASDAQ:TLT",
    "VTI": "AMEX:VTI",
    "VOO": "AMEX:VOO",
}


def tradingview_symbol(ticker: str, asset_type: str = "") -> str:
    """Traduce el ticker de FinSight al símbolo que entiende TradingView."""
    symbol = (ticker or "").upper().strip()
    asset_type = asset_type or ""
    if not symbol:
        return "NASDAQ:AAPL"
    if asset_type == "crypto":
        pair = normalize_crypto_symbol(symbol)
        base, _, quote = pair.partition("/")
        quote = "USDT" if quote in {"", "USD", "USDT"} else quote
        return f"BINANCE:{base}{quote}"
    if asset_type == "forex":
        return f"OANDA:{symbol.replace('=X', '')}"
    if asset_type == "futures":
        root = symbol.replace("=F", "")
        return _FUTURES.get(root, root)
    if asset_type == "index":
        return _INDEXES.get(symbol, symbol.lstrip("^"))
    if symbol in _ETFS:
        return _ETFS[symbol]
    return symbol.replace("-", ".")


def tradingview_widget_html(symbol: str, height: int = 560, interval: str = "D") -> str:
    """Widget oficial gratuito. El enlace de atribución lo pide TradingView."""
    safe = (symbol or "NASDAQ:AAPL").replace('"', "").replace("<", "").replace(">", "")
    container = "finsight_tv"
    if interval == "D":
        studies = [
            "MASimple@tv-basicstudies",
            "RSI@tv-basicstudies",
            "MACD@tv-basicstudies",
            "BB@tv-basicstudies",
            "Volume@tv-basicstudies",
        ]
    else:
        studies = [
            "VWAP@tv-basicstudies",
            "MAExp@tv-basicstudies",
            "RSI@tv-basicstudies",
            "MACD@tv-basicstudies",
            "Volume@tv-basicstudies",
        ]
    studies_json = ", ".join(f'"{name}"' for name in studies)
    return f"""
    <div class="tradingview-widget-container" style="height:{height - 32}px;width:100%">
      <div id="{container}" style="height:100%;width:100%"></div>
      <div class="tradingview-widget-copyright">
        <a href="https://www.tradingview.com/symbols/{safe.replace(':', '-')}/" rel="noopener nofollow" target="_blank">
          <span class="blue-text">{safe} en TradingView</span>
        </a>
      </div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
        new TradingView.widget({{
          "autosize": true,
          "symbol": "{safe}",
          "interval": "{interval}",
          "timezone": "exchange",
          "theme": "light",
          "style": "1",
          "locale": "es",
          "toolbar_bg": "#f8fafc",
          "enable_publishing": false,
          "hide_top_toolbar": false,
          "allow_symbol_change": true,
          "save_image": false,
          "container_id": "{container}",
          "studies": [{studies_json}]
        }});
      </script>
    </div>
    """
