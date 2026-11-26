import operator
from typing import Annotated, Any, Dict, List, TypedDict


class AnalysisState(TypedDict, total=False):
    ticker: str
    asset_type: str  # stock, etf, crypto, futures, forex, index, unknown
    raw_data: Dict[str, Any]
    technical: Dict[str, Any]
    fundamental: Dict[str, Any]
    sentiment: Dict[str, Any]
    final_recommendation: Dict[str, Any]
    charts: List[Any]
    # Varios nodos pueden añadir avisos en el mismo paso del grafo.
    errors: Annotated[List[str], operator.add]
