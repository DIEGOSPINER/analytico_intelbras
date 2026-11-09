"""Escuta o áudio do RTSP, separado da imagem do OpenCV.

Pico curto = barulho alto (não afirma disparo). Transcrição só com
evidência forte de fala; alucinações típicas do Whisper são descartadas.
Risco de disparo nasce da fusão visual + barulho no Detector de risco,
com confirmação do operador no Stive.
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
# Whisper inventa legendas de YouTube / frases de risco em silêncio ou ruído.
FRASES_INVENTADAS = (
    "obrigado por assistir",
    "obrigada por assistir",
    "thanks for watching",
    "thank you for watching",
    "inscreva-se",
    "inscreva no canal",
    "se inscreva",
    "se inscreva no canal",
    "ative o sininho",
    "ativa o sininho",
    "sininho",
    "receba notificações",
    "novos vídeos",
    "novos videos",
    "legendas pela comunidade",
    "legendas geradas automaticamente",
    "amara.org",
    "até a próxima",
    "ate a proxima",
    "tchau tchau",
    "subscribe to the channel",
    "subscribe",
    "notification bell",
    "leave a like",
    "like and subscribe",
    # Frase fantasma recorrente neste projeto (ruído → "socorro/briga/disparo")
    "socorro, tem uma briga e disparo",
    "socorro tem uma briga e disparo",
    "tem uma briga e disparo na rua",
    "briga e disparo na rua",
)
_ALUCINACAO_RISCO = re.compile(
    r"socorro.{0,40}brig|brig.{0,40}dispar|socorro.{0,40}dispar",
    re.IGNORECASE,
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
    """Devolve ('barulho'|'ruido_continuo'|'voz', nivel) ou None.

    Pico curto = estalo/barulho esporádico. Energia alta contínua = ruído
    sustentado (candidato a perturbação de sossego após 30 min).
    """
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
    media = float(serie.mean())
    piso_alto = max(0.08, base * 8)
    altos = int(np.sum(serie > piso_alto))
    pico_min, mult, _cooldown = 0.45, 20.0, 90.0
    try:
        from agente.aprendizado_feedback import limiar_audio_disparo

        pico_min, mult, _cooldown = limiar_audio_disparo()
    except Exception:
        pass
    # Pico curto (estalos): poucos frames altos e pico bem acima da base.
    if pico > pico_min and altos <= 3 and pico > base * mult:
        return "barulho", pico
    # Ruído muito alto ininterrupto nesta janela (≥35% dos frames altos e média elevada).
    if altos >= max(8, int(0.35 * len(serie))) and media >= max(0.06, base * 4):
        return "ruido_continuo", media
    # Exige mais frames com energia de fala antes de gastar Whisper.
    voz = int(np.sum(serie > 0.02))
    if voz >= 55:
        return "voz", pico
    return None


def _transcrever(wav: bytes, api_key: str) -> dict:
    limite = "----audioanalitico"
    partes = []
    prompt = (
        "Ambiente de câmera de rua / CFTV em português brasileiro. "
        "Transcreva apenas fala humana clara e inteligível. "
        "Se for só ruído, vento, motor, música ou silêncio, devolva texto vazio. "
        "Nunca invente pedidos de socorro, briga, disparo, legendas, "
        "inscrições em canal, sininho ou 'obrigado por assistir'."
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
    if len(texto) < 8:
        return ""
    if any(frase in baixo for frase in FRASES_INVENTADAS):
        return ""
    if _ALUCINACAO_RISCO.search(baixo):
        return ""
    letras = sum(1 for c in texto if c.isalpha())
    if letras < 8:
        return ""
    palavras = [p for p in re.findall(r"\w+", baixo) if len(p) > 1]
    if len(palavras) >= 4 and len(set(palavras)) <= 2:
        return ""
    segmentos = corpo.get("segments") or []
    if not segmentos:
        return ""
    silencio = sum(float(item.get("no_speech_prob") or 0) for item in segmentos) / len(segmentos)
    confianca = sum(float(item.get("avg_logprob") or -10) for item in segmentos) / len(segmentos)
    compressao = sum(float(item.get("compression_ratio") or 1) for item in segmentos) / len(segmentos)
    # Mais rigoroso: silêncio/ruído → Whisper alucina legendas e frases de risco.
    if silencio > 0.22 or confianca < -0.55 or compressao > 2.15:
        return ""
    # Palavras de risco exigem confiança ainda maior (evita inventar "socorro/tiro").
    if classificar_texto(texto):
        if silencio > 0.12 or confianca < -0.35:
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
        self._ultimo_barulho = 0.0
        self._ultima_fala = 0.0
        self._ruido_continuo_desde = 0.0
        self._ultimo_sossego = 0.0
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
        agora = time.time()
        if classe is None:
            # Quebra a sequência de ruído contínuo se a janela ficou quieta.
            self._ruido_continuo_desde = 0.0
            return
        tipo, nivel = classe
        cooldown = 90.0
        try:
            from agente.aprendizado_feedback import limiar_audio_disparo

            _pico, _mult, cooldown = limiar_audio_disparo()
        except Exception:
            pass
        # Estalos/barulho esporádico → alerta vermelho (não afirma disparo sozinho).
        if tipo == "barulho" and agora - self._ultimo_barulho >= cooldown:
            self._ultimo_barulho = agora
            self._ruido_continuo_desde = 0.0
            self.suspeito_ate = agora + 90
            self.suspeito_tipo = "barulho"
            self.suspeito_detalhe = (
                "Estalo/barulho alto esporádico (possível disparo ou impacto). "
                "Alerta vermelho — confirme no Stive se houve arma de fogo."
            )
            registrar_audio(
                self.nome,
                "Estalo_Alto",
                texto="",
                detalhe=self.suspeito_detalhe,
                confianca=float(nivel or 0),
                categoria="estalo",
                nivel=3,
                palavras=["estalo", "barulho"],
            )
            return
        # Ruído muito alto ininterrupto: acumula tempo até 30 min → sossego (amarelo).
        if tipo == "ruido_continuo":
            if self._ruido_continuo_desde <= 0:
                self._ruido_continuo_desde = agora
            decorrido = agora - self._ruido_continuo_desde
            if decorrido >= 1800 and agora - self._ultimo_sossego >= 1800:
                self._ultimo_sossego = agora
                self.suspeito_ate = agora + 300
                self.suspeito_tipo = "sossego"
                self.suspeito_detalhe = (
                    f"Ruído muito alto ininterrupto há {int(decorrido // 60)} min. "
                    "Ocorrência: perturbação do sossego."
                )
                registrar_audio(
                    self.nome,
                    "Perturbacao_Sossego",
                    texto="",
                    detalhe=self.suspeito_detalhe,
                    confianca=float(nivel or 0),
                    categoria="sossego",
                    nivel=2,
                    palavras=["perturbacao", "sossego", "ruido"],
                )
                try:
                    from ocorrencias import informar_ocorrencia
                    from cadastro import cliente_ativo

                    conta = cliente_ativo() or {}
                    informar_ocorrencia(
                        "".join(c for c in str(conta.get("documento") or "") if c.isdigit()),
                        {
                            "natureza": "Perturbacao",
                            "descricao": self.suspeito_detalhe,
                            "endereco": self.nome,
                            "data": time.strftime("%Y-%m-%d"),
                            "hora": time.strftime("%H:%M"),
                        },
                        usar_modelo=False,
                    )
                except Exception:
                    pass
            return
        self._ruido_continuo_desde = 0.0
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
        nivel_risco = max((int(item.get("nivel") or 0) for item in achados), default=0)
        cats = sorted({str(item.get("categoria") or "") for item in achados if item.get("categoria")})
        # Gritos/xingamentos/briga/socorro/ameaças elevam LED vermelho.
        vermelho = nivel_risco >= 3 or any(
            c in ("briga", "socorro", "disparo", "xingamento") for c in cats
        )
        if vermelho:
            self.suspeito_ate = agora + 120
            self.suspeito_tipo = cats[0] if cats else "voz_risco"
            self.suspeito_detalhe = (
                f"Áudio de risco ({', '.join(cats) or 'fala'}): {trecho[:160]}"
            )
            registrar_audio(
                self.nome,
                "Audio_Risco",
                texto=trecho,
                detalhe=self.suspeito_detalhe,
                confianca=0.7,
                categoria=",".join(cats) or "voz_risco",
                nivel=max(nivel_risco, 3),
                palavras=[item["palavra"] for item in achados],
            )
            return
        registrar_audio(
            self.nome,
            "Transcricao_Audio",
            texto=trecho,
            detalhe="Transcrição de áudio da câmera (informativo).",
            confianca=0.55,
            categoria="transcricao",
            nivel=0,
            palavras=[item["palavra"] for item in achados],
        )
