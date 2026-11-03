"""Painel C4ISTAR desenhado ao lado da imagem da câmera."""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from datetime import datetime

import cv2
import numpy as np

LARGURA_PAINEL = 268

FUNDO = (14, 18, 12)
LINHA = (48, 72, 42)
AMBAR = (0, 176, 255)
CIANO = (220, 196, 40)
VERDE = (90, 210, 96)
TEXTO = (226, 232, 220)
DIM = (130, 142, 124)
VERMELHO = (60, 60, 240)

ROTULOS_ACAO = {
    "Em_Pe": ("EMP", "em pe"),
    "Sentado": ("SEN", "sentado"),
    "Caminhando": ("CAM", "caminhando"),
    "Bracos_Levantados": ("BRA", "bracos"),
    "Agachado": ("AGA", "agachado"),
    "Deitado": ("DEI", "deitado"),
    "Correndo": ("COR", "correndo"),
    "Permanencia": ("PER", "parado"),
    "Interacao_Proxima": ("INT", "interacao"),
    "Aglomeracao": ("AGL", "grupo"),
    "Levantando": ("LEV", "levantando"),
    "Possivel_Queda": ("QDA", "queda"),
    "Possivel_Briga": ("BRG", "briga"),
    "Possivel_Arma_Fogo": ("ARM", "arma"),
}

NIVEL_RISCO = {
    "Em_Pe": 1,
    "Sentado": 1,
    "Caminhando": 1,
    "Bracos_Levantados": 1,
    "Agachado": 2,
    "Deitado": 2,
    "Correndo": 2,
    "Permanencia": 2,
    "Interacao_Proxima": 2,
    "Aglomeracao": 2,
    "Levantando": 2,
    "Possivel_Queda": 3,
    "Possivel_Briga": 3,
    "Possivel_Arma_Fogo": 4,
}

COR_NIVEL = {
    1: (168, 168, 150),
    2: (0, 176, 255),
    3: (0, 120, 255),
    4: (70, 70, 255),
}

ROTULO_RISCO = {
    1: ("INF", "info"),
    2: ("ATN", "atencao"),
    3: ("PRI", "priorid."),
    4: ("CRI", "critico"),
}


