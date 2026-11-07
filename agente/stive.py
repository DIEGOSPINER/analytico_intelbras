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
    "Responda em português, com frases curtas, só com o contexto enviado. "
    "O contexto é a base inteira do cliente logado, não apenas o dia de hoje. "
    "Quando o operador relatar uma ocorrência, preencha o objeto ocorrencia. "
    "Devolva sempre um JSON com as chaves fala, visual e ocorrencia. "
    "visual.tipo pode ser numeros, lista, texto, barras, linha ou rosca. "
    "Para gráfico, análise ou comparação, use barras, linha ou rosca e preencha itens com rotulo e total. "
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
        return {"respostas": [], "reacoes": []}
    try:
        bruto = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"respostas": [], "reacoes": []}
    if not isinstance(bruto, dict):
        return {"respostas": [], "reacoes": []}
    bruto.setdefault("respostas", [])
    bruto.setdefault("reacoes", [])
    return bruto


def _gravar(bruto: dict):
    ARQUIVO.write_text(json.dumps(bruto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def registrar_reacao(documento: str, chave: str, titulo: str, texto: str, nota: int, tipo: str = "") -> dict:
    """Guarda like (+1), dislike (-1) ou fechamento (0) das falas do Stive."""
    try:
        valor = int(nota)
    except (TypeError, ValueError):
        valor = 0
    if valor not in (-1, 0, 1):
        valor = 0
    with _TRAVA:
        bruto = _ler()
        bruto.setdefault("reacoes", []).append({
            "documento": str(documento or ""),
            "chave": str(chave or "")[:120],
            "titulo": str(titulo or "")[:80],
            "texto": str(texto or "")[:240],
            "tipo": str(tipo or "")[:40],
            "nota": valor,
            "quando": datetime.now().isoformat(timespec="seconds"),
        })
        bruto["reacoes"] = bruto["reacoes"][-1000:]
        _gravar(bruto)
    return {"ok": True, "nota": valor}


def _taxa_reacoes(itens: list[dict]) -> dict:
    positivos = sum(1 for item in itens if int(item.get("nota") or 0) == 1)
    negativos = sum(1 for item in itens if int(item.get("nota") or 0) == -1)
    avaliados = positivos + negativos
    percentual = round(100 * positivos / avaliados, 1) if avaliados else 0.0
    return {
        "positivos": positivos,
        "negativos": negativos,
        "avaliados": avaliados,
        "percentual": percentual,
    }


def resumo_satisfacao(documento: str = "") -> dict:
    """Percentual de likes positivos no mês, no ano e no total."""
    agora = datetime.now()
    mes_chave = agora.strftime("%Y-%m")
    ano_chave = agora.strftime("%Y")
    with _TRAVA:
        reacoes = list((_ler().get("reacoes") or []))
    if documento:
        reacoes = [item for item in reacoes if str(item.get("documento") or "") == str(documento)]
    do_mes = [item for item in reacoes if str(item.get("quando") or "").startswith(mes_chave)]
    do_ano = [item for item in reacoes if str(item.get("quando") or "").startswith(ano_chave)]
    return {
        "mes": _taxa_reacoes(do_mes),
        "ano": _taxa_reacoes(do_ano),
        "total": _taxa_reacoes(reacoes),
        "serie_mes": _serie_meses(reacoes),
    }


def _serie_meses(reacoes: list[dict]) -> list[dict]:
    totais = {}
    for item in reacoes:
        nota = int(item.get("nota") or 0)
        if nota not in (-1, 1):
            continue
        chave = str(item.get("quando") or "")[:7]
        if len(chave) < 7:
            continue
        slot = totais.setdefault(chave, {"positivos": 0, "negativos": 0})
        if nota == 1:
            slot["positivos"] += 1
        else:
            slot["negativos"] += 1
    saida = []
    for chave in sorted(totais)[-12:]:
        slot = totais[chave]
        avaliados = slot["positivos"] + slot["negativos"]
        saida.append({
            "rotulo": chave,
            "positivos": slot["positivos"],
            "negativos": slot["negativos"],
            "percentual": round(100 * slot["positivos"] / avaliados, 1) if avaliados else 0.0,
        })
    return saida


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


def _somar(itens, chave):
    totais = {}
    for item in itens:
        nome = str(item.get(chave) or "").strip() or "Sem informação"
        totais[nome] = totais.get(nome, 0) + 1
    return sorted(totais.items(), key=lambda par: -par[1])[:8]


def _contexto(resumo: dict) -> str:
    resumo = resumo or {}
    periodos = resumo.get("periodos") or {}
    total = periodos.get("total") or {}
    mes = periodos.get("mes") or {}
    cubo = resumo.get("cubo") or []
    por_classe = {}
    por_camera = {}
    datas = []
    for item in cubo:
        classe = str(item.get("k") or "")
        camera = str(item.get("c") or "")
        valor = int(item.get("n") or 0)
        if classe:
            por_classe[classe] = por_classe.get(classe, 0) + valor
        if camera:
            por_camera[camera] = por_camera.get(camera, 0) + valor
        if item.get("d"):
            datas.append(str(item.get("d")))
    app = resumo.get("app_linhas") or []
    datas_app = [str(item.get("data") or "") for item in app if item.get("data")]
    naturezas = ", ".join(f"{nome} {qtd}" for nome, qtd in _somar(app, "natureza")) or "nenhuma"
    ruas = ", ".join(f"{nome} {qtd}" for nome, qtd in _somar(app, "rua")) or "nenhuma"
    cameras_agora = []
    for camera in resumo.get("cameras_vivo") or []:
        agora = camera.get("agora") or {}
        cameras_agora.append(
            f"{camera.get('nome')}: pessoas {agora.get('Pessoa', 0)}, "
            f"veículos {agora.get('Veiculo', 0)}, risco {camera.get('risco') or 'branco'}"
        )
    pendencias = [item.get("texto") or "" for item in resumo.get("pendencias") or []]
    intervalo = ""
    if datas or datas_app:
        tudo = datas + datas_app
        intervalo = f"Período coberto: {min(tudo)} a {max(tudo)}."
    return "\n".join([
        "Base completa do cliente logado, não só o dia corrente.",
        intervalo,
        "Acumulado analítico: " + ", ".join(f"{chave} {valor}" for chave, valor in por_classe.items()),
        "Totais gravados: " + ", ".join(f"{chave} {valor}" for chave, valor in total.items()),
        "No mês: " + ", ".join(f"{chave} {valor}" for chave, valor in mes.items()),
        "Por câmera no histórico: " + ", ".join(f"{nome} {qtd}" for nome, qtd in sorted(por_camera.items(), key=lambda par: -par[1])[:8]),
        "Câmeras neste instante: " + ("; ".join(cameras_agora) or "nenhuma"),
        f"Ocorrências do aplicativo: {len(app)}. Naturezas: {naturezas}. Logradouros: {ruas}.",
        "Confirmações pendentes: " + ("; ".join(pendencias) or "nenhuma"),
        f"LED geral: {resumo.get('led') or 'branco'}",
        f"Voz da tela: {resumo.get('voz') or ''}"[:500],
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
            "tipo": str(visual.get("tipo") or "texto") if str(visual.get("tipo") or "texto") in ("numeros", "lista", "texto", "barras", "linha", "rosca") else "texto",
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


def _total_base(resumo: dict, classe: str) -> int:
    cubo = (resumo or {}).get("cubo") or []
    if cubo:
        return sum(int(item.get("n") or 0) for item in cubo if item.get("k") == classe)
    return int((((resumo or {}).get("periodos") or {}).get("total") or {}).get(classe) or 0)


def _local(pergunta: str, resumo: dict) -> dict:
    baixo = pergunta.lower()
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
    quer_grafico = any(trecho in baixo for trecho in ("gráf", "graf", "analis", "visual", "compar"))
    if "pessoa" in baixo:
        total = _total_base(resumo, "Pessoa")
        return _normalizar({
            "fala": f"Na base do cliente há {total} pessoas contadas.",
            "visual": {"tipo": "barras" if quer_grafico else "numeros", "titulo": "Pessoas na base", "itens": [{"rotulo": "Pessoas", "total": total}]},
        })
    if "veícul" in baixo or "veicul" in baixo or "placa" in baixo:
        total = _total_base(resumo, "Veiculo")
        return _normalizar({
            "fala": f"Na base do cliente há {total} veículos contados.",
            "visual": {"tipo": "barras" if quer_grafico else "numeros", "titulo": "Veículos na base", "itens": [{"rotulo": "Veículos", "total": total}]},
        })
    linhas = (resumo or {}).get("app_linhas") or []
    if "ocorr" in baixo or "natureza" in baixo:
        pares = _somar(linhas, "natureza")
        itens = [{"rotulo": nome, "total": qtd} for nome, qtd in pares] or [
            {"rotulo": item.get("natureza") or "Ocorrência", "total": item.get("data") or ""} for item in linhas[-6:]
        ]
        return _normalizar({
            "fala": f"A base do aplicativo tem {len(linhas)} ocorrências.",
            "visual": {"tipo": "rosca" if quer_grafico else "lista", "titulo": "Ocorrências", "itens": itens},
        })
    if quer_grafico:
        itens = [
            {"rotulo": classe, "total": _total_base(resumo, classe)}
            for classe in ("Pessoa", "Veiculo", "Arma", "Fogo", "Animal", "Bicicleta")
            if _total_base(resumo, classe)
        ]
        return _normalizar({
            "fala": "Este é o acumulado da base do cliente.",
            "visual": {"tipo": "barras", "titulo": "Base do cliente", "itens": itens or [{"rotulo": "Sem contagem", "total": 0}]},
        })
    voz = (resumo or {}).get("voz") or "A área está em observação."
    return _normalizar({
        "fala": voz,
        "visual": {"tipo": "texto", "titulo": "Situação", "itens": [{"rotulo": "Risco", "total": (resumo or {}).get("led") or "branco"}]},
    })
