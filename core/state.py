from typing import TypedDict, Optional, List, Dict, Any

class AnalysisState(TypedDict):
    ticker: str
    asset_type: str  # "stock", "etf", "crypto"
    raw_data: Dict[str, Any]
    technical: Dict[str, Any]
    fundamental: Dict[str, Any]
    sentiment: Dict[str, Any]
    final_recommendation: Dict[str, Any]
    charts: List[Any]
    errors: List[str]
