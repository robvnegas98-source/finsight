"""
Agente 3: Fundamental Analyst
Análisis fundamental (acciones y ETFs).
Añade ratios o métricas en analyze_fundamental().
"""
from typing import Dict, Any

def analyze_fundamental(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    info = raw_data.get("sources", {}).get("yfinance", {}).get("info", {})
    
    return {
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "market_cap": info.get("marketCap"),
        "dividend_yield": info.get("dividendYield"),
        "summary": "Análisis fundamental básico (ampliable)"
    }
