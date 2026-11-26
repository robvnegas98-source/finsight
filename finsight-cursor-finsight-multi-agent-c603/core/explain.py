"""Textos en prosa para las pestañas de detalle. Usan las mismas cifras que el análisis."""

from typing import Any, Dict, List, Optional

from core.assets import asset_type_label
from core.labels import format_number, scenario_label, signal_label


_FEAR_LABELS = {
    "Extreme Fear": "miedo extremo",
    "Fear": "miedo",
    "Neutral": "neutral",
    "Greed": "codicia",
    "Extreme Greed": "codicia extrema",
}


def _sentences(parts: List[str]) -> List[str]:
    cleaned = []
    for part in parts:
        text = " ".join((part or "").split())
        if not text:
            continue
        if text[-1] not in ".!?":
            text += "."
        cleaned.append(text)
    return cleaned or ["No hay suficiente información para contarlo con detalle."]


def _rsi_sentence(value) -> str:
    if value is None:
        return "No pude calcular el RSI de 14 días porque falta historia de precios."
    number = format_number(value, 2)
    if value < 30:
        reading = (
            "Está bajo. El precio ha caído con fuerza y el indicador entra en lo que se llama sobreventa."
        )
    elif value > 70:
        reading = (
            "Está alto. El precio ha subido con fuerza y el indicador entra en lo que se llama sobrecompra."
        )
    else:
        reading = "Está en una zona media, sin un extremo que por sí solo pida comprar o vender."
    return f"El RSI de 14 días vale {number}. {reading}"


def _macd_sentence(macd, signal) -> str:
    if macd is None or signal is None:
        return "No hay un MACD fiable con estos datos."
    if macd > signal:
        relation = "por encima de su línea de señal. En el corto plazo eso acompaña a las subidas."
    elif macd < signal:
        relation = "por debajo de su línea de señal. En el corto plazo eso acompaña a las bajadas."
    else:
        relation = "pegado a su línea de señal. Ahora mismo no inclina ni hacia arriba ni hacia abajo."
    return (
        f"El MACD vale {format_number(macd, 4)} y la línea de señal vale {format_number(signal, 4)}. "
        f"El MACD está {relation}"
    )


def _trend_sentence(price, sma50, sma200) -> str:
    if price is None:
        return "No tengo un precio de cierre reciente para comparar con las medias."
    price_text = format_number(price, 2)
    if sma50 is None and sma200 is None:
        return f"El último precio es {price_text}. Todavía no hay medias de 50 y 200 días."
    if sma50 is not None and sma200 is not None:
        if price > sma50 > sma200:
            order = (
                "El precio está por encima de la media de 50 días y esa media está por encima de la de 200. "
                "Eso es una tendencia de subida."
            )
        elif price < sma50 < sma200:
            order = (
                "El precio está por debajo de la media de 50 días y esa media está por debajo de la de 200. "
                "Eso es una tendencia de bajada."
            )
        else:
            order = "Las medias no están ordenadas en una tendencia limpia, así que el recorrido se ve mixto."
        return (
            f"El último precio es {price_text}. "
            f"La media de 50 días está en {format_number(sma50, 2)} "
            f"y la de 200 días en {format_number(sma200, 2)}. {order}"
        )
    if sma50 is not None:
        return (
            f"El último precio es {price_text} y la media de 50 días está en {format_number(sma50, 2)}. "
            "Aún no hay media de 200 días."
        )
    return (
        f"El último precio es {price_text} y la media de 200 días está en {format_number(sma200, 2)}."
    )


