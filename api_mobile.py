"""API JSON para o app Expo (iOS/Android).

Login emite o mesmo token do cookie do portal (Bearer).
YOLO permanece na borda; o app só lê resumo/Stive.
"""

from __future__ import annotations

import json
from typing import Callable
from urllib.parse import parse_qs


def token_de_headers(cookie: str, authorization: str) -> str:
    for parte in str(cookie or "").split(";"):
        nome, _, valor = parte.strip().partition("=")
        if nome == "analitico":
            return valor
    auth = str(authorization or "").strip()
    if not auth:
        return ""
    esquema, _, resto = auth.partition(" ")
    if esquema.lower() == "bearer":
        return resto.strip()
    return auth


def corpo_json(rfile, content_length: str) -> dict:
    try:
        tamanho = int(content_length or "0")
    except ValueError:
        tamanho = 0
    if tamanho <= 0 or tamanho > 1_000_000:
        return {}
    bruto = rfile.read(tamanho)
    try:
        dados = json.loads(bruto.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        try:
            qs = parse_qs(bruto.decode("utf-8"), keep_blank_values=True)
            return {k: (v[0] if v else "") for k, v in qs.items()}
        except Exception:
            return {}
    return dados if isinstance(dados, dict) else {}


def login(portal, email: str, senha: str) -> tuple[int, dict]:
    import acesso
    import cadastro

    try:
        usuario = acesso.autenticar(email, senha)
    except ValueError as exc:
        return 401, {"ok": False, "erro": str(exc)}
    conta = cadastro.cliente_por_documento(usuario.get("documento") or "")
    if conta is not None and conta.get("ativo") is False and usuario.get("perfil") != "administrador":
        return 403, {"ok": False, "erro": "Esta conta está inativa."}
    token = acesso.emitir_cookie(usuario, portal.senha)
    return 200, {
        "ok": True,
        "token": token,
        "usuario": {
            "email": usuario.get("email") or "",
            "nome": usuario.get("nome") or "",
            "documento": usuario.get("documento") or "",
            "perfil": usuario.get("perfil") or "",
            "trocar_no_acesso": bool(usuario.get("trocar_no_acesso")),
        },
        "api": {
            "dados": "/api/mobile/dados",
            "stive": "/api/mobile/stive",
            "custos": "/api/mobile/custos",
            "saude": "/api/mobile/saude",
        },
    }


def dados(portal, sessao: dict, dados_json: Callable) -> tuple[int, dict]:
    import cadastro

    documento = sessao.get("documento") or ""
    if not cadastro.pode_ver_analise(documento):
        return 403, {"ok": False, "erro": "Sem permissão para ver a análise."}
    payload = dict(dados_json(portal))
    payload["ok"] = True
    payload["usuario"] = {
        "email": sessao.get("email") or "",
        "nome": sessao.get("nome") or "",
        "documento": documento,
        "perfil": sessao.get("perfil") or "",
    }
    return 200, payload


def stive(portal, sessao: dict, pergunta: str, resumo: dict | None = None) -> tuple[int, dict]:
    from agente.stive import responder
    import cadastro
    from custos.estimativa import registrar_envio

    if not cadastro.pode_ver_analise(sessao.get("documento") or ""):
        return 403, {"ok": False, "erro": "Sem permissão."}
    texto = str(pergunta or "").strip()
    if not texto:
        return 400, {"ok": False, "erro": "Informe a pergunta."}
    documento = sessao.get("documento") or ""
    base = resumo if isinstance(resumo, dict) else portal.resumo()
    try:
        saida = responder(
            documento,
            texto,
            base,
            email=sessao.get("email") or "",
            perfil=sessao.get("perfil") or "",
        )
    except ValueError as exc:
        return 200, {"ok": True, "fala": str(exc), "visual": {}}
    except Exception:
        return 500, {"ok": False, "erro": "A base respondeu com erro. Tente de novo em instantes."}
    try:
        registrar_envio("openai", "out", unidades=1.0, detalhe="stive-mobile", documento=documento)
    except Exception:
        pass
    return 200, {"ok": True, "fala": (saida or {}).get("fala") or "", "visual": (saida or {}).get("visual") or {}}


def custos(sessao: dict) -> tuple[int, dict]:
    from db import custos as ledger

    documento = sessao.get("documento") or ""
    try:
        resumo = ledger.resumo_mensal(documento)
    except Exception as exc:
        return 200, {"ok": True, "disponivel": False, "erro": str(exc), "itens": [], "total_usd": 0}
    return 200, {"ok": True, "disponivel": True, **resumo}


def saude() -> dict:
    from db.conexao import disponivel

    return {
        "ok": True,
        "servico": "c4istar-mobile",
        "postgres": disponivel(),
        "modelo": "borda",
        "nota": "Inferência YOLO fica no PC do cliente; o app só consome API.",
    }
