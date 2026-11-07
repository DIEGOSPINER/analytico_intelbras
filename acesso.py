"""Usuários do navegador.

Cada e-mail entra com a própria senha e fica preso a um CPF ou CNPJ.
A senha da instalação (WEB_SENHA) só autoriza o primeiro usuário.
O cookie guarda o e-mail e o documento, assinados, sem a senha.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path


ARQUIVO_USUARIOS = Path("usuarios.json")
_RODADAS = 200_000
_VALIDADE_SEG = 30 * 24 * 3600
_FALHAS = {}
_LIMITE_FALHAS = 8
_BLOQUEIO_SEG = 300


def _digitos(valor) -> str:
    return "".join(caractere for caractere in str(valor or "") if caractere.isdigit())


def _ler() -> dict:
    if not ARQUIVO_USUARIOS.exists():
        return {"usuarios": []}
    try:
        bruto = json.loads(ARQUIVO_USUARIOS.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"usuarios.json inválido: {exc}") from exc
    if isinstance(bruto, dict):
        return {"usuarios": list(bruto.get("usuarios") or [])}
    raise ValueError("usuarios.json deve conter a chave usuarios.")


def _gravar(dados: dict):
    ARQUIVO_USUARIOS.write_text(
        json.dumps({"usuarios": dados.get("usuarios") or []}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def listar() -> list[dict]:
    return _ler()["usuarios"]


def email_valido(valor: str) -> bool:
    texto = str(valor or "").strip().lower()
    if " " in texto or texto.count("@") != 1:
        return False
    nome, _, dominio = texto.partition("@")
    return bool(nome and "." in dominio and not dominio.startswith(".") and not dominio.endswith("."))


def gerar_hash(senha: str) -> str:
    sal = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(sal), _RODADAS)
    return f"pbkdf2_sha256${_RODADAS}${sal}${digest.hex()}"


def verificar_senha(senha: str, armazenada: str) -> bool:
    try:
        algo, rodadas, sal, digest = str(armazenada or "").split("$")
        if algo != "pbkdf2_sha256":
            return False
        calculado = hashlib.pbkdf2_hmac(
            "sha256", senha.encode("utf-8"), bytes.fromhex(sal), int(rodadas)
        )
        return hmac.compare_digest(calculado.hex(), digest)
    except (ValueError, TypeError):
        return False


def _marca(senha_hash: str) -> str:
    return hashlib.sha256(str(senha_hash or "").encode("utf-8")).hexdigest()[:16]


def _por_email(email: str) -> dict | None:
    procurado = str(email or "").strip().lower()
    for usuario in listar():
        if str(usuario.get("email") or "").strip().lower() == procurado:
            return usuario
    return None


def _exigir_senha(senha: str, confirmacao: str):
    if senha != confirmacao:
        raise ValueError("A confirmação da senha não confere.")
    if len(senha) < 8:
        raise ValueError("A senha nova precisa ter pelo menos 8 caracteres.")


def perfil_de(documento: str) -> str:
    from cadastro import DOCUMENTO_ADMIN

    if _digitos(documento) == _digitos(DOCUMENTO_ADMIN):
        return "administrador"
    return "cliente"


def _publico(usuario: dict) -> dict:
    return {
        "email": usuario.get("email") or "",
        "nome": usuario.get("nome") or "",
        "documento": usuario.get("documento") or "",
        "perfil": perfil_de(usuario.get("documento") or ""),
        "trocar_no_acesso": bool(usuario.get("trocar_no_acesso")),
    }


def criar_primeiro(chave_instalacao: str, segredo: str, nome: str, email: str, senha: str, confirmacao: str, documento: str) -> dict:
    if listar():
        raise ValueError("Já existe usuário. Entre e crie os próximos pela conta.")
    if not hmac.compare_digest(str(chave_instalacao or "").encode("utf-8"), str(segredo or "").encode("utf-8")):
        raise ValueError("A senha da instalação não confere.")
    from cadastro import documento_valido, vincular_documento_local

    digitos = _digitos(documento)
    if not documento_valido(digitos):
        raise ValueError("Informe um CPF ou CNPJ válido.")
    if not email_valido(email):
        raise ValueError("Informe um e-mail válido.")
    _exigir_senha(senha, confirmacao)
    cliente = vincular_documento_local(digitos, nome, email)
    usuario = {
        "email": email.strip().lower(),
        "nome": (nome or cliente.get("nome") or "").strip(),
        "documento": digitos,
        "senha_hash": gerar_hash(senha),
    }
    _gravar({"usuarios": [usuario]})
    return _publico(usuario)


def criar_usuario(documento: str, nome: str, email: str, senha: str, confirmacao: str) -> dict:
    from cadastro import cliente_por_documento

    if cliente_por_documento(documento) is None:
        raise ValueError("Cadastre o cliente deste CPF antes de criar outro usuário.")
    if not email_valido(email):
        raise ValueError("Informe um e-mail válido.")
    _exigir_senha(senha, confirmacao)
    dados = _ler()
    if _por_email(email):
        raise ValueError("Este e-mail já está em uso.")
    usuario = {
        "email": email.strip().lower(),
        "nome": (nome or "").strip(),
        "documento": _digitos(documento),
        "senha_hash": gerar_hash(senha),
    }
    dados["usuarios"].append(usuario)
    _gravar(dados)
    return _publico(usuario)


def criar_convite(documento: str, nome: str, email: str, senha: str) -> dict:
    from cadastro import cliente_por_documento

    if cliente_por_documento(documento) is None:
        raise ValueError("Cadastre o cliente deste CPF antes de criar o acesso.")
    if not email_valido(email):
        raise ValueError("Informe um e-mail válido.")
    if len(senha) < 8:
        raise ValueError("A senha provisória precisa ter pelo menos 8 caracteres.")
    dados = _ler()
    if _por_email(email):
        raise ValueError("Este e-mail já está em uso.")
    usuario = {
        "email": email.strip().lower(),
        "nome": (nome or "").strip(),
        "documento": _digitos(documento),
        "senha_hash": gerar_hash(senha),
        "trocar_no_acesso": True,
    }
    dados["usuarios"].append(usuario)
    _gravar(dados)
    return _publico(usuario)


def remover_por_documento(documento: str):
    digitos = _digitos(documento)
    dados = _ler()
    dados["usuarios"] = [
        item for item in dados["usuarios"]
        if _digitos(item.get("documento")) != digitos
    ]
    _gravar(dados)


def autenticar(email: str, senha: str) -> dict:
    chave = str(email or "").strip().lower()
    agora = time.time()
    falhas = _FALHAS.get(chave)
    if falhas and falhas["n"] >= _LIMITE_FALHAS and agora - falhas["quando"] < _BLOQUEIO_SEG:
        raise ValueError("Muitas tentativas. Espere alguns minutos e tente de novo.")
    usuario = _por_email(chave)
    hash_falso = "pbkdf2_sha256$1$00$00"
    confere = verificar_senha(senha, usuario.get("senha_hash") if usuario else hash_falso)
    if usuario is None or not confere:
        atual = _FALHAS.get(chave) or {"n": 0, "quando": agora}
        if agora - atual["quando"] > _BLOQUEIO_SEG:
            atual = {"n": 0, "quando": agora}
        atual["n"] += 1
        atual["quando"] = agora
        _FALHAS[chave] = atual
        raise ValueError("E-mail ou senha não conferem.")
    _FALHAS.pop(chave, None)
    return _publico(usuario) | {"marca": _marca(usuario.get("senha_hash"))}


def trocar_senha(email: str, atual: str, nova: str, confirmacao: str) -> dict:
    dados = _ler()
    usuario = None
    for item in dados["usuarios"]:
        if str(item.get("email") or "").lower() == str(email or "").strip().lower():
            usuario = item
            break
    if usuario is None or not verificar_senha(atual, usuario.get("senha_hash") or ""):
        raise ValueError("A senha atual não confere.")
    _exigir_senha(nova, confirmacao)
    usuario["senha_hash"] = gerar_hash(nova)
    usuario["trocar_no_acesso"] = False
    _gravar(dados)
    return _publico(usuario) | {"marca": _marca(usuario["senha_hash"])}


def mover_documento(antigo: str, novo: str):
    antigo_d, novo_d = _digitos(antigo), _digitos(novo)
    if not antigo_d or antigo_d == novo_d:
        return
    dados = _ler()
    for usuario in dados["usuarios"]:
        if _digitos(usuario.get("documento")) == antigo_d:
            usuario["documento"] = novo_d
    _gravar(dados)


def da_conta(documento: str) -> list[dict]:
    digitos = _digitos(documento)
    return [
        _publico(usuario)
        for usuario in listar()
        if _digitos(usuario.get("documento")) == digitos
    ]


def emitir_cookie(usuario: dict, segredo: str) -> str:
    corpo = {
        "email": usuario["email"],
        "documento": _digitos(usuario["documento"]),
        "marca": usuario.get("marca") or "",
        "exp": int(time.time()) + _VALIDADE_SEG,
        "csrf": secrets.token_hex(16),
    }
    payload = base64.urlsafe_b64encode(
        json.dumps(corpo, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    assinatura = hmac.new(str(segredo).encode("utf-8"), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{assinatura}"


def ler_cookie(valor: str, segredo: str) -> dict | None:
    payload, separador, assinatura = str(valor or "").partition(".")
    if not payload or not separador or not assinatura:
        return None
    esperada = hmac.new(str(segredo).encode("utf-8"), payload.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(esperada, assinatura):
        return None
    try:
        bruto = base64.urlsafe_b64decode(payload.encode("ascii") + b"===")
        corpo = json.loads(bruto.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(corpo, dict) or int(corpo.get("exp") or 0) < time.time():
        return None
    usuario = _por_email(corpo.get("email") or "")
    if usuario is None:
        return None
    if _digitos(usuario.get("documento")) != _digitos(corpo.get("documento")):
        return None
    if _marca(usuario.get("senha_hash")) != str(corpo.get("marca") or ""):
        return None
    corpo["nome"] = usuario.get("nome") or ""
    corpo["perfil"] = perfil_de(usuario.get("documento") or "")
    corpo["trocar_no_acesso"] = bool(usuario.get("trocar_no_acesso"))
    return corpo
