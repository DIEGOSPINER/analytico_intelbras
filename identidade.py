"""
Identificação de faces e placas de veículos.

- Faces: MediaPipe FaceDetector + características SFace gravadas em disco.
  Cada pessoa fica com um Face_ID estável. Novas fotos do mesmo rosto
  entram na pasta desse ID e atualizam a galeria de características.
- Placas: OCR com correção de leitura e assinatura visual do veículo,
  para reutilizar o mesmo Placa_ID quando o carro volta.

A captura de face tenta qualquer distância em que a resolução ainda permita
detectar o rosto (mínimo em pixels). Faces mais próximas tendem a ter
melhor qualidade de identificação, mas não são um pré-requisito.
"""

from __future__ import annotations

import csv
import os
import re
import shutil
import threading
import time
import urllib.request
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
FACE_LADO_MINIMO_CADASTRO = 32
CONF_FACE_MINIMA = 0.50
COOLDOWN_PASSAGEM_FACE_SEG = 90
INTERVALO_AMOSTRA_FACE = 2.5
TTL_TRACK_SEG = 6
MAX_AMOSTRAS = 12

# Similaridade de cosseno do SFace. Abaixo disso a foto vira outra pessoa.
LIMIAR_MATCH = 0.50
LIMIAR_CERTEZA = 0.60
MARGEM_MATCH = 0.05
LIMIAR_FUNDIR = 0.52

MODELO_SFACE = "face_recognition_sface_2021dec.onnx"
URL_SFACE = (
    "https://github.com/opencv/opencv_zoo/raw/refs/heads/main/"
    "models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
)
# Olho direito, olho esquerdo, nariz, canto direito da boca, canto esquerdo.
PONTOS_SFACE = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)

# Placas
INTERVALO_OCR_VEICULO = 1.5
REOCR_TRACK_SEG = 8.0
COOLDOWN_PASSAGEM_PLACA_SEG = 120
CONF_OCR_MINIMA = 0.30
CONF_OCR_CORRIGIDA = 0.45
SIMILARIDADE_PLACA_VISUAL = 0.88
PADRAO_PLACA = re.compile(
    r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$|^[A-Z]{3}[0-9]{4}$"
)
_LETRA_DE = {"0": "O", "1": "I", "2": "Z", "4": "A", "5": "S", "6": "G", "8": "B"}
_DIGITO_DE = {
    "O": "0", "Q": "0", "D": "0",
    "I": "1", "L": "1",
    "Z": "2",
    "A": "4",
    "S": "5",
    "G": "6",
    "T": "7",
    "B": "8",
}


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
        "Foto_Referencia",
        "Similaridade"
    ]
    if not os.path.exists(ARQUIVO_PLACAS):
        with open(ARQUIVO_PLACAS, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f, delimiter=";").writerow(cabecalho)
        print("Histórico de placas criado.")
    else:
        print("Histórico de placas existente. Novos registros serão anexados.")


_CACHE_FACES = {"quando": 0.0, "linhas": []}


