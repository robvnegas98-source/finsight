import pytest

from core.assets import (
    asset_type_label,
    classify_asset,
    normalize_crypto_symbol,
    refine_asset_type,
    should_request_fundamentals,
)


@pytest.mark.parametrize(
    ("ticker", "expected"),
    [
        ("AAPL", "stock"),
        ("brk-b", "stock"),
        ("SPY", "etf"),
        ("GLD", "etf"),
        ("BTC-USD", "crypto"),
        ("ETH-USD", "crypto"),
        ("BTC/USDT", "crypto"),
        ("BTCUSDT", "crypto"),
        ("GC=F", "futures"),
        ("XAUUSD=X", "forex"),
        ("^GSPC", "index"),
        ("", "unknown"),
    ],
)
def test_classify_asset(ticker, expected):
    assert classify_asset(ticker) == expected


@pytest.mark.parametrize(
    ("ticker", "expected"),
    [
        ("BTC-USD", "BTC/USDT"),
        ("eth-usd", "ETH/USDT"),
        ("BTC/USD", "BTC/USDT"),
        ("BTC/USDT", "BTC/USDT"),
        ("ETH-USDT", "ETH/USDT"),
        ("SOLUSDT", "SOL/USDT"),
        ("ETHBTC", "ETH/BTC"),
    ],
)
def test_normalize_crypto_symbol(ticker, expected):
    assert normalize_crypto_symbol(ticker) == expected


def test_refine_and_fundamentals_policy():
    assert refine_asset_type("stock", {"quoteType": "ETF"}) == "etf"
    assert refine_asset_type("stock", {"quoteType": "CRYPTOCURRENCY"}) == "crypto"
    assert refine_asset_type("futures", {"quoteType": "EQUITY"}) == "futures"
    assert refine_asset_type("forex", {"quoteType": "ETF"}) == "forex"
    assert should_request_fundamentals("stock") is True
    assert should_request_fundamentals("etf") is True
    assert should_request_fundamentals("crypto") is False
    assert should_request_fundamentals("futures") is False
    assert should_request_fundamentals("forex") is False
    assert should_request_fundamentals("index") is False
    assert asset_type_label("crypto") == "Cripto"
