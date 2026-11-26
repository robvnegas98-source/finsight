"""
Agente 6: Supervisor
Orquesta el flujo, decide el orden y comparte información.
En LangGraph este rol lo cumple el grafo + esta función de control.
"""
from typing import Dict, Any
from agents.data_collector import collect_data
from agents.technical import analyze_technical
from agents.fundamental import analyze_fundamental
from agents.sentiment import analyze_sentiment
from agents.chief import generate_recommendation

def run_analysis(ticker: str) -> Dict[str, Any]:
    state = {"ticker": ticker, "errors": []}
    
    # 1. Data Collector
    try:
        state["raw_data"] = collect_data(ticker)
    except Exception as e:
        state["errors"].append(f"Data: {e}")
        state["raw_data"] = {}
    
    # 2-4. Analistas en secuencia (puedes paralelizar después)
    try:
        state["technical"] = analyze_technical(state["raw_data"])
    except Exception as e:
        state["errors"].append(f"Technical: {e}")
    
    try:
        state["fundamental"] = analyze_fundamental(state["raw_data"])
    except Exception as e:
        state["errors"].append(f"Fundamental: {e}")
    
    try:
        state["sentiment"] = analyze_sentiment(ticker, state["raw_data"])
    except Exception as e:
        state["errors"].append(f"Sentiment: {e}")
    
    # 5. Chief Analyst
    try:
        state["final_recommendation"] = generate_recommendation(state)
    except Exception as e:
        state["errors"].append(f"Chief: {e}")
    
    return state
