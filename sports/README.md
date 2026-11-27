# FinSight Sports — parlays (MVP)

App Streamlit **aparte** del análisis financiero de FinSight. Sugiere parlays (MLB / NFL) con datos públicos reales y un modelo de probabilidad transparente.

## Cómo ejecutar

Desde la raíz del repo `finsight`:

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r sports/requirements.txt
streamlit run sports/app.py
```

La UI está en español. En la barra lateral elige **NFL** o **MLB** (NBA y fútbol aparecen como «próximamente»).

## Qué hace

| Panel | Comportamiento |
| --- | --- |
| **Parlays de hoy** | Solo muestra combinadas cuya probabilidad **combinada estimada del modelo sea ≥ 80%**. Piernas: ganador del partido, totales de equipo o del partido. Cada pierna trae % y una razón corta. Si ninguna califica, lo dice y **no** rellena con peores opciones. |
| **Cara a cara** | Eliges dos equipos: % estimado de victoria, rango probable de puntos/carreras y contexto (local, forma, lesiones). |
| **Refresh** | Caché ~60 s + meta-refresh; se muestra la marca de tiempo de la última descarga. |

## Fuentes de datos

- **MLB:** [MLB Stats API](https://statsapi.mlb.com/) (calendario, sede, pitchers probables, forma) y feed público ESPN de lesiones.
- **NFL:** endpoints públicos ESPN (scoreboard, calendarios por equipo, lesiones).

Si una fuente falla, la app muestra el error; **no inventa** estadísticas.

## Modelo y umbral del 80%

Estimación por partido (no son cuotas de casa de apuestas):

1. Forma reciente (últimos partidos finales: win rate relativo).
2. Ventaja local (~3–4 puntos porcentuales según deporte).
3. Penalización por lesiones públicas en posiciones clave (p. ej. QB / pitcher).
4. Proyección de puntos/carreras = mezcla de ofensiva propia y defensa rival.

Un parlay combina piernas multiplicando sus probabilidades estimadas (supuesto de independencia aproximada). El **80% es un umbral del modelo** para filtrar la lista, **no** una garantía empírica de acierto ni consejo de apuestas.

## Aviso

Las estimaciones son informativas. No constituyen consejo de apuestas ni promesa de resultados.
