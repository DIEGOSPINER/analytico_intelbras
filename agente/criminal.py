"""Skill de analista criminal do Agente Stive: probabilidade e cruzamento de histórico."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from agente.fontes import FonteCsv, carregar_interesse
from cadastro import classe_pessoa, pessoa_de_risco

DIAS_SEMANA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
PESO_MADRUGADA = 1.75
PESO_FIM_SEMANA = 1.25
# Cada passagem de pessoa de risco conta como 1 unidade de risco de invasão.
UNIDADE_INVASAO = 1.0


def _hora_int(texto: str) -> int | None:
    bruto = str(texto or "").strip()
    if len(bruto) < 2:
        return None
    try:
        return int(bruto[:2])
    except ValueError:
        return None


def _data_iso(texto: str) -> date | None:
    bruto = str(texto or "").strip()[:10]
    if len(bruto) < 10:
        return None
    try:
        return date.fromisoformat(bruto)
    except ValueError:
        return None


def eh_madrugada(hora: str | int | None) -> bool:
    if isinstance(hora, int):
        valor = hora
    else:
        valor = _hora_int(hora or "")
    if valor is None:
        return False
    return valor >= 20 or valor < 6


def peso_horario(hora: str | int | None) -> float:
    return PESO_MADRUGADA if eh_madrugada(hora) else 1.0


def peso_dia_semana(dia: date | None) -> float:
    if dia is None:
        return 1.0
    # Sexta, sábado e domingo elevam a atenção operacional.
    return PESO_FIM_SEMANA if dia.weekday() >= 4 else 1.0


def probabilidade_ao_menos_um(lambda_: float) -> float:
    """Chance percentual de ao menos um evento, com teto operacional de 95%."""
    try:
        valor = float(lambda_)
    except (TypeError, ValueError):
        valor = 0.0
    if valor <= 0:
        return 0.0
    return round(min(95.0, 100.0 * (1.0 - math.exp(-valor))), 1)


def _pessoas_cadastro(documento: str = "") -> list[dict]:
    pessoas = []
    try:
        import cadastro

        if documento:
            cliente = cadastro.cliente_por_documento(documento) or {}
            pessoas.extend(cliente.get("pessoas") or [])
        if not pessoas:
            for cliente in cadastro.listar_clientes() or []:
                pessoas.extend(cliente.get("pessoas") or [])
    except Exception:
        pass
    try:
        interesse = carregar_interesse()
        pessoas.extend(interesse.get("pessoas") or [])
    except Exception:
        pass
    vistos = set()
    unicos = []
    for item in pessoas:
        face = str(item.get("face_id") or item.get("id") or "").strip().upper()
        if not face or face in vistos:
            continue
        vistos.add(face)
        unicos.append(dict(item, face_id=face))
    return unicos


def _passagens_face(fonte: FonteCsv, face_id: str) -> list[dict]:
    face_id = str(face_id or "").strip().upper()
    saida = []
    for linha in fonte.linhas("faces"):
        if str(linha.get("Face_ID") or "").strip().upper() != face_id:
            continue
        saida.append(linha)
    return saida


def _extrair_alvo(pergunta: str, pessoas: list[dict]) -> dict | None:
    baixo = (pergunta or "").lower()
    for pessoa in pessoas:
        face = str(pessoa.get("face_id") or "").strip().upper()
        nome = str(pessoa.get("nome") or "").strip()
        if face and face.lower() in baixo:
            return pessoa
        if nome and len(nome) >= 3 and nome.lower() in baixo:
            return pessoa
        # tokens do nome
        for pedaco in re.findall(r"[a-zà-ü]{4,}", nome.lower()):
            if pedaco in baixo:
                return pessoa
    return None


def _avaliar_pessoa(pessoa: dict, passagens: list[dict]) -> dict:
    face = str(pessoa.get("face_id") or "").strip().upper()
    nome = str(pessoa.get("nome") or face)
    classe = classe_pessoa(pessoa) or str(pessoa.get("motivo") or "")
    risco = pessoa_de_risco(pessoa) or bool(re.search(
        r"invas|roub|furt|mandad|risco|suspei|ex.?deten|protetiv",
        f"{classe} {pessoa.get('motivo') or ''}".lower(),
    ))
    datas = []
    cameras = Counter()
    horas = Counter()
    dias_semana = Counter()
    madrugada = 0
    diurno = 0
    risco_ponderado = 0.0
    for linha in passagens:
        dia = _data_iso(linha.get("Data") or "")
        hora = linha.get("Hora") or ""
        if dia:
            datas.append(dia)
            dias_semana[DIAS_SEMANA[dia.weekday()]] += 1
        cameras[str(linha.get("Camera") or "Sem câmera")] += 1
        hi = _hora_int(hora)
        if hi is not None:
            horas[f"{hi:02d}h"] += 1
        peso = UNIDADE_INVASAO * peso_horario(hora) * peso_dia_semana(dia)
        risco_ponderado += peso
        if eh_madrugada(hora):
            madrugada += 1
        else:
            diurno += 1
    dias_unicos = sorted(set(datas))
    janela_dias = max(1, (dias_unicos[-1] - dias_unicos[0]).days + 1) if dias_unicos else 1
    unidades = float(len(passagens))  # 1 passagem = 1 risco de invasão
    taxa_dia = risco_ponderado / janela_dias
    taxa_simples = unidades / janela_dias
    agora = datetime.now()
    fator_agora = peso_horario(agora.hour) * peso_dia_semana(agora.date())
    expectativa_24h = taxa_dia * fator_agora
    expectativa_madrugada = (madrugada * PESO_MADRUGADA / janela_dias) if janela_dias else 0.0
    return {
        "id": face,
        "nome": nome,
        "classe": classe,
        "risco": risco,
        "passagens": len(passagens),
        "unidades_invasao": unidades,
        "dias_com_passagem": len(dias_unicos),
        "janela_dias": janela_dias,
        "madrugada": madrugada,
        "diurno": diurno,
        "risco_ponderado": round(risco_ponderado, 2),
        "taxa_dia": round(taxa_dia, 3),
        "taxa_simples": round(taxa_simples, 3),
        "prob_24h": probabilidade_ao_menos_um(expectativa_24h),
        "prob_madrugada": probabilidade_ao_menos_um(expectativa_madrugada * fator_agora),
        "prob_periodo": probabilidade_ao_menos_um(risco_ponderado / max(janela_dias / 7.0, 1.0)),
        "cameras": cameras.most_common(5),
        "horas": horas.most_common(6),
        "dias_semana": dias_semana.most_common(7),
        "primeira": dias_unicos[0].isoformat() if dias_unicos else "",
        "ultima": dias_unicos[-1].isoformat() if dias_unicos else "",
    }


def _cruzar_ocorrencias(fonte: FonteCsv, cameras: set[str]) -> list[dict]:
    cruzados = []
    for linha in fonte.linhas("ocorrencias")[-400:]:
        nivel = 0
        try:
            nivel = int(float(linha.get("Nivel_Risco") or 0))
        except (TypeError, ValueError):
            nivel = 0
        camera = str(linha.get("Camera") or "")
        classe = str(linha.get("Classe") or "")
        if nivel < 2 and not re.search(r"Briga|Queda|Arma|Aglomer|Permanenc|Interacao", classe, re.I):
            continue
        if cameras and camera and camera not in cameras:
            continue
        cruzados.append({
            "data": linha.get("Data") or "",
            "hora": linha.get("Hora") or "",
            "camera": camera,
            "classe": classe,
            "risco": linha.get("Risco") or "",
            "nivel": nivel,
            "madrugada": eh_madrugada(linha.get("Hora") or ""),
        })
    return cruzados[-40:]


def _cruzar_app(resumo: dict, nomes: list[str], cameras: set[str]) -> list[dict]:
    saida = []
    nomes_l = [n.lower() for n in nomes if n]
    for item in (resumo or {}).get("app_linhas") or []:
        texto = " ".join([
            str(item.get("natureza") or ""),
            str(item.get("descricao") or ""),
            str(item.get("rua") or ""),
            str(item.get("camera") or ""),
        ]).lower()
        camera = str(item.get("camera") or "")
        bate_nome = any(n in texto for n in nomes_l)
        bate_cam = camera in cameras if cameras and camera else False
        if not (bate_nome or bate_cam):
            continue
        saida.append({
            "data": item.get("data") or "",
            "hora": item.get("hora") or "",
            "natureza": item.get("natureza") or "",
            "descricao": (item.get("descricao") or "")[:120],
            "camera": camera,
            "rua": item.get("rua") or "",
            "madrugada": eh_madrugada(str(item.get("hora") or "")),
        })
    return saida[:20]


def analisar(documento: str = "", pergunta: str = "", resumo: dict | None = None) -> dict:
    """Calcula chances de invasão/ocorrência e cruza pessoa, horário, local e registros."""
    fonte = FonteCsv(".")
    pessoas = _pessoas_cadastro(documento)
    alvo = _extrair_alvo(pergunta, pessoas)
    foco = [alvo] if alvo else [p for p in pessoas if pessoa_de_risco(p)]
    if not foco:
        foco = pessoas[:8]
    avaliacoes = []
    for pessoa in foco:
        face = str(pessoa.get("face_id") or "").strip().upper()
        if not face:
            continue
        avaliacoes.append(_avaliar_pessoa(pessoa, _passagens_face(fonte, face)))
    avaliacoes.sort(key=lambda item: (-item["risco_ponderado"], -item["passagens"]))

    cameras = {cam for item in avaliacoes for cam, _ in item.get("cameras") or []}
    nomes = [item["nome"] for item in avaliacoes]
    ocorrencias = _cruzar_ocorrencias(fonte, cameras)
    app = _cruzar_app(resumo or {}, nomes, cameras)

    # Janela agregada da área
    total_unidades = sum(item["unidades_invasao"] for item in avaliacoes)
    total_ponderado = sum(item["risco_ponderado"] for item in avaliacoes)
    janela = max((item["janela_dias"] for item in avaliacoes), default=1)
    agora = datetime.now()
    fator = peso_horario(agora.hour) * peso_dia_semana(agora.date())
    prob_area_24h = probabilidade_ao_menos_um((total_ponderado / max(janela, 1)) * fator)
    prob_area_madrugada = probabilidade_ao_menos_um(
        (sum(item["madrugada"] * PESO_MADRUGADA for item in avaliacoes) / max(janela, 1)) * max(fator, PESO_MADRUGADA)
    )

    por_hora = Counter()
    por_dia = Counter()
    for item in avaliacoes:
        for rotulo, qtd in item.get("horas") or []:
            por_hora[rotulo] += qtd
        for rotulo, qtd in item.get("dias_semana") or []:
            por_dia[rotulo] += qtd

    return {
        "alvo": avaliacoes[0] if alvo and avaliacoes else None,
        "pessoas": avaliacoes[:8],
        "total_passagens": int(total_unidades),
        "total_ponderado": round(total_ponderado, 2),
        "janela_dias": janela,
        "prob_area_24h": prob_area_24h,
        "prob_area_madrugada": prob_area_madrugada,
        "fator_agora": round(fator, 2),
        "agora_madrugada": eh_madrugada(agora.hour),
        "ocorrencias_cruzadas": ocorrencias[:12],
        "app_cruzado": app[:10],
        "por_hora": por_hora.most_common(8),
        "por_dia": por_dia.most_common(7),
        "regra": (
            "Cada passagem de pessoa de risco = 1 unidade de risco de invasão. "
            f"Entre 20h e 06h o peso sobe para {PESO_MADRUGADA}x; "
            f"sexta a domingo {PESO_FIM_SEMANA}x."
        ),
    }


def texto_briefing(analise: dict) -> str:
    linhas = [
        "Briefing de analista criminal (base histórica local):",
        analise.get("regra") or "",
        (
            f"Área: {analise.get('total_passagens', 0)} passagens-risco em "
            f"{analise.get('janela_dias', 1)} dia(s). "
            f"Chance estimada nas próximas 24h: {analise.get('prob_area_24h', 0)}%. "
            f"Na faixa 20h–06h: {analise.get('prob_area_madrugada', 0)}%."
        ),
        f"Fator horário/dia agora: {analise.get('fator_agora', 1)}x"
        + (" (madrugada — eleva a atenção)." if analise.get("agora_madrugada") else " (diurno)."),
    ]
    for item in analise.get("pessoas") or []:
        cams = ", ".join(f"{c} ({n})" for c, n in (item.get("cameras") or [])[:3]) or "sem câmera"
        linhas.append(
            f"- {item.get('nome')} ({item.get('id')}): {item.get('passagens')} passagem(ns) = "
            f"{item.get('unidades_invasao')} risco(s) de invasão; "
            f"{item.get('madrugada')} na madrugada; "
            f"chance 24h {item.get('prob_24h')}%, madrugada {item.get('prob_madrugada')}%; "
            f"câmeras: {cams}."
        )
    if analise.get("ocorrencias_cruzadas"):
        linhas.append(
            "Cruzamento com ocorrências de risco nas mesmas câmeras: "
            + "; ".join(
                f"{o.get('data')} {str(o.get('hora') or '')[:5]} {o.get('camera')} {o.get('classe')}"
                for o in analise["ocorrencias_cruzadas"][:5]
            )
        )
    if analise.get("app_cruzado"):
        linhas.append(
            "Cruzamento com informes do aplicativo: "
            + "; ".join(
                f"{o.get('data')} {o.get('natureza')} {o.get('rua') or o.get('camera')}"
                for o in analise["app_cruzado"][:5]
            )
        )
    if analise.get("por_hora"):
        linhas.append("Horários mais quentes: " + ", ".join(f"{h} {n}" for h, n in analise["por_hora"][:5]))
    if analise.get("por_dia"):
        linhas.append("Dias da semana: " + ", ".join(f"{d} {n}" for d, n in analise["por_dia"][:5]))
    return "\n".join(linhas)


def resposta_chat(documento: str = "", pergunta: str = "", resumo: dict | None = None) -> dict:
    """Monta fala e visual para o chatbot a partir da análise criminal."""
    analise = analisar(documento, pergunta, resumo)
    alvo = analise.get("alvo")
    if alvo:
        fala = (
            f"Como analista criminal: {alvo['nome']} aparece {alvo['passagens']} vez(es) "
            f"em {alvo['janela_dias']} dia(s) de histórico. "
            f"Pela regra operacional, isso equivale a {int(alvo['unidades_invasao'])} risco(s) de invasão. "
            f"{alvo['madrugada']} dessas passagens foram entre 20h e 06h, faixa preferida para furto e invasão. "
            f"Chance estimada nas próximas 24h: {alvo['prob_24h']}%. "
            f"Se a exposição for na madrugada: {alvo['prob_madrugada']}%. "
        )
        if alvo.get("cameras"):
            cam, qtd = alvo["cameras"][0]
            fala += f"Ponto mais recorrente: {cam} ({qtd} passagem(ns)). "
    else:
        fala = (
            f"Como analista criminal da área: {analise.get('total_passagens', 0)} passagem(ns) "
            f"de interesse em {analise.get('janela_dias', 1)} dia(s). "
            f"Cada passagem conta 1 risco de invasão; de 20h às 06h o peso sobe. "
            f"Chance estimada nas próximas 24h: {analise.get('prob_area_24h', 0)}%. "
            f"Na madrugada: {analise.get('prob_area_madrugada', 0)}%. "
        )
    cruz = len(analise.get("ocorrencias_cruzadas") or []) + len(analise.get("app_cruzado") or [])
    if cruz:
        fala += f"Cruzei {cruz} registro(s) correlatos de ocorrência/informe nos mesmos pontos. "
    if analise.get("agora_madrugada"):
        fala += "Estamos na janela de madrugada: mantenha reforço de observação."
    else:
        fala += "Fora da madrugada o peso é menor, mas o padrão histórico permanece válido."

    itens = []
    for item in analise.get("pessoas") or []:
        itens.append({
            "rotulo": f"{item.get('nome')} · 24h",
            "total": item.get("prob_24h"),
        })
        itens.append({
            "rotulo": f"{item.get('nome')} · madrugada",
            "total": item.get("prob_madrugada"),
        })
    if not itens:
        itens = [
            {"rotulo": "Área 24h", "total": analise.get("prob_area_24h", 0)},
            {"rotulo": "Área madrugada", "total": analise.get("prob_area_madrugada", 0)},
        ]
    for hora, qtd in (analise.get("por_hora") or [])[:4]:
        itens.append({"rotulo": f"Passagens {hora}", "total": qtd})

    return {
        "fala": fala.strip()[:1200],
        "visual": {
            "tipo": "barras",
            "titulo": "Chance estimada de risco / invasão (%)",
            "itens": itens[:12],
        },
        "ocorrencia": {},
        "analise": analise,
    }


def pede_analise_criminal(pergunta: str) -> bool:
    baixo = (pergunta or "").lower()
    gatilhos = (
        "probabil", "chance", "invas", "risco de", "madrugada", "cruz",
        "padrão", "padrao", "crimin", "analista", "policial", "onde passa",
        "quantas vezes", "passou", "passagem", "quando costuma", "dia da semana",
        "horário", "horario", "furto", "roub", "vigilân", "vigilan", "ameaça", "ameaca",
        "pessoa de interesse", "ex-detento", "mandado", "medida protetiva",
    )
    return any(g in baixo for g in gatilhos)
