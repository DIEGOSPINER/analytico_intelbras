"""Ocorrências informadas pelo cliente.

O relato fica na conta de quem informou. A descrição é lida para achar
pessoas, placas e situações já conhecidas nessa conta ou vistas pelas
câmeras dela. O arquivo de fenômenos guarda só contagens, sem nome,
documento, placa, endereço ou mídia de ninguém.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from agente.fontes import ler_tabela
from cadastro import cliente_ativo, garantir_cliente_local


ARQUIVO = Path("ocorrencias_informadas.json")
ARQUIVO_FENOMENOS = Path("fenomenos.json")
ARQUIVO_CSV = Path("historico_ocorrencias_informadas.csv")
PASTA_MIDIA = Path("evidencias") / "ocorrencias"

COLUNAS = [
    "Data", "Hora", "Natureza", "Descricao", "Endereco", "Latitude", "Longitude",
    "Placa", "Pessoa", "Pessoas_Ligadas", "Veiculos_Ligados", "Situacoes",
    "Foto", "Video", "Cliente_Documento", "Id",
]

_PLACA = re.compile(
    r"\b([A-Za-z]{3})\s*-?\s*(\d[A-Za-z0-9]\d{2}|\d{4})\b",
    re.IGNORECASE,
)
_SITUACOES = {
    "queda": "Possivel_Queda",
    "briga": "Possivel_Briga",
    "arma": "Possivel_Arma",
    "tiro": "Possivel_Arma",
    "disparo": "Possivel_Arma",
    "roubo": "Roubo",
    "furto": "Furto",
    "assalto": "Assalto",
    "suspeito": "Suspeito",
    "suspeita": "Suspeito",
    "agress": "Agressao",
    "incendio": "Incendio",
    "incêndio": "Incendio",
    "acidente": "Acidente",
    "invas": "Invasao",
    "grito": "Perturbacao",
    "persegui": "Perseguicao",
    "correndo": "Correndo",
    "correu": "Correndo",
    "deitado": "Deitado",
    "discuss": "Discussao",
}
_FOTOS = {".jpg", ".jpeg", ".png", ".webp"}
_VIDEOS = {".mp4", ".mov", ".avi", ".mkv"}


def _ler() -> list[dict]:
    if not ARQUIVO.exists():
        return []
    try:
        bruto = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"ocorrencias_informadas.json inválido: {exc}") from exc
    if isinstance(bruto, dict):
        return list(bruto.get("ocorrencias") or [])
    if isinstance(bruto, list):
        return bruto
    return []


def _gravar(registros: list[dict]):
    ARQUIVO.write_text(
        json.dumps({"ocorrencias": registros}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _cliente(documento: str = ""):
    garantir_cliente_local()
    if documento:
        from cadastro import cliente_por_documento
        cliente = cliente_por_documento(documento)
    else:
        cliente = cliente_ativo()
    if cliente is None:
        raise ValueError("Conta não encontrada para este CPF ou CNPJ.")
    return cliente


def _data_hora(data, hora) -> tuple[str, str]:
    texto_data = str(data or "").strip()
    texto_hora = str(hora or "").strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            texto_data = datetime.strptime(texto_data, formato).strftime("%Y-%m-%d")
            break
        except ValueError:
            continue
    else:
        raise ValueError("Informe a data no formato AAAA-MM-DD.")
    if len(texto_hora) == 5:
        texto_hora += ":00"
    try:
        texto_hora = datetime.strptime(texto_hora, "%H:%M:%S").strftime("%H:%M:%S")
    except ValueError as exc:
        raise ValueError("Informe a hora no formato HH:MM.") from exc
    return texto_data, texto_hora


def _coordenada(valor, limite: float):
    if valor in (None, ""):
        return None
    try:
        numero = float(str(valor).replace(",", "."))
    except ValueError as exc:
        raise ValueError("Latitude e longitude precisam ser números.") from exc
    if not -limite <= numero <= limite:
        raise ValueError("Latitude ou longitude fora do intervalo.")
    return round(numero, 6)


def _placas_no_texto(texto: str) -> list[str]:
    achadas = []
    for grupo in _PLACA.findall(texto or ""):
        placa = (grupo[0] + grupo[1]).upper()
        if placa not in achadas:
            achadas.append(placa)
    return achadas


def _situacoes_no_texto(texto: str) -> list[str]:
    baixo = (texto or "").lower()
    achadas = []
    for trecho, nome in _SITUACOES.items():
        if trecho in baixo and nome not in achadas:
            achadas.append(nome)
    return achadas


def _vistas_na_rua() -> tuple[set[str], set[str]]:
    placas = {
        (linha.get("Placa") or "").strip().upper()
        for linha in ler_tabela(Path("historico_placas.csv"))
    }
    faces = {
        (linha.get("Face_ID") or "").strip().upper()
        for linha in ler_tabela(Path("historico_faces.csv"))
    }
    return {item for item in placas if item}, {item for item in faces if item}


def extrair_vinculos(descricao: str, cliente: dict, placa="", pessoa="") -> dict:
    """Liga o texto ao cadastro do próprio cliente e ao que as câmeras dele já viram."""
    texto = descricao or ""
    placas_vistas, faces_vistas = _vistas_na_rua()
    pessoas = []
    veiculos = []
    for item in cliente.get("pessoas") or []:
        nome = str(item.get("nome") or "").strip()
        face_id = str(item.get("face_id") or "").strip().upper()
        if nome and nome.lower() in texto.lower():
            pessoas.append({"nome": nome, "id": face_id, "origem": "cadastro"})
        elif face_id and face_id in texto.upper():
            pessoas.append({"nome": nome or face_id, "id": face_id, "origem": "cadastro"})
    if pessoa and not any(item["nome"].lower() == pessoa.lower() for item in pessoas):
        pessoas.append({"nome": pessoa, "id": "", "origem": "informe"})
    for face_id in faces_vistas:
        if face_id in texto.upper() and not any(item["id"] == face_id for item in pessoas):
            pessoas.append({"nome": face_id, "id": face_id, "origem": "cameras"})
    for placa_texto in _placas_no_texto(texto):
        conhecida = any(
            str(item.get("placa") or "").upper() == placa_texto
            for item in cliente.get("veiculos") or []
        )
        if conhecida:
            origem = "cadastro"
        elif placa_texto in placas_vistas:
            origem = "cameras"
        else:
            origem = "descricao"
        veiculos.append({"placa": placa_texto, "origem": origem})
    if placa and not any(item["placa"] == placa.upper() for item in veiculos):
        veiculos.append({"placa": placa.upper(), "origem": "informe"})
    return {
        "pessoas": pessoas,
        "veiculos": veiculos,
        "situacoes": _situacoes_no_texto(f"{texto} {pessoa}"),
    }


def _completar_com_modelo(descricao: str, vinculos: dict, cliente: dict) -> dict:
    from agente.modelo import SessaoGPT, extrair_json

    sessao = SessaoGPT()
    if not sessao.disponivel or not (descricao or "").strip():
        return vinculos
    conhecidos = {
        "pessoas": [item.get("nome") for item in cliente.get("pessoas") or [] if item.get("nome")],
        "placas": [item.get("placa") for item in cliente.get("veiculos") or [] if item.get("placa")],
    }
    try:
        texto = sessao.perguntar(
            "Extraia apenas o que estiver na descrição. Responda em JSON com as chaves "
            "pessoas (lista de nomes), veiculos (lista de placas) e situacoes (lista curta). "
            "Não invente nome ou placa ausente do texto.",
            json.dumps({"descricao": descricao, "ja_cadastrados": conhecidos}, ensure_ascii=False),
        )
        extra = extrair_json(texto)
    except (RuntimeError, json.JSONDecodeError, ValueError):
        return vinculos
    for nome in extra.get("pessoas") or []:
        nome = str(nome).strip()
        if nome and not any(item["nome"].lower() == nome.lower() for item in vinculos["pessoas"]):
            cadastrada = any(
                str(item.get("nome") or "").lower() == nome.lower()
                for item in cliente.get("pessoas") or []
            )
            vinculos["pessoas"].append({
                "nome": nome,
                "id": "",
                "origem": "cadastro" if cadastrada else "descricao",
            })
    for placa in extra.get("veiculos") or []:
        for normal in _placas_no_texto(str(placa)) or [str(placa).upper()]:
            if normal and not any(item["placa"] == normal for item in vinculos["veiculos"]):
                vinculos["veiculos"].append({"placa": normal, "origem": "descricao"})
    for situacao in extra.get("situacoes") or []:
        situacao = str(situacao).strip()
        if situacao and situacao not in vinculos["situacoes"]:
            vinculos["situacoes"].append(situacao)
    return vinculos


def informar_ocorrencia(documento: str = "", dados: dict | None = None, usar_modelo=True) -> dict:
    dados = dados or {}
    cliente = _cliente(documento)
    data, hora = _data_hora(dados.get("data"), dados.get("hora"))
    natureza = str(dados.get("natureza") or "").strip()
    descricao = str(dados.get("descricao") or "").strip()
    if not natureza or not descricao:
        raise ValueError("Informe a natureza e a descrição da ocorrência.")
    placa = str(dados.get("placa") or "").strip().upper()
    pessoa = str(dados.get("pessoa") or "").strip()
    vinculos = extrair_vinculos(descricao, cliente, placa, pessoa)
    if usar_modelo:
        vinculos = _completar_com_modelo(descricao, vinculos, cliente)
    registro = {
        "id": "oc-" + datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "cliente_id": cliente.get("id") or "",
        "documento": cliente.get("documento") or "",
        "data": data,
        "hora": hora,
        "natureza": natureza,
        "descricao": descricao,
        "latitude": _coordenada(dados.get("latitude"), 90),
        "longitude": _coordenada(dados.get("longitude"), 180),
        "endereco": str(dados.get("endereco") or "").strip(),
        "placa": placa,
        "pessoa": pessoa,
        "foto": "",
        "video": "",
        "extraido": vinculos,
        "criado_em": datetime.now().isoformat(timespec="seconds"),
    }
    registros = _ler()
    registros.append(registro)
    _gravar(registros)
    _anexar_csv(registro)
    _atualizar_fenomenos(registros)
    return registro


def anexar_midia(documento: str, ocorrencia_id: str, origem, tipo: str) -> str:
    if tipo not in ("foto", "video"):
        raise ValueError("O anexo deve ser foto ou vídeo.")
    caminho = Path(origem)
    if not caminho.is_file():
        raise ValueError("Arquivo de foto ou vídeo não encontrado.")
    permitidas = _FOTOS if tipo == "foto" else _VIDEOS
    if caminho.suffix.lower() not in permitidas:
        raise ValueError("Formato de arquivo não aceito para este anexo.")
    cliente = _cliente(documento)
    registros = _ler()
    registro = next((item for item in registros if item.get("id") == ocorrencia_id), None)
    if registro is None or registro.get("cliente_id") != cliente.get("id"):
        raise ValueError("Ocorrência não encontrada nesta conta.")
    destino_pasta = PASTA_MIDIA / str(cliente.get("id") or "conta") / ocorrencia_id
    destino_pasta.mkdir(parents=True, exist_ok=True)
    destino = destino_pasta / f"{tipo}{caminho.suffix.lower()}"
    shutil.copy2(caminho, destino)
    registro[tipo] = str(destino).replace("\\", "/")
    _gravar(registros)
    return registro[tipo]


def listar_ocorrencias(documento: str = "", inicio: str = "", fim: str = "") -> list[dict]:
    cliente = _cliente(documento)
    itens = [
        item for item in _ler()
        if item.get("cliente_id") == cliente.get("id")
    ]
    if inicio:
        itens = [item for item in itens if (item.get("data") or "") >= inicio]
    if fim:
        itens = [item for item in itens if (item.get("data") or "") <= fim]
    return itens


def para_relatorio(inicio: str, fim: str, documento: str = "") -> list[dict]:
    """Versão enviada ao modelo: sem caminho de mídia de outra conta."""
    saida = []
    for item in listar_ocorrencias(documento, inicio, fim):
        saida.append({
            "data": item.get("data"),
            "hora": item.get("hora"),
            "natureza": item.get("natureza"),
            "descricao": item.get("descricao"),
            "endereco": item.get("endereco"),
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "placa": item.get("placa"),
            "pessoa": item.get("pessoa"),
            "extraido": item.get("extraido") or {},
            "tem_foto": bool(item.get("foto")),
            "tem_video": bool(item.get("video")),
        })
    return saida


def resumo_fenomenos(limite: int = 20) -> list[dict]:
    if not ARQUIVO_FENOMENOS.exists():
        return []
    try:
        bruto = json.loads(ARQUIVO_FENOMENOS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    itens = list(bruto.get("fenomenos") or [])
    itens.sort(key=lambda item: item.get("quantidade") or 0, reverse=True)
    return itens[:limite]


def _natureza_agregada(item: dict) -> str:
    from cadastro import listar_clientes

    natureza = str(item.get("natureza") or "").strip()
    reservados = []
    for cliente in listar_clientes():
        reservados.extend(str(pessoa.get("nome") or "") for pessoa in cliente.get("pessoas") or [])
        reservados.extend(str(veiculo.get("placa") or "") for veiculo in cliente.get("veiculos") or [])
    baixo = natureza.lower()
    for reservado in reservados:
        if len(reservado) > 2 and reservado.lower() in baixo:
            return "Informe"
    return natureza[:40]


def _atualizar_fenomenos(registros: list[dict]):
    dias = ("segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo")
    contagem = {}
    for item in registros:
        try:
            dia = dias[datetime.strptime(item.get("data") or "", "%Y-%m-%d").weekday()]
        except ValueError:
            dia = ""
        faixa = (item.get("hora") or "")[:2]
        area = ""
        if item.get("latitude") is not None and item.get("longitude") is not None:
            area = f"{round(item['latitude'], 2):.2f},{round(item['longitude'], 2):.2f}"
        situacoes = (item.get("extraido") or {}).get("situacoes") or [""]
        for situacao in situacoes:
            chave = (_natureza_agregada(item), situacao, faixa, dia, area)
            contagem[chave] = contagem.get(chave, 0) + 1
    fenomenos = [
        {
            "natureza": natureza,
            "situacao": situacao,
            "faixa_hora": faixa,
            "dia_semana": dia,
            "area": area,
            "quantidade": quantidade,
        }
        for (natureza, situacao, faixa, dia, area), quantidade in contagem.items()
    ]
    ARQUIVO_FENOMENOS.write_text(
        json.dumps(
            {"atualizado_em": datetime.now().isoformat(timespec="seconds"), "fenomenos": fenomenos},
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


def _anexar_csv(registro: dict):
    novo = not ARQUIVO_CSV.exists()
    extra = registro.get("extraido") or {}
    linha = {
        "Data": registro.get("data"),
        "Hora": registro.get("hora"),
        "Natureza": registro.get("natureza"),
        "Descricao": registro.get("descricao"),
        "Endereco": registro.get("endereco"),
        "Latitude": registro.get("latitude") if registro.get("latitude") is not None else "",
        "Longitude": registro.get("longitude") if registro.get("longitude") is not None else "",
        "Placa": registro.get("placa"),
        "Pessoa": registro.get("pessoa"),
        "Pessoas_Ligadas": ", ".join(item.get("nome") or "" for item in extra.get("pessoas") or []),
        "Veiculos_Ligados": ", ".join(item.get("placa") or "" for item in extra.get("veiculos") or []),
        "Situacoes": ", ".join(extra.get("situacoes") or []),
        "Foto": registro.get("foto"),
        "Video": registro.get("video"),
        "Cliente_Documento": registro.get("documento"),
        "Id": registro.get("id"),
    }
    with ARQUIVO_CSV.open("a", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS, delimiter=";")
        if novo:
            escritor.writeheader()
        escritor.writerow(linha)
