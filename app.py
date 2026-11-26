import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from agents.supervisor import run_analysis

st.set_page_config(page_title="FinSight Multi-Agent", layout="wide")

st.title("FinSight — Analizador Multi-Agente")
st.caption("Acciones · ETFs · Criptomonedas")

ticker = st.text_input(
    "Ticker (ej: AAPL, SPY, BTC-USD, GLD, GC=F, XAUUSD=X)", 
    value="GC=F"
).upper().strip()

if st.button("Analizar", type="primary") and ticker:
    with st.spinner("Ejecutando los 6 agentes..."):
        result = run_analysis(ticker)
    
    rec = result.get("final_recommendation", {})
    tech = result.get("technical", {})
    bp = tech.get("buying_pressure", {})
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Señal Final", rec.get("signal", "N/A"))
    col2.metric("Confianza", f"{rec.get('confidence', 0):.0%}")
    col3.metric("Señal Técnica", tech.get("signal", "N/A"))
    col4.metric("Proyección", tech.get("projection", "—"))
    
    st.subheader("Justificación")
    st.write(rec.get("reasoning", "Sin datos suficientes"))
    
    # Cuadro de presión compradora
    if bp:
        st.subheader("Presión Compradora")
        level = bp.get("level", "—")
        desc = bp.get("description", "")
        ratio = bp.get("volume_ratio", 1)
        
        # Color según nivel
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
        
        st.markdown(
            f"""
            <div style="background-color:{color}; border-left:5px solid {border}; padding:12px 16px; border-radius:6px; margin-bottom:16px;">
                <strong style="font-size:1.1em;">{level}</strong><br>
                <span style="color:#333;">{desc}</span><br>
                <small>Ratio volumen vs promedio 20d: <b>{ratio}x</b></small>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Gráfico con escenarios
    st.subheader("Gráfico de Precio + Escenarios con Probabilidades")
    yf_hist = result.get("raw_data", {}).get("sources", {}).get("yfinance", {}).get("history")
    scenarios = tech.get("scenarios", {})
    probs = scenarios.get("probabilities", {})
    
    if yf_hist and scenarios and probs:
        df = pd.DataFrame(yf_hist)
        if "Close" in df.columns:
            df["Close"] = df["Close"].astype(float)
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df.index, y=df["Close"],
                mode="lines", name="Precio histórico",
                line=dict(color="#1f77b4", width=2)
            ))
            
            future_dates = pd.to_datetime(scenarios["dates"])
            fig.add_trace(go.Scatter(
                x=future_dates, y=scenarios["optimistic"],
                mode="lines", name=f"Optimista ({probs.get('optimistic', 0)}%)",
                line=dict(color="green", dash="dash", width=2)
            ))
            fig.add_trace(go.Scatter(
                x=future_dates, y=scenarios["base"],
                mode="lines", name=f"Base ({probs.get('base', 0)}%)",
                line=dict(color="orange", dash="dash", width=2)
            ))
            fig.add_trace(go.Scatter(
                x=future_dates, y=scenarios["pessimistic"],
                mode="lines", name=f"Pesimista ({probs.get('pessimistic', 0)}%)",
                line=dict(color="red", dash="dash", width=2)
            ))
            
            best = scenarios.get("best_scenario", "base")
            best_prob = probs.get(best, 0)
            best_name = {"optimistic": "Optimista", "base": "Base", "pessimistic": "Pesimista"}.get(best, best)
            
            fig.add_annotation(
                x=future_dates[len(future_dates)//2],
                y=max(scenarios[best]) if scenarios.get(best) else df["Close"].iloc[-1],
                text=f"Más probable: {best_name} ({best_prob}%)",
                showarrow=True, arrowhead=2,
                font=dict(size=13, color="black"),
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor="gray"
            )
            
            sr = tech.get("support_resistance", {})
            if sr.get("support"):
                fig.add_hline(y=sr["support"], line_dash="dot", line_color="green", annotation_text="Soporte")
            if sr.get("resistance"):
                fig.add_hline(y=sr["resistance"], line_dash="dot", line_color="red", annotation_text="Resistencia")
            
            fig.update_layout(height=520, margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"Escenario más probable: **{best_name}** ({best_prob}%).")
    else:
        st.info("No se obtuvieron datos suficientes para graficar escenarios.")
    
    st.subheader("Indicadores Técnicos")
    ind = tech.get("indicators", {})
    if ind:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("RSI (14)", ind.get("rsi_14", "—"))
        c2.metric("MACD", ind.get("macd", "—"))
        c3.metric("SMA 50", ind.get("sma_50", "—"))
        c4.metric("SMA 200", ind.get("sma_200", "—"))
    
    if tech.get("notes"):
        st.caption("Notas: " + " · ".join(tech["notes"]))
    
    with st.expander("Detalle Técnico completo"):
        st.json(tech)
    with st.expander("Detalle Fundamental"):
        st.json(result.get("fundamental", {}))
    with st.expander("Detalle Sentimiento & Macro"):
        st.json(result.get("sentiment", {}))
    with st.expander("Recomendación final"):
        st.json(rec)
    
    if result.get("errors"):
        st.warning("Advertencias:")
        for err in result["errors"]:
            st.write(f"- {err}")

else:
    st.info("Introduce un ticker y pulsa Analizar. Prueba con **GC=F** o **GLD** para oro.")
