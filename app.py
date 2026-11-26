import contextlib

import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import pandas as pd

from agents.daytrade import (
    DAYTRADE_STEPS,
    add_entry_exit_lines,
    analyze_session,
    daytrade_levels_table,
    daytrade_trend_table,
    entry_exit_table,
    fetch_intraday,
    intraday_entry_chart,
    swing_entry_exit,
)
from core.explain import (
    entry_advice,
    explain_fundamental,
    explain_recommendation,
    explain_sentiment,
    explain_technical,
)
from core.graph import build_graph, initial_state
from core.labels import DISCLAIMER, price_source_label, scenario_label
from core.prices import history_to_frame
from core.tradingview import tradingview_symbol, tradingview_widget_html
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

st.set_page_config(page_title="La Bobina Bursátil", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
      background:
        radial-gradient(900px 280px at 0% -10%, rgba(15, 118, 110, 0.16), transparent 60%),
        radial-gradient(700px 240px at 100% 0%, rgba(180, 83, 9, 0.12), transparent 55%),
        linear-gradient(180deg, #e7eef8 0%, #f7f4ef 240px, #f5f7fb 100%);
    }
    h1, h2, h3 { color: #0f2744; letter-spacing: -0.02em; }
    div[data-testid="stCaption"] { color: #3d4c63; }
    div[data-testid="stDataFrame"] {
      border: 1px solid #dbe3ef;
      border-radius: 12px;
      overflow: hidden;
      background: #ffffff;
    }
    .fs-banner {
      background: linear-gradient(120deg, #0f2744 0%, #0f766e 62%, #b45309 140%);
      color: #f8fafc;
      border-radius: 16px;
      padding: 22px 26px 18px;
      margin-bottom: 12px;
      box-shadow: 0 10px 30px rgba(15, 39, 68, 0.16);
    }
    .fs-banner h1 { color: #ffffff; margin: 0 0 4px; font-size: 2rem; }
    .fs-banner p { margin: 0; color: #dbe7f5; }
    .fs-signal {
      border-radius: 12px;
      padding: 12px 16px;
      margin: 8px 0 16px;
      font-weight: 650;
      border: 1px solid transparent;
    }
    div.stButton > button[kind="primary"] {
      background: #0f766e;
      border: none;
      border-radius: 10px;
    }
    </style>
    <div class="fs-banner">
      <h1>LA BOBINA BURSATIL</h1>
      <p>Analizador multi-agente · Acciones, ETFs, criptomonedas y futuros</p>
    </div>
    """,
    unsafe_allow_html=True,
)
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
modo = st.radio(
    "Horizonte",
    ["Day trading", "Varias semanas"],
    horizontal=True,
)

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

    day_plan = None
    intraday = None
    if modo == "Day trading":
        intraday, intraday_notes = fetch_intraday(result.get("ticker") or ticker, result.get("asset_type") or "")
        day_plan = analyze_session(intraday)
        if intraday_notes:
            day_plan["notes"] = intraday_notes
    swing_levels = None if day_plan is not None else swing_entry_exit(tech, rec.get("signal"))

    advice = day_plan if day_plan is not None else entry_advice(rec)
    advice_styles = {
        "compra": ("#ecfdf5", "#047857", "#a7f3d0"),
        "venta": ("#fef2f2", "#b91c1c", "#fecaca"),
        "esperar": ("#fffbeb", "#b45309", "#fde68a"),
    }
    background, ink, border = advice_styles[advice["action"]]
    st.markdown(
        f"""
        <div class="fs-signal" style="background:{background};color:{ink};border-color:{border};">
          <div style="font-size:0.95rem;letter-spacing:0.04em;text-transform:uppercase;">Consejo de entrada</div>
          <div style="font-size:1.35rem;margin-top:4px;">{advice["title"]}</div>
          <div style="font-weight:500;margin-top:8px;">{advice["detail"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if day_plan is not None:
        if day_plan.get("entry") is not None:
            st.subheader("Entrada y salida de hoy")
            _show_table(entry_exit_table(day_plan))
            session_chart = intraday_entry_chart(intraday, day_plan)
            if session_chart is not None:
                st.plotly_chart(session_chart, width="stretch")
                st.caption("Línea azul: entras. Línea verde: sales con ganancia. Línea roja: sales si la operación sale mal.")
        st.subheader("Tendencia del día")
        _show_table(daytrade_trend_table(day_plan))
        st.subheader("Plan del día")
        _show_table(daytrade_levels_table(day_plan))
    elif swing_levels and swing_levels.get("entry") is not None:
        st.subheader("Entrada y salida")
        st.write(swing_levels.get("detail"))
        _show_table(entry_exit_table(swing_levels))
        st.subheader("Cómo se hace un day trade")
        for step in DAYTRADE_STEPS:
            st.write(f"- {step}")
        for note in day_plan.get("notes") or []:
            st.caption(note)

    tv_symbol = tradingview_symbol(result.get("ticker") or ticker, result.get("asset_type") or "")
    tv_interval = "5" if day_plan is not None else "D"
    st.subheader("Gráfico en vivo (TradingView)")
    if day_plan is not None:
        st.caption(
            "Velas de 5 minutos con los indicadores de TradingView: media exponencial, RSI y MACD. "
            "Esos dibujos viven en el gráfico. Los precios de entrada y salida los calcula el programa, "
            "porque TradingView no deja leer esos números sin una licencia de pago. "
            "En el acceso gratuito algunos símbolos van con retraso."
        )
    else:
        st.caption(
            "Gráfico diario con los indicadores de TradingView: media simple, RSI y MACD. "
            "La entrada y la salida de la tabla las calcula el programa. "
            "En el acceso gratuito algunos símbolos van con retraso."
        )
    components.html(tradingview_widget_html(tv_symbol, height=560, interval=tv_interval), height=570)

    swing_box = (
        st.expander("Contexto de varias semanas", expanded=False)
        if day_plan is not None
        else contextlib.nullcontext()
    )
    with swing_box:
        st.subheader("Resumen")
        _show_table(summary_table(result, source))

        left, right = st.columns(2)
        with left:
            st.subheader("Tendencia e indicadores")
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
            if swing_levels and swing_levels.get("entry") is not None:
                add_entry_exit_lines(fig, swing_levels)

            fig.update_layout(
                height=520,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#ffffff",
                font=dict(color="#1e293b"),
                margin=dict(l=0, r=0, t=40, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            fig.update_xaxes(gridcolor="#e2e8f0")
            fig.update_yaxes(gridcolor="#e2e8f0")
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
