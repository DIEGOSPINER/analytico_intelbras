import os

os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|stimeout;4000000",
)

import ctypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import cv2
import threading
import time
import csv
import os
import math
from datetime import datetime
from collections import defaultdict, deque
from pathlib import Path

import mediapipe as mp
import numpy as np
from ultralytics import YOLO

from audio import EscutaAudio
from cadastro import cameras_para_analise
from cameras import (
    ARQUIVO_CAMERAS,
    destino_publico,
    garantir_arquivo_cameras,
)
from identidade import (
    IdentificadorFaces,
    IdentificadorPlacas,
    inicializar_csv_faces,
    inicializar_csv_placas,
    salvar_passagem_face,
    salvar_passagem_placa,
)
from monitores import (
    INTERVALO_PAINEL_SEG,
    JANELAS_PAINEL,
    Acervo,
    aplicar_pulso,
    desenhar_monitor,
)
from painel import desenhar_controle, desenhar_painel, resumir_comportamento, resumir_risco


def carregar_env(caminho=".env"):
    """Carrega variáveis de um arquivo .env simples (sem dependência extra)."""
    env_path = Path(caminho)
    if not env_path.exists():
        return

    for linha in env_path.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        os.environ.setdefault(chave, valor)


carregar_env()

# ===================== CONFIGURAÇÕES =====================

ARQUIVO_HISTORICO = "historico_analitico.csv"
ARQUIVO_OCORRENCIAS = "historico_ocorrencias.csv"

MODELO_YOLO = "yolov8n.pt"
MODELO_ARMA = "arma_fogo.pt"  # opcional
MODELO_POSE = "pose_landmarker_lite.task"
MODELO_FACE = "blaze_face_full_range.tflite"
TRACKER = "bytetrack.yaml"

CONF_MINIMA = 0.4
CONF_ARMA_MINIMA = 0.45
CONFIANCA_POSE = 0.45

LARGURA, ALTURA = 640, 480

# A detecção roda numa imagem menor para o computador de teste acompanhar a câmera.
# A placa é lida no quadro original, onde o texto ainda está nítido.
# frames_veiculo: um quadro que pisca (caixa, muro) não completa a passagem.
PERFIS_CAMERA = {
    "im5": {"lado": 640, "conf": 0.40, "conf_veiculo": 0.32, "frames_veiculo": 2},
    "im3": {"lado": 640, "conf": 0.45, "conf_veiculo": 0.40, "frames_veiculo": 2},
    "padrao": {"lado": 640, "conf": 0.40, "conf_veiculo": 0.35, "frames_veiculo": 2},
}

# Pessoa, carro, moto, ônibus e caminhão. Barco, pássaro e outros objetos ficam de fora.
CLASSES_ANALISE = [0, 2, 3, 5, 7]
LADO_MINIMO_VEICULO = 18
DESLOCAMENTO_PASSAGEM = 0.03
ABERTURA_CAMERA_MS = 4000
SONDA_OFFLINE_SEG = 20


def perfil_camera(modelo: str) -> dict:
    chave = (modelo or "").lower().replace(" ", "").replace("-", "")
    for nome, perfil in PERFIS_CAMERA.items():
        if nome != "padrao" and nome in chave:
            return dict(perfil)
    return dict(PERFIS_CAMERA["padrao"])


def _ler_foto(caminho):
    if not caminho or not os.path.exists(caminho):
        return None
    return cv2.imread(str(caminho))


def _montar_match(tipo, ident, nome, taxa, rotulo, referencia, atual, agora):
    return {
        "tipo": tipo,
        "id": ident,
        "nome": nome,
        "taxa": max(0.0, min(1.0, taxa)),
        "rotulo_taxa": rotulo,
        "referencia": _ler_foto(referencia),
        "atual": _ler_foto(atual),
        "ate": agora + 30,
    }


def redimensionar_para_analise(frame, lado: int):
    """Mantém a proporção. Esticar para 640x480 achatava o carro e a detecção perdia ele."""
    altura, largura = frame.shape[:2]
    maior = max(altura, largura)
    if maior <= lado:
        return frame
    escala = lado / maior
    return cv2.resize(frame, (int(largura * escala), int(altura * escala)))

CLASSE_PESSOA = 0

CLASSES_VEICULOS = {
    2: "Carro",
    3: "Motocicleta",
    5: "Onibus",
    7: "Caminhao"
}

CLASSES_ANIMAIS = {
    14: "Passaro",
    15: "Gato",
    16: "Cachorro",
    17: "Cavalo",
    18: "Ovelha",
    19: "Vaca",
    20: "Elefante",
    21: "Urso",
    22: "Zebra",
    23: "Girafa"
}

CORES = {
    "Pessoa": (0, 255, 0),
    "Animal": (0, 255, 255),
    "Veiculo": (255, 0, 0),
    "Objeto": (255, 165, 0),
    "Comportamento": (0, 140, 255),
    "Interacao": (255, 128, 0),
    "Alerta": (0, 0, 255)
}

CORES_RISCO = {
    "Informativo": (180, 180, 180),
    "Atencao": (0, 200, 255),
    "Prioritario": (0, 140, 255),
    "Critico": (0, 0, 255)
}

# ---- parâmetros comportamentais ----
INTERVALO_POSE = 0.20                 # ~5 análises/s por pessoa
TEMPO_PARADO_SEG = 30
DESLOCAMENTO_PARADO = 0.03
DISTANCIA_AGLOMERACAO = 0.18
MIN_PESSOAS_AGLOMERACAO = 3
DISTANCIA_INTERACAO = 0.14
DISTANCIA_BRIGA = 0.12
VELOCIDADE_CAMINHAR = 0.025
VELOCIDADE_CORRER = 0.08
VELOCIDADE_BRIGA = 0.06
FRAMES_CONFIRMACAO = 3
COOLDOWN_INFO_SEG = 25
COOLDOWN_RISCO_SEG = 12
HISTORICO_POSICOES = 120
MAX_PESSOAS_POSE = 6                  # limite de pose por frame (CPU)

# Classificação de risco por ação detectada
RISCO_POR_ACAO = {
    "Em_Pe": ("Informativo", 1),
    "Sentado": ("Informativo", 1),
    "Caminhando": ("Informativo", 1),
    "Bracos_Levantados": ("Informativo", 1),
    "Agachado": ("Atencao", 2),
    "Deitado": ("Atencao", 2),
    "Correndo": ("Atencao", 2),
    "Permanencia": ("Atencao", 2),
    "Interacao_Proxima": ("Atencao", 2),
    "Aglomeracao": ("Atencao", 2),
    "Levantando": ("Atencao", 2),
    "Possivel_Queda": ("Prioritario", 3),
    "Possivel_Briga": ("Prioritario", 3),
    "Possivel_Arma_Fogo": ("Critico", 4),
}

# ==========================================================


def abrir_captura(src):
    captura = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
    captura.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    captura.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, ABERTURA_CAMERA_MS)
    captura.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, ABERTURA_CAMERA_MS)
    return captura


def captura_com_quadro(src):
    """Abre a câmera e exige um quadro. Sem resposta, devolve None e não segura o analítico."""
    captura = abrir_captura(src)
    if not captura.isOpened():
        captura.release()
        return None, None
    try:
        ok, quadro = captura.read()
    except cv2.error:
        ok, quadro = False, None
    if not ok or quadro is None:
        captura.release()
        return None, None
    return captura, quadro


class CameraStream:

    def __init__(self, src, captura=None, quadro=None):
        self.stream = captura if captura is not None else abrir_captura(src)
        self.frame = quadro
        self.preview = None
        self.stopped = False
        if self.frame is not None:
            self._guardar(self.frame)
        if self.frame is None:
            try:
                ok, quadro = self.stream.read()
                self.frame = quadro if ok else None
            except cv2.error:
                self.frame = None

    def start(self):
        threading.Thread(target=self.update, daemon=True).start()
        return self

    def update(self):
        while not self.stopped:
            if not self.stream.isOpened():
                time.sleep(0.1)
                continue

            try:
                ret, frame = self.stream.read()
            except cv2.error:
                time.sleep(0.2)
                continue
            if ret:
                self._guardar(frame)
            else:
                time.sleep(0.01)

    def _guardar(self, frame):
        self.frame = frame
        self.preview = redimensionar_para_analise(frame, 640)

    def read(self):
        return self.frame

    def stop(self):
        self.stopped = True
        self.stream.release()


class DetectorArma:
    """Detecção opcional de arma de fogo com modelo YOLO dedicado."""

    def __init__(self, caminho_modelo):
        self.disponivel = False
        self.model = None

        if os.path.exists(caminho_modelo):
            try:
                self.model = YOLO(caminho_modelo)
                self.disponivel = True
                print(f"Modelo de arma carregado: {caminho_modelo}")
            except Exception as exc:
                print(f"Falha ao carregar modelo de arma ({caminho_modelo}): {exc}")
        else:
            print(
                f"Modelo de arma não encontrado ({caminho_modelo}). "
                "Detecção de arma de fogo desabilitada."
            )

    def detectar(self, frame):
        if not self.disponivel:
            return []

        results = self.model.predict(frame, conf=CONF_ARMA_MINIMA, verbose=False)
        armas = []
        boxes = results[0].boxes
        if boxes is None:
            return armas

        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().tolist())
            conf = float(box.conf[0].item())
            cls_id = int(box.cls[0].item())
            nome = self.model.names.get(cls_id, "Arma")
            armas.append({
                "bbox": (x1, y1, x2, y2),
                "centro": ((x1 + x2) / 2, (y1 + y2) / 2),
                "confianca": conf,
                "classe": nome
            })
        return armas


class PoseAnalyzer:
    """Extrai landmarks corporais (MediaPipe Pose Landmarker) por recorte de pessoa."""

    LANDMARKS = {
        "ombro_e": 11,
        "ombro_d": 12,
        "cotovelo_e": 13,
        "cotovelo_d": 14,
        "pulso_e": 15,
        "pulso_d": 16,
        "quadril_e": 23,
        "quadril_d": 24,
        "joelho_e": 25,
        "joelho_d": 26,
        "tornozelo_e": 27,
        "tornozelo_d": 28,
    }

    def __init__(self, caminho_modelo=MODELO_POSE):
        self.disponivel = False
        self.landmarker = None

        if not os.path.exists(caminho_modelo):
            print(f"Modelo de pose não encontrado: {caminho_modelo}")
            return

        try:
            BaseOptions = mp.tasks.BaseOptions
            options = mp.tasks.vision.PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=caminho_modelo),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                num_poses=1,
                min_pose_detection_confidence=0.5,
                min_pose_presence_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self.landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)
            self.disponivel = True
            print(f"Modelo de pose carregado: {caminho_modelo}")
        except Exception as exc:
            print(f"Falha ao iniciar Pose Landmarker: {exc}")

    def processar(self, frame, bbox):
        if not self.disponivel:
            return None

        h, w = frame.shape[:2]
        x1, y1, x2, y2 = map(int, bbox)

        margem_x = int((x2 - x1) * 0.15)
        margem_y = int((y2 - y1) * 0.15)
        x1 = max(0, x1 - margem_x)
        y1 = max(0, y1 - margem_y)
        x2 = min(w, x2 + margem_x)
        y2 = min(h, y2 + margem_y)

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        resultado = self.landmarker.detect(mp_image)

        if not resultado.pose_landmarks:
            return None

        landmarks = resultado.pose_landmarks[0]
        ch, cw = crop.shape[:2]
        pontos = {}
        visiveis = 0

        for nome, idx in self.LANDMARKS.items():
            lm = landmarks[idx]
            if lm.visibility >= CONFIANCA_POSE:
                pontos[nome] = (
                    x1 + lm.x * cw,
                    y1 + lm.y * ch,
                    lm.visibility
                )
                visiveis += 1
            else:
                pontos[nome] = None

        qualidade = visiveis / len(self.LANDMARKS)
        return {"pontos": pontos, "qualidade": qualidade}

    def stop(self):
        if self.landmarker is not None:
            self.landmarker.close()
            self.landmarker = None


