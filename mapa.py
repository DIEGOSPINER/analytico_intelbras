"""Mapa das ocorrências a partir de latitude e longitude."""

from __future__ import annotations

import math
import os
import urllib.request

import cv2
import numpy as np

PASTA = "cache_mapa"
TILE = 256
AGENTE = "AnaliticoIntelbras/1.0 (monitoramento local)"
PALETA = (
    (235, 140, 20),
    (40, 140, 255),
    (180, 60, 170),
    (90, 210, 96),
    (0, 176, 255),
    (60, 60, 240),
    (220, 196, 40),
    (200, 120, 255),
)


def cor_tipo(nome: str):
    texto = str(nome or "Ocorrencia")
    return PALETA[sum(ord(caractere) for caractere in texto) % len(PALETA)]


def _fracao(lat, lon, zoom):
    n = 2 ** zoom
    x = (lon + 180.0) / 360.0 * n
    lat = max(-85.0, min(85.0, float(lat)))
    radiano = math.radians(lat)
    y = (1.0 - math.log(math.tan(radiano) + 1.0 / math.cos(radiano)) / math.pi) / 2.0 * n
    return x, y


def _baixar(zoom, x, y):
    os.makedirs(PASTA, exist_ok=True)
    caminho = os.path.join(PASTA, f"{zoom}-{x}-{y}.png")
    if os.path.exists(caminho):
        imagem = cv2.imread(caminho)
        if imagem is not None and imagem.size:
            return imagem
    pedido = urllib.request.Request(
        f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png",
        headers={"User-Agent": AGENTE},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=8) as resposta:
            dados = resposta.read()
    except Exception:
        return None
    with open(caminho, "wb") as arquivo:
        arquivo.write(dados)
    return cv2.imdecode(np.frombuffer(dados, np.uint8), cv2.IMREAD_COLOR)


def _zoom(pontos):
    if len(pontos) <= 1:
        return 15
    lats = [ponto["lat"] for ponto in pontos]
    lons = [ponto["lon"] for ponto in pontos]
    span = max(max(lats) - min(lats), max(lons) - min(lons), 0.0015)
    for zoom in range(16, 9, -1):
        if span / (360.0 / (2 ** zoom)) <= 2.0:
            return zoom
    return 10


