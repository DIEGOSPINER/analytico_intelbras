"""Agente Stive: conversa sobre a base local e confirmações para o modelo."""

from __future__ import annotations

import json
import re
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

ARQUIVO = Path("feedback_modelo.json")
_TRAVA = threading.Lock()
_CHATS = {}

_SISTEMA = (
    "Você é Stive, agente de segurança do C4ISTAR MONITOR e analista criminal de campo. "
    "Fale como policial experiente: horário, dia da semana, local, pessoa e padrão importam. "
    "Responda em português, objetivo, usando SEMPRE o contexto numérico e textual enviado abaixo. "
    "Esse contexto JÁ É a consulta à base do cliente logado (dia, semana, mês, total, cubo, app, alertas). "
    "NUNCA diga que não tem acesso, que não consegue consultar, que falta permissão ou que os dados "
    "do dia/semana não estão disponíveis. Se o total do período for zero, diga claramente que "
    "na base daquele período não há registros — isso ainda é uma resposta com base nos dados. "
    "Quando perguntarem o que ocorreu no dia, na semana ou no mês, use os blocos Totais do dia / "
    "da semana / do mês, a série diária, ocorrências, matches e áudio do contexto. "
    "Regra de probabilidade: cada passagem de pessoa de risco no histórico = 1 risco de invasão. "
    "Entre 20h e 06h aumente a chance (ladrões preferem a madrugada); sexta a domingo também eleva. "
    "Quando pedirem chance, probabilidade, invasão, cruzamento ou padrão, use o briefing criminal "
    "e diga números claros (passagens, dias, % estimada). Cruze pessoa × câmera × horário × ocorrências. "
    "Quando o operador RELATAR (não perguntar) uma ocorrência nova para gravar, preencha o objeto ocorrencia. "
    "Perguntas do tipo 'o que aconteceu', 'houve', 'resumo do dia' NÃO são registro — só narração. "
    "Devolva sempre um JSON com as chaves fala, visual e ocorrencia. "
    "visual.tipo pode ser numeros, lista, texto, barras, linha ou rosca. "
    "Para gráfico, análise, chance ou comparação, use barras, linha ou rosca e preencha itens com rotulo e total. "
    "ocorrencia tem natureza, descricao, endereco, data e hora, ou fica vazio."
)

