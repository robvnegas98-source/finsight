import pandas as pd

from agents.data_collector import collect_data
from core.prices import history_to_frame


class _Ticker:
    def __init__(self, symbol, calls, info):
        calls["symbols"].append(symbol)
        self.calls = calls
        self._info = info

    def history(self, **kwargs):
        self.calls["history"] += 1
        index = pd.date_range("2024-01-01", periods=5, freq="D")
        return pd.DataFrame(
            {"Open": 1.0, "High": 1.2, "Low": 0.8, "Close": [1, 2, 3, 4, 5], "Volume": 10},
            index=index,
        )

    @property
    def info(self):
        self.calls["info"] += 1
        return self._info


def _patch(monkeypatch, info=None, ohlcv=None, ccxt_error=False):
    calls = {"symbols": [], "history": 0, "info": 0, "ccxt": []}

    def ticker(symbol):
        return _Ticker(symbol, calls, info or {"quoteType": "EQUITY", "shortName": "Test", "trailingPE": 12})

    def fetch(symbol):
        calls["ccxt"].append(symbol)
        if ccxt_error:
            raise RuntimeError('binance GET https://api.binance.com/api/v3/exchangeInfo 451  {"code": 0}')
        if ohlcv is None:
            raise AssertionError(f"CCXT no debería llamarse para {symbol}")
        return ohlcv, symbol, "binance"

    monkeypatch.setattr("agents.data_collector.yf.Ticker", ticker)
    monkeypatch.setattr("agents.data_collector._fetch_ccxt_market", fetch)
    return calls


def _candles(count=60):
    start = 1_700_000_000_000
    return [[start + i * 86_400_000, 10, 12, 9, 10 + i * 0.1, 1000] for i in range(count)]


def test_crypto_uses_ccxt_and_skips_fundamentals(monkeypatch):
    calls = _patch(monkeypatch, ohlcv=_candles())
    data = collect_data("btc-usd")
    assert data["asset_type"] == "crypto"
    assert data["price_source"] == "ccxt"
    assert data["ccxt_symbol"] == "BTC/USDT"
    assert data["ccxt_exchange"] == "binance"
    assert calls["ccxt"] == ["BTC/USDT"]
    assert calls["symbols"] == []
    assert calls["info"] == 0
    assert "trailingPE" not in data["sources"]["yfinance"]["info"]
    frame = history_to_frame(data["history"])
    assert len(frame) == 60
    assert frame["Close"].iloc[-1] == pytest_close()


def pytest_close():
    return 10 + 59 * 0.1


def test_crypto_falls_back_to_yahoo_without_requesting_pe(monkeypatch):
    calls = _patch(monkeypatch, ccxt_error=True)
    data = collect_data("ETH-USD")
    assert data["asset_type"] == "crypto"
    assert data["price_source"] == "yfinance"
    assert calls["info"] == 0
    assert calls["history"] == 1
    assert any("respaldo" in err for err in data["errors"])
    assert all("{" not in err for err in data["errors"])


def test_stock_requests_fundamentals_and_not_ccxt(monkeypatch):
    calls = _patch(monkeypatch)
    data = collect_data("AAPL")
    assert data["asset_type"] == "stock"
    assert data["price_source"] == "yfinance"
    assert calls["info"] == 1
    assert calls["ccxt"] == []
    assert data["sources"]["yfinance"]["info"]["trailingPE"] == 12


def test_futures_skip_pe_and_ccxt(monkeypatch):
    calls = _patch(monkeypatch)
    data = collect_data("GC=F")
    assert data["asset_type"] == "futures"
    assert calls["info"] == 0
    assert calls["ccxt"] == []
    assert data["sources"]["yfinance"]["info"] == {}


def test_quote_type_can_reclassify_and_switch_to_ccxt(monkeypatch):
    calls = _patch(
        monkeypatch,
        info={"quoteType": "CRYPTOCURRENCY", "shortName": "Bitcoin", "trailingPE": 99, "currency": "USD"},
        ohlcv=_candles(30),
    )
    data = collect_data("AAPL")
    assert data["asset_type"] == "crypto"
    assert data["price_source"] == "ccxt"
    assert calls["ccxt"] == ["AAPL/USDT"]
    assert "trailingPE" not in data["sources"]["yfinance"]["info"]
    assert data["sources"]["yfinance"]["info"]["shortName"] == "Bitcoin"
