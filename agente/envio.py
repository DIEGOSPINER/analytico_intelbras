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
    return bool(_limpo("EMAIL_DESTINO") and _limpo("SMTP_USUARIO") and _limpo("SMTP_SENHA"))


def whatsapp_configurado() -> bool:
    ativo = _limpo("WHATSAPP_ATIVO").lower() in ("1", "true", "sim", "yes")
    return ativo and bool(_limpo("WHATSAPP_DESTINO") and _limpo("WHATSAPP_APIKEY"))


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
    return True


def enviar_whatsapp(texto: str) -> bool:
    destino = "".join(caractere for caractere in _limpo("WHATSAPP_DESTINO") if caractere.isdigit())
    apikey = _limpo("WHATSAPP_APIKEY")
    if not (destino and apikey):
        print("WhatsApp não enviado. Preencha WHATSAPP_APIKEY no .env.")
        return False
    consulta = urllib.parse.urlencode({
        "phone": destino,
        "text": (texto or "")[:1200],
        "apikey": apikey,
    })
    url = f"https://api.callmebot.com/whatsapp.php?{consulta}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resposta:
            corpo = resposta.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detalhe = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"WhatsApp não enviado: HTTP {exc.code}: {detalhe}")
        return False
    except urllib.error.URLError as exc:
        print(f"WhatsApp não enviado: {exc.reason}")
        return False
    if "error" in corpo.lower() and "message sent" not in corpo.lower():
        print(f"WhatsApp não enviado: {corpo[:300]}")
        return False
    print(f"WhatsApp enviado para {destino}.")
    return True
