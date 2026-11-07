"""Envio do relatório por e-mail e do resumo por WhatsApp."""

from __future__ import annotations

import os
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from pathlib import Path


def _limpo(nome: str) -> str:
    return os.getenv(nome, "").strip()


def email_configurado() -> bool:
    from cadastro import destinatarios

    return bool(destinatarios() and _limpo("SMTP_USUARIO") and _limpo("SMTP_SENHA"))


def whatsapp_configurado() -> bool:
    ativo = _limpo("WHATSAPP_ATIVO").lower() in ("1", "true", "sim", "yes")
    if not ativo:
        return False
    modo = (_limpo("WHATSAPP_MODO") or "callmebot").lower()
    if modo in ("meta", "cloud", "oficial"):
        return bool(_limpo("WHATSAPP_TOKEN") and _limpo("WHATSAPP_PHONE_NUMBER_ID") and _limpo("WHATSAPP_DESTINO"))
    return bool(_limpo("WHATSAPP_DESTINO") and _limpo("WHATSAPP_APIKEY"))


def enviar_email(assunto: str, texto: str, anexo: str = "", destinos=None) -> bool:
    from cadastro import destinatarios

    lista = [item.strip() for item in (destinos or destinatarios()) if str(item).strip()]
    usuario = _limpo("SMTP_USUARIO")
    senha = _limpo("SMTP_SENHA").replace(" ", "")
    if not (lista and usuario and senha):
        print("E-mail não enviado. Preencha SMTP_USUARIO, SMTP_SENHA e o e-mail do cliente.")
        return False
    mensagem = EmailMessage()
    mensagem["Subject"] = assunto
    mensagem["From"] = usuario
    mensagem["To"] = ", ".join(lista)
    mensagem.set_content(texto)
    caminho = Path(anexo) if anexo else None
    if caminho and caminho.exists():
        mensagem.add_attachment(
            caminho.read_bytes(),
            maintype="text",
            subtype="plain",
            filename=caminho.name,
        )
    host = _limpo("SMTP_HOST") or "smtp.gmail.com"
    porta = int(_limpo("SMTP_PORT") or "587")
    try:
        with smtplib.SMTP(host, porta, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(usuario, senha)
            smtp.send_message(mensagem)
    except (smtplib.SMTPException, OSError) as exc:
        print(f"E-mail não enviado: {exc}")
        return False
    print(f"E-mail enviado para {', '.join(lista)}.")
    try:
        from custos.estimativa import registrar_envio

        registrar_envio("email", "out", unidades=float(len(lista)), detalhe=assunto[:120])
    except Exception:
        pass
    return True


def enviar_whatsapp(texto: str) -> bool:
    ativo = _limpo("WHATSAPP_ATIVO").lower() in ("1", "true", "sim", "yes")
    if not ativo:
        print("WhatsApp desligado (WHATSAPP_ATIVO=0).")
        return False
    try:
        from agente.whatsapp_canal import enviar

        ok = enviar(texto or "")
        if ok:
            print("WhatsApp enviado.")
        return ok
    except Exception as exc:
        print(f"WhatsApp não enviado: {exc}")
        return False