def explain_technical(tech: Optional[Dict[str, Any]]) -> List[str]:
    tech = tech or {}
    indicators = tech.get("indicators") or {}
    pressure = tech.get("buying_pressure") or {}
    levels = tech.get("support_resistance") or {}
    scenarios = tech.get("scenarios") or {}
    probs = scenarios.get("probabilities") or {}
    confidence = tech.get("confidence")
    try:
        confidence_text = f"{float(confidence):.0%}" if confidence is not None else "una confianza sin calcular"
    except (TypeError, ValueError):
        confidence_text = "una confianza sin calcular"

    parts = [
        (
            f"Si miro solo el precio, la lectura es {signal_label(tech.get('signal'))} "
            f"y la proyección es {tech.get('projection') or 'indefinida'}. "
            f"La confianza de esta parte es {confidence_text}."
        ),
        _rsi_sentence(indicators.get("rsi_14")),
        _macd_sentence(indicators.get("macd"), indicators.get("macd_signal")),
        _trend_sentence(indicators.get("price"), indicators.get("sma_50"), indicators.get("sma_200")),
    ]
    if levels.get("support") is not None or levels.get("resistance") is not None:
        parts.append(
            "En las últimas sesiones el suelo cercano, el soporte, está en "
            f"{format_number(levels.get('support'), 2)} y el techo, la resistencia, en "
            f"{format_number(levels.get('resistance'), 2)}."
        )
    if pressure.get("level"):
        ratio = pressure.get("volume_ratio")
        volume = (
            f" El volumen reciente es {format_number(ratio, 2)} veces el promedio de 20 días."
            if ratio is not None
            else ""
        )
        description = pressure.get("description") or ""
        parts.append(f"La presión compradora la resumiría así: {pressure['level']}. {description}.{volume}")
    if probs:
        best = scenarios.get("best_scenario") or "base"
        parts.append(
            "Para los próximos tres meses aproximadamente planteo tres caminos. "
            f"El optimista tiene un {int(probs.get('optimistic', 0))} % de probabilidad, "
            f"el base un {int(probs.get('base', 0))} % y el pesimista un {int(probs.get('pessimistic', 0))} %. "
            f"El que más peso le doy es el {scenario_label(best).lower()}, "
            f"con un {int(probs.get(best, 0))} %."
        )
    notes = [note for note in (tech.get("notes") or []) if note]
    if notes:
        parts.append("Los avisos que salieron de las cuentas fueron: " + "; ".join(notes) + ".")
    return _sentences(parts)


def _pe_plain(pe: float) -> str:
    if pe < 0:
        return "Hay pérdidas, así que ese PER no se puede leer como una ganga."
    if pe < 12:
        return "Está bajo: se paga poco por cada peso de beneficio."
    if pe < 18:
        return "Está en un rango moderado."
    if pe < 25:
        return "Está en un rango razonable para un negocio que crece."
    if pe < 35:
        return "Está exigente: el precio ya descuenta bastantes beneficios."
    return "Está muy exigente: el precio solo se sostiene si los beneficios siguen creciendo."


def explain_fundamental(fund: Optional[Dict[str, Any]]) -> List[str]:
    fund = fund or {}
    if fund.get("applicable") is False:
        summary = fund.get("summary") or "Este activo no se valora con un PER."
        return _sentences([
            summary,
            "Por eso no lo mezclo con la señal final. Meter un PER aquí solo confundiría la lectura.",
        ])

    name = fund.get("name") or "Este activo"
    pe = fund.get("pe_ratio")
    forward = fund.get("forward_pe")
    dividend = fund.get("dividend_yield")
    parts = []
    if pe is not None:
        parts.append(f"{name} cotiza con un PER de {format_number(pe, 2)}. {_pe_plain(float(pe))}")
    else:
        parts.append(f"De {name} no tengo un PER reciente.")
    if forward is not None and pe is not None:
        if float(forward) < float(pe):
            comparison = "Es más bajo que el PER actual, así que el mercado anticipa más beneficios."
        elif float(forward) > float(pe):
            comparison = "Es más alto que el PER actual, así que se esperan menos beneficios."
        else:
            comparison = "Se mantiene en el mismo nivel."
        parts.append(f"El PER esperado es {format_number(forward, 2)}. {comparison}")
    elif forward is not None:
        parts.append(f"El PER esperado es {format_number(forward, 2)}.")
    if dividend is not None:
        parts.append(f"El dividendo reparte alrededor de un {format_number(dividend, 2)} % al año.")
    if fund.get("sector"):
        parts.append(f"El sector que figura en la ficha es {fund['sector']}.")
    summary = fund.get("summary")
    if summary:
        parts.append(f"En una línea, la ficha dice: {summary}")
    return _sentences(parts)


