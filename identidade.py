"""
Identificação de faces e placas de veículos.

- Faces: MediaPipe FaceDetector (full range) + OpenCV LBPH para reidentificação
- Placas: OCR (RapidOCR/EasyOCR) na região inferior do veículo detectado pelo YOLO

A captura de face tenta qualquer distância em que a resolução ainda permita
detectar o rosto (mínimo em pixels). Faces mais próximas tendem a ter
melhor qualidade de identificação, mas não são um pré-requisito.
"""

from __future__ import annotations

import csv
import os
import re
import time
from datetime import datetime
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np


ARQUIVO_FACES = "historico_faces.csv"
ARQUIVO_PLACAS = "historico_placas.csv"

DIR_FACES = Path("evidencias") / "faces"
DIR_PLACAS = Path("evidencias") / "placas"

# full_range cobre rostos distantes; short_range fica como fallback
MODELO_FACE = "blaze_face_full_range.tflite"
MODELO_FACE_FALLBACK = "blaze_face_short_range.tflite"

# Limite prático pela resolução: lado mínimo do rosto em pixels
FACE_LADO_MINIMO_PX = 24
CONF_FACE_MINIMA = 0.50
LIMIAR_LBPH = 85.0
COOLDOWN_PASSAGEM_FACE_SEG = 90
TAMANHO_FACE = (120, 120)

# Placas
INTERVALO_OCR_VEICULO = 1.5
COOLDOWN_PASSAGEM_PLACA_SEG = 120
CONF_OCR_MINIMA = 0.35
PADRAO_PLACA = re.compile(
    r"\b([A-Z]{3}[0-9][A-Z0-9][0-9]{2}|[A-Z]{3}[0-9]{4})\b"
)


def _agora():
    return datetime.now()


def _garantir_dirs():
    DIR_FACES.mkdir(parents=True, exist_ok=True)
    DIR_PLACAS.mkdir(parents=True, exist_ok=True)


def inicializar_csv_faces():
    _garantir_dirs()
    cabecalho = [
        "Data",
        "Hora",
        "Camera",
        "Face_ID",
        "Evento",
        "Total_Passagens",
        "Track_ID",
        "Confianca",
        "Proximidade",
        "Caminho_Foto",
        "Foto_Referencia"
    ]
    if not os.path.exists(ARQUIVO_FACES):
        with open(ARQUIVO_FACES, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f, delimiter=";").writerow(cabecalho)
        print("Histórico de faces criado.")
    else:
        print("Histórico de faces existente. Novos registros serão anexados.")


def inicializar_csv_placas():
    _garantir_dirs()
    cabecalho = [
        "Data",
        "Hora",
        "Camera",
        "Placa_ID",
        "Placa",
        "Evento",
        "Total_Passagens",
        "Track_ID_Veiculo",
        "Tipo_Veiculo",
        "Confianca",
        "Caminho_Foto",
        "Foto_Referencia"
    ]
    if not os.path.exists(ARQUIVO_PLACAS):
        with open(ARQUIVO_PLACAS, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f, delimiter=";").writerow(cabecalho)
        print("Histórico de placas criado.")
    else:
        print("Histórico de placas existente. Novos registros serão anexados.")


def salvar_passagem_face(registro: dict):
    agora = _agora()
    linha = [
        agora.strftime("%Y-%m-%d"),
        agora.strftime("%H:%M:%S"),
        registro.get("camera", ""),
        registro.get("face_id", ""),
        registro.get("evento", ""),
        registro.get("total_passagens", 1),
        registro.get("track_id", ""),
        registro.get("confianca", 0),
        registro.get("proximidade", 0),
        registro.get("caminho_foto", ""),
        registro.get("foto_referencia", "")
    ]
    with open(ARQUIVO_FACES, "a", newline="", encoding="utf-8-sig") as f:
        csv.writer(f, delimiter=";").writerow(linha)
    print(
        f"[{linha[1]}] FACE {linha[2]} | {linha[4]} {linha[3]} | "
        f"passagens={linha[5]} | track={linha[6]}"
    )