class AnaliseComportamental:
    """
    Interpreta pose + trajetória + interações.
    Registra ações e enfatiza eventos de risco.
    """

    def __init__(self, nome_camera, pose_analyzer):
        self.nome = nome_camera
        self.pose = pose_analyzer
        self.historico = defaultdict(lambda: deque(maxlen=HISTORICO_POSICOES))
        self.historico_tronco = defaultdict(lambda: deque(maxlen=30))
        self.inicio_parado = {}
        self.ultima_pose = {}
        self.estado_atual = {}
        self.candidato = {}
        self.confirmacoes = defaultdict(int)
        self.ultimo_registro = {}
        self.unicos_por_classe = defaultdict(set)
        self.acoes_ativas = {}

    @staticmethod
    def _diag(largura, altura):
        return math.hypot(largura, altura) or 1.0

    @staticmethod
    def _xy(ponto):
        if ponto is None:
            return None
        return (ponto[0], ponto[1])

    @staticmethod
    def angulo(a, b, c):
        if a is None or b is None or c is None:
            return None
        ba = np.array(a) - np.array(b)
        bc = np.array(c) - np.array(b)
        denom = np.linalg.norm(ba) * np.linalg.norm(bc)
        if denom == 0:
            return None
        cos_ang = float(np.dot(ba, bc) / denom)
        cos_ang = max(-1.0, min(1.0, cos_ang))
        return math.degrees(math.acos(cos_ang))

    def _cooldown(self, risco):
        if risco in ("Prioritario", "Critico"):
            return COOLDOWN_RISCO_SEG
        return COOLDOWN_INFO_SEG

    def _pode_registrar(self, chave, agora, risco):
        ultimo = self.ultimo_registro.get(chave)
        if ultimo is None:
            return True
        return (agora - ultimo) >= self._cooldown(risco)

    def _deslocamento(self, track_id, janela_seg, diagonal):
        hist = self.historico.get(track_id)
        if not hist or len(hist) < 2:
            return None
        agora = hist[-1][0]
        pontos = [p for t, p in hist if agora - t <= janela_seg]
        if len(pontos) < 2:
            return None
        xs = [p[0] for p in pontos]
        ys = [p[1] for p in pontos]
        return math.hypot(max(xs) - min(xs), max(ys) - min(ys)) / diagonal

    def _velocidade(self, track_id, janela_seg, diagonal):
        hist = self.historico.get(track_id)
        if not hist or len(hist) < 2:
            return 0.0
        agora = hist[-1][0]
        pontos = [(t, p) for t, p in hist if agora - t <= janela_seg]
        if len(pontos) < 2:
            return 0.0
        (t0, p0), (t1, p1) = pontos[0], pontos[-1]
        dt = max(t1 - t0, 1e-3)
        return (math.dist(p0, p1) / diagonal) / dt

    def _classificar_pose(self, pontos, velocidade):
        ombro_e = self._xy(pontos.get("ombro_e"))
        ombro_d = self._xy(pontos.get("ombro_d"))
        quadril_e = self._xy(pontos.get("quadril_e"))
        quadril_d = self._xy(pontos.get("quadril_d"))
        joelho_e = self._xy(pontos.get("joelho_e"))
        joelho_d = self._xy(pontos.get("joelho_d"))
        tornozelo_e = self._xy(pontos.get("tornozelo_e"))
        tornozelo_d = self._xy(pontos.get("tornozelo_d"))
        pulso_e = self._xy(pontos.get("pulso_e"))
        pulso_d = self._xy(pontos.get("pulso_d"))

        if None in (ombro_e, ombro_d, quadril_e, quadril_d):
            return None

        ombro = ((ombro_e[0] + ombro_d[0]) / 2, (ombro_e[1] + ombro_d[1]) / 2)
        quadril = ((quadril_e[0] + quadril_d[0]) / 2, (quadril_e[1] + quadril_d[1]) / 2)
        altura_tronco = abs(quadril[1] - ombro[1]) or 1.0
        inclinacao = abs(ombro[0] - quadril[0]) / altura_tronco

        ang_joelho_e = self.angulo(quadril_e, joelho_e, tornozelo_e)
        ang_joelho_d = self.angulo(quadril_d, joelho_d, tornozelo_d)
        angulos_joelho = [a for a in (ang_joelho_e, ang_joelho_d) if a is not None]
        ang_joelho = sum(angulos_joelho) / len(angulos_joelho) if angulos_joelho else 170

        # Braços levantados: pulsos acima dos ombros
        bracos = "Bracos_Abaixados"
        if pulso_e is not None and pulso_d is not None:
            if pulso_e[1] < ombro_e[1] - 10 and pulso_d[1] < ombro_d[1] - 10:
                bracos = "Bracos_Levantados"
            elif pulso_e[1] < ombro_e[1] - 10 or pulso_d[1] < ombro_d[1] - 10:
                bracos = "Braco_Levantado"

        # Postura
        if inclinacao > 1.1 or altura_tronco < 25:
            postura = "Deitado"
        elif ang_joelho < 100:
            postura = "Agachado"
        elif ang_joelho < 140:
            postura = "Sentado"
        else:
            postura = "Em_Pe"

        # Locomoção
        if velocidade >= VELOCIDADE_CORRER:
            locomocao = "Correndo"
        elif velocidade >= VELOCIDADE_CAMINHAR:
            locomocao = "Caminhando"
        else:
            locomocao = "Parado"

        return {
            "postura": postura,
            "locomocao": locomocao,
            "bracos": bracos,
            "ombro": ombro,
            "quadril": quadril,
            "altura_tronco": altura_tronco,
            "inclinacao": inclinacao
        }

    def _acao_principal(self, features, parado_prolongado, possivel_queda):
        if possivel_queda:
            return "Possivel_Queda"

        if parado_prolongado:
            return "Permanencia"

        if features["postura"] in ("Agachado", "Deitado", "Sentado"):
            return features["postura"]

        if features["locomocao"] == "Correndo":
            return "Correndo"

        if features["locomocao"] == "Caminhando":
            return "Caminhando"

        if features["bracos"] in ("Bracos_Levantados", "Braco_Levantado"):
            return "Bracos_Levantados"

        return features["postura"]

    def _montar_evento(
        self,
        classe,
        track_id,
        id_alvo="",
        duracao=0,
        confianca=0.6,
        pessoas_envolvidas=1,
        detalhe="",
        qualidade_pose=0.0
    ):
        risco_nome, risco_nivel = RISCO_POR_ACAO.get(classe, ("Informativo", 1))

        if risco_nivel >= 3:
            categoria = "Alerta"
            status = "Verificar"
        elif risco_nivel == 2:
            categoria = "Interacao" if classe in (
                "Aglomeracao", "Interacao_Proxima", "Possivel_Briga"
            ) else "Comportamento"
            status = "Atencao"
        else:
            categoria = "Comportamento"
            status = "Informativo"

        # Interações forçam categoria Interacao
        if classe in ("Aglomeracao", "Interacao_Proxima", "Possivel_Briga"):
            categoria = "Interacao" if risco_nivel < 3 else "Alerta"

        return {
            "categoria": categoria,
            "classe": classe,
            "id": track_id,
            "id_alvo": id_alvo,
            "duracao": round(duracao, 1),
            "confianca": round(confianca, 2),
            "status": status,
            "pessoas_envolvidas": pessoas_envolvidas,
            "detalhe": detalhe,
            "risco": risco_nome,
            "nivel_risco": risco_nivel,
            "qualidade_pose": round(qualidade_pose, 2)
        }

    def _confirmar_e_registrar(self, chave_conf, chave_cd, agora, risco, builder):
        self.confirmacoes[chave_conf] += 1
        if self.confirmacoes[chave_conf] < FRAMES_CONFIRMACAO:
            return None
        if not self._pode_registrar(chave_cd, agora, risco):
            return None
        self.ultimo_registro[chave_cd] = agora
        evento = builder()
        self.unicos_por_classe[evento["classe"]].add(
            (evento["id"], str(evento.get("id_alvo", "")))
        )
        self.acoes_ativas[evento["id"]] = evento["classe"]
        return evento

    def analisar_pessoa(self, track_id, frame, bbox, centro, agora, diagonal):
        self.historico[track_id].append((agora, centro))
        velocidade = self._velocidade(track_id, 1.2, diagonal)

        # Throttle de pose
        ultima = self.ultima_pose.get(track_id, 0)
        if agora - ultima < INTERVALO_POSE:
            return None, velocidade, 0.0

        self.ultima_pose[track_id] = agora
        pose = self.pose.processar(frame, bbox)
        if pose is None:
            # fallback só com trajetória
            if velocidade >= VELOCIDADE_CORRER:
                acao = "Correndo"
            elif velocidade >= VELOCIDADE_CAMINHAR:
                acao = "Caminhando"
            else:
                acao = "Em_Pe"
            return {"acao": acao, "features": None}, velocidade, 0.0

        features = self._classificar_pose(pose["pontos"], velocidade)
        if features is None:
            return None, velocidade, pose["qualidade"]

        self.historico_tronco[track_id].append(
            (agora, features["ombro"][1], features["altura_tronco"], features["postura"])
        )

        # Permanência
        desloc = self._deslocamento(track_id, TEMPO_PARADO_SEG, diagonal)
        parado_prolongado = False
        duracao_parado = 0.0
        if desloc is not None and desloc <= DESLOCAMENTO_PARADO:
            inicio = self.inicio_parado.get(track_id, agora)
            self.inicio_parado[track_id] = inicio
            duracao_parado = agora - inicio
            parado_prolongado = duracao_parado >= TEMPO_PARADO_SEG
        else:
            self.inicio_parado.pop(track_id, None)

        # Queda: tronco cai rapidamente e fica deitado/agachado
        possivel_queda = False
        hist_t = self.historico_tronco[track_id]
        if len(hist_t) >= 5:
            y0 = hist_t[0][1]
            y1 = hist_t[-1][1]
            dt = max(hist_t[-1][0] - hist_t[0][0], 1e-3)
            queda_y = (y1 - y0) / diagonal
            if queda_y > 0.08 and (y1 - y0) / dt > 0.12:
                if features["postura"] in ("Deitado", "Agachado"):
                    possivel_queda = True

        # Transição levantando
        if len(hist_t) >= 4:
            posturas = [p[3] for p in list(hist_t)[-4:]]
            if posturas[0] in ("Deitado", "Agachado") and posturas[-1] == "Em_Pe":
                acao = "Levantando"
                return {
                    "acao": acao,
                    "features": features,
                    "duracao_parado": duracao_parado,
                    "qualidade": pose["qualidade"]
                }, velocidade, pose["qualidade"]

        acao = self._acao_principal(features, parado_prolongado, possivel_queda)
        return {
            "acao": acao,
            "features": features,
            "duracao_parado": duracao_parado,
            "qualidade": pose["qualidade"]
        }, velocidade, pose["qualidade"]

    def analisar(self, frame, pessoas, armas, largura, altura, agora=None):
        agora = agora or time.time()
        diagonal = self._diag(largura, altura)
        eventos = []
        ativos = defaultdict(int)
        velocidades = {}

        # Limita custo de pose: pessoas maiores primeiro
        ordenadas = sorted(
            pessoas.items(),
            key=lambda item: (
                (item[1]["bbox"][2] - item[1]["bbox"][0]) *
                (item[1]["bbox"][3] - item[1]["bbox"][1])
            ),
            reverse=True
        )

        for idx, (track_id, info) in enumerate(ordenadas):
            if idx >= MAX_PESSOAS_POSE:
                # ainda atualiza trajetória
                self.historico[track_id].append((agora, info["centro"]))
                velocidades[track_id] = self._velocidade(track_id, 1.2, diagonal)
                continue

            resultado, velocidade, _qualidade = self.analisar_pessoa(
                track_id,
                frame,
                info["bbox"],
                info["centro"],
                agora,
                diagonal
            )
            velocidades[track_id] = velocidade

            if resultado is None:
                continue

            acao = resultado["acao"]
            ativos[acao] += 1
            qualidade = resultado.get("qualidade", 0.0)
            duracao = resultado.get("duracao_parado", 0.0)

            # Máquina de estados: registra mudança confirmada de ação
            atual = self.estado_atual.get(track_id)
            cand = self.candidato.get(track_id)

            if cand != acao:
                self.candidato[track_id] = acao
                self.confirmacoes[("acao", track_id)] = 1
            else:
                self.confirmacoes[("acao", track_id)] += 1

            if (
                self.confirmacoes[("acao", track_id)] >= FRAMES_CONFIRMACAO
                and acao != atual
            ):
                risco_nome, _ = RISCO_POR_ACAO.get(acao, ("Informativo", 1))
                chave_cd = ("acao", track_id, acao)
                if self._pode_registrar(chave_cd, agora, risco_nome):
                    self.ultimo_registro[chave_cd] = agora
                    self.estado_atual[track_id] = acao
                    self.unicos_por_classe[acao].add((track_id, ""))
                    self.acoes_ativas[track_id] = acao

                    conf = 0.55 + 0.35 * qualidade
                    if acao in ("Correndo", "Caminhando", "Permanencia"):
                        conf = max(conf, 0.65)
                    if acao == "Possivel_Queda":
                        conf = 0.6

                    detalhe = acao
                    if resultado.get("features"):
                        f = resultado["features"]
                        detalhe = (
                            f"postura={f['postura']};"
                            f"loco={f['locomocao']};"
                            f"bracos={f['bracos']}"
                        )

                    eventos.append(self._montar_evento(
                        acao,
                        track_id,
                        duracao=duracao if acao == "Permanencia" else 0,
                        confianca=conf,
                        detalhe=detalhe,
                        qualidade_pose=qualidade
                    ))

        ids = list(pessoas.keys())

        # Interação próxima
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                id_a, id_b = ids[i], ids[j]
                dist = math.dist(
                    pessoas[id_a]["centro"],
                    pessoas[id_b]["centro"]
                ) / diagonal

                if dist > DISTANCIA_INTERACAO:
                    self.confirmacoes[("Interacao_Proxima", id_a, id_b)] = 0
                    self.confirmacoes[("Possivel_Briga", id_a, id_b)] = 0
                    continue

                ativos["Interacao_Proxima"] += 1
                vel_a = velocidades.get(id_a, 0.0)
                vel_b = velocidades.get(id_b, 0.0)
                abrupto = vel_a >= VELOCIDADE_BRIGA and vel_b >= VELOCIDADE_BRIGA

                if abrupto and dist <= DISTANCIA_BRIGA:
                    ativos["Possivel_Briga"] += 1
                    ev = self._confirmar_e_registrar(
                        ("Possivel_Briga", id_a, id_b),
                        ("Possivel_Briga", tuple(sorted((id_a, id_b)))),
                        agora,
                        "Prioritario",
                        lambda: self._montar_evento(
                            "Possivel_Briga",
                            id_a,
                            id_alvo=id_b,
                            confianca=0.58,
                            pessoas_envolvidas=2,
                            detalhe=f"dist={dist:.3f};vel={max(vel_a, vel_b):.3f}"
                        )
                    )
                    if ev:
                        eventos.append(ev)
                else:
                    ev = self._confirmar_e_registrar(
                        ("Interacao_Proxima", id_a, id_b),
                        ("Interacao_Proxima", tuple(sorted((id_a, id_b)))),
                        agora,
                        "Atencao",
                        lambda: self._montar_evento(
                            "Interacao_Proxima",
                            id_a,
                            id_alvo=id_b,
                            confianca=0.65,
                            pessoas_envolvidas=2,
                            detalhe=f"dist={dist:.3f}"
                        )
                    )
                    if ev:
                        eventos.append(ev)

        # Aglomeração
        if len(ids) >= MIN_PESSOAS_AGLOMERACAO:
            visitado = set()
            for i, id_a in enumerate(ids):
                if id_a in visitado:
                    continue
                cluster = [id_a]
                for id_b in ids[i + 1:]:
                    dist = math.dist(
                        pessoas[id_a]["centro"],
                        pessoas[id_b]["centro"]
                    ) / diagonal
                    if dist <= DISTANCIA_AGLOMERACAO:
                        cluster.append(id_b)

                if len(cluster) >= MIN_PESSOAS_AGLOMERACAO:
                    for pid in cluster:
                        visitado.add(pid)
                    ativos["Aglomeracao"] += 1
                    cluster_t = tuple(sorted(cluster))
                    ev = self._confirmar_e_registrar(
                        ("Aglomeracao", cluster_t),
                        ("Aglomeracao", cluster_t),
                        agora,
                        "Atencao",
                        lambda c=cluster: self._montar_evento(
                            "Aglomeracao",
                            c[0],
                            id_alvo=",".join(str(x) for x in c[1:]),
                            confianca=0.7,
                            pessoas_envolvidas=len(c),
                            detalhe=f"cluster={len(c)}"
                        )
                    )
                    if ev:
                        eventos.append(ev)

        # Arma de fogo
        if not armas:
            for k in list(self.confirmacoes.keys()):
                if isinstance(k, tuple) and k and k[0] == "Possivel_Arma_Fogo":
                    self.confirmacoes[k] = 0
        else:
            for arma in armas:
                pessoa_proxima = None
                menor = 1e9
                for track_id, info in pessoas.items():
                    dist = math.dist(arma["centro"], info["centro"]) / diagonal
                    if dist < menor:
                        menor = dist
                        pessoa_proxima = track_id

                chave_pessoa = pessoa_proxima if (
                    pessoa_proxima is not None and menor <= 0.20
                ) else "cena"
                ativos["Possivel_Arma_Fogo"] += 1
                ev = self._confirmar_e_registrar(
                    ("Possivel_Arma_Fogo", chave_pessoa),
                    ("Possivel_Arma_Fogo", chave_pessoa),
                    agora,
                    "Critico",
                    lambda: self._montar_evento(
                        "Possivel_Arma_Fogo",
                        "" if chave_pessoa == "cena" else chave_pessoa,
                        confianca=float(arma["confianca"]),
                        pessoas_envolvidas=0 if chave_pessoa == "cena" else 1,
                        detalhe=f"{arma['classe']};dist={menor:.3f}"
                    )
                )
                if ev:
                    eventos.append(ev)

        return eventos, dict(ativos)

    def total_unicos_classe(self, classe):
        return len(self.unicos_por_classe[classe])

    def stop(self):
        self.pose.stop()


