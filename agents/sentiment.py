"""
Agente 4: Sentiment & Macro Analyst
Sentimiento y contexto macro.
Puedes conectar más APIs de noticias o índices de miedo/codicia aquí.
"""
from typing import Dict, Any

def analyze_sentiment(ticker: str, raw_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "sentiment_score": 0.5,  # Neutral por defecto
        "macro_context": "Mercado en condiciones normales",
        "notes": "Placeholder - conectar fuentes de noticias y FRED"
    }