def salvar_passagem_placa(registro: dict):
    agora = _agora()
    linha = [
        agora.strftime("%Y-%m-%d"),
        agora.strftime("%H:%M:%S"),
        registro.get("camera", ""),
        registro.get("placa_id", ""),
        registro.get("placa", ""),
        registro.get("evento", ""),
        registro.get("total_passagens", 1),
        registro.get("track_id", ""),
        registro.get("tipo_veiculo", ""),
        registro.get("confianca", 0),
        registro.get("caminho_foto", ""),
        registro.get("foto_referencia", "")
    ]
    with open(ARQUIVO_PLACAS, "a", newline="", encoding="utf-8-sig") as f:
        csv.writer(f, delimiter=";").writerow(linha)
    print(
        f"[{linha[1]}] PLACA {linha[2]} | {linha[4]} ({linha[3]}) | "
        f"{linha[5]} | passagens={linha[6]}"
    )


class IdentificadorFaces:
    """Detecta rostos em qualquer distância viável, cadastra foto e reidentifica."""

    def __init__(self, caminho_modelo=MODELO_FACE):
        self.disponivel = False
        self.detector = None
        self.recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=2, neighbors=8, grid_x=8, grid_y=8
        )
        self.treinado = False
        self.proximo_label = 1
        self.label_para_id = {}
        self.id_para_label = {}
        self.cadastro = {}  # face_id -> metadados
        self.ultima_passagem = {}  # face_id -> timestamp
        self.track_para_face = {}  # (camera, track_id) -> face_id
        self._seq = 0

        candidatos = [caminho_modelo, MODELO_FACE, MODELO_FACE_FALLBACK]
        modelo_usado = None
        ultimo_erro = None

        for caminho in candidatos:
            if not caminho or not os.path.exists(caminho):
                continue
            try:
                BaseOptions = mp.tasks.BaseOptions
                options = mp.tasks.vision.FaceDetectorOptions(
                    base_options=BaseOptions(model_asset_path=caminho),
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    min_detection_confidence=CONF_FACE_MINIMA
                )
                self.detector = mp.tasks.vision.FaceDetector.create_from_options(
                    options
                )
                modelo_usado = caminho
                break
            except Exception as exc:
                ultimo_erro = exc

        if modelo_usado is None:
            print(f"Falha ao iniciar detector de faces: {ultimo_erro}")
            return

        self.disponivel = True
        self._carregar_galeria_existente()
        print(f"Identificador de faces pronto ({modelo_usado}).")

    def _novo_face_id(self):
        self._seq += 1
        return f"F{self._seq:04d}"

    def _carregar_galeria_existente(self):
        """Reaproveita fotos de referência já salvas em evidencias/faces."""
        imagens = []
        labels = []

        for pasta in sorted(DIR_FACES.glob("F*")):
            if not pasta.is_dir():
                continue
            face_id = pasta.name
            ref = pasta / "referencia.jpg"
            if not ref.exists():
                continue

            img = cv2.imread(str(ref), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue

            img = cv2.resize(img, TAMANHO_FACE)
            label = self.proximo_label
            self.proximo_label += 1
            self.label_para_id[label] = face_id
            self.id_para_label[face_id] = label
            self.cadastro[face_id] = {
                "foto_referencia": str(ref).replace("\\", "/"),
                "total_passagens": 1,
                "primeira_vez": ""
            }
            imagens.append(img)
            labels.append(label)

            # tenta ler total de passagens do CSV
            if os.path.exists(ARQUIVO_FACES):
                try:
                    with open(ARQUIVO_FACES, encoding="utf-8-sig") as f:
                        reader = csv.DictReader(f, delimiter=";")
                        for row in reader:
                            if row.get("Face_ID") == face_id:
                                try:
                                    total = int(row.get("Total_Passagens", 1))
                                    self.cadastro[face_id]["total_passagens"] = max(
                                        self.cadastro[face_id]["total_passagens"],
                                        total
                                    )
                                except ValueError:
                                    pass
                except Exception:
                    pass

            nums = re.findall(r"\d+", face_id)
            if nums:
                self._seq = max(self._seq, int(nums[0]))

        if imagens:
            self.recognizer.train(imagens, np.array(labels))
            self.treinado = True
            print(f"Galeria de faces recarregada: {len(imagens)} identidade(s).")

    def _preprocessar(self, face_bgr):
        cinza = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        cinza = cv2.equalizeHist(cinza)
        return cv2.resize(cinza, TAMANHO_FACE)

    def _detectar_faces_no_recorte(self, frame, bbox_pessoa):
        if not self.disponivel:
            return []

        h, w = frame.shape[:2]
        x1, y1, x2, y2 = map(int, bbox_pessoa)
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

        altura_pessoa = max(1, y2 - y1)
        # Pessoa pequena/distante: usa quase o corpo inteiro.
        # Pessoa grande: prioriza a metade superior (onde está o rosto).
        area_pessoa = (x2 - x1) * altura_pessoa / float(h * w)
        fracao_superior = 0.95 if area_pessoa < 0.05 else 0.65
        y2_face = min(h, y1 + max(20, int(altura_pessoa * fracao_superior)))

        crop = frame[y1:y2_face, x1:x2]
        if crop.size == 0:
            return []

        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        resultado = self.detector.detect(mp_image)
        faces = []

        if not resultado.detections:
            return faces

        area_frame = float(h * w)

        for det in resultado.detections:
            box = det.bounding_box
            fx1 = x1 + int(box.origin_x)
            fy1 = y1 + int(box.origin_y)
            fx2 = fx1 + int(box.width)
            fy2 = fy1 + int(box.height)
            fx1, fy1 = max(0, fx1), max(0, fy1)
            fx2, fy2 = min(w, fx2), min(h, fy2)

            largura_f = max(0, fx2 - fx1)
            altura_f = max(0, fy2 - fy1)
            # Só descarta se for menor do que a resolução permite reconhecer
            if largura_f < FACE_LADO_MINIMO_PX or altura_f < FACE_LADO_MINIMO_PX:
                continue

            score = float(det.categories[0].score) if det.categories else 0.0
            if score < CONF_FACE_MINIMA:
                continue

            area = largura_f * altura_f
            faces.append({
                "bbox": (fx1, fy1, fx2, fy2),
                "confianca": score,
                "area_frac": area / area_frame,
                "lado_px": min(largura_f, altura_f)
            })

        faces.sort(key=lambda f: f["lado_px"], reverse=True)
        return faces

    def _reconhecer_ou_cadastrar(self, face_gray):
        if self.treinado:
            label, distancia = self.recognizer.predict(face_gray)
            if label in self.label_para_id and distancia <= LIMIAR_LBPH:
                face_id = self.label_para_id[label]
                conf = max(0.0, 1.0 - (distancia / (LIMIAR_LBPH * 1.5)))
                return face_id, conf, False

        face_id = self._novo_face_id()
        label = self.proximo_label
        self.proximo_label += 1
        self.label_para_id[label] = face_id
        self.id_para_label[face_id] = label

        pasta = DIR_FACES / face_id
        pasta.mkdir(parents=True, exist_ok=True)
        ref = pasta / "referencia.jpg"
        cv2.imwrite(str(ref), face_gray)

        if self.treinado:
            self.recognizer.update([face_gray], np.array([label]))
        else:
            self.recognizer.train([face_gray], np.array([label]))
            self.treinado = True

        self.cadastro[face_id] = {
            "foto_referencia": str(ref).replace("\\", "/"),
            "total_passagens": 0,
            "primeira_vez": _agora().isoformat(timespec="seconds")
        }
        return face_id, 0.9, True

    def processar(self, camera, frame, pessoas):
        """
        pessoas: dict track_id -> {bbox, centro}
        Retorna lista de eventos de passagem e anotações visuais.
        """
        eventos = []
        anotacoes = []
        if not self.disponivel or not pessoas:
            return eventos, anotacoes

        h, w = frame.shape[:2]
        area_frame = float(h * w)
        agora = time.time()

        for track_id, info in pessoas.items():
            x1, y1, x2, y2 = info["bbox"]
            area_pessoa = max(0, x2 - x1) * max(0, y2 - y1) / area_frame

            faces = self._detectar_faces_no_recorte(frame, info["bbox"])
            if not faces:
                continue

            face = faces[0]
            fx1, fy1, fx2, fy2 = face["bbox"]
            crop = frame[fy1:fy2, fx1:fx2]
            if crop.size == 0:
                continue

            face_gray = self._preprocessar(crop)
            chave_track = (camera, track_id)

            # Se este track já tem face associada nesta sessão recente, só desenha
            face_id_track = self.track_para_face.get(chave_track)
            if face_id_track is not None:
                anotacoes.append({
                    "bbox": face["bbox"],
                    "rotulo": f"{face_id_track}",
                    "confianca": face["confianca"]
                })
                continue

            face_id, conf_id, novo = self._reconhecer_ou_cadastrar(face_gray)
            self.track_para_face[chave_track] = face_id

            ultimo = self.ultima_passagem.get(face_id, 0)
            if (agora - ultimo) < COOLDOWN_PASSAGEM_FACE_SEG and not novo:
                anotacoes.append({
                    "bbox": face["bbox"],
                    "rotulo": f"{face_id}",
                    "confianca": conf_id
                })
                continue

            self.ultima_passagem[face_id] = agora
            meta = self.cadastro.setdefault(face_id, {
                "foto_referencia": "",
                "total_passagens": 0
            })
            meta["total_passagens"] = int(meta.get("total_passagens", 0)) + 1
            evento = "Novo" if novo else "Reaparecimento"

            pasta = DIR_FACES / face_id
            pasta.mkdir(parents=True, exist_ok=True)
            nome_foto = (
                f"{_agora().strftime('%Y%m%d_%H%M%S')}_"
                f"{camera.replace(' ', '')}_t{track_id}.jpg"
            )
            caminho = pasta / nome_foto
            cv2.imwrite(str(caminho), crop)

            if not meta.get("foto_referencia"):
                ref = pasta / "referencia.jpg"
                cv2.imwrite(str(ref), face_gray)
                meta["foto_referencia"] = str(ref).replace("\\", "/")

            registro = {
                "camera": camera,
                "face_id": face_id,
                "evento": evento,
                "total_passagens": meta["total_passagens"],
                "track_id": track_id,
                "confianca": round(float(conf_id), 2),
                "proximidade": round(float(area_pessoa), 3),
                "caminho_foto": str(caminho).replace("\\", "/"),
                "foto_referencia": meta.get("foto_referencia", "")
            }
            eventos.append(registro)
            anotacoes.append({
                "bbox": face["bbox"],
                "rotulo": f"{face_id} {evento}",
                "confianca": conf_id
            })

        return eventos, anotacoes

    def stop(self):
        if self.detector is not None:
            self.detector.close()
            self.detector = None


class IdentificadorPlacas:
    """Lê placas em recortes de veículos e registra passagens."""

    def __init__(self):
        self.disponivel = False
        self.backend = None  # "rapidocr" | "easyocr"
        self.reader = None
        self.cadastro = {}  # placa -> metadados
        self.ultima_passagem = {}
        self.ultimo_ocr_track = {}
        self.track_para_placa = {}
        self._seq = 0

        # Preferência: RapidOCR (leve). Fallback: EasyOCR.
        try:
            from rapidocr_onnxruntime import RapidOCR
            self.reader = RapidOCR()
            self.backend = "rapidocr"
            self.disponivel = True
            self._carregar_cadastro_csv()
            print("Identificador de placas (RapidOCR) pronto.")
        except Exception as exc_rapid:
            try:
                import easyocr
                self.reader = easyocr.Reader(["pt", "en"], gpu=False, verbose=False)
                self.backend = "easyocr"
                self.disponivel = True
                self._carregar_cadastro_csv()
                print("Identificador de placas (EasyOCR) pronto.")
            except Exception as exc_easy:
                print(
                    "OCR de placas indisponível — funcionalidade desabilitada. "
                    f"RapidOCR: {exc_rapid} | EasyOCR: {exc_easy}"
                )

    def _ocr(self, imagem_bgr):
        """Normaliza saídas de diferentes backends para [(bbox, texto, conf), ...]."""
        if self.backend == "rapidocr":
            resultado, _ = self.reader(imagem_bgr)
            saida = []
            if not resultado:
                return saida
            for item in resultado:
                # item: [box, text, score]
                if len(item) >= 3:
                    saida.append((item[0], item[1], float(item[2])))
            return saida

        if self.backend == "easyocr":
            return self.reader.readtext(imagem_bgr)

        return []

    def _novo_placa_id(self, placa):
        self._seq += 1
        return f"P{self._seq:04d}_{placa}"

    def _carregar_cadastro_csv(self):
        if not os.path.exists(ARQUIVO_PLACAS):
            return
        try:
            with open(ARQUIVO_PLACAS, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    placa = (row.get("Placa") or "").upper()
                    placa_id = row.get("Placa_ID") or ""
                    if not placa:
                        continue
                    total = 1
                    try:
                        total = int(row.get("Total_Passagens", 1))
                    except ValueError:
                        pass
                    atual = self.cadastro.get(placa, {"total_passagens": 0})
                    self.cadastro[placa] = {
                        "placa_id": placa_id or atual.get("placa_id", ""),
                        "total_passagens": max(
                            atual.get("total_passagens", 0), total
                        ),
                        "foto_referencia": row.get("Foto_Referencia", "")
                    }
                    nums = re.findall(r"P(\d+)_", placa_id)
                    if nums:
                        self._seq = max(self._seq, int(nums[0]))
        except Exception:
            pass

    @staticmethod
    def _normalizar_texto(texto: str) -> str:
        texto = texto.upper()
        texto = re.sub(r"[^A-Z0-9]", "", texto)
        # confusões comuns OCR
        return texto

    def _extrair_placa(self, textos):
        candidatos = []
        for item in textos:
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                txt, conf = item[1], float(item[2])
            else:
                continue
            limpo = self._normalizar_texto(txt)
            match = PADRAO_PLACA.search(limpo)
            if match and conf >= CONF_OCR_MINIMA:
                candidatos.append((match.group(1), conf))
            # tenta placa colada sem separadores já limpa
            elif len(limpo) in (7,) and conf >= CONF_OCR_MINIMA:
                if re.fullmatch(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}", limpo) or \
                   re.fullmatch(r"[A-Z]{3}[0-9]{4}", limpo):
                    candidatos.append((limpo, conf))

        if not candidatos:
            return None, 0.0
        candidatos.sort(key=lambda x: x[1], reverse=True)
        return candidatos[0]

    def processar(self, camera, frame, veiculos):
        """
        veiculos: dict track_id -> {bbox, classe}
        """
        eventos = []
        anotacoes = []
        if not self.disponivel or not veiculos:
            return eventos, anotacoes

        h, w = frame.shape[:2]
        agora = time.time()

        for track_id, info in veiculos.items():
            chave_track = (camera, track_id)
            if chave_track in self.track_para_placa:
                placa = self.track_para_placa[chave_track]
                anotacoes.append({
                    "bbox": info["bbox"],
                    "rotulo": placa,
                    "confianca": 1.0
                })
                continue

            ultimo = self.ultimo_ocr_track.get(chave_track, 0)
            if agora - ultimo < INTERVALO_OCR_VEICULO:
                continue
            self.ultimo_ocr_track[chave_track] = agora

            x1, y1, x2, y2 = map(int, info["bbox"])
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            # região inferior do veículo (onde costuma estar a placa)
            y_ini = y1 + int((y2 - y1) * 0.45)
            crop = frame[y_ini:y2, x1:x2]
            if crop.size == 0 or crop.shape[0] < 15 or crop.shape[1] < 40:
                continue

            try:
                resultados = self._ocr(crop)
            except Exception:
                continue

            placa, conf = self._extrair_placa(resultados)
            if not placa:
                continue

            self.track_para_placa[chave_track] = placa
            meta = self.cadastro.get(placa)
            novo = meta is None
            if novo:
                placa_id = self._novo_placa_id(placa)
                pasta = DIR_PLACAS / placa
                pasta.mkdir(parents=True, exist_ok=True)
                ref = pasta / "referencia.jpg"
                cv2.imwrite(str(ref), crop)
                meta = {
                    "placa_id": placa_id,
                    "total_passagens": 0,
                    "foto_referencia": str(ref).replace("\\", "/")
                }
                self.cadastro[placa] = meta
            else:
                placa_id = meta["placa_id"]

            ultimo_pass = self.ultima_passagem.get(placa, 0)
            if (agora - ultimo_pass) < COOLDOWN_PASSAGEM_PLACA_SEG and not novo:
                anotacoes.append({
                    "bbox": info["bbox"],
                    "rotulo": placa,
                    "confianca": conf
                })
                continue

            self.ultima_passagem[placa] = agora
            meta["total_passagens"] = int(meta.get("total_passagens", 0)) + 1
            evento = "Novo" if novo else "Reaparecimento"

            pasta = DIR_PLACAS / placa
            pasta.mkdir(parents=True, exist_ok=True)
            nome_foto = (
                f"{_agora().strftime('%Y%m%d_%H%M%S')}_"
                f"{camera.replace(' ', '')}_t{track_id}.jpg"
            )
            caminho = pasta / nome_foto
            cv2.imwrite(str(caminho), crop)

            eventos.append({
                "camera": camera,
                "placa_id": placa_id,
                "placa": placa,
                "evento": evento,
                "total_passagens": meta["total_passagens"],
                "track_id": track_id,
                "tipo_veiculo": info.get("classe", "Veiculo"),
                "confianca": round(float(conf), 2),
                "caminho_foto": str(caminho).replace("\\", "/"),
                "foto_referencia": meta.get("foto_referencia", "")
            })
            anotacoes.append({
                "bbox": (x1, y_ini, x2, y2),
                "rotulo": f"{placa} {evento}",
                "confianca": conf
            })

        return eventos, anotacoes
