"""Rede de vizinhos: busca por nome, solicitação com aceite e chat com foto."""

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
import uuid
from pathlib import Path

ARQUIVO = Path("vizinhos_chat.json")
DIR_FOTOS = Path("evidencias") / "vizinhos"
_TRAVA = threading.RLock()


def _agora() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _digitos(valor: str) -> str:
    return "".join(c for c in str(valor or "") if c.isdigit())


def _nome_norm(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.casefold().split())


def _chave_par(a: str, b: str) -> str:
    docs = sorted({_digitos(a), _digitos(b)} - {""})
    if len(docs) != 2:
        raise ValueError("Informe duas contas distintas.")
    return f"{docs[0]}|{docs[1]}"


def _ler() -> dict:
    if not ARQUIVO.exists():
        return {"contatos": {}, "chats": {}, "convites": [], "notificacoes": []}
    try:
        bruto = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"contatos": {}, "chats": {}, "convites": [], "notificacoes": []}
    if not isinstance(bruto, dict):
        return {"contatos": {}, "chats": {}, "convites": [], "notificacoes": []}
    bruto.setdefault("contatos", {})
    bruto.setdefault("chats", {})
    bruto.setdefault("convites", [])
    bruto.setdefault("notificacoes", [])
    # Contatos antigos sem status = já aceitos.
    for meta in bruto["contatos"].values():
        if isinstance(meta, dict) and not meta.get("status"):
            meta["status"] = "aceito"
    return bruto


def _notificar(documento: str, tipo: str, texto: str, meta: dict | None = None) -> None:
    digitos = _digitos(documento)
    if not digitos:
        return
    with _TRAVA:
        bruto = _ler()
        bruto.setdefault("notificacoes", []).append({
            "id": uuid.uuid4().hex[:12],
            "para": digitos,
            "tipo": str(tipo or "info"),
            "texto": str(texto or "")[:280],
            "quando": _agora(),
            "lida": False,
            **dict(meta or {}),
        })
        bruto["notificacoes"] = bruto["notificacoes"][-300:]
        _gravar(bruto)


def listar_alertas(documento: str) -> list[dict]:
    """Pendências + notificações para selo/nav e tela."""
    eu = _digitos(documento)
    if not eu:
        return []
    saida = []
    sols = listar_solicitacoes(eu)
    for item in sols.get("recebidas") or []:
        saida.append({
            "id": f"sol:{item.get('documento')}",
            "tipo": "solicitacao",
            "texto": f"{item.get('nome')} quer te adicionar como vizinho",
            "documento": item.get("documento"),
            "quando": item.get("quando") or "",
        })
    with _TRAVA:
        bruto = _ler()
        notas = list(bruto.get("notificacoes") or [])
    for nota in notas:
        if str(nota.get("para") or "") != eu or nota.get("lida") is True:
            continue
        saida.append({
            "id": f"nota:{nota.get('id')}",
            "tipo": nota.get("tipo") or "info",
            "texto": nota.get("texto") or "",
            "documento": nota.get("de") or "",
            "quando": nota.get("quando") or "",
        })
    return saida


def marcar_alertas_vistos(documento: str) -> None:
    eu = _digitos(documento)
    with _TRAVA:
        bruto = _ler()
        for nota in bruto.get("notificacoes") or []:
            if str(nota.get("para") or "") == eu:
                nota["lida"] = True
        _gravar(bruto)


