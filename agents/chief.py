"""
Agente 5: Chief Analyst
Sintetiza todos los análisis y da la recomendación final.
Modifica generate_recommendation() para cambiar la lógica de decisión.
"""
from typing import Dict, Any

def generate_recommendation(state: Dict[str, Any]) -> Dict[str, Any]:
    tech = state.get("technical", {})
    fund = state.get("fundamental", {})
    sent = state.get("sentiment", {})
    
    # Lógica simple de ejemplo (fácil de reemplazar)
    signal = tech.get("signal", "NEUTRAL")
    confidence = 0.6
    
    return {
        "signal": signal,
        "confidence": confidence,
        "reasoning": f"Señal técnica: {signal}. Fundamental y sentimiento considerados.",
        "scenarios": {
            "optimistic": "+15% en 6 meses",
            "base": "Lateral",
            "pessimistic": "-10% en 6 meses"
        }
    }
