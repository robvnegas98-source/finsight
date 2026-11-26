from pathlib import Path

from agents.supervisor import prepare_state
from core.graph import build_graph, initial_state
from core.labels import DISCLAIMER


def test_graph_has_one_node_per_agent():
    nodes = set(build_graph().get_graph().nodes)
    assert {
        "supervisor",
        "data_collector",
        "technical",
        "fundamental",
        "sentiment",
        "chief",
    } <= nodes


def test_graph_fans_in_shared_state(monkeypatch):
    def collect(ticker):
        assert ticker == "AAPL"
        return {
            "ticker": ticker,
            "asset_type": "stock",
            "history": None,
            "price_source": "yfinance",
            "sources": {},
            "errors": ["aviso de datos"],
        }

    def technical(raw):
        return {
            "signal": "BUY",
            "confidence": 0.8,
            "indicators": {"rsi_14": 45.0},
            "scenarios": {},
            "buying_pressure": {},
            "notes": [],
            "projection": "Alcista",
        }

    def fundamental(raw, asset_type="stock"):
        assert asset_type == "stock"
        return {"applicable": True, "pe_ratio": 10, "summary": "PER 10.00"}

    def sentiment(ticker, raw, asset_type=""):
        assert ticker == "AAPL"
        assert asset_type == "stock"
        return {
            "available": True,
            "sentiment_score": 0.7,
            "label": "Alcista",
            "summary": "Sentimiento Alcista (0.70).",
        }

    def chief(state):
        assert state["technical"]["signal"] == "BUY"
        assert state["fundamental"]["pe_ratio"] == 10
        assert state["sentiment"]["label"] == "Alcista"
        assert state["asset_type"] == "stock"
        return {"signal": "BUY", "confidence": 0.7, "reasoning": "sintesis de prueba"}

    monkeypatch.setattr("core.graph.collect_data", collect)
    monkeypatch.setattr("core.graph.analyze_technical", technical)
    monkeypatch.setattr("core.graph.analyze_fundamental", fundamental)
    monkeypatch.setattr("core.graph.analyze_sentiment", sentiment)
    monkeypatch.setattr("core.graph.generate_recommendation", chief)

    result = build_graph().invoke(initial_state("aapl"))
    assert result["final_recommendation"]["reasoning"] == "sintesis de prueba"
    assert result["asset_type"] == "stock"
    assert "aviso de datos" in result["errors"]


def test_prepare_state_normalizes_ticker():
    assert prepare_state({"ticker": " btc-usd "})["ticker"] == "BTC-USD"
    assert prepare_state({"ticker": "  "})["errors"]


def test_app_runs_the_graph_and_shows_the_disclaimer():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "build_graph" in source
    assert "run_analysis" not in source
    assert "DISCLAIMER" in source
    assert "no constituyen asesoramiento de inversión" in DISCLAIMER
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "no constituyen asesoramiento de inversión" in readme
    assert "OPENAI_API_KEY" in readme
    assert "BTC-USD" in readme
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    for entry in (".env", "venv/", "__pycache__/", ".pytest_cache/"):
        assert entry in gitignore
