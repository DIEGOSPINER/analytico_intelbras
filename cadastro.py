"""Conta do cliente.

Cada CPF ou CNPJ enxerga só o próprio mundo: dados pessoais, câmeras,
pessoas e veículos de interesse, contatos de apoio e relatórios.
O WhatsApp e o aplicativo futuro chamam estas funções depois que a
pessoa se identifica pelo documento. Um cliente não recebe dados de outro.

Pessoa de interesse só entra com uma destas bases, em respeito à LGPD:
mandado judicial, medida protetiva ou acompanhamento de filhos e parentes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


ARQUIVO_CLIENTES = Path("clientes.json")
BASES_LEGAIS = {
    "mandado_judicial": "Mandado judicial",
    "medida_protetiva": "Medida protetiva",
    "acompanhamento_familiar": "Acompanhamento de filhos ou parentes",
}


def _digitos(valor) -> str:
    return "".join(caractere for caractere in str(valor or "") if caractere.isdigit())


def _cpf_valido(digitos: str) -> bool:
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(digitos[i]) * (tamanho + 1 - i) for i in range(tamanho))
        resto = (soma * 10) % 11
        if resto == 10:
            resto = 0
        if resto != int(digitos[tamanho]):
            return False
    return True


def _cnpj_valido(digitos: str) -> bool:
    if len(digitos) != 14 or digitos == digitos[0] * 14:
        return False
    pesos = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    for tamanho in (12, 13):
        soma = sum(int(digitos[i]) * pesos[i] for i in range(tamanho))
        resto = soma % 11
        verificador = 0 if resto < 2 else 11 - resto
        if verificador != int(digitos[tamanho]):
            return False
        pesos = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    return True


def documento_valido(valor) -> bool:
    digitos = _digitos(valor)
    if len(digitos) == 11:
        return _cpf_valido(digitos)
    if len(digitos) == 14:
        return _cnpj_valido(digitos)
    return False


def _ler() -> dict:
    if not ARQUIVO_CLIENTES.exists():
        return {"clientes": []}
    try:
        bruto = json.loads(ARQUIVO_CLIENTES.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"clientes.json inválido: {exc}") from exc
    if isinstance(bruto, list):
        return {"clientes": bruto}
    if isinstance(bruto, dict):
        return {"clientes": list(bruto.get("clientes") or [])}
    raise ValueError("clientes.json deve conter a chave clientes.")


def _gravar(dados: dict):
    ARQUIVO_CLIENTES.write_text(
        json.dumps({"clientes": dados.get("clientes") or []}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _cliente_novo(indice: int) -> dict:
    return {
        "id": f"cli-{indice}",
        "nome": "",
        "rg": "",
        "documento": "",
        "tipo_documento": "",
        "email": "",
        "cameras": [],
        "pessoas": [],
        "veiculos": [],
        "contatos_apoio": [],
    }


def garantir_cliente_local():
    """Cria a conta local a partir de cameras.json e interesse.json, uma vez."""
    if ARQUIVO_CLIENTES.exists():
        return cliente_ativo()
    cliente = _cliente_novo(1)
    cameras = Path("cameras.json")
    if cameras.exists():
        try:
            bruto = json.loads(cameras.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            bruto = {}
        if isinstance(bruto, dict):
            cliente["cameras"] = list(bruto.get("cameras") or [])
        elif isinstance(bruto, list):
            cliente["cameras"] = bruto
    interesse = Path("interesse.json")
    if interesse.exists():
        try:
            bruto = json.loads(interesse.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            bruto = {}
        if isinstance(bruto, dict):
            cliente["pessoas"] = list(bruto.get("pessoas") or [])
            cliente["veiculos"] = list(bruto.get("veiculos") or [])
    _gravar({"clientes": [cliente]})
    print("Conta local criada em clientes.json. O documento do cliente ainda pode ser preenchido.")
    return cliente


def listar_clientes() -> list[dict]:
    return _ler()["clientes"]


def cliente_por_documento(documento: str) -> dict | None:
    procurado = _digitos(documento)
    if not procurado:
        return None
    for cliente in listar_clientes():
        if _digitos(cliente.get("documento")) == procurado:
            return cliente
    return None


def cliente_ativo() -> dict | None:
    """A instalação local usa CLIENTE_DOCUMENTO ou a única conta existente."""
    documento = os.getenv("CLIENTE_DOCUMENTO", "").strip()
    if documento:
        return cliente_por_documento(documento)
    clientes = listar_clientes()
    if len(clientes) == 1:
        return clientes[0]
    return None


def _substituir(cliente: dict):
    dados = _ler()
    clientes = dados["clientes"]
    for indice, atual in enumerate(clientes):
        if atual.get("id") == cliente.get("id"):
            clientes[indice] = cliente
            _gravar(dados)
            return
    raise ValueError("Cliente não encontrado nesta instalação.")


def atualizar_dados_pessoais(documento_atual: str, nome: str, rg: str, documento: str, email: str = ""):
    cliente = cliente_por_documento(documento_atual) if documento_atual else cliente_ativo()
    if cliente is None:
        cliente = _cliente_novo(len(listar_clientes()) + 1)
        dados = _ler()
        dados["clientes"].append(cliente)
        _gravar(dados)
    digitos = _digitos(documento)
    if not documento_valido(digitos):
        raise ValueError("Informe um CPF ou CNPJ válido.")
    outro = cliente_por_documento(digitos)
    if outro and outro.get("id") != cliente.get("id"):
        raise ValueError("Este documento já pertence a outra conta.")
    cliente["nome"] = (nome or "").strip()
    cliente["rg"] = (rg or "").strip()
    cliente["documento"] = digitos
    cliente["tipo_documento"] = "cnpj" if len(digitos) == 14 else "cpf"
    if email:
        cliente["email"] = email.strip()
    _substituir(cliente)
    return cliente


def cadastrar_camera(documento: str, camera: dict):
    cliente = _exigir(documento)
    if not isinstance(camera, dict):
        raise ValueError("A câmera precisa ter marca, modelo e o endereço RTSP ou o host.")
    marca = str(camera.get("marca") or "").strip()
    modelo = str(camera.get("modelo") or "").strip()
    if not marca or not modelo:
        raise ValueError("Informe a marca e o modelo da câmera.")
    if not str(camera.get("url") or camera.get("host") or "").strip():
        raise ValueError("Informe a URL RTSP ou o host da câmera.")
    ident = str(camera.get("id") or f"cam-{len(cliente['cameras']) + 1}").strip()
    registro = dict(camera)
    registro["id"] = ident
    registro["marca"] = marca
    registro["modelo"] = modelo
    cameras = [item for item in cliente["cameras"] if str(item.get("id")) != ident]
    cameras.append(registro)
    cliente["cameras"] = cameras
    _substituir(cliente)
    return registro


def validar_pessoa(pessoa: dict):
    if not isinstance(pessoa, dict):
        raise ValueError("O cadastro da pessoa está incompleto.")
    base = str(pessoa.get("base_legal") or "").strip()
    if base not in BASES_LEGAIS:
        raise ValueError(
            "A pessoa de interesse precisa de base legal: "
            "mandado judicial, medida protetiva ou acompanhamento de filhos e parentes."
        )
    if not str(pessoa.get("referencia") or "").strip():
        raise ValueError(
            "Informe a referência: número do mandado, da medida protetiva ou o parentesco."
        )
    if not str(pessoa.get("nome") or "").strip():
        raise ValueError("Informe o nome da pessoa.")
    if not str(pessoa.get("face_id") or "").strip():
        raise ValueError("Informe o Face_ID reconhecido pelo analítico.")


def cadastrar_pessoa(documento: str, pessoa: dict):
    validar_pessoa(pessoa)
    cliente = _exigir(documento)
    face_id = str(pessoa.get("face_id") or "").strip().upper()
    registro = dict(pessoa)
    registro["face_id"] = face_id
    registro["base_legal"] = str(pessoa.get("base_legal")).strip()
    pessoas = [item for item in cliente["pessoas"] if str(item.get("face_id") or "").upper() != face_id]
    pessoas.append(registro)
    cliente["pessoas"] = pessoas
    _substituir(cliente)
    return registro


def cadastrar_veiculo(documento: str, veiculo: dict):
    if not isinstance(veiculo, dict) or not str(veiculo.get("placa") or "").strip():
        raise ValueError("Informe a placa.")
    cliente = _exigir(documento)
    placa = str(veiculo.get("placa") or "").strip().upper()
    registro = dict(veiculo)
    registro["placa"] = placa
    veiculos = [item for item in cliente["veiculos"] if str(item.get("placa") or "").upper() != placa]
    veiculos.append(registro)
    cliente["veiculos"] = veiculos
    _substituir(cliente)
    return registro


def cadastrar_contato(documento: str, contato: dict):
    if not isinstance(contato, dict):
        raise ValueError("Informe o contato de apoio.")
    email = str(contato.get("email") or "").strip()
    telefone = _digitos(contato.get("telefone"))
    if not email and not telefone:
        raise ValueError("O contato de apoio precisa de e-mail ou telefone.")
    cliente = _exigir(documento)
    registro = {
        "nome": str(contato.get("nome") or "").strip(),
        "email": email,
        "telefone": telefone,
        "recebe_alerta": contato.get("recebe_alerta", True) is not False,
    }
    cliente["contatos_apoio"] = list(cliente.get("contatos_apoio") or []) + [registro]
    _substituir(cliente)
    return registro


def _exigir(documento: str) -> dict:
    cliente = cliente_por_documento(documento) if documento else cliente_ativo()
    if cliente is None:
        raise ValueError("Conta não encontrada para este CPF ou CNPJ.")
    return cliente


def cameras_para_analise() -> list[dict]:
    from cameras import filtrar_ativas, ler_cameras

    garantir_cliente_local()
    cliente = cliente_ativo()
    if cliente is not None and cliente.get("cameras"):
        return filtrar_ativas(cliente["cameras"])
    return ler_cameras()


def interesse_ativo() -> dict:
    from agente.fontes import carregar_interesse

    garantir_cliente_local()
    cliente = cliente_ativo()
    if cliente is None:
        return carregar_interesse()
    return {
        "pessoas": list(cliente.get("pessoas") or []),
        "veiculos": list(cliente.get("veiculos") or []),
    }


def destinatarios(cliente: dict | None = None) -> list[str]:
    cliente = cliente if cliente is not None else cliente_ativo()
    emails = []
    if cliente:
        if str(cliente.get("email") or "").strip():
            emails.append(str(cliente["email"]).strip())
        for contato in cliente.get("contatos_apoio") or []:
            if contato.get("recebe_alerta", True) and str(contato.get("email") or "").strip():
                emails.append(str(contato["email"]).strip())
    if not emails:
        destino = os.getenv("EMAIL_DESTINO", "").strip()
        if destino:
            emails.append(destino)
    vistos = []
    for email in emails:
        if email not in vistos:
            vistos.append(email)
    return vistos


def consultar(documento: str) -> dict:
    """Visão da própria conta. Não inclui outros clientes."""
    cliente = _exigir(documento)
    return {
        "id": cliente.get("id"),
        "nome": cliente.get("nome") or "",
        "rg": cliente.get("rg") or "",
        "documento": cliente.get("documento") or "",
        "tipo_documento": cliente.get("tipo_documento") or "",
        "email": cliente.get("email") or "",
        "cameras": list(cliente.get("cameras") or []),
        "pessoas": list(cliente.get("pessoas") or []),
        "veiculos": list(cliente.get("veiculos") or []),
        "contatos_apoio": list(cliente.get("contatos_apoio") or []),
    }
