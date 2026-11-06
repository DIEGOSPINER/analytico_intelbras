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

from mapa import compor_bolhas, compor_calor, compor_mapa

INTERVALO_PAINEL_SEG = 1

JANELAS_PAINEL = {
    "1": "C4ISTAR MONITOR  CONTAGENS",
    "2": "C4ISTAR MONITOR  COMPORTAMENTO",
    "3": "C4ISTAR MONITOR  ALERTAS DE RF E LPR",
    "4": "C4ISTAR MONITOR  MAPAS",
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
CORES_CAMERA = (AZUL, LARANJA, VERDE, CIANO, ROXO, ROSA, AMBAR, VERMELHO)


def _limpo(texto) -> str:
    return str(texto or "").translate(str.maketrans(
        "áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ",
        "aaaaeeioooucAAAAEEIOOOUC",
    ))


def _escala_visivel(escala, espessura=1):
    if escala < 0.8:
        return max(0.62, escala * 1.5), max(espessura, 2)
    return escala, espessura


def _texto(imagem, texto, x, y, escala, cor, espessura=1):
    escala, espessura = _escala_visivel(escala, espessura)
    cv2.putText(
        imagem, _limpo(texto), (int(x), int(y)),
        cv2.FONT_HERSHEY_SIMPLEX, escala, cor, espessura, cv2.LINE_AA,
    )


def _quebrar(texto, largura_px, escala=0.42):
    escala, espessura = _escala_visivel(escala, 1)
    palavras = _limpo(texto).split()
    linhas = []
    atual = ""
    for palavra in palavras:
        teste = f"{atual} {palavra}".strip()
        largura, _ = cv2.getTextSize(teste, cv2.FONT_HERSHEY_SIMPLEX, escala, espessura)[0]
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


def cor_camera(nome, indice=0):
    digitos = "".join(caractere for caractere in str(nome or "") if caractere.isdigit())
    if digitos:
        indice = max(int(digitos) - 1, 0)
    return CORES_CAMERA[indice % len(CORES_CAMERA)]


def _quando(texto):
    bruto = str(texto or "").strip().replace("T", " ")
    if len(bruto) >= 10 and bruto[4] == "-" and bruto[7] == "-":
        data = f"{bruto[8:10]}/{bruto[5:7]}/{bruto[0:4]}"
        hora = bruto[11:16] if len(bruto) >= 16 else ""
        return f"{data} {hora}".strip()
    return bruto


def _linha_relatorio(pacote):
    inicio = _quando(pacote.get("leitura_inicio"))[:10]
    fim = _quando(pacote.get("leitura_fim"))[:10]
    gerado = _quando(pacote.get("leitura_quando"))
    if inicio and fim and inicio != fim:
        periodo = f"{inicio} a {fim}"
    else:
        periodo = inicio or fim
    if periodo and gerado:
        return f"Relatorio {periodo}   gerado {gerado}"
    if gerado:
        return f"Relatorio gerado {gerado}"
    return "relatorio do dia ainda nao fechou"


def _pontos_geo(pacote, contagens):
    pontos = []
    for indice, local in enumerate(pacote.get("locais") or []):
        if local.get("latitude") is None or local.get("longitude") is None:
            continue
        nome = local.get("nome") or ""
        pontos.append({
            "lat": local["latitude"],
            "lon": local["longitude"],
            "nome": nome,
            "rua": local.get("rua") or "",
            "valor": int((contagens or {}).get(nome, 0) or 0),
            "cor": cor_camera(nome, indice),
        })
    return pontos


def _desenhar_mapa_cameras(imagem, x, y, largura, altura, pontos, legenda=True):
    if not pontos:
        _texto(imagem, "cameras sem latitude", x, y + 24, 0.38, DIM, 1)
        return
    reserva = (18 * min(len(pontos), 3) + 8) if legenda else 0
    mapa_h = max(72, altura - reserva)
    try:
        mapa = compor_bolhas(pontos, largura, mapa_h)
    except Exception:
        _texto(imagem, "mapa de cameras indisponivel", x, y + 24, 0.38, DIM, 1)
        return
    if not _colar(imagem, mapa, x, y):
        return
    if not legenda:
        return
    ly = y + mapa_h + 16
    for ponto in pontos[:3]:
        cv2.circle(imagem, (x + 8, ly - 4), 5, ponto["cor"], -1, cv2.LINE_AA)
        rotulo = ponto["rua"] or ponto["nome"]
        _texto(imagem, rotulo[:24], x + 18, ly, 0.3, ponto["cor"], 1)
        _texto(imagem, str(ponto["valor"]), x + largura - 40, ly, 0.32, TEXTO, 1)
        ly += 18


def _cabecalho(imagem, titulo, pacote):
    _texto(imagem, "C4ISTAR MONITOR", 16, 28, 0.62, TEXTO, 1)
    _texto(imagem, titulo, 16, 52, 0.48, AZUL_CLARO, 1)
    _texto(
        imagem,
        f"HOJE {pacote.get('hoje', '')}   {pacote.get('relogio', '')}",
        LARGURA - 340, 28, 0.42, DIM, 1,
    )
    if not pacote.get("pronto"):
        _texto(imagem, "LENDO HISTORICO", LARGURA - 340, 52, 0.42, AMBAR, 1)
    else:
        _texto(imagem, "ao vivo", LARGURA - 340, 52, 0.4, DIM, 1)


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
    _cabecalho(imagem, "Contagens", pacote)
    categorias = pacote.get("categorias") or {}
    total = pacote.get("total") or 0
    cameras = pacote.get("cameras") or []

    _cartao(imagem, 12, 68, 360, 300, "ACESSOS POR CAMERA")
    _texto(imagem, "Camera", 28, 104, 0.36, DIM, 1)
    _texto(imagem, "Total", 300, 104, 0.36, DIM, 1)
    y = 128
    if not cameras:
        _texto(imagem, "nenhuma camera no dia", 28, y, 0.42, DIM, 1)
    for camera in cameras[:4]:
        cor = cor_camera(camera.get("nome"))
        cv2.circle(imagem, (32, y - 4), 5, cor, -1, cv2.LINE_AA)
        _texto(imagem, str(camera.get("nome") or "")[:16], 46, y, 0.42, TEXTO, 1)
        _texto(imagem, str(camera.get("itens") or 0), 300, y, 0.46, AZUL_CLARO, 1)
        rua = str(camera.get("rua") or "")
        if rua:
            _texto(imagem, rua[:28], 46, y + 16, 0.34, DIM, 1)
            y += 16
        x = 46
        y += 18
        for nome_cat, sigla in (("Veiculo", "Vei"), ("Pessoa", "Pes"), ("Objeto", "Obj"), ("Animal", "Ani")):
            valor = int((camera.get("categorias") or {}).get(nome_cat, 0))
            _texto(imagem, f"{sigla} {valor}", x, y, 0.34, COR_CATEGORIA[nome_cat], 1)
            x += 76
        y += 28

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

    _cartao(imagem, 12, 380, 760, 286, "HISTORICO")
    _texto(imagem, "Categoria", 28, 412, 0.36, DIM, 1)
    x = 120
    for nome in CATEGORIAS:
        cv2.circle(imagem, (x, 407), 4, COR_CATEGORIA[nome], -1, cv2.LINE_AA)
        _texto(imagem, nome, x + 10, 412, 0.36, COR_CATEGORIA[nome], 1)
        x += 120
    horas = pacote.get("horas") or {}
    series = [(nome, horas.get(nome) or [0] * 24, COR_CATEGORIA[nome]) for nome in CATEGORIAS]
    _grafico(
        imagem, 36, 428, 700, 190, series,
        [f"{hora:02d}:00" for hora in range(24)],
        passo=4, marcar=True,
    )
    _cartao(imagem, 784, 380, 402, 286, "MAPA DAS CAMERAS")
    _desenhar_mapa_cameras(
        imagem, 800, 412, 370, 240,
        _pontos_geo(pacote, {item.get("nome"): item.get("itens") or 0 for item in cameras}),
    )
    _rodape(imagem)
    return imagem


def desenhar_comportamento(pacote):
    imagem = _base()
    _cabecalho(imagem, "Comportamento", pacote)
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
        for camera in cameras[:3]:
            valor = int((faixas.get(nome) or {}).get(camera, 0))
            largura = int(180 * valor / maior)
            cor = cor_camera(camera)
            if largura > 0:
                cv2.rectangle(imagem, (inicio, y - 12), (inicio + largura, y), cor, -1)
                inicio += largura
        y += 42
    x = 438
    for camera in cameras[:3]:
        _texto(imagem, str(camera)[:12], x, 352, 0.34, cor_camera(camera), 1)
        x += 110

    _cartao(imagem, 796, 68, 390, 300, "TIPO DE COMPORTAMENTO")
    tipos = pacote.get("tipos") or []
    maior_tipo = 1
    for item in tipos[:6]:
        maior_tipo = max(maior_tipo, sum(int(v) for v in (item.get("cameras") or {}).values()))
    y = 128
    for item in tipos[:6]:
        _texto(imagem, str(item.get("classe") or "")[:16], 810, y, 0.36, TEXTO, 1)
        inicio = 960
        total_barra = 0
        for camera in cameras[:3]:
            valor = int((item.get("cameras") or {}).get(camera, 0))
            largura = int(150 * valor / maior_tipo)
            total_barra += valor
            if largura > 0:
                cv2.rectangle(imagem, (inicio, y - 12), (inicio + largura, y), cor_camera(camera), -1)
                inicio += largura
        centro = 960 + max(inicio - 960, 36) // 2
        _texto(imagem, str(total_barra), centro - 8, y - 24, 0.36, TEXTO, 1)
        y += 36

    _cartao(imagem, 12, 380, 500, 286, "PRIORIDADE AO LONGO DOS DIAS")
    serie = pacote.get("serie") or {}
    rotulos = serie.get("rotulos") or []
    curvas = []
    for indice, (nome, valores) in enumerate((serie.get("curvas") or [])[:6]):
        curvas.append((nome, valores, CORES_SERIE[indice % len(CORES_SERIE)]))
    _grafico(imagem, 28, 436, 468, 184, curvas, rotulos, passo=1)
    x = 28
    for nome, _, cor in curvas[:3]:
        _texto(imagem, str(nome)[:12], x, 418, 0.32, cor, 1)
        x += 150

    _cartao(imagem, 524, 380, 300, 286, "MAPA DAS CAMERAS")
    _desenhar_mapa_cameras(
        imagem, 536, 412, 276, 240,
        _pontos_geo(pacote, pacote.get("contagem_comportamento") or {}),
    )

    _cartao(imagem, 836, 380, 352, 286, "APP")
    avisos = pacote.get("app") or []
    if not avisos:
        _texto(imagem, "sem ocorrencia informada", 852, 430, 0.4, DIM, 1)
    y = 424
    for aviso in avisos[:4]:
        _texto(imagem, str(aviso.get("quando") or ""), 852, y, 0.34, AZUL_CLARO, 1)
        _texto(imagem, str(aviso.get("titulo") or "")[:28], 852, y + 18, 0.38, TEXTO, 1)
        _texto(imagem, str(aviso.get("lugar") or "")[:28], 852, y + 36, 0.34, DIM, 1)
        y += 58
    _rodape(imagem)
    return imagem


def desenhar_leitura(pacote):
    altura = 860
    imagem = np.zeros((altura, LARGURA, 3), dtype=np.uint8)
    imagem[:] = FUNDO
    _cabecalho(imagem, "Alertas de RF e LPR", pacote)
    _cartao(imagem, 12, 68, 560, 200, "ALERTAS DE RF E LPR")
    _match_grande(imagem, 28, 96, pacote.get("match"))

    _cartao(imagem, 584, 68, 604, 200, "ULTIMOS ALERTAS DE RF E LPR")
    interesses = pacote.get("interesse") or []
    if not interesses:
        _texto(imagem, "nenhum rosto ou placa de interesse ainda", 600, 120, 0.4, DIM, 1)
    for indice, item in enumerate(interesses[:4]):
        _linha_interesse(imagem, 600, 108 + indice * 38, item)

    _cartao(imagem, 12, 278, 1176, 250, "OCORRENCIAS")
    _texto(imagem, _linha_relatorio(pacote), 620, 302, 0.36, AZUL_CLARO, 1)
    _texto(imagem, "MEMORIAS DE RUA", 28, 332, 0.38, AMBAR, 1)
    memorias = pacote.get("memorias") or []
    if not memorias:
        _texto(imagem, "sem memoria registrada", 28, 360, 0.38, DIM, 1)
    y = 358
    for memoria in memorias[:3]:
        _texto(imagem, _quando(memoria.get("quando"))[:16], 28, y, 0.34, AZUL_CLARO, 1)
        for linha in _quebrar(memoria.get("texto") or "", 360, 0.38)[:2]:
            y += 16
            _texto(imagem, linha, 28, y, 0.36, TEXTO, 1)
        y += 22

    _texto(imagem, "ULTIMOS INFORMES", 420, 332, 0.38, AMBAR, 1)
    informes = pacote.get("enviados") or pacote.get("insights") or []
    if not informes:
        _texto(imagem, "nenhum informe enviado", 420, 360, 0.38, DIM, 1)
    y = 360
    for informe in informes[:4]:
        _texto(imagem, _quando(informe.get("quando"))[:16], 420, y, 0.34, AZUL_CLARO, 1)
        _texto(imagem, str(informe.get("descricao") or informe.get("tipo") or "")[:34], 560, y, 0.34, TEXTO, 1)
        y += 40

    _desenhar_mapa_cameras(
        imagem, 900, 328, 270, 180,
        _pontos_geo(pacote, pacote.get("contagem_alertas") or {}),
        legenda=False,
    )

    _cartao(imagem, 12, 540, 384, 280, "RESUMO")
    _bloco(imagem, 28, 598, 352, pacote.get("resumo") or (
        "O relatorio do dia ainda nao tem resumo. "
        "O agente grava este texto no fechamento do dia."
    ), limite=8)
    _cartao(imagem, 408, 540, 384, 280, "ASSESSORAMENTO")
    _bloco(imagem, 424, 598, 352, pacote.get("assessoramento") or (
        "O assessoramento entra no relatorio, "
        "com a conclusao de risco e a orientacao do periodo."
    ), limite=8)
    _cartao(imagem, 804, 540, 384, 280, "APRENDIZADO")
    _bloco(imagem, 820, 598, 352, pacote.get("aprendizado") or (
        "O aprendizado da rua entra quando o relatorio fecha o dia."
    ), limite=8)
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
    _cabecalho(imagem, "Mapas", pacote)
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

    _cartao(imagem, 924, 96, 264, 268, "CAMERAS")
    _desenhar_mapa_cameras(
        imagem, 936, 124, 240, 224,
        _pontos_geo(pacote, {item.get("nome"): item.get("itens") or 0 for item in pacote.get("cameras") or []}),
    )
    _cartao(imagem, 924, 376, 264, 280, "LEGENDA POR TIPO")
    y = 412
    legenda = pacote.get("legenda_painel") or []
    if not legenda:
        _texto(imagem, "nenhum ponto", 940, y, 0.4, DIM, 1)
    for item in legenda[:7]:
        cv2.circle(imagem, (948, y - 4), 6, item.get("cor") or AZUL, -1, cv2.LINE_AA)
        _texto(imagem, str(item.get("tipo") or "")[:14], 964, y, 0.36, TEXTO, 1)
        _texto(imagem, str(item.get("quantidade") or 0), 1128, y, 0.36, DIM, 1)
        y += 26
    if desenho == "calor" and y < 630:
        _texto(imagem, "CALOR", 940, y + 8, 0.36, AMBAR, 1)
        for indice, cor in enumerate(((255, 40, 20), (40, 220, 220), (20, 40, 255))):
            cv2.circle(imagem, (1020 + indice * 22, y + 4), 5, cor, -1, cv2.LINE_AA)
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


def _pegar_numero(origem, chaves):
    if not isinstance(origem, dict):
        return None
    for chave in chaves:
        if origem.get(chave) not in (None, ""):
            numero = _numero(origem.get(chave))
            if numero is not None:
                return numero
    return None


def _coordenada_item(item):
    lat = _pegar_numero(item, ("latitude", "lat", "cr3d0_latitude", "Latitude"))
    lon = _pegar_numero(item, ("longitude", "lon", "lng", "long", "cr3d0_longitude", "Longitude"))
    extra = item.get("extraido") if isinstance(item.get("extraido"), dict) else {}
    if lat is None:
        lat = _pegar_numero(extra, ("latitude", "lat"))
    if lon is None:
        lon = _pegar_numero(extra, ("longitude", "lon", "lng", "long"))
    texto = str(item.get("coordenadas") or item.get("localizacao") or "")
    if (lat is None or lon is None) and "," in texto:
        partes = texto.split(",")
        if len(partes) >= 2:
            lat = lat if lat is not None else _numero(partes[0])
            lon = lon if lon is not None else _numero(partes[1])
    if lat is not None and lon is not None and abs(lat) > 90 and abs(lon) <= 90:
        lat, lon = lon, lat
    elif (
        lat is not None and lon is not None
        and abs(lat) > abs(lon) and abs(lat) > 20
    ):
        lat, lon = lon, lat
    return lat, lon


def _coordenada_camera(item):
    texto = " ".join(
        str(item.get(chave) or "")
        for chave in ("endereco", "lugar", "descricao", "natureza", "titulo")
    ).lower()
    if not texto.strip():
        return None
    try:
        from cadastro import locais_cameras
        locais = locais_cameras()
    except Exception:
        return None
    for local in locais:
        nome = str(local.get("nome") or "").strip().lower()
        if not nome or nome not in texto:
            continue
        if local.get("latitude") is None or local.get("longitude") is None:
            continue
        return float(local["latitude"]), float(local["longitude"])
    return None


def _ponto_ocorrencia(item, tipo):
    lat, lon = _coordenada_item(item)
    aproximado = False
    if lat is None or lon is None:
        camera = _coordenada_camera(item)
        if camera is None:
            return None
        lat, lon = camera
        aproximado = True
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    if abs(lat) < 0.0001 and abs(lon) < 0.0001:
        return None
    data = str(item.get("data") or item.get("quando") or "")[:10]
    return {
        "lat": lat,
        "lon": lon,
        "tipo": str(tipo or "Ocorrencia"),
        "data": data,
        "aproximado": aproximado,
    }


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
        self.hora_faixa = {}
        self.ids = set()
        self.resumo = ""
        self.assessoramento = ""
        self.aprendizado = ""
        self.leitura_quando = ""
        self.leitura_inicio = ""
        self.leitura_fim = ""
        self.memorias = []
        self._mtime_memoria = None
        self.interesse_cam = {}
        self.matches = {}
        self.total_antigo = {nome: 0 for nome in CATEGORIAS}
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
        self.titulo = "C4ISTAR MONITOR"

    def _loop(self):
        while not self._parar:
            try:
                self._consumir_fluxo()
                self._consumir_ocorrencias()
                self._consumir_interesse()
                self._consumir_alertas()
                self._consumir_insights()
                self._ler_leitura()
                self._ler_memorias()
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
            if dia is None:
                continue
            categoria = colunas[3] if colunas[3] in CATEGORIAS else "Objeto"
            if dia < limite:
                with self._trava:
                    self.total_antigo[categoria] = self.total_antigo.get(categoria, 0) + 1
                continue
            try:
                hora = int((colunas[1] or "0")[:2])
            except ValueError:
                hora = 0
            registros.append((
                dia.isoformat(),
                colunas[2] or "CAMERA",
                categoria,
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
            try:
                hora = int((colunas[1] or "0")[:2])
            except ValueError:
                hora = 0
            registros.append((
                dia.isoformat(),
                colunas[2] or "CAMERA",
                colunas[3] or "",
                colunas[4] or "",
                colunas[5] if len(colunas) > 5 else "",
                _risco(colunas[14] if len(colunas) > 14 else "", colunas[15] if len(colunas) > 15 else ""),
                _faixa(colunas[3] or "", colunas[15] if len(colunas) > 15 else ""),
                max(0, min(23, hora)),
            ))
        with self._trava:
            for dia, camera, _categoria, classe, ident, risco, faixa, hora in registros:
                self.risco[(dia, risco)] = self.risco.get((dia, risco), 0) + 1
                self.faixa[(dia, faixa, camera)] = self.faixa.get((dia, faixa, camera), 0) + 1
                self.tipo[(dia, classe, camera)] = self.tipo.get((dia, classe, camera), 0) + 1
                self.hora_faixa[(dia, faixa, hora)] = self.hora_faixa.get((dia, faixa, hora), 0) + 1
                if ident:
                    self.ids.add((dia, camera, classe, ident))

    def _atualizar_interesse(self):
        if time.time() - self._interesse_em < 2 and self._interesse_em:
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
            for item in novos:
                dia = str(item.get("quando") or "")[:10]
                camera = item.get("camera") or ""
                if dia and camera:
                    chave = (dia, camera)
                    self.interesse_cam[chave] = self.interesse_cam.get(chave, 0) + 1
                    tipo = item.get("tipo") or ""
                    if tipo:
                        marca = (dia, tipo)
                        self.matches[marca] = self.matches.get(marca, 0) + 1

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
        leitura = ultimo.get("leitura") or {}
        with self._trava:
            self.resumo = str(leitura.get("resumo") or ultimo.get("resumo") or "")
            self.assessoramento = str(leitura.get("assessoramento") or ultimo.get("assessoramento") or "")
            self.aprendizado = str(leitura.get("aprendizado") or "")
            self.leitura_quando = str(ultimo.get("gerado_em") or ultimo.get("fim") or "")
            self.leitura_inicio = str(ultimo.get("inicio") or "")
            self.leitura_fim = str(ultimo.get("fim") or "")
            self.insights_relatorio = textos[:6]

    def _ler_memorias(self):
        caminho = "memoria_rua.json"
        if not os.path.exists(caminho):
            return
        marca = os.path.getmtime(caminho)
        if marca == self._mtime_memoria:
            return
        self._mtime_memoria = marca
        try:
            with open(caminho, encoding="utf-8") as arquivo:
                bruto = json.loads(arquivo.read())
        except (OSError, json.JSONDecodeError):
            return
        itens = []
        for item in (bruto or {}).get("aprendizados") or []:
            if not isinstance(item, dict):
                continue
            texto = str(item.get("texto") or "").strip()
            if not texto:
                continue
            itens.append({"quando": str(item.get("quando") or ""), "texto": texto})
        with self._trava:
            self.memorias = list(reversed(itens[-6:]))

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
        try:
            from cadastro import locais_cameras
            locais = locais_cameras()
        except Exception:
            locais = []
        por_rua = {item.get("nome"): item for item in locais}
        with self._trava:
            categorias = {nome: 0 for nome in CATEGORIAS}
            por_camera = {}
            por_categoria = {}
            for (dia, camera, categoria), valor in self.cat.items():
                if dia != hoje:
                    continue
                categorias[categoria] = categorias.get(categoria, 0) + valor
                por_camera[camera] = por_camera.get(camera, 0) + valor
                grupo = por_categoria.setdefault(camera, {})
                grupo[categoria] = grupo.get(categoria, 0) + valor
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
            for local in locais:
                nome = local.get("nome")
                if nome and nome not in vistos:
                    nomes.append(nome)
                    vistos.add(nome)
            faixas = {nome: {} for nome in FAIXAS}
            for (dia, faixa, camera), valor in self.faixa.items():
                if dia == hoje and faixa in faixas:
                    faixas[faixa][camera] = faixas[faixa].get(camera, 0) + valor
            tipos_mapa = {}
            comportamento_cam = {}
            for (dia, classe, camera), valor in self.tipo.items():
                if dia != hoje or not classe:
                    continue
                item = tipos_mapa.setdefault(classe, {})
                item[camera] = item.get(camera, 0) + valor
                comportamento_cam[camera] = comportamento_cam.get(camera, 0) + valor
            alertas_cam = {
                camera: valor
                for (dia, camera), valor in self.interesse_cam.items()
                if dia == hoje
            }
            curvas_mapa = {}
            for (dia, classe, _camera), valor in self.tipo.items():
                if dia in dias and classe:
                    linha = curvas_mapa.setdefault(classe, {nome: 0 for nome in dias})
                    linha[dia] = linha.get(dia, 0) + valor
            ids = sum(1 for dia, *_resto in self.ids if dia == hoje)
            resumo = self.resumo
            assessoramento = self.assessoramento
            aprendizado = self.aprendizado
            leitura_quando = self.leitura_quando
            leitura_inicio = self.leitura_inicio
            leitura_fim = self.leitura_fim
            memorias = [dict(item) for item in self.memorias]
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
            inicio_mes = hoje[:8] + "01"
            dias_serie = [(date.today() - timedelta(days=offset)).isoformat() for offset in range(6, -1, -1)]

            def somar_cat(inicio):
                totais = {nome: int(self.total_antigo.get(nome, 0) if not inicio else 0) for nome in CATEGORIAS}
                for (dia, _camera, categoria), valor in self.cat.items():
                    if categoria in totais and (not inicio or dia >= inicio):
                        totais[categoria] += valor
                return totais

            def somar_comportamento(inicio):
                return sum(
                    valor for (dia, _classe), valor in self.classe.items()
                    if not inicio or dia >= inicio
                )

            def somar_match(inicio, tipo):
                return sum(
                    valor for (dia, qual), valor in self.matches.items()
                    if qual == tipo and (not inicio or dia >= inicio)
                )

            def bloco(inicio):
                base = somar_cat(inicio)
                base["Comportamento"] = somar_comportamento(inicio)
                base["MatchFace"] = somar_match(inicio, "FACE")
                base["MatchPlaca"] = somar_match(inicio, "PLACA")
                return base

            periodos = {"dia": bloco(hoje), "mes": bloco(inicio_mes), "total": bloco("")}
            serie_dias = []
            dias_empilhados = []
            for dia in dias_serie:
                item = {"rotulo": f"{dia[8:10]}/{dia[5:7]}"}
                por_cam = {}
                for (quando, camera, categoria), valor in self.cat.items():
                    if quando != dia or categoria not in CATEGORIAS:
                        continue
                    item[categoria] = item.get(categoria, 0) + valor
                    slot = por_cam.setdefault(camera, {nome: 0 for nome in CATEGORIAS})
                    slot[categoria] += valor
                for nome in CATEGORIAS:
                    item.setdefault(nome, 0)
                serie_dias.append(item)
                dias_empilhados.append({"rotulo": item["rotulo"], "cameras": por_cam})
            horas_prioridade = {nome: [0] * 24 for nome in FAIXAS}
            for (dia, faixa, hora), valor in self.hora_faixa.items():
                if dia == hoje and faixa in horas_prioridade and 0 <= hora <= 23:
                    horas_prioridade[faixa][hora] = valor
            classes_lista = [
                {"nome": nome, "total": total}
                for nome, total in sorted(classes.items(), key=lambda item: -item[1])[:8]
            ]
            pontos_mapa = []
            for ponto in list(self.pontos_locais) + list(self.pontos_remotos):
                pontos_mapa.append({
                    "lat": ponto.get("lat"),
                    "lon": ponto.get("lon"),
                    "tipo": ponto.get("tipo") or "Ocorrencia",
                    "data": ponto.get("data") or "",
                    "aproximado": bool(ponto.get("aproximado")),
                })
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
                "rua": (por_rua.get(nome) or {}).get("rua") or "",
                "online": any(item.get("nome") == nome for item in cameras_online or []),
                "itens": por_camera.get(nome, 0),
                "categorias": dict(por_categoria.get(nome) or {}),
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
            "periodos": periodos,
            "serie_dias": serie_dias,
            "dias_empilhados": dias_empilhados,
            "horas_prioridade": horas_prioridade,
            "classes_web": classes_lista,
            "pontos": pontos_mapa,
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
            "app": list(reversed(app[-6:])),
            "interesse": list(reversed(interesse[-4:])),
            "enviados": list(reversed(enviados[-6:])),
            "insights": list(reversed(insights[-4:])),
            "match": vivo,
            "resumo": resumo,
            "assessoramento": assessoramento,
            "aprendizado": aprendizado,
            "leitura_quando": leitura_quando,
            "leitura_inicio": leitura_inicio,
            "leitura_fim": leitura_fim,
            "memorias": memorias,
            "locais": locais,
            "contagem_comportamento": comportamento_cam,
            "contagem_alertas": alertas_cam,
            "geo": [
                {
                    "nome": item["nome"],
                    "rua": item["rua"],
                    "lat": (por_rua.get(item["nome"]) or {}).get("latitude"),
                    "lon": (por_rua.get(item["nome"]) or {}).get("longitude"),
                    "itens": item["itens"],
                    "comportamento": int(comportamento_cam.get(item["nome"], 0)),
                    "alertas": int(alertas_cam.get(item["nome"], 0)),
                }
                for item in cameras
            ],
        }
