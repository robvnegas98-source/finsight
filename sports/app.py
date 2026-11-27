"""
FinSight Sports — sugeridor de parlays (MLB / NFL).

Ejecutar desde la raíz del repo:
    streamlit run sports/app.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# Permite `streamlit run sports/app.py` con imports `sports.*`
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sports.data.mlb import fetch_mlb_bundle, fetch_team_form as mlb_team_form
from sports.data.nfl import fetch_nfl_bundle, fetch_team_form as nfl_team_form
from sports.data.types import SportBundle, TeamSnapshot
from sports.model.parlays import PARLAY_THRESHOLD, build_parlays
from sports.model.scoring import estimate_pair

REFRESH_SECONDS = 60

st.set_page_config(
    page_title="FinSight Sports — Parlays",
    page_icon="🏟️",
    layout="wide",
)

DISCLAIMER = (
    "**Aviso:** las probabilidades y parlays son **estimaciones de un modelo interno** "
    "(forma reciente, local/visitante y lesiones públicas). **No son consejo de apuestas**, "
    "no garantizan aciertos y el umbral del 80% es un filtro del modelo, no una promesa de rentabilidad."
)


def _fmt_pct(p: float) -> str:
    return f"{p * 100:.1f}%"


def _fmt_ts(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    except ValueError:
        return iso


@st.cache_data(ttl=REFRESH_SECONDS, show_spinner=False)
def load_bundle(sport: str) -> SportBundle:
    if sport == "mlb":
        return fetch_mlb_bundle()
    if sport == "nfl":
        return fetch_nfl_bundle()
    raise ValueError(sport)


@st.cache_data(ttl=REFRESH_SECONDS, show_spinner=False)
def load_team_enriched(sport: str, team_id: str) -> TeamSnapshot:
    if sport == "mlb":
        snap, _ = mlb_team_form(team_id)
        return snap
    snap, _ = nfl_team_form(team_id)
    return snap


def _render_errors(errors: list[str]) -> None:
    if not errors:
        return
    with st.expander(f"Avisos de datos ({len(errors)})", expanded=len(errors) <= 3):
        for err in errors:
            st.warning(err)


def _render_games(bundle: SportBundle) -> None:
    if not bundle.games:
        st.info(
            "No hay partidos programados en la ventana actual según las APIs públicas. "
            "En temporada baja (p. ej. MLB fuera de calendario) el panel de parlays puede quedar vacío."
        )
        return
    rows = []
    for g in bundle.games:
        rows.append(
            {
                "Estado": g.status_detail or g.status,
                "Visitante": g.away.name,
                "Local": g.home.name,
                "Sede": g.venue,
                "Inicio (UTC)": (g.start_time or "")[:19].replace("T", " "),
                "Marcador": (
                    f"{int(g.away_score) if g.away_score is not None else '-'} – "
                    f"{int(g.home_score) if g.home_score is not None else '-'}"
                ),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_parlays(bundle: SportBundle) -> None:
    st.subheader("Parlays de hoy")
    st.caption(
        f"Solo se muestran combinadas con probabilidad **combinada estimada ≥ {_fmt_pct(PARLAY_THRESHOLD)}**. "
        "Piernas: ganador, totales de equipo o del partido."
    )
    open_games = [g for g in bundle.games if g.status in {"pre", "in"}]
    if not open_games:
        st.warning("No hay partidos por jugar o en curso en la cartelera cargada; no se sugieren parlays.")
        return

    parlays = build_parlays(bundle.games)
    if not parlays:
        st.warning(
            f"Ningún parlay alcanza el umbral del modelo ({_fmt_pct(PARLAY_THRESHOLD)}). "
            "No se rellenan alternativas por debajo del filtro."
        )
        return

    for i, parlay in enumerate(parlays, start=1):
        with st.container(border=True):
            st.markdown(
                f"**Parlay #{i}** — probabilidad combinada estimada: "
                f"**{_fmt_pct(parlay.combined_probability)}** ({len(parlay.legs)} pierna/s)"
            )
            for leg in parlay.legs:
                st.markdown(
                    f"- {_fmt_pct(leg.probability)} · **{leg.label}**  \n"
                    f"  _{leg.reason}_"
                )


def _merge_injuries(enriched: TeamSnapshot, base: TeamSnapshot) -> TeamSnapshot:
    if not enriched.injuries and base.injuries:
        enriched.injuries = base.injuries
    return enriched


def _render_h2h(bundle: SportBundle, sport: str) -> None:
    st.subheader("Cara a cara")
    st.caption("Elige dos equipos para ver % estimado de victoria y un rango probable de puntos/carreras.")

    roster = sorted(bundle.roster_teams, key=lambda t: t.name)
    if len(roster) < 2:
        st.error("No se pudo cargar el listado de equipos.")
        return

    # Limpiar comparación previa si cambió el deporte (evita KeyError con nombres de otra liga)
    if st.session_state.get("h2h_sport") != sport:
        st.session_state["h2h_sport"] = sport
        st.session_state.pop("h2h_last", None)

    names = {t.name: t for t in roster}
    name_list = list(names.keys())
    c1, c2 = st.columns([3, 3])
    with c1:
        a_name = st.selectbox(
            "Equipo A (local en la simulación)",
            name_list,
            index=0,
            key=f"h2h_a_{sport}",
        )
    with c2:
        default_b = 1 if len(name_list) > 1 else 0
        b_name = st.selectbox(
            "Equipo B (visitante)",
            name_list,
            index=default_b,
            key=f"h2h_b_{sport}",
        )
    run = st.button("Comparar", type="primary", key=f"h2h_run_{sport}")

    if a_name == b_name:
        st.info("Selecciona dos equipos distintos.")
        return
    if not run and "h2h_last" not in st.session_state:
        return
    if run:
        st.session_state["h2h_last"] = (sport, a_name, b_name)

    last = st.session_state.get("h2h_last")
    if not last or last[0] != sport:
        return
    _, a_name, b_name = last
    if a_name not in names or b_name not in names or a_name == b_name:
        return

    base_a, base_b = names[a_name], names[b_name]
    with st.spinner("Cargando forma reciente…"):
        team_a = _merge_injuries(load_team_enriched(sport, base_a.id), base_a)
        team_b = _merge_injuries(load_team_enriched(sport, base_b.id), base_b)

    est = estimate_pair(team_a, team_b, sport, a_is_home=True)
    left, right = st.columns(2)
    with left:
        st.metric(f"Victoria {team_a.name}", _fmt_pct(est.home_win_pct))
        for r in est.reasons_home[:4]:
            st.caption(f"• {r}")
        if team_a.injuries:
            outs = [i for i in team_a.injuries if "out" in (i.status or "").lower() or "doubt" in (i.status or "").lower()]
            st.caption(f"Lesiones reportadas: {len(team_a.injuries)}" + (f" (graves/dudosas: {len(outs)})" if outs else ""))
    with right:
        st.metric(f"Victoria {team_b.name}", _fmt_pct(est.away_win_pct))
        for r in est.reasons_away[:4]:
            st.caption(f"• {r}")
        if team_b.injuries:
            outs = [i for i in team_b.injuries if "out" in (i.status or "").lower() or "doubt" in (i.status or "").lower()]
            st.caption(f"Lesiones reportadas: {len(team_b.injuries)}" + (f" (graves/dudosas: {len(outs)})" if outs else ""))

    st.markdown(
        f"**Marcador probable:** {team_a.name} {est.projected_home_score:.1f} – "
        f"{est.projected_away_score:.1f} {team_b.name}  \n"
        f"**Rango total estimado:** {est.score_low:.1f} – {est.score_high:.1f} {est.unit} "
        f"(proyección basada en promedios recientes reales; si faltan datos, se indica en el contexto)."
    )


def main() -> None:
    st.title("FinSight Sports")
    st.markdown("Sugeridor de parlays con datos públicos (calendario, sede, forma y lesiones).")
    st.info(DISCLAIMER)

    sport_label = st.sidebar.radio(
        "Deporte",
        ["NFL", "MLB", "NBA", "Fútbol"],
        index=0,
    )
    st.sidebar.caption(f"Auto-refresh cada ~{REFRESH_SECONDS}s (caché Streamlit).")

    if sport_label in {"NBA", "Fútbol"}:
        st.header(f"{sport_label}: próximamente")
        st.write("La arquitectura está lista; el MVP actual cubre **MLB** y **NFL**.")
        st.markdown(DISCLAIMER)
        return

    sport = "nfl" if sport_label == "NFL" else "mlb"

    # Dispara rerun periódico
    now = datetime.now(timezone.utc)
    st.caption(f"Hora local de consulta: {now.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}")

    try:
        with st.spinner(f"Actualizando datos {sport_label}…"):
            bundle = load_bundle(sport)
    except Exception as exc:  # noqa: BLE001 — mostrar fallo de red al usuario
        st.error(f"No se pudieron obtener datos: {exc}")
        st.markdown(DISCLAIMER)
        return

    st.success(f"Última actualización de datos: **{_fmt_ts(bundle.fetched_at)}**")
    _render_errors(bundle.errors)

    st.subheader(f"Cartelera {sport_label}")
    _render_games(bundle)

    col_a, col_b = st.columns(2)
    with col_a:
        _render_parlays(bundle)
    with col_b:
        _render_h2h(bundle, sport)

    st.divider()
    st.markdown(DISCLAIMER)

    # Refresh suave: fragmento / meta refresh
    st.markdown(
        f'<meta http-equiv="refresh" content="{REFRESH_SECONDS}">',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