def _validos(pontos):
    saida = []
    for ponto in pontos or []:
        try:
            lat = float(ponto["lat"])
            lon = float(ponto["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        if abs(lat) < 0.0001 and abs(lon) < 0.0001:
            continue
        item = dict(ponto)
        item["lat"] = lat
        item["lon"] = lon
        item["tipo"] = str(ponto.get("tipo") or "Ocorrencia")
        saida.append(item)
    return saida


def _legenda(validos):
    contagem = {}
    for item in validos:
        contagem[item["tipo"]] = contagem.get(item["tipo"], 0) + 1
    return [
        {"tipo": tipo, "quantidade": quantidade, "cor": cor_tipo(tipo)}
        for tipo, quantidade in sorted(contagem.items(), key=lambda par: (-par[1], par[0]))
    ]


def _projetar(pontos, largura, altura, baixar=None):
    baixar = baixar or _baixar
    validos = _validos(pontos)
    legenda = _legenda(validos)
    imagem = np.zeros((altura, largura, 3), dtype=np.uint8)
    imagem[:] = (22, 24, 22)
    if not validos:
        return imagem, [], legenda

    zoom = _zoom(validos)
    fracoes = [_fracao(ponto["lat"], ponto["lon"], zoom) for ponto in validos]
    xs = [item[0] for item in fracoes]
    ys = [item[1] for item in fracoes]
    margem = 0.6
    x0, x1 = min(xs) - margem, max(xs) + margem
    y0, y1 = min(ys) - margem, max(ys) + margem
    tx0, ty0, tx1, ty1 = _limites(x0, y0, x1, y1, zoom)
    while (tx1 - tx0 + 1) * (ty1 - ty0 + 1) > 12 and zoom > 10:
        zoom -= 1
        fracoes = [_fracao(ponto["lat"], ponto["lon"], zoom) for ponto in validos]
        xs = [item[0] for item in fracoes]
        ys = [item[1] for item in fracoes]
        x0, x1 = min(xs) - margem, max(xs) + margem
        y0, y1 = min(ys) - margem, max(ys) + margem
        tx0, ty0, tx1, ty1 = _limites(x0, y0, x1, y1, zoom)

    colunas = tx1 - tx0 + 1
    linhas = ty1 - ty0 + 1
    base = np.full((linhas * TILE, colunas * TILE, 3), (22, 24, 22), dtype=np.uint8)
    baixou = False
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            tile = baixar(zoom, tx, ty)
            if tile is None or getattr(tile, "size", 0) == 0:
                continue
            baixou = True
            tile = cv2.resize(tile, (TILE, TILE))
            base[(ty - ty0) * TILE:(ty - ty0 + 1) * TILE, (tx - tx0) * TILE:(tx - tx0 + 1) * TILE] = tile

    esquerda = max(0, min(base.shape[1] - 2, int((x0 - tx0) * TILE)))
    topo = max(0, min(base.shape[0] - 2, int((y0 - ty0) * TILE)))
    direita = max(esquerda + 2, min(base.shape[1], int((x1 - tx0) * TILE)))
    baixo = max(topo + 2, min(base.shape[0], int((y1 - ty0) * TILE)))
    recorte = base[topo:baixo, esquerda:direita]
    mapa = cv2.resize(recorte, (largura, altura), interpolation=cv2.INTER_AREA)
    escala_x = largura / max(recorte.shape[1], 1)
    escala_y = altura / max(recorte.shape[0], 1)
    marcas = []
    for ponto, (fx, fy) in zip(validos, fracoes):
        cx = int(((fx - tx0) * TILE - esquerda) * escala_x)
        cy = int(((fy - ty0) * TILE - topo) * escala_y)
        cx = max(8, min(largura - 8, cx))
        cy = max(8, min(altura - 8, cy))
        marcas.append((cx, cy, cor_tipo(ponto["tipo"])))
    if not baixou:
        cv2.putText(
            mapa, "sem ruas", (8, altura - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1, cv2.LINE_AA,
        )
    return mapa, marcas, legenda


def compor_mapa(pontos, largura, altura, baixar=None):
    mapa, marcas, legenda = _projetar(pontos, largura, altura, baixar)
    for cx, cy, cor in marcas:
        cv2.circle(mapa, (cx, cy), 7, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(mapa, (cx, cy), 5, cor, -1, cv2.LINE_AA)
    return mapa, legenda


def compor_calor(pontos, largura, altura, baixar=None):
    mapa, marcas, legenda = _projetar(pontos, largura, altura, baixar)
    if not marcas:
        return mapa, legenda
    calor = np.zeros(mapa.shape[:2], dtype=np.float32)
    raio = 36
    eixo = np.arange(-raio, raio + 1)
    grade_x, grade_y = np.meshgrid(eixo, eixo)
    nucleo = np.exp(-(grade_x ** 2 + grade_y ** 2) / (2 * 14 ** 2)).astype(np.float32)
    for cx, cy, _cor in marcas:
        x0, y0 = cx - raio, cy - raio
        x1, y1 = cx + raio + 1, cy + raio + 1
        rec_x0, rec_y0 = max(0, x0), max(0, y0)
        rec_x1, rec_y1 = min(largura, x1), min(altura, y1)
        if rec_x0 >= rec_x1 or rec_y0 >= rec_y1:
            continue
        nx0, ny0 = rec_x0 - x0, rec_y0 - y0
        nx1, ny1 = nx0 + (rec_x1 - rec_x0), ny0 + (rec_y1 - rec_y0)
        calor[rec_y0:rec_y1, rec_x0:rec_x1] += nucleo[ny0:ny1, nx0:nx1]
    pico = float(calor.max())
    if pico <= 0:
        return mapa, legenda
    nivel = calor / pico
    azul = np.clip(1 - nivel * 2, 0, 1)
    verde = np.clip(1 - np.abs(nivel - 0.55) * 2.2, 0, 1)
    vermelho = np.clip((nivel - 0.35) * 1.8, 0, 1)
    tinta = np.dstack((azul, verde, vermelho)) * 255
    alpha = np.clip(nivel * 1.35, 0, 0.78)[..., None]
    mistura = mapa.astype(np.float32) * (1 - alpha) + tinta * alpha
    return mistura.astype(np.uint8), legenda


def _limites(x0, y0, x1, y1, zoom):
    limite = 2 ** zoom
    tx0 = max(0, min(limite - 1, int(math.floor(x0))))
    tx1 = max(0, min(limite - 1, int(math.floor(x1))))
    ty0 = max(0, min(limite - 1, int(math.floor(y0))))
    ty1 = max(0, min(limite - 1, int(math.floor(y1))))
    if tx1 < tx0:
        tx0, tx1 = tx1, tx0
    if ty1 < ty0:
        ty0, ty1 = ty1, ty0
    return tx0, ty0, tx1, ty1
