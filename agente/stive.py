"""Agente Stive: conversa sobre a base local e confirmações para o modelo."""

from __future__ import annotations

import json
import re
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

ARQUIVO = Path("feedback_modelo.json")
ARQUIVO_CHATS = Path("historico_stive.json")
_TRAVA = threading.Lock()
_CHATS = {}
_VISUAIS = {}


def _chave_chat(documento: str = "", email: str = "") -> str:
    """Cada usuário (e-mail) tem conversa própria; documento só como fallback."""
    mail = str(email or "").strip().lower()
    if mail:
        return f"u:{mail}"
    digitos = "".join(c for c in str(documento or "") if c.isdigit())
    return f"d:{digitos}" if digitos else "u:anonimo"


def _carregar_chats_disco():
    if not ARQUIVO_CHATS.exists():
        return
    try:
        bruto = json.loads(ARQUIVO_CHATS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(bruto, dict):
        return
    conversas = bruto.get("conversas") if isinstance(bruto.get("conversas"), dict) else None
    visuais = bruto.get("visuais") if isinstance(bruto.get("visuais"), dict) else None
    if conversas is None:
        conversas = {k: v for k, v in bruto.items() if isinstance(v, list)}
    for chave, fila in conversas.items():
        if isinstance(fila, list):
            _CHATS[str(chave)] = [dict(item) for item in fila if isinstance(item, dict)][-40:]
    if isinstance(visuais, dict):
        for chave, visual in visuais.items():
            if isinstance(visual, dict):
                _VISUAIS[str(chave)] = dict(visual)


def _gravar_chats_disco():
    try:
        ARQUIVO_CHATS.write_text(
            json.dumps(
                {"conversas": _CHATS, "visuais": _VISUAIS},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


_carregar_chats_disco()

_SISTEMA = (
    "Você é Stive, agente de segurança do C4ISTAR MONITOR e analista criminal de campo. "
    "Fale como policial experiente: horário, dia da semana, local, pessoa e padrão importam. "
    "Responda em português, objetivo, usando SEMPRE o contexto numérico e textual enviado abaixo. "
    "Esse contexto JÁ É a consulta à base do CPF/CNPJ da sessão (dia, semana, mês, total, cubo, app, alertas). "
    "ISOLAMENTO: cada dado está atrelado a um CPF/CNPJ. Se o perfil não for administrador, fale e enxergue "
    "APENAS o documento da sessão. Nunca mencione, compare ou invente dados de outros clientes, do administrador "
    "ou de outros CPF/CNPJ. Não sugira nem descreva alerta/informe classificado para outro documento. "
    "Se o perfil for administrador, pode falar sobre qualquer cliente listado no contexto. "
    "NUNCA diga que não tem acesso, que não consegue consultar, que falta permissão ou que os dados "
    "do dia/semana não estão disponíveis. Se o total do período for zero, diga claramente que "
    "na base daquele período não há registros — isso ainda é uma resposta com base nos dados. "
    "Quando perguntarem o que ocorreu no dia, na semana ou no mês, use os blocos Totais do dia / "
    "da semana / do mês, a série diária, ocorrências, matches, áudio, informes, insights e "
    "variações de fluxo (pessoas/veículos por minuto com percentual) do contexto. "
    "Se houver aumento ou redução de fluxo, cite câmera, compare com a média da hora, "
    "informe de→para e a variação percentual (também hora/dia quando houver). "
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


def faces_rosto_respondidas() -> set[str]:
    """Faces já tratadas no fluxo conhece/vínculo/suspeito (não perguntar de novo)."""
    saida: set[str] = set()
    bruto = _ler()
    for item in bruto.get("respostas") or []:
        tipo = str(item.get("tipo") or "")
        if not tipo.lower().startswith("rosto_"):
            continue
        if ":" in tipo:
            face = tipo.split(":", 1)[1].strip().upper()
            if face:
                saida.add(face)
    return saida


def historico(
    documento: str = "",
    email: str = "",
    perfil: str = "",
    todos: bool = False,
) -> list[dict]:
    """Histórico do usuário. Só o administrador pode pedir a visão completa (todos=True)."""
    with _TRAVA:
        if todos and perfil == "administrador":
            saida = []
            for chave, fila in _CHATS.items():
                for item in fila[-20:]:
                    bloco = dict(item)
                    bloco["origem"] = chave
                    saida.append(bloco)
            return saida[-80:]
        chave = _chave_chat(documento, email)
        return [dict(item) for item in _CHATS.get(chave, [])][-40:]


def visual_usuario(documento: str = "", email: str = "") -> dict:
    """Último quadro pedido pelo próprio usuário (nunca compartilha entre sessões)."""
    with _TRAVA:
        chave = _chave_chat(documento, email)
        bruto = _VISUAIS.get(chave) or {}
        return dict(bruto) if isinstance(bruto, dict) else {}


def responder(documento: str, pergunta: str, resumo: dict, email: str = "", perfil: str = "") -> dict:
    pergunta = (pergunta or "").strip()
    if not pergunta:
        raise ValueError("Escreva a pergunta para o Stive.")
    from agente.criminal import analisar, pede_analise_criminal, texto_briefing

    chave = _chave_chat(documento, email)
    perfil = (perfil or str((resumo or {}).get("perfil_sessao") or "")).strip().lower()
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
        _guardar(
            chave,
            pergunta,
            local_periodo["fala"],
            email=email,
            documento=documento,
            visual=local_periodo.get("visual"),
        )
        return local_periodo
    contexto = _contexto(resumo, documento=documento, perfil=perfil)
    if briefing:
        contexto = contexto + "\n\n" + briefing
    try:
        from agente.modelo import SessaoGPT, extrair_json

        sessao = SessaoGPT()
        if sessao.disponivel:
            texto = sessao.perguntar(
                _SISTEMA,
                contexto + "\n\nHistórico:\n" + _historico_texto(chave) + "\n\nPergunta: " + pergunta,
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
                _guardar(
                    chave,
                    pergunta,
                    resultado["fala"],
                    email=email,
                    documento=documento,
                    visual=resultado.get("visual"),
                )
                _registrar_ocorrencia(documento, resultado.get("ocorrencia"), perfil=perfil)
                return resultado
    except Exception:
        pass
    resultado = local_periodo or _local(pergunta, resumo, documento=documento)
    _guardar(
        chave,
        pergunta,
        resultado["fala"],
        email=email,
        documento=documento,
        visual=resultado.get("visual"),
    )
    _registrar_ocorrencia(documento, resultado.get("ocorrencia"), perfil=perfil)
    return resultado


def confirmar(
    documento: str,
    ident: str,
    resposta: str,
    texto: str,
    camera: str,
    tipo: str,
    vinculo: str = "",
    nome: str = "",
    faces_engine=None,
) -> dict:
    ident = (ident or "").strip()
    if not ident:
        raise ValueError("Confirmação sem identificador.")
    sim = (resposta or "").strip().lower() in ("sim", "s", "1", "confirmo")
    vinculo = str(vinculo or "").strip().lower()
    nome = " ".join(str(nome or "").split())
    with _TRAVA:
        bruto = _ler()
        bruto.setdefault("respostas", []).append({
            "id": ident,
            "resposta": "sim" if sim else "nao",
            "texto": (texto or "")[:240],
            "camera": camera or "",
            "tipo": tipo or "",
            "vinculo": vinculo,
            "nome": nome,
            "quando": datetime.now().isoformat(timespec="seconds"),
        })
        bruto["respostas"] = bruto["respostas"][-200:]
        _gravar(bruto)
    try:
        from agente.aprendizado_feedback import aplicar_feedback

        aplicar_feedback(
            1 if sim else -1,
            texto=texto or "",
            tipo=tipo or "",
            titulo="confirmação",
            camera=camera or "",
            documento=documento or "",
        )
    except Exception:
        pass
    tipo_base = str(tipo or "")
    face_freq = ""
    if tipo_base.startswith("rosto_frequente:"):
        face_freq = tipo_base.split(":", 1)[1].strip().upper()
    elif tipo_base.startswith("rosto_vinculo:"):
        face_freq = tipo_base.split(":", 1)[1].strip().upper()
    elif tipo_base.startswith("rosto_suspeito:"):
        face_freq = tipo_base.split(":", 1)[1].strip().upper()

    if not sim:
        try:
            from audio_registro import rejeitar_pendente

            rejeitar_pendente(ident)
        except Exception:
            pass
        if face_freq:
            return {
                "fala": "Anotado. Mantemos só o código do rosto sem cadastro de interesse.",
                "ok": True,
            }
        return {
            "fala": "Anotado. Sem disparo — dado ignorado e nada entra na base.",
            "ok": True,
        }

    if tipo_base.startswith("rosto_frequente:") and face_freq:
        # Mesmo balão: pede nome + vínculo (não cria segunda pendência).
        if vinculo:
            return _gravar_vinculo_e_perguntar_suspeito(
                documento, ident, face_freq, vinculo, camera, nome=nome, faces_engine=faces_engine
            )
        try:
            from grafo_relacoes import VINCULOS_STIVE

            opcoes = list(VINCULOS_STIVE.items())
        except Exception:
            opcoes = [
                ("conhecido", "Conhecido"),
                ("amigo", "Amigo(a)"),
                ("familiar", "Familiar"),
            ]
        return {
            "fala": (
                f"Você conhece o rosto {face_freq}. "
                "Informe o nome desta pessoa e o vínculo para eu associar na base."
            ),
            "etapa": "vinculo",
            "face_id": face_freq,
            "id": ident,
            "tipo": f"rosto_vinculo:{face_freq}",
            "camera": camera or "frequentes",
            "foto": f"/rosto/{face_freq}.jpg",
            "vinculos": [{"id": k, "rotulo": v} for k, v in opcoes],
            "ok": True,
        }

    if tipo_base.startswith("rosto_vinculo:") and face_freq:
        return _gravar_vinculo_e_perguntar_suspeito(
            documento, ident, face_freq, vinculo, camera, nome=nome, faces_engine=faces_engine
        )

    if tipo_base.startswith("rosto_suspeito:") and face_freq:
        try:
            from cadastro import cadastrar_pessoa

            cadastrar_pessoa(documento, {
                "face_id": face_freq,
                "nome": f"Interesse {face_freq}",
                "classe": "comportamento_suspeito",
                "base_legal": "comportamento_suspeito",
                "motivo": "ameaca",
                "referencia": "Cadastro automático via Stive (rosto frequente)",
            })
            return {
                "fala": (
                    f"Cadastrado {face_freq} como pessoa de interesse (comportamento suspeito). "
                    "A partir de agora o monitoramento gera alerta."
                ),
                "ok": True,
            }
        except Exception as exc:
            return {"fala": f"Não consegui cadastrar automaticamente: {exc}", "ok": False}

    natureza = {
        "disparo": "Disparo",
        "audio": "Áudio de risco",
        "veiculo": "Permanência de veículo",
        "pessoa": "Permanência de pessoa",
    }.get(tipo_base, "Confirmação de campo")
    audio_gravado = False
    if tipo_base in ("disparo", "audio", "briga", "socorro"):
        try:
            from audio_registro import confirmar_pendente

            audio_gravado = confirmar_pendente(ident)
        except Exception:
            audio_gravado = False
    if tipo_base == "disparo":
        try:
            from audio_registro import marcar_disparo_confirmado

            marcar_disparo_confirmado(camera or "", segundos=300)
        except Exception:
            pass
    from ocorrencias import informar_ocorrencia

    informar_ocorrencia(documento, {
        "data": datetime.now().strftime("%Y-%m-%d"),
        "hora": datetime.now().strftime("%H:%M"),
        "natureza": natureza,
        "descricao": (texto or natureza) + " Confirmado pelo operador com o Agente Stive.",
        "endereco": camera or "",
    }, usar_modelo=False)
    if tipo_base == "disparo":
        return {
            "fala": "Confirmado. Disparo lançado na base e risco vermelho ativado na câmera.",
            "ok": True,
        }
    if audio_gravado:
        return {"fala": "Confirmado. Áudio e ocorrência gravados na base.", "ok": True}
    return {"fala": "Confirmação gravada na base de ocorrências.", "ok": True}


def _gravar_vinculo_e_perguntar_suspeito(
    documento: str,
    ident: str,
    face_freq: str,
    vinculo: str,
    camera: str,
    nome: str = "",
    faces_engine=None,
) -> dict:
    vinculo = str(vinculo or "").strip().lower() or "conhecido"
    nome = " ".join(str(nome or "").split())
    face_final = face_freq
    assoc = None
    try:
        from grafo_relacoes import TIPOS_VINCULO, VINCULOS_STIVE
        from cadastro import associar_rosto_conhecido

        validos = set(TIPOS_VINCULO) | set(VINCULOS_STIVE)
        if vinculo not in validos or vinculo in {"medida_protege", "proprio"}:
            vinculo = "conhecido"
        if faces_engine is None:
            try:
                from remoto import portal as _portal

                faces_engine = getattr(_portal, "_faces", None)
            except Exception:
                faces_engine = None
        assoc = associar_rosto_conhecido(
            documento,
            face_freq,
            nome,
            vinculo,
            faces_engine=faces_engine,
        )
        face_final = str((assoc or {}).get("face_canonica") or face_freq).upper()
    except Exception as exc:
        return {"fala": f"Não consegui gravar o vínculo: {exc}", "ok": False}
    try:
        from main import _lembrar_pendencia
        import time as _time

        rotulo_pessoa = nome or face_final
        _lembrar_pendencia(
            "frequentes",
            f"rosto_suspeito:{face_final}",
            (
                f"Essa pessoa ({rotulo_pessoa} · {face_final}) é suspeita? "
                f"Confirme pela foto. Se sim, eu cadastro automaticamente como comportamento suspeito. "
                f"Foto: /rosto/{face_final}.jpg"
            ),
            _time.time(),
        )
    except Exception:
        pass
    rotulo = vinculo
    try:
        from grafo_relacoes import TIPOS_VINCULO

        rotulo = TIPOS_VINCULO.get(vinculo, vinculo)
    except Exception:
        pass
    nome_exib = nome or face_final
    extra = ""
    if assoc and assoc.get("cliente_associado"):
        cli_a = assoc["cliente_associado"]
        extra = (
            f" Associei também à conta de {cli_a.get('nome') or cli_a.get('documento')} "
            f"(face {assoc.get('face_canonica')}"
            + (f", score {assoc.get('score')}" if assoc.get("score") is not None else "")
            + ")."
        )
    elif nome:
        extra = " Nome registrado; ainda sem match facial com outro cliente cadastrado."
    return {
        "fala": (
            f"Vínculo «{rotulo}» salvo com {nome_exib} ({face_final}).{extra} "
            "Ela é suspeita? Responda Sim ou Não no próximo balão."
        ),
        "ok": True,
        "face_id": face_final,
        "vinculo": vinculo,
        "nome": nome_exib,
        "associacao": assoc,
    }


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
    if valor in (-1, 1):
        try:
            from agente.aprendizado_feedback import aplicar_feedback

            aplicar_feedback(
                valor,
                texto=texto or "",
                tipo=tipo or "",
                titulo=titulo or "",
                documento=documento or "",
            )
        except Exception:
            pass
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


def _guardar(chave: str, pergunta: str, fala: str, email: str = "", documento: str = "", visual=None):
    with _TRAVA:
        fila = _CHATS.setdefault(chave or "u:anonimo", [])
        agora = datetime.now().isoformat(timespec="seconds")
        fila.append({
            "papel": "eu",
            "texto": pergunta[:500],
            "quando": agora,
            "email": (email or "").strip().lower(),
            "documento": "".join(c for c in str(documento or "") if c.isdigit()),
        })
        fila.append({
            "papel": "stive",
            "texto": fala[:800],
            "quando": agora,
            "email": (email or "").strip().lower(),
            "documento": "".join(c for c in str(documento or "") if c.isdigit()),
        })
        del fila[:-40]
        if isinstance(visual, dict) and (visual.get("itens") or visual.get("tipo") or visual.get("titulo")):
            _VISUAIS[chave or "u:anonimo"] = {
                "tipo": str(visual.get("tipo") or "texto")[:20],
                "titulo": str(visual.get("titulo") or "")[:80],
                "itens": list(visual.get("itens") or [])[:24],
            }
        _gravar_chats_disco()


def _historico_texto(chave: str) -> str:
    with _TRAVA:
        fila = list(_CHATS.get(chave, []))[-12:]
    linhas = []
    for item in fila:
        linhas.append(f"{item.get('papel')}: {item.get('texto')}")
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
    eventos_fluxo = (resumo or {}).get("fluxo_eventos") or []
    if eventos_fluxo and chave == "dia":
        trechos = [str(e.get("texto") or "").strip() for e in eventos_fluxo[:4] if e.get("texto")]
        if trechos:
            partes.append("Variações de fluxo recentes: " + " ".join(trechos))
    for camera in (resumo or {}).get("cameras_vivo") or []:
        if chave != "dia":
            break
        fluxo_p = camera.get("fluxo") or {}
        fluxo_v = camera.get("fluxo_veiculo") or {}
        fp = int(fluxo_p.get("minuto") or 0)
        fph = int(fluxo_p.get("hora_dia") or fluxo_p.get("hora") or 0)
        fpd = int(fluxo_p.get("dia") or 0)
        fv = int(fluxo_v.get("minuto") or 0)
        fvh = int(fluxo_v.get("hora_dia") or fluxo_v.get("hora") or 0)
        fvd = int(fluxo_v.get("dia") or 0)
        if fp or fph or fpd or fv or fvh or fvd:
            partes.append(
                f"Agora na {camera.get('nome')}: pessoas {fp}/min, {fph}/h, {fpd}/dia; "
                f"veículos {fv}/min, {fvh}/h, {fvd}/dia."
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
        "fluxo", "aumento", "repentin", "lotação", "lotacao", "superlota",
        "por minuto", "passando", "informe", "alerta",
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


def _diretorio_clientes_admin() -> str:
    try:
        from cadastro import listar_clientes

        linhas = []
        for item in listar_clientes():
            doc = "".join(c for c in str(item.get("documento") or "") if c.isdigit())
            if not doc:
                continue
            nome = str(item.get("nome") or "") or doc
            ativo = "ativo" if item.get("ativo") is not False else "inativo"
            cams = len(item.get("cameras") or [])
            linhas.append(f"{nome} | CPF/CNPJ {doc} | {ativo} | câmeras {cams}")
        return "Contas cadastradas: " + (" || ".join(linhas[:40]) if linhas else "nenhuma")
    except Exception:
        return "Contas cadastradas: (indisponível)"


def _contexto(resumo: dict, documento: str = "", perfil: str = "") -> str:
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
        fluxo_p = camera.get("fluxo") or {}
        fluxo_v = camera.get("fluxo_veiculo") or {}
        cameras_agora.append(
            f"{camera.get('nome')}: agora P{agora.get('Pessoa', 0)} V{agora.get('Veiculo', 0)}; "
            f"fluxo pessoas {int(fluxo_p.get('minuto') or 0)}/min, "
            f"{int(fluxo_p.get('hora_dia') or fluxo_p.get('hora') or 0)}/h, "
            f"{int(fluxo_p.get('dia') or 0)}/dia; "
            f"fluxo veículos {int(fluxo_v.get('minuto') or 0)}/min, "
            f"{int(fluxo_v.get('hora_dia') or fluxo_v.get('hora') or 0)}/h, "
            f"{int(fluxo_v.get('dia') or 0)}/dia; "
            f"risco {camera.get('risco') or 'branco'}"
            + ("; fluxo anormal" if camera.get("fluxo_anormal") else "")
        )
    eventos_fluxo = resumo.get("fluxo_eventos") or []
    fluxo_txt = " | ".join(
        f"{e.get('quando') or ''} [{e.get('periodo') or 'minuto'}] {e.get('texto') or ''}"
        for e in eventos_fluxo[:12]
        if e.get("texto")
    ) or "nenhuma variação recente de faixa"
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
    doc = "".join(c for c in str(documento or resumo.get("cliente_documento") or "") if c.isdigit())
    perfil = (perfil or str(resumo.get("perfil_sessao") or "")).strip().lower()
    cabeca = [
        f"DOCUMENTO DA SESSÃO (CPF/CNPJ): {doc or '(não informado)'}. Perfil: {perfil or 'usuario'}.",
        "CONSULTA À BASE já carregada — use estes números; não diga que não tem acesso.",
    ]
    if perfil == "administrador":
        cabeca.append("ADMIN: pode perguntar sobre qualquer cliente/conta da lista.")
        cabeca.append(_diretorio_clientes_admin())
    else:
        cabeca.append(
            "RESTRITO AO CPF/CNPJ DA SESSÃO: não fale de outros clientes, do administrador "
            "nem de dados classificados de outro documento. Não envie nem sugira alerta para outro CPF/CNPJ."
        )
    return "\n".join(cabeca + [
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
        "Variações de fluxo (vs média da hora, com % ↑/↓): " + fluxo_txt,
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


def _registrar_ocorrencia(documento: str, ocorrencia: dict, perfil: str = ""):
    if not ocorrencia:
        return
    # Sempre grava só no CPF/CNPJ da sessão — nunca em outro documento.
    digitos = "".join(c for c in str(documento or "") if c.isdigit())
    if not digitos:
        return
    from ocorrencias import informar_ocorrencia

    agora = datetime.now()
    informar_ocorrencia(digitos, {
        "data": ocorrencia.get("data") or agora.strftime("%Y-%m-%d"),
        "hora": (ocorrencia.get("hora") or agora.strftime("%H:%M"))[:5],
        "natureza": ocorrencia.get("natureza"),
        "descricao": ocorrencia.get("descricao"),
        "endereco": ocorrencia.get("endereco") or "",
        "documento": digitos,
        "perfil_origem": (perfil or "")[:40],
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


def _narrar_fluxo(resumo: dict) -> dict:
    eventos = (resumo or {}).get("fluxo_eventos") or []
    cameras = (resumo or {}).get("cameras_vivo") or []
    partes = []
    itens = []
    for camera in cameras:
        nome = camera.get("nome") or "câmera"
        fluxo_p = camera.get("fluxo") or {}
        fluxo_v = camera.get("fluxo_veiculo") or {}
        fp = int(fluxo_p.get("minuto") or 0)
        fph = int(fluxo_p.get("hora_dia") or fluxo_p.get("hora") or 0)
        fpd = int(fluxo_p.get("dia") or 0)
        fv = int(fluxo_v.get("minuto") or 0)
        fvh = int(fluxo_v.get("hora_dia") or fluxo_v.get("hora") or 0)
        fvd = int(fluxo_v.get("dia") or 0)
        itens.extend([
            {"rotulo": f"{nome} pessoas/min", "total": fp},
            {"rotulo": f"{nome} pessoas/h", "total": fph},
            {"rotulo": f"{nome} pessoas/dia", "total": fpd},
            {"rotulo": f"{nome} veículos/min", "total": fv},
        ])
        if fp or fph or fpd or fv or fvh or fvd:
            partes.append(
                f"Na {nome} agora: {fp}/min, {fph}/h e {fpd}/dia de pessoas; "
                f"{fv}/min, {fvh}/h e {fvd}/dia de veículos."
            )
        if camera.get("fluxo_anormal"):
            partes.append(f"Fluxo de pessoas anormal na {nome} ({fp}/min).")
    unidade = {"minuto": "/min", "hora": "/h", "dia": "/dia"}
    for evento in eventos[:8]:
        texto = str(evento.get("texto") or "").strip()
        if texto:
            partes.append(texto)
            pct = evento.get("variacao_pct")
            periodo = str(evento.get("periodo") or "minuto")
            itens.append({
                "rotulo": f"{evento.get('camera') or ''} {evento.get('tipo') or ''} {periodo}",
                "total": (
                    f"{evento.get('de', 0)}→{evento.get('para', 0)}"
                    f"{unidade.get(periodo, '/min')}"
                    + (f" ({'+' if int(pct) >= 0 else ''}{pct}%)" if pct is not None else "")
                ),
            })
    if not partes:
        partes.append(
            "Neste momento não há variação de faixa de fluxo registrada; "
            "as contagens por minuto, hora e dia seguem nos monitores das câmeras."
        )
    return _normalizar({
        "fala": " ".join(partes),
        "visual": {
            "tipo": "barras" if len(itens) > 1 else "lista",
            "titulo": "Fluxo ao vivo",
            "itens": itens[:10] or [{"rotulo": "Sem variação", "total": 0}],
        },
    })


def _local(pergunta: str, resumo: dict, documento: str = "") -> dict:
    baixo = pergunta.lower()
    if any(trecho in baixo for trecho in (
        "fluxo", "por minuto", "por hora", "por dia", "/min", "/h",
        "superlota", "lotação", "lotacao",
        "aumento de pessoa", "aumento de veícul", "aumento de veicul",
        "repentin", "volume de pessoa", "volume de veícul", "volume de veicul",
        "passando agora", "quantas pessoas por", "quantos veículos por",
        "quantos veiculos por", "variação de fluxo", "variacao de fluxo",
    )):
        return _narrar_fluxo(resumo)
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
