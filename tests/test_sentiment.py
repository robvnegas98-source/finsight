from agents.sentiment import build_sentiment_report, score_headlines


def test_stock_ignores_crypto_fear_index_and_counts_every_headline():
    headlines = [
        {"title": "Shares surge after upgrade", "summary": ""},
        {"title": "Stock crash and plunge", "summary": ""},
        {"title": "Company holds a meeting", "summary": ""},
    ]
    report = build_sentiment_report(
        "AAPL",
        "stock",
        headlines,
        fear_greed={"value": 11, "classification": "Extreme Fear"},
        vix={"value": 18.0, "context": "Volatilidad contenida."},
        llm_summary=None,
        notes=[],
    )
    counts = report["headline_counts"]
    assert "fear_greed" not in report["sources_used"]
    assert "miedo" not in report["summary"].lower()
    assert "VIX" in report["summary"]
    assert counts["positive"] + counts["negative"] + counts["neutral"] == 3
    assert counts["neutral"] >= 1
    assert "sin un tono claro" in report["summary"]


def test_headline_lexicon_and_missing_sources():
    score, positive, negative = score_headlines(
        [{"title": "Shares surge and rally after upgrade", "summary": "bullish optimism"}]
    )
    assert score > 0.5
    assert positive > negative

    empty = build_sentiment_report("AAPL", "stock", None, None, None, None, ["falló"])
    assert empty["available"] is False
    assert empty["sentiment_score"] == 0.5
    assert empty["label"] == "Neutral"


def test_crypto_fear_and_greed_pulls_the_score_down():
    report = build_sentiment_report(
        "BTC-USD",
        "crypto",
        headlines=[{"title": "Bitcoin crash and plunge", "summary": "bearish fear"}],
        fear_greed={"value": 11, "classification": "Extreme Fear"},
        vix=None,
        llm_summary=None,
        notes=[],
    )
    assert report["available"] is True
    assert "fear_greed" in report["sources_used"]
    assert report["sentiment_score"] < 0.4
    assert report["label"] == "Bajista"
    assert "11" in report["summary"]
    assert "miedo extremo" in report["summary"]