def contar_passagens_faces(limite: int = 14) -> list[tuple[str, int]]:
    """Quantas vezes cada Face_ID passou, do mais frequente ao menos."""
    agora = time.time()
    if agora - _CACHE_FACES["quando"] < 1 and _CACHE_FACES["linhas"]:
        return _CACHE_FACES["linhas"][:limite]
    contagem = {}
    if os.path.exists(ARQUIVO_FACES):
        with open(ARQUIVO_FACES, encoding="utf-8-sig", newline="") as arquivo:
            leitor = csv.reader(arquivo, delimiter=";")
            next(leitor, None)
            for linha in leitor:
                if len(linha) > 3 and linha[3].strip():
                    ident = linha[3].strip().upper()
                    contagem[ident] = contagem.get(ident, 0) + 1
    linhas = sorted(contagem.items(), key=lambda item: (-item[1], item[0]))
    _CACHE_FACES["quando"] = agora
    _CACHE_FACES["linhas"] = linhas
    return linhas[:limite]


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
        registro.get("foto_referencia", ""),
        "" if registro.get("similaridade") is None else registro.get("similaridade"),
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
        self.reconhecedor = None
        self.usa_sface = False
        self.limiar_match = LIMIAR_MATCH
        self.limiar_certeza = LIMIAR_CERTEZA
        self.limiar_fundir = LIMIAR_FUNDIR
        self.cadastro = {}
        self.galeria = {}
        self.ultima_passagem = {}
        self.track_para_face = {}
        self.track_score = {}
        self.track_ultima_amostra = {}
        self.track_visto = {}
        self._trava = threading.Lock()
        self._seq = 0
        self._dim = 128

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

        self._iniciar_reconhecedor()
        self.disponivel = True
        self._carregar_galeria_existente()
        modo = "SFace" if self.usa_sface else "características visuais"
        print(
            f"Identificador de faces pronto ({modelo_usado}, {modo}). "
            f"Galeria: {len(self.galeria)} identidade(s)."
        )

    def _iniciar_reconhecedor(self):
        caminho = self._garantir_modelo_sface()
        if not caminho or not hasattr(cv2, "FaceRecognizerSF"):
            print(
                "Modelo SFace indisponível. "
                "A reidentificação usará características visuais locais."
            )
            self._dim = 400
            self.limiar_match = 0.46
            self.limiar_certeza = 0.62
            self.limiar_fundir = 0.55
            return
        try:
            self.reconhecedor = cv2.FaceRecognizerSF.create(caminho, "")
            self.usa_sface = True
            self._dim = 128
        except Exception as exc:
            print(f"Falha ao abrir SFace ({exc}). Usando características visuais.")
            self._dim = 400
            self.limiar_match = 0.46
            self.limiar_certeza = 0.62
            self.limiar_fundir = 0.55

    @staticmethod
    def _garantir_modelo_sface():
        if os.path.exists(MODELO_SFACE):
            return MODELO_SFACE
        print("Baixando modelo de características faciais (SFace)...")
        try:
            urllib.request.urlretrieve(URL_SFACE, MODELO_SFACE)
            return MODELO_SFACE
        except Exception as exc:
            print(f"Não foi possível baixar o modelo de faces: {exc}")
            return None

    def _novo_face_id(self):
        self._seq += 1
        return f"F{self._seq:04d}"

    def _pacote_vazio(self):
        return {
            "vetores": np.zeros((0, self._dim), np.float32),
            "alinhados": np.zeros((0, self._dim), np.float32),
            "tem_alinhado": np.zeros((0,), np.uint8),
        }

    @staticmethod
    def _eh_colorida(bgr):
        if bgr is None or bgr.ndim != 3:
            return False
        azul, verde, vermelho = cv2.split(bgr)
        diferenca = float(np.mean(cv2.absdiff(azul, verde)))
        diferenca += float(np.mean(cv2.absdiff(verde, vermelho)))
        return diferenca > 4.0

    def _carregar_galeria_existente(self):
        """Recarrega características já salvas e une fotos da mesma pessoa."""
        for pasta in sorted(DIR_FACES.glob("F*")):
            if not pasta.is_dir():
                continue
            face_id = pasta.name
            pack = self._carregar_ou_calcular(pasta)
            if pack is None:
                continue
            self.galeria[face_id] = pack
            ref = pasta / "referencia.jpg"
            self.cadastro[face_id] = {
                "foto_referencia": str(ref).replace("\\", "/") if ref.exists() else "",
                "total_passagens": 0,
                "primeira_vez": "",
            }
            nums = re.findall(r"\d+", face_id)
            if nums:
                self._seq = max(self._seq, int(nums[0]))

        self._fundir_duplicatas()
        self._aplicar_contagens_csv()
        for face_id in list(self.galeria):
            pasta = DIR_FACES / face_id
            self._garantir_referencia_colorida(pasta)
            ref = pasta / "referencia.jpg"
            if face_id in self.cadastro and ref.exists():
                self.cadastro[face_id]["foto_referencia"] = str(ref).replace("\\", "/")

    def _carregar_ou_calcular(self, pasta: Path):
        npz = pasta / "caracteristicas.npz"
        if npz.exists():
            try:
                dados = np.load(str(npz))
                vetores = np.atleast_2d(dados["vetores"]).astype(np.float32)
                if vetores.size > 0 and vetores.shape[1] == self._dim:
                    return {
                        "vetores": vetores,
                        "alinhados": np.atleast_2d(dados["alinhados"]).astype(np.float32),
                        "tem_alinhado": dados["tem_alinhado"].astype(np.uint8).reshape(-1),
                    }
            except Exception:
                pass

        vetores, alinhados, tem = [], [], []
        for caminho in self._listar_fotos(pasta):
            imagem = cv2.imread(str(caminho))
            if imagem is None:
                continue
            if caminho.name == "referencia.jpg" and not self._eh_colorida(imagem):
                continue
            vetor, alinhado = self._extrair(imagem, imagem, None)
            if vetor is None:
                continue
            vetores.append(vetor)
            if alinhado is None:
                alinhados.append(np.zeros_like(vetor))
                tem.append(0)
            else:
                alinhados.append(alinhado)
                tem.append(1)
            if len(vetores) >= MAX_AMOSTRAS:
                break

        if not vetores:
            ref = pasta / "referencia.jpg"
            imagem = cv2.imread(str(ref)) if ref.exists() else None
            if imagem is None:
                return None
            vetor, alinhado = self._extrair(imagem, imagem, None)
            if vetor is None:
                return None
            vetores = [vetor]
            alinhados = [alinhado if alinhado is not None else np.zeros_like(vetor)]
            tem = [1 if alinhado is not None else 0]

        pack = {
            "vetores": np.stack(vetores).astype(np.float32),
            "alinhados": np.stack(alinhados).astype(np.float32),
            "tem_alinhado": np.array(tem, dtype=np.uint8),
        }
        self._salvar_pack(pasta, pack)
        return pack

    def _listar_fotos(self, pasta: Path):
        fotos = []
        for caminho in pasta.glob("*.jpg"):
            imagem = cv2.imread(str(caminho))
            if imagem is None:
                continue
            if caminho.name == "referencia.jpg" and not self._eh_colorida(imagem):
                continue
            fotos.append((imagem.shape[0] * imagem.shape[1], caminho))
        fotos.sort(reverse=True)
        return [caminho for _, caminho in fotos]

    def _salvar_pack(self, pasta: Path, pack: dict):
        pasta.mkdir(parents=True, exist_ok=True)
        np.savez(
            pasta / "caracteristicas.npz",
            vetores=pack["vetores"],
            alinhados=pack["alinhados"],
            tem_alinhado=pack["tem_alinhado"],
        )

    def _salvar_caracteristicas(self, face_id):
        pack = self.galeria.get(face_id)
        if pack is None:
            return
        self._salvar_pack(DIR_FACES / face_id, pack)

    def _garantir_referencia_colorida(self, pasta: Path):
        ref = pasta / "referencia.jpg"
        atual = cv2.imread(str(ref)) if ref.exists() else None
        if atual is not None and self._eh_colorida(atual):
            return
        melhor = None
        melhor_area = 0
        for caminho in pasta.glob("*.jpg"):
            imagem = cv2.imread(str(caminho))
            if imagem is None or not self._eh_colorida(imagem):
                continue
            area = imagem.shape[0] * imagem.shape[1]
            if area > melhor_area:
                melhor = imagem
                melhor_area = area
        if melhor is not None:
            cv2.imwrite(str(ref), melhor)

    def _score_contra_id(self, face_id, vetor, alinhado):
        pack = self.galeria.get(face_id)
        if pack is None or vetor is None or len(pack["vetores"]) == 0:
            return -1.0
        score = float(np.max(pack["vetores"] @ vetor.astype(np.float32)))
        if alinhado is not None and pack["tem_alinhado"].any():
            mascara = pack["tem_alinhado"].astype(bool)
            score_alinhado = float(np.max(pack["alinhados"][mascara] @ alinhado.astype(np.float32)))
            score = max(score, score_alinhado)
        return score

    def _buscar(self, vetor, alinhado):
        ranking = []
        for face_id in self.galeria:
            ranking.append((self._score_contra_id(face_id, vetor, alinhado), face_id))
        if not ranking:
            return None, 0.0
        ranking.sort(reverse=True)
        melhor_score, melhor_id = ranking[0]
        segundo = ranking[1][0] if len(ranking) > 1 else -1.0
        aceito = melhor_score >= self.limiar_certeza or (
            melhor_score >= self.limiar_match
            and (melhor_score - segundo) >= MARGEM_MATCH
        )
        if aceito and melhor_id in self._ids_protegidos():
            if melhor_score < self.limiar_certeza or (melhor_score - segundo) < 0.08:
                return None, melhor_score
        if aceito:
            return melhor_id, melhor_score
        return None, melhor_score

    def _ids_protegidos(self) -> set[str]:
        """Pessoas já cadastradas não absorvem um rosto parecido."""
        agora = time.time()
        if agora - getattr(self, "_protegidos_em", 0) < 2:
            return getattr(self, "_protegidos", set())
        try:
            from cadastro import interesse_ativo
            interesse = interesse_ativo() or {}
        except Exception:
            interesse = {}
        ids = {
            str(pessoa.get("face_id") or "").upper()
            for pessoa in interesse.get("pessoas") or []
            if pessoa.get("face_id")
        }
        self._protegidos = ids
        self._protegidos_em = agora
        return ids

    def _anexar_vetor(self, pack, vetor, alinhado):
        linha = vetor.reshape(1, -1).astype(np.float32)
        if alinhado is None:
            linha_alinhada = np.zeros_like(linha)
            tem = np.array([0], dtype=np.uint8)
        else:
            linha_alinhada = alinhado.reshape(1, -1).astype(np.float32)
            tem = np.array([1], dtype=np.uint8)
        if len(pack["vetores"]) == 0:
            pack["vetores"] = linha
            pack["alinhados"] = linha_alinhada
            pack["tem_alinhado"] = tem
            return
        pack["vetores"] = np.vstack([pack["vetores"], linha])
        pack["alinhados"] = np.vstack([pack["alinhados"], linha_alinhada])
        pack["tem_alinhado"] = np.concatenate([pack["tem_alinhado"], tem])

    def _adicionar_amostra(self, face_id, vetor, alinhado):
        if vetor is None or face_id not in self.galeria:
            return
        pack = self.galeria[face_id]
        if len(pack["vetores"]) == 0:
            self._anexar_vetor(pack, vetor, alinhado)
            self._salvar_caracteristicas(face_id)
            return
        score = self._score_contra_id(face_id, vetor, alinhado)
        if face_id in self._ids_protegidos() and score < 0.75:
            return
        if score >= 0.92:
            return
        if len(pack["vetores"]) < MAX_AMOSTRAS:
            self._anexar_vetor(pack, vetor, alinhado)
        else:
            indice = int(np.argmax(pack["vetores"] @ vetor.astype(np.float32)))
            pack["vetores"][indice] = vetor.astype(np.float32)
            if alinhado is not None:
                pack["alinhados"][indice] = alinhado.astype(np.float32)
                pack["tem_alinhado"][indice] = 1
        self._salvar_caracteristicas(face_id)

    def _cadastrar(self, crop, vetor, alinhado):
        face_id = self._novo_face_id()
        pasta = DIR_FACES / face_id
        pasta.mkdir(parents=True, exist_ok=True)
        ref = pasta / "referencia.jpg"
        cv2.imwrite(str(ref), crop)
        pack = self._pacote_vazio()
        self._anexar_vetor(pack, vetor, alinhado)
        self.galeria[face_id] = pack
        self._salvar_caracteristicas(face_id)
        self.cadastro[face_id] = {
            "foto_referencia": str(ref).replace("\\", "/"),
            "total_passagens": 0,
            "primeira_vez": _agora().isoformat(timespec="seconds"),
        }
        return face_id

    def _score_entre_ids(self, origem, destino):
        pack = self.galeria.get(origem)
        if pack is None:
            return -1.0
        melhor = -1.0
        for indice in range(len(pack["vetores"])):
            alinhado = pack["alinhados"][indice] if pack["tem_alinhado"][indice] else None
            melhor = max(
                melhor,
                self._score_contra_id(destino, pack["vetores"][indice], alinhado),
            )
        return melhor

    def _concatenar_galeria(self, destino, origem):
        pacote_destino = self.galeria[destino]
        pacote_origem = self.galeria[origem]
        if len(pacote_origem["vetores"]) == 0:
            return
        if len(pacote_destino["vetores"]) == 0:
            self.galeria[destino] = pacote_origem
            return
        pacote_destino["vetores"] = np.vstack(
            [pacote_destino["vetores"], pacote_origem["vetores"]]
        )
        pacote_destino["alinhados"] = np.vstack(
            [pacote_destino["alinhados"], pacote_origem["alinhados"]]
        )
        pacote_destino["tem_alinhado"] = np.concatenate(
            [pacote_destino["tem_alinhado"], pacote_origem["tem_alinhado"]]
        )
        if len(pacote_destino["vetores"]) > MAX_AMOSTRAS:
            indices = np.linspace(
                0, len(pacote_destino["vetores"]) - 1, MAX_AMOSTRAS
            ).astype(int)
            pacote_destino["vetores"] = pacote_destino["vetores"][indices]
            pacote_destino["alinhados"] = pacote_destino["alinhados"][indices]
            pacote_destino["tem_alinhado"] = pacote_destino["tem_alinhado"][indices]

    def _mover_fotos(self, origem_id, destino_id):
        origem = DIR_FACES / origem_id
        destino = DIR_FACES / destino_id
        destino.mkdir(parents=True, exist_ok=True)
        mapa = {}
        for imagem in origem.glob("*.jpg"):
            if imagem.name == "referencia.jpg":
                continue
            alvo = destino / imagem.name
            if alvo.exists():
                alvo = destino / f"{imagem.stem}_{origem_id}{imagem.suffix}"
            shutil.move(str(imagem), str(alvo))
            antigo = f"evidencias/faces/{origem_id}/{imagem.name}"
            mapa[antigo] = f"evidencias/faces/{destino_id}/{alvo.name}"
        return mapa

    def _fundir_duplicatas(self):
        identidades = list(self.galeria)
        if len(identidades) < 2:
            return
        pai = {identidade: identidade for identidade in identidades}

        def achar(identidade):
            while pai[identidade] != identidade:
                pai[identidade] = pai[pai[identidade]]
                identidade = pai[identidade]
            return identidade

        for indice, origem in enumerate(identidades):
            for destino in identidades[indice + 1:]:
                if self._score_entre_ids(origem, destino) >= self.limiar_fundir:
                    pai[achar(destino)] = achar(origem)

        grupos = {}
        for identidade in identidades:
            grupos.setdefault(achar(identidade), []).append(identidade)

        mapa_ids = {}
        mapa_arquivos = {}
        fundiu = False
        for membros in grupos.values():
            if len(membros) < 2:
                continue
            canon = min(membros)
            fundiu = True
            print(
                "Faces unificadas em "
                f"{canon}: {', '.join(sorted(membros))}"
            )
            for membro in membros:
                mapa_ids[membro] = canon
                if membro == canon:
                    continue
                mapa_arquivos.update(self._mover_fotos(membro, canon))
                self._concatenar_galeria(canon, membro)
                self.galeria.pop(membro, None)
                self.cadastro.pop(membro, None)
                shutil.rmtree(DIR_FACES / membro, ignore_errors=True)
            self._salvar_caracteristicas(canon)
            self._garantir_referencia_colorida(DIR_FACES / canon)
            ref = DIR_FACES / canon / "referencia.jpg"
            if canon in self.cadastro and ref.exists():
                self.cadastro[canon]["foto_referencia"] = str(ref).replace("\\", "/")

        if fundiu:
            self._reescrever_csv_faces(mapa_ids, mapa_arquivos)

    def _reescrever_csv_faces(self, mapa_ids, mapa_arquivos):
        if not os.path.exists(ARQUIVO_FACES):
            return
        campos = [
            "Data", "Hora", "Camera", "Face_ID", "Evento", "Total_Passagens",
            "Track_ID", "Confianca", "Proximidade", "Caminho_Foto", "Foto_Referencia",
        ]
        with open(ARQUIVO_FACES, encoding="utf-8-sig") as arquivo:
            linhas = list(csv.DictReader(arquivo, delimiter=";"))

        contagem = {}
        for linha in linhas:
            antigo = linha.get("Face_ID") or ""
            novo = mapa_ids.get(antigo, antigo)
            linha["Face_ID"] = novo
            caminho = (linha.get("Caminho_Foto") or "").replace("\\", "/")
            if caminho in mapa_arquivos:
                linha["Caminho_Foto"] = mapa_arquivos[caminho]
            else:
                for origem, destino in mapa_ids.items():
                    caminho = caminho.replace(f"/faces/{origem}/", f"/faces/{destino}/")
                linha["Caminho_Foto"] = caminho
            linha["Foto_Referencia"] = f"evidencias/faces/{novo}/referencia.jpg"
            contagem[novo] = contagem.get(novo, 0) + 1
            linha["Total_Passagens"] = contagem[novo]
            linha["Evento"] = "Novo" if contagem[novo] == 1 else "Reaparecimento"

        temporario = ARQUIVO_FACES + ".tmp"
        with open(temporario, "w", newline="", encoding="utf-8-sig") as arquivo:
            escritor = csv.DictWriter(
                arquivo, fieldnames=campos, delimiter=";", extrasaction="ignore"
            )
            escritor.writeheader()
            escritor.writerows(linhas)
        os.replace(temporario, ARQUIVO_FACES)

    def _aplicar_contagens_csv(self):
        if not os.path.exists(ARQUIVO_FACES):
            return
        totais = {}
        try:
            with open(ARQUIVO_FACES, encoding="utf-8-sig") as arquivo:
                for linha in csv.DictReader(arquivo, delimiter=";"):
                    face_id = linha.get("Face_ID") or ""
                    if not face_id:
                        continue
                    try:
                        total = int(linha.get("Total_Passagens") or 0)
                    except ValueError:
                        total = 0
                    totais[face_id] = max(totais.get(face_id, 0), total)
        except Exception:
            return
        for face_id, total in totais.items():
            if face_id in self.cadastro:
                self.cadastro[face_id]["total_passagens"] = total

    def _normalizar(self, vetor):
        vetor = np.asarray(vetor, dtype=np.float32).reshape(-1)
        norma = float(np.linalg.norm(vetor))
        if norma > 0:
            vetor = vetor / norma
        return vetor

    def _embedding_sface(self, imagem_bgr):
        preparado = cv2.resize(imagem_bgr, (112, 112))
        return self._normalizar(self.reconhecedor.feature(preparado))

    def _embedding_classico(self, face_bgr):
        cinza = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        cinza = cv2.resize(cinza, (96, 96))
        cinza = cv2.createCLAHE(2.0, (8, 8)).apply(cinza)
        blocos = cv2.resize(cinza, (12, 12)).astype(np.float32)
        blocos = (blocos - blocos.mean()) / (blocos.std() + 1e-6)
        pequeno = cv2.resize(cinza, (48, 48)).astype(np.float32)
        gradiente_x = cv2.Sobel(pequeno, cv2.CV_32F, 1, 0, ksize=3)
        gradiente_y = cv2.Sobel(pequeno, cv2.CV_32F, 0, 1, ksize=3)
        magnitude = np.sqrt(gradiente_x * gradiente_x + gradiente_y * gradiente_y)
        angulo = (np.rad2deg(np.arctan2(gradiente_y, gradiente_x)) + 180.0) % 180.0
        faixas = np.clip((angulo / (180.0 / 8.0)).astype(np.int32), 0, 7)
        partes = []
        for topo in range(0, 48, 12):
            for esquerda in range(0, 48, 12):
                histograma = np.zeros(8, np.float32)
                pesos = magnitude[topo:topo + 12, esquerda:esquerda + 12].ravel()
                indices = faixas[topo:topo + 12, esquerda:esquerda + 12].ravel()
                for peso, indice in zip(pesos, indices):
                    histograma[int(indice)] += peso
                partes.append(histograma)
        hog = self._normalizar(np.concatenate(partes))
        hsv = cv2.cvtColor(cv2.resize(face_bgr, (64, 64)), cv2.COLOR_BGR2HSV)
        hist_cor = cv2.calcHist(
            [hsv], [0, 1, 2], None, [8, 4, 4], [0, 180, 0, 256, 0, 256]
        ).flatten().astype(np.float32)
        hist_cor = hist_cor / (hist_cor.sum() + 1e-6)
        return self._normalizar(np.concatenate([blocos.ravel() * 0.5, hog, hist_cor * 2.0]))

    def _embedding_alinhado(self, frame, keypoints):
        if self.reconhecedor is None or not keypoints or len(keypoints) < 4:
            return None
        olho_direito, olho_esquerdo, nariz, boca = keypoints[:4]
        distancia = float(np.hypot(
            olho_direito[0] - olho_esquerdo[0],
            olho_direito[1] - olho_esquerdo[1],
        ))
        if distancia < 8:
            return None
        origem = np.array(
            [
                olho_direito,
                olho_esquerdo,
                nariz,
                (boca[0] - 0.35 * distancia, boca[1]),
                (boca[0] + 0.35 * distancia, boca[1]),
            ],
            dtype=np.float32,
        )
        matriz, _ = cv2.estimateAffinePartial2D(origem, PONTOS_SFACE, method=cv2.LMEDS)
        if matriz is None:
            return None
        escala = float(np.hypot(matriz[0, 0], matriz[1, 0]))
        if escala < 0.15 or escala > 8:
            return None
        alinhada = cv2.warpAffine(frame, matriz, (112, 112), borderValue=(0, 0, 0))
        cinza = cv2.cvtColor(alinhada, cv2.COLOR_BGR2GRAY)
        if float((cinza < 8).mean()) > 0.45:
            return None
        return self._embedding_sface(alinhada)

    def _embedding_alinhado_redetect(self, crop):
        if self.reconhecedor is None or self.detector is None or crop is None or crop.size == 0:
            return None
        altura, largura = crop.shape[:2]
        margem = int(max(altura, largura) * 0.6)
        canvas = cv2.copyMakeBorder(
            crop, margem, margem, margem, margem, cv2.BORDER_CONSTANT, value=(0, 0, 0)
        )
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        resultado = self.detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        if not resultado.detections:
            return None
        deteccao = max(
            resultado.detections,
            key=lambda item: item.categories[0].score if item.categories else 0,
        )
        if not deteccao.keypoints or len(deteccao.keypoints) < 4:
            return None
        altura_canvas, largura_canvas = canvas.shape[:2]
        pontos = []
        for ponto in deteccao.keypoints[:4]:
            x, y = float(ponto.x), float(ponto.y)
            if max(abs(x), abs(y)) <= 1.5:
                x, y = x * largura_canvas, y * altura_canvas
            pontos.append((x, y))
        return self._embedding_alinhado(canvas, pontos)

    def _extrair(self, frame, crop, keypoints):
        if crop is None or crop.size == 0:
            return None, None
        if self.reconhecedor is None:
            return self._embedding_classico(crop), None
        try:
            vetor = self._embedding_sface(crop)
        except Exception:
            return None, None
        alinhado = None
        if keypoints and len(keypoints) >= 4:
            try:
                alinhado = self._embedding_alinhado(frame, keypoints)
            except Exception:
                alinhado = None
        if alinhado is None:
            try:
                alinhado = self._embedding_alinhado_redetect(crop)
            except Exception:
                alinhado = None
        return vetor, alinhado

    @staticmethod
    def _crop_util(crop):
        if crop is None or crop.size == 0:
            return False
        cinza = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
        return float(cinza.std()) >= 12

    def _expirar_tracks_face(self, camera, ativos, agora):
        for chave in ativos:
            self.track_visto[chave] = agora
        for chave in list(self.track_visto):
            if chave[0] != camera or chave in ativos:
                continue
            if agora - self.track_visto[chave] > TTL_TRACK_SEG:
                self.track_visto.pop(chave, None)
                self.track_para_face.pop(chave, None)
                self.track_score.pop(chave, None)
                self.track_ultima_amostra.pop(chave, None)

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

            pontos = []
            if det.keypoints:
                altura_crop, largura_crop = crop.shape[:2]
                coordenadas = [(float(kp.x), float(kp.y)) for kp in det.keypoints]
                normalizado = all(
                    max(abs(px), abs(py)) <= 1.5 for px, py in coordenadas
                )
                for px, py in coordenadas:
                    if normalizado:
                        px, py = px * largura_crop, py * altura_crop
                    pontos.append((x1 + px, y1 + py))

            area = largura_f * altura_f
            faces.append({
                "bbox": (fx1, fy1, fx2, fy2),
                "confianca": score,
                "area_frac": area / area_frame,
                "lado_px": min(largura_f, altura_f),
                "keypoints": pontos,
            })

        faces.sort(key=lambda f: f["lado_px"], reverse=True)
        return faces

    def _identificar_face(self, frame, crop, face, camera, track_id, agora):
        """Devolve (face_id, score, novo) reutilizando a galeria de características."""
        chave = (camera, track_id)
        cached = self.track_para_face.get(chave)
        ultimo_calc = self.track_ultima_amostra.get(chave, 0)
        if cached is not None and (agora - ultimo_calc) < INTERVALO_AMOSTRA_FACE:
            return cached, self.track_score.get(chave, 0.0), False

        vetor, alinhado = self._extrair(frame, crop, face.get("keypoints"))
        self.track_ultima_amostra[chave] = agora
        if vetor is None:
            if cached is None:
                return None, 0.0, False
            return cached, self.track_score.get(chave, 0.0), False

        encontrado, score_busca = self._buscar(vetor, alinhado)
        lado = face.get("lado_px", 0)
        pode_cadastrar = lado >= FACE_LADO_MINIMO_CADASTRO and self._crop_util(crop)

        if encontrado is not None and (cached is None or encontrado == cached):
            face_id, score, novo = encontrado, score_busca, False
            self._adicionar_amostra(face_id, vetor, alinhado)
        elif encontrado is not None and cached is not None:
            proprio = self._score_contra_id(cached, vetor, alinhado)
            if score_busca >= self.limiar_certeza and proprio < self.limiar_match:
                face_id, score, novo = encontrado, score_busca, False
                self._adicionar_amostra(face_id, vetor, alinhado)
            else:
                face_id, score, novo = cached, proprio, False
                if proprio >= 0.30 and pode_cadastrar:
                    self._adicionar_amostra(face_id, vetor, alinhado)
        elif cached is not None:
            proprio = self._score_contra_id(cached, vetor, alinhado)
            if proprio < 0.25 and pode_cadastrar:
                face_id = self._cadastrar(crop, vetor, alinhado)
                score, novo = 0.90, True
            else:
                face_id, score, novo = cached, proprio, False
                if proprio >= 0.30 and pode_cadastrar:
                    self._adicionar_amostra(face_id, vetor, alinhado)
        elif pode_cadastrar:
            face_id = self._cadastrar(crop, vetor, alinhado)
            score, novo = 0.90, True
        else:
            return None, score_busca, False

        self.track_para_face[chave] = face_id
        self.track_score[chave] = float(score)
        return face_id, score, novo

    def inscrever_foto(self, imagem):
        """Inclui a foto na galeria e passa a reconhecer o reaparecimento."""
        with self._trava:
            if imagem is None or getattr(imagem, "size", 0) == 0:
                raise ValueError("Envie uma foto com o rosto da pessoa.")
            if not self.disponivel:
                raise ValueError("O reconhecedor de faces não está pronto.")
            altura, largura = imagem.shape[:2]
            faces = self._detectar_faces_no_recorte(imagem, (0, 0, largura, altura))
            if not faces:
                raise ValueError("Nenhum rosto encontrado. Use uma foto de frente, com o rosto visível.")
            face = max(faces, key=lambda item: int(item.get("lado_px") or 0))
            x1, y1, x2, y2 = face["bbox"]
            crop = imagem[y1:y2, x1:x2]
            if not self._crop_util(crop):
                raise ValueError("A foto do rosto está sem nitidez.")
            vetor, alinhado = self._extrair(imagem, crop, face.get("keypoints"))
            if vetor is None:
                raise ValueError("Não foi possível ler as características deste rosto.")
            return self._cadastrar(crop, vetor, alinhado), True

    def substituir_foto(self, face_id, imagem):
        """Troca a referência de um código existente e esquece amostras de outro rosto."""
        with self._trava:
            ident = str(face_id or "").strip().upper()
            if ident not in self.galeria:
                raise ValueError("Este código de face não está na galeria.")
            if imagem is None or getattr(imagem, "size", 0) == 0:
                raise ValueError("Envie uma foto com o rosto da pessoa.")
            altura, largura = imagem.shape[:2]
            faces = self._detectar_faces_no_recorte(imagem, (0, 0, largura, altura))
            if not faces:
                raise ValueError("Nenhum rosto encontrado. Use uma foto de frente, com o rosto visível.")
            face = max(faces, key=lambda item: int(item.get("lado_px") or 0))
            x1, y1, x2, y2 = face["bbox"]
            crop = imagem[y1:y2, x1:x2]
            vetor, alinhado = self._extrair(imagem, crop, face.get("keypoints"))
            if vetor is None:
                raise ValueError("Não foi possível ler as características deste rosto.")
            pack = self._pacote_vazio()
            self._anexar_vetor(pack, vetor, alinhado)
            self.galeria[ident] = pack
            self._salvar_caracteristicas(ident)
            pasta = DIR_FACES / ident
            pasta.mkdir(parents=True, exist_ok=True)
            ref = pasta / "referencia.jpg"
            cv2.imwrite(str(ref), crop)
            self.cadastro.setdefault(ident, {})["foto_referencia"] = str(ref).replace("\\", "/")
            return ident

    def processar(self, camera, frame, pessoas):
        with self._trava:
            return self._processar_bloqueado(camera, frame, pessoas)

    def _processar_bloqueado(self, camera, frame, pessoas):
        """
        pessoas: dict track_id -> {bbox, centro}
        Retorna lista de eventos de passagem e anotações visuais.
        """
        agora = time.time()
        ativos = {(camera, track_id) for track_id in (pessoas or {})}
        self._expirar_tracks_face(camera, ativos, agora)

        eventos = []
        anotacoes = []
        if not self.disponivel or not pessoas:
            return eventos, anotacoes

        h, w = frame.shape[:2]
        area_frame = float(max(h * w, 1))

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

            face_id, score, novo = self._identificar_face(
                frame, crop, face, camera, track_id, agora
            )
            if not face_id:
                continue

            rotulo = f"{face_id} Novo" if novo else f"{face_id} {score:.2f}"
            chave_passagem = (face_id, camera)
            ultimo = self.ultima_passagem.get(chave_passagem, 0)
            if (not novo) and (agora - ultimo) < COOLDOWN_PASSAGEM_FACE_SEG:
                anotacoes.append({
                    "bbox": face["bbox"],
                    "rotulo": rotulo,
                    "confianca": score,
                })
                continue

            self.ultima_passagem[chave_passagem] = agora
            meta = self.cadastro.setdefault(face_id, {
                "foto_referencia": "",
                "total_passagens": 0,
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

            if not meta.get("foto_referencia") or not (pasta / "referencia.jpg").exists():
                ref = pasta / "referencia.jpg"
                cv2.imwrite(str(ref), crop)
                meta["foto_referencia"] = str(ref).replace("\\", "/")

            eventos.append({
                "camera": camera,
                "face_id": face_id,
                "evento": evento,
                "total_passagens": meta["total_passagens"],
                "track_id": track_id,
                "confianca": round(float(score), 2),
                "similaridade": round(float(score), 2),
                "proximidade": round(float(area_pessoa), 3),
                "caminho_foto": str(caminho).replace("\\", "/"),
                "foto_referencia": meta.get("foto_referencia", ""),
            })
            anotacoes.append({
                "bbox": face["bbox"],
                "rotulo": f"{face_id} {evento}",
                "confianca": score,
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
        self.track_confianca = {}
        self.track_visto = {}
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
                    total = 0
                    try:
                        total = int(row.get("Total_Passagens") or 0)
                    except ValueError:
                        total = 0
                    atual = self.cadastro.get(placa, {"total_passagens": 0})
                    self.cadastro[placa] = {
                        "placa_id": placa_id or atual.get("placa_id", ""),
                        "total_passagens": max(
                            atual.get("total_passagens", 0), total
                        ),
                        "foto_referencia": row.get("Foto_Referencia", "")
                            or atual.get("foto_referencia", ""),
                        "assinatura": atual.get("assinatura"),
                    }
                    self._carregar_assinatura(placa)
                    nums = re.findall(r"P(\d+)_", placa_id)
                    if nums:
                        self._seq = max(self._seq, int(nums[0]))
        except Exception:
            pass

    def _carregar_assinatura(self, placa):
        meta = self.cadastro.get(placa)
        if meta is None or meta.get("assinatura") is not None:
            return
        pasta = DIR_PLACAS / placa
        npz = pasta / "caracteristicas.npz"
        if npz.exists():
            try:
                meta["assinatura"] = np.load(str(npz))["assinatura"].astype(np.float32)
                return
            except Exception:
                pass
        for nome in ("referencia.jpg",):
            imagem = cv2.imread(str(pasta / nome))
            if imagem is not None:
                meta["assinatura"] = self._assinatura_veiculo(imagem)
                return

    def _salvar_assinatura(self, placa):
        meta = self.cadastro.get(placa) or {}
        assinatura = meta.get("assinatura")
        if assinatura is None:
            return
        pasta = DIR_PLACAS / placa
        pasta.mkdir(parents=True, exist_ok=True)
        np.savez(pasta / "caracteristicas.npz", assinatura=assinatura.astype(np.float32))

    @staticmethod
    def _assinatura_veiculo(imagem_bgr):
        if imagem_bgr is None or imagem_bgr.size == 0:
            return None
        hsv = cv2.cvtColor(cv2.resize(imagem_bgr, (64, 64)), cv2.COLOR_BGR2HSV)
        hist_h = cv2.calcHist([hsv], [0], None, [16], [0, 180]).flatten()
        hist_s = cv2.calcHist([hsv], [1], None, [8], [0, 256]).flatten()
        matiz = cv2.resize(hsv[:, :, 0], (8, 8)).reshape(-1)
        saturacao = cv2.resize(hsv[:, :, 1], (8, 8)).reshape(-1)
        vetor = np.concatenate([hist_h, hist_s, matiz, saturacao]).astype(np.float32)
        norma = float(np.linalg.norm(vetor))
        if norma > 0:
            vetor /= norma
        return vetor

    def _atualizar_assinatura(self, placa, nova):
        if nova is None or placa not in self.cadastro:
            return
        antiga = self.cadastro[placa].get("assinatura")
        if antiga is None:
            self.cadastro[placa]["assinatura"] = nova
        else:
            mistura = (0.75 * antiga) + (0.25 * nova)
            norma = float(np.linalg.norm(mistura))
            if norma > 0:
                mistura = mistura / norma
            self.cadastro[placa]["assinatura"] = mistura.astype(np.float32)
        self._salvar_assinatura(placa)

    @staticmethod
    def _cosseno(a, b):
        if a is None or b is None:
            return 0.0
        return float(np.dot(a, b))

    @staticmethod
    def _distancia_placa(a, b):
        if not a or not b or len(a) != len(b):
            return 99
        return sum(caractere_a != caractere_b for caractere_a, caractere_b in zip(a, b))

    def _resolver_placa(self, texto, assinatura):
        if texto in self.cadastro:
            return texto
        melhor = None
        melhor_sim = 0.0
        for conhecida, meta in self.cadastro.items():
            if self._distancia_placa(texto, conhecida) != 1:
                continue
            sim = self._cosseno(assinatura, meta.get("assinatura"))
            if sim >= SIMILARIDADE_PLACA_VISUAL and sim > melhor_sim:
                melhor = conhecida
                melhor_sim = sim
        return melhor or texto

    def _expirar_tracks_placa(self, camera, ativos, agora):
        for chave in ativos:
            self.track_visto[chave] = agora
        for chave in list(self.track_visto):
            if chave[0] != camera or chave in ativos:
                continue
            if agora - self.track_visto[chave] > TTL_TRACK_SEG:
                self.track_visto.pop(chave, None)
                self.track_para_placa.pop(chave, None)
                self.track_confianca.pop(chave, None)
                self.ultimo_ocr_track.pop(chave, None)

    @staticmethod
    def _normalizar_texto(texto: str) -> str:
        texto = texto.upper()
        return re.sub(r"[^A-Z0-9]", "", texto)

    @staticmethod
    def _para_letra(caractere):
        if caractere.isalpha():
            return caractere
        return _LETRA_DE.get(caractere)

    @staticmethod
    def _para_digito(caractere):
        if caractere.isdigit():
            return caractere
        return _DIGITO_DE.get(caractere)

    def _forcar_padrao(self, texto):
        if len(texto) != 7:
            return None
        opcoes = []
        for tipo in ("mercosul", "antiga"):
            chars = []
            mudancas = 0
            valido = True
            for indice, caractere in enumerate(texto):
                quer_letra = indice in (0, 1, 2, 4) if tipo == "mercosul" else indice in (0, 1, 2)
                convertido = self._para_letra(caractere) if quer_letra else self._para_digito(caractere)
                if not convertido:
                    valido = False
                    break
                if convertido != caractere:
                    mudancas += 1
                chars.append(convertido)
            if valido and mudancas <= 2:
                opcoes.append(("".join(chars), mudancas))
        if not opcoes:
            return None
        opcoes.sort(key=lambda item: item[1])
        return opcoes[0][0]

    def _juntar_fragmentos(self, textos):
        itens = []
        for item in textos:
            if not isinstance(item, (list, tuple)) or len(item) < 3:
                continue
            caixa, txt, conf = item[0], item[1], float(item[2])
            try:
                xs = [ponto[0] for ponto in caixa]
                ys = [ponto[1] for ponto in caixa]
            except Exception:
                xs, ys = [0], [0]
            itens.append({
                "x": min(xs),
                "y": sum(ys) / len(ys),
                "txt": self._normalizar_texto(str(txt)),
                "conf": conf,
            })
        itens.sort(key=lambda item: (item["y"], item["x"]))
        if not itens:
            return []
        linhas = [[itens[0]]]
        for item in itens[1:]:
            if abs(item["y"] - linhas[-1][0]["y"]) > 25:
                linhas.append([item])
            else:
                linhas[-1].append(item)
        saida = []
        for linha in linhas:
            linha.sort(key=lambda item: item["x"])
            junto = "".join(item["txt"] for item in linha)
            conf = sum(item["conf"] for item in linha) / len(linha)
            saida.append((junto, conf))
            for item in linha:
                saida.append((item["txt"], item["conf"]))
        return saida

    def _extrair_placa(self, textos):
        candidatos = []
        for texto, conf in self._juntar_fragmentos(textos):
            limpo = self._normalizar_texto(texto)
            if len(limpo) < 7:
                continue
            for inicio in range(0, len(limpo) - 6):
                janela = limpo[inicio:inicio + 7]
                if PADRAO_PLACA.fullmatch(janela) and conf >= CONF_OCR_MINIMA:
                    candidatos.append((janela, conf))
                    continue
                corrigida = self._forcar_padrao(janela)
                if corrigida is None or conf < CONF_OCR_CORRIGIDA:
                    continue
                mudancas = sum(a != b for a, b in zip(janela, corrigida))
                if mudancas <= 2:
                    candidatos.append((corrigida, conf * (1 - 0.15 * mudancas)))
        if not candidatos:
            return None, 0.0
        candidatos.sort(key=lambda item: item[1], reverse=True)
        return candidatos[0]

    def _ler_placa(self, crop):
        if crop is None or crop.size == 0 or crop.shape[0] < 12 or crop.shape[1] < 28:
            return None, 0.0
        maior = max(crop.shape[:2])
        if maior > 640:
            fator = 640 / maior
            crop = cv2.resize(
                crop,
                (max(1, int(crop.shape[1] * fator)), max(1, int(crop.shape[0] * fator))),
                interpolation=cv2.INTER_AREA,
            )
        escala = 3 if max(crop.shape[:2]) < 220 else 2
        ampliada = cv2.resize(
            crop, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC
        )
        cinza = cv2.cvtColor(ampliada, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(2.0, (8, 8)).apply(cinza)
        variantes = [
            ampliada,
            cv2.cvtColor(clahe, cv2.COLOR_GRAY2BGR),
        ]
        textos = []
        for imagem in variantes:
            try:
                textos.extend(self._ocr(imagem))
            except Exception:
                continue
            texto, confianca = self._extrair_placa(textos)
            if texto and confianca >= 0.60:
                return texto, confianca
        return self._extrair_placa(textos)

    def _registrar_placa(self, placa, crop_veiculo, assinatura, novo):
        pasta = DIR_PLACAS / placa
        pasta.mkdir(parents=True, exist_ok=True)
        ref = pasta / "referencia.jpg"
        if novo or not ref.exists():
            cv2.imwrite(str(ref), crop_veiculo)
        meta = self.cadastro.get(placa)
        if meta is None:
            meta = {
                "placa_id": self._novo_placa_id(placa),
                "total_passagens": 0,
                "foto_referencia": str(ref).replace("\\", "/"),
                "assinatura": assinatura,
            }
            self.cadastro[placa] = meta
        elif not meta.get("foto_referencia"):
            meta["foto_referencia"] = str(ref).replace("\\", "/")
        if assinatura is not None:
            self._atualizar_assinatura(placa, assinatura)
        return meta

    def processar(self, camera, frame, veiculos, frame_nitido=None):
        """
        veiculos: dict track_id -> {bbox, classe, bbox_nitida}
        A leitura usa o quadro original da câmera. O quadro da análise só desenha.
        """
        agora = time.time()
        ativos = {(camera, track_id) for track_id in (veiculos or {})}
        self._expirar_tracks_placa(camera, ativos, agora)

        eventos = []
        anotacoes = []
        if not self.disponivel or not veiculos:
            return eventos, anotacoes

        origem = frame_nitido if frame_nitido is not None else frame
        h, w = origem.shape[:2]

        for track_id, info in veiculos.items():
            chave_track = (camera, track_id)
            x1, y1, x2, y2 = map(int, info.get("bbox_nitida") or info["bbox"])
            largura = max(1, x2 - x1)
            altura = max(1, y2 - y1)
            margem_x = int(largura * 0.06)
            margem_y = int(altura * 0.06)
            x1 = max(0, x1 - margem_x)
            y1 = max(0, y1 - margem_y)
            x2 = min(w, x2 + margem_x)
            y2 = min(h, y2 + margem_y)
            veiculo = origem[y1:y2, x1:x2]
            if veiculo.size == 0 or veiculo.shape[0] < 30 or veiculo.shape[1] < 40:
                continue

            cached = self.track_para_placa.get(chave_track)
            ultimo = self.ultimo_ocr_track.get(chave_track, 0)
            intervalo = REOCR_TRACK_SEG if cached else INTERVALO_OCR_VEICULO
            placa = cached
            conf = self.track_confianca.get(chave_track, 0.0)
            assinatura = self._assinatura_veiculo(veiculo)

            if agora - ultimo >= intervalo:
                self.ultimo_ocr_track[chave_track] = agora
                altura_v = veiculo.shape[0]
                faixas = [
                    veiculo[int(altura_v * 0.62):, :],
                    veiculo[int(altura_v * 0.40):, :],
                    veiculo[int(altura_v * 0.25):int(altura_v * 0.80), :],
                ]
                melhor_txt, melhor_conf = None, 0.0
                for faixa in faixas:
                    texto, confianca = self._ler_placa(faixa)
                    if texto and confianca > melhor_conf:
                        melhor_txt, melhor_conf = texto, confianca
                    if melhor_conf >= 0.70:
                        break
                if melhor_txt:
                    canon = self._resolver_placa(melhor_txt, assinatura)
                    if (
                        cached
                        and canon != cached
                        and not (
                            melhor_conf >= 0.55
                            and self.track_confianca.get(chave_track, 0) < 0.45
                        )
                    ):
                        placa = cached
                    else:
                        placa = canon
                        conf = melhor_conf
                        self.track_para_placa[chave_track] = placa
                        self.track_confianca[chave_track] = conf

            if not placa:
                continue

            meta = self.cadastro.get(placa)
            novo = meta is None
            anterior = None if novo else (meta or {}).get("assinatura")
            similaridade = self._cosseno(assinatura, anterior) if anterior is not None else None
            if novo:
                meta = self._registrar_placa(placa, veiculo, assinatura, True)

            chave_passagem = (placa, camera)
            ultimo_pass = self.ultima_passagem.get(chave_passagem, 0)
            if (agora - ultimo_pass) < COOLDOWN_PASSAGEM_PLACA_SEG and not novo:
                anotacoes.append({
                    "bbox": info["bbox"],
                    "rotulo": f"{placa} {conf:.2f}",
                    "confianca": conf,
                })
                continue

            self.ultima_passagem[chave_passagem] = agora
            if not novo:
                self._atualizar_assinatura(placa, assinatura)
            meta["total_passagens"] = int(meta.get("total_passagens", 0)) + 1
            evento = "Novo" if novo else "Reaparecimento"

            pasta = DIR_PLACAS / placa
            pasta.mkdir(parents=True, exist_ok=True)
            nome_foto = (
                f"{_agora().strftime('%Y%m%d_%H%M%S')}_"
                f"{camera.replace(' ', '')}_t{track_id}.jpg"
            )
            caminho = pasta / nome_foto
            cv2.imwrite(str(caminho), veiculo)

            eventos.append({
                "camera": camera,
                "placa_id": meta["placa_id"],
                "placa": placa,
                "evento": evento,
                "total_passagens": meta["total_passagens"],
                "track_id": track_id,
                "tipo_veiculo": info.get("classe", "Veiculo"),
                "confianca": round(float(conf), 2),
                "similaridade": None if similaridade is None else round(float(similaridade), 2),
                "caminho_foto": str(caminho).replace("\\", "/"),
                "foto_referencia": meta.get("foto_referencia", ""),
            })
            anotacoes.append({
                "bbox": info["bbox"],
                "rotulo": f"{placa} {evento}",
                "confianca": conf,
            })

        return eventos, anotacoes
