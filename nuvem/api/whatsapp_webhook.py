"""Webhook WhatsApp (Meta Cloud API) → Stive → resposta + custo."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/v1/whatsapp", tags=["whatsapp"])


def _limpo(nome: str) -> str:
    return os.getenv(nome, "").strip()


@router.get("")
def verificar(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    token = _limpo("WHATSAPP_VERIFY_TOKEN")
    if hub_mode == "subscribe" and token and hub_verify_token == token:
        return int(hub_challenge or "0")
    raise HTTPException(status_code=403, detail="Verify token inválido.")


@router.post("")
async def receber(request: Request):
    import sys
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    if str(raiz) not in sys.path:
        sys.path.insert(0, str(raiz))

    from agente.whatsapp_canal import extrair_mensagens_entrada, enviar, processar_entrada_stive
    from custos.estimativa import registrar_envio

    payload: dict[str, Any] = await request.json()
    mensagens = extrair_mensagens_entrada(payload)
    documento = "".join(c for c in _limpo("CLIENTE_DOCUMENTO") if c.isdigit())
    respondidas = 0
    for msg in mensagens:
        texto = msg.get("texto") or ""
        if not texto:
            continue
        try:
            registrar_envio("whatsapp", "in", unidades=1.0, detalhe="webhook", documento=documento)
        except Exception:
            pass
        fala = processar_entrada_stive(texto, documento=documento, resumo={})
        if enviar(fala, destino=msg.get("de") or "", documento=documento):
            respondidas += 1
            try:
                registrar_envio("openai", "out", unidades=1.0, detalhe="stive-whatsapp", documento=documento)
            except Exception:
                pass
    return {"ok": True, "recebidas": len(mensagens), "respondidas": respondidas}
