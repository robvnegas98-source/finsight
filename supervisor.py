"""
Agente 6: Supervisor
El orden de los agentes vive en core/graph.py. Aquí solo se normaliza el ticker
y queda un acceso cómodo para scripts. La interfaz ejecuta el grafo directamente.
"""
from typing import Any, Dict


def prepare_state(state: Dict[str, Any]) -> Dict[str, Any]:
    ticker = str(state.get("ticker") or "").strip().upper()
    update: Dict[str, Any] = {"ticker": ticker}
    if not ticker:
        update["errors"] = ["Indica un ticker para analizar."]
    return update


def run_analysis(ticker: str) -> Dict[str, Any]:
    """Ejecuta el grafo LangGraph. app.py no usa esta función: llama a build_graph()."""
    from core.graph import build_graph, initial_state

    return build_graph().invoke(initial_state(ticker))
