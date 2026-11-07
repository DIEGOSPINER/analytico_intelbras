"""Registro CSV e buffer ao vivo das transcrições e detecções de áudio."""

from __future__ import annotations

import csv
import re
import threading
from collections import Counter, defaultdict, deque
from datetime import datetime
from pathlib import Path

ARQUIVO = Path("historico_audio.csv")
COLUNAS = [
    "Data", "Hora", "Camera", "Tipo", "Categoria", "Nivel",
    "Texto", "Palavras", "Confianca", "Detalhe",
]
_TRAVA = threading.Lock()
_ESTEIRA = deque(maxlen=240)
_NUVEM = defaultdict(Counter)
_RANK = defaultdict(Counter)
_ALERTAS = deque(maxlen=80)
_HIDRATADO = False

STOP = {
    "a", "o", "os", "as", "um", "uma", "uns", "umas", "de", "da", "do", "das", "dos",
    "e", "é", "em", "no", "na", "nos", "nas", "por", "para", "com", "sem", "sob",
    "que", "se", "não", "nao", "sim", "ou", "mas", "como", "mais", "menos", "já", "ja",
    "também", "tambem", "muito", "pouco", "ele", "ela", "eles", "elas", "eu", "tu",
    "você", "voce", "vocês", "voces", "meu", "minha", "seu", "sua", "nosso", "nossa",
    "ao", "à", "aos", "às", "pelo", "pela", "pelos", "pelas", "lhe", "lhes", "isso",
    "isto", "aqui", "ali", "lá", "la", "então", "entao", "quando", "onde", "porque",
    "porquê", "pra", "pro", "tá", "ta", "tô", "to", "né", "ne", "aí", "ai", "ok",
    "the", "and", "you", "that",
}

# Lexico de risco: categoria -> (nivel, padroes regex)
LEXICO_RISCO = {
    "xingamento": (2, (
        r"\bporra\b", r"\bmerda\b", r"\bcaralho\b", r"\bfilho da puta\b", r"\bvai se ferr\w*",
        r"\bidiota\b", r"\bvagabund\w*", r"\bdesgraç\w*", r"\bbuceta\b", r"\bcuz[aã]o\b",
    )),
    "disparo": (3, (
        r"\btiro\b", r"\btiros\b", r"\bdisparo\b", r"\bdisparos\b", r"\barma\b",
        r"\brev[oó]lver\b", r"\bpistola\b", r"\bespingarda\b", r"\bbang\b", r"\bpow\b",
    )),
    "ruido": (2, (
        r"\bbarulho\b", r"\bestouro\b", r"\bexplod\w*", r"\bestalo\b", r"\bru[ií]do\b",
        r"\bgritaria\b", r"\bgritando\b", r"\bbuzina\b",
    )),
    "briga": (3, (
        r"\bbrig(?:a|as|ando|aram|ou)\b", r"\bagress\w*", r"\bporrada\b", r"\btapa\b",
        r"\bempurra\w*", r"\bcala a boca\b", r"\bte mato\b", r"\bvou te matar\b",
        r"\bsoco\b", r"\bespanca\w*", r"\bpelea\b",
    )),
    "socorro": (3, (
        r"\bsocorro\b", r"\bme ajuda\b", r"\bajuda\b", r"\bpol[ií]cia\b", r"\bsamu\b",
        r"\bbombeiro\b", r"\bemerg[eê]ncia\b", r"\bestou ferid\w*", r"\bfogo\b",
    )),
    "incidente": (2, (
        r"\bacidente\b", r"\batropel\w*", r"\brou[bv]o\b", r"\bfurto\b", r"\bassalto\b",
        r"\binvas\w*", r"\bbloqueio\b", r"\bincidente\b", r"\bquebraram\b", r"\bvidro\b",
    )),
}


def inicializar_csv_audio():
    global _HIDRATADO
    if not ARQUIVO.exists():
        with ARQUIVO.open("w", encoding="utf-8-sig", newline="") as arquivo:
            csv.DictWriter(arquivo, fieldnames=COLUNAS, delimiter=";").writerow(
                {chave: chave for chave in COLUNAS}
            )
    with _TRAVA:
        if _HIDRATADO:
            return
        _HIDRATADO = True
    for item in reversed(carregar_historico(120)):
        camera = item.get("camera") or "Camera"
        with _TRAVA:
            _ESTEIRA.appendleft(item)
            for token in tokens_nuvem(item.get("texto") or ""):
                _NUVEM[camera][token] += 1
            for palavra in item.get("palavras") or []:
                cats = [c.strip() for c in str(item.get("categoria") or "risco").split(",") if c.strip()]
                cat = cats[0] if cats else "risco"
                _RANK[camera][f"{cat}:{palavra}"] += 1
            if item.get("risco"):
                _ALERTAS.appendleft(item)


