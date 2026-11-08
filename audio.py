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
from audio_registro import classificar_texto, registrar as registrar_audio
from cameras import destino_publico


TAXA = 16000
JANELA_SEGUNDOS = 6
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
    pico_min, mult, _cooldown = 0.45, 20.0, 90.0
    try:
        from agente.aprendizado_feedback import limiar_audio_disparo

        pico_min, mult, _cooldown = limiar_audio_disparo()
    except Exception:
        pass
    if pico > pico_min and altos <= 3 and pico > base * mult:
        return "disparo", pico
    voz = int(np.sum(serie > 0.015))
    if voz >= 40:
        return "voz", pico
    return None


def _transcrever(wav: bytes, api_key: str) -> dict:
    limite = "----audioanalitico"
    partes = []
    prompt = (
        "Transcreva somente falas humanas claras em português brasileiro. "
        "Se não houver fala inteligível, devolva texto vazio. "
        "Não invente palavras, música, legendas ou comentários."
    )
    campos = (
        ("model", "whisper-1"),
        ("language", "pt"),
        ("temperature", "0"),
        ("response_format", "verbose_json"),
        ("prompt", prompt),
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
    """Aceita só trechos com evidência forte de fala; rejeita alucinações do Whisper."""
    texto = str(corpo.get("text") or "").strip()
    baixo = texto.lower()
    if len(texto) < 8 or any(frase in baixo for frase in FRASES_INVENTADAS):
        return ""
    # Poucas letras / repetição típica de alucinação
    letras = sum(1 for c in texto if c.isalpha())
    if letras < 6:
        return ""
    palavras = [p for p in re.findall(r"\w+", baixo) if len(p) > 1]
    if len(palavras) >= 4 and len(set(palavras)) <= 2:
        return ""
    segmentos = corpo.get("segments") or []
    if not segmentos:
        # Sem segmentos verbose: só aceita se o modelo reportou duração plausível
        return ""
    silencio = sum(float(item.get("no_speech_prob") or 0) for item in segmentos) / len(segmentos)
    confianca = sum(float(item.get("avg_logprob") or -10) for item in segmentos) / len(segmentos)
    compressao = sum(float(item.get("compression_ratio") or 1) for item in segmentos) / len(segmentos)
    # Mais rigoroso: silêncio alto ou logprob ruim = ruído/alucinação
    if silencio > 0.32 or confianca < -0.75 or compressao > 2.4:
        return ""
    return texto


def _risco_audio(texto: str) -> list[dict]:
    return classificar_texto(texto)


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
        self.suspeito_detalhe = ""

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
        cooldown = 90.0
        try:
            from agente.aprendizado_feedback import limiar_audio_disparo

            _pico, _mult, cooldown = limiar_audio_disparo()
        except Exception:
            pass
        if tipo == "disparo" and agora - self._ultimo_disparo >= cooldown:
            self._ultimo_disparo = agora
            self.suspeito_ate = agora + 45
            self.suspeito_tipo = "disparo"
            detalhe = "Pico curto de áudio compatível com disparo. Confirme o trecho; moto e porta também estouram."
            self.suspeito_detalhe = detalhe
            conf = round(min(nivel, 1.0), 2)
            # Não grava na base até o operador confirmar no Stive.
            self.eventos.put({
                "classe": "Possivel_Disparo",
                "risco": "Atencao",
                "nivel": 3,
                "confianca": conf,
                "detalhe": detalhe,
                "texto": "",
                "categoria": "disparo",
                "palavras": ["disparo"],
                "stive": True,
                "confirmar": True,
                "pergunta": f"Houve disparo na {self.nome}? Confirme se foi de fato para gravar na base.",
            })
            return
        if tipo != "voz" or agora - self._ultima_fala < 50:
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
        if not texto:
            return
        trecho = " ".join(texto.split())[:240]
        achados = _risco_audio(trecho)
        categorias = sorted({item["categoria"] for item in achados})
        palavras = [item["palavra"] for item in achados]
        nivel = max((int(item["nivel"]) for item in achados), default=0)
        classe = "Transcricao_Audio"
        risco_nome = "Informativo"
        avisar = False
        if achados:
            if "disparo" in categorias or "briga" in categorias or "socorro" in categorias:
                classe = "Audio_Risco"
                risco_nome = "Prioritario"
                avisar = True
            else:
                classe = "Audio_Atencao"
                risco_nome = "Atencao"
                avisar = True
        # Fala limpa (sem risco) pode ir direto à esteira; risco só após Sim no Stive.
        if not avisar:
            registrar_audio(
                self.nome,
                classe,
                texto=trecho,
                detalhe="Transcrição de áudio da câmera.",
                confianca=0.55,
                categoria="transcricao",
                nivel=0,
                palavras=[],
            )
            return
        self.suspeito_ate = time.time() + 45
        self.suspeito_tipo = "voz"
        self.suspeito_detalhe = f"{', '.join(categorias)}. {trecho}".strip()
        pergunta = (
            f"Na {self.nome} parece ter havido {', '.join(categorias)}. "
            f'Ouvi: "{trecho}". Isso aconteceu de fato? Confirme para gravar na base.'
        )
        self.eventos.put({
            "classe": classe,
            "risco": risco_nome,
            "nivel": nivel or 1,
            "confianca": 0.7,
            "detalhe": f"Áudio com sinal de {', '.join(categorias)}: {trecho}",
            "texto": trecho,
            "categoria": ",".join(categorias),
            "palavras": palavras,
            "stive": True,
            "confirmar": True,
            "pergunta": pergunta,
        })
