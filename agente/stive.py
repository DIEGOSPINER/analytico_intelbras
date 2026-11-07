"""Agente Stive: conversa sobre a base local e confirmações para o modelo."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

ARQUIVO = Path("feedback_modelo.json")
_TRAVA = threading.Lock()
_CHATS = {}

_SISTEMA = (
    "Você é Stive, agente de segurança do C4ISTAR MONITOR. "
    "Responda em português, com frases curtas, só com base no contexto enviado. "
    "Quando o operador relatar uma ocorrência, preencha o objeto ocorrencia. "
    "Devolva sempre um JSON com as chaves fala, visual e ocorrencia. "
    "visual tem tipo (numeros, lista ou texto), titulo e itens [{rotulo, total}]. "
    "ocorrencia tem natureza, descricao, endereco, data e hora, ou fica vazio."
)


def ids_respondidos() -> set[str]:
    bruto = _ler()
    return {str(item.get("id") or "") for item in bruto.get("respostas") or [] if item.get("id")}


def historico(documento: str) -> list[dict]:
    with _TRAVA:
        return [dict(item) for item in _CHATS.get(documento, [])][-12:]


def responder(documento: str, pergunta: str, resumo: dict) -> dict:
    pergunta = (pergunta or "").strip()
    if not pergunta:
        raise ValueError("Escreva a pergunta para o Stive.")
    contexto = _contexto(resumo)
    try:
        from agente.modelo import SessaoGPT, extrair_json

        sessao = SessaoGPT()
        if sessao.disponivel:
            texto = sessao.perguntar(
                _SISTEMA,
                contexto + "\n\nHistórico:\n" + _historico_texto(documento) + "\n\nPergunta: " + pergunta,
                json_mode=True,
            )
            saida = extrair_json(texto)
            if isinstance(saida, dict) and saida.get("fala"):
                resultado = _normalizar(saida)
                _guardar(documento, pergunta, resultado["fala"])
                _registrar_ocorrencia(documento, resultado.get("ocorrencia"))
                return resultado
    except Exception:
        pass
    resultado = _local(pergunta, resumo)
    _guardar(documento, pergunta, resultado["fala"])
    _registrar_ocorrencia(documento, resultado.get("ocorrencia"))
    return resultado


def confirmar(documento: str, ident: str, resposta: str, texto: str, camera: str, tipo: str) -> str:
    ident = (ident or "").strip()
    if not ident:
        raise ValueError("Confirmação sem identificador.")
    sim = (resposta or "").strip().lower() in ("sim", "s", "1", "confirmo")
    with _TRAVA:
        bruto = _ler()
        bruto.setdefault("respostas", []).append({
            "id": ident,
            "resposta": "sim" if sim else "nao",
            "texto": (texto or "")[:240],
            "camera": camera or "",
            "tipo": tipo or "",
            "quando": datetime.now().isoformat(timespec="seconds"),
        })
        bruto["respostas"] = bruto["respostas"][-200:]
        _gravar(bruto)
    if not sim:
        return "Anotado. Essa situação não entra na base."
    natureza = {
        "disparo": "Disparo",
        "veiculo": "Permanência de veículo",
        "pessoa": "Permanência de pessoa",
    }.get(tipo, "Confirmação de campo")
    from ocorrencias import informar_ocorrencia

    informar_ocorrencia(documento, {
        "data": datetime.now().strftime("%Y-%m-%d"),
        "hora": datetime.now().strftime("%H:%M"),
        "natureza": natureza,
        "descricao": (texto or natureza) + " Confirmado pelo operador com o Agente Stive.",
        "endereco": camera or "",
    }, usar_modelo=False)
    return "Confirmação gravada na base de ocorrências."


def caminho_avatar() -> Path | None:
    for nome in ("assets/stive.png", "assets/stive.jpg", "assets/stive.jpeg", "stive.png", "stive.jpg"):
        caminho = Path(nome)
        if caminho.is_file():
            return caminho
    return None


def _ler() -> dict:
    if not ARQUIVO.exists():
        return {"respostas": []}
    try:
        bruto = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"respostas": []}
    return bruto if isinstance(bruto, dict) else {"respostas": []}


def _gravar(bruto: dict):
    ARQUIVO.write_text(json.dumps(bruto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _guardar(documento: str, pergunta: str, fala: str):
    with _TRAVA:
        fila = _CHATS.setdefault(documento or "", [])
        fila.append({"papel": "eu", "texto": pergunta[:500]})
        fila.append({"papel": "stive", "texto": fala[:800]})
        del fila[:-12]


def _historico_texto(documento: str) -> str:
    linhas = []
    for item in historico(documento):
        linhas.append(f"{item['papel']}: {item['texto']}")
    return "\n".join(linhas) or "(início da conversa)"


def _contexto(resumo: dict) -> str:
    periodos = ((resumo or {}).get("periodos") or {}).get("dia") or {}
    cameras = []
    for camera in (resumo or {}).get("cameras_vivo") or []:
        agora = camera.get("agora") or {}
        cameras.append(
            f"{camera.get('nome')}: pessoas {agora.get('Pessoa', 0)}, "
            f"veículos {agora.get('Veiculo', 0)}, risco {camera.get('risco') or 'branco'}"
        )
    linhas = []
    for item in ((resumo or {}).get("app_linhas") or [])[-20:]:
        linhas.append(
            f"{item.get('data')} {item.get('natureza')} em {item.get('rua') or item.get('camera')}"
        )
    pendencias = [item.get("texto") or "" for item in (resumo or {}).get("pendencias") or []]
    return "\n".join([
        f"LED geral: {(resumo or {}).get('led') or 'branco'}",
        "Contagens de hoje: " + ", ".join(f"{chave} {valor}" for chave, valor in periodos.items()),
        "Câmeras agora: " + ("; ".join(cameras) or "nenhuma"),
        "Ocorrências recentes do aplicativo: " + ("; ".join(linhas) or "nenhuma"),
        "Confirmações pendentes: " + ("; ".join(pendencias) or "nenhuma"),
        f"Voz da tela: {(resumo or {}).get('voz') or ''}"[:500],
    ])


def _normalizar(saida: dict) -> dict:
    visual = saida.get("visual") if isinstance(saida.get("visual"), dict) else {}
    itens = []
    for item in visual.get("itens") or []:
        if not isinstance(item, dict):
            continue
        itens.append({
            "rotulo": str(item.get("rotulo") or "")[:80],
            "total": item.get("total") if isinstance(item.get("total"), (int, float)) else str(item.get("total") or "")[:40],
        })
    ocorrencia = saida.get("ocorrencia") if isinstance(saida.get("ocorrencia"), dict) else {}
    if not str(ocorrencia.get("natureza") or "").strip() or not str(ocorrencia.get("descricao") or "").strip():
        ocorrencia = {}
    return {
        "fala": str(saida.get("fala") or "Estou com a base, pode perguntar de novo.")[:1200],
        "visual": {
            "tipo": str(visual.get("tipo") or "texto"),
            "titulo": str(visual.get("titulo") or "")[:80],
            "itens": itens[:12],
        },
        "ocorrencia": {
            "natureza": str(ocorrencia.get("natureza") or "")[:60],
            "descricao": str(ocorrencia.get("descricao") or "")[:400],
            "endereco": str(ocorrencia.get("endereco") or "")[:120],
            "data": str(ocorrencia.get("data") or "")[:10],
            "hora": str(ocorrencia.get("hora") or "")[:8],
        } if ocorrencia else {},
    }


def _registrar_ocorrencia(documento: str, ocorrencia: dict):
    if not ocorrencia:
        return
    from ocorrencias import informar_ocorrencia

    agora = datetime.now()
    informar_ocorrencia(documento, {
        "data": ocorrencia.get("data") or agora.strftime("%Y-%m-%d"),
        "hora": (ocorrencia.get("hora") or agora.strftime("%H:%M"))[:5],
        "natureza": ocorrencia.get("natureza"),
        "descricao": ocorrencia.get("descricao"),
        "endereco": ocorrencia.get("endereco") or "",
    }, usar_modelo=False)


def _local(pergunta: str, resumo: dict) -> dict:
    baixo = pergunta.lower()
    periodos = ((resumo or {}).get("periodos") or {}).get("dia") or {}
    if any(trecho in baixo for trecho in ("registr", "informar ocorr", "houve ", "aconteceu")):
        return _normalizar({
            "fala": "Anotado como ocorrência informada pelo operador.",
            "visual": {"tipo": "texto", "titulo": "Ocorrência", "itens": [{"rotulo": pergunta[:80], "total": ""}]},
            "ocorrencia": {
                "natureza": "Informe do operador",
                "descricao": pergunta,
                "endereco": "",
                "data": datetime.now().strftime("%Y-%m-%d"),
                "hora": datetime.now().strftime("%H:%M"),
            },
        })
    if "pessoa" in baixo:
        total = int(periodos.get("Pessoa") or 0)
        return _normalizar({
            "fala": f"Hoje as câmeras contaram {total} pessoas.",
            "visual": {"tipo": "numeros", "titulo": "Pessoas hoje", "itens": [{"rotulo": "Pessoas", "total": total}]},
        })
    if "veícul" in baixo or "veicul" in baixo or "placa" in baixo:
        total = int(periodos.get("Veiculo") or 0)
        return _normalizar({
            "fala": f"Hoje as câmeras contaram {total} veículos.",
            "visual": {"tipo": "numeros", "titulo": "Veículos hoje", "itens": [{"rotulo": "Veículos", "total": total}]},
        })
    linhas = (resumo or {}).get("app_linhas") or []
    if "ocorr" in baixo or "natureza" in baixo:
        itens = [{"rotulo": item.get("natureza") or "Ocorrência", "total": item.get("data") or ""} for item in linhas[-6:]]
        return _normalizar({
            "fala": f"A base do aplicativo tem {len(linhas)} ocorrências carregadas nesta visão.",
            "visual": {"tipo": "lista", "titulo": "Ocorrências", "itens": itens},
        })
    voz = (resumo or {}).get("voz") or "A área está em observação."
    return _normalizar({
        "fala": voz,
        "visual": {"tipo": "texto", "titulo": "Situação", "itens": [{"rotulo": "Risco", "total": (resumo or {}).get("led") or "branco"}]},
    })
