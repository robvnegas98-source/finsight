"""Tablas de la pantalla. Las cifras son las mismas del análisis."""

from typing import Any, Dict, Optional

import pandas as pd

from core.assets import asset_type_label
from core.explain import entry_advice
from core.labels import format_number, scenario_label, signal_label

_FEAR_LABELS = {
    "Extreme Fear": "miedo extremo",
    "Fear": "miedo",
    "Neutral": "neutral",
    "Greed": "codicia",
    "Extreme Greed": "codicia extrema",
}


def _frame(rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["Concepto", "Valor"])


def _reading_rsi(value) -> str:
    if value is None:
        return "Sin dato"
    if value < 30:
        return "Sobreventa"
    if value > 70:
        return "Sobrecompra"
    return "Zona media"


def _trend_reading(trend) -> str:
    return {
        "Alcista": "El precio y las medias apuntan hacia arriba",
        "Bajista": "El precio y las medias apuntan hacia abajo",
        "Lateral": "No hay una tendencia limpia",
    }.get(trend or "", "Sin dato suficiente")


def _bollinger_value(value) -> str:
    if value is None:
        return "—"
    return format_number(value, 2)


def _bollinger_reading(value) -> str:
    if value is None:
        return "Sin dato"
    if value > 1:
        return "Por encima de la banda superior: el movimiento va estirado"
    if value < 0:
        return "Por debajo de la banda inferior: el movimiento va estirado a la baja"
    return "Dentro de las bandas"


def _volume_value(value) -> str:
    if value is None:
        return "—"
    return f"{format_number(value, 2)}x"


def _volume_reading(value) -> str:
    if value is None:
        return "Sin dato de volumen"
    if value >= 1.3:
        return "Volumen alto: la tendencia tiene respaldo"
    if value <= 0.7:
        return "Volumen bajo: la tendencia es débil"
    return "Volumen normal"


def _signed_percent(value) -> str:
    if value is None:
        return "—"
    number = float(value)
    sign = "+" if number > 0 else ""
    return f"{sign}{format_number(number, 2)} %"


def _reading_macd(macd, signal) -> str:
    if macd is None or signal is None:
        return "Sin dato"
    if macd > signal:
        return "Por encima de la señal"
    if macd < signal:
        return "Por debajo de la señal"
    return "Junto a la señal"


def summary_table(result: Dict[str, Any], source: str) -> pd.DataFrame:
    rec = result.get("final_recommendation") or {}
    tech = result.get("technical") or {}
    confidence = rec.get("confidence")
    try:
        confidence_text = f"{float(confidence):.0%}" if confidence is not None else "—"
    except (TypeError, ValueError):
        confidence_text = "—"
    return _frame([
        ["Consejo de entrada", entry_advice(rec)["label"]],
        ["Señal final", signal_label(rec.get("signal"))],
        ["Confianza", confidence_text],
        ["Señal técnica", signal_label(tech.get("signal"))],
        ["Proyección", tech.get("projection") or "—"],
        ["Tipo de activo", asset_type_label(result.get("asset_type"))],
        ["Fuente de precios", source or "—"],
    ])


def indicators_table(tech: Optional[Dict[str, Any]]) -> pd.DataFrame:
    tech = tech or {}
    indicators = tech.get("indicators") or {}
    levels = tech.get("support_resistance") or {}
    macd = indicators.get("macd")
    macd_signal = indicators.get("macd_signal")
    volume_ratio = (tech.get("buying_pressure") or {}).get("volume_ratio")
    rows = [
        ["1. Medias", indicators.get("trend") or "Sin dato", _trend_reading(indicators.get("trend"))],
        ["2. RSI (14)", format_number(indicators.get("rsi_14"), 2), _reading_rsi(indicators.get("rsi_14"))],
        ["3. MACD", format_number(macd, 4), _reading_macd(macd, macd_signal)],
        ["4. Bandas de Bollinger", _bollinger_value(indicators.get("bollinger")), _bollinger_reading(indicators.get("bollinger"))],
        ["5. Volumen", _volume_value(volume_ratio), _volume_reading(volume_ratio)],
        ["Precio", format_number(indicators.get("price"), 2), "Último cierre"],
        ["Distancia a la SMA 50", _signed_percent(indicators.get("distance_sma50_pct")), "Positivo: el precio va por encima de la media"],
        ["SMA 20", format_number(indicators.get("sma_20"), 2), "Media corta de 20 días"],
        ["SMA 50", format_number(indicators.get("sma_50"), 2), "Media de 50 días"],
        ["SMA 200", format_number(indicators.get("sma_200"), 2), "Media larga de 200 días"],
        ["Soporte", format_number(levels.get("support"), 2), "Suelo reciente"],
        ["Resistencia", format_number(levels.get("resistance"), 2), "Techo reciente"],
    ]
    return pd.DataFrame(rows, columns=["Indicador", "Valor", "Lectura"])


