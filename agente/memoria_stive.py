"""Memória operacional do Stive: dataset de episódios + recuperação para o prompt.

Não treina pesos do LLM. Acumula pergunta/resposta/feedback e injeta casos
similares (com like ou correção) nas próximas perguntas. Também exporta JSONL
no formato de fine-tune para treino offline futuro.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path

ARQUIVO = Path("stive_aprendizado.jsonl")
EXPORT_PADRAO = Path("stive_finetune.jsonl")
_TRAVA = threading.RLock()
_STOP = {
    "a", "o", "os", "as", "um", "uma", "de", "da", "do", "das", "dos", "e", "ou",
    "em", "na", "no", "nas", "nos", "que", "com", "por", "para", "se", "ao", "à",
    "é", "foi", "ser", "tem", "há", "ha", "me", "meu", "minha", "seu", "sua",
    "the", "and", "or", "of", "to", "in", "on", "is", "are",
}


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _tokens(texto: str) -> set[str]:
    palavras = re.findall(r"[a-zA-ZÀ-ÿ0-9]{3,}", (texto or "").lower())
    return {p for p in palavras if p not in _STOP}


def _score(pergunta: str, episodio: dict) -> float:
    q = _tokens(pergunta)
    if not q:
        return 0.0
    base = " ".join([
        str(episodio.get("pergunta") or ""),
        str(episodio.get("fala") or ""),
        str(episodio.get("correcao") or ""),
        str(episodio.get("titulo") or ""),
        str(episodio.get("tipo") or ""),
    ])
    t = _tokens(base)
    if not t:
        return 0.0
    inter = len(q & t)
    if inter <= 0:
        return 0.0
    jaccard = inter / max(1, len(q | t))
    bonus = 0.0
    nota = int(episodio.get("nota") or 0)
    if nota == 1:
        bonus += 0.25
    elif nota == -1:
        bonus -= 0.35
    if str(episodio.get("correcao") or "").strip():
        bonus += 0.35
    if str(episodio.get("origem") or "") == "confirmacao":
        bonus += 0.1
    return jaccard + bonus


def _ler_todos() -> list[dict]:
    if not ARQUIVO.exists():
        return []
    saida = []
    try:
        with ARQUIVO.open("r", encoding="utf-8") as arq:
            for linha in arq:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    item = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict) and item.get("id"):
                    saida.append(item)
    except OSError:
        return []
    return saida[-4000:]


def _reescrever(itens: list[dict]) -> None:
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    with ARQUIVO.open("w", encoding="utf-8") as arq:
        for item in itens[-4000:]:
            arq.write(json.dumps(item, ensure_ascii=False) + "\n")


def _append(item: dict) -> None:
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    with ARQUIVO.open("a", encoding="utf-8") as arq:
        arq.write(json.dumps(item, ensure_ascii=False) + "\n")


def digest_resumo(resumo: dict | None) -> str:
    """Trecho curto do resumo para o dataset (não o contexto inteiro)."""
    if not isinstance(resumo, dict):
        return ""
    partes = []
    for chave in ("itens", "cameras", "led", "risco_aberto"):
        if chave in resumo:
            partes.append(f"{chave}={resumo.get(chave)}")
    cubo = resumo.get("cubo") or []
    if isinstance(cubo, list) and cubo:
        partes.append(f"cubo_linhas={len(cubo)}")
    vivo = resumo.get("cameras_vivo") or []
    if isinstance(vivo, list) and vivo:
        nomes = [str(c.get("nome") or "") for c in vivo[:4] if isinstance(c, dict)]
        if nomes:
            partes.append("vivo=" + ",".join(n for n in nomes if n))
    voz = str(resumo.get("voz") or "").strip()
    if voz:
        partes.append("voz=" + voz[:120])
    return " | ".join(partes)[:400]


def registrar_episodio(
    *,
    pergunta: str,
    fala: str,
    documento: str = "",
    email: str = "",
    perfil: str = "",
    origem: str = "chat",
    tipo: str = "",
    titulo: str = "",
    camera: str = "",
    resumo: dict | None = None,
    visual: dict | None = None,
    chave_ui: str = "",
) -> dict:
    """Grava um episódio (pergunta → fala) para aprendizado operacional."""
    item = {
        "id": f"ep_{uuid.uuid4().hex[:12]}",
        "quando": _agora(),
        "origem": str(origem or "chat")[:40],
        "tipo": str(tipo or "")[:40],
        "titulo": str(titulo or "")[:80],
        "camera": str(camera or "")[:80],
        "documento": "".join(c for c in str(documento or "") if c.isdigit()),
        "email": str(email or "").strip().lower()[:120],
        "perfil": str(perfil or "").strip().lower()[:40],
        "pergunta": str(pergunta or "").strip()[:500],
        "fala": str(fala or "").strip()[:800],
        "digest": digest_resumo(resumo),
        "chave_ui": str(chave_ui or "")[:160],
        "nota": 0,
        "correcao": "",
        "visual_tipo": str((visual or {}).get("tipo") or "")[:20] if isinstance(visual, dict) else "",
    }
    with _TRAVA:
        _append(item)
    return item


def marcar_feedback(
    *,
    nota: int,
    episodio_id: str = "",
    chave_ui: str = "",
    texto: str = "",
    titulo: str = "",
    pergunta: str = "",
    correcao: str = "",
    documento: str = "",
) -> dict | None:
    """Associa like/dislike/correção ao episódio mais próximo."""
    try:
        valor = int(nota)
    except (TypeError, ValueError):
        valor = 0
    if valor not in (-1, 0, 1) and not str(correcao or "").strip():
        return None
    texto = str(texto or "").strip()
    titulo = str(titulo or "").strip()
    pergunta = str(pergunta or "").strip()
    correcao = str(correcao or "").strip()[:500]
    digitos = "".join(c for c in str(documento or "") if c.isdigit())
    with _TRAVA:
        itens = _ler_todos()
        alvo = None
        if episodio_id:
            for item in reversed(itens):
                if item.get("id") == episodio_id:
                    alvo = item
                    break
        if alvo is None and chave_ui:
            for item in reversed(itens):
                if str(item.get("chave_ui") or "") == chave_ui:
                    alvo = item
                    break
        if alvo is None and texto:
            baixo = texto[:160].casefold()
            for item in reversed(itens):
                fala = str(item.get("fala") or "")
                if baixo and (baixo in fala.casefold() or fala.casefold()[:120] in baixo):
                    if digitos and item.get("documento") and item.get("documento") != digitos:
                        continue
                    alvo = item
                    break
        if alvo is None and (pergunta or titulo or texto):
            consulta = " ".join([pergunta, titulo, texto])
            melhor = None
            melhor_s = 0.0
            for item in itens[-800:]:
                if digitos and item.get("documento") and item.get("documento") != digitos:
                    continue
                s = _score(consulta, item)
                if s > melhor_s:
                    melhor_s = s
                    melhor = item
            if melhor is not None and melhor_s >= 0.12:
                alvo = melhor
        if alvo is None:
            # Feedback órfão: cria episódio mínimo para não perder o sinal.
            alvo = {
                "id": f"ep_{uuid.uuid4().hex[:12]}",
                "quando": _agora(),
                "origem": "reacao",
                "tipo": "",
                "titulo": titulo[:80],
                "camera": "",
                "documento": digitos,
                "email": "",
                "perfil": "",
                "pergunta": pergunta[:500] or titulo[:500],
                "fala": texto[:800],
                "digest": "",
                "chave_ui": chave_ui[:160],
                "nota": 0,
                "correcao": "",
                "visual_tipo": "",
            }
            itens.append(alvo)
        if valor in (-1, 0, 1):
            alvo["nota"] = valor
        if correcao:
            alvo["correcao"] = correcao
            if valor == 0:
                alvo["nota"] = 1
        alvo["feedback_quando"] = _agora()
        _reescrever(itens)
        return dict(alvo)


def buscar_similares(
    pergunta: str,
    *,
    limite: int = 5,
    documento: str = "",
    so_uteis: bool = True,
) -> list[dict]:
    """Recupera episódios parecidos para colar no prompt."""
    pergunta = str(pergunta or "").strip()
    if len(pergunta) < 3:
        return []
    digitos = "".join(c for c in str(documento or "") if c.isdigit())
    with _TRAVA:
        itens = _ler_todos()
    candidatos = []
    for item in itens:
        nota = int(item.get("nota") or 0)
        tem_correcao = bool(str(item.get("correcao") or "").strip())
        if so_uteis and nota < 1 and not tem_correcao:
            # Dislikes entram só se tiverem correção explícita.
            continue
        doc_ep = str(item.get("documento") or "")
        if digitos and doc_ep and doc_ep != digitos:
            # Isolamento por CPF/CNPJ: não vaza memória de outro cliente.
            continue
        s = _score(pergunta, item)
        if s < 0.14:
            continue
        candidatos.append((s, item))
    candidatos.sort(key=lambda par: (-par[0], str(par[1].get("quando") or "")))
    return [dict(it) for _s, it in candidatos[: max(1, min(limite, 8))]]


def texto_para_prompt(pergunta: str, documento: str = "", limite: int = 5) -> str:
    casos = buscar_similares(pergunta, limite=limite, documento=documento, so_uteis=True)
    if not casos:
        return ""
    linhas = [
        "Memória operacional (casos parecidos já avaliados pelo operador — use como referência, "
        "sem inventar números que não estejam no contexto atual):"
    ]
    for i, item in enumerate(casos, 1):
        nota = int(item.get("nota") or 0)
        selo = "like" if nota == 1 else ("dislike" if nota == -1 else "corrigido")
        pergunta_ep = str(item.get("pergunta") or item.get("titulo") or "").strip()
        fala = str(item.get("correcao") or item.get("fala") or "").strip()
        linhas.append(
            f"{i}. [{selo}] Pergunta: {pergunta_ep[:180]}\n"
            f"   Resposta de referência: {fala[:280]}"
        )
    return "\n".join(linhas)


def exportar_finetune(caminho: str | Path | None = None, minimo_nota: int = 1) -> dict:
    """Gera JSONL no formato messages[] para fine-tune offline."""
    destino = Path(caminho or EXPORT_PADRAO)
    with _TRAVA:
        itens = _ler_todos()
    sistema = (
        "Você é Stive, agente de segurança do C4ISTAR MONITOR. "
        "Responda em português com base no contexto operacional."
    )
    n = 0
    with destino.open("w", encoding="utf-8") as arq:
        for item in itens:
            nota = int(item.get("nota") or 0)
            correcao = str(item.get("correcao") or "").strip()
            if nota < minimo_nota and not correcao:
                continue
            pergunta = str(item.get("pergunta") or "").strip()
            fala = correcao or str(item.get("fala") or "").strip()
            if not pergunta or not fala:
                continue
            user = pergunta
            digest = str(item.get("digest") or "").strip()
            if digest:
                user = f"Contexto: {digest}\n\nPergunta: {pergunta}"
            linha = {
                "messages": [
                    {"role": "system", "content": sistema},
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": json.dumps({"fala": fala, "visual": {}, "ocorrencia": {}}, ensure_ascii=False)},
                ]
            }
            arq.write(json.dumps(linha, ensure_ascii=False) + "\n")
            n += 1
    return {"ok": True, "arquivo": str(destino), "exemplos": n}


def estatisticas() -> dict:
    with _TRAVA:
        itens = _ler_todos()
    likes = sum(1 for i in itens if int(i.get("nota") or 0) == 1)
    dislikes = sum(1 for i in itens if int(i.get("nota") or 0) == -1)
    correcoes = sum(1 for i in itens if str(i.get("correcao") or "").strip())
    return {
        "total": len(itens),
        "likes": likes,
        "dislikes": dislikes,
        "correcoes": correcoes,
        "uteis_prompt": likes + correcoes,
        "arquivo": str(ARQUIVO),
    }
