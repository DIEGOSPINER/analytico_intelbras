"""Três painéis de monitoramento ao vivo, no lugar das páginas do Power BI."""

from __future__ import annotations

import csv
import json
import os
import threading
import time
from collections import deque
from datetime import date, datetime, timedelta

import cv2
import numpy as np

from mapa import compor_calor, compor_mapa

INTERVALO_PAINEL_SEG = 15

JANELAS_PAINEL = {
    "1": "MONITORAMENTO CONTAGENS",
    "2": "MONITORAMENTO COMPORTAMENTO",
    "3": "MONITORAMENTO LEITURA",
    "4": "MONITORAMENTO MAPAS",
}

LARGURA = 1200
ALTURA = 700
FUNDO = (12, 12, 12)
CARTAO = (18, 18, 18)
BORDA = (48, 48, 92)
TEXTO = (235, 235, 235)
DIM = (150, 150, 150)
AZUL = (235, 140, 20)
AZUL_CLARO = (255, 196, 90)
LARANJA = (40, 140, 255)
ROXO = (180, 60, 170)
CIANO = (220, 196, 40)
VERDE = (90, 210, 96)
AMBAR = (0, 176, 255)
VERMELHO = (60, 60, 240)
ROSA = (180, 80, 220)

CATEGORIAS = ("Veiculo", "Pessoa", "Objeto", "Animal")
RISCOS = ("Informativo", "Atencao", "Prioritario", "Critico")
FAIXAS = ("Comportamento", "Interacao", "Alerta")
COR_CATEGORIA = {
    "Veiculo": CIANO,
    "Pessoa": LARANJA,
    "Objeto": AZUL,
    "Animal": ROXO,
}
COR_RISCO = {
    "Informativo": AZUL,
    "Atencao": AMBAR,
    "Prioritario": LARANJA,
    "Critico": VERMELHO,
}
COR_FAIXA = {
    "Comportamento": AZUL,
    "Interacao": AZUL_CLARO,
    "Alerta": VERMELHO,
}
CORES_SERIE = (ROSA, AZUL, LARANJA, VERDE, CIANO, ROXO, AMBAR)


def _limpo(texto) -> str:
    return str(texto or "").translate(str.maketrans(
        "áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ",
        "aaaaeeioooucAAAAEEIOOOUC",
    ))


def _texto(imagem, texto, x, y, escala, cor, espessura=1):
    cv2.putText(
        imagem, _limpo(texto), (int(x), int(y)),
        cv2.FONT_HERSHEY_SIMPLEX, escala, cor, espessura, cv2.LINE_AA,
    )


def _quebrar(texto, largura_px, escala=0.42):
    palavras = _limpo(texto).split()
    linhas = []
    atual = ""
    for palavra in palavras:
        teste = f"{atual} {palavra}".strip()
        largura, _ = cv2.getTextSize(teste, cv2.FONT_HERSHEY_SIMPLEX, escala, 1)[0]
        if atual and largura > largura_px:
            linhas.append(atual)
            atual = palavra
        else:
            atual = teste
    if atual:
        linhas.append(atual)
    return linhas


def _cartao(imagem, x, y, largura, altura, titulo):
    cv2.rectangle(imagem, (x, y), (x + largura, y + altura), CARTAO, -1)
    cv2.rectangle(imagem, (x, y), (x + largura, y + altura), BORDA, 1)
    if titulo:
        _texto(imagem, titulo, x + 14, y + 24, 0.45, TEXTO, 1)


def _barra(imagem, x, y, largura, altura, fracao, cor):
    cv2.rectangle(imagem, (x, y), (x + largura, y + altura), (40, 40, 40), -1)
    preenchido = int(largura * max(0.0, min(1.0, fracao)))
    if preenchido > 0:
        cv2.rectangle(imagem, (x, y), (x + preenchido, y + altura), cor, -1)


def _base():
    imagem = np.zeros((ALTURA, LARGURA, 3), dtype=np.uint8)
    imagem[:] = FUNDO
    return imagem


def _cabecalho(imagem, titulo, pacote):
    nome = pacote.get("titulo") or "MONITORAMENTO"
    _texto(imagem, nome, 16, 28, 0.62, TEXTO, 1)
    _texto(imagem, titulo, 16, 52, 0.48, AZUL_CLARO, 1)
    _texto(
        imagem,
        f"HOJE {pacote.get('hoje', '')}   {pacote.get('relogio', '')}",
        LARGURA - 340, 28, 0.42, DIM, 1,
    )
    if not pacote.get("pronto"):
        _texto(imagem, "LENDO HISTORICO", LARGURA - 340, 52, 0.42, AMBAR, 1)
    else:
        _texto(imagem, "atualiza a cada 15s", LARGURA - 340, 52, 0.4, DIM, 1)


def _rodape(imagem):
    _texto(
        imagem,
        "METODOLOGIA: CONTAGEM DE FACES OBJETOS POR INTELIGENCIA ARTIFICIAL",
        16, ALTURA - 14, 0.38, DIM, 1,
    )


def _maximo(valores):
    maior = 0
    for valor in valores:
        if isinstance(valor, dict):
            maior = max(maior, sum(valor.values()))
        else:
            maior = max(maior, valor)
    return max(maior, 1)