def explain_sentiment(sent: Optional[Dict[str, Any]]) -> List[str]:
    sent = sent or {}
    label = sent.get("label") or "Neutral"
    score = sent.get("sentiment_score")
    try:
        score_text = format_number(float(score), 2) if score is not None else "sin cifra"
    except (TypeError, ValueError):
        score_text = "sin cifra"
    parts = [
        (
            f"El ánimo que leo en las noticias y en el contexto de mercado es {label}. "
            f"Lo pongo en {score_text} dentro de una escala de 0 a 1, donde 0,50 es un punto neutro."
        )
    ]
    counts = sent.get("headline_counts") or {}
    news = sent.get("news") or []
    if news or any(counts.values() if isinstance(counts, dict) else []):
        positive = int(counts.get("positive") or 0)
        negative = int(counts.get("negative") or 0)
        neutral = int(counts.get("neutral") or 0)
        total = positive + negative + neutral or len(news)
        parts.append(
            f"Revisé {total} titulares. {positive} sonaban positivos, {negative} negativos "
            f"y {neutral} no inclinaban la balanza."
        )
    fear = sent.get("fear_greed") or {}
    if fear.get("value") is not None:
        klass = _FEAR_LABELS.get(fear.get("classification") or "", "")
        if not klass and fear.get("classification"):
            klass = str(fear.get("classification")).lower()
        extra = f", es decir, {klass}" if klass else ""
        parts.append(
            "En cripto miro también el índice de miedo y codicia. "
            f"Hoy está en {fear.get('value')}{extra}."
        )
    vix = sent.get("vix") or {}
    if vix.get("value") is not None:
        context = vix.get("context") or ""
        parts.append(f"El VIX, el termómetro del nerviosismo del mercado, está en {format_number(vix.get('value'), 2)}. {context}")
    if sent.get("llm_summary"):
        parts.append(f"Además, un resumen automático añade esto: {sent['llm_summary']}")
    else:
        parts.append(
            "No usé inteligencia artificial para redactar el ánimo. "
            "Sale de los titulares públicos y, si el activo es cripto, del índice de miedo y codicia."
        )
    if sent.get("available") is False:
        parts.append("Casi no llegaron fuentes, así que esta parte pesa poco o nada en la señal final.")
    return _sentences(parts)


def _lean(score) -> str:
    if score is None:
        return "no entró en la mezcla"
    if score > 0.15:
        return "empuja hacia una compra"
    if score < -0.15:
        return "empuja hacia una venta"
    return "se queda en el medio"


def explain_recommendation(rec: Optional[Dict[str, Any]], asset_type: str = "") -> List[str]:
    rec = rec or {}
    asset_type = rec.get("asset_type") or asset_type or "unknown"
    components = rec.get("components") or {}
    technical = components.get("technical") or {}
    fundamental = components.get("fundamental") or {}
    sentiment = components.get("sentiment") or {}
    confidence = rec.get("confidence")
    try:
        confidence_text = f"{float(confidence):.0%}" if confidence is not None else "sin una confianza calculada"
    except (TypeError, ValueError):
        confidence_text = "sin una confianza calculada"

    final_name = signal_label(rec.get("signal"))
    technical_name = signal_label(technical.get("signal"))
    parts = [
        (
            f"La señal con la que me quedo es {final_name}, "
            f"con una confianza del {confidence_text}. "
            f"Esto no es una orden de compra ni de venta: es la lectura conjunta de las tres partes."
        ),
        (
            f"Como es {asset_type_label(asset_type).lower()}, "
            f"reparto el peso así: un {technical.get('weight', 0):.0%} al precio, "
            f"un {fundamental.get('weight', 0):.0%} a los fundamentales "
            f"y un {sentiment.get('weight', 0):.0%} al ánimo del mercado."
        ),
        (
            f"La parte del precio {_lean(technical.get('score'))}. "
            f"La parte fundamental "
            f"{_lean(fundamental.get('score')) if fundamental.get('applied') else 'no aplica en este activo y la dejo fuera'}. "
            f"El ánimo del mercado "
            f"{_lean(sentiment.get('score')) if sentiment.get('applied') else 'no tenía fuentes suficientes y no lo usé'}."
        ),
    ]
    if technical.get("signal") and technical.get("signal") != rec.get("signal"):
        parts.append(
            f"Por eso la señal final ({final_name}) no copia a la técnica ({technical_name}). "
            "Las otras partes inclinaron la balanza."
        )
    elif technical.get("signal"):
        parts.append(
            f"En este caso la señal final coincide con la técnica: las dos dicen {final_name}."
        )
    return _sentences(parts)
