import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from core.explain import (
    explain_fundamental,
    explain_recommendation,
    explain_sentiment,
    explain_technical,
)
from core.graph import build_graph, initial_state
from core.labels import DISCLAIMER, price_source_label, scenario_label
from core.prices import history_to_frame
from core.tables import (
    fundamental_table,
    headlines_table,
    indicators_table,
    pressure_table,
    scenarios_table,
    sentiment_table,
    summary_table,
    weights_table,
)

st.set_page_config(page_title="FinSight Multi-Agent", layout="wide")

st.title("FinSight — Analizador Multi-Agente")
st.caption("Acciones · ETFs · Criptomonedas · Futuros")
st.caption(DISCLAIMER)


def _show_table(frame: pd.DataFrame) -> None:
    if frame is None or frame.empty:
        st.caption("Sin datos para esta tabla.")
        return
    st.dataframe(frame, hide_index=True, width="stretch")


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

    source = price_source_label(
        raw.get("price_source"),
        raw.get("ccxt_symbol") or "",
        raw.get("ccxt_exchange") or "",
    )

    st.subheader("Resumen")
    _show_table(summary_table(result, source))

    left, right = st.columns(2)
    with left:
        st.subheader("Indicadores")
        _show_table(indicators_table(tech))
    with right:
        st.subheader("Escenarios")
        _show_table(scenarios_table(tech))
        st.subheader("Presión compradora")
        _show_table(pressure_table(tech))

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
        st.caption(
            f"Línea verde: soporte. Línea roja: resistencia. "
            f"El camino más probable es {best_name} ({best_prob} %). Fuente: {source}."
        )
    else:
        st.info("No se obtuvieron datos suficientes para graficar escenarios.")

    fund_col, sent_col = st.columns(2)
    with fund_col:
        st.subheader("Fundamental")
        _show_table(fundamental_table(fund))
    with sent_col:
        st.subheader("Sentimiento y macro")
        _show_table(sentiment_table(sent))

    news = headlines_table(sent)
    if not news.empty:
        st.subheader("Titulares")
        st.dataframe(
            news,
            hide_index=True,
            width="stretch",
            column_config={"Enlace": st.column_config.LinkColumn("Enlace", display_text="Abrir")},
        )

    st.subheader("Cómo se armó la señal")
    _show_table(weights_table(rec))

    with st.expander("Detalle técnico completo"):
        for paragraph in explain_technical(tech):
            st.write(paragraph)
    with st.expander("Detalle fundamental"):
        for paragraph in explain_fundamental(fund):
            st.write(paragraph)
    with st.expander("Detalle de sentimiento y macro"):
        for paragraph in explain_sentiment(sent):
            st.write(paragraph)
    with st.expander("Recomendación final"):
        for paragraph in explain_recommendation(rec, result.get("asset_type")):
            st.write(paragraph)

    if result.get("errors"):
        st.warning("Advertencias:")
        for err in result["errors"]:
            st.write(f"- {err}")
else:
    st.info("Introduce un ticker y pulsa Analizar. Prueba con **AAPL**, **BTC-USD**, **GLD** o **GC=F**.")
