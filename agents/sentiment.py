"""
Agente 4: Sentiment & Macro Analyst
Titulares de Yahoo Finance, índice cripto de miedo y codicia y VIX.
OpenAI es opcional: sin clave el análisis sigue con las fuentes públicas.
"""
import json
import os
import re
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import yfinance as yf
from dotenv import load_dotenv

POSITIVE_WORDS = {
    "beat", "beats", "surge", "surges", "rally", "rallies", "upgrade", "upgraded",
    "bullish", "soar", "soars", "jump", "jumps", "optimism", "outperform", "rises",
    "rise", "gain", "gains", "growth", "boom", "alta", "alza", "sube", "suben",
    "supera", "récord", "record",
}
NEGATIVE_WORDS = {
    "miss", "misses", "downgrade", "downgraded", "bearish", "crash", "plunge",
    "plunges", "slump", "slumps", "recession", "fraud", "lawsuit", "falls", "fall",
    "drop", "drops", "loss", "losses", "layoffs", "layoff", "decline", "declines",
    "fear", "baja", "cae", "caen", "recesión", "demanda", "miedo", "inflation",
}

FEAR_GREED_LABELS = {
    "Extreme Fear": "miedo extremo",
    "Fear": "miedo",
    "Neutral": "neutral",
    "Greed": "codicia",
    "Extreme Greed": "codicia extrema",
}


def score_headlines(headlines: List[Dict[str, Any]]) -> Tuple[float, int, int]:
    """0 es muy negativo y 1 muy positivo. Sin palabras clave queda en 0.5."""
    positive = 0
    negative = 0
    for item in headlines or []:
        text = f"{item.get('title') or ''} {item.get('summary') or ''}"
        for token in re.findall(r"[a-záéíóúüñ]+", text.lower()):
            if token in POSITIVE_WORDS:
                positive += 1
            elif token in NEGATIVE_WORDS:
                negative += 1
    if positive + negative == 0:
        return 0.5, 0, 0
    tilt = (positive - negative) / (positive + negative)
    return max(0.0, min(1.0, 0.5 + 0.5 * tilt)), positive, negative


def label_from_score(score: float) -> str:
    if score >= 0.6:
        return "Alcista"
    if score <= 0.4:
        return "Bajista"
    return "Neutral"


def vix_context(value: float) -> str:
    if value < 15:
        return "Volatilidad baja, mercado relativamente calmado."
    if value < 20:
        return "Volatilidad contenida."
    if value < 30:
        return "Volatilidad elevada; el contexto pide cautela."
    return "Volatilidad muy alta; contexto de estrés."


def _weighted_average(parts: List[Tuple[float, float]]) -> float:
    total = sum(weight for _, weight in parts)
    if total <= 0:
        return 0.5
    return sum(score * weight for score, weight in parts) / total


def headline_tone(headlines: List[Dict[str, Any]]) -> Tuple[float, int, int, int]:
    """Promedio por titular y recuento. Positivos + negativos + neutros = nº de titulares."""
    positive = negative = neutral = 0
    scores: List[float] = []
    for item in headlines or []:
        score, pos_hits, neg_hits = score_headlines([item])
        scores.append(score)
        if pos_hits == 0 and neg_hits == 0:
            neutral += 1
        elif score >= 0.6:
            positive += 1
        elif score <= 0.4:
            negative += 1
        else:
            neutral += 1
    if not scores:
        return 0.5, 0, 0, 0
    return sum(scores) / len(scores), positive, negative, neutral


def build_sentiment_report(
    ticker: str,
    asset_type: str,
    headlines: Optional[List[Dict[str, Any]]],
    fear_greed: Optional[Dict[str, Any]],
    vix: Optional[Dict[str, Any]],
    llm_summary: Optional[str],
    notes: Optional[List[str]],
) -> Dict[str, Any]:
    """Combina fuentes ya descargadas. No abre red."""
    del ticker  # el titular ya viene filtrado; se conserva la firma por claridad
    notes = list(notes or [])
    headlines = list(headlines or [])
    if asset_type != "crypto":
        fear_greed = None
    parts: List[Tuple[float, float]] = []
    sources: List[str] = []
    detail: List[str] = []
    headline_counts = {"positive": 0, "negative": 0, "neutral": 0}

    if headlines:
        score, positive, negative, neutral = headline_tone(headlines)
        headline_counts = {"positive": positive, "negative": negative, "neutral": neutral}
        weight = 0.35 if asset_type == "crypto" else 0.75
        parts.append((score, weight))
        sources.append("yfinance_news")
        detail.append(
            f"Titulares ({len(headlines)}): {positive} con tono positivo, "
            f"{negative} con tono negativo y {neutral} sin un tono claro."
        )
    else:
        detail.append("Sin titulares utilizables.")

    # El índice de alternative.me es de cripto. No se mezcla con acciones ni futuros.
    if asset_type == "crypto" and fear_greed and fear_greed.get("value") is not None:
        try:
            value = int(fear_greed["value"])
        except (TypeError, ValueError):
            value = None
        if value is not None:
            fg_score = max(0.0, min(1.0, value / 100))
            weight = 0.65 if asset_type == "crypto" else 0.25
            parts.append((fg_score, weight))
            sources.append("fear_greed")
            klass = FEAR_GREED_LABELS.get(fear_greed.get("classification") or "", "")
            if klass:
                detail.append(f"Índice de miedo y codicia cripto: {value} ({klass}).")
            else:
                detail.append(f"Índice de miedo y codicia cripto: {value}.")

    score = _weighted_average(parts) if parts else 0.5
    if vix and vix.get("value") is not None:
        vix_value = float(vix["value"])
        sources.append("vix")
        if vix_value >= 30:
            score -= 0.05
        elif vix_value < 15:
            score += 0.03
        context = vix.get("context") or vix_context(vix_value)
        detail.append(f"VIX: {vix_value:.2f}. {context}".strip())

    if not sources:
        notes.append("No hubo fuentes de sentimiento disponibles; se asume un sesgo neutro.")

    score = round(min(1.0, max(0.0, score)), 2)
    label = label_from_score(score)
    macro = " ".join(detail).strip() or "Sin contexto macro."
    summary = f"Sentimiento {label} ({score:.2f}). {macro}"
    if llm_summary:
        summary = f"{summary} Resumen adicional: {llm_summary}"

    return {
        "available": bool(sources),
        "sentiment_score": score,
        "label": label,
        "macro_context": macro,
        "summary": summary,
        "news": headlines[:8],
        "headline_counts": headline_counts,
        "fear_greed": fear_greed,
        "vix": vix,
        "sources_used": sources,
        "notes": notes,
        "llm_summary": llm_summary,
    }


