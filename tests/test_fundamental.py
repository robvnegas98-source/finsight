from agents.fundamental import analyze_fundamental, dividend_yield_percent


def test_crypto_futures_and_forex_skip_pe():
    raw = {"sources": {"yfinance": {"info": {"trailingPE": 8, "marketCap": 10}}}}
    for asset_type in ("crypto", "futures", "forex", "index"):
        result = analyze_fundamental(raw, asset_type)
        assert result["applicable"] is False
        assert "pe_ratio" not in result
        assert "no aplican" in result["summary"] or "omite" in result["summary"]


def test_stock_fundamentals_from_synthetic_info():
    raw = {
        "sources": {
            "yfinance": {
                "info": {
                    "shortName": "Test Inc",
                    "trailingPE": 10,
                    "forwardPE": 8,
                    "trailingAnnualDividendYield": 0.02,
                    "marketCap": 2_000_000_000_000,
                    "currency": "USD",
                    "sector": "Technology",
                }
            }
        }
    }
    result = analyze_fundamental(raw, "stock")
    assert result["applicable"] is True
    assert result["pe_ratio"] == 10
    assert result["forward_pe"] == 8
    assert result["dividend_yield"] == 2.0
    assert "PER 10.00" in result["summary"]
    assert "Test Inc" in result["summary"]


def test_dividend_yield_units():
    assert dividend_yield_percent({"trailingAnnualDividendYield": 0.002993758}) == 0.3
    assert dividend_yield_percent({"dividendYield": 1.0}) == 1.0
    assert dividend_yield_percent({"dividendYield": 0.004}) == 0.4