class _FileTime(ctypes.Structure):
    _fields_ = [("lo", wintypes.DWORD), ("hi", wintypes.DWORD)]


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _ProcessMemory(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _filetime(valor: _FileTime) -> int:
    return (int(valor.hi) << 32) | int(valor.lo)


class Telemetria:
    """CPU e RAM do processo e da máquina. A leitura real ocorre a cada meio segundo."""

    def __init__(self):
        self.cpu = 0.0
        self.cpu_maquina = 0.0
        self.ram_mb = 0.0
        self.ram_pct = 0.0
        self._marca = 0.0
        self._proc = None
        self._sys = None
        self._nucleos = max(1, os.cpu_count() or 1)

    def atualizar(self):
        agora = time.perf_counter()
        if self._marca and (agora - self._marca) < 0.5:
            return self
        try:
            self._ler_windows(agora)
        except Exception:
            pass
        self._marca = agora
        return self

    def _ler_windows(self, agora):
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        ponteiro_tempo = ctypes.POINTER(_FileTime)
        kernel32.GetProcessTimes.argtypes = [
            ctypes.c_void_p, ponteiro_tempo, ponteiro_tempo, ponteiro_tempo, ponteiro_tempo,
        ]
        processo = kernel32.GetCurrentProcess()
        criacao, saida, kernel, usuario = _FileTime(), _FileTime(), _FileTime(), _FileTime()
        kernel32.GetProcessTimes(
            processo,
            ctypes.byref(criacao),
            ctypes.byref(saida),
            ctypes.byref(kernel),
            ctypes.byref(usuario),
        )
        proc = _filetime(kernel) + _filetime(usuario)

        ocioso, sys_kernel, sys_usuario = _FileTime(), _FileTime(), _FileTime()
        ponteiro_tempo = ctypes.POINTER(_FileTime)
        kernel32.GetSystemTimes.argtypes = [ponteiro_tempo, ponteiro_tempo, ponteiro_tempo]
        kernel32.GetSystemTimes.restype = wintypes.BOOL
        kernel32.GetSystemTimes(
            ctypes.byref(ocioso),
            ctypes.byref(sys_kernel),
            ctypes.byref(sys_usuario),
        )
        sys_total = _filetime(sys_kernel) + _filetime(sys_usuario)
        sys_ocioso = _filetime(ocioso)

        if self._proc is not None and self._sys is not None:
            parede = max(agora - self._marca, 1e-6)
            self.cpu = (proc - self._proc) / (parede * 1e7 * self._nucleos) * 100
            self.cpu = max(0.0, min(100.0, self.cpu))
            delta_total = sys_total - self._sys[0]
            delta_ocioso = sys_ocioso - self._sys[1]
            if delta_total > 0:
                self.cpu_maquina = max(0.0, min(100.0, (1 - delta_ocioso / delta_total) * 100))
        self._proc = proc
        self._sys = (sys_total, sys_ocioso)

        memoria = _ProcessMemory()
        memoria.cb = ctypes.sizeof(memoria)
        psapi = ctypes.windll.psapi
        psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(_ProcessMemory), wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        psapi.GetProcessMemoryInfo(processo, ctypes.byref(memoria), memoria.cb)
        self.ram_mb = memoria.WorkingSetSize / (1024 * 1024)

        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        self.ram_pct = float(status.dwMemoryLoad)


TELEMETRIA = Telemetria()


def _texto(imagem, texto, x, y, escala, cor, espessura=1):
    cv2.putText(
        imagem, texto, (x, y),
        cv2.FONT_HERSHEY_SIMPLEX, escala, cor, espessura, cv2.LINE_AA,
    )


def _barra(imagem, x, y, largura, altura, fracao, cor):
    cv2.rectangle(imagem, (x, y), (x + largura, y + altura), LINHA, 1)
    preenchido = int(largura * max(0.0, min(1.0, fracao)))
    if preenchido > 0:
        cv2.rectangle(imagem, (x, y), (x + preenchido, y + altura), cor, -1)


def _cor_carga(fracao):
    if fracao >= 0.85:
        return VERMELHO
    if fracao >= 0.60:
        return AMBAR
    return VERDE


def _cantos(imagem, cor):
    altura, largura = imagem.shape[:2]
    traco = 16
    pontos = (
        ((8, 28), (8, 28 + traco), (8, 28), (8 + traco, 28)),
        ((largura - 9, 28), (largura - 9, 28 + traco), (largura - 9, 28), (largura - 9 - traco, 28)),
        ((8, altura - 9), (8, altura - 9 - traco), (8, altura - 9), (8 + traco, altura - 9)),
        ((largura - 9, altura - 9), (largura - 9, altura - 9 - traco), (largura - 9, altura - 9), (largura - 9 - traco, altura - 9)),
    )
    for a, b, c, d in pontos:
        cv2.line(imagem, a, b, cor, 1, cv2.LINE_AA)
        cv2.line(imagem, c, d, cor, 1, cv2.LINE_AA)


def _faixa(imagem, y1, y2, escurecer):
    recorte = imagem[y1:y2]
    if recorte.size == 0:
        return
    base = np.full_like(recorte, FUNDO)
    cv2.addWeighted(recorte, 1 - escurecer, base, escurecer, 0, recorte)


def resumir_comportamento(unicos_por_classe, acoes_ativas):
    agora = {}
    for acao in acoes_ativas.values():
        agora[acao] = agora.get(acao, 0) + 1
    linhas = []
    for classe, ids in unicos_por_classe.items():
        total = len(ids)
        if total <= 0:
            continue
        sigla, nome = ROTULOS_ACAO.get(classe, (classe[:3].upper(), classe.replace("_", " ").lower()))
        nivel = NIVEL_RISCO.get(classe, 1)
        linhas.append({
            "sigla": sigla,
            "nome": nome,
            "total": total,
            "agora": agora.get(classe, 0),
            "nivel": nivel,
        })
    linhas.sort(key=lambda item: (-item["nivel"], -item["total"], item["sigla"]))
    return linhas


def resumir_risco(unicos_por_classe):
    totais = {1: 0, 2: 0, 3: 0, 4: 0}
    for classe, ids in unicos_por_classe.items():
        nivel = NIVEL_RISCO.get(classe, 1)
        totais[nivel] += len(ids)
    return totais


def desenhar_controle(exibir, nomes, paineis=None, cameras=None):
    """Janela pequena que permanece quando o vídeo está oculto."""
    paineis = paineis or {}
    cameras = cameras or []
    linhas = max(1, len(cameras))
    altura = 196 + linhas * 26
    largura = 1040
    imagem = np.zeros((altura, largura, 3), dtype=np.uint8)
    imagem[:] = FUNDO
    cv2.rectangle(imagem, (0, 0), (largura - 1, altura - 1), AMBAR, 1)
    fase = int(time.time() * 4) % 5
    aceso = int(time.time() * 2) % 2 == 0
    for indice in range(5):
        cor = (80, 230, 110) if indice == fase else (0, 45, 18)
        cv2.circle(imagem, (largura - 130 + indice * 16, 22), 4, cor, -1, cv2.LINE_AA)
    cv2.circle(imagem, (largura - 24, 22), 6, VERDE if aceso else (0, 55, 18), -1, cv2.LINE_AA)
    _texto(imagem, "C4ISTAR", 14, 28, 0.55, AMBAR, 1)
    if exibir:
        _texto(imagem, "VIDEO ABERTO", 160, 28, 0.48, VERDE, 1)
    else:
        _texto(imagem, "VIDEO OCULTO", 160, 28, 0.48, CIANO, 1)
    _texto(imagem, "Monitoramento em execucao", 14, 58, 0.42, TEXTO, 1)
    _texto(imagem, "V todas    Q encerra", 14, 86, 0.42, AMBAR, 1)
    comandos = (("1", "CONTAGENS"), ("2", "COMPORT."), ("3", "RF/LPR"), ("4", "MAPAS"))
    x = 280
    for tecla, nome in comandos:
        aberto = bool(paineis.get(tecla))
        estado = "ON" if aberto else "OFF"
        _texto(imagem, f"{tecla} {nome} {estado}", x, 86, 0.4, VERDE if aberto else DIM, 1)
        x += 155
    _texto(imagem, "Cameras", 14, 118, 0.42, TEXTO, 1)
    if not cameras:
        _texto(imagem, "aguardando camera online", 120, 118, 0.4, DIM, 1)
    y = 148
    for camera in cameras:
        ligada = bool(camera.get("aberto"))
        cv2.circle(imagem, (22, y - 4), 5, VERDE if ligada else (0, 40, 18), -1, cv2.LINE_AA)
        lugar = camera.get("rua") or camera.get("nome") or ""
        _texto(
            imagem,
            f"{camera.get('tecla')}   Camera {camera.get('indice')}   {lugar}"[:52],
            36, y, 0.42, VERDE if ligada else DIM, 1,
        )
        _texto(imagem, "ATIVA" if ligada else "OCULTA", 860, y, 0.4, VERDE if ligada else DIM, 1)
        y += 26
    return imagem


def desenhar_painel(
    frame,
    nome,
    fps,
    pessoas_cena,
    veiculos_cena,
    passagens_pessoa,
    passagens_veiculo,
    faces,
    placas,
    comportamentos,
    riscos,
    alerta=None,
    match=None,
):
    """Devolve a imagem com a faixa superior e o painel à direita."""
    tele = TELEMETRIA.atualizar()
    altura, largura = frame.shape[:2]
    saida = np.zeros((altura, largura + LARGURA_PAINEL, 3), dtype=np.uint8)
    saida[:, :largura] = frame
    video = saida[:, :largura]
    painel = saida[:, largura:]
    painel[:] = FUNDO

    _faixa(video, 0, 24, 0.72)
    _texto(video, "C4ISTAR", 10, 16, 0.42, AMBAR, 1)
    _texto(video, nome.upper(), 92, 16, 0.42, TEXTO, 1)
    _texto(video, datetime.now().strftime("%H:%M:%S"), largura - 168, 16, 0.42, CIANO, 1)
    _texto(video, "AO VIVO", largura - 72, 16, 0.38, VERDE, 1)
    _cantos(video, AMBAR)

    if alerta:
        texto_alerta, cor_alerta = alerta
        _faixa(video, altura - 22, altura, 0.78)
        _texto(video, texto_alerta[:42], 10, altura - 7, 0.42, cor_alerta, 1)

    limite_texto = altura - 118

    def cabe(y_linha):
        return y_linha <= limite_texto - 6

    def secao(titulo, y_secao):
        if not cabe(y_secao):
            return y_secao
        _texto(painel, titulo, 12, y_secao, 0.36, AMBAR, 1)
        return y_secao + 14

    def linha(sigla, valor, legenda, y_linha, cor, x_sigla=12):
        if not cabe(y_linha):
            return y_linha
        _texto(painel, sigla, x_sigla, y_linha, 0.38, cor, 1)
        _texto(painel, valor, x_sigla + 34, y_linha, 0.40, TEXTO, 1)
        if legenda:
            _texto(painel, legenda, x_sigla + 78, y_linha, 0.34, DIM, 1)
        return y_linha + 14

    _texto(painel, "C4ISTAR", 12, 16, 0.46, AMBAR, 1)
    _texto(painel, "MONITOR", 118, 16, 0.40, DIM, 1)
    cv2.line(painel, (8, 26), (LARGURA_PAINEL - 8, 26), LINHA, 1)

    cor_cpu = _cor_carga(tele.cpu / 100)
    cor_maq = _cor_carga(tele.cpu_maquina / 100)
    cor_ram = _cor_carga(tele.ram_pct / 100)

    y = 42
    y = secao("HOST", y)
    y = linha("FPS", f"{fps:4.1f}", "quadros/s", y, CIANO)
    y = linha("CPU", f"{tele.cpu:4.0f}%", "processo", y, cor_cpu)
    if cabe(y):
        _barra(painel, 12, y - 10, LARGURA_PAINEL - 24, 5, tele.cpu / 100, cor_cpu)
        y += 8
    y = linha("SYS", f"{tele.cpu_maquina:4.0f}%", "maquina", y, cor_maq)
    y = linha("RAM", f"{tele.ram_mb:5.0f}", "MB do app", y, cor_ram)
    y = linha("MEM", f"{tele.ram_pct:4.0f}%", "da maquina", y, cor_ram)
    if cabe(y):
        _barra(painel, 12, y - 10, LARGURA_PAINEL - 24, 5, tele.ram_pct / 100, cor_ram)
        y += 8
    if cabe(y):
        cv2.line(painel, (8, y), (LARGURA_PAINEL - 8, y), LINHA, 1)
        y += 16

    if cabe(y):
        _texto(painel, "CENA", 12, y, 0.36, AMBAR, 1)
        _texto(painel, "ACUMULADO", 140, y, 0.36, AMBAR, 1)
        y += 15
    y = linha("PES", f"{pessoas_cena:02d}", "", y, VERDE)
    linha("PES", f"{passagens_pessoa:04d}", "", y - 14, VERDE, x_sigla=140)
    y = linha("VEI", f"{veiculos_cena:02d}", "", y, CIANO)
    linha("VEI", f"{passagens_veiculo:04d}", "", y - 14, CIANO, x_sigla=140)
    y = linha("FAC", f"{faces:02d}", "", y, (210, 90, 230))
    linha("PLC", f"{placas:02d}", "", y - 14, (80, 220, 255), x_sigla=140)
    if cabe(y):
        cv2.line(painel, (8, y), (LARGURA_PAINEL - 8, y), LINHA, 1)
        y += 16

    y = secao("RISCO ACUMULADO", y)
    if cabe(y + 12):
        for indice, nivel in enumerate((1, 2, 3, 4)):
            sigla, legenda = ROTULO_RISCO[nivel]
            cor = COR_NIVEL[nivel]
            total = riscos.get(nivel, 0)
            x_nivel = 12 + indice * 64
            _texto(painel, sigla, x_nivel, y, 0.34, cor, 1)
            _texto(painel, f"{total:03d}", x_nivel, y + 14, 0.40, TEXTO, 1)
            _texto(painel, legenda, x_nivel, y + 24, 0.28, DIM, 1)
        y += 36

    if cabe(y + 8):
        cv2.line(painel, (8, y), (LARGURA_PAINEL - 8, y), LINHA, 1)
        y += 16
        y = secao("COMPORTAMENTO", y)
        visiveis = comportamentos[:4]
        if not visiveis and cabe(y):
            _texto(painel, "sem registro", 12, y, 0.34, DIM, 1)
        for item in visiveis:
            if not cabe(y):
                break
            cor = COR_NIVEL.get(item["nivel"], DIM)
            legenda = item["nome"]
            if item["agora"]:
                legenda = f"{legenda} agora {item['agora']}"
            y = linha(item["sigla"], f"{item['total']:03d}", legenda, y, cor)

    _desenhar_match(painel, match)
    cv2.line(painel, (0, 0), (0, altura), AMBAR, 1)
    return saida


def _miniatura_painel(imagem, largura=108, altura=62):
    if imagem is None or getattr(imagem, "size", 0) == 0:
        return None
    return cv2.resize(imagem, (largura, altura), interpolation=cv2.INTER_AREA)


def _desenhar_match(painel, match):
    altura, largura = painel.shape[:2]
    y0 = altura - 118
    cv2.rectangle(painel, (0, y0), (largura, altura), FUNDO, -1)
    cv2.line(painel, (8, y0), (largura - 8, y0), AMBAR, 1)
    _texto(painel, "MATCH", 12, y0 + 16, 0.36, AMBAR, 1)
    if not match:
        _texto(painel, "sem interesse", 12, y0 + 42, 0.36, DIM, 1)
        return
    cor_tipo = (210, 90, 230) if match.get("tipo") == "FACE" else CIANO
    _texto(painel, match.get("tipo") or "", 68, y0 + 16, 0.32, cor_tipo, 1)
    taxa = float(match.get("taxa") or 0)
    _texto(painel, f"{match.get('rotulo_taxa') or 'SIM'} {taxa:.2f}", 138, y0 + 16, 0.38, TEXTO, 1)
    _barra(painel, 138, y0 + 20, 112, 5, taxa, VERDE if taxa >= 0.60 else AMBAR)
    for rotulo, imagem, x in (
        ("REF", match.get("referencia"), 12),
        ("AGORA", match.get("atual"), 140),
    ):
        _texto(painel, rotulo, x, y0 + 36, 0.30, DIM, 1)
        thumb = _miniatura_painel(imagem)
        if thumb is None:
            _texto(painel, "sem foto", x, y0 + 70, 0.32, DIM, 1)
            continue
        y = y0 + 42
        h, w = thumb.shape[:2]
        painel[y:y + h, x:x + w] = thumb
    legenda = f"{match.get('id') or ''} {match.get('nome') or ''}".strip()
    _texto(painel, legenda[:32], 12, altura - 6, 0.32, TEXTO, 1)