def _extract_headline(item: Dict[str, Any]) -> Optional[Dict[str, str]]:
    if not isinstance(item, dict):
        return None
    content = item.get("content") if isinstance(item.get("content"), dict) else None
    if content:
        title = content.get("title")
        provider = content.get("provider") or {}
        publisher = provider.get("displayName") if isinstance(provider, dict) else ""
        canonical = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
        link = canonical.get("url") if isinstance(canonical, dict) else ""
        summary = content.get("summary") or content.get("description") or ""
    else:
        title = item.get("title")
        publisher = item.get("publisher") or ""
        link = item.get("link") or item.get("url") or ""
        summary = item.get("summary") or ""
    if not title:
        return None
    return {
        "title": str(title),
        "publisher": str(publisher or ""),
        "link": str(link or ""),
        "summary": str(summary or ""),
    }


def _fetch_headlines(ticker: str) -> List[Dict[str, str]]:
    items = yf.Ticker(ticker).news or []
    parsed = []
    for item in items:
        row = _extract_headline(item)
        if row:
            parsed.append(row)
    return parsed[:12]


def _fetch_fear_greed() -> Dict[str, Any]:
    request = urllib.request.Request(
        "https://api.alternative.me/fng/?limit=1",
        headers={"User-Agent": "FinSight/0.1"},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))
    row = (payload.get("data") or [{}])[0]
    return {
        "value": int(row["value"]),
        "classification": row.get("value_classification") or "",
        "source": "alternative.me",
    }


def _fetch_vix() -> Optional[Dict[str, Any]]:
    history = yf.Ticker("^VIX").history(period="10d")
    if history is None or history.empty or "Close" not in history.columns:
        return None
    value = float(history["Close"].iloc[-1])
    if value != value:  # NaN
        return None
    value = round(value, 2)
    return {"value": value, "context": vix_context(value)}


def _optional_llm_summary(ticker: str, headlines: List[Dict[str, str]], asset_type: str) -> Tuple[Optional[str], Optional[str]]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None, None
    titles = [item.get("title") or "" for item in headlines[:8] if item.get("title")]
    if not titles:
        return None, None
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            api_key=api_key,
            timeout=20,
        )
        prompt = (
            "Resume en español, en máximo dos frases, el tono de estos titulares "
            f"para {ticker} ({asset_type}). No des asesoramiento de inversión ni "
            "una orden de compra o venta.\n- " + "\n- ".join(titles)
        )
        response = llm.invoke(prompt)
        text = getattr(response, "content", str(response)).strip()
        return (text or None), None
    except Exception as exc:
        return None, f"OpenAI no disponible ({type(exc).__name__})."


def analyze_sentiment(ticker: str, raw_data: Dict[str, Any], asset_type: str = "") -> Dict[str, Any]:
    load_dotenv()
    asset_type = asset_type or (raw_data or {}).get("asset_type") or "unknown"
    notes: List[str] = []
    headlines: List[Dict[str, str]] = []
    fear_greed = None
    vix = None

    try:
        headlines = _fetch_headlines(ticker)
        if not headlines:
            notes.append("Yahoo Finance no devolvió titulares.")
    except Exception as exc:
        notes.append(f"Titulares no disponibles ({type(exc).__name__}).")

    if asset_type == "crypto":
        try:
            fear_greed = _fetch_fear_greed()
        except Exception as exc:
            notes.append(f"Índice de miedo y codicia no disponible ({type(exc).__name__}).")

    try:
        vix = _fetch_vix()
        if vix is None:
            notes.append("VIX sin datos recientes.")
    except Exception as exc:
        notes.append(f"VIX no disponible ({type(exc).__name__}).")

    llm_summary = None
    if not os.getenv("OPENAI_API_KEY", "").strip():
        notes.append("OPENAI_API_KEY no configurada; sentimiento calculado solo con fuentes públicas.")
    else:
        llm_summary, llm_note = _optional_llm_summary(ticker, headlines, asset_type)
        if llm_note:
            notes.append(llm_note)

    return build_sentiment_report(ticker, asset_type, headlines, fear_greed, vix, llm_summary, notes)