def classificar_texto(texto: str) -> list[dict]:
    """Devolve achados {categoria, nivel, palavra} no texto."""
    baixo = (texto or "").lower()
    if not baixo.strip():
        return []
    achados = []
    vistos = set()
    for categoria, (nivel, padroes) in LEXICO_RISCO.items():
        for padrao in padroes:
            for match in re.finditer(padrao, baixo, flags=re.IGNORECASE):
                palavra = match.group(0).strip().lower()
                chave = (categoria, palavra)
                if chave in vistos:
                    continue
                vistos.add(chave)
                achados.append({"categoria": categoria, "nivel": nivel, "palavra": palavra})
    return achados


def tokens_nuvem(texto: str) -> list[str]:
    palavras = re.findall(r"[a-záàâãéêíóôõúç]{3,}", (texto or "").lower())
    return [p for p in palavras if p not in STOP]


def _agora_partes():
    agora = datetime.now()
    return agora.strftime("%Y-%m-%d"), agora.strftime("%H:%M:%S")


def registrar(
    camera: str,
    tipo: str,
    texto: str = "",
    detalhe: str = "",
    confianca: float = 0.0,
    categoria: str = "",
    nivel: int = 0,
    palavras: list[str] | None = None,
):
    """Grava CSV, esteira ao vivo, nuvem e ranking de risco."""
    inicializar_csv_audio()
    data, hora = _agora_partes()
    texto = " ".join(str(texto or "").split())[:400]
    detalhe = " ".join(str(detalhe or "").split())[:300]
    camera = str(camera or "Camera")
    tipo = str(tipo or "Audio")
    achados = classificar_texto(texto) if texto else []
    if tipo.lower() in ("disparo", "possivel_disparo") and not achados:
        achados = [{"categoria": "disparo", "nivel": 3, "palavra": "disparo"}]
    if not categoria and achados:
        categoria = ",".join(sorted({item["categoria"] for item in achados}))
    if not nivel and achados:
        nivel = max(int(item["nivel"]) for item in achados)
    lista_palavras = list(palavras or [])
    if not lista_palavras:
        lista_palavras = [item["palavra"] for item in achados]
    linha = {
        "Data": data,
        "Hora": hora,
        "Camera": camera,
        "Tipo": tipo,
        "Categoria": categoria or ("transcricao" if texto else "ruido"),
        "Nivel": int(nivel or 0),
        "Texto": texto,
        "Palavras": ", ".join(lista_palavras),
        "Confianca": round(float(confianca or 0), 2),
        "Detalhe": detalhe,
    }
    evento = {
        "quando": f"{data} {hora}",
        "camera": camera,
        "tipo": tipo,
        "categoria": linha["Categoria"],
        "nivel": int(linha["Nivel"]),
        "texto": texto,
        "palavras": lista_palavras,
        "confianca": linha["Confianca"],
        "detalhe": detalhe,
        "risco": int(linha["Nivel"]) >= 2,
    }
    with _TRAVA:
        with ARQUIVO.open("a", encoding="utf-8-sig", newline="") as arquivo:
            csv.DictWriter(arquivo, fieldnames=COLUNAS, delimiter=";").writerow(linha)
        _ESTEIRA.appendleft(evento)
        for token in tokens_nuvem(texto):
            _NUVEM[camera][token] += 1
        for item in achados:
            _RANK[camera][f"{item['categoria']}:{item['palavra']}"] += 1
        if evento["risco"]:
            _ALERTAS.appendleft(evento)


def _top(counter: Counter, limite: int = 20) -> list[dict]:
    return [{"rotulo": chave, "total": int(total)} for chave, total in counter.most_common(limite)]


def resumo_audio(limite_esteira: int = 80) -> dict:
    with _TRAVA:
        esteira = list(_ESTEIRA)[:limite_esteira]
        cameras = sorted(set(list(_NUVEM.keys()) + list(_RANK.keys()) + [e["camera"] for e in esteira]))
        por_camera = {}
        for camera in cameras:
            por_camera[camera] = {
                "nuvem": _top(_NUVEM[camera], 24),
                "ranking_risco": _top(_RANK[camera], 12),
            }
        alertas = list(_ALERTAS)[:20]
    return {
        "esteira": esteira,
        "cameras": por_camera,
        "alertas": alertas,
        "risco_aberto": sum(1 for item in alertas if int(item.get("nivel") or 0) >= 2),
    }


def carregar_historico(limite: int = 120) -> list[dict]:
    if not ARQUIVO.exists():
        return []
    with ARQUIVO.open(encoding="utf-8-sig", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo, delimiter=";"))
    saida = []
    for linha in linhas[-limite:]:
        saida.append({
            "quando": f"{linha.get('Data') or ''} {linha.get('Hora') or ''}".strip(),
            "camera": linha.get("Camera") or "",
            "tipo": linha.get("Tipo") or "",
            "categoria": linha.get("Categoria") or "",
            "nivel": int(float(linha.get("Nivel") or 0) or 0),
            "texto": linha.get("Texto") or "",
            "palavras": [p.strip() for p in str(linha.get("Palavras") or "").split(",") if p.strip()],
            "confianca": float(linha.get("Confianca") or 0 or 0),
            "detalhe": linha.get("Detalhe") or "",
            "risco": int(float(linha.get("Nivel") or 0) or 0) >= 2,
        })
    saida.reverse()
    return saida
