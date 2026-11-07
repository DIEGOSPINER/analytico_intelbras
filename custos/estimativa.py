"""Tarifas configuráveis via .env para estimar custo de e-mail, WhatsApp e OpenAI."""

from __future__ import annotations

import os


def _f(nome: str, padrao: float) -> float:
    bruto = os.getenv(nome, "").strip().replace(",", ".")
    if not bruto:
        return padrao
    try:
        return float(bruto)
    except ValueError:
        return padrao


def usd_email_out() -> float:
    # SMTP próprio costuma ser ~0; use valor simbólico se quiser ratear.
    return _f("EMAIL_USD_MSG_OUT", 0.0)


def usd_whatsapp_out() -> float:
    # Meta Cloud API: template/utilidade varia por país; default conservador BR.
    return _f("WHATSAPP_USD_MSG_OUT", 0.05)


def usd_whatsapp_in() -> float:
    return _f("WHATSAPP_USD_MSG_IN", 0.0)


def usd_openai_1k_tokens() -> float:
    return _f("OPENAI_USD_1K_TOKENS", 0.01)


def estimar(canal: str, direcao: str = "out", unidades: float = 1.0) -> float:
    canal = (canal or "").lower()
    direcao = (direcao or "out").lower()
    u = float(unidades or 1)
    if canal == "email":
        return round(usd_email_out() * u, 6)
    if canal == "whatsapp":
        tarifa = usd_whatsapp_in() if direcao == "in" else usd_whatsapp_out()
        return round(tarifa * u, 6)
    if canal in ("openai", "stive"):
        return round(usd_openai_1k_tokens() * u, 6)
    return 0.0


def registrar_envio(canal: str, direcao: str = "out", unidades: float = 1.0, detalhe: str = "", documento: str = ""):
    from db import custos as ledger

    usd = estimar(canal, direcao, unidades)
    ledger.registrar(canal, direcao, usd, unidades=unidades, detalhe=detalhe, documento=documento)
    return usd
