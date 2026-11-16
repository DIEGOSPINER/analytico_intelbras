"""Grupos de segurança de vizinhos: compartilhamento de câmeras e alertas entre membros."""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

ARQUIVO = Path("grupos_seguranca.json")
_TRAVA = threading.RLock()


def _agora() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _digitos(valor: str) -> str:
    return "".join(c for c in str(valor or "") if c.isdigit())


def _ler() -> dict:
    if not ARQUIVO.exists():
        return {"grupos": []}
    try:
        bruto = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"grupos": []}
    if not isinstance(bruto, dict):
        return {"grupos": []}
    bruto.setdefault("grupos", [])
    return bruto


def _gravar(bruto: dict) -> None:
    ARQUIVO.write_text(json.dumps(bruto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _nome_camera(documento: str, camera_id: str) -> str:
    from cadastro import cliente_por_documento

    cli = cliente_por_documento(documento) or {}
    ident = str(camera_id or "").strip()
    for cam in cli.get("cameras") or []:
        if not isinstance(cam, dict) or cam.get("ativa") is False:
            continue
        if str(cam.get("id") or "").strip() == ident or str(cam.get("nome") or "").strip() == ident:
            return str(cam.get("nome") or "").strip()
    return ""


def criar_grupo(documento: str, nome: str, *, descricao: str = "", alertas=None) -> dict:
    digitos = _digitos(documento)
    nome_limpo = " ".join(str(nome or "").split())
    if not digitos:
        raise ValueError("Informe a conta criadora.")
    if len(nome_limpo) < 3:
        raise ValueError("Informe um nome com pelo menos 3 letras para o grupo.")
    from config_alertas import normalizar_alertas_grupo

    grupo = {
        "id": f"g_{uuid.uuid4().hex[:10]}",
        "nome": nome_limpo,
        "descricao": " ".join(str(descricao or "").split())[:240],
        "criador": digitos,
        "quando": _agora(),
        "membros": [digitos],
        "cameras": [],
        "alertas": normalizar_alertas_grupo(alertas),
    }
    with _TRAVA:
        bruto = _ler()
        bruto["grupos"].append(grupo)
        bruto["grupos"] = bruto["grupos"][-500:]
        _gravar(bruto)
    return grupo


def listar_grupos(documento: str) -> list[dict]:
    digitos = _digitos(documento)
    with _TRAVA:
        bruto = _ler()
        grupos = list(bruto.get("grupos") or [])
    saida = []
    for g in grupos:
        membros = [_digitos(m) for m in (g.get("membros") or [])]
        if digitos and digitos not in membros:
            continue
        saida.append(_publico(g))
    saida.sort(key=lambda item: (item.get("nome") or "").casefold())
    return saida


def obter_grupo(grupo_id: str) -> dict | None:
    ident = str(grupo_id or "").strip()
    with _TRAVA:
        for g in _ler().get("grupos") or []:
            if str(g.get("id") or "") == ident:
                return dict(g)
    return None


def _publico(grupo: dict) -> dict:
    from cadastro import cliente_por_documento

    membros = []
    for doc in grupo.get("membros") or []:
        digitos = _digitos(doc)
        cli = cliente_por_documento(digitos) or {}
        membros.append({
            "documento": digitos,
            "nome": str(cli.get("nome") or digitos),
            "foto_face_id": str(cli.get("foto_face_id") or "").strip().upper(),
        })
    cameras = []
    for item in grupo.get("cameras") or []:
        if not isinstance(item, dict):
            continue
        doc = _digitos(item.get("documento"))
        cam_id = str(item.get("camera_id") or "").strip()
        nome = _nome_camera(doc, cam_id)
        if not nome:
            continue
        cameras.append({
            "documento": doc,
            "camera_id": cam_id,
            "nome": nome,
            "rotulo": f"{nome} - grupo de vizinhos",
        })
    from config_alertas import alertas_padrao_grupo, normalizar_alertas_grupo

    alertas = grupo.get("alertas")
    if not isinstance(alertas, list) or not alertas:
        alertas = alertas_padrao_grupo()
    else:
        alertas = normalizar_alertas_grupo(alertas)
    return {
        "id": grupo.get("id") or "",
        "nome": grupo.get("nome") or "",
        "descricao": grupo.get("descricao") or "",
        "criador": _digitos(grupo.get("criador")),
        "quando": grupo.get("quando") or "",
        "membros": membros,
        "cameras": cameras,
        "alertas": alertas,
        "total_membros": len(membros),
        "total_cameras": len(cameras),
    }


def adicionar_membro(grupo_id: str, documento_ator: str, documento_membro: str) -> dict:
    """Só criador ou membro pode convidar vizinho já aceito (validado na UI)."""
    ator = _digitos(documento_ator)
    membro = _digitos(documento_membro)
    if not ator or not membro:
        raise ValueError("Informe as contas.")
    with _TRAVA:
        bruto = _ler()
        grupo = None
        for g in bruto.get("grupos") or []:
            if str(g.get("id") or "") == str(grupo_id or "").strip():
                grupo = g
                break
        if not grupo:
            raise ValueError("Grupo não encontrado.")
        membros = [_digitos(m) for m in (grupo.get("membros") or [])]
        if ator not in membros:
            raise ValueError("Só membros do grupo podem adicionar pessoas.")
        if membro in membros:
            raise ValueError("Esta pessoa já está no grupo.")
        membros.append(membro)
        grupo["membros"] = membros
        grupo["atualizado"] = _agora()
        _gravar(bruto)
        return _publico(grupo)


def remover_membro(grupo_id: str, documento_ator: str, documento_membro: str) -> dict:
    ator = _digitos(documento_ator)
    membro = _digitos(documento_membro)
    with _TRAVA:
        bruto = _ler()
        grupo = None
        for g in bruto.get("grupos") or []:
            if str(g.get("id") or "") == str(grupo_id or "").strip():
                grupo = g
                break
        if not grupo:
            raise ValueError("Grupo não encontrado.")
        membros = [_digitos(m) for m in (grupo.get("membros") or [])]
        criador = _digitos(grupo.get("criador"))
        if ator != criador and ator != membro:
            raise ValueError("Só o criador ou o próprio membro pode sair/remover.")
        if membro == criador:
            raise ValueError("O criador não pode ser removido. Exclua o grupo se precisar.")
        if membro not in membros:
            raise ValueError("Membro não encontrado.")
        grupo["membros"] = [m for m in membros if m != membro]
        # Remove câmeras do membro removido.
        grupo["cameras"] = [
            c for c in (grupo.get("cameras") or [])
            if _digitos((c or {}).get("documento")) != membro
        ]
        grupo["atualizado"] = _agora()
        _gravar(bruto)
        return _publico(grupo)


def definir_alertas(grupo_id: str, documento: str, alertas) -> dict:
    """Atualiza quais tipos de alerta o grupo compartilha entre membros."""
    from config_alertas import normalizar_alertas_grupo

    digitos = _digitos(documento)
    with _TRAVA:
        bruto = _ler()
        grupo = None
        for g in bruto.get("grupos") or []:
            if str(g.get("id") or "") == str(grupo_id or "").strip():
                grupo = g
                break
        if not grupo:
            raise ValueError("Grupo não encontrado.")
        membros = [_digitos(m) for m in (grupo.get("membros") or [])]
        if digitos not in membros:
            raise ValueError("Só membros podem configurar alertas do grupo.")
        grupo["alertas"] = normalizar_alertas_grupo(alertas)
        grupo["atualizado"] = _agora()
        _gravar(bruto)
        return _publico(grupo)


def grupo_compartilha_alerta(grupo: dict, tipo: str) -> bool:
    from config_alertas import alertas_padrao_grupo

    chave = str(tipo or "").strip()
    lista = grupo.get("alertas")
    if not isinstance(lista, list) or not lista:
        lista = alertas_padrao_grupo()
    return chave in set(lista)


def compartilhar_camera(grupo_id: str, documento: str, camera_id: str) -> dict:
    digitos = _digitos(documento)
    cam_id = str(camera_id or "").strip()
    nome = _nome_camera(digitos, cam_id)
    if not nome:
        raise ValueError("Escolha uma câmera ativa da sua conta.")
    with _TRAVA:
        bruto = _ler()
        grupo = None
        for g in bruto.get("grupos") or []:
            if str(g.get("id") or "") == str(grupo_id or "").strip():
                grupo = g
                break
        if not grupo:
            raise ValueError("Grupo não encontrado.")
        membros = [_digitos(m) for m in (grupo.get("membros") or [])]
        if digitos not in membros:
            raise ValueError("Só membros podem compartilhar câmeras no grupo.")
        cameras = [
            c for c in (grupo.get("cameras") or [])
            if isinstance(c, dict)
        ]
        ja = any(
            _digitos(c.get("documento")) == digitos and str(c.get("camera_id") or "") == cam_id
            for c in cameras
        )
        if not ja:
            cameras.append({"documento": digitos, "camera_id": cam_id})
        grupo["cameras"] = cameras
        grupo["atualizado"] = _agora()
        _gravar(bruto)
        return _publico(grupo)


def remover_camera(grupo_id: str, documento: str, camera_id: str) -> dict:
    digitos = _digitos(documento)
    cam_id = str(camera_id or "").strip()
    with _TRAVA:
        bruto = _ler()
        grupo = None
        for g in bruto.get("grupos") or []:
            if str(g.get("id") or "") == str(grupo_id or "").strip():
                grupo = g
                break
        if not grupo:
            raise ValueError("Grupo não encontrado.")
        membros = [_digitos(m) for m in (grupo.get("membros") or [])]
        criador = _digitos(grupo.get("criador"))
        if digitos not in membros:
            raise ValueError("Só membros podem gerir câmeras do grupo.")
        novas = []
        for c in grupo.get("cameras") or []:
            if not isinstance(c, dict):
                continue
            dono = _digitos(c.get("documento"))
            cid = str(c.get("camera_id") or "")
            if cid == cam_id and (dono == digitos or digitos == criador):
                continue
            novas.append(c)
        grupo["cameras"] = novas
        grupo["atualizado"] = _agora()
        _gravar(bruto)
        return _publico(grupo)


def excluir_grupo(grupo_id: str, documento: str) -> None:
    digitos = _digitos(documento)
    with _TRAVA:
        bruto = _ler()
        restantes = []
        achou = False
        for g in bruto.get("grupos") or []:
            if str(g.get("id") or "") != str(grupo_id or "").strip():
                restantes.append(g)
                continue
            if _digitos(g.get("criador")) != digitos:
                raise ValueError("Só o criador pode excluir o grupo.")
            achou = True
        if not achou:
            raise ValueError("Grupo não encontrado.")
        bruto["grupos"] = restantes
        _gravar(bruto)


def nomes_cameras_compartilhadas(documento: str) -> set[str]:
    """Nomes de câmeras que o CPF enxerga via grupos de segurança."""
    return set(rotulos_cameras_grupo(documento).keys())


def rotulos_cameras_grupo(documento: str) -> dict[str, str]:
    """Mapa nome_original -> 'Nome - grupo de vizinhos' para câmeras só vistas via grupo.

    Câmeras próprias do documento não entram (para o dono o nome fica limpo).
    """
    digitos = _digitos(documento)
    if not digitos:
        return {}
    from cadastro import nomes_cameras_conta

    proprias = {n.casefold() for n in nomes_cameras_conta(digitos)}
    saida: dict[str, str] = {}
    with _TRAVA:
        grupos = list(_ler().get("grupos") or [])
    for g in grupos:
        membros = {_digitos(m) for m in (g.get("membros") or [])}
        if digitos not in membros:
            continue
        for item in g.get("cameras") or []:
            if not isinstance(item, dict):
                continue
            dono = _digitos(item.get("documento"))
            nome = _nome_camera(dono, str(item.get("camera_id") or ""))
            if not nome:
                continue
            if nome.casefold() in proprias and dono == digitos:
                continue
            if nome not in saida:
                saida[nome] = f"{nome} - grupo de vizinhos"
    return saida


def grupos_da_camera(camera_ref: str) -> list[dict]:
    """Grupos que compartilham a câmera (por nome)."""
    alvo = str(camera_ref or "").strip().casefold()
    if not alvo:
        return []
    saida = []
    with _TRAVA:
        grupos = list(_ler().get("grupos") or [])
    for g in grupos:
        for item in g.get("cameras") or []:
            if not isinstance(item, dict):
                continue
            nome = _nome_camera(_digitos(item.get("documento")), str(item.get("camera_id") or ""))
            if nome and nome.casefold() == alvo:
                saida.append({"id": g.get("id") or "", "nome": g.get("nome") or ""})
                break
    return saida


def grupos_visiveis_na_camera(documento: str, camera_ref: str) -> list[dict]:
    """Grupos da câmera dos quais o documento é membro."""
    digitos = _digitos(documento)
    if not digitos:
        return []
    saida = []
    with _TRAVA:
        grupos = list(_ler().get("grupos") or [])
    alvo = str(camera_ref or "").strip().casefold()
    for g in grupos:
        membros = {_digitos(m) for m in (g.get("membros") or [])}
        if digitos not in membros:
            continue
        for item in g.get("cameras") or []:
            if not isinstance(item, dict):
                continue
            nome = _nome_camera(_digitos(item.get("documento")), str(item.get("camera_id") or ""))
            if nome and nome.casefold() == alvo:
                saida.append({"id": g.get("id") or "", "nome": g.get("nome") or ""})
                break
    return saida


def prefixo_alerta(documento: str, camera_ref: str) -> str:
    grupos = grupos_visiveis_na_camera(documento, camera_ref)
    if not grupos:
        return ""
    nomes = ", ".join(g["nome"] for g in grupos if g.get("nome"))
    if not nomes:
        return ""
    return f"Alerta do grupo {nomes}: "


def prefixo_reconhecimento(documento: str, camera_ref: str) -> str:
    grupos = grupos_visiveis_na_camera(documento, camera_ref)
    if not grupos:
        return ""
    nomes = ", ".join(g["nome"] for g in grupos if g.get("nome"))
    if not nomes:
        return ""
    return f"no grupo {nomes}"


def emails_membros_grupos_camera(
    camera_ref: str,
    exceto_documento: str = "",
    tipo_alerta: str = "",
) -> list[str]:
    """E-mails dos membros dos grupos que compartilham a câmera (e o tipo de alerta)."""
    from cadastro import _emails_da_conta, cliente_por_documento
    from config_alertas import ativo as alerta_ativo

    exc = _digitos(exceto_documento)
    emails: list[str] = []
    with _TRAVA:
        grupos = list(_ler().get("grupos") or [])
    alvo = str(camera_ref or "").strip().casefold()
    tipo = str(tipo_alerta or "").strip()
    for g in grupos:
        compartilha = False
        for item in g.get("cameras") or []:
            if not isinstance(item, dict):
                continue
            nome = _nome_camera(_digitos(item.get("documento")), str(item.get("camera_id") or ""))
            if nome and nome.casefold() == alvo:
                compartilha = True
                break
        if not compartilha:
            continue
        if tipo and not grupo_compartilha_alerta(g, tipo):
            continue
        for doc in g.get("membros") or []:
            digitos = _digitos(doc)
            if not digitos or digitos == exc:
                continue
            if tipo and not alerta_ativo(digitos, "alertas_grupo"):
                continue
            if tipo and not alerta_ativo(digitos, tipo):
                continue
            cli = cliente_por_documento(digitos)
            if cli:
                emails.extend(_emails_da_conta(cli))
    # únicos
    vistos = []
    for email in emails:
        texto = str(email or "").strip()
        if texto and texto not in vistos:
            vistos.append(texto)
    return vistos
