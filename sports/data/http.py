"""HTTP helpers con errores explícitos (sin inventar datos)."""

from __future__ import annotations

from typing import Any, Optional

import requests

DEFAULT_TIMEOUT = 20
DEFAULT_HEADERS = {
    "User-Agent": "FinSightSportsMVP/1.0 (+https://github.com/robvnegas98-source/finsight)",
    "Accept": "application/json",
}


class FetchError(Exception):
    """Fallo al obtener o interpretar una fuente pública."""


def get_json(url: str, *, params: Optional[dict] = None, timeout: int = DEFAULT_TIMEOUT) -> Any:
    try:
        resp = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.Timeout as exc:
        raise FetchError(f"Tiempo de espera agotado: {url}") from exc
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        raise FetchError(f"HTTP {code} al consultar {url}") from exc
    except requests.RequestException as exc:
        raise FetchError(f"Error de red al consultar {url}: {exc}") from exc
    except ValueError as exc:
        raise FetchError(f"JSON inválido desde {url}") from exc
