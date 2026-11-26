"""
Definición del grafo LangGraph.
Puedes modificar el flujo aquí cuando quieras cambiar el orden o añadir pasos.
"""
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from core.state import AnalysisState
from agents.supervisor import run_analysis

def build_graph():
    # Por ahora el supervisor ejecuta todo de forma secuencial.
    # Más adelante se puede separar cada agente en un nodo del grafo.
    workflow = StateGraph(AnalysisState)
    
    def supervisor_node(state: AnalysisState) -> Dict[str, Any]:
        result = run_analysis(state["ticker"])
        return result
    
    workflow.add_node("supervisor", supervisor_node)
    workflow.set_entry_point("supervisor")
    workflow.add_edge("supervisor", END)
    
    return workflow.compile()
