"""Configuração de alertas por usuário e por grupo de segurança."""

from __future__ import annotations

import json
import threading
from pathlib import Path

ARQUIVO = Path("config_alertas.json")
_TRAVA = threading.RLock()

# Catálogo: o que o usuário pode marcar na tela e o Stive/e-mail respeitam.
CATALOGO = (
    {
        "id": "disparos",
        "nome": "Disparos e áudio de risco",
        "descricao": "Estalos, disparo, briga, socorro e áudio crítico no Stive e por e-mail.",
        "grupo": "Campo",
        "stive": True,
        "email": True,
    },
    {
        "id": "comportamentos",
        "nome": "Comportamentos",
        "descricao": "Pessoa caída, correndo, interação, aglomeração e frases de comportamento.",
        "grupo": "Campo",
        "stive": True,
        "email": True,
    },
    {
        "id": "permanencia",
        "nome": "Permanência / parada",
        "descricao": "Pessoa ou veículo parado além do tempo — confirmação no Stive.",
        "grupo": "Campo",
        "stive": True,
        "email": False,
    },
    {
        "id": "variacao_fluxo",
        "nome": "Variações de fluxo",
        "descricao": "Aumento ou queda anormal de pessoas/veículos por minuto.",
        "grupo": "Campo",
        "stive": True,
        "email": False,
    },
    {
        "id": "ocorrencias_area",
        "nome": "Ocorrências na área",
        "descricao": "Ocorrências lançadas no aplicativo na rua/bairro.",
        "grupo": "Área",
        "stive": True,
        "email": True,
    },
    {
        "id": "reconhecimento_interesse",
        "nome": "Reconhecimento de pessoas de interesse",
        "descricao": "Match facial de risco (mandado, suspeito, desaparecida, etc.).",
        "grupo": "RF / LPR",
        "stive": True,
        "email": True,
    },
    {
        "id": "rostos_frequentes",
        "nome": "Rostos frequentes / vínculo",
        "descricao": "Perguntas do Stive sobre rostos que passam muito ou vínculo.",
        "grupo": "RF / LPR",
        "stive": True,
        "email": False,
    },
    {
        "id": "placas_interesse",
        "nome": "Placas de interesse (LPR)",
        "descricao": "Veículos cadastrados como interesse.",
        "grupo": "RF / LPR",
        "stive": True,
        "email": True,
    },
    {
        "id": "informes",
        "nome": "Informes do sistema",
        "descricao": "Avisos operacionais e informes enviados pelo monitor.",
        "grupo": "Sistema",
        "stive": True,
        "email": True,
    },
    {
        "id": "insights",
        "nome": "Insights e padrões",
        "descricao": "Padrões e insights gerados pelo agente.",
        "grupo": "Sistema",
        "stive": True,
        "email": False,
    },
    {
        "id": "alertas_grupo",
        "nome": "Alertas do grupo de segurança",
        "descricao": "Receber alertas canalizados pelos grupos em que você participa.",
        "grupo": "Grupos",
        "stive": True,
        "email": True,
    },
    {
        "id": "relatorio_diario",
        "nome": "Relatório diário por e-mail",
        "descricao": "Receber o fechamento do dia por e-mail.",
        "grupo": "E-mail",
        "stive": False,
        "email": True,
    },
)

IDS = tuple(item["id"] for item in CATALOGO)

PERFIS = {
    "completo": {
        "nome": "Completo",
        "descricao": "Todos os alertas ligados (recomendado para quem monitora a área).",
        "ativos": list(IDS),
    },
    "essencial": {
        "nome": "Essencial",
        "descricao": "Disparos, RF de risco, placas, permanência, ocorrências e relatório.",
        "ativos": [
            "disparos",
            "permanencia",
            "ocorrencias_area",
            "reconhecimento_interesse",
            "placas_interesse",
            "alertas_grupo",
            "relatorio_diario",
        ],
    },
    "silencioso": {
        "nome": "Silencioso",
        "descricao": "Só o crítico: disparos e pessoas/placas de interesse.",
        "ativos": [
            "disparos",
            "reconhecimento_interesse",
            "placas_interesse",
            "alertas_grupo",
        ],
    },
    "personalizado": {
        "nome": "Personalizado",
        "descricao": "Você escolhe item a item nos checks abaixo.",
        "ativos": None,
    },
}

_DEFAULT_ATIVOS = list(PERFIS["completo"]["ativos"])


def _digitos(valor: str) -> str:
    return "".join(c for c in str(valor or "") if c.isdigit())


def _ler() -> dict:
    if not ARQUIVO.exists():
        return {"contas": {}}
    try:
        bruto = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"contas": {}}
    if not isinstance(bruto, dict):
        return {"contas": {}}
    bruto.setdefault("contas", {})
    return bruto


