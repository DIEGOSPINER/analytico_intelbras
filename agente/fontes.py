"""
Leitura dos históricos. Hoje os dados vêm de CSV; a função `resumo`
devolve um pacote estável para o modelo. Uma fonte de banco depois
precisa produzir o mesmo pacote.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


ARQUIVOS = {
    "analitico": "historico_analitico.csv",
    "ocorrencias": "historico_ocorrencias.csv",
    "faces": "historico_faces.csv",
    "placas": "historico_placas.csv",
    "contagem": "historico_contagem.csv",
    "pessoas": "historico_pessoas.csv",
}

ARQUIVO_INTERESSE = "interesse.json"


def periodo(nome: str, referencia: date | None = None):
    hoje = referencia or date.today()
    if nome == "dia":
        return hoje, hoje
    if nome == "semana":
        return hoje - timedelta(days=6), hoje
    if nome == "mes":
        return hoje.replace(day=1), hoje
    raise ValueError("Período deve ser dia, semana ou mes.")


def ler_tabela(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return []
    texto = caminho.read_text(encoding="utf-8-sig")
    if not texto.strip():
        return []
    primeira = texto.splitlines()[0]
    delimitador = ";" if primeira.count(";") >= primeira.count(",") else ","
    return list(csv.DictReader(io.StringIO(texto), delimiter=delimitador))


def _data(linha: dict):
    bruto = (linha.get("Data") or "")[:10]
    try:
        return datetime.strptime(bruto, "%Y-%m-%d").date()
    except ValueError:
        return None


def _no_periodo(linhas, inicio: date, fim: date):
    return [linha for linha in linhas if (data := _data(linha)) and inicio <= data <= fim]


def _inteiro(valor, padrao=0):
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return padrao


def carregar_interesse(caminho=ARQUIVO_INTERESSE) -> dict:
    path = Path(caminho)
    if not path.exists():
        return {"pessoas": [], "veiculos": []}
    try:
        bruto = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"interesse.json inválido: {exc}") from exc
    return {
        "pessoas": list(bruto.get("pessoas") or []),
        "veiculos": list(bruto.get("veiculos") or []),
    }


def indice_interesse(interesse: dict):
    pessoas = {}
    for item in interesse.get("pessoas") or []:
        face_id = str(item.get("face_id") or "").strip().upper()
        if face_id:
            pessoas[face_id] = item
    veiculos = {}
    for item in interesse.get("veiculos") or []:
        placa = str(item.get("placa") or "").strip().upper()
        if placa:
            veiculos[placa] = item
    return pessoas, veiculos


class FonteCsv:
    """Pacote de leitura dos CSVs atuais."""

    def __init__(self, pasta="."):
        self.pasta = Path(pasta)

    def linhas(self, chave: str) -> list[dict]:
        return ler_tabela(self.pasta / ARQUIVOS[chave])

    def resumo(self, inicio: date, fim: date) -> dict:
        analitico = _no_periodo(self.linhas("analitico"), inicio, fim)
        ocorrencias = _no_periodo(self.linhas("ocorrencias"), inicio, fim)
        faces = _no_periodo(self.linhas("faces"), inicio, fim)
        placas = _no_periodo(self.linhas("placas"), inicio, fim)
        contagem = _no_periodo(self.linhas("contagem"), inicio, fim)
        pessoas = _no_periodo(self.linhas("pessoas"), inicio, fim)

        por_categoria = Counter((linha.get("Categoria") or "") for linha in analitico)
        por_camera = Counter((linha.get("Camera") or "") for linha in analitico)
        por_hora = Counter((linha.get("Hora") or "")[:2] for linha in analitico if linha.get("Hora"))
        riscos = Counter((linha.get("Risco") or "Sem risco") for linha in ocorrencias)
        comportamentos = Counter((linha.get("Classe") or "") for linha in ocorrencias)

        prioritarias = []
        for linha in ocorrencias:
            nivel = _inteiro(linha.get("Nivel_Risco"), 1)
            if nivel < 2:
                continue
            prioritarias.append({
                "data": linha.get("Data"),
                "hora": linha.get("Hora"),
                "camera": linha.get("Camera"),
                "classe": linha.get("Classe"),
                "risco": linha.get("Risco"),
                "nivel": nivel,
                "detalhe": linha.get("Detalhe") or "",
                "duracao_segundos": linha.get("Duracao_Segundos") or "",
            })
        prioritarias.sort(key=lambda item: (item["nivel"], item["data"] or "", item["hora"] or ""), reverse=True)

        faces_por_id = {}
        for linha in faces:
            face_id = (linha.get("Face_ID") or "").strip()
            if not face_id:
                continue
            atual = faces_por_id.setdefault(face_id, {
                "face_id": face_id,
                "registros": 0,
                "total_passagens": 0,
                "cameras": [],
                "ultimo": "",
                "foto_referencia": linha.get("Foto_Referencia") or "",
            })
            atual["registros"] += 1
            atual["total_passagens"] = max(
                atual["total_passagens"], _inteiro(linha.get("Total_Passagens"))
            )
            camera = linha.get("Camera") or ""
            if camera and camera not in atual["cameras"]:
                atual["cameras"].append(camera)
            atual["ultimo"] = f"{linha.get('Data')} {linha.get('Hora')}"
            if linha.get("Foto_Referencia"):
                atual["foto_referencia"] = linha["Foto_Referencia"]
        faces_rank = sorted(
            faces_por_id.values(),
            key=lambda item: item["total_passagens"],
            reverse=True,
        )[:15]

        placas_por_id = {}
        for linha in placas:
            placa = (linha.get("Placa") or "").strip().upper()
            if not placa:
                continue
            atual = placas_por_id.setdefault(placa, {
                "placa": placa,
                "placa_id": linha.get("Placa_ID") or "",
                "tipo": linha.get("Tipo_Veiculo") or "",
                "registros": 0,
                "total_passagens": 0,
                "cameras": [],
                "ultimo": "",
                "foto_referencia": linha.get("Foto_Referencia") or "",
            })
            atual["registros"] += 1
            atual["total_passagens"] = max(
                atual["total_passagens"], _inteiro(linha.get("Total_Passagens"))
            )
            camera = linha.get("Camera") or ""
            if camera and camera not in atual["cameras"]:
                atual["cameras"].append(camera)
            atual["ultimo"] = f"{linha.get('Data')} {linha.get('Hora')}"

        placas_rank = sorted(
            placas_por_id.values(),
            key=lambda item: item["total_passagens"],
            reverse=True,
        )[:15]

        ocupacao = defaultdict(list)
        for linha in contagem:
            chave = f"{linha.get('Camera')}|{(linha.get('Hora') or '')[:2]}"
            ocupacao[chave].append((
                _inteiro(linha.get("Pessoas")),
                _inteiro(linha.get("Veiculos")),
            ))
        ocupacao_hora = []
        for chave, pares in sorted(ocupacao.items()):
            camera, hora = chave.split("|", 1)
            ocupacao_hora.append({
                "camera": camera,
                "hora": hora,
                "pessoas_max": max(par[0] for par in pares),
                "veiculos_max": max(par[1] for par in pares),
            })

        return {
            "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
            "volume": {
                "deteccoes": len(analitico),
                "por_categoria": dict(por_categoria),
                "por_camera": dict(por_camera),
                "por_hora": dict(sorted(por_hora.items())),
                "rastreios_pessoa": len(pessoas),
            },
            "ocorrencias": {
                "total": len(ocorrencias),
                "por_risco": dict(riscos),
                "por_comportamento": dict(comportamentos),
                "prioritarias": prioritarias[:25],
            },
            "faces": {
                "registros": len(faces),
                "identidades": len(faces_por_id),
                "mais_recorrentes": faces_rank,
            },
            "veiculos": {
                "registros": len(placas),
                "placas": len(placas_por_id),
                "mais_recorrentes": placas_rank,
            },
            "ocupacao_por_hora": ocupacao_hora[:48],
            "nota": (
                "ID do histórico analítico é o rastreio do YOLO na cena, "
                "não a identidade da face. Face_ID e Placa identificam a pessoa e o veículo."
            ),
        }


def cruzar_interesse(faces: list[dict], placas: list[dict], interesse: dict) -> list[dict]:
    pessoas, veiculos = indice_interesse(interesse)
    alertas = []
    for linha in faces:
        face_id = (linha.get("Face_ID") or "").strip().upper()
        item = pessoas.get(face_id)
        if not item:
            continue
        alertas.append({
            "tipo": "pessoa",
            "id": face_id,
            "nome": item.get("nome") or face_id,
            "motivo": item.get("motivo") or "",
            "data": linha.get("Data") or "",
            "hora": linha.get("Hora") or "",
            "camera": linha.get("Camera") or "",
            "evento": linha.get("Evento") or "",
            "passagens": linha.get("Total_Passagens") or "",
            "foto": linha.get("Caminho_Foto") or linha.get("Foto_Referencia") or "",
        })
    for linha in placas:
        placa = (linha.get("Placa") or "").strip().upper()
        item = veiculos.get(placa)
        if not item:
            continue
        alertas.append({
            "tipo": "veiculo",
            "id": placa,
            "nome": item.get("nome") or item.get("descricao") or placa,
            "motivo": item.get("motivo") or "",
            "data": linha.get("Data") or "",
            "hora": linha.get("Hora") or "",
            "camera": linha.get("Camera") or "",
            "evento": linha.get("Evento") or "",
            "passagens": linha.get("Total_Passagens") or "",
            "foto": linha.get("Caminho_Foto") or linha.get("Foto_Referencia") or "",
            "tipo_veiculo": linha.get("Tipo_Veiculo") or "",
        })
    return alertas
