# FinSight Multi-Agent
Sistema local de análisis financiero con 6 agentes para acciones, ETFs y criptomonedas.

## Instalación

```bash
cd finsight
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecutar

```bash
streamlit run app.py
```

## Estructura

- `app.py` → Interfaz Streamlit (fácil de modificar)
- `agents/` → Un archivo por agente (puedes cambiar su lógica cuando quieras)
- `core/graph.py` → Flujo entre agentes (LangGraph)
- `core/state.py` → Estado compartido

Todo está preparado para que puedas editar o ampliar cualquier parte sin romper el resto.