def _gravar(bruto: dict) -> None:
    ARQUIVO.write_text(json.dumps(bruto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def catalogo() -> list[dict]:
    return [dict(item) for item in CATALOGO]


def perfis() -> dict:
    return {chave: dict(valor) for chave, valor in PERFIS.items()}


def _normalizar_ativos(ativos, *, permitir_vazio: bool = False) -> list[str]:
    if not isinstance(ativos, (list, tuple, set)):
        return list(_DEFAULT_ATIVOS)
    vistos = []
    for item in ativos:
        chave = str(item or "").strip()
        if chave in IDS and chave not in vistos:
            vistos.append(chave)
    if vistos or permitir_vazio:
        return vistos
    return list(_DEFAULT_ATIVOS)


def padrao() -> dict:
    return {
        "perfil": "completo",
        "ativos": list(_DEFAULT_ATIVOS),
    }


def obter(documento: str) -> dict:
    digitos = _digitos(documento)
    with _TRAVA:
        contas = _ler().get("contas") or {}
        bruto = contas.get(digitos) if digitos else None
    if not isinstance(bruto, dict):
        return padrao()
    perfil = str(bruto.get("perfil") or "personalizado").strip().lower()
    if perfil not in PERFIS:
        perfil = "personalizado"
    if perfil != "personalizado" and PERFIS[perfil]["ativos"] is not None:
        ativos = list(PERFIS[perfil]["ativos"])
    else:
        ativos = _normalizar_ativos(bruto.get("ativos"))
        perfil = "personalizado"
    return {"perfil": perfil, "ativos": ativos}


def salvar(documento: str, *, perfil: str = "", ativos=None) -> dict:
    digitos = _digitos(documento)
    if not digitos:
        raise ValueError("Informe a conta.")
    perfil = str(perfil or "personalizado").strip().lower()
    if perfil not in PERFIS:
        perfil = "personalizado"
    if perfil != "personalizado" and PERFIS[perfil]["ativos"] is not None:
        lista = list(PERFIS[perfil]["ativos"])
    else:
        perfil = "personalizado"
        lista = _normalizar_ativos(ativos, permitir_vazio=True)
    registro = {"perfil": perfil, "ativos": lista}
    with _TRAVA:
        bruto = _ler()
        bruto.setdefault("contas", {})[digitos] = registro
        _gravar(bruto)
    return dict(registro)


def ativo(documento: str, tipo: str) -> bool:
    chave = str(tipo or "").strip()
    if chave not in IDS:
        return True
    return chave in set(obter(documento).get("ativos") or [])


def tipos_pendencia(tipo: str) -> str | None:
    """Mapeia tipo de pendência do main → id do catálogo."""
    base = str(tipo or "").strip().lower()
    if base.startswith("rosto_"):
        return "rostos_frequentes"
    if base == "disparo" or base.startswith("disparo"):
        return "disparos"
    if "perman" in base:
        return "permanencia"
    return None


def tipo_de_match(match: dict | None) -> str | None:
    if not isinstance(match, dict):
        return None
    tipo = str(match.get("tipo") or "").upper()
    if tipo == "PLACA":
        return "placas_interesse"
    if tipo == "FACE":
        return "reconhecimento_interesse"
    return None


def tipo_de_informe(item: dict | None) -> str:
    if not isinstance(item, dict):
        return "informes"
    baixo = f"{item.get('tipo') or ''} {item.get('descricao') or ''}".lower()
    if any(t in baixo for t in ("disparo", "tiro", "arma", "estalo")):
        return "disparos"
    if any(t in baixo for t in ("placa", "lpr", "veículo", "veiculo")):
        return "placas_interesse"
    if any(t in baixo for t in ("face", "facial", "pessoa de risco", "reconhec")):
        return "reconhecimento_interesse"
    if "fluxo" in baixo:
        return "variacao_fluxo"
    return "informes"


def tipo_de_voz(voz: str, match: dict | None = None) -> str | None:
    if match:
        t = tipo_de_match(match)
        if t:
            return t
    baixo = str(voz or "").lower()
    if any(t in baixo for t in ("disparo", "tiro", "briga", "socorro", "áudio", "audio")):
        return "disparos"
    if "reconhecimento facial" in baixo or "pessoa de risco" in baixo:
        return "reconhecimento_interesse"
    if "veículo de interesse" in baixo or "veiculo de interesse" in baixo:
        return "placas_interesse"
    if "fluxo" in baixo:
        return "variacao_fluxo"
    if any(t in baixo for t in ("queda", "correndo", "aglomer", "interaç", "interac", "deitad")):
        return "comportamentos"
    if "perman" in baixo or "parado" in baixo:
        return "permanencia"
    return None


def filtrar_resumo(resumo: dict, documento: str) -> dict:
    """Remove do pacote o que o usuário desmarcou (Stive / painéis)."""
    digitos = _digitos(documento)
    prefs = obter(digitos)
    ativos = set(prefs.get("ativos") or [])
    resumo = dict(resumo or {})
    resumo["alertas_prefs"] = prefs
    resumo["alertas_catalogo"] = [
        {**item, "ativo": item["id"] in ativos} for item in catalogo()
    ]

    pend = []
    for item in resumo.get("pendencias") or []:
        if not isinstance(item, dict):
            continue
        chave = tipos_pendencia(item.get("tipo") or "")
        if chave and chave not in ativos:
            continue
        pend.append(item)
    resumo["pendencias"] = pend

    resumo["informes"] = [
        item for item in (resumo.get("informes") or [])
        if isinstance(item, dict) and tipo_de_informe(item) in ativos
    ]
    if "ocorrencias_area" not in ativos:
        resumo["app"] = []
        # Mantém app_linhas nos painéis analíticos; só silencia Stive via flag.
        resumo["app_stive"] = False
    else:
        resumo["app_stive"] = True
    if "insights" not in ativos:
        resumo["insights"] = []

    match = resumo.get("match")
    tipo_m = tipo_de_match(match if isinstance(match, dict) else None)
    if tipo_m and tipo_m not in ativos:
        resumo["match"] = None
        resumo["narracao"] = ""
        resumo["narracao_ia"] = ""
        # Só limpa voz se ela era do match.
        voz = str(resumo.get("voz") or "")
        if "reconhecimento" in voz.lower() or "veículo de interesse" in voz.lower() or "veiculo de interesse" in voz.lower():
            resumo["voz"] = ""

    voz = str(resumo.get("voz") or "").strip()
    if voz:
        tipo_v = tipo_de_voz(voz, resumo.get("match") if isinstance(resumo.get("match"), dict) else None)
        if tipo_v and tipo_v not in ativos:
            resumo["voz"] = ""
        # Prefixo de grupo: se alertas_grupo off, remove prefixo mas mantém se o tipo base estiver on.
        if "alertas_grupo" not in ativos and voz.lower().startswith("alerta do grupo"):
            # Se o usuário não quer canal de grupo, silencia alertas que só vieram pelo grupo.
            grupos = []
            if isinstance(resumo.get("match"), dict):
                grupos = resumo["match"].get("grupos") or []
            if grupos:
                resumo["voz"] = ""
                resumo["match"] = None

    # Fluxo anormal nas câmeras ao vivo (Stive lê fluxo_anormal).
    if "variacao_fluxo" not in ativos:
        vivo = []
        for cam in resumo.get("cameras_vivo") or []:
            if not isinstance(cam, dict):
                continue
            copia = dict(cam)
            copia["fluxo_anormal"] = False
            copia["fluxo_eventos"] = []
            copia["fluxo_veiculo_eventos"] = []
            vivo.append(copia)
        resumo["cameras_vivo"] = vivo
        resumo["fluxo_eventos"] = []

    if "comportamentos" not in ativos:
        vivo = []
        for cam in resumo.get("cameras_vivo") or []:
            if not isinstance(cam, dict):
                continue
            copia = dict(cam)
            # Mantém dados no painel comportamento; só zera frase de risco para Stive.
            if copia.get("frase") and not copia.get("audio_vivo"):
                copia["frase"] = ""
            vivo.append(copia)
        resumo["cameras_vivo"] = vivo

    if "disparos" not in ativos:
        vivo = []
        for cam in resumo.get("cameras_vivo") or []:
            if not isinstance(cam, dict):
                continue
            copia = dict(cam)
            audio = copia.get("audio_vivo") or {}
            tipo_a = str(audio.get("tipo") or "").lower() if isinstance(audio, dict) else ""
            if tipo_a in ("disparo", "briga", "socorro", "xingamento", "voz_risco", "estalo"):
                copia["audio_vivo"] = None
            vivo.append(copia)
        resumo["cameras_vivo"] = vivo

    return resumo


def filtrar_emails_por_tipo(emails: list[str], tipo: str) -> list[str]:
    """Mantém só e-mails de contas que aceitam o tipo de alerta."""
    from cadastro import listar_clientes

    chave = str(tipo or "").strip()
    if chave not in IDS:
        return list(emails or [])
    mapa = {}
    for cli in listar_clientes():
        digitos = _digitos(cli.get("documento"))
        for email in (cli.get("emails") or []):
            texto = str(email or "").strip().lower()
            if texto:
                mapa[texto] = digitos
        # e-mail principal
        mail = str(cli.get("email") or "").strip().lower()
        if mail:
            mapa[mail] = digitos
        for cam in cli.get("cameras") or []:
            if not isinstance(cam, dict):
                continue
            for aviso in cam.get("avisos") or []:
                if not isinstance(aviso, dict):
                    continue
                em = str(aviso.get("email") or "").strip().lower()
                if em:
                    mapa[em] = digitos
    saida = []
    for email in emails or []:
        texto = str(email or "").strip()
        if not texto:
            continue
        digitos = mapa.get(texto.lower())
        if not digitos or ativo(digitos, chave):
            saida.append(texto)
    return saida


def alertas_padrao_grupo() -> list[str]:
    return [
        "disparos",
        "reconhecimento_interesse",
        "placas_interesse",
        "ocorrencias_area",
        "permanencia",
        "comportamentos",
    ]


def normalizar_alertas_grupo(alertas) -> list[str]:
    return _normalizar_ativos(alertas) if alertas is not None else alertas_padrao_grupo()
