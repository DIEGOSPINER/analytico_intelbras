"""Canal WhatsApp: CallMeBot (legado) ou Meta Cloud API (Stive bidirecional)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request


def _limpo(nome: str) -> str:
    return os.getenv(nome, "").strip()


def modo() -> str:
    valor = _limpo("WHATSAPP_MODO").lower() or "callmebot"
    if valor in ("meta", "cloud", "oficial"):
        return "meta"
    return "callmebot"


def meta_configurado() -> bool:
    ativo = _limpo("WHATSAPP_ATIVO").lower() in ("1", "true", "sim", "yes")
    return ativo and bool(_limpo("WHATSAPP_TOKEN") and _limpo("WHATSAPP_PHONE_NUMBER_ID"))


def enviar(texto: str, destino: str = "", documento: str = "") -> bool:
    """Envia texto. Destino: DDI+número só dígitos."""
    mensagem = (texto or "")[:4000]
    if not mensagem:
        return False
    if modo() == "meta":
        ok = _enviar_meta(mensagem, destino)
    else:
        ok = _enviar_callmebot(mensagem, destino)
    if ok:
        try:
            from custos.estimativa import registrar_envio

            registrar_envio("whatsapp", "out", unidades=1.0, detalhe="alerta", documento=documento)
        except Exception:
            pass
    return ok


def _enviar_callmebot(texto: str, destino: str = "") -> bool:
    phone = "".join(c for c in (destino or _limpo("WHATSAPP_DESTINO")) if c.isdigit())
    apikey = _limpo("WHATSAPP_APIKEY")
    if not (phone and apikey):
        print("WhatsApp CallMeBot: preencha WHATSAPP_DESTINO e WHATSAPP_APIKEY.")
        return False
    consulta = urllib.parse.urlencode({"phone": phone, "text": texto[:1200], "apikey": apikey})
    url = f"https://api.callmebot.com/whatsapp.php?{consulta}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            resp.read()
    except (urllib.error.URLError, OSError) as exc:
        print(f"WhatsApp CallMeBot falhou: {exc}")
        return False
    return True


def _enviar_meta(texto: str, destino: str = "") -> bool:
    token = _limpo("WHATSAPP_TOKEN")
    phone_id = _limpo("WHATSAPP_PHONE_NUMBER_ID")
    to = "".join(c for c in (destino or _limpo("WHATSAPP_DESTINO")) if c.isdigit())
    if not (token and phone_id and to):
        print("WhatsApp Meta: preencha WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID e destino.")
        return False
    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    corpo = json.dumps({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": texto[:4096]},
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=corpo,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        print(f"WhatsApp Meta HTTP {exc.code}: {exc.read()[:300]}")
        return False
    except (urllib.error.URLError, OSError) as exc:
        print(f"WhatsApp Meta falhou: {exc}")
        return False
    return True


def extrair_mensagens_entrada(payload: dict) -> list[dict]:
    """Normaliza webhook Meta Cloud API → [{de, texto, id, documento?}]."""
    saida = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            contatos = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts") or []}
            for msg in value.get("messages") or []:
                if msg.get("type") != "text":
                    continue
                de = str(msg.get("from") or "")
                saida.append({
                    "de": de,
                    "nome": contatos.get(de) or "",
                    "texto": ((msg.get("text") or {}).get("body") or "").strip(),
                    "id": msg.get("id") or "",
                })
    return saida


def processar_entrada_stive(texto: str, documento: str = "", resumo: dict | None = None) -> str:
    from agente.stive import responder

    try:
        saida = responder(documento or "", texto, resumo or {})
        return (saida or {}).get("fala") or "Recebi sua mensagem."
    except Exception as exc:
        return f"Não consegui consultar a base agora ({exc})."