def desenhar_fluxo(pacote):
    imagem = _base()
    _cabecalho(imagem, "CONTAGENS", pacote)
    categorias = pacote.get("categorias") or {}
    total = pacote.get("total") or 0
    cameras = pacote.get("cameras") or []

    _cartao(imagem, 12, 68, 360, 300, "ACESSOS POR CAMERA")
    _texto(imagem, "Camera", 28, 108, 0.4, DIM, 1)
    y = 136
    if not cameras:
        _texto(imagem, "nenhuma camera no dia", 28, y, 0.42, DIM, 1)
    for camera in cameras[:6]:
        cor = AZUL if camera.get("online") else DIM
        cv2.circle(imagem, (36, y - 4), 5, cor, -1, cv2.LINE_AA)
        _texto(imagem, str(camera.get("nome") or "")[:20], 52, y, 0.46, TEXTO, 1)
        _texto(imagem, str(camera.get("itens") or 0), 300, y, 0.46, AZUL_CLARO, 1)
        y += 32

    _cartao(imagem, 384, 68, 500, 108, "")
    _texto(imagem, str(total), 404, 128, 1.35, TEXTO, 2)
    _texto(imagem, "TOTAL DE ITENS", 404, 156, 0.42, DIM, 1)
    if cameras:
        cv2.circle(imagem, (700, 100), 5, AZUL, -1, cv2.LINE_AA)
        _texto(imagem, str(cameras[0].get("nome") or "")[:16], 714, 106, 0.38, TEXTO, 1)

    _cartao(imagem, 384, 188, 500, 180, "FLUXO POR CATEGORIA")
    maior = _maximo(categorias.get(nome, 0) for nome in CATEGORIAS)
    y = 232
    for nome in CATEGORIAS:
        valor = int(categorias.get(nome, 0))
        _texto(imagem, nome, 400, y, 0.42, TEXTO, 1)
        _barra(imagem, 490, y - 12, 280, 14, valor / maior, AZUL)
        _texto(imagem, str(valor), 780, y, 0.42, TEXTO, 1)
        y += 30
    _texto(imagem, "0", 490, 358, 0.32, DIM, 1)
    _texto(imagem, str(maior // 2), 610, 358, 0.32, DIM, 1)
    _texto(imagem, str(maior), 750, 358, 0.32, DIM, 1)

    _cartao(imagem, 896, 68, 292, 300, "DATA E HORA")
    y = 104
    for camera in cameras[:3]:
        marca = "[x]" if camera.get("online") else "[ ]"
        _texto(imagem, f"{marca} {camera.get('nome', '')}"[:26], 910, y, 0.38, TEXTO, 1)
        y += 20
    y += 8
    for dia in (pacote.get("dias") or [])[:3]:
        if y > 200:
            break
        _texto(imagem, f"[x] {dia.get('rotulo', '')}  {dia.get('total', 0)}", 910, y, 0.36, TEXTO, 1)
        y += 18
    y += 6
    for hora in (pacote.get("horas_ativas") or [])[:2]:
        if y > 246:
            break
        _texto(imagem, f"[x] {hora.get('rotulo', '')}", 910, y, 0.36, DIM, 1)
        y += 18
    _texto(imagem, "TIPO DE DETECCAO", 910, 268, 0.4, TEXTO, 1)
    y = 290
    classes = pacote.get("classes") or []
    if not classes:
        _texto(imagem, "[ ] sem deteccao", 910, y, 0.36, DIM, 1)
    for nome, valor in classes[:5]:
        _texto(imagem, f"[x] {nome[:14]}  {valor}", 910, y, 0.36, TEXTO, 1)
        y += 18

    _cartao(imagem, 12, 380, 1176, 286, "HISTORICO")
    _texto(imagem, "Categoria", 28, 412, 0.36, DIM, 1)
    x = 120
    for nome in CATEGORIAS:
        cv2.circle(imagem, (x, 407), 4, COR_CATEGORIA[nome], -1, cv2.LINE_AA)
        _texto(imagem, nome, x + 10, 412, 0.36, COR_CATEGORIA[nome], 1)
        x += 120
    horas = pacote.get("horas") or {}
    series = [(nome, horas.get(nome) or [0] * 24, COR_CATEGORIA[nome]) for nome in CATEGORIAS]
    _grafico(
        imagem, 48, 428, 1100, 190, series,
        [f"{hora:02d}:00" for hora in range(24)],
        passo=3, marcar=True,
    )
    _rodape(imagem)
    return imagem


def desenhar_comportamento(pacote):
    imagem = _base()
    _cabecalho(imagem, "COMPORTAMENTOS", pacote)
    riscos = pacote.get("riscos") or {}
    total_risco = sum(int(riscos.get(nome, 0)) for nome in RISCOS) or 0

    _cartao(imagem, 12, 68, 400, 300, "PRIORIDADE DE DETECCAO")
    fatias = [(int(riscos.get(nome, 0)), COR_RISCO[nome]) for nome in RISCOS]
    _donut(imagem, 118, 210, 72, fatias)
    rotulo = str(total_risco)
    _texto(imagem, rotulo, 118 - 7 * len(rotulo), 216, 0.55, TEXTO, 1)
    y = 108
    for nome in RISCOS:
        valor = int(riscos.get(nome, 0))
        pct = (100.0 * valor / total_risco) if total_risco else 0.0
        cv2.circle(imagem, (210, y - 4), 5, COR_RISCO[nome], -1, cv2.LINE_AA)
        _texto(imagem, nome, 224, y, 0.4, COR_RISCO[nome], 1)
        _texto(imagem, f"{valor}   {pct:.1f}%", 224, y + 18, 0.4, TEXTO, 1)
        y += 46

    _cartao(imagem, 424, 68, 360, 100, "")
    _texto(imagem, str(pacote.get("ids") or 0), 440, 125, 1.15, TEXTO, 2)
    _texto(imagem, "CONTAGEM DE ID", 440, 152, 0.4, DIM, 1)

    _cartao(imagem, 424, 180, 360, 188, "O QUE FOI DETECTADO")
    faixas = pacote.get("faixas") or {}
    cameras = [c.get("nome") for c in pacote.get("cameras") or [] if c.get("nome")]
    maior = 1
    for nome in FAIXAS:
        maior = max(maior, sum(int((faixas.get(nome) or {}).get(cam, 0)) for cam in cameras))
    y = 222
    for nome in FAIXAS:
        _texto(imagem, nome[:14], 438, y, 0.38, TEXTO, 1)
        inicio = 560
        for indice, camera in enumerate(cameras[:3]):
            valor = int((faixas.get(nome) or {}).get(camera, 0))
            largura = int(180 * valor / maior)
            cor = AZUL if indice == 0 else AZUL_CLARO if indice == 1 else VERDE
            if largura > 0:
                cv2.rectangle(imagem, (inicio, y - 12), (inicio + largura, y), cor, -1)
                inicio += largura
        y += 42
    x = 438
    for indice, camera in enumerate(cameras[:3]):
        cor = AZUL if indice == 0 else AZUL_CLARO if indice == 1 else VERDE
        _texto(imagem, str(camera)[:12], x, 352, 0.34, cor, 1)
        x += 110

    _cartao(imagem, 796, 68, 390, 300, "TIPO DE COMPORTAMENTO")
    tipos = pacote.get("tipos") or []
    maior_tipo = 1
    for item in tipos[:6]:
        maior_tipo = max(maior_tipo, sum(int(v) for v in (item.get("cameras") or {}).values()))
    y = 112
    for item in tipos[:6]:
        _texto(imagem, str(item.get("classe") or "")[:18], 810, y, 0.38, TEXTO, 1)
        inicio = 980
        for indice, camera in enumerate(cameras[:3]):
            valor = int((item.get("cameras") or {}).get(camera, 0))
            largura = int(170 * valor / maior_tipo)
            cor = AZUL if indice == 0 else AZUL_CLARO if indice == 1 else VERDE
            if largura > 0:
                cv2.rectangle(imagem, (inicio, y - 12), (inicio + largura, y), cor, -1)
                inicio += largura
        y += 36

    _cartao(imagem, 12, 380, 760, 286, "PRIORIDADE AO LONGO DOS DIAS")
    serie = pacote.get("serie") or {}
    rotulos = serie.get("rotulos") or []
    curvas = []
    for indice, (nome, valores) in enumerate((serie.get("curvas") or [])[:6]):
        curvas.append((nome, valores, CORES_SERIE[indice % len(CORES_SERIE)]))
    _grafico(imagem, 36, 430, 710, 190, curvas, rotulos, passo=1)
    x = 36
    for nome, _, cor in curvas[:4]:
        _texto(imagem, str(nome)[:14], x, 418, 0.34, cor, 1)
        x += 150

    _cartao(imagem, 784, 380, 402, 286, "APP")
    avisos = pacote.get("app") or []
    if not avisos:
        _texto(imagem, "sem ocorrencia informada", 800, 430, 0.42, DIM, 1)
    y = 424
    for aviso in avisos[:4]:
        _texto(imagem, str(aviso.get("quando") or ""), 800, y, 0.36, AZUL_CLARO, 1)
        _texto(imagem, str(aviso.get("titulo") or "")[:32], 800, y + 18, 0.42, TEXTO, 1)
        _texto(imagem, str(aviso.get("lugar") or "")[:32], 800, y + 36, 0.36, DIM, 1)
        y += 58
    _rodape(imagem)
    return imagem


def desenhar_leitura(pacote):
    altura = 780
    imagem = np.zeros((altura, LARGURA, 3), dtype=np.uint8)
    imagem[:] = FUNDO
    _cabecalho(imagem, "LEITURA", pacote)
    _cartao(imagem, 12, 68, 520, 210, "ALERTAS DE RF E LPR")
    _match_grande(imagem, 28, 100, pacote.get("match"))

    _cartao(imagem, 544, 68, 644, 210, "ULTIMOS ALERTAS  FACE E PLACA")
    interesses = pacote.get("interesse") or []
    if not interesses:
        _texto(imagem, "nenhum rosto ou placa de interesse ainda", 560, 120, 0.4, DIM, 1)
    for indice, item in enumerate(interesses[:4]):
        _linha_interesse(imagem, 560, 104 + indice * 40, item)

    _cartao(imagem, 12, 290, 760, 220, "OCORRENCIAS")
    mapa = pacote.get("mapa")
    if mapa is not None and getattr(mapa, "size", 0):
        thumb = cv2.resize(mapa, (736, 180), interpolation=cv2.INTER_AREA)
        _colar(imagem, thumb, 24, 318)
    else:
        _texto(imagem, "sem latitude e longitude nas ocorrencias do app", 28, 380, 0.42, DIM, 1)

    _cartao(imagem, 784, 290, 404, 220, "LEGENDA POR TIPO")
    y = 328
    legenda = pacote.get("legenda_mapa") or []
    if not legenda:
        _texto(imagem, "nenhum ponto no mapa", 800, y, 0.4, DIM, 1)
        y += 24
    for item in legenda[:6]:
        cv2.circle(imagem, (808, y - 4), 6, item.get("cor") or AZUL, -1, cv2.LINE_AA)
        _texto(
            imagem,
            f"{item.get('tipo') or 'Ocorrencia'}"[:22],
            824, y, 0.38, TEXTO, 1,
        )
        _texto(imagem, str(item.get("quantidade") or 0), 1104, y, 0.38, DIM, 1)
        y += 22
    informe = (pacote.get("enviados") or [None])[0]
    insight = (pacote.get("insights") or [None])[0]
    if informe and y < 470:
        _texto(imagem, str(informe.get("descricao") or informe.get("tipo") or "")[:36], 800, y + 4, 0.32, AZUL_CLARO, 1)
        y += 18
    if insight and y < 492:
        _texto(imagem, str(insight.get("descricao") or "")[:36], 800, y + 4, 0.32, AMBAR, 1)

    _cartao(imagem, 12, 522, 580, 220, "RESUMO")
    _bloco(imagem, 28, 582, 548, pacote.get("resumo") or (
        "O relatorio do dia ainda nao tem resumo. "
        "O agente grava este texto no fechamento do dia."
    ), limite=6)
    _cartao(imagem, 604, 522, 584, 220, "ASSESSORAMENTO")
    _bloco(imagem, 620, 582, 548, pacote.get("assessoramento") or (
        "O assessoramento entra no mesmo relatorio, "
        "com a conclusao de risco e a orientacao do periodo."
    ), limite=6)
    _texto(
        imagem,
        "METODOLOGIA: CONTAGEM DE FACES OBJETOS POR INTELIGENCIA ARTIFICIAL",
        16, altura - 14, 0.38, DIM, 1,
    )
    return imagem


def _match_grande(imagem, x, y, match):
    if not match:
        _texto(imagem, "sem alerta de interesse agora", x, y + 28, 0.46, DIM, 1)
        _texto(imagem, "a comparacao sobe com o mesmo match da camera", x, y + 54, 0.38, DIM, 1)
        return
    cor_tipo = (210, 90, 230) if match.get("tipo") == "FACE" else CIANO
    _texto(imagem, match.get("tipo") or "", x, y + 8, 0.5, cor_tipo, 1)
    _texto(imagem, str(match.get("camera") or ""), x + 90, y + 8, 0.42, DIM, 1)
    taxa = float(match.get("taxa") or 0)
    _texto(imagem, f"{match.get('rotulo_taxa') or 'SIM'} {taxa:.2f}", x + 250, y + 8, 0.55, TEXTO, 1)
    _barra(imagem, x + 250, y + 16, 180, 8, taxa, VERDE if taxa >= 0.60 else AMBAR)
    for rotulo, foto, px in (
        ("REF", match.get("referencia"), x),
        ("AGORA", match.get("atual"), x + 180),
    ):
        _texto(imagem, rotulo, px, y + 40, 0.36, DIM, 1)
        thumb = _miniatura(foto, 160, 92)
        if not _colar(imagem, thumb, px, y + 48):
            _texto(imagem, "sem foto", px, y + 80, 0.4, DIM, 1)
    legenda = f"{match.get('id') or ''}  {match.get('nome') or ''}".strip()
    _texto(imagem, legenda[:40], x, y + 162, 0.46, TEXTO, 1)


def _linha_interesse(imagem, x, y, item):
    cor = (210, 90, 230) if item.get("tipo") == "FACE" else CIANO
    _texto(imagem, str(item.get("tipo") or "")[:5], x, y, 0.36, cor, 1)
    _texto(imagem, str(item.get("quando") or "")[5:16], x + 58, y, 0.34, DIM, 1)
    _texto(imagem, str(item.get("id") or "")[:12], x + 150, y, 0.38, TEXTO, 1)
    taxa = float(item.get("taxa") or 0)
    _texto(imagem, f"{item.get('rotulo') or 'SIM'} {taxa:.2f}", x + 280, y, 0.36, TEXTO, 1)
    _barra(imagem, x + 380, y - 10, 70, 8, taxa, VERDE if taxa >= 0.60 else AMBAR)
    _texto(imagem, str(item.get("nome") or item.get("veiculo") or "")[:16], x + 460, y, 0.34, DIM, 1)
    _colar(imagem, _miniatura(item.get("atual"), 52, 28), x + 575, y - 16)


def _miniatura(imagem, largura, altura):
    if imagem is None or getattr(imagem, "size", 0) == 0:
        return None
    return cv2.resize(imagem, (largura, altura), interpolation=cv2.INTER_AREA)


def _colar(imagem, thumb, x, y):
    if thumb is None:
        return False
    altura, largura = imagem.shape[:2]
    h, w = thumb.shape[:2]
    if x < 0 or y < 0 or x + w > largura or y + h > altura:
        return False
    imagem[y:y + h, x:x + w] = thumb
    return True


def _bloco(imagem, x, y, largura, texto, limite=22):
    for linha in _quebrar(texto, largura, 0.42)[:limite]:
        _texto(imagem, linha, x, y, 0.45, TEXTO, 1)
        y += 22


def _donut(imagem, cx, cy, raio, fatias):
    """Fatias preenchidas. O traço grosso fazia um status raro parecer grande demais."""
    total = sum(valor for valor, _ in fatias)
    if total <= 0:
        cv2.circle(imagem, (cx, cy), raio, (50, 50, 50), -1, cv2.LINE_AA)
        cv2.circle(imagem, (cx, cy), int(raio * 0.58), CARTAO, -1, cv2.LINE_AA)
        return
    angulo = -90.0
    for valor, cor in fatias:
        if valor <= 0:
            continue
        passo = 360.0 * valor / total
        cv2.ellipse(
            imagem, (cx, cy), (raio, raio), 0, angulo, angulo + passo, cor, -1, cv2.LINE_AA,
        )
        angulo += passo
    cv2.circle(imagem, (cx, cy), int(raio * 0.58), CARTAO, -1, cv2.LINE_AA)


def aplicar_pulso(imagem):
    """LEDs que correm e uma luz que pisca, para a tela não parecer parada."""
    agora = time.time()
    fase = int(agora * 4) % 5
    aceso = int(agora * 2) % 2 == 0
    largura = imagem.shape[1]
    for indice in range(5):
        cor = (80, 230, 110) if indice == fase else (0, 45, 18)
        cv2.circle(imagem, (largura - 118 + indice * 14, 16), 4, cor, -1, cv2.LINE_AA)
    cv2.circle(imagem, (largura - 22, 16), 6, (90, 255, 130) if aceso else (0, 55, 18), -1, cv2.LINE_AA)
    return imagem


def _grafico(imagem, x, y, largura, altura, series, rotulos, passo=1, marcar=False):
    cv2.rectangle(imagem, (x, y), (x + largura, y + altura), (28, 28, 28), -1)
    maior = 1
    for _, valores, _ in series:
        if valores:
            maior = max(maior, max(valores))
    if marcar:
        for fracao in (0.0, 0.5, 1.0):
            py = y + altura - 8 - int((altura - 20) * fracao)
            for px in range(x + 4, x + largura - 4, 10):
                cv2.line(imagem, (px, py), (min(px + 4, x + largura - 4), py), (70, 70, 70), 1)
        _texto(imagem, str(maior), x + 4, y + 14, 0.32, DIM, 1)
    if len(rotulos) > 1:
        for indice, rotulo in enumerate(rotulos):
            if indice % passo:
                continue
            px = x + int(indice * (largura - 8) / (len(rotulos) - 1))
            _texto(imagem, str(rotulo)[:5], px - 8, y + altura + 16, 0.32, DIM, 1)
    for _, valores, cor in series:
        if not valores:
            continue
        pontos = []
        ultimo = max(len(valores) - 1, 1)
        for indice, valor in enumerate(valores):
            px = x + int(indice * (largura - 8) / ultimo)
            py = y + altura - 8 - int((altura - 20) * valor / maior)
            pontos.append((px, py))
        if len(pontos) >= 2:
            cv2.polylines(imagem, [np.array(pontos, dtype=np.int32)], False, cor, 2, cv2.LINE_AA)
        if marcar and pontos:
            indice = max(range(len(valores)), key=lambda i: valores[i])
            if valores[indice] > 0:
                _texto(imagem, str(valores[indice]), pontos[indice][0] - 8, pontos[indice][1] - 6, 0.32, cor, 1)


def desenhar_mapas(pacote):
    imagem = _base()
    _cabecalho(imagem, "MAPAS", pacote)
    periodo = pacote.get("modo_periodo") or "dia"
    desenho = pacote.get("modo_desenho") or "pontos"
    rotulos = (("dia", "D DIA"), ("semana", "S SEMANA"), ("mes", "M MES"))
    x = 16
    for chave, texto in rotulos:
        cor = VERDE if chave == periodo else DIM
        _texto(imagem, texto, x, 78, 0.46, cor, 1)
        x += 150
    _texto(imagem, "P PONTOS", 520, 78, 0.46, VERDE if desenho == "pontos" else DIM, 1)
    _texto(imagem, "C CALOR", 680, 78, 0.46, VERDE if desenho == "calor" else DIM, 1)
    _texto(
        imagem,
        f"{pacote.get('pontos_periodo', 0)} ocorrencias no periodo",
        860, 78, 0.4, TEXTO, 1,
    )

    _cartao(imagem, 12, 96, 900, 560, "")
    mapa = pacote.get("mapa_painel")
    if mapa is not None and getattr(mapa, "size", 0):
        thumb = cv2.resize(mapa, (876, 520), interpolation=cv2.INTER_AREA)
        _colar(imagem, thumb, 24, 118)
    else:
        _texto(imagem, "sem latitude e longitude neste periodo", 40, 360, 0.5, DIM, 1)
        _texto(imagem, "o mapa usa as ocorrencias do aplicativo", 40, 390, 0.42, DIM, 1)

    _cartao(imagem, 924, 96, 264, 560, "LEGENDA POR TIPO")
    y = 140
    legenda = pacote.get("legenda_painel") or []
    if not legenda:
        _texto(imagem, "nenhum ponto", 940, y, 0.4, DIM, 1)
    for item in legenda[:12]:
        cv2.circle(imagem, (948, y - 4), 6, item.get("cor") or AZUL, -1, cv2.LINE_AA)
        _texto(imagem, str(item.get("tipo") or "")[:16], 964, y, 0.38, TEXTO, 1)
        _texto(imagem, str(item.get("quantidade") or 0), 1128, y, 0.38, DIM, 1)
        y += 28
    if desenho == "calor":
        _texto(imagem, "CALOR", 940, 620, 0.4, AMBAR, 1)
        for indice, cor in enumerate(((255, 40, 20), (40, 220, 220), (20, 40, 255))):
            cv2.circle(imagem, (940 + indice * 28, 644), 6, cor, -1, cv2.LINE_AA)
        _texto(imagem, "frio        quente", 940, 668, 0.34, DIM, 1)
    _rodape(imagem)
    return imagem


def desenhar_monitor(chave, pacote):
    if chave == "1":
        return desenhar_fluxo(pacote)
    if chave == "2":
        return desenhar_comportamento(pacote)
    if chave == "4":
        return desenhar_mapas(pacote)
    return desenhar_leitura(pacote)


def _colunas(linha):
    separador = ";" if ";" in linha else ","
    return next(csv.reader([linha], delimiter=separador))


def _linhas_novas(caminho, cursor):
    if not os.path.exists(caminho):
        return []
    tamanho = os.path.getsize(caminho)
    if tamanho < cursor["pos"]:
        cursor["pos"] = 0
        cursor["sobra"] = ""
        cursor["pulou_cabeca"] = False
    if tamanho == cursor["pos"]:
        return []
    with open(caminho, "rb") as arquivo:
        arquivo.seek(cursor["pos"])
        bloco = arquivo.read()
        cursor["pos"] = arquivo.tell()
    codificacao = "utf-8-sig" if cursor["pos"] == len(bloco) else "utf-8"
    texto = cursor["sobra"] + bloco.decode(codificacao, errors="replace")
    partes = texto.splitlines(keepends=True)
    if partes and not partes[-1].endswith(("\n", "\r")):
        cursor["sobra"] = partes.pop()
    else:
        cursor["sobra"] = ""
    linhas = [parte.strip("\r\n") for parte in partes if parte.strip()]
    if not cursor["pulou_cabeca"]:
        if not linhas:
            return []
        cursor["pulou_cabeca"] = True
        linhas = linhas[1:]
    return linhas


def _taxa(valor):
    texto = str(valor or "").strip()
    if texto.lower() in ("", "none"):
        return None
    try:
        numero = float(texto.replace(",", "."))
    except ValueError:
        return None
    if numero > 1:
        numero /= 100.0
    return max(0.0, min(1.0, numero))


_CACHE_THUMB = {}


def _thumb(caminho, largura=96, altura=54):
    if not caminho or not os.path.exists(caminho):
        return None
    try:
        marca = os.path.getmtime(caminho)
    except OSError:
        return None
    chave = (str(caminho), marca, largura, altura)
    pronto = _CACHE_THUMB.get(chave)
    if pronto is not None:
        return pronto
    imagem = cv2.imread(str(caminho))
    if imagem is None or imagem.size == 0:
        return None
    thumb = cv2.resize(imagem, (largura, altura), interpolation=cv2.INTER_AREA)
    if len(_CACHE_THUMB) > 48:
        _CACHE_THUMB.clear()
    _CACHE_THUMB[chave] = thumb
    return thumb


def _cursor():
    return {"pos": 0, "sobra": "", "pulou_cabeca": False}


def _numero(valor):
    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _aviso_ocorrencia(item, origem):
    return {
        "quando": f"{item.get('data') or ''} {item.get('hora') or ''}".strip(),
        "titulo": item.get("natureza") or item.get("titulo") or "Ocorrencia",
        "lugar": item.get("endereco") or item.get("lugar") or "",
        "origem": origem,
        "detalhe": str(item.get("descricao") or item.get("resumo") or "")[:80],
    }


def _ponto_ocorrencia(item, tipo):
    lat = _numero(item.get("latitude"))
    lon = _numero(item.get("longitude"))
    if lat is None or lon is None:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    if abs(lat) < 0.0001 and abs(lon) < 0.0001:
        return None
    data = str(item.get("data") or item.get("quando") or "")[:10]
    return {"lat": lat, "lon": lon, "tipo": str(tipo or "Ocorrencia"), "data": data}


def _dia(texto):
    try:
        return datetime.strptime(str(texto)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _risco(nome, nivel):
    chave = _limpo(nome).lower()
    mapa = {
        "informativo": "Informativo",
        "atencao": "Atencao",
        "prioritario": "Prioritario",
        "critico": "Critico",
    }
    if chave in mapa:
        return mapa[chave]
    try:
        indice = int(float(nivel or 1))
    except ValueError:
        indice = 1
    return {1: "Informativo", 2: "Atencao", 3: "Prioritario", 4: "Critico"}.get(indice, "Informativo")


def _faixa(categoria, nivel):
    if categoria == "Interacao":
        return "Interacao"
    try:
        alto = int(float(nivel or 1)) >= 2
    except ValueError:
        alto = False
    if categoria == "Audio" or alto:
        return "Alerta"
    return "Comportamento"


class Acervo:
    """Lê os CSV em segundo plano e só guarda os totais dos últimos dias."""

    def __init__(self):
        self._trava = threading.Lock()
        self._parar = False
        self._fio = None
        self.pronto = False
        self._fluxo = _cursor()
        self._ocorrencias = _cursor()
        self._faces = _cursor()
        self._placas = _cursor()
        self._alertas = _cursor()
        self._insights = _cursor()
        self._mtime_leitura = None
        self._mtime_app = None
        self._interesse_em = 0.0
        self._faces_interesse = {}
        self._placas_interesse = {}
        self._app_remoto_em = 0.0
        self._app_buscando = False
        self.quer_leitura = False
        self.quer_mapas = False
        self.modo_periodo = "dia"
        self.modo_desenho = "pontos"
        self.cat = {}
        self.classe = {}
        self.hora = {}
        self.risco = {}
        self.faixa = {}
        self.tipo = {}
        self.ids = set()
        self.resumo = ""
        self.assessoramento = ""
        self.leitura_quando = ""
        self.insights_relatorio = []
        self.app = []
        self.app_remoto = []
        self.pontos_locais = []
        self.pontos_remotos = []
        self.mapa = None
        self.legenda_mapa = []
        self._mapa_chave = None
        self.mapa_painel = None
        self.legenda_painel = []
        self._mapa_painel_chave = None
        self.pontos_periodo = 0
        self.mapa_versao = 0
        self.interesse = deque(maxlen=8)
        self.enviados = deque(maxlen=8)
        self.insights = deque(maxlen=8)
        self.titulo = "MONITORAMENTO"

    def iniciar(self):
        self._titulo()
        self._fio = threading.Thread(target=self._loop, name="monitores", daemon=True)
        self._fio.start()

    def parar(self):
        self._parar = True

    def _titulo(self):
        try:
            from cadastro import cliente_ativo
            cliente = cliente_ativo() or {}
            nome = str(cliente.get("nome") or "").strip()
            if nome:
                self.titulo = f"MONITORAMENTO {nome}".upper()
        except Exception:
            pass

    def _loop(self):
        while not self._parar:
            try:
                self._consumir_fluxo()
                self._consumir_ocorrencias()
                self._consumir_interesse()
                self._consumir_alertas()
                self._consumir_insights()
                self._ler_leitura()
                self._ler_app()
                self._agendar_app_remoto()
                if self.quer_leitura or self.quer_mapas:
                    self._atualizar_mapa()
                self.pronto = True
            except Exception:
                pass
            time.sleep(0.4)

    def _consumir_fluxo(self):
        linhas = _linhas_novas("historico_analitico.csv", self._fluxo)
        if not linhas:
            return
        limite = date.today() - timedelta(days=14)
        registros = []
        for linha in linhas:
            colunas = _colunas(linha)
            if len(colunas) < 5:
                continue
            dia = _dia(colunas[0])
            if dia is None or dia < limite:
                continue
            try:
                hora = int((colunas[1] or "0")[:2])
            except ValueError:
                hora = 0
            registros.append((
                dia.isoformat(),
                colunas[2] or "CAMERA",
                colunas[3] if colunas[3] in CATEGORIAS else "Objeto",
                colunas[4] or "objeto",
                max(0, min(23, hora)),
            ))
        with self._trava:
            for dia, camera, categoria, classe, hora in registros:
                chave_cat = (dia, camera, categoria)
                self.cat[chave_cat] = self.cat.get(chave_cat, 0) + 1
                self.classe[(dia, classe)] = self.classe.get((dia, classe), 0) + 1
                chave_hora = (dia, categoria, hora)
                self.hora[chave_hora] = self.hora.get(chave_hora, 0) + 1

    def _consumir_ocorrencias(self):
        linhas = _linhas_novas("historico_ocorrencias.csv", self._ocorrencias)
        if not linhas:
            return
        limite = date.today() - timedelta(days=14)
        registros = []
        for linha in linhas:
            colunas = _colunas(linha)
            if len(colunas) < 5:
                continue
            dia = _dia(colunas[0])
            if dia is None or dia < limite:
                continue
            registros.append((
                dia.isoformat(),
                colunas[2] or "CAMERA",
                colunas[3] or "",
                colunas[4] or "",
                colunas[5] if len(colunas) > 5 else "",
                _risco(colunas[14] if len(colunas) > 14 else "", colunas[15] if len(colunas) > 15 else ""),
                _faixa(colunas[3] or "", colunas[15] if len(colunas) > 15 else ""),
            ))
        with self._trava:
            for dia, camera, _categoria, classe, ident, risco, faixa in registros:
                self.risco[(dia, risco)] = self.risco.get((dia, risco), 0) + 1
                self.faixa[(dia, faixa, camera)] = self.faixa.get((dia, faixa, camera), 0) + 1
                self.tipo[(dia, classe, camera)] = self.tipo.get((dia, classe, camera), 0) + 1
                if ident:
                    self.ids.add((dia, camera, classe, ident))

    def _atualizar_interesse(self):
        if time.time() - self._interesse_em < 15 and self._interesse_em:
            return
        try:
            from cadastro import interesse_ativo
            interesse = interesse_ativo() or {}
        except Exception:
            interesse = {}
        self._faces_interesse = {
            str(pessoa.get("face_id") or ""): str(pessoa.get("nome") or "")
            for pessoa in interesse.get("pessoas") or []
            if pessoa.get("face_id")
        }
        self._placas_interesse = {
            str(veiculo.get("placa") or "").upper(): str(veiculo.get("nome") or "")
            for veiculo in interesse.get("veiculos") or []
            if veiculo.get("placa")
        }
        self._interesse_em = time.time()

    def _consumir_interesse(self):
        self._atualizar_interesse()
        novos = []
        for linha in _linhas_novas("historico_faces.csv", self._faces):
            colunas = _colunas(linha)
            if len(colunas) < 11:
                continue
            ident = str(colunas[3] or "")
            if ident not in self._faces_interesse:
                continue
            taxa = _taxa(colunas[7]) or 0.0
            novos.append({
                "quando": f"{colunas[0]} {colunas[1]}",
                "tipo": "FACE",
                "id": ident,
                "nome": self._faces_interesse.get(ident, ""),
                "camera": colunas[2],
                "taxa": taxa,
                "rotulo": "SIM",
                "veiculo": "",
                "foto": colunas[9],
                "ref": colunas[10],
            })
        for linha in _linhas_novas("historico_placas.csv", self._placas):
            colunas = _colunas(linha)
            if len(colunas) < 12:
                continue
            ident = str(colunas[4] or "").upper()
            if ident not in self._placas_interesse:
                continue
            sim = _taxa(colunas[12]) if len(colunas) > 12 else None
            if sim is None:
                taxa, rotulo = _taxa(colunas[9]) or 0.0, "LEIT"
            else:
                taxa, rotulo = sim, "SIM"
            novos.append({
                "quando": f"{colunas[0]} {colunas[1]}",
                "tipo": "PLACA",
                "id": ident,
                "nome": self._placas_interesse.get(ident, ""),
                "camera": colunas[2],
                "taxa": taxa,
                "rotulo": rotulo,
                "veiculo": colunas[8],
                "foto": colunas[10],
                "ref": colunas[11],
            })
        if not novos:
            return
        novos.sort(key=lambda item: item.get("quando") or "")
        for item in novos[-8:]:
            item["atual"] = _thumb(item.pop("foto", ""))
            item["referencia"] = _thumb(item.pop("ref", ""))
        with self._trava:
            self.interesse.extend(novos[-8:])

    def _consumir_alertas(self):
        novos = []
        for linha in _linhas_novas("historico_alertas_ia.csv", self._alertas):
            colunas = _colunas(linha)
            if len(colunas) < 14:
                continue
            novos.append({
                "quando": f"{colunas[0]} {colunas[1]}",
                "origem": colunas[4],
                "tipo": colunas[5],
                "id": colunas[6],
                "nome": colunas[7],
                "camera": colunas[9],
                "descricao": colunas[13] or colunas[8],
            })
        if novos:
            with self._trava:
                self.enviados.extend(novos)

    def _consumir_insights(self):
        novos = []
        for linha in _linhas_novas("historico_insights.csv", self._insights):
            colunas = _colunas(linha)
            if len(colunas) < 9:
                continue
            novos.append({
                "quando": f"{colunas[0]} {colunas[1]}",
                "tipo": colunas[5],
                "nome": colunas[6],
                "descricao": colunas[8] or colunas[6],
            })
        if novos:
            with self._trava:
                self.insights.extend(novos)

    def _ler_leitura(self):
        caminho = os.path.join("relatorios", "historico_relatorios.json")
        if not os.path.exists(caminho):
            return
        marca = os.path.getmtime(caminho)
        if marca == self._mtime_leitura:
            return
        self._mtime_leitura = marca
        try:
            with open(caminho, encoding="utf-8") as arquivo:
                bruto = json.loads(arquivo.read())
        except (OSError, json.JSONDecodeError):
            return
        registros = bruto if isinstance(bruto, list) else list((bruto or {}).get("registros") or [])
        if not registros:
            return
        ultimo = registros[-1]
        textos = []
        for item in (ultimo.get("leitura") or {}).get("insights") or []:
            if isinstance(item, str) and item.strip():
                textos.append(item.strip())
            elif isinstance(item, dict) and (item.get("descricao") or item.get("texto")):
                textos.append(str(item.get("descricao") or item.get("texto")))
        with self._trava:
            self.resumo = str(ultimo.get("resumo") or "")
            self.assessoramento = str(ultimo.get("assessoramento") or "")
            self.leitura_quando = str(ultimo.get("gerado_em") or ultimo.get("fim") or "")
            self.insights_relatorio = textos[:6]

    def _ler_app(self):
        caminho = "ocorrencias_informadas.json"
        if not os.path.exists(caminho):
            return
        marca = os.path.getmtime(caminho)
        if marca == self._mtime_app:
            return
        self._mtime_app = marca
        try:
            with open(caminho, encoding="utf-8") as arquivo:
                bruto = json.loads(arquivo.read())
        except (OSError, json.JSONDecodeError):
            return
        itens = bruto.get("ocorrencias") if isinstance(bruto, dict) else bruto
        if not isinstance(itens, list):
            return
        itens = sorted(itens, key=lambda item: (item.get("data") or "", item.get("hora") or ""))
        avisos = []
        pontos = []
        for item in itens:
            aviso = _aviso_ocorrencia(item, "Informada")
            avisos.append(aviso)
            ponto = _ponto_ocorrencia(item, aviso["titulo"])
            if ponto:
                pontos.append(ponto)
        with self._trava:
            self.app = list(reversed(avisos[-4:]))
            self.pontos_locais = pontos

    def _agendar_app_remoto(self):
        if not (self.quer_leitura or self.quer_mapas) or self._app_buscando:
            return
        if time.time() - self._app_remoto_em < INTERVALO_PAINEL_SEG:
            return
        self._app_remoto_em = time.time()
        self._app_buscando = True
        threading.Thread(target=self._buscar_app_remoto, name="app-leitura", daemon=True).start()

    def _buscar_app_remoto(self):
        try:
            from dataverse import ClienteDataverse
            cliente = ClienteDataverse()
            if not cliente.configurado():
                return
            inicio = (date.today() - timedelta(days=14)).isoformat()
            linhas = cliente.listar(inicio=inicio)
        except Exception:
            return
        finally:
            self._app_buscando = False
        avisos = []
        pontos = []
        for item in linhas or []:
            aviso = _aviso_ocorrencia(item, "App")
            avisos.append(aviso)
            ponto = _ponto_ocorrencia(item, aviso["titulo"])
            if ponto:
                pontos.append(ponto)
        with self._trava:
            self.app_remoto = list(reversed(avisos[-4:]))
            self.pontos_remotos = pontos

    def _filtrar_periodo(self, pontos, periodo):
        hoje = date.today()
        if periodo == "semana":
            inicio = (hoje - timedelta(days=6)).isoformat()
        elif periodo == "mes":
            inicio = (hoje - timedelta(days=29)).isoformat()
        else:
            inicio = hoje.isoformat()
            return [ponto for ponto in pontos if (ponto.get("data") or "")[:10] == inicio]
        return [ponto for ponto in pontos if (ponto.get("data") or "")[:10] >= inicio]

    def _atualizar_mapa(self):
        with self._trava:
            pontos = list(self.pontos_locais) + list(self.pontos_remotos)
            periodo = self.modo_periodo
            desenho = self.modo_desenho
        hoje = self._filtrar_periodo(pontos, "dia")
        chave = tuple(sorted(
            (round(ponto["lat"], 5), round(ponto["lon"], 5), ponto["tipo"], ponto.get("data") or "")
            for ponto in hoje
        ))
        if chave != self._mapa_chave or self.mapa is None:
            imagem, legenda = compor_mapa(hoje, 736, 180)
            with self._trava:
                self.mapa = imagem
                self.legenda_mapa = legenda
                self._mapa_chave = chave
                self.mapa_versao += 1
        if not self.quer_mapas:
            return
        selecionados = self._filtrar_periodo(pontos, periodo)
        chave_painel = (periodo, desenho, tuple(sorted(
            (round(ponto["lat"], 5), round(ponto["lon"], 5), ponto["tipo"], ponto.get("data") or "")
            for ponto in selecionados
        )))
        if chave_painel == self._mapa_painel_chave and self.mapa_painel is not None:
            return
        if desenho == "calor":
            imagem, legenda = compor_calor(selecionados, 876, 520)
        else:
            imagem, legenda = compor_mapa(selecionados, 876, 520)
        with self._trava:
            self.mapa_painel = imagem
            self.legenda_painel = legenda
            self._mapa_painel_chave = chave_painel
            self.pontos_periodo = len(selecionados)
            self.mapa_versao += 1

    def pacote(self, cameras_online, matches=None):
        hoje = date.today().isoformat()
        dias = [(date.today() - timedelta(days=offset)).isoformat() for offset in range(7, -1, -1)]
        with self._trava:
            categorias = {nome: 0 for nome in CATEGORIAS}
            por_camera = {}
            for (dia, camera, categoria), valor in self.cat.items():
                if dia != hoje:
                    continue
                categorias[categoria] = categorias.get(categoria, 0) + valor
                por_camera[camera] = por_camera.get(camera, 0) + valor
            classes = {}
            for (dia, classe), valor in self.classe.items():
                if dia == hoje:
                    classes[classe] = classes.get(classe, 0) + valor
            horas = {nome: [0] * 24 for nome in CATEGORIAS}
            for (dia, categoria, hora), valor in self.hora.items():
                if dia == hoje and categoria in horas and 0 <= hora <= 23:
                    horas[categoria][hora] = valor
            riscos = {nome: 0 for nome in RISCOS}
            for (dia, risco), valor in self.risco.items():
                if dia == hoje and risco in riscos:
                    riscos[risco] += valor
            nomes = []
            vistos = set()
            for camera in cameras_online or []:
                nome = camera.get("nome")
                if nome and nome not in vistos:
                    nomes.append(nome)
                    vistos.add(nome)
            for camera in por_camera:
                if camera not in vistos:
                    nomes.append(camera)
                    vistos.add(camera)
            faixas = {nome: {} for nome in FAIXAS}
            for (dia, faixa, camera), valor in self.faixa.items():
                if dia == hoje and faixa in faixas:
                    faixas[faixa][camera] = faixas[faixa].get(camera, 0) + valor
            tipos_mapa = {}
            for (dia, classe, camera), valor in self.tipo.items():
                if dia != hoje or not classe:
                    continue
                item = tipos_mapa.setdefault(classe, {})
                item[camera] = item.get(camera, 0) + valor
            curvas_mapa = {}
            for (dia, classe, _camera), valor in self.tipo.items():
                if dia in dias and classe:
                    linha = curvas_mapa.setdefault(classe, {nome: 0 for nome in dias})
                    linha[dia] = linha.get(dia, 0) + valor
            ids = sum(1 for dia, *_resto in self.ids if dia == hoje)
            resumo = self.resumo
            assessoramento = self.assessoramento
            leitura_quando = self.leitura_quando
            app = [dict(item) for item in self.app]
            app.extend(dict(item) for item in self.app_remoto)
            interesse = list(self.interesse)
            enviados = list(self.enviados)
            insights = list(self.insights)
            vistos = {item.get("descricao") for item in insights}
            for texto in self.insights_relatorio:
                if texto not in vistos:
                    insights.append({
                        "quando": leitura_quando,
                        "tipo": "Relatorio",
                        "nome": "",
                        "descricao": texto,
                    })
            titulo = self.titulo
            pronto = self.pronto
            mapa = self.mapa
            legenda_mapa = list(self.legenda_mapa)
            mapa_painel = self.mapa_painel
            legenda_painel = list(self.legenda_painel)
            modo_periodo = self.modo_periodo
            modo_desenho = self.modo_desenho
            pontos_periodo = self.pontos_periodo
            por_dia = {}
            for (dia, _camera, _categoria), valor in self.cat.items():
                por_dia[dia] = por_dia.get(dia, 0) + valor
            dias_lista = [
                {
                    "rotulo": f"{dia[8:10]}/{dia[5:7]}/{dia[2:4]}",
                    "total": por_dia[dia],
                }
                for dia in sorted(por_dia)[-4:]
            ]
            horas_ativas = []
            for hora in range(24):
                soma = sum(int(horas[nome][hora]) for nome in CATEGORIAS)
                if soma:
                    horas_ativas.append({"rotulo": f"{hora:02d}:00:00", "total": soma})
        vivo = None
        for match in matches or []:
            if match and (vivo is None or float(match.get("ate") or 0) >= float(vivo.get("ate") or 0)):
                vivo = match
        if vivo is None and interesse:
            ultimo = interesse[-1]
            vivo = {
                "tipo": ultimo.get("tipo"),
                "id": ultimo.get("id"),
                "nome": ultimo.get("nome"),
                "camera": ultimo.get("camera"),
                "taxa": ultimo.get("taxa"),
                "rotulo_taxa": ultimo.get("rotulo"),
                "referencia": ultimo.get("referencia"),
                "atual": ultimo.get("atual"),
            }
        app.sort(key=lambda item: item.get("quando") or "")

        cameras = []
        for nome in nomes:
            cameras.append({
                "nome": nome,
                "online": any(item.get("nome") == nome for item in cameras_online or []),
                "itens": por_camera.get(nome, 0),
            })
        tipos = [
            {"classe": classe, "cameras": dict(contagem)}
            for classe, contagem in sorted(
                tipos_mapa.items(), key=lambda item: -sum(item[1].values()),
            )
        ]
        ordenadas = sorted(curvas_mapa.items(), key=lambda item: -sum(item[1].values()))[:6]
        curvas = [(classe, [valores.get(dia, 0) for dia in dias]) for classe, valores in ordenadas]
        return {
            "titulo": titulo,
            "hoje": hoje,
            "relogio": datetime.now().strftime("%H:%M:%S"),
            "pronto": pronto,
            "total": sum(categorias.values()),
            "categorias": categorias,
            "cameras": cameras,
            "classes": sorted(classes.items(), key=lambda item: -item[1])[:8],
            "dias": dias_lista,
            "horas_ativas": horas_ativas[-4:],
            "horas": horas,
            "mapa": mapa,
            "legenda_mapa": legenda_mapa,
            "mapa_painel": mapa_painel,
            "legenda_painel": legenda_painel,
            "modo_periodo": modo_periodo,
            "modo_desenho": modo_desenho,
            "pontos_periodo": pontos_periodo,
            "riscos": riscos,
            "ids": ids,
            "faixas": faixas,
            "tipos": tipos,
            "serie": {
                "rotulos": [dia[8:10] + "/" + dia[5:7] for dia in dias],
                "curvas": curvas,
            },
            "app": list(reversed(app[-5:])),
            "interesse": list(reversed(interesse[-4:])),
            "enviados": list(reversed(enviados[-4:])),
            "insights": list(reversed(insights[-4:])),
            "match": vivo,
            "resumo": resumo,
            "assessoramento": assessoramento,
            "leitura_quando": leitura_quando,
        }
