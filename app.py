import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from core.assets import asset_type_label
from core.explain import (
    explain_fundamental,
    explain_recommendation,
    explain_sentiment,
    explain_technical,
)
from core.graph import build_graph, initial_state
from core.labels import DISCLAIMER, format_number, price_source_label, scenario_label, signal_label
from core.prices import history_to_frame

st.set_page_config(page_title="FinSight Multi-Agent", layout="wide")

st.title("FinSight — Analizador Multi-Agente")
st.caption("Acciones · ETFs · Criptomonedas · Futuros")
st.caption(DISCLAIMER)


@st.cache_resource
def get_analysis_graph():
    return build_graph()


ticker = st.text_input(
    "Ticker (ej: AAPL, SPY, BTC-USD, GLD, GC=F, XAUUSD=X)",
    value="AAPL",
).upper().strip()

if st.button("Analizar", type="primary") and ticker:
    with st.spinner("Ejecutando los 6 agentes..."):
        result = get_analysis_graph().invoke(initial_state(ticker))

    rec = result.get("final_recommendation") or {}
    tech = result.get("technical") or {}
    fund = result.get("fundamental") or {}
    sent = result.get("sentiment") or {}
    raw = result.get("raw_data") or {}
    bp = tech.get("buying_pressure") or {}
    indicators = tech.get("indicators") or {}

    source = price_source_label(
        raw.get("price_source"),
        raw.get("ccxt_symbol") or "",
        raw.get("ccxt_exchange") or "",
    )
    st.markdown(
        f"**Tipo de activo:** {asset_type_label(result.get('asset_type'))} · "
        f"**Fuente de precios:** {source}"
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Señal final", signal_label(rec.get("signal")))
    col2.metric("Confianza", f"{rec.get('confidence', 0):.0%}")
    col3.metric("Señal técnica", signal_label(tech.get("signal")))
    col4.metric("Proyección", tech.get("projection") or "—")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("RSI (14)", format_number(indicators.get("rsi_14"), 2))
    c2.metric("MACD", format_number(indicators.get("macd"), 4))
    c3.metric("SMA 50", format_number(indicators.get("sma_50"), 2))
    c4.metric("SMA 200", format_number(indicators.get("sma_200"), 2))

    st.subheader("Justificación")
    st.write(rec.get("reasoning") or "Sin datos suficientes")
    st.caption(DISCLAIMER)

    if bp:
        st.subheader("Presión compradora")
        level = bp.get("level", "—")
        desc = bp.get("description", "")
        ratio = bp.get("volume_ratio", 1)

        if "mucho" in level.lower():
            color = "#d4edda"
            border = "#28a745"
        elif "regular" in level.lower() or "manteniéndose" in level.lower():
            color = "#fff3cd"
            border = "#ffc107"
        elif "baja" in level.lower() or "muy baja" in level.lower():
            color = "#f8d7da"
            border = "#dc3545"
        else:
            color = "#e2e3e5"
            border = "#6c757d"

        ratio_text = format_number(ratio, 2) if bp.get("volume_ratio") is not None else "—"
        st.markdown(
            f"""
            <div style="background-color:{color}; border-left:5px solid {border}; padding:12px 16px; border-radius:6px; margin-bottom:16px;">
                <strong style="font-size:1.1em;">{level}</strong><br>
                <span style="color:#333;">{desc}</span><br>
                <small>Ratio volumen vs promedio 20d: <b>{ratio_text}x</b></small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("Gráfico de precio y escenarios")
    frame = history_to_frame(raw.get("history"))
    if frame is None:
        frame = history_to_frame((raw.get("sources") or {}).get("yfinance", {}).get("history"))
    scenarios = tech.get("scenarios") or {}
    probs = scenarios.get("probabilities") or {}

    if frame is not None and "Close" in frame.columns and scenarios and probs:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=frame.index, y=frame["Close"],
            mode="lines", name="Precio histórico",
            line=dict(color="#1f77b4", width=2),
        ))

        future_dates = pd.to_datetime(scenarios["dates"])
        for key, color in (("optimistic", "green"), ("base", "orange"), ("pessimistic", "red")):
            fig.add_trace(go.Scatter(
                x=future_dates,
                y=scenarios[key],
                mode="lines",
                name=f"{scenario_label(key)} ({probs.get(key, 0)}%)",
                line=dict(color=color, dash="dash", width=2),
            ))

        best = scenarios.get("best_scenario", "base")
        best_prob = probs.get(best, 0)
        best_name = scenario_label(best)

        sr = tech.get("support_resistance") or {}
        if sr.get("support"):
            fig.add_hline(y=sr["support"], line_dash="dot", line_color="green")
        if sr.get("resistance"):
            fig.add_hline(y=sr["resistance"], line_dash="dot", line_color="red")

        fig.update_layout(
            height=520,
            margin=dict(l=0, r=0, t=40, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, width="stretch")
        levels = []
        if sr.get("support"):
            levels.append(f"Soporte (línea verde): {format_number(sr.get('support'), 2)}")
        if sr.get("resistance"):
            levels.append(f"Resistencia (línea roja): {format_number(sr.get('resistance'), 2)}")
        level_text = (" " + " · ".join(levels) + ".") if levels else ""
        st.caption(
            f"Escenario más probable: **{best_name}** ({best_prob}%). "
            f"Fuente de precios: {source}.{level_text}"
        )
    else:
        st.info("No se obtuvieron datos suficientes para graficar escenarios.")

    if tech.get("notes"):
        st.caption("Notas técnicas: " + " · ".join(tech["notes"]))

    st.subheader("Fundamental")
    st.write(fund.get("summary") or "Sin análisis fundamental.")

    st.subheader("Sentimiento y macro")
    st.write(sent.get("summary") or "Sin datos de sentimiento.")
    news = sent.get("news") or []
    if news:
        for item in news[:5]:
            title = item.get("title") or "Titular"
            link = item.get("link") or ""
            publisher = item.get("publisher") or ""
            if link:
                st.markdown(f"- [{title}]({link})" + (f" · {publisher}" if publisher else ""))
            else:
                st.markdown(f"- {title}" + (f" · {publisher}" if publisher else ""))
    if sent.get("notes"):
        st.caption("Notas: " + " · ".join(sent["notes"]))

    with st.expander("Detalle técnico completo"):
        for paragraph in explain_technical(tech):
            st.write(paragraph)
    with st.expander("Detalle fundamental"):
        for paragraph in explain_fundamental(fund):
            st.write(paragraph)
    with st.expander("Detalle de sentimiento y macro"):
        for paragraph in explain_sentiment(sent):
            st.write(paragraph)
        if news:
            st.write("Algunos titulares que tuve en cuenta:")
            for item in news[:5]:
                title = item.get("title") or "Titular"
                link = item.get("link") or ""
                publisher = item.get("publisher") or ""
                suffix = f" ({publisher})" if publisher else ""
                if link:
                    st.markdown(f"- [{title}]({link}){suffix}")
                else:
                    st.write(f"- {title}{suffix}")
    with st.expander("Recomendación final"):
        for paragraph in explain_recommendation(rec, result.get("asset_type")):
            st.write(paragraph)

    if result.get("errors"):
        st.warning("Advertencias:")
        for err in result["errors"]:
            st.write(f"- {err}")
else:
    st.info("Introduce un ticker y pulsa Analizar. Prueba con **AAPL**, **BTC-USD**, **GLD** o **GC=F**.")
