# FinSight Multi-Agent

Sistema local de análisis financiero con seis agentes sobre [LangGraph](https://github.com/langchain-ai/langgraph). Cubre acciones, ETFs, futuros, divisas e índices y criptomonedas.

> **Aviso:** las señales, escenarios y textos de FinSight son informativos y **no constituyen asesoramiento de inversión** ni una recomendación de compra o venta. No uses este prototipo como única base para decidir.

## Requisitos

- Python 3.11 o superior (desarrollado con 3.12)
- Conexión a internet para cotizaciones

No hace falta ninguna clave para precios, titulares o el índice de miedo y codicia.

## Instalación

En Windows no actives el entorno desde PowerShell: suele fallar con «la ejecución de scripts está deshabilitada» y después `streamlit` no se reconoce. Haz doble clic en `iniciar.bat` (está en la carpeta del proyecto). Ese archivo crea el entorno, instala las librerías y abre el navegador. Hace falta [Python 3.11 o más nuevo](https://www.python.org/downloads/) con la casilla **Add python.exe to PATH** marcada.

En Mac o Linux:

```bash
cd finsight
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### FinSight Sports (parlays MLB/NFL)

App Streamlit **separada** (no mezcla la lógica financiera). Detalles en [`sports/README.md`](sports/README.md):

```bash
pip install -r sports/requirements.txt
streamlit run sports/app.py
```

Copia el ejemplo de variables si quieres activar el resumen opcional:

```bash
cp .env.example .env
```

## Variables de entorno

| Variable | Obligatoria | Uso |
| --- | --- | --- |
| `OPENAI_API_KEY` | No | Si está definida, el agente de sentimiento añade un resumen corto de los titulares. Si falta, o si la llamada falla, el análisis sigue con las fuentes públicas. |
| `OPENAI_MODEL` | No | Modelo de ese resumen. Por defecto `gpt-4o-mini`. |

`ALPHA_VANTAGE_KEY` aparece comentada en `.env.example` y el código actual no la lee.

## Tickers de ejemplo

| Ticker | Tipo | Notas |
| --- | --- | --- |
| `AAPL` | Acción | Yahoo Finance, con PER |
| `BRK-B` | Acción | La clase `B` no se confunde con cripto |
| `SPY`, `GLD` | ETF | PER solo como referencia del fondo |
| `BTC-USD`, `ETH-USD` | Cripto | Se normalizan a `BTC/USDT`. El precio se pide a Binance por CCXT; si no responde, a Kraken o Coinbase (`BTC/USD`) y, si tampoco, a Yahoo |
| `GC=F` | Futuro | Oro. Sin PER |
| `XAUUSD=X` | Divisa / metal spot | Sin PER |
| `^GSPC` | Índice | Sin PER del propio ticker |

## Ejecutar

En Windows, doble clic en `iniciar.bat`. En Mac o Linux, con el entorno ya activado:

```bash
streamlit run app.py
```

Se abre en el navegador, normalmente en http://localhost:8501. La interfaz llama a `build_graph()` y recorre los seis nodos. No usa el supervisor lineal antiguo.

## Tests

Sin red: indicadores, señal técnica, clasificación y el grafo van con datos sintéticos.

```bash
python -m pytest
```

## Arquitectura

El estado compartido está en `core/state.py` (`AnalysisState`). `core/graph.py` compila un grafo con un nodo por agente:

1. **Supervisor** (`agents/supervisor.py`) — normaliza el ticker. El orden ya no está en un bucle: son las aristas del grafo.
2. **Data Collector** (`agents/data_collector.py`) — clasifica el activo, descarga OHLCV y solo pide fundamentales tipo PER a acciones y ETFs (o a un símbolo que todavía no está clasificado). En cripto, CCXT es la fuente de precios: primero Binance en par USDT y, si ese mercado no está disponible, Kraken o Coinbase en par USD. Yahoo Finance queda como último respaldo.
3. **Technical**, **Fundamental** y **Sentiment** salen en paralelo del recolector y escriben cada uno su parte del estado.
4. **Chief Analyst** (`agents/chief.py`) espera a los tres. Pondera la señal técnica, el fundamental (si aplica) y el sentimiento, y redacta la justificación con el RSI, el MACD, las medias, la presión compradora y las probabilidades de escenario que también muestra la interfaz.

Pesos de partida, renormalizados si falta una pata:

| Tipo | Técnico | Fundamental | Sentimiento |
| --- | --- | --- | --- |
| Acción | 45 % | 30 % | 25 % |
| ETF | 50 % | 20 % | 30 % |
| Cripto | 55 % | 0 % | 45 % |
| Futuro o divisa | 70 % | 0 % | 30 % |
| Índice | 65 % | 0 % | 35 % |

Sentimiento, en este orden y saltando lo que falle:

- Titulares de Yahoo Finance (`Ticker.news`), con un léxico simple en español e inglés.
- Índice cripto de miedo y codicia de [alternative.me](https://api.alternative.me/fng/) (sin clave). Solo entra en la nota y en la ponderación cuando el activo es cripto.
- VIX (`^VIX`) como contexto de volatilidad.
- OpenAI, solo si hay `OPENAI_API_KEY`.

Los avisos de cada nodo se acumulan en `errors` (el grafo los concatena) y la pantalla los enseña sin cortar el resto.

## Estructura

- `app.py` — interfaz Streamlit
- `agents/` — un archivo por agente
- `core/graph.py` — flujo LangGraph
- `core/state.py` — estado compartido
- `core/assets.py` — clasificación y símbolos cripto, sin red
- `core/prices.py` — OHLCV común para Yahoo y CCXT
- `tests/` — pytest, sin red

## Aviso

Las señales no son asesoramiento de inversión. Los escenarios son una proyección ilustrativa a partir de la tendencia y la volatilidad recientes, y las probabilidades de optimista, base y pesimista suman 100.
