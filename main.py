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

RTSP_CAM_1 = os.getenv(
    "RTSP_CAM_1",
    "rtsp://usuario:senha@192.168.0.21:554/cam/realmonitor?channel=1&subtype=0"
)
RTSP_CAM_2 = os.getenv(
    "RTSP_CAM_2",
    "rtsp://usuario:senha@192.168.0.108:554/cam/realmonitor?channel=1&subtype=0"
)

ARQUIVO_HISTORICO = "historico_analitico.csv"
ARQUIVO_OCORRENCIAS = "historico_ocorrencias.csv"

MODELO_YOLO = "yolov8n.pt"
MODELO_ARMA = "arma_fogo.pt"  # opcional
MODELO_POSE = "pose_landmarker_lite.task"
TRACKER = "bytetrack.yaml"

CONF_MINIMA = 0.4
CONF_ARMA_MINIMA = 0.45
CONFIANCA_POSE = 0.45

LARGURA, ALTURA = 640, 480

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


class CameraStream:

    def __init__(self, src):
        self.stream = cv2.VideoCapture(src)
        self.ret, self.frame = self.stream.read()
        self.stopped = False

    def start(self):
        threading.Thread(target=self.update, daemon=True).start()
        return self

    def update(self):
        while not self.stopped:
            if not self.stream.isOpened():
                time.sleep(0.1)
                continue

            ret, frame = self.stream.read()
            if ret:
                self.frame = frame
            else:
                time.sleep(0.01)

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

    def __init__(self, nome, src, detector_arma=None, pose_analyzer=None):
        self.nome = nome
        self.stream = CameraStream(src).start()
        self.model = YOLO(MODELO_YOLO)
        self.detector_arma = detector_arma or DetectorArma(MODELO_ARMA)
        self.pose = pose_analyzer or PoseAnalyzer(MODELO_POSE)

        self.ids_vistos = set()
        self.unicos_por_categoria = defaultdict(set)
        self.comportamento = AnaliseComportamental(nome, self.pose)

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

    def process(self):
        frame = self.stream.read()
        if frame is None:
            return None, [], {}, [], {}

        frame = cv2.resize(frame, (LARGURA, ALTURA))

        results = self.model.track(
            frame,
            conf=CONF_MINIMA,
            persist=True,
            tracker=TRACKER,
            verbose=False
        )

        boxes = results[0].boxes
        if boxes is None:
            return frame, [], {}, [], {}

        if boxes.id is not None:
            ids = boxes.id.int().cpu().tolist()
        else:
            ids = [None] * len(boxes)

        quantidade_cena = defaultdict(int)
        novos_eventos = []
        pessoas_cena = {}

        for box, track_id in zip(boxes, ids):
            cls_id = int(box.cls[0].item())
            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().tolist())
            categoria = self.classificar(cls_id)
            nome = self.nome_classe(cls_id)
            quantidade_cena[categoria] += 1

            chave = (categoria, cls_id, track_id)
            if track_id is not None and chave not in self.ids_vistos:
                self.ids_vistos.add(chave)
                self.unicos_por_categoria[categoria].add(chave)
                novos_eventos.append((categoria, nome, track_id))

            if categoria == "Pessoa" and track_id is not None:
                pessoas_cena[track_id] = {
                    "centro": ((x1 + x2) / 2, (y1 + y2) / 2),
                    "bbox": (x1, y1, x2, y2)
                }

            cor = CORES[categoria]
            rotulo = f"{nome} #{track_id}" if track_id is not None else nome
            acao = self.comportamento.acoes_ativas.get(track_id)
            if categoria == "Pessoa" and acao:
                rotulo = f"{rotulo} | {acao}"

            cv2.rectangle(frame, (x1, y1), (x2, y2), cor, 2)
            cv2.putText(
                frame, rotulo, (x1, max(y1 - 5, 15)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, cor, 2
            )

        armas = self.detector_arma.detectar(frame)
        for arma in armas:
            x1, y1, x2, y2 = arma["bbox"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(
                frame, f"ARMA {arma['confianca']:.2f}",
                (x1, max(y1 - 8, 15)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2
            )

        eventos_comp, ativos_comp = self.comportamento.analisar(
            frame, pessoas_cena, armas, LARGURA, ALTURA
        )

        cv2.rectangle(frame, (0, 0), (LARGURA, 95), (0, 0, 0), -1)

        texto1 = (
            f"{self.nome} | P: {quantidade_cena['Pessoa']} | "
            f"A: {quantidade_cena['Animal']} | "
            f"V: {quantidade_cena['Veiculo']} | "
            f"O: {quantidade_cena['Objeto']}"
        )
        texto2 = (
            f"Unicos P/A/V/O: "
            f"{len(self.unicos_por_categoria['Pessoa'])}/"
            f"{len(self.unicos_por_categoria['Animal'])}/"
            f"{len(self.unicos_por_categoria['Veiculo'])}/"
            f"{len(self.unicos_por_categoria['Objeto'])}"
        )
        texto3 = (
            f"Risco ativos | Queda {ativos_comp.get('Possivel_Queda', 0)} "
            f"Briga {ativos_comp.get('Possivel_Briga', 0)} "
            f"Arma {ativos_comp.get('Possivel_Arma_Fogo', 0)} "
            f"Aglom {ativos_comp.get('Aglomeracao', 0)} "
            f"Perm {ativos_comp.get('Permanencia', 0)}"
        )

        cv2.putText(frame, texto1, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)
        cv2.putText(frame, texto2, (8, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (255, 255, 255), 1)
        cv2.putText(frame, texto3, (8, 74), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 200, 255), 1)

        if eventos_comp:
            ev = max(eventos_comp, key=lambda e: e["nivel_risco"])
            cor = CORES_RISCO.get(ev["risco"], (0, 0, 255))
            cv2.putText(
                frame,
                f"{ev['risco']} | {ev['classe']} ID {ev['id']}",
                (8, ALTURA - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                cor,
                2
            )

        return (
            frame,
            novos_eventos,
            dict(quantidade_cena),
            eventos_comp,
            ativos_comp
        )

    def total_unicos_categoria(self, categoria):
        return len(self.unicos_por_categoria[categoria])

    def stop(self):
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

def main():
    inicializar_csv()
    inicializar_csv_ocorrencias()

    print("Carregando modelos YOLO + Pose...")
    detector_arma = DetectorArma(MODELO_ARMA)

    # Um PoseAnalyzer por câmera (estado interno isolado)
    cam1 = CameraAnalitica(
        "CAMERA 1",
        RTSP_CAM_1,
        detector_arma,
        PoseAnalyzer(MODELO_POSE)
    )
    cam2 = CameraAnalitica(
        "CAMERA 2",
        RTSP_CAM_2,
        detector_arma,
        PoseAnalyzer(MODELO_POSE)
    )

    print("Analítico comportamental iniciado!")
    print(
        "Ações: Em_Pe, Sentado, Agachado, Deitado, Caminhando, Correndo, "
        "Bracos_Levantados, Permanencia, Interacao_Proxima, Aglomeracao, "
        "Levantando, Possivel_Queda, Possivel_Briga, Possivel_Arma_Fogo"
    )
    print("Risco: Informativo(1) | Atencao(2) | Prioritario(3) | Critico(4)")
    print("Pressione Q para encerrar.")

    try:
        while True:
            out1, eventos1, cena1, comp1, ativos1 = cam1.process()
            out2, eventos2, cena2, comp2, ativos2 = cam2.process()

            for categoria, classe, track_id in eventos1:
                salvar_evento(
                    cam1.nome, categoria, classe, track_id,
                    cam1.total_unicos_categoria(categoria),
                    cena1.get(categoria, 0)
                )

            for categoria, classe, track_id in eventos2:
                salvar_evento(
                    cam2.nome, categoria, classe, track_id,
                    cam2.total_unicos_categoria(categoria),
                    cena2.get(categoria, 0)
                )

            for ev in comp1:
                salvar_ocorrencia(
                    cam1.nome,
                    ev["categoria"],
                    ev["classe"],
                    ev["id"],
                    cam1.comportamento.total_unicos_classe(ev["classe"]),
                    ativos1.get(ev["classe"], 0),
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

            for ev in comp2:
                salvar_ocorrencia(
                    cam2.nome,
                    ev["categoria"],
                    ev["classe"],
                    ev["id"],
                    cam2.comportamento.total_unicos_classe(ev["classe"]),
                    ativos2.get(ev["classe"], 0),
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

            if out1 is not None:
                cv2.imshow("Analitico - Camera 1", out1)
            if out2 is not None:
                cv2.imshow("Analitico - Camera 2", out2)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        print("Encerrando analítico...")
        cam1.stop()
        cam2.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
