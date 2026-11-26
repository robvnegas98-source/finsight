"""
Grafo LangGraph: un nodo por agente y un estado compartido.

El supervisor solo normaliza la entrada. Después el recolector alimenta en
paralelo al técnico, al fundamental y al de sentimiento, y el Chief espera
a los tres antes de cerrar la señal.
"""
from typing import Any, Dict

from langgraph.graph import END, START, StateGraph

from agents.chief import generate_recommendation
from agents.data_collector import collect_data
from agents.fundamental import analyze_fundamental
from agents.sentiment import analyze_sentiment
from agents.supervisor import prepare_state
from agents.technical import analyze_technical
from core.state import AnalysisState


def initial_state(ticker: str) -> AnalysisState:
    return {
        "ticker": (ticker or "").strip().upper(),
        "asset_type": "unknown",
        "raw_data": {},
        "technical": {},
        "fundamental": {},
        "sentiment": {},
        "final_recommendation": {},
        "charts": [],
        "errors": [],
    }


def _supervisor_node(state: AnalysisState) -> Dict[str, Any]:
    return prepare_state(state)


def _data_node(state: AnalysisState) -> Dict[str, Any]:
    try:
        raw = collect_data(state.get("ticker") or "")
    except Exception as exc:
        return {
            "raw_data": {"ticker": state.get("ticker"), "sources": {}, "history": None},
            "asset_type": "unknown",
            "errors": [f"Datos: {exc}"],
        }
    errors = list(raw.pop("errors", []) or [])
    return {
        "raw_data": raw,
        "asset_type": raw.get("asset_type") or "unknown",
        "errors": errors,
    }


def _technical_node(state: AnalysisState) -> Dict[str, Any]:
    try:
        return {"technical": analyze_technical(state.get("raw_data") or {})}
    except Exception as exc:
        return {
            "technical": {
                "signal": "NEUTRAL",
                "confidence": 0.0,
                "indicators": {},
                "scenarios": {},
                "buying_pressure": {},
                "notes": [f"Error en cálculo técnico: {exc}"],
                "projection": "—",
            },
            "errors": [f"Técnico: {exc}"],
        }


def _fundamental_node(state: AnalysisState) -> Dict[str, Any]:
    try:
        return {
            "fundamental": analyze_fundamental(
                state.get("raw_data") or {},
                state.get("asset_type") or "unknown",
            )
        }
    except Exception as exc:
        return {
            "fundamental": {
                "applicable": False,
                "summary": "No se pudo calcular el análisis fundamental.",
            },
            "errors": [f"Fundamental: {exc}"],
        }


def _sentiment_node(state: AnalysisState) -> Dict[str, Any]:
    try:
        return {
            "sentiment": analyze_sentiment(
                state.get("ticker") or "",
                state.get("raw_data") or {},
                state.get("asset_type") or "unknown",
            )
        }
    except Exception as exc:
        return {
            "sentiment": {
                "available": False,
                "sentiment_score": 0.5,
                "label": "Neutral",
                "macro_context": "Sin contexto de sentimiento.",
                "summary": "El análisis de sentimiento no pudo completarse.",
                "news": [],
                "notes": [str(exc)],
                "sources_used": [],
            },
            "errors": [f"Sentimiento: {exc}"],
        }


def _chief_node(state: AnalysisState) -> Dict[str, Any]:
    try:
        return {"final_recommendation": generate_recommendation(state)}
    except Exception as exc:
        return {
            "final_recommendation": {
                "signal": "NEUTRAL",
                "signal_label": "Neutral",
                "confidence": 0.0,
                "reasoning": "No se pudo sintetizar la recomendación.",
            },
            "errors": [f"Chief: {exc}"],
        }


def build_graph():
    workflow = StateGraph(AnalysisState)
    workflow.add_node("supervisor", _supervisor_node)
    workflow.add_node("data_collector", _data_node)
    workflow.add_node("technical", _technical_node)
    workflow.add_node("fundamental", _fundamental_node)
    workflow.add_node("sentiment", _sentiment_node)
    workflow.add_node("chief", _chief_node)

    workflow.add_edge(START, "supervisor")
    workflow.add_edge("supervisor", "data_collector")
    workflow.add_edge("data_collector", "technical")
    workflow.add_edge("data_collector", "fundamental")
    workflow.add_edge("data_collector", "sentiment")
    workflow.add_edge("technical", "chief")
    workflow.add_edge("fundamental", "chief")
    workflow.add_edge("sentiment", "chief")
    workflow.add_edge("chief", END)
    return workflow.compile()