class CameraAnalitica:

    def __init__(
        self,
        nome,
        src,
        detector_arma=None,
        pose_analyzer=None,
        identificador_faces=None,
        identificador_placas=None,
        modelo="",
        captura=None,
        quadro=None,
    ):
        self.nome = nome
        self.modelo = modelo or ""
        self.perfil = perfil_camera(self.modelo)
        self.stream = CameraStream(src, captura=captura, quadro=quadro)
        try:
            self.model = YOLO(MODELO_YOLO)
            self.detector_arma = detector_arma or DetectorArma(MODELO_ARMA)
            self.pose = pose_analyzer or PoseAnalyzer(MODELO_POSE)
            self.faces = identificador_faces
            self.placas = identificador_placas
            self.ids_vistos = set()
            self.unicos_por_categoria = defaultdict(set)
            self.estabilidade = {}
            self.origem_veiculo = {}
            self._fps = 0.0
            self._ultimo_quadro = time.time()
            self.comportamento = AnaliseComportamental(nome, self.pose)
            self._parar_analise = threading.Event()
            self._trava = threading.Lock()
            self._pendentes = []
            self._visao = {
                "fps": 0.0,
                "pessoas_cena": 0,
                "veiculos_cena": 0,
                "passagens_pessoa": 0,
                "passagens_veiculo": 0,
                "faces": 0,
                "placas": 0,
                "comportamentos": [],
                "riscos": {1: 0, 2: 0, 3: 0, 4: 0},
                "alerta": None,
                "anotacoes": [],
                "quando": 0.0,
                "match": None,
            }
            self._match = None
        except Exception:
            self.stream.stop()
            raise
        self.stream.start()
        self._analise = threading.Thread(
            target=self._analisar_continuo, name=f"analise-{nome}", daemon=True
        )
        self._analise.start()

    def _analisar_continuo(self):
        while not self._parar_analise.is_set():
            try:
                resultado = self.process(False)
            except Exception as exc:
                print(f"Análise de {self.nome} interrompida neste quadro: {exc}")
                time.sleep(0.2)
                continue
            _out, eventos, cena, comp, ativos, faces, placas = resultado
            with self._trava:
                self._pendentes.append((eventos, cena, comp, ativos, faces, placas))

    def retirar_resultados(self):
        with self._trava:
            pacotes = self._pendentes
            self._pendentes = []
            visao = dict(self._visao)
            visao["anotacoes"] = list(self._visao["anotacoes"])
        return pacotes, visao

    def classificar(self, cls_id):
        if cls_id == CLASSE_PESSOA:
            return "Pessoa"
        if cls_id in CLASSES_VEICULOS:
            return "Veiculo"
        if cls_id in CLASSES_ANIMAIS:
            return "Animal"
        return "Objeto"

    def nome_classe(self, cls_id):
        if cls_id in CLASSES_VEICULOS:
            return CLASSES_VEICULOS[cls_id]
        if cls_id in CLASSES_ANIMAIS:
            return CLASSES_ANIMAIS[cls_id]
        return self.model.names.get(cls_id, f"Classe_{cls_id}")

    def process(self, exibir=True):
        vazio = (None, [], {}, [], {}, [], [])
        frame = self.stream.read()
        if frame is None:
            return vazio
        frame = frame.copy()

        agora = time.time()
        intervalo = agora - self._ultimo_quadro
        self._ultimo_quadro = agora
        if intervalo > 0:
            self._fps = (0.85 * self._fps) + (0.15 * (1.0 / intervalo))

        original = frame
        frame = redimensionar_para_analise(frame, self.perfil["lado"])
        altura, largura = frame.shape[:2]
        escala_x = original.shape[1] / max(largura, 1)
        escala_y = original.shape[0] / max(altura, 1)
        conf_pessoa = self.perfil["conf"]
        conf_veiculo = self.perfil["conf_veiculo"]
        frames_veiculo = self.perfil["frames_veiculo"]
        diagonal = math.hypot(largura, altura) or 1.0

        results = self.model.track(
            frame,
            conf=min(conf_pessoa, conf_veiculo),
            imgsz=self.perfil["lado"],
            classes=CLASSES_ANALISE,
            max_det=30,
            persist=True,
            tracker=TRACKER,
            verbose=False
        )

        boxes = results[0].boxes
        if boxes is None:
            self.estabilidade.clear()
            self.origem_veiculo.clear()
            if not exibir:
                return (None, [], {}, [], {}, [], [])
            frame = self._compor_painel(frame, defaultdict(int), [], [], [])
            return (frame, [], {}, [], {}, [], [])

        if boxes.id is not None:
            ids = boxes.id.int().cpu().tolist()
        else:
            ids = [None] * len(boxes)

        quantidade_cena = defaultdict(int)
        novos_eventos = []
        pessoas_cena = {}
        veiculos_cena = {}
        presentes = set()
        anotacoes = []

        for box, track_id in zip(boxes, ids):
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().tolist())
            categoria = self.classificar(cls_id)
            if categoria not in ("Pessoa", "Veiculo"):
                continue
            if categoria == "Veiculo" and conf < conf_veiculo:
                continue
            if categoria == "Pessoa" and conf < conf_pessoa:
                continue
            nome = self.nome_classe(cls_id)

            centro = ((x1 + x2) / 2, (y1 + y2) / 2)
            if categoria == "Veiculo":
                if track_id is None or (x2 - x1) < LADO_MINIMO_VEICULO or (y2 - y1) < 16:
                    continue
                presentes.add(track_id)
                self.estabilidade[track_id] = self.estabilidade.get(track_id, 0) + 1
                # Um carro nítido conta no primeiro quadro. O quadro fraco espera repetir,
                # para uma caixa piscando não virar passagem quando a imagem congela.
                nitido = conf >= 0.48 and (x2 - x1) >= 36
                if self.estabilidade[track_id] < frames_veiculo and not nitido:
                    continue
                passou = True
            elif track_id is None:
                grade = (int(centro[0] // 48), int(centro[1] // 48))
                chave_grade = ("pessoa", grade)
                passou = chave_grade not in self.ids_vistos
                if passou:
                    self.ids_vistos.add(chave_grade)
            else:
                passou = True

            quantidade_cena[categoria] += 1

            chave = (categoria, cls_id, track_id)
            if passou and track_id is None and categoria == "Pessoa":
                self.unicos_por_categoria[categoria].add(chave_grade)
                novos_eventos.append((categoria, nome, f"{grade[0]}-{grade[1]}"))
            elif passou and track_id is not None and chave not in self.ids_vistos:
                self.ids_vistos.add(chave)
                self.unicos_por_categoria[categoria].add(chave)
                novos_eventos.append((categoria, nome, track_id))

            if categoria == "Pessoa" and track_id is not None:
                pessoas_cena[track_id] = {
                    "centro": ((x1 + x2) / 2, (y1 + y2) / 2),
                    "bbox": (x1, y1, x2, y2)
                }

            if categoria == "Veiculo" and track_id is not None:
                veiculos_cena[track_id] = {
                    "centro": ((x1 + x2) / 2, (y1 + y2) / 2),
                    "bbox": (x1, y1, x2, y2),
                    "bbox_nitida": (
                        int(x1 * escala_x),
                        int(y1 * escala_y),
                        int(x2 * escala_x),
                        int(y2 * escala_y),
                    ),
                    "classe": nome
                }

            cor = CORES[categoria]
            rotulo = f"{nome} #{track_id}" if track_id is not None else nome
            acao = self.comportamento.acoes_ativas.get(track_id)
            if categoria == "Pessoa" and acao:
                rotulo = f"{rotulo} | {acao}"
            anotacoes.append((x1, y1, x2, y2, rotulo, cor))
            if exibir:
                cv2.rectangle(frame, (x1, y1), (x2, y2), cor, 2)
                cv2.putText(
                    frame, rotulo, (x1, max(y1 - 5, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, cor, 2
                )

        for track_id in list(self.estabilidade):
            if track_id not in presentes:
                self.estabilidade[track_id] = self.estabilidade.get(track_id, 1) - 1
                if self.estabilidade[track_id] <= 0:
                    self.estabilidade.pop(track_id, None)
                    self.origem_veiculo.pop(track_id, None)

        armas = self.detector_arma.detectar(frame)
        if exibir:
            for arma in armas:
                x1, y1, x2, y2 = arma["bbox"]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(
                    frame, f"ARMA {arma['confianca']:.2f}",
                    (x1, max(y1 - 8, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2
                )

        eventos_comp, ativos_comp = self.comportamento.analisar(
            frame, pessoas_cena, armas, largura, altura
        )

        eventos_faces, anot_faces = ([], [])
        if self.faces is not None:
            eventos_faces, anot_faces = self.faces.processar(
                self.nome, frame, pessoas_cena
            )

        eventos_placas, anot_placas = ([], [])
        if self.placas is not None:
            eventos_placas, anot_placas = self.placas.processar(
                self.nome, frame, veiculos_cena, frame_nitido=original
            )

        if exibir:
            for an in anot_faces:
                x1, y1, x2, y2 = an["bbox"]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 2)
                cv2.putText(
                    frame, an["rotulo"], (x1, max(y1 - 5, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2
                )

            for an in anot_placas:
                x1, y1, x2, y2 = an["bbox"]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
                cv2.putText(
                    frame, an["rotulo"], (x1, max(y1 - 5, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2
                )

            frame = self._compor_painel(
                frame, quantidade_cena, eventos_comp, eventos_faces, eventos_placas
            )
        else:
            frame = None

        self._definir_match(eventos_faces, eventos_placas)
        with self._trava:
            self._visao = {
                "fps": self._fps,
                "pessoas_cena": quantidade_cena["Pessoa"],
                "veiculos_cena": quantidade_cena["Veiculo"],
                "objetos_cena": quantidade_cena.get("Objeto", 0),
                "animais_cena": quantidade_cena.get("Animal", 0),
                "passagens_pessoa": len(self.unicos_por_categoria["Pessoa"]),
                "passagens_veiculo": len(self.unicos_por_categoria["Veiculo"]),
                "passagens_objeto": len(self.unicos_por_categoria["Objeto"]),
                "passagens_animal": len(self.unicos_por_categoria["Animal"]),
                "faces": len(eventos_faces),
                "placas": len(eventos_placas),
                "comportamentos": resumir_comportamento(
                    self.comportamento.unicos_por_classe,
                    self.comportamento.acoes_ativas,
                ),
                "riscos": resumir_risco(self.comportamento.unicos_por_classe),
                "alerta": None,
                "anotacoes": anotacoes,
                "quando": time.time(),
                "match": self._match if self._match and time.time() <= self._match.get("ate", 0) else None,
                "centros_pessoa": [list(item["centro"]) for item in pessoas_cena.values() if item.get("centro")],
                "centros_veiculo": [list(item["centro"]) for item in veiculos_cena.values() if item.get("centro")],
            }
            if eventos_comp:
                ev = max(eventos_comp, key=lambda item: item["nivel_risco"])
                self._visao["alerta"] = (
                    f"{ev['risco'].upper()}  {ev['classe']}  ID {ev['id']}",
                    CORES_RISCO.get(ev["risco"], (0, 0, 255)),
                )

        return (
            frame,
            novos_eventos,
            dict(quantidade_cena),
            eventos_comp,
            ativos_comp,
            eventos_faces,
            eventos_placas
        )

    def _compor_painel(self, frame, quantidade_cena, eventos_comp, eventos_faces, eventos_placas):
        alerta = None
        if eventos_comp:
            ev = max(eventos_comp, key=lambda item: item["nivel_risco"])
            cor = CORES_RISCO.get(ev["risco"], (0, 0, 255))
            alerta = (f"{ev['risco'].upper()}  {ev['classe']}  ID {ev['id']}", cor)
        return desenhar_painel(
            frame,
            nome=self.nome,
            fps=self._fps,
            pessoas_cena=quantidade_cena["Pessoa"],
            veiculos_cena=quantidade_cena["Veiculo"],
            passagens_pessoa=len(self.unicos_por_categoria["Pessoa"]),
            passagens_veiculo=len(self.unicos_por_categoria["Veiculo"]),
            faces=len(eventos_faces),
            placas=len(eventos_placas),
            comportamentos=resumir_comportamento(
                self.comportamento.unicos_por_classe,
                self.comportamento.acoes_ativas,
            ),
            riscos=resumir_risco(self.comportamento.unicos_por_classe),
            alerta=alerta,
        )

    def _definir_match(self, eventos_faces, eventos_placas):
        agora = time.time()
        if self._match and agora > self._match.get("ate", 0):
            self._match = None
        try:
            from cadastro import interesse_ativo
            interesse = interesse_ativo()
        except Exception:
            return
        nomes_face = {
            str(pessoa.get("face_id") or ""): str(pessoa.get("nome") or "")
            for pessoa in interesse.get("pessoas") or []
            if pessoa.get("face_id")
        }
        nomes_placa = {
            str(veiculo.get("placa") or "").upper(): str(veiculo.get("nome") or "")
            for veiculo in interesse.get("veiculos") or []
            if veiculo.get("placa")
        }
        face = None
        for ev in eventos_faces or []:
            ident = str(ev.get("face_id") or "")
            if ident not in nomes_face:
                continue
            taxa = ev.get("similaridade")
            if taxa is None:
                taxa = ev.get("confianca") or 0
            face = _montar_match(
                "FACE", ident, nomes_face[ident], float(taxa), "SIM",
                ev.get("foto_referencia"), ev.get("caminho_foto"), agora,
            )
        placa = None
        for ev in eventos_placas or []:
            ident = str(ev.get("placa") or "").upper()
            if ident not in nomes_placa:
                continue
            sim = ev.get("similaridade")
            if sim is None:
                taxa, rotulo = float(ev.get("confianca") or 0), "LEIT"
            else:
                taxa, rotulo = float(sim), "SIM"
            placa = _montar_match(
                "PLACA", ident, nomes_placa[ident], taxa, rotulo,
                ev.get("foto_referencia"), ev.get("caminho_foto"), agora,
            )
        if face:
            self._match = face
        elif placa:
            self._match = placa

    def total_unicos_categoria(self, categoria):
        return len(self.unicos_por_categoria[categoria])

    def stop(self):
        self._parar_analise.set()
        if getattr(self, "_analise", None) is not None and self._analise.is_alive():
            self._analise.join(timeout=2)
        self.stream.stop()
        self.comportamento.stop()


# ===================== ARQUIVO CSV =====================

def inicializar_csv():
    cabecalho = [
        "Data", "Hora", "Camera", "Categoria", "Classe", "ID",
        "Total_Unicos_Categoria", "Quantidade_Categoria_Na_Cena"
    ]

    if not os.path.exists(ARQUIVO_HISTORICO):
        with open(ARQUIVO_HISTORICO, mode="w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f, delimiter=";").writerow(cabecalho)
        print("Histórico analítico criado.")
    else:
        print("Histórico existente. Novos registros serão anexados.")


def inicializar_csv_ocorrencias():
    cabecalho = [
        "Data",
        "Hora",
        "Camera",
        "Categoria",
        "Classe",
        "ID",
        "Total_Unicos_Categoria",
        "Quantidade_Categoria_Na_Cena",
        "ID_Alvo",
        "Duracao_Segundos",
        "Confianca",
        "Status",
        "Pessoas_Envolvidas",
        "Detalhe",
        "Risco",
        "Nivel_Risco",
        "Qualidade_Pose"
    ]

    if not os.path.exists(ARQUIVO_OCORRENCIAS):
        with open(ARQUIVO_OCORRENCIAS, mode="w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f, delimiter=";").writerow(cabecalho)
        print("Histórico de ocorrências comportamentais criado.")
    else:
        # Se o arquivo antigo existir sem as colunas de risco, cria um novo complementar
        with open(ARQUIVO_OCORRENCIAS, mode="r", encoding="utf-8-sig") as f:
            primeira = f.readline().strip()
        if "Nivel_Risco" not in primeira:
            backup = ARQUIVO_OCORRENCIAS.replace(
                ".csv",
                f"_legado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            os.rename(ARQUIVO_OCORRENCIAS, backup)
            with open(ARQUIVO_OCORRENCIAS, mode="w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f, delimiter=";").writerow(cabecalho)
            print(
                "Ocorrências antigas arquivadas em "
                f"{backup}. Novo arquivo com classificação de risco criado."
            )
        else:
            print("Ocorrências existentes. Novos registros serão anexados.")


def salvar_evento(camera, categoria, classe, track_id, total_unicos, quantidade_cena):
    agora = datetime.now()
    linha = [
        agora.strftime("%Y-%m-%d"),
        agora.strftime("%H:%M:%S"),
        camera,
        categoria,
        classe,
        track_id,
        total_unicos,
        quantidade_cena
    ]
    with open(ARQUIVO_HISTORICO, mode="a", newline="", encoding="utf-8-sig") as f:
        csv.writer(f, delimiter=";").writerow(linha)
    print(
        f"[{linha[1]}] {camera} | {categoria}: {classe} | "
        f"ID {track_id} | Total únicos: {total_unicos}"
    )


def salvar_ocorrencia(
    camera,
    categoria,
    classe,
    track_id,
    total_unicos,
    quantidade_cena,
    id_alvo="",
    duracao=0,
    confianca=0,
    status="Detectado",
    pessoas_envolvidas=1,
    detalhe="",
    risco="Informativo",
    nivel_risco=1,
    qualidade_pose=0.0
):
    agora = datetime.now()
    linha = [
        agora.strftime("%Y-%m-%d"),
        agora.strftime("%H:%M:%S"),
        camera,
        categoria,
        classe,
        track_id,
        total_unicos,
        quantidade_cena,
        id_alvo,
        duracao,
        confianca,
        status,
        pessoas_envolvidas,
        detalhe,
        risco,
        nivel_risco,
        qualidade_pose
    ]
    with open(ARQUIVO_OCORRENCIAS, mode="a", newline="", encoding="utf-8-sig") as f:
        csv.writer(f, delimiter=";").writerow(linha)

    print(
        f"[{linha[1]}] OCORRENCIA {camera} | "
        f"Risco {risco}/{nivel_risco} | {categoria}/{classe} | "
        f"ID {track_id} | alvo {id_alvo}"
    )


# ===================== EXECUÇÃO =====================

JANELA_CONTROLE = "ANALITICO"


_JANELAS_PREPARADAS = set()


def _tamanho_inicial(largura, altura):
    """Cabe no monitor atual. Depois o operador estica para o video wall."""
    tela_w = ctypes.windll.user32.GetSystemMetrics(0)
    tela_h = ctypes.windll.user32.GetSystemMetrics(1)
    if tela_w <= 0 or tela_h <= 0:
        return largura, altura
    limite_w = int(tela_w * 0.92)
    limite_h = int(tela_h * 0.92)
    if largura <= limite_w and altura <= limite_h:
        return largura, altura
    escala = min(limite_w / max(largura, 1), limite_h / max(altura, 1))
    return max(320, int(largura * escala)), max(180, int(altura * escala))


def mostrar_janela(titulo, imagem):
    if titulo not in _JANELAS_PREPARADAS:
        cv2.namedWindow(
            titulo,
            cv2.WINDOW_NORMAL | cv2.WINDOW_FREERATIO | cv2.WINDOW_GUI_NORMAL,
        )
        try:
            cv2.setWindowProperty(titulo, cv2.WND_PROP_ASPECT_RATIO, cv2.WINDOW_FREERATIO)
        except Exception:
            pass
        altura, largura = imagem.shape[:2]
        largura, altura = _tamanho_inicial(largura, altura)
        cv2.resizeWindow(titulo, largura, altura)
        _JANELAS_PREPARADAS.add(titulo)
    cv2.imshow(titulo, imagem)


def fechar_janela(titulo):
    _JANELAS_PREPARADAS.discard(titulo)
    try:
        cv2.destroyWindow(titulo)
    except Exception:
        pass


def _titulo_em_foco():
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return ""
    tamanho = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    if tamanho <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(tamanho + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, tamanho + 1)
    return buffer.value


def alternar_tela_cheia():
    titulo = _titulo_em_foco()
    if titulo not in _JANELAS_PREPARADAS:
        return
    try:
        atual = cv2.getWindowProperty(titulo, cv2.WND_PROP_FULLSCREEN)
        destino = cv2.WINDOW_NORMAL if atual >= 1 else cv2.WINDOW_FULLSCREEN
        cv2.setWindowProperty(titulo, cv2.WND_PROP_FULLSCREEN, destino)
    except Exception:
        pass


def _fechar_janelas(titulos):
    for titulo in list(titulos):
        fechar_janela(titulo)
    titulos.clear()


def titulo_janela(nome):
    return f"Analitico - {nome}"


def _encerrar_camera(item):
    analitica = item["analitica"]
    print(f"Câmera encerrada: {analitica.nome}")
    audio = item.get("audio")
    if audio is not None:
        audio.stop()
    analitica.stop()
    fechar_janela(titulo_janela(item["janela"]))


def _copiar_local(destino, cfg):
    destino["rua"] = cfg.get("rua") or ""
    destino["bairro"] = cfg.get("bairro") or ""
    destino["cidade"] = cfg.get("cidade") or ""
    destino["latitude"] = cfg.get("latitude")
    destino["longitude"] = cfg.get("longitude")


def aplicar_cameras(desejadas, estado, detector_arma, id_faces, id_placas, avisos_offline):
    """Abre câmeras novas e fecha as que saíram da lista ou trocaram de acesso."""
    por_id = {camera["id"]: camera for camera in desejadas}

    for ident in list(estado):
        atual = estado[ident]
        nova = por_id.get(ident)
        if nova is None or nova["url"] != atual["url"]:
            _encerrar_camera(atual)
            del estado[ident]

    for ident, cfg in por_id.items():
        if ident in estado:
            atual = estado[ident]
            _copiar_local(atual, cfg)
            if cfg.get("modelo") != atual.get("modelo"):
                atual["modelo"] = cfg.get("modelo") or ""
                atual["analitica"].modelo = atual["modelo"]
                atual["analitica"].perfil = perfil_camera(atual["modelo"])
            if cfg["nome"] != atual["nome"]:
                fechar_janela(titulo_janela(atual["janela"]))
                atual["analitica"].nome = cfg["nome"]
                atual["analitica"].comportamento.nome = cfg["nome"]
                atual["nome"] = cfg["nome"]
                atual["janela"] = cfg["nome"]
            continue

        captura, quadro = captura_com_quadro(cfg["url"])
        if captura is None:
            if ident not in avisos_offline:
                print(
                    f"{cfg['nome']} offline ({destino_publico(cfg['url'])}). "
                    "O monitoramento segue com as câmeras online."
                )
                avisos_offline.add(ident)
            continue

        perfil = perfil_camera(cfg.get("modelo") or "")
        try:
            analitica = CameraAnalitica(
                cfg["nome"],
                cfg["url"],
                detector_arma,
                PoseAnalyzer(MODELO_POSE),
                id_faces,
                id_placas,
                modelo=cfg.get("modelo") or "",
                captura=captura,
                quadro=quadro,
            )
        except Exception as exc:
            print(f"Falha ao abrir {cfg['nome']}: {exc}")
            continue
        avisos_offline.discard(ident)
        print(
            f"Câmera iniciada: {cfg['nome']} ({destino_publico(cfg['url'])}) "
            f"perfil {cfg.get('modelo') or 'padrao'} | analise {perfil['lado']}px | "
            f"carro a partir de {perfil['conf_veiculo']} em {perfil['frames_veiculo']} quadros"
        )
        estado[ident] = {
            "analitica": analitica,
            "url": cfg["url"],
            "nome": cfg["nome"],
            "modelo": cfg.get("modelo") or "",
            "janela": cfg["nome"],
            "audio": EscutaAudio(cfg["nome"], cfg["url"]).start(),
        }
        _copiar_local(estado[ident], cfg)


def _registrar_saida(cam, eventos, cena, comp, ativos):
    for categoria, classe, track_id in eventos:
        salvar_evento(
            cam.nome, categoria, classe, track_id,
            cam.total_unicos_categoria(categoria),
            cena.get(categoria, 0)
        )

    for ev in comp:
        salvar_ocorrencia(
            cam.nome,
            ev["categoria"],
            ev["classe"],
            ev["id"],
            cam.comportamento.total_unicos_classe(ev["classe"]),
            ativos.get(ev["classe"], 0),
            id_alvo=ev.get("id_alvo", ""),
            duracao=ev.get("duracao", 0),
            confianca=ev.get("confianca", 0),
            status=ev.get("status", "Informativo"),
            pessoas_envolvidas=ev.get("pessoas_envolvidas", 1),
            detalhe=ev.get("detalhe", ""),
            risco=ev.get("risco", "Informativo"),
            nivel_risco=ev.get("nivel_risco", 1),
            qualidade_pose=ev.get("qualidade_pose", 0.0)
        )


def _enderecos_portal(host, porta):
    if host not in ("0.0.0.0", "::", ""):
        return [f"http://{host}:{porta}/"]
    vistos = [f"http://127.0.0.1:{porta}/"]
    try:
        import socket

        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127."):
                continue
            url = f"http://{ip}:{porta}/"
            if url not in vistos:
                vistos.append(url)
    except OSError:
        pass
    return vistos


def _abrir_portal(acervo):
    senha = os.getenv("WEB_SENHA", "").strip()
    if not senha:
        print("Acesso remoto desligado. Defina WEB_SENHA no .env para abrir pelo navegador.")
        return None
    from remoto import Portal

    host = os.getenv("WEB_HOST", "0.0.0.0").strip() or "0.0.0.0"
    porta = int(os.getenv("WEB_PORT", "8787") or "8787")
    portal = Portal(senha, host, porta)
    portal.ligar_acervo(acervo)
    portal.iniciar()
    for url in _enderecos_portal(host, porta):
        print(f"Acesso no navegador: {url}")
    print("De fora de casa, use o túnel. Não abra a porta da câmera no roteador.")
    print("No navegador, entre com o e-mail do usuário. O primeiro acesso cria a conta.")
    return portal


def _quadro_portal(quadro, largura=960):
    if quadro is None or getattr(quadro, "size", 0) == 0:
        return None
    try:
        copia = quadro.copy()
    except Exception:
        return None
    altura, atual = copia.shape[:2]
    if atual > largura and atual > 0:
        nova = max(1, int(round(altura * largura / atual)))
        copia = cv2.resize(copia, (largura, nova), interpolation=cv2.INTER_AREA)
    return copia


def _publicar_cameras(portal, estado, parar):
    """Envia o quadro cheio da câmera várias vezes por segundo, fora do painel."""
    from remoto import slug_camera

    while not parar.is_set():
        catalogo = []
        for item in list(estado.values()):
            slug = slug_camera(item["nome"])
            catalogo.append((slug, item["nome"], item.get("rua") or ""))
            stream = item["analitica"].stream
            quadro = _quadro_portal(getattr(stream, "frame", None))
            if quadro is None:
                continue
            portal.publicar(f"camera-{slug}", quadro)
        portal.definir_cameras(catalogo)
        if parar.wait(0.08):
            break


_FLUXO = {}
_SERIE = deque(maxlen=90)
_NARRACAO = {"chave": "", "texto": "", "pedido": ""}
_ORDEM_LED = {"branco": 0, "verde": 1, "amarelo": 2, "vermelho": 3, "preto": 4}


_FRASES = {
    "Deitado": "uma pessoa deitada",
    "Possivel_Queda": "uma queda identificada",
    "Possivel_Briga": "uma possível briga",
    "Interacao_Proxima": "uma interação próxima",
    "Possivel_Arma_Fogo": "uma arma identificada",
    "Aglomeracao": "uma aglomeração",
}


_PENDENCIAS = {}


def _ids_respondidos():
    from agente.stive import ids_respondidos

    return ids_respondidos()


def _lembrar_pendencia(camera, tipo, texto, agora):
    bloco = int(agora // 1800)
    chave = f"{camera}|{tipo}|{bloco}"
    if chave in _ids_respondidos():
        return
    atual = _PENDENCIAS.get(chave)
    if atual is None:
        _PENDENCIAS[chave] = {"texto": texto, "camera": camera, "tipo": tipo, "expira": agora + 1200}
    else:
        atual["texto"] = texto
        atual["expira"] = agora + 1200


def _pendencias_vivas(cameras):
    agora = time.time()
    for camera in cameras or []:
        nome = camera.get("nome") or "câmera"
        for frase in camera.get("permanencias") or []:
            baixo = frase.lower()
            if "parado" not in baixo and "parada" not in baixo:
                continue
            tipo = "veiculo" if "veículo" in baixo or "veiculo" in baixo else "pessoa"
            pergunta = (
                f"Confirma o veículo que permanece parado na {nome}?"
                if tipo == "veiculo"
                else f"Confirma a pessoa que permanece parada na {nome}?"
            )
            _lembrar_pendencia(nome, tipo, pergunta, agora)
        if "disparo" in (camera.get("frase") or "").lower():
            _lembrar_pendencia(nome, "disparo", f"Houve disparo na {nome}? Pode confirmar para a base?", agora)
    respondidas = _ids_respondidos()
    vivos = []
    for chave, item in list(_PENDENCIAS.items()):
        if chave in respondidas or item["expira"] < agora:
            _PENDENCIAS.pop(chave, None)
            continue
        vivos.append({
            "id": chave,
            "texto": item["texto"],
            "camera": item["camera"],
            "tipo": item["tipo"],
        })
    return vivos[:6]


def _montar_voz(cameras, match, narracao, narracao_ia):
    partes = []
    for camera in cameras or []:
        risco = camera.get("risco") or "branco"
        if risco in ("amarelo", "vermelho", "preto") and camera.get("frase"):
            partes.append(camera["frase"])
        partes.extend(camera.get("permanencias") or [])
        if risco in ("vermelho", "preto") and camera.get("rua"):
            partes.append(f"O ponto é {camera['rua']}, na {camera['nome']}.")
    if match and match.get("tipo") == "FACE":
        quem = match.get("nome") or match.get("id") or "uma pessoa"
        partes.append(
            f"Reconhecimento facial: {quem} na {match.get('camera') or 'câmera'}. "
            f"{narracao_ia or narracao or ''}".strip()
        )
    elif match and match.get("tipo") == "PLACA":
        partes.append(f"Veículo de interesse {match.get('id') or ''} na {match.get('camera') or 'câmera'}.")
    if not partes:
        return "A área está em observação. Nenhum risco acima de informe neste momento."
    return " ".join(parte.strip() for parte in partes if str(parte).strip())


def _frase_camera(nome, visao, audio_suspeito, audio_tipo):
    partes = []
    for item in visao.get("comportamentos") or []:
        if int(item.get("agora") or 0) <= 0:
            continue
        texto = _FRASES.get(item.get("classe") or "")
        if texto and texto not in partes:
            partes.append(texto)
    if audio_suspeito and audio_tipo == "disparo":
        partes.append("um disparo")
    elif audio_suspeito:
        partes.append("uma fala com sinal de briga")
    if not partes:
        return f"{nome} sem comportamento de risco agora."
    return "Existe " + ", ".join(partes) + f" na {nome}. Atenção!"


def _risco_camera(visao, audio_suspeito, tem_interesse, interesse_risco=True):
    acoes = {
        item.get("classe") or item.get("nome"): int(item.get("agora") or 0)
        for item in visao.get("comportamentos") or []
    }
    deitado = acoes.get("Deitado", 0) > 0
    interacao = acoes.get("Interacao_Proxima", 0) > 0 or acoes.get("Possivel_Briga", 0) > 0
    queda = acoes.get("Possivel_Queda", 0) > 0
    briga = acoes.get("Possivel_Briga", 0) > 0
    if deitado and interacao and audio_suspeito:
        return "preto"
    if queda or briga:
        return "vermelho"
    if tem_interesse and interesse_risco:
        return "vermelho"
    if deitado or interacao or audio_suspeito:
        return "amarelo"
    if tem_interesse:
        return "verde"
    return "branco"


def _fluxo_serie(nome, tipo, acumulado):
    agora = time.time()
    fila = _FLUXO.setdefault((nome, tipo), deque())
    delta = 0 if not fila else max(0, int(acumulado) - int(fila[-1][1]))
    fila.append((agora, int(acumulado), delta))
    while fila and agora - fila[0][0] > 3600:
        fila.popleft()
    return {
        "segundo": sum(item[2] for item in fila if agora - item[0] <= 1),
        "minuto": sum(item[2] for item in fila if agora - item[0] <= 60),
        "hora": sum(item[2] for item in fila),
    }


def _fluxo_pessoa(nome, passagens):
    return _fluxo_serie(nome, "pessoa", passagens)


_TRILHAS = {}
_INTERVALO_AVISO_PARADO = 600


def _formatar_duracao(segundos) -> str:
    total = max(0, int(segundos))
    if total < 60:
        return f"{total} segundo{'s' if total != 1 else ''}"
    dias, resto = divmod(total, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, segs = divmod(resto, 60)
    if dias:
        partes = [f"{dias} dia{'s' if dias != 1 else ''}"]
        if horas:
            partes.append(f"{horas} hora{'s' if horas != 1 else ''}")
        return " e ".join(partes)
    if horas:
        partes = [f"{horas} hora{'s' if horas != 1 else ''}"]
        if minutos:
            partes.append(f"{minutos} minuto{'s' if minutos != 1 else ''}")
        return " e ".join(partes)
    texto = f"{minutos} minuto{'s' if minutos != 1 else ''}"
    if segs:
        texto += f" e {segs} segundo{'s' if segs != 1 else ''}"
    return texto


def _permanencias(nome, centros_pessoa, centros_veiculo):
    """Conta quem permanece na cena e quem fica parado no mesmo ponto."""
    agora = time.time()
    frases = []
    for tipo, centros, parado_seg, cena_seg, sujeito in (
        ("pessoa", centros_pessoa, 20, 10, "Uma pessoa"),
        ("veiculo", centros_veiculo, 20, 10, "Um veículo"),
    ):
        chave = (nome, tipo)
        trilhas = _TRILHAS.setdefault(chave, [])
        usados = set()
        for centro in centros or []:
            if not centro or len(centro) < 2:
                continue
            x, y = float(centro[0]), float(centro[1])
            melhor = None
            melhor_dist = 90
            for indice, trilha in enumerate(trilhas):
                if indice in usados:
                    continue
                dist = ((trilha["x"] - x) ** 2 + (trilha["y"] - y) ** 2) ** 0.5
                if dist < melhor_dist:
                    melhor = indice
                    melhor_dist = dist
            if melhor is None:
                trilhas.append({"x": x, "y": y, "inicio": agora, "parado": agora, "visto": agora, "avisou": 0.0})
                continue
            usados.add(melhor)
            trilha = trilhas[melhor]
            if melhor_dist <= 28:
                trilha["x"], trilha["y"] = x, y
            else:
                trilha["x"], trilha["y"] = x, y
                trilha["parado"] = agora
                trilha["avisou"] = 0.0
            trilha["visto"] = agora
            na_cena = agora - trilha["inicio"]
            parado = agora - trilha["parado"]
            if parado >= parado_seg:
                ultima = float(trilha.get("avisou") or 0)
                if ultima <= 0 or agora - ultima >= _INTERVALO_AVISO_PARADO:
                    trilha["avisou"] = agora
                    frases.append(
                        f"{sujeito} está parado no mesmo lugar há {_formatar_duracao(parado)} na {nome}."
                    )
            elif na_cena >= cena_seg:
                ultima = float(trilha.get("avisou") or 0)
                if ultima <= 0 or agora - ultima >= _INTERVALO_AVISO_PARADO:
                    trilha["avisou"] = agora
                    frases.append(f"{sujeito} permanece na {nome} há {_formatar_duracao(na_cena)}.")
        _TRILHAS[chave] = [item for item in trilhas if agora - item["visto"] <= 3]
    return frases


def _lado_pessoa(comportamento):
    for hist in comportamento.historico.values():
        if len(hist) < 2:
            continue
        dx = hist[-1][1][0] - hist[0][1][0]
        if dx >= 12:
            return "para a direita da imagem"
        if dx <= -12:
            return "para a esquerda da imagem"
    return "sem deslocamento claro"


def _narrar_local(nome_camera, match, comportamento):
    if not match or match.get("tipo") != "FACE":
        return ""
    acoes = list(comportamento.acoes_ativas.values())
    acao = str(acoes[0] if acoes else "em observação").replace("_", " ").lower()
    quem = match.get("nome") or match.get("id") or "A pessoa"
    return (
        f"{quem} está {acao} na {nome_camera} e segue {_lado_pessoa(comportamento)}. "
        f"Similaridade {float(match.get('taxa') or 0):.2f}."
    )


def _narrar_ia(chave, base):
    if not base:
        return ""
    if _NARRACAO["chave"] == chave and _NARRACAO["texto"]:
        return _NARRACAO["texto"]
    if _NARRACAO["pedido"] == chave:
        return _NARRACAO["texto"]
    _NARRACAO["pedido"] = chave

    def trabalho():
        try:
            from agente.modelo import SessaoGPT
            sessao = SessaoGPT()
            if not sessao.disponivel:
                return
            texto = sessao.perguntar(
                "Narre em uma frase curta, em português, o movimento da pessoa e para onde ela segue. Use apenas os fatos informados.",
                base,
                json_mode=False,
            )
            _NARRACAO["chave"] = chave
            _NARRACAO["texto"] = str(texto).strip()[:400]
        except Exception:
            return
        finally:
            if _NARRACAO.get("pedido") == chave:
                _NARRACAO["pedido"] = ""

    threading.Thread(target=trabalho, name="narracao-risco", daemon=True).start()
    return _NARRACAO["texto"] if _NARRACAO["chave"] == chave else ""


def _match_json(match, classe, risco, narracao, narracao_ia):
    if not match:
        return None
    return {
        "tipo": match.get("tipo") or "",
        "id": match.get("id") or "",
        "nome": match.get("nome") or "",
        "taxa": float(match.get("taxa") or 0),
        "camera": match.get("camera") or "",
        "classe": classe,
        "risco": bool(risco),
        "narracao": narracao,
        "narracao_ia": narracao_ia,
    }


def _publicar_remoto(portal, acervo, cameras_online, matches, estado):
    from remoto import slug_camera
    import cadastro

    pacote = acervo.pacote(cameras_online, matches)
    for chave in ("1", "2", "3", "4"):
        portal.publicar(f"painel-{chave}", desenhar_monitor(chave, pacote))
    pessoas = {}
    try:
        interesse = cadastro.interesse_ativo() or {}
    except Exception:
        interesse = {}
    for pessoa in interesse.get("pessoas") or []:
        if pessoa.get("face_id"):
            pessoas[str(pessoa.get("face_id")).upper()] = pessoa
    cameras = []
    led = "branco"
    match_vivo = None
    narracao = ""
    narracao_ia = ""
    soma = {"Pessoa": 0, "Veiculo": 0, "Objeto": 0, "Animal": 0}
    for item in estado.values():
        analitica = item["analitica"]
        with analitica._trava:
            visao = dict(analitica._visao)
            visao["comportamentos"] = list(analitica._visao.get("comportamentos") or [])
            match = visao.get("match")
        audio = item.get("audio")
        audio_on = bool(audio and time.time() <= float(getattr(audio, "suspeito_ate", 0) or 0))
        audio_tipo = str(getattr(audio, "suspeito_tipo", "") or "") if audio_on else ""
        interesse_risco = True
        if match and match.get("tipo") == "FACE":
            pessoa_match = pessoas.get(str(match.get("id") or "").upper()) or {}
            interesse_risco = cadastro.pessoa_de_risco(pessoa_match)
        elif match and match.get("tipo") == "PLACA":
            interesse_risco = True
        risco = _risco_camera(visao, audio_on, bool(match), interesse_risco)
        if _ORDEM_LED.get(risco, 0) > _ORDEM_LED.get(led, 0):
            led = risco
        slug = slug_camera(item["nome"])
        if risco == "preto":
            quadro = _quadro_portal(getattr(analitica.stream, "frame", None))
            if quadro is not None:
                portal.publicar(f"cena-{slug}", quadro)
        if match and getattr(match.get("referencia"), "size", 0):
            portal.publicar("match-ref", match["referencia"])
        if match and getattr(match.get("atual"), "size", 0):
            portal.publicar("match-agora", match["atual"])
        if match and (match_vivo is None or float(match.get("ate") or 0) >= float(match_vivo.get("ate") or 0)):
            match_vivo = dict(match)
            match_vivo["camera"] = item["nome"]
            narracao = _narrar_local(item["nome"], match, analitica.comportamento)
        agora = {
            "Pessoa": int(visao.get("pessoas_cena") or 0),
            "Veiculo": int(visao.get("veiculos_cena") or 0),
            "Objeto": int(visao.get("objetos_cena") or 0),
            "Animal": int(visao.get("animais_cena") or 0),
        }
        acumulado = {
            "Pessoa": int(visao.get("passagens_pessoa") or 0),
            "Veiculo": int(visao.get("passagens_veiculo") or 0),
            "Objeto": int(visao.get("passagens_objeto") or 0),
            "Animal": int(visao.get("passagens_animal") or 0),
        }
        soma["Pessoa"] += agora["Pessoa"]
        soma["Veiculo"] += agora["Veiculo"]
        soma["Objeto"] += agora["Objeto"]
        soma["Animal"] += agora["Animal"]
        cameras.append({
            "nome": item["nome"],
            "rua": item.get("rua") or "",
            "slug": slug,
            "agora": agora,
            "acumulado": acumulado,
            "comportamentos": [
                {
                    "nome": comp.get("nome") or "",
                    "classe": comp.get("classe") or "",
                    "total": int(comp.get("total") or 0),
                    "agora": int(comp.get("agora") or 0),
                }
                for comp in (visao.get("comportamentos") or [])[:6]
            ],
            "frase": _frase_camera(item["nome"], visao, audio_on, audio_tipo),
            "fluxo": _fluxo_serie(item["nome"], "pessoa", acumulado["Pessoa"]),
            "fluxo_veiculo": _fluxo_serie(item["nome"], "veiculo", acumulado["Veiculo"]),
            "permanencias": _permanencias(
                item["nome"],
                visao.get("centros_pessoa") or [],
                visao.get("centros_veiculo") or [],
            ),
            "risco": risco,
            "cena": f"/img/cena-{slug}.jpg" if risco == "preto" else "",
        })
    classe = ""
    risco_match = False
    if match_vivo and match_vivo.get("tipo") == "FACE":
        pessoa = pessoas.get(str(match_vivo.get("id") or "").upper()) or {}
        classe = cadastro.classe_pessoa(pessoa)
        risco_match = cadastro.pessoa_de_risco(pessoa)
        if narracao:
            narracao_ia = _narrar_ia(f"{match_vivo.get('id')}:{int(time.time()) // 60}", narracao)
    elif match_vivo and match_vivo.get("tipo") == "PLACA":
        risco_match = True
    _SERIE.append({"t": int(time.time()), "Risco": 1 if risco_match else 0, **soma})
    historico = []
    for indice, item in enumerate((pacote.get("interesse") or [])[:4]):
        if getattr(item.get("referencia"), "size", 0):
            portal.publicar(f"alerta-{indice}-ref", item["referencia"])
        if getattr(item.get("atual"), "size", 0):
            portal.publicar(f"alerta-{indice}-agora", item["atual"])
        historico.append({
            "quando": str(item.get("quando") or ""),
            "tipo": str(item.get("tipo") or ""),
            "id": str(item.get("id") or ""),
            "nome": str(item.get("nome") or ""),
            "camera": str(item.get("camera") or ""),
            "taxa": float(item.get("taxa") or 0),
            "rotulo": str(item.get("rotulo") or ""),
            "ref": f"/img/alerta-{indice}-ref.jpg",
            "agora": f"/img/alerta-{indice}-agora.jpg",
        })
    from monitores import _linha_relatorio

    def _limpos(itens, chaves):
        saida = []
        for item in itens or []:
            if not isinstance(item, dict):
                continue
            saida.append({chave: str(item.get(chave) or "") for chave in chaves})
        return saida

    portal.definir_resumo({
        "itens": int(pacote.get("total") or 0),
        "cameras": len(pacote.get("cameras") or []),
        "periodos": pacote.get("periodos") or {},
        "horas": pacote.get("horas") or {},
        "serie_dias": pacote.get("serie_dias") or [],
        "dias_empilhados": pacote.get("dias_empilhados") or [],
        "horas_prioridade": pacote.get("horas_prioridade") or {},
        "classes": pacote.get("classes_web") or [],
        "tipos": pacote.get("tipos") or [],
        "geo": pacote.get("geo") or [],
        "riscos": pacote.get("riscos") or {},
        "pontos": pacote.get("pontos") or [],
        "app_linhas": pacote.get("app_linhas") or [],
        "cubo": pacote.get("cubo") or [],
        "pendencias": _pendencias_vivas(cameras),
        "led": led,
        "cameras_vivo": cameras,
        "serie": list(_SERIE),
        "match": _match_json(match_vivo, classe, risco_match, narracao, narracao_ia),
        "narracao": narracao,
        "narracao_ia": narracao_ia,
        "historico": historico,
        "memorias": _limpos(pacote.get("memorias"), ("quando", "texto")),
        "informes": _limpos(pacote.get("enviados"), ("quando", "tipo", "descricao", "camera", "origem")),
        "insights": _limpos(pacote.get("insights"), ("quando", "tipo", "nome", "descricao")),
        "app": _limpos(pacote.get("app"), ("quando", "titulo", "lugar", "detalhe")),
        "resumo": str(pacote.get("resumo") or ""),
        "assessoramento": str(pacote.get("assessoramento") or ""),
        "aprendizado": str(pacote.get("aprendizado") or ""),
        "relatorio": _linha_relatorio(pacote),
        "voz": _montar_voz(cameras, match_vivo, narracao, narracao_ia),
    })


def main():
    inicializar_csv()
    inicializar_csv_ocorrencias()
    inicializar_csv_faces()
    inicializar_csv_placas()
    garantir_arquivo_cameras()

    print("Carregando modelos YOLO + Pose + Faces/Placas...")
    detector_arma = DetectorArma(MODELO_ARMA)

    # Galeria compartilhada entre todas as câmeras
    id_faces = IdentificadorFaces(MODELO_FACE)
    id_placas = IdentificadorPlacas()

    estado = {}
    exibir = True
    janelas_video = set()
    lista = []
    mtime_visto = None
    avisou_vazio = False
    avisos_offline = set()
    proxima_sonda = 0.0
    vigia = None
    try:
        from agente.vigia import Vigia
        vigia = Vigia()
        vigia.iniciar()
    except Exception as exc:
        print(f"Agente de análise não iniciado: {exc}")

    print("Analítico comportamental iniciado!")
    print(
        "Ações: Em_Pe, Sentado, Agachado, Deitado, Caminhando, Correndo, "
        "Bracos_Levantados, Permanencia, Interacao_Proxima, Aglomeracao, "
        "Levantando, Possivel_Queda, Possivel_Briga, Possivel_Arma_Fogo"
    )
    print("Risco: Informativo(1) | Atencao(2) | Prioritario(3) | Critico(4)")
    print("Identidade: faces próximas + placas de veículos")
    print("Câmeras: clientes.json (a conta do cliente é relida durante a execução).")
    print("V mostra ou oculta o vídeo. O monitoramento continua oculto.")
    print("1 abre ou fecha Contagens.")
    print("2 abre ou fecha Comportamento.")
    print("3 abre ou fecha Alertas de RF e LPR.")
    print("4 abre ou fecha Mapas. D dia, S semana, M mês, P pontos, C calor.")
    print("5 liga a Camera 1, 6 a Camera 2, e assim por diante.")
    print("Q encerra o monitoramento por completo.")
    print(
        "As janelas esticam pela borda, maximizam e encaixam com Win+Tab. "
        "F alterna tela cheia na janela em foco."
    )

    acervo = Acervo()
    acervo.iniciar()
    portal = _abrir_portal(acervo)
    parar_video = threading.Event()
    if portal is not None:
        portal.ligar_faces(id_faces)
        threading.Thread(
            target=_publicar_cameras,
            args=(portal, estado, parar_video),
            name="video-portal",
            daemon=True,
        ).start()
    paineis = {"1": False, "2": False, "3": False, "4": False}
    video_cameras = {}
    janelas_painel = set()
    cache_painel = {}
    sumiu_painel = {}
    sumiu_camera = {}
    proxima_tela = 0.0
    proxima_remota = 0.0
    versao_mapa_vista = 0

    try:
        while True:
            marcas = []
            for caminho in (Path("clientes.json"), Path(ARQUIVO_CAMERAS)):
                marcas.append(caminho.stat().st_mtime if caminho.exists() else None)
            mtime = tuple(marcas)
            if mtime != mtime_visto:
                mtime_visto = mtime
                try:
                    lista = cameras_para_analise()
                except ValueError as exc:
                    print(exc)
                    print("Mantendo as câmeras já em análise.")
                else:
                    aplicar_cameras(
                        lista, estado, detector_arma, id_faces, id_placas, avisos_offline
                    )
                    proxima_sonda = time.time() + SONDA_OFFLINE_SEG
            elif lista and time.time() >= proxima_sonda:
                aplicar_cameras(
                    lista, estado, detector_arma, id_faces, id_placas, avisos_offline
                )
                proxima_sonda = time.time() + SONDA_OFFLINE_SEG

            if not estado and not avisou_vazio and mtime_visto is not None:
                if lista:
                    print(
                        "Nenhuma câmera online. "
                        "O monitoramento abre quando alguma responder."
                    )
                else:
                    print(
                        "Nenhuma câmera ativa. "
                        f"Inclua registros em {ARQUIVO_CAMERAS}."
                    )
                avisou_vazio = True
            elif estado:
                avisou_vazio = False

            ativas = {titulo_janela(item["janela"]) for item in estado.values()}
            janelas_video.intersection_update(ativas)

            for item in list(estado.values()):
                video_cameras.setdefault(item["nome"], True)
                titulo = titulo_janela(item["janela"])
                if titulo not in janelas_video or not video_cameras.get(item["nome"], True):
                    continue
                try:
                    visivel = cv2.getWindowProperty(titulo, cv2.WND_PROP_VISIBLE) >= 1
                except Exception:
                    visivel = False
                if visivel:
                    sumiu_camera.pop(titulo, None)
                    continue
                sumiu_camera[titulo] = sumiu_camera.get(titulo, 0) + 1
                if sumiu_camera[titulo] < 8:
                    continue
                video_cameras[item["nome"]] = False
                fechar_janela(titulo)
                janelas_video.discard(titulo)
                sumiu_camera.pop(titulo, None)
                print(
                    f"{item['nome']} oculta. O monitoramento continua. "
                    "A tecla da camera mostra de novo."
                )

            matches_vivos = []
            for item in list(estado.values()):
                cam = item["analitica"]
                for som in item.get("audio").drenar() if item.get("audio") else []:
                    salvar_ocorrencia(
                        cam.nome,
                        "Audio",
                        som["classe"],
                        "",
                        0,
                        0,
                        duracao=6,
                        confianca=som.get("confianca", 0),
                        status=som["risco"],
                        pessoas_envolvidas=0,
                        detalhe=som.get("detalhe", ""),
                        risco=som["risco"],
                        nivel_risco=som["nivel"],
                    )
                pacotes, visao = cam.retirar_resultados()
                match = visao.get("match")
                if match and time.time() <= float(match.get("ate") or 0):
                    ativo = dict(match)
                    ativo["camera"] = cam.nome
                    matches_vivos.append(ativo)
                for eventos, cena, comp, ativos, faces, placas in pacotes:
                    _registrar_saida(cam, eventos, cena, comp, ativos)
                    for reg in faces:
                        salvar_passagem_face(reg)
                    for reg in placas:
                        salvar_passagem_placa(reg)
                titulo = titulo_janela(item["janela"])
                if video_cameras.get(cam.nome, True) and cam.stream.preview is not None:
                    tela = cam.stream.preview.copy()
                    if time.time() - visao["quando"] < 0.6:
                        for x1, y1, x2, y2, rotulo, cor in visao["anotacoes"]:
                            cv2.rectangle(tela, (x1, y1), (x2, y2), cor, 2)
                            cv2.putText(
                                tela, rotulo, (x1, max(y1 - 5, 15)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, cor, 2,
                            )
                    tela = desenhar_painel(
                        tela,
                        nome=cam.nome,
                        fps=visao["fps"],
                        pessoas_cena=visao["pessoas_cena"],
                        veiculos_cena=visao["veiculos_cena"],
                        passagens_pessoa=visao["passagens_pessoa"],
                        passagens_veiculo=visao["passagens_veiculo"],
                        faces=visao["faces"],
                        placas=visao["placas"],
                        comportamentos=visao["comportamentos"],
                        riscos=visao["riscos"],
                        alerta=visao["alerta"],
                        match=visao.get("match"),
                    )
                    mostrar_janela(titulo, aplicar_pulso(tela))
                    janelas_video.add(titulo)
                elif titulo in janelas_video:
                    fechar_janela(titulo)
                    janelas_video.discard(titulo)

            cameras_online = [{"nome": item["nome"]} for item in estado.values()]
            acervo.quer_leitura = bool(paineis.get("3") or paineis.get("4") or portal)
            acervo.quer_mapas = bool(paineis.get("4") or portal)
            if portal is not None and time.time() >= proxima_remota:
                _publicar_remoto(portal, acervo, cameras_online, matches_vivos, estado)
                proxima_remota = time.time() + 1
            if (paineis.get("3") or paineis.get("4")) and acervo.mapa_versao != versao_mapa_vista:
                proxima_tela = min(proxima_tela, time.time())
            if any(paineis.values()) and time.time() >= proxima_tela:
                pacote = acervo.pacote(cameras_online, matches_vivos)
                for chave, aberto in paineis.items():
                    if aberto:
                        cache_painel[chave] = desenhar_monitor(chave, pacote)
                versao_mapa_vista = acervo.mapa_versao
                proxima_tela = time.time() + INTERVALO_PAINEL_SEG

            for chave, titulo in JANELAS_PAINEL.items():
                if not paineis[chave]:
                    if titulo in janelas_painel:
                        fechar_janela(titulo)
                        janelas_painel.discard(titulo)
                    continue
                imagem = cache_painel.get(chave)
                if imagem is None:
                    cache_painel[chave] = desenhar_monitor(
                        chave, acervo.pacote(cameras_online, matches_vivos),
                    )
                    imagem = cache_painel[chave]
                mostrar_janela(titulo, aplicar_pulso(imagem.copy()))
                if titulo in janelas_painel:
                    try:
                        visivel = cv2.getWindowProperty(titulo, cv2.WND_PROP_VISIBLE) >= 1
                    except Exception:
                        visivel = False
                    if visivel:
                        sumiu_painel.pop(titulo, None)
                    else:
                        sumiu_painel[titulo] = sumiu_painel.get(titulo, 0) + 1
                        if sumiu_painel[titulo] >= 8:
                            paineis[chave] = False
                            fechar_janela(titulo)
                            janelas_painel.discard(titulo)
                            sumiu_painel.pop(titulo, None)
                            print(f"Painel fechado. {chave} abre de novo.")
                            continue
                janelas_painel.add(titulo)

            ordem = list(estado.values())
            menu_cameras = [
                {
                    "indice": indice,
                    "nome": item["nome"],
                    "rua": item.get("rua") or "",
                    "tecla": str(4 + indice),
                    "aberto": video_cameras.get(item["nome"], True),
                }
                for indice, item in enumerate(ordem, start=1)
                if indice <= 5
            ]
            mostrar_janela(
                JANELA_CONTROLE,
                desenhar_controle(
                    any(camera["aberto"] for camera in menu_cameras),
                    [item["nome"] for item in ordem],
                    paineis,
                    menu_cameras,
                ),
            )

            if not estado:
                time.sleep(0.3)

            tecla = cv2.waitKey(1) & 0xFF
            if tecla in (ord("q"), ord("Q")):
                break
            if tecla in (ord("f"), ord("F")):
                alternar_tela_cheia()
            if tecla in (ord("v"), ord("V")):
                ligar = not any(video_cameras.get(item["nome"], True) for item in estado.values())
                for item in estado.values():
                    video_cameras[item["nome"]] = ligar
                if ligar:
                    print("Vídeo de todas as câmeras aberto.")
                else:
                    print("Vídeo oculto. O monitoramento continua. V mostra de novo.")
            if ord("5") <= tecla <= ord("9"):
                posicao = tecla - ord("5")
                ordem = list(estado.values())
                if posicao < len(ordem):
                    nome = ordem[posicao]["nome"]
                    video_cameras[nome] = not video_cameras.get(nome, True)
                    estado_camera = "ativa" if video_cameras[nome] else "oculta"
                    print(f"Camera {posicao + 1} {estado_camera}. O monitoramento continua.")
            if tecla in (ord("1"), ord("2"), ord("3"), ord("4")):
                chave = chr(tecla)
                paineis[chave] = not paineis[chave]
                proxima_tela = 0.0
                if paineis[chave]:
                    print(f"Painel {JANELAS_PAINEL[chave]} aberto. {chave} fecha.")
                else:
                    cache_painel.pop(chave, None)
                    print(f"Painel {JANELAS_PAINEL[chave]} fechado. {chave} abre.")
            if tecla in (ord("d"), ord("D"), ord("s"), ord("S"), ord("m"), ord("M")):
                acervo.modo_periodo = {ord("d"): "dia", ord("s"): "semana", ord("m"): "mes"}[tecla | 32]
                acervo._mapa_painel_chave = None
                proxima_tela = 0.0
            if tecla in (ord("p"), ord("P"), ord("c"), ord("C")):
                acervo.modo_desenho = "pontos" if tecla in (ord("p"), ord("P")) else "calor"
                acervo._mapa_painel_chave = None
                proxima_tela = 0.0

    finally:
        print("Encerrando analítico...")
        parar_video.set()
        if portal is not None:
            portal.parar()
        acervo.parar()
        if vigia is not None:
            vigia.parar()
        for item in estado.values():
            item["analitica"].stop()
        id_faces.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