def scenarios_table(tech: Optional[Dict[str, Any]]) -> pd.DataFrame:
    scenarios = (tech or {}).get("scenarios") or {}
    probs = scenarios.get("probabilities") or {}
    if not probs:
        return pd.DataFrame(columns=["Escenario", "Probabilidad", "Más probable"])
    best = scenarios.get("best_scenario") or ""
    rows = []
    for key in ("optimistic", "base", "pessimistic"):
        rows.append([
            scenario_label(key),
            f"{int(probs.get(key, 0))} %",
            "Sí" if key == best else "No",
        ])
    return pd.DataFrame(rows, columns=["Escenario", "Probabilidad", "Más probable"])


def pressure_table(tech: Optional[Dict[str, Any]]) -> pd.DataFrame:
    pressure = (tech or {}).get("buying_pressure") or {}
    if not pressure:
        return pd.DataFrame(columns=["Concepto", "Valor"])
    ratio = pressure.get("volume_ratio")
    ratio_text = f"{format_number(ratio, 2)}x" if ratio is not None else "—"
    return _frame([
        ["Nivel", pressure.get("level") or "—"],
        ["Qué se ve", pressure.get("description") or "—"],
        ["Volumen contra el promedio de 20 días", ratio_text],
    ])


def fundamental_table(fund: Optional[Dict[str, Any]]) -> pd.DataFrame:
    fund = fund or {}
    applies = "Sí" if fund.get("applicable") else "No"
    rows = [["¿Sirve el PER aquí?", applies]]
    if fund.get("applicable"):
        rows.extend([
            ["Nombre", fund.get("name") or "—"],
            ["PER", format_number(fund.get("pe_ratio"), 2)],
            ["PER forward", format_number(fund.get("forward_pe"), 2)],
            ["Dividendo anual", _percent(fund.get("dividend_yield"))],
            ["Sector", fund.get("sector") or "—"],
        ])
    rows.append(["Comentario", fund.get("summary") or "Sin análisis fundamental."])
    return _frame(rows)


def sentiment_table(sent: Optional[Dict[str, Any]]) -> pd.DataFrame:
    sent = sent or {}
    counts = sent.get("headline_counts") or {}
    score = sent.get("sentiment_score")
    try:
        score_text = format_number(float(score), 2) if score is not None else "—"
    except (TypeError, ValueError):
        score_text = "—"
    fear = sent.get("fear_greed") or {}
    if fear.get("value") is None:
        fear_text = "No aplica"
    else:
        klass = _FEAR_LABELS.get(fear.get("classification") or "", "")
        fear_text = str(fear.get("value"))
        if klass:
            fear_text = f"{fear_text} ({klass})"
    vix = sent.get("vix") or {}
    vix_text = format_number(vix.get("value"), 2) if vix.get("value") is not None else "—"
    return _frame([
        ["Ánimo", sent.get("label") or "—"],
        ["Puntuación de 0 a 1", score_text],
        ["Titulares positivos", str(int(counts.get("positive") or 0))],
        ["Titulares negativos", str(int(counts.get("negative") or 0))],
        ["Titulares sin un tono claro", str(int(counts.get("neutral") or 0))],
        ["Miedo y codicia (solo cripto)", fear_text],
        ["VIX", vix_text],
    ])


def headlines_table(sent: Optional[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for item in ((sent or {}).get("news") or [])[:8]:
        rows.append([
            item.get("title") or "Titular",
            item.get("publisher") or "—",
            item.get("link") or "",
        ])
    return pd.DataFrame(rows, columns=["Titular", "Medio", "Enlace"])


def weights_table(rec: Optional[Dict[str, Any]]) -> pd.DataFrame:
    components = (rec or {}).get("components") or {}
    labels = {
        "technical": "Precio y técnica",
        "fundamental": "Fundamental",
        "sentiment": "Sentimiento",
    }
    rows = []
    for key in ("technical", "fundamental", "sentiment"):
        part = components.get(key) or {}
        weight = part.get("weight")
        try:
            weight_text = f"{float(weight):.0%}" if weight is not None else "—"
        except (TypeError, ValueError):
            weight_text = "—"
        if not part.get("applied"):
            role = "No entra en la mezcla"
        else:
            score = part.get("score")
            if score is None:
                role = "Sin lectura"
            elif score > 0.15:
                role = "Empuja hacia compra"
            elif score < -0.15:
                role = "Empuja hacia venta"
            else:
                role = "Se queda en el medio"
        rows.append([labels[key], weight_text, role])
    return pd.DataFrame(rows, columns=["Parte", "Peso", "Qué hizo"])


def _percent(value) -> str:
    if value is None:
        return "—"
    return f"{format_number(value, 2)} %"