_RECUSAS = (
    "não tenho acesso",
    "nao tenho acesso",
    "sem acesso",
    "não consigo consultar",
    "nao consigo consultar",
    "não posso consultar",
    "nao posso consultar",
    "não tenho como acessar",
    "nao tenho como acessar",
    "não disponho dos dados",
    "nao disponho dos dados",
    "dados não estão disponíveis",
    "dados nao estao disponiveis",
    "não posso responder",
    "nao posso responder",
    "fora do meu alcance",
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
    from agente.criminal import analisar, pede_analise_criminal, texto_briefing

    briefing = ""
    analise = None
    if pede_analise_criminal(pergunta):
        try:
            analise = analisar(documento, pergunta, resumo)
            briefing = texto_briefing(analise)
        except Exception:
            briefing = ""
    # Perguntas de período respondem direto da base — evita GPT inventar "sem acesso".
    local_periodo = _resposta_periodo(pergunta, resumo)
    if local_periodo is not None and not pede_analise_criminal(pergunta):
        _guardar(documento, pergunta, local_periodo["fala"])
        return local_periodo
    contexto = _contexto(resumo)
    if briefing:
        contexto = contexto + "\n\n" + briefing
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
                if _parece_recusa(resultado.get("fala") or ""):
                    resultado = local_periodo or _local(pergunta, resumo, documento=documento)
                elif analise and (not resultado.get("visual") or not (resultado["visual"].get("itens"))):
                    from agente.criminal import resposta_chat

                    visual = resposta_chat(documento, pergunta, resumo).get("visual") or {}
                    if visual.get("itens"):
                        resultado["visual"] = visual
                _guardar(documento, pergunta, resultado["fala"])
                _registrar_ocorrencia(documento, resultado.get("ocorrencia"))
                return resultado
    except Exception:
        pass
    resultado = local_periodo or _local(pergunta, resumo, documento=documento)
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
        try:
            from audio_registro import rejeitar_pendente

            rejeitar_pendente(ident)
        except Exception:
            pass
        return "Anotado. Essa situação não entra na base."
    natureza = {
        "disparo": "Disparo",
        "audio": "Áudio de risco",
        "veiculo": "Permanência de veículo",
        "pessoa": "Permanência de pessoa",
    }.get(tipo, "Confirmação de campo")
    audio_gravado = False
    if tipo in ("disparo", "audio", "briga", "socorro"):
        try:
            from audio_registro import confirmar_pendente

            audio_gravado = confirmar_pendente(ident)
        except Exception:
            audio_gravado = False
    from ocorrencias import informar_ocorrencia

    informar_ocorrencia(documento, {
        "data": datetime.now().strftime("%Y-%m-%d"),
        "hora": datetime.now().strftime("%H:%M"),
        "natureza": natureza,
        "descricao": (texto or natureza) + " Confirmado pelo operador com o Agente Stive.",
        "endereco": camera or "",
    }, usar_modelo=False)
    if audio_gravado:
        return "Confirmado. Áudio e ocorrência gravados na base."
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


def _parece_recusa(fala: str) -> bool:
    baixo = (fala or "").lower()
    return any(trecho in baixo for trecho in _RECUSAS)


def _fmt_bloco(bloco: dict) -> str:
    if not bloco:
        return "sem contagem"
    partes = [f"{chave} {int(valor or 0)}" for chave, valor in bloco.items() if int(valor or 0)]
    return ", ".join(partes) if partes else "nenhum registro"


def _periodo_chave(baixo: str) -> str | None:
    if any(t in baixo for t in ("semana", "últimos 7", "ultimos 7", "7 dias", "nessa semana", "nesta semana")):
        return "semana"
    if any(t in baixo for t in ("mês", "mes", "neste mês", "nesse mes", "no mês", "no mes")):
        return "mes"
    if any(t in baixo for t in (
        "hoje", "no dia", "do dia", "neste dia", "nesse dia", "dia de hoje",
        "ocorreram hoje", "ocorreu hoje", "aconteceu hoje", "aconteceram hoje",
    )):
        return "dia"
    if any(t in baixo for t in (
        "o que ocorreu", "o que aconteceu", "o que houve", "resumo do",
        "balanço", "balanco", "situação atual", "situacao atual",
    )):
        return "dia"
    return None


def _cubo_periodo(resumo: dict, chave: str) -> list[dict]:
    cubo = (resumo or {}).get("cubo") or []
    hoje = date.today()
    if chave == "dia":
        inicio = hoje.isoformat()
        return [item for item in cubo if str(item.get("d") or "")[:10] == inicio]
    if chave == "semana":
        inicio = (hoje - timedelta(days=6)).isoformat()
    elif chave == "mes":
        inicio = hoje.replace(day=1).isoformat()
    else:
        return list(cubo)
    return [item for item in cubo if str(item.get("d") or "")[:10] >= inicio]


def _app_periodo(resumo: dict, chave: str) -> list[dict]:
    app = (resumo or {}).get("app_linhas") or []
    hoje = date.today()
    if chave == "dia":
        inicio = hoje.isoformat()
        return [item for item in app if str(item.get("data") or "")[:10] == inicio]
    if chave == "semana":
        inicio = (hoje - timedelta(days=6)).isoformat()
    elif chave == "mes":
        inicio = hoje.replace(day=1).isoformat()
    else:
        return list(app)
    return [item for item in app if str(item.get("data") or "")[:10] >= inicio]


def _bloco_periodo(resumo: dict, chave: str) -> dict:
    periodos = (resumo or {}).get("periodos") or {}
    bloco = dict(periodos.get(chave) or {})
    if bloco:
        return bloco
    # Fallback: monta a partir do cubo se periodos.semana ainda não existir no resumo vivo.
    totais = {}
    for item in _cubo_periodo(resumo, chave):
        classe = str(item.get("k") or "") or "Outro"
        totais[classe] = totais.get(classe, 0) + int(item.get("n") or 0)
    return totais


def _rotulo_periodo(chave: str) -> str:
    return {"dia": "hoje", "semana": "nesta semana", "mes": "neste mês"}.get(chave, "no período")


def _narrar_periodo(resumo: dict, chave: str) -> dict:
    bloco = _bloco_periodo(resumo, chave)
    app = _app_periodo(resumo, chave)
    cubo = _cubo_periodo(resumo, chave)
    historico = (resumo or {}).get("historico") or []
    informes = (resumo or {}).get("informes") or []
    audio = ((resumo or {}).get("audio") or {}).get("alertas") or []
    rotulo = _rotulo_periodo(chave)
    pessoas = int(bloco.get("Pessoa") or 0)
    veiculos = int(bloco.get("Veiculo") or 0)
    armas = int(bloco.get("Arma") or 0)
    faces = int(bloco.get("MatchFace") or 0)
    placas = int(bloco.get("MatchPlaca") or 0)
    soma = sum(int(v or 0) for v in bloco.values())
    naturezas = _somar(app, "natureza")
    por_camera = {}
    for item in cubo:
        cam = str(item.get("c") or "Sem câmera")
        por_camera[cam] = por_camera.get(cam, 0) + int(item.get("n") or 0)
    top_cams = sorted(por_camera.items(), key=lambda par: -par[1])[:5]

    partes = []
    if soma <= 0 and not app and not historico:
        partes.append(f"Na base {rotulo} não há registros analíticos ainda.")
    else:
        partes.append(
            f"Na base {rotulo}: {pessoas} pessoas, {veiculos} veículos"
            + (f", {armas} armas" if armas else "")
            + (f", {faces} matches de face" if faces else "")
            + (f", {placas} matches de placa" if placas else "")
            + "."
        )
    if app:
        nat = ", ".join(f"{n} {q}" for n, q in naturezas[:4]) or "diversas"
        partes.append(f"Ocorrências do app: {len(app)} ({nat}).")
    if historico and chave == "dia":
        nomes = ", ".join(
            f"{(h.get('nome') or h.get('id') or 'alerta')}" for h in historico[:3]
        )
        partes.append(f"Alertas recentes de interesse: {nomes}.")
    if informes and chave in ("dia", "semana"):
        partes.append(f"Informes enviados recentes: {len(informes)}.")
    if audio and chave == "dia":
        partes.append(
            "Áudio de risco: " + "; ".join(
                f"{a.get('camera') or ''}: {a.get('categoria') or ''}" for a in audio[:3]
            ) + "."
        )
    if top_cams:
        partes.append(
            "Câmeras com mais movimento: "
            + ", ".join(f"{nome} ({qtd})" for nome, qtd in top_cams) + "."
        )

    itens = [{"rotulo": k, "total": int(v or 0)} for k, v in bloco.items() if int(v or 0)]
    if not itens and naturezas:
        itens = [{"rotulo": n, "total": q} for n, q in naturezas]
    if not itens:
        itens = [{"rotulo": f"Sem registros {rotulo}", "total": 0}]
    titulo = {"dia": "Resumo do dia", "semana": "Resumo da semana", "mes": "Resumo do mês"}.get(chave, "Resumo")
    return _normalizar({
        "fala": " ".join(partes),
        "visual": {
            "tipo": "barras" if len(itens) > 1 else "numeros",
            "titulo": titulo,
            "itens": itens[:10],
        },
    })


def _resposta_periodo(pergunta: str, resumo: dict) -> dict | None:
    baixo = (pergunta or "").lower()
    chave = _periodo_chave(baixo)
    if not chave:
        return None
    # Só força resposta local quando a pergunta é sobre o que ocorreu / resumo / totais do período.
    gatilhos = (
        "ocorreu", "ocorreram", "aconteceu", "aconteceram", "houve", "resumo",
        "balanço", "balanco", "total", "quantos", "quantas", "movimento",
        "passou", "passaram", "situação", "situacao", "status", "hoje",
        "no dia", "na semana", "no mês", "no mes", "nesta semana", "neste dia",
    )
    if not any(t in baixo for t in gatilhos):
        return None
    return _narrar_periodo(resumo, chave)


def _contexto_audio(resumo: dict) -> str:
    pacote = (resumo or {}).get("audio") or {}
    alertas = pacote.get("alertas") or []
    if not alertas:
        return "Áudio: sem alerta verbal recente."
    linhas = []
    for item in alertas[:5]:
        linhas.append(
            f"{item.get('quando') or ''} {item.get('camera') or ''}: "
            f"{item.get('categoria') or ''} · {(item.get('texto') or item.get('detalhe') or '')[:120]}"
        )
    return "Áudio de risco recente: " + " | ".join(linhas)


def _contexto(resumo: dict) -> str:
    resumo = resumo or {}
    periodos = resumo.get("periodos") or {}
    total = periodos.get("total") or _bloco_periodo(resumo, "total")
    dia = periodos.get("dia") or _bloco_periodo(resumo, "dia")
    semana = periodos.get("semana") or _bloco_periodo(resumo, "semana")
    mes = periodos.get("mes") or _bloco_periodo(resumo, "mes")
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
        intervalo = f"Período coberto na base: {min(tudo)} a {max(tudo)}."
    serie = resumo.get("serie_dias") or []
    serie_txt = ", ".join(
        f"{item.get('rotulo')}: P{item.get('Pessoa', 0)} V{item.get('Veiculo', 0)}"
        for item in serie[-7:]
    ) or "sem série"
    historico = resumo.get("historico") or []
    hist_txt = " | ".join(
        f"{h.get('quando') or ''} {h.get('tipo') or ''} {h.get('nome') or h.get('id') or ''} "
        f"@{h.get('camera') or ''}"
        for h in historico[:6]
    ) or "nenhum"
    informes = resumo.get("informes") or []
    inf_txt = " | ".join(
        f"{i.get('quando') or ''} {i.get('tipo') or ''}: {(i.get('descricao') or '')[:80]}"
        for i in informes[:5]
    ) or "nenhum"
    insights = resumo.get("insights") or []
    ins_txt = " | ".join(
        f"{i.get('quando') or ''} {i.get('tipo') or ''} {i.get('nome') or ''}: {(i.get('descricao') or '')[:80]}"
        for i in insights[:4]
    ) or "nenhum"
    texto_resumo = str(resumo.get("resumo") or "").strip()
    assessoramento = str(resumo.get("assessoramento") or "").strip()
    return "\n".join([
        "CONSULTA À BASE do cliente logado (já carregada — use estes números; não diga que não tem acesso).",
        intervalo,
        "Totais do dia (hoje): " + _fmt_bloco(dia),
        "Totais da semana (últimos 7 dias): " + _fmt_bloco(semana),
        "Totais do mês: " + _fmt_bloco(mes),
        "Totais acumulados: " + _fmt_bloco(total),
        "Série diária (7 dias): " + serie_txt,
        "Acumulado analítico (cubo): " + ", ".join(f"{chave} {valor}" for chave, valor in por_classe.items()),
        "Por câmera no histórico: " + ", ".join(
            f"{nome} {qtd}" for nome, qtd in sorted(por_camera.items(), key=lambda par: -par[1])[:8]
        ),
        "Câmeras neste instante: " + ("; ".join(cameras_agora) or "nenhuma"),
        f"Ocorrências do aplicativo: {len(app)}. Naturezas: {naturezas}. Logradouros: {ruas}.",
        "Alertas de interesse: " + hist_txt,
        "Informes: " + inf_txt,
        "Insights: " + ins_txt,
        ("Resumo operacional: " + texto_resumo[:500]) if texto_resumo else "Resumo operacional: (vazio)",
        ("Assessoramento: " + assessoramento[:400]) if assessoramento else "",
        "Confirmações pendentes: " + ("; ".join(pendencias) or "nenhuma"),
        f"LED geral: {resumo.get('led') or 'branco'}",
        f"Voz da tela: {resumo.get('voz') or ''}"[:500],
        "Skill: analista criminal / policial experiente — cruza pessoa, horário, dia, câmera e ocorrências.",
        "Regra: 1 passagem de risco = 1 chance de invasão; 20h–06h e fim de semana elevam o peso.",
        _contexto_audio(resumo),
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


def _quer_registrar(baixo: str) -> bool:
    if any(t in baixo for t in (
        "o que ocorreu", "o que aconteceu", "o que houve", "resumo",
        "quantos", "quantas", "houve algo", "aconteceu algo",
    )):
        return False
    return bool(re.search(
        r"\b(registra|registrar|informar ocorr|lan[cç]ar ocorr|anota(?:r)? ocorr|"
        r"grava(?:r)? ocorr|houve um[a]? |aconteceu um[a]? )\b",
        baixo,
    )) or baixo.startswith(("houve ", "aconteceu "))


def _local(pergunta: str, resumo: dict, documento: str = "") -> dict:
    baixo = pergunta.lower()
    periodo = _resposta_periodo(pergunta, resumo)
    if periodo is not None:
        return periodo
    if _quer_registrar(baixo):
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
    from agente.criminal import pede_analise_criminal, resposta_chat

    if pede_analise_criminal(pergunta):
        try:
            return _normalizar(resposta_chat(documento, pergunta, resumo))
        except Exception:
            pass
    if any(trecho in baixo for trecho in ("áudio", "audio", "transcri", "xing", "socorro", "disparo", "nuvem")):
        pacote = (resumo or {}).get("audio") or {}
        alertas = pacote.get("alertas") or []
        esteira = pacote.get("esteira") or []
        if alertas:
            itens = [{"rotulo": f"{a.get('camera')}: {a.get('categoria')}", "total": a.get("nivel") or 1} for a in alertas[:8]]
            fala = "No áudio recente há risco. " + " ".join(
                f"{a.get('camera')}: {(a.get('texto') or a.get('detalhe') or '')[:80]}." for a in alertas[:3]
            )
        elif esteira:
            itens = [{"rotulo": e.get("camera") or "Camera", "total": 1} for e in esteira[:8]]
            fala = f"Há {len(esteira)} trecho(s) na esteira de transcrição, ainda sem palavra de risco ranqueada."
        else:
            itens = [{"rotulo": "Sem áudio", "total": 0}]
            fala = "Ainda não há transcrição de áudio registrada nesta sessão."
        return _normalizar({
            "fala": fala,
            "visual": {"tipo": "barras", "titulo": "Áudio por câmera", "itens": itens},
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
    # Fallback geral: narra o dia a partir da base em vez de só ecoar a voz da tela.
    return _narrar_periodo(resumo, "dia")
