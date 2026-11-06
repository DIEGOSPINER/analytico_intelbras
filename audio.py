"""Escuta o áudio do RTSP, separado da imagem do OpenCV.

Um pico muito curto vira possível disparo. Um trecho de voz pode ser
transcrito para procurar briga. Os dois avisos pedem confirmação: moto,
porta e conversa alta também fazem barulho.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
import wave
from io import BytesIO

import numpy as np

from agente.modelo import carregar_env
from cameras import destino_publico


TAXA = 16000
JANELA_SEGUNDOS = 6
PALAVRAS_BRIGA = (
    r"\bbrig(?:a|as|ando|aram|ou)\b",
    r"\bagress\w*",
    r"\bporrada\b",
    r"\btapa\b",
    r"\bempurra\w*",
    r"\bcala a boca\b",
    r"\bte mato\b",
    r"\bvou te matar\b",
    r"\barma\b",
    r"\btiro\b",
    r"\bdisparo\b",
)
FRASES_INVENTADAS = (
    "obrigado por assistir",
    "thanks for watching",
    "inscreva-se",
    "legendas pela comunidade",
    "amara.org",
    "até a próxima",
    "tchau tchau",
)


def ffmpeg_disponivel() -> bool:
    return shutil.which("ffmpeg") is not None


def _sem_segredo(texto: str, url: str) -> str:
    if url and url in texto:
        texto = texto.replace(url, destino_publico(url))
    return texto


def _pcm_para_wav(pcm: bytes) -> bytes:
    saida = BytesIO()
    with wave.open(saida, "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(TAXA)
        arquivo.writeframes(pcm)
    return saida.getvalue()


def classificar_pcm(pcm: bytes):
    """Devolve ('disparo', nivel) ou ('voz', nivel). Silêncio devolve None."""
    if len(pcm) < TAXA * 2:
        return None
    amostras = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    quadro = 320
    niveis = []
    for inicio in range(0, amostras.size - quadro, quadro):
        bloco = amostras[inicio:inicio + quadro]
        niveis.append(float(np.sqrt(np.mean(bloco * bloco))))
    if not niveis:
        return None
    serie = np.array(niveis)
    pico = float(serie.max())
    base = float(np.median(serie))
    altos = int(np.sum(serie > max(0.08, base * 8)))
    if pico > 0.45 and altos <= 3 and pico > base * 20:
        return "disparo", pico
    voz = int(np.sum(serie > 0.015))
    if voz >= 40:
        return "voz", pico
    return None


def _transcrever(wav: bytes, api_key: str) -> dict:
    limite = "----audioanalitico"
    partes = []
    campos = (
        ("model", "whisper-1"),
        ("language", "pt"),
        ("temperature", "0"),
        ("response_format", "verbose_json"),
    )
    for nome, valor in campos:
        partes.append(
            f"--{limite}\r\nContent-Disposition: form-data; name=\"{nome}\"\r\n\r\n{valor}\r\n".encode()
        )
    partes.append(
        f"--{limite}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"trecho.wav\"\r\n"
        f"Content-Type: audio/wav\r\n\r\n".encode()
        + wav
        + b"\r\n"
    )
    partes.append(f"--{limite}--\r\n".encode())
    pedido = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=b"".join(partes),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={limite}",
        },
        method="POST",
    )
    with urllib.request.urlopen(pedido, timeout=60) as resposta:
        corpo = json.loads(resposta.read().decode("utf-8"))
    return corpo if isinstance(corpo, dict) else {"text": str(corpo)}


def _transcricao_confiavel(corpo: dict) -> str:
    texto = str(corpo.get("text") or "").strip()
    baixo = texto.lower()
    if len(texto) < 12 or any(frase in baixo for frase in FRASES_INVENTADAS):
        return ""
    segmentos = corpo.get("segments") or []
    if segmentos:
        silencio = sum(float(item.get("no_speech_prob") or 0) for item in segmentos) / len(segmentos)
        confianca = sum(float(item.get("avg_logprob") or -10) for item in segmentos) / len(segmentos)
        if silencio > 0.45 or confianca < -1.0:
            return ""
    return texto


def _fala_de_briga(texto: str) -> bool:
    baixo = (texto or "").lower()
    return any(re.search(padrao, baixo) for padrao in PALAVRAS_BRIGA)


class EscutaAudio:
    """Lê alguns segundos de áudio por vez, sem bloquear o vídeo."""

    def __init__(self, nome: str, url: str):
        carregar_env()
        self.nome = nome
        self.url = url
        self.eventos = queue.Queue()
        self.stopped = False
        self._thread = None
        self._ultimo_disparo = 0.0
        self._ultima_fala = 0.0
        self.suspeito_ate = 0.0
        self.suspeito_tipo = ""
        self.suspeito_ate = 0.0
        self.suspeito_tipo = ""

    def start(self):
        if os.getenv("AUDIO_ATIVO", "1").strip().lower() in ("0", "false", "nao", "não"):
            return self
        if not ffmpeg_disponivel():
            print(f"Áudio de {self.nome} desligado: ffmpeg não está instalado.")
            return self
        self._thread = threading.Thread(target=self._loop, name=f"audio-{self.nome}", daemon=True)
        self._thread.start()
        print(f"Escuta de áudio ativa: {self.nome} ({destino_publico(self.url)})")
        return self

    def stop(self):
        self.stopped = True

    def drenar(self) -> list[dict]:
        achados = []
        while True:
            try:
                achados.append(self.eventos.get_nowait())
            except queue.Empty:
                return achados

    def _loop(self):
        import time
        while not self.stopped:
            try:
                pcm = self._capturar()
                if pcm:
                    self._avaliar(pcm)
            except Exception as exc:
                print(f"Áudio {self.nome}: {_sem_segredo(str(exc), self.url)}")
            for _ in range(8):
                if self.stopped:
                    return
                time.sleep(1)

    def _capturar(self) -> bytes:
        comando = [
            "ffmpeg", "-nostdin", "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-i", self.url,
            "-t", str(JANELA_SEGUNDOS),
            "-vn", "-ac", "1", "-ar", str(TAXA),
            "-f", "s16le", "pipe:1",
        ]
        processo = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=JANELA_SEGUNDOS + 8,
            check=False,
        )
        if processo.returncode != 0 and not processo.stdout:
            erro = processo.stderr.decode("utf-8", errors="replace")[:180]
            raise RuntimeError(_sem_segredo(erro, self.url) or "ffmpeg não leu o áudio")
        return processo.stdout

    def _avaliar(self, pcm: bytes):
        import time
        classe = classificar_pcm(pcm)
        if classe is None:
            return
        tipo, nivel = classe
        agora = time.time()
        if tipo == "disparo" and agora - self._ultimo_disparo >= 90:
            self._ultimo_disparo = agora
            self.suspeito_ate = agora + 45
            self.suspeito_tipo = "disparo"
            self.eventos.put({
                "classe": "Possivel_Disparo",
                "risco": "Atencao",
                "nivel": 2,
                "confianca": round(min(nivel, 1.0), 2),
                "detalhe": "Pico curto de áudio compatível com disparo. Confirme o trecho; moto e porta também estouram.",
            })
            return
        if tipo != "voz" or agora - self._ultima_fala < 180:
            return
        if os.getenv("AUDIO_TRANSCRICAO", "1").strip().lower() in ("0", "false", "nao", "não"):
            return
        chave = os.getenv("OPENAI_API_KEY", "").strip()
        if not chave:
            return
        self._ultima_fala = agora
        try:
            corpo = _transcrever(_pcm_para_wav(pcm), chave)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            print(f"Transcrição de {self.nome} não concluída: {_sem_segredo(str(exc), self.url)[:180]}")
            return
        texto = _transcricao_confiavel(corpo)
        if not texto or not _fala_de_briga(texto):
            return
        trecho = " ".join(texto.split())[:240]
        self.suspeito_ate = time.time() + 45
        self.suspeito_tipo = "voz"
        self.eventos.put({
            "classe": "Possivel_Briga",
            "risco": "Prioritario",
            "nivel": 3,
            "confianca": 0.7,
            "detalhe": f"Fala com sinal de briga: {trecho}",
        })