def _gravar(bruto: dict) -> None:
    ARQUIVO.write_text(json.dumps(bruto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resumo_conta(cliente: dict) -> dict:
    digitos = _digitos(cliente.get("documento"))
    item = {
        "documento": digitos,
        "nome": str(cliente.get("nome") or digitos),
        "email": str(cliente.get("email") or ""),
        "foto_face_id": str(cliente.get("foto_face_id") or "").strip().upper(),
        "bairro": "",
        "rua": "",
    }
    for cam in cliente.get("cameras") or []:
        if not isinstance(cam, dict) or cam.get("ativa") is False:
            continue
        if not item["rua"] and cam.get("rua"):
            item["rua"] = str(cam.get("rua") or "")
        if not item["bairro"] and cam.get("bairro"):
            item["bairro"] = str(cam.get("bairro") or "")
    return item


def buscar_contas(consulta: str, exceto_documento: str = "", limite: int = 12) -> list[dict]:
    """Busca contas ativas na plataforma pelo nome (ou trecho do documento/e-mail)."""
    from cadastro import listar_clientes

    q = _nome_norm(consulta)
    if len(q) < 2:
        return []
    digitos_q = _digitos(consulta)
    exc = _digitos(exceto_documento)
    saida = []
    for cliente in listar_clientes():
        if cliente.get("ativo") is False:
            continue
        digitos = _digitos(cliente.get("documento"))
        if not digitos or digitos == exc:
            continue
        nome = _nome_norm(cliente.get("nome") or "")
        email = _nome_norm(cliente.get("email") or "")
        if q in nome or q in email or (digitos_q and digitos_q in digitos):
            saida.append(_resumo_conta(cliente))
    saida.sort(key=lambda item: (item.get("nome") or "").casefold())
    return saida[: max(1, int(limite or 12))]


def _gravar_vinculo_grafo(eu: str, outro: str, vinculo: str, *, nome: str = "", email: str = "") -> None:
    vinculo = str(vinculo or "").strip().lower()
    if not vinculo:
        return
    try:
        from cadastro import cliente_por_documento
        from grafo_relacoes import TIPOS_VINCULO, VINCULOS_STIVE, relacionar_usuarios

        if vinculo not in TIPOS_VINCULO and vinculo not in VINCULOS_STIVE:
            vinculo = "vizinho"
        if vinculo in {"medida_protege", "proprio", "monitora", "mesmo_individuo"}:
            vinculo = "vizinho"
        cli_eu = cliente_por_documento(eu) or {}
        cli_outro = cliente_por_documento(outro) or {}
        relacionar_usuarios(
            eu,
            outro,
            vinculo if vinculo in TIPOS_VINCULO else "vizinho",
            nome_origem=str(nome or cli_eu.get("nome") or ""),
            email_origem=str(email or cli_eu.get("email") or ""),
            nome_destino=str(cli_outro.get("nome") or ""),
            email_destino=str(cli_outro.get("email") or ""),
            meta={"fonte": "vizinhos_ui"},
            reciproco=True,
        )
    except Exception as exc:
        print(f"Grafo vizinho: {exc}")


def solicitar_vizinho(
    documento: str,
    documento_vizinho: str,
    vinculo: str = "",
    *,
    nome: str = "",
    email: str = "",
    notificar: str = "",
) -> dict:
    """Envia solicitação; a outra conta precisa aceitar. notificar: email|whatsapp|ambos|."""
    eu = _digitos(documento)
    outro = _digitos(documento_vizinho)
    if not eu or not outro or eu == outro:
        raise ValueError("Escolha uma conta da plataforma diferente da sua.")
    from cadastro import cliente_por_documento

    cli_eu = cliente_por_documento(eu)
    cli_outro = cliente_por_documento(outro)
    if cli_outro is None or cli_outro.get("ativo") is False:
        raise ValueError("Não encontrei esta conta ativa na plataforma.")
    vinculo = str(vinculo or "").strip().lower()
    chave = _chave_par(eu, outro)
    with _TRAVA:
        bruto = _ler()
        atual = dict(bruto["contatos"].get(chave) or {})
        status_atual = str(atual.get("status") or ("aceito" if atual else ""))
        if status_atual == "aceito":
            raise ValueError("Vocês já são vizinhos.")
        if status_atual == "pendente" and atual.get("de") == eu:
            raise ValueError("Solicitação já enviada. Aguarde a resposta.")
        if status_atual == "pendente" and atual.get("de") == outro:
            raise ValueError("Esta pessoa já te enviou uma solicitação. Responda em pendências.")
        contato = {
            "a": eu,
            "b": outro,
            "status": "pendente",
            "de": eu,
            "quando": _agora(),
            "atualizado": _agora(),
            "vinculo_por": {
                eu: vinculo,
            },
        }
        bruto["contatos"][chave] = contato
        bruto["chats"].setdefault(chave, [])
        _gravar(bruto)

    avisos = _notificar_solicitacao(
        cli_eu or {},
        cli_outro or {},
        vinculo=vinculo,
        canais=notificar,
    )
    _notificar(
        outro,
        "solicitacao",
        f"{(cli_eu or {}).get('nome') or 'Alguém'} quer te adicionar como vizinho"
        + (f" ({vinculo})" if vinculo else ""),
        meta={"de": eu, "vinculo": vinculo},
    )
    return {
        "chave": chave,
        "documento": outro,
        "nome": str((cli_outro or {}).get("nome") or outro),
        "status": "pendente",
        "vinculo": vinculo,
        "notificacoes": avisos,
    }


def _notificar_solicitacao(cli_eu: dict, cli_outro: dict, *, vinculo: str = "", canais: str = "") -> dict:
    canais = str(canais or "").strip().lower()
    if canais in ("", "nao", "não", "0", "false"):
        return {"email": False, "whatsapp": False}
    nome_eu = str(cli_eu.get("nome") or "Um vizinho")
    nome_outro = str(cli_outro.get("nome") or "")
    vinculo_txt = f" Vínculo sugerido: {vinculo}." if vinculo else ""
    texto = (
        f"{nome_eu} quer te adicionar como vizinho no C4ISTAR MONITOR.{vinculo_txt}\n"
        "Abra a tela Vizinhos e aceite ou recuse a solicitação."
    )
    resultado = {"email": False, "whatsapp": False}
    if canais in ("email", "ambos", "all", "1", "sim"):
        destino = str(cli_outro.get("email") or "").strip()
        if destino:
            try:
                from agente.envio import enviar_email

                resultado["email"] = bool(
                    enviar_email(
                        "Solicitação de vizinho · C4ISTAR MONITOR",
                        texto,
                        destinos=[destino],
                    )
                )
            except Exception as exc:
                print(f"E-mail solicitação vizinho: {exc}")
    if canais in ("whatsapp", "ambos", "all", "1", "sim"):
        telefone = _telefone_cliente(cli_outro)
        if telefone:
            try:
                from agente.whatsapp_canal import enviar

                resultado["whatsapp"] = bool(enviar(texto, destino=telefone, documento=_digitos(cli_outro.get("documento"))))
            except Exception as exc:
                print(f"WhatsApp solicitação vizinho: {exc}")
        resultado["whatsapp_link"] = _link_wa(telefone, texto) if telefone else ""
    return resultado


def _telefone_cliente(cliente: dict) -> str:
    for cam in cliente.get("cameras") or []:
        if not isinstance(cam, dict):
            continue
        for aviso in cam.get("avisos") or []:
            if not isinstance(aviso, dict):
                continue
            digitos = _digitos(
                f"{aviso.get('codigo_pais') or ''}{aviso.get('ddd') or ''}{aviso.get('numero') or ''}{aviso.get('telefone') or ''}"
            )
            if len(digitos) >= 10:
                return digitos
    return ""


def _link_wa(telefone: str, texto: str) -> str:
    phone = _digitos(telefone)
    if not phone:
        return ""
    from urllib.parse import quote

    return f"https://wa.me/{phone}?text={quote((texto or '')[:900])}"


def listar_solicitacoes(documento: str) -> dict:
    """Pendências recebidas e enviadas."""
    eu = _digitos(documento)
    from cadastro import cliente_por_documento

    recebidas, enviadas = [], []
    with _TRAVA:
        bruto = _ler()
        contatos = dict(bruto.get("contatos") or {})
    for chave, meta in contatos.items():
        if meta.get("status") != "pendente":
            continue
        partes = str(chave).split("|")
        if eu not in partes:
            continue
        outro = partes[0] if partes[1] == eu else partes[1]
        cli = cliente_por_documento(outro) or {}
        item = {
            "chave": chave,
            "documento": outro,
            "nome": str(cli.get("nome") or outro),
            "foto_face_id": str(cli.get("foto_face_id") or "").strip().upper(),
            "vinculo": str((meta.get("vinculo_por") or {}).get(meta.get("de") or "") or ""),
            "quando": meta.get("quando") or "",
            "de": meta.get("de") or "",
        }
        if meta.get("de") == eu:
            enviadas.append(item)
        else:
            recebidas.append(item)
    return {"recebidas": recebidas, "enviadas": enviadas}


def responder_solicitacao(
    documento: str,
    documento_vizinho: str,
    aceitar: bool,
    *,
    vinculo: str = "",
    nome: str = "",
    email: str = "",
) -> dict:
    eu = _digitos(documento)
    outro = _digitos(documento_vizinho)
    chave = _chave_par(eu, outro)
    solicitante = ""
    with _TRAVA:
        bruto = _ler()
        meta = dict(bruto["contatos"].get(chave) or {})
        if meta.get("status") != "pendente":
            raise ValueError("Não há solicitação pendente com esta pessoa.")
        if meta.get("de") == eu:
            raise ValueError("Você enviou esta solicitação; aguarde a outra pessoa.")
        solicitante = str(meta.get("de") or outro)
        if aceitar:
            vinculos = dict(meta.get("vinculo_por") or {})
            if vinculo:
                vinculos[eu] = str(vinculo).strip().lower()
            meta["status"] = "aceito"
            meta["vinculo_por"] = vinculos
            meta["aceito_em"] = _agora()
            meta["atualizado"] = _agora()
            bruto["contatos"][chave] = meta
            bruto["chats"].setdefault(chave, [])
            _gravar(bruto)
            vinculo_final = vinculos.get(meta.get("de") or "") or vinculos.get(eu) or "vizinho"
            _gravar_vinculo_grafo(eu, outro, vinculo_final, nome=nome, email=email)
            from cadastro import cliente_por_documento

            cli_eu = cliente_por_documento(eu) or {}
            _notificar(
                solicitante,
                "aceite",
                f"{cli_eu.get('nome') or 'Seu vizinho'} aceitou sua solicitação. Já podem conversar.",
                {"de": eu},
            )
            return {"status": "aceito", "documento": outro, "vinculo": vinculo_final}
        bruto["contatos"].pop(chave, None)
        _gravar(bruto)
    _notificar(solicitante, "recusa", "Sua solicitação de vizinho foi recusada.", {"de": eu})
    return {"status": "recusado", "documento": outro}


def convidar_externo(
    documento: str,
    *,
    nome: str = "",
    email_destino: str = "",
    telefone: str = "",
    canal: str = "email",
    mensagem: str = "",
) -> dict:
    """Convida alguém (com ou sem conta) por e-mail e/ou WhatsApp."""
    eu = _digitos(documento)
    from cadastro import cliente_por_documento

    cli_eu = cliente_por_documento(eu) or {}
    nome_eu = str(cli_eu.get("nome") or "Um vizinho")
    nome_alvo = " ".join(str(nome or "").split()) or "vizinho"
    canal = str(canal or "email").strip().lower()
    email_destino = str(email_destino or "").strip().lower()
    telefone = _digitos(telefone)
    texto = mensagem.strip() or (
        f"{nome_eu} convidou você ({nome_alvo}) para a rede de vizinhos do C4ISTAR MONITOR. "
        "Se já tiver conta, abra Vizinhos e aceite. Se ainda não tiver, peça acesso ao administrador."
    )
    resultado = {"email": False, "whatsapp": False, "whatsapp_link": ""}
    with _TRAVA:
        bruto = _ler()
        bruto.setdefault("convites", []).append({
            "id": uuid.uuid4().hex[:10],
            "de": eu,
            "nome": nome_alvo,
            "email": email_destino,
            "telefone": telefone,
            "canal": canal,
            "quando": _agora(),
        })
        bruto["convites"] = bruto["convites"][-200:]
        _gravar(bruto)
    if canal in ("email", "ambos") and email_destino:
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_destino):
            raise ValueError("Informe um e-mail válido para o convite.")
        try:
            from agente.envio import enviar_email

            resultado["email"] = bool(
                enviar_email(
                    "Convite para vizinhos · C4ISTAR MONITOR",
                    texto,
                    destinos=[email_destino],
                )
            )
        except Exception as exc:
            print(f"Convite e-mail: {exc}")
    if canal in ("whatsapp", "ambos"):
        if not telefone:
            raise ValueError("Informe o WhatsApp (DDI+DDD+número) para o convite.")
        resultado["whatsapp_link"] = _link_wa(telefone, texto)
        try:
            from agente.whatsapp_canal import enviar

            resultado["whatsapp"] = bool(enviar(texto, destino=telefone, documento=eu))
        except Exception as exc:
            print(f"Convite WhatsApp: {exc}")
    if not resultado["email"] and not resultado["whatsapp"] and not resultado["whatsapp_link"]:
        raise ValueError("Não foi possível montar o convite. Informe e-mail e/ou WhatsApp.")
    return resultado


def listar_vizinhos(documento: str) -> list[dict]:
    eu = _digitos(documento)
    if not eu:
        return []
    from cadastro import cliente_por_documento

    with _TRAVA:
        bruto = _ler()
        contatos = dict(bruto.get("contatos") or {})
        chats = dict(bruto.get("chats") or {})
    saida = []
    for chave, meta in contatos.items():
        if meta.get("status") not in (None, "", "aceito"):
            continue
        partes = str(chave).split("|")
        if eu not in partes:
            continue
        outro = partes[0] if partes[1] == eu else partes[1]
        cli = cliente_por_documento(outro) or {}
        msgs = list(chats.get(chave) or [])
        ultima = msgs[-1] if msgs else {}
        saida.append({
            "chave": chave,
            "documento": outro,
            "nome": str(cli.get("nome") or outro),
            "email": str(cli.get("email") or ""),
            "foto_face_id": str(cli.get("foto_face_id") or "").strip().upper(),
            "vinculo": str((meta.get("vinculo_por") or {}).get(eu) or next(iter((meta.get("vinculo_por") or {}).values()), "")),
            "ultima_mensagem": str(ultima.get("texto") or ""),
            "ultima_quando": str(ultima.get("quando") or meta.get("atualizado") or ""),
            "total_mensagens": len(msgs),
            "status": "aceito",
        })
    saida.sort(key=lambda item: item.get("ultima_quando") or "", reverse=True)
    return saida


def historico_chat(documento: str, documento_vizinho: str, limite: int = 200) -> list[dict]:
    eu = _digitos(documento)
    outro = _digitos(documento_vizinho)
    chave = _chave_par(eu, outro)
    with _TRAVA:
        bruto = _ler()
        meta = (bruto.get("contatos") or {}).get(chave) or {}
        if meta.get("status") not in (None, "", "aceito"):
            return []
        msgs = list((bruto.get("chats") or {}).get(chave) or [])
    return msgs[-max(1, int(limite or 200)):]


def enviar_mensagem(
    documento: str,
    documento_vizinho: str,
    texto: str,
    *,
    foto_bytes: bytes | None = None,
    foto_ext: str = ".jpg",
) -> dict:
    eu = _digitos(documento)
    outro = _digitos(documento_vizinho)
    chave = _chave_par(eu, outro)
    texto = str(texto or "").strip()
    foto_rel = ""
    if foto_bytes:
        DIR_FOTOS.mkdir(parents=True, exist_ok=True)
        ext = str(foto_ext or ".jpg").lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            ext = ".jpg"
        nome = f"{uuid.uuid4().hex}{ext}"
        caminho = DIR_FOTOS / nome
        caminho.write_bytes(foto_bytes)
        foto_rel = nome
    if not texto and not foto_rel:
        raise ValueError("Escreva uma mensagem ou envie uma foto.")
    with _TRAVA:
        bruto = _ler()
        meta = (bruto.get("contatos") or {}).get(chave) or {}
        if meta.get("status") not in (None, "", "aceito"):
            raise ValueError("Só é possível conversar depois que o vizinho aceitar.")
        if chave not in (bruto.get("contatos") or {}):
            raise ValueError("Adicione este vizinho antes de conversar.")
        msg = {
            "id": uuid.uuid4().hex[:12],
            "de": eu,
            "texto": texto[:4000],
            "foto": foto_rel,
            "quando": _agora(),
        }
        bruto["chats"].setdefault(chave, []).append(msg)
        bruto["chats"][chave] = bruto["chats"][chave][-500:]
        cont = dict(bruto["contatos"].get(chave) or {})
        cont["atualizado"] = _agora()
        cont["status"] = "aceito"
        bruto["contatos"][chave] = cont
        _gravar(bruto)
    return msg


def caminho_foto(nome: str) -> Path | None:
    base = Path(str(nome or "")).name
    if not base or ".." in base or "/" in base or "\\" in base:
        return None
    caminho = DIR_FOTOS / base
    return caminho if caminho.is_file() else None


# Compatibilidade com chamadas antigas.
def adicionar_vizinho(*args, **kwargs):
    return solicitar_vizinho(*args, **kwargs)
