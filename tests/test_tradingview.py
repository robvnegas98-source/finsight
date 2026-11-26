from core.tradingview import tradingview_symbol, tradingview_widget_html


def test_tradingview_symbols():
    assert tradingview_symbol("BTC-USD", "crypto") == "BINANCE:BTCUSDT"
    assert tradingview_symbol("ETH-USD", "crypto") == "BINANCE:ETHUSDT"
    assert tradingview_symbol("GC=F", "futures") == "COMEX:GC1!"
    assert tradingview_symbol("XAUUSD=X", "forex") == "OANDA:XAUUSD"
    assert tradingview_symbol("^GSPC", "index") == "SP:SPX"
    assert tradingview_symbol("SPY", "etf") == "AMEX:SPY"
    assert tradingview_symbol("BRK-B", "stock") == "BRK.B"
    assert tradingview_symbol("AAPL", "stock") == "AAPL"


def test_widget_html_contains_the_symbol_and_attribution():
    html = tradingview_widget_html('BINANCE:BTCUSDT"><script>')
    assert "BINANCE:BTCUSDT" in html
    assert '"><script>' not in html
    assert "TradingView" in html
    assert '"locale": "es"' in html
    assert "RSI@tv-basicstudies" in html
    assert "MACD@tv-basicstudies" in html
    intraday = tradingview_widget_html("AAPL", interval="5")
    daily = tradingview_widget_html("AAPL", interval="D")
    for name in ("VWAP@tv-basicstudies", "MAExp@tv-basicstudies", "RSI@tv-basicstudies", "MACD@tv-basicstudies", "Volume@tv-basicstudies"):
        assert name in intraday
    for name in ("MASimple@tv-basicstudies", "RSI@tv-basicstudies", "MACD@tv-basicstudies", "BB@tv-basicstudies", "Volume@tv-basicstudies"):
        assert name in daily
