"""Rotas de trânsito entre pontos (OSRM), no estilo de apps de navegação."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from functools import lru_cache

_TIMEOUT = 8
_URL = "https://router.project-osrm.org/route/v1/driving/{coords}?overview=full&geometries=geojson"


def _chave(pontos: list[tuple[float, float]]) -> tuple:
    return tuple((round(lat, 5), round(lon, 5)) for lat, lon in pontos)


@lru_cache(maxsize=256)
def _buscar(chave: tuple) -> tuple:
    if len(chave) < 2:
        return tuple((lat, lon) for lat, lon in chave)
    coords = ";".join(f"{lon},{lat}" for lat, lon in chave)
    url = _URL.format(coords=coords)
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT) as resposta:
            bruto = json.loads(resposta.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return tuple((lat, lon) for lat, lon in chave)
    rotas = bruto.get("routes") if isinstance(bruto, dict) else None
    if not rotas:
        return tuple((lat, lon) for lat, lon in chave)
    geometria = (rotas[0] or {}).get("geometry") or {}
    coordenadas = geometria.get("coordinates") or []
    if not coordenadas:
        return tuple((lat, lon) for lat, lon in chave)
    return tuple((float(lat), float(lon)) for lon, lat in coordenadas)


def caminho_dirigindo(pontos: list[tuple[float, float]]) -> list[list[float]]:
    """Devolve [[lat, lon], ...] seguindo as vias entre os pontos."""
    limpos = []
    for item in pontos or []:
        try:
            lat, lon = float(item[0]), float(item[1])
        except (TypeError, ValueError, IndexError):
            continue
        if abs(lat) <= 90 and abs(lon) <= 180:
            limpos.append((lat, lon))
    if len(limpos) < 2:
        return [[lat, lon] for lat, lon in limpos]
    return [[lat, lon] for lat, lon in _buscar(_chave(limpos))]
