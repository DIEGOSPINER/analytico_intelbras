"""Conta do cliente.

Cada CPF ou CNPJ enxerga só o próprio mundo: dados pessoais, câmeras,
pessoas e veículos de interesse, contatos de apoio e relatórios.
O WhatsApp e o aplicativo futuro chamam estas funções depois que a
pessoa se identifica pelo documento. Um cliente não recebe dados de outro.

Pessoa de interesse entra com uma classe: morador, prestador, visitante,
desaparecida, comportamento de risco, mandado, ex-detento ou medida protetiva.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


ARQUIVO_CLIENTES = Path("clientes.json")
BASES_LEGAIS = {
    "morador": "Morador",
    "prestador_servico": "Prestador de serviço",
    "visitante": "Visitante",
    "pessoa_desaparecida": "Pessoa desaparecida",
    "comportamento_suspeito": "Comportamento suspeito ou de risco",
    "mandado": "Pessoa com mandado",
    "ex_detento": "Pessoa ex-detento",
    "medida_protetiva": "Medida protetiva",
    "mandado_judicial": "Mandado judicial",
    "acompanhamento_familiar": "Acompanhamento de filhos ou parentes",
}
MOTIVOS_PESSOA = {
    "comportamento_suspeito": {
        "cleptomania": "Cleptomania",
        "agressivo": "Agressivo",
        "surto_psicotico": "Surto psicótico",
        "ameaca": "Cometeu ameaça",
    },
    "medida_protetiva": {
        "violencia_mulher": "Violência contra a mulher",
        "violencia_geral": "Violência geral",
    },
}
CLASSES_RISCO = {"comportamento_suspeito", "mandado", "ex_detento", "mandado_judicial"}


def classe_pessoa(pessoa: dict) -> str:
    return str((pessoa or {}).get("classe") or (pessoa or {}).get("base_legal") or "").strip()


def pessoa_de_risco(pessoa: dict) -> bool:
    return classe_pessoa(pessoa) in CLASSES_RISCO


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


DOCUMENTO_ADMIN = "02401001581"


def cliente_ativo() -> dict | None:
    """A instalação local usa CLIENTE_DOCUMENTO, a conta do administrador ou a única conta ativa."""
    documento = os.getenv("CLIENTE_DOCUMENTO", "").strip()
    if documento:
        return cliente_por_documento(documento)
    ativos = [item for item in listar_clientes() if item.get("ativo") is not False]
    if len(ativos) == 1:
        return ativos[0]
    administrador = cliente_por_documento(DOCUMENTO_ADMIN)
    if administrador is not None and administrador.get("ativo") is not False:
        return administrador
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


def atualizar_dados_pessoais(documento_atual: str, nome: str, rg: str, documento: str, email: str | None = None):
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
    if email is not None:
        cliente["email"] = str(email).strip()
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
    classe = classe_pessoa(pessoa)
    if classe not in BASES_LEGAIS:
        raise ValueError("Escolha o tipo da pessoa de interesse.")
    motivo = str(pessoa.get("motivo") or "").strip()
    if classe in MOTIVOS_PESSOA and motivo not in MOTIVOS_PESSOA[classe]:
        raise ValueError("Escolha o motivo desta pessoa.")
    if classe in ("mandado", "mandado_judicial", "medida_protetiva") and not str(pessoa.get("referencia") or "").strip():
        raise ValueError("Informe o número do mandado ou da medida protetiva.")
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
    registro["classe"] = classe_pessoa(pessoa)
    registro["base_legal"] = registro["classe"]
    registro["motivo"] = str(pessoa.get("motivo") or "").strip()
    pessoas = [item for item in cliente["pessoas"] if str(item.get("face_id") or "").upper() != face_id]
    pessoas.append(registro)
    cliente["pessoas"] = pessoas
    _substituir(cliente)
    return registro


def remover_pessoa(documento: str, face_id: str):
    cliente = _exigir(documento)
    ident = str(face_id or "").strip().upper()
    if not ident:
        raise ValueError("Informe a pessoa que será excluída.")
    pessoas = [
        item for item in cliente.get("pessoas") or []
        if str(item.get("face_id") or "").upper() != ident
    ]
    if len(pessoas) == len(cliente.get("pessoas") or []):
        raise ValueError("Pessoa não encontrada nesta conta.")
    cliente["pessoas"] = pessoas
    _substituir(cliente)
    interesse = Path("interesse.json")
    if interesse.exists():
        try:
            bruto = json.loads(interesse.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            bruto = {}
        if isinstance(bruto, dict):
            bruto["pessoas"] = [
                item for item in bruto.get("pessoas") or []
                if str(item.get("face_id") or "").upper() != ident
            ]
            interesse.write_text(json.dumps(bruto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ident


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


def _email_valido(valor: str) -> bool:
    texto = str(valor or "").strip().lower()
    if " " in texto or texto.count("@") != 1:
        return False
    nome, _, dominio = texto.partition("@")
    return bool(nome and "." in dominio and not dominio.startswith(".") and not dominio.endswith("."))


def _telefone_partes(codigo_pais, ddd, numero) -> dict:
    pais = _digitos(codigo_pais)
    codigo_ddd = _digitos(ddd)
    local = _digitos(numero)
    if not 1 <= len(pais) <= 4:
        raise ValueError("Informe o código do país, como 55.")
    if not 2 <= len(codigo_ddd) <= 4:
        raise ValueError("Informe o DDD.")
    if not 8 <= len(local) <= 12:
        raise ValueError("Informe o número do telefone.")
    return {
        "codigo_pais": pais,
        "ddd": codigo_ddd,
        "numero": local,
        "telefone": pais + codigo_ddd + local,
    }


def vincular_documento_local(documento: str, nome: str = "", email: str = "") -> dict:
    """Amarra o primeiro acesso à conta que já está nesta máquina."""
    digitos = _digitos(documento)
    if not documento_valido(digitos):
        raise ValueError("Informe um CPF ou CNPJ válido.")
    existente = cliente_por_documento(digitos)
    if existente:
        if email and not str(existente.get("email") or "").strip():
            return atualizar_dados_pessoais(
                digitos,
                existente.get("nome") or nome,
                existente.get("rg") or "",
                digitos,
                email,
            )
        return existente
    clientes = listar_clientes()
    sem_documento = [item for item in clientes if not _digitos(item.get("documento"))]
    if len(clientes) == 1 and sem_documento:
        atual = sem_documento[0]
        return atualizar_dados_pessoais(
            "",
            atual.get("nome") or nome,
            atual.get("rg") or "",
            digitos,
            email or atual.get("email") or "",
        )
    if not clientes:
        return atualizar_dados_pessoais("", nome, "", digitos, email)
    raise ValueError("Este CPF não corresponde à conta desta instalação.")


def salvar_cliente(documento_atual: str, nome: str, rg: str, documento: str, email: str) -> dict:
    if email and not _email_valido(email):
        raise ValueError("Informe um e-mail válido.")
    cliente = atualizar_dados_pessoais(documento_atual, nome, rg, documento, email)
    if _digitos(documento_atual) and _digitos(documento_atual) != cliente["documento"]:
        from acesso import mover_documento

        mover_documento(documento_atual, cliente["documento"])
    return cliente


def _camera_por_id(cliente: dict, ident: str) -> dict | None:
    for camera in cliente.get("cameras") or []:
        if str(camera.get("id")) == str(ident):
            return camera
    return None


def camera_publica(camera: dict) -> dict:
    avisos = []
    for aviso in camera.get("avisos") or []:
        if not isinstance(aviso, dict):
            continue
        avisos.append({
            "codigo_pais": aviso.get("codigo_pais") or "",
            "ddd": aviso.get("ddd") or "",
            "numero": aviso.get("numero") or "",
            "telefone": aviso.get("telefone") or "",
            "email": aviso.get("email") or "",
            "recebe_alerta": aviso.get("recebe_alerta", True) is not False,
            "recebe_relatorio": aviso.get("recebe_relatorio", True) is not False,
        })
    return {
        "id": str(camera.get("id") or ""),
        "nome": str(camera.get("nome") or ""),
        "marca": str(camera.get("marca") or ""),
        "modelo": str(camera.get("modelo") or ""),
        "ativa": camera.get("ativa") is not False,
        "host": str(camera.get("host") or ""),
        "porta": camera.get("porta") if camera.get("porta") not in (None, "") else "",
        "usuario": str(camera.get("usuario") or ""),
        "canal": camera.get("canal") if camera.get("canal") not in (None, "") else "",
        "subtype": camera.get("subtype") if camera.get("subtype") not in (None, "") else "",
        "rua": str(camera.get("rua") or ""),
        "bairro": str(camera.get("bairro") or ""),
        "cidade": str(camera.get("cidade") or ""),
        "latitude": camera.get("latitude") if camera.get("latitude") not in (None, "") else "",
        "longitude": camera.get("longitude") if camera.get("longitude") not in (None, "") else "",
        "tem_acesso": bool(str(camera.get("url") or camera.get("host") or "").strip()),
        "avisos": avisos,
    }


def cameras_publicas(documento: str) -> list[dict]:
    cliente = _exigir(documento)
    return [camera_publica(item) for item in cliente.get("cameras") or [] if isinstance(item, dict)]


def _espelhar_cameras(cliente: dict):
    ativo = cliente_ativo()
    if ativo is None or ativo.get("id") != cliente.get("id"):
        return
    from cameras import ARQUIVO_CAMERAS

    Path(ARQUIVO_CAMERAS).write_text(
        json.dumps({"cameras": list(cliente.get("cameras") or [])}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _inteiro(valor, padrao: int, nome: str) -> int:
    if valor in (None, ""):
        return padrao
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ValueError(f"Informe {nome} com um número inteiro.") from None


def _coordenada_campo(valor, nome: str):
    from cameras import _coordenada

    if str(valor or "").strip() == "":
        return None
    numero = _coordenada(valor)
    if numero is None:
        raise ValueError(f"Informe {nome} entre -180 e 180.")
    return numero


def salvar_camera(documento: str, campos: dict, id_anterior: str = "") -> dict:
    from cameras import montar_url_rtsp

    cliente = _exigir(documento)
    if not isinstance(campos, dict):
        raise ValueError("Informe os dados da câmera.")
    cameras = [item for item in cliente.get("cameras") or [] if isinstance(item, dict)]
    ident = str(campos.get("id") or id_anterior or f"cam-{len(cameras) + 1}").strip()
    if not ident:
        raise ValueError("Informe o identificador da câmera.")
    anterior = _camera_por_id(cliente, id_anterior or ident)
    if any(str(item.get("id")) == ident for item in cameras) and (anterior is None or str(anterior.get("id")) != ident):
        raise ValueError("Já existe uma câmera com este identificador.")
    nome = str(campos.get("nome") or "").strip()
    modelo = str(campos.get("modelo") or (anterior or {}).get("modelo") or "").strip()
    marca = str(campos.get("marca") or (anterior or {}).get("marca") or "Intelbras").strip() or "Intelbras"
    if not nome or not modelo:
        raise ValueError("Informe o nome e o modelo da câmera.")
    registro = dict(anterior or {})
    registro.update({
        "id": ident,
        "nome": nome,
        "marca": marca,
        "modelo": modelo,
        "ativa": campos.get("ativa", True) is not False,
        "rua": str(campos.get("rua") or "").strip(),
        "bairro": str(campos.get("bairro") or "").strip(),
        "cidade": str(campos.get("cidade") or "").strip(),
        "latitude": _coordenada_campo(campos.get("latitude"), "a latitude"),
        "longitude": _coordenada_campo(campos.get("longitude"), "a longitude"),
    })
    host = str(campos.get("host") or "").strip()
    if host:
        registro["host"] = host
        registro["porta"] = _inteiro(campos.get("porta"), 554, "a porta")
        registro["canal"] = _inteiro(campos.get("canal"), 1, "o canal")
        registro["subtype"] = _inteiro(campos.get("subtype"), 0, "o subtype")
        registro["usuario"] = str(campos.get("usuario") or registro.get("usuario") or "").strip()
        senha = str(campos.get("senha") or "")
        if senha:
            registro["senha"] = senha
        if not str(registro.get("senha") or ""):
            raise ValueError("Informe a senha da câmera para gravar o novo host.")
        registro["url"] = montar_url_rtsp(registro)
    elif not str(registro.get("url") or registro.get("host") or "").strip():
        raise ValueError("Informe o host da câmera.")
    else:
        if str(campos.get("usuario") or "").strip():
            registro["usuario"] = str(campos.get("usuario")).strip()
        if str(campos.get("porta") or "").strip():
            registro["porta"] = _inteiro(campos.get("porta"), 554, "a porta")
        if str(campos.get("canal") or "").strip():
            registro["canal"] = _inteiro(campos.get("canal"), 1, "o canal")
        if str(campos.get("subtype") or "").strip():
            registro["subtype"] = _inteiro(campos.get("subtype"), 0, "o subtype")
    registro["avisos"] = list((anterior or {}).get("avisos") or [])
    cliente["cameras"] = [item for item in cameras if str(item.get("id")) != str((anterior or {}).get("id") or ident)]
    cliente["cameras"].append(registro)
    _substituir(cliente)
    _espelhar_cameras(cliente)
    return camera_publica(registro)


def cadastrar_aviso(documento: str, camera_id: str, aviso: dict) -> dict:
    cliente = _exigir(documento)
    camera = _camera_por_id(cliente, camera_id)
    if camera is None:
        raise ValueError("Escolha uma câmera desta conta.")
    if not isinstance(aviso, dict):
        raise ValueError("Informe o telefone e o e-mail.")
    email = str(aviso.get("email") or "").strip().lower()
    if not _email_valido(email):
        raise ValueError("Informe o e-mail que recebe os alertas desta câmera.")
    partes = _telefone_partes(aviso.get("codigo_pais"), aviso.get("ddd"), aviso.get("numero"))
    registro = {
        **partes,
        "email": email,
        "recebe_alerta": aviso.get("recebe_alerta", True) is not False,
        "recebe_relatorio": aviso.get("recebe_relatorio", True) is not False,
    }
    avisos = [item for item in camera.get("avisos") or [] if isinstance(item, dict)]
    if any(str(item.get("email") or "").lower() == email and item.get("telefone") == registro["telefone"] for item in avisos):
        raise ValueError("Este telefone e este e-mail já estão nesta câmera.")
    avisos.append(registro)
    camera["avisos"] = avisos
    _substituir(cliente)
    _espelhar_cameras(cliente)
    return registro


def remover_camera(documento: str, ident: str):
    cliente = _exigir(documento)
    ident = str(ident or "").strip()
    cameras = [item for item in cliente.get("cameras") or [] if isinstance(item, dict)]
    restantes = [item for item in cameras if str(item.get("id")) != ident]
    if len(restantes) == len(cameras):
        raise ValueError("Câmera não encontrada nesta conta.")
    cliente["cameras"] = restantes
    _substituir(cliente)
    _espelhar_cameras(cliente)


def limpar_pessoas() -> int:
    """Apaga os cadastros de pessoas de interesse. As câmeras e as contas permanecem."""
    dados = _ler()
    total = 0
    for cliente in dados["clientes"]:
        total += len(cliente.get("pessoas") or [])
        cliente["pessoas"] = []
    _gravar(dados)
    interesse = Path("interesse.json")
    if interesse.exists():
        try:
            bruto = json.loads(interesse.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            bruto = {}
        if isinstance(bruto, dict):
            bruto["pessoas"] = []
            interesse.write_text(json.dumps(bruto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return total


def criar_cliente(nome: str, documento: str, email: str) -> dict:
    digitos = _digitos(documento)
    if not documento_valido(digitos):
        raise ValueError("Informe um CPF ou CNPJ válido.")
    if not _email_valido(email):
        raise ValueError("Informe o e-mail do cliente.")
    if cliente_por_documento(digitos) is not None:
        raise ValueError("Este documento já pertence a um cliente.")
    cliente = _cliente_novo(len(listar_clientes()) + 1)
    cliente["nome"] = (nome or "").strip()
    cliente["documento"] = digitos
    cliente["tipo_documento"] = "cnpj" if len(digitos) == 14 else "cpf"
    cliente["email"] = str(email).strip().lower()
    cliente["ativo"] = True
    dados = _ler()
    dados["clientes"].append(cliente)
    _gravar(dados)
    return cliente


def definir_atividade(documento: str, ativo: bool):
    if _digitos(documento) == DOCUMENTO_ADMIN:
        raise ValueError("A conta do administrador permanece ativa.")
    cliente = cliente_por_documento(documento)
    if cliente is None:
        raise ValueError("Cliente não encontrado.")
    cliente["ativo"] = bool(ativo)
    _substituir(cliente)
    return cliente


def excluir_cliente(documento: str):
    if _digitos(documento) == DOCUMENTO_ADMIN:
        raise ValueError("A conta do administrador não pode ser excluída.")
    dados = _ler()
    digitos = _digitos(documento)
    restantes = [item for item in dados["clientes"] if _digitos(item.get("documento")) != digitos]
    if len(restantes) == len(dados["clientes"]):
        raise ValueError("Cliente não encontrado.")
    _gravar({"clientes": restantes})
    from acesso import remover_por_documento

    remover_por_documento(digitos)


def resumo_clientes() -> list[dict]:
    saida = []
    for cliente in listar_clientes():
        cameras = [item for item in cliente.get("cameras") or [] if isinstance(item, dict)]
        saida.append({
            "nome": cliente.get("nome") or "",
            "documento": cliente.get("documento") or "",
            "email": cliente.get("email") or "",
            "ativo": cliente.get("ativo") is not False,
            "cameras": len(cameras),
            "cameras_ativas": sum(1 for item in cameras if item.get("ativa") is not False),
        })
    return saida


def remover_aviso(documento: str, camera_id: str, indice: int):
    cliente = _exigir(documento)
    camera = _camera_por_id(cliente, camera_id)
    if camera is None:
        raise ValueError("Câmera não encontrada nesta conta.")
    avisos = [item for item in camera.get("avisos") or [] if isinstance(item, dict)]
    if indice < 0 or indice >= len(avisos):
        raise ValueError("Aviso não encontrado.")
    del avisos[indice]
    camera["avisos"] = avisos
    _substituir(cliente)
    _espelhar_cameras(cliente)


def _exigir(documento: str) -> dict:
    cliente = cliente_por_documento(documento) if documento else cliente_ativo()
    if cliente is None:
        raise ValueError("Conta não encontrada para este CPF ou CNPJ.")
    return cliente


def locais_cameras() -> list[dict]:
    """Rua e coordenadas das câmeras ativas, sem endereço de acesso."""
    garantir_cliente_local()
    cliente = cliente_ativo()
    registros = list((cliente or {}).get("cameras") or [])
    if not registros:
        caminho = Path("cameras.json")
        if caminho.exists():
            try:
                bruto = json.loads(caminho.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                bruto = {}
            if isinstance(bruto, dict):
                registros = list(bruto.get("cameras") or [])
            elif isinstance(bruto, list):
                registros = bruto
    locais = []
    for item in registros:
        if not isinstance(item, dict) or item.get("ativa") is False:
            continue
        try:
            latitude = float(item.get("latitude"))
            longitude = float(item.get("longitude"))
        except (TypeError, ValueError):
            latitude = longitude = None
        locais.append({
            "nome": str(item.get("nome") or "").strip(),
            "rua": str(item.get("rua") or "").strip(),
            "bairro": str(item.get("bairro") or "").strip(),
            "cidade": str(item.get("cidade") or "").strip(),
            "latitude": latitude,
            "longitude": longitude,
        })
    return locais


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


def _emails_unicos(emails) -> list[str]:
    vistos = []
    for email in emails:
        texto = str(email or "").strip()
        if texto and texto not in vistos:
            vistos.append(texto)
    return vistos


def _emails_avisos(cliente: dict, camera_ref: str = "", somente_alerta: bool = False) -> list[str]:
    ref = str(camera_ref or "").strip().lower()
    emails = []
    for camera in cliente.get("cameras") or []:
        if not isinstance(camera, dict):
            continue
        nome = str(camera.get("nome") or "").strip().lower()
        ident = str(camera.get("id") or "").strip().lower()
        if ref and ref not in (nome, ident):
            continue
        for aviso in camera.get("avisos") or []:
            if not isinstance(aviso, dict):
                continue
            if somente_alerta and aviso.get("recebe_alerta", True) is False:
                continue
            if not somente_alerta and aviso.get("recebe_relatorio", True) is False:
                continue
            if str(aviso.get("email") or "").strip():
                emails.append(str(aviso["email"]).strip())
    return emails


def _emails_da_conta(cliente: dict | None) -> list[str]:
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
    return _emails_unicos(emails)


def destinatarios(cliente: dict | None = None) -> list[str]:
    cliente = cliente if cliente is not None else cliente_ativo()
    emails = _emails_da_conta(cliente)
    if cliente:
        emails.extend(_emails_avisos(cliente))
    return _emails_unicos(emails)


def emails_do_alerta(camera_ref: str) -> list[str]:
    """E-mails da câmera citada no alerta. Sem aviso próprio, usa o e-mail da conta."""
    cliente = cliente_ativo()
    if cliente is None or not str(camera_ref or "").strip():
        return destinatarios(cliente)
    proprios = _emails_unicos(_emails_avisos(cliente, camera_ref, somente_alerta=True))
    if proprios:
        return proprios
    return _emails_da_conta(cliente)


def nomes_cameras_conta(documento: str) -> set[str]:
    """Nomes das câmeras do CPF/CNPJ (para filtrar ao vivo e painéis)."""
    digitos = _digitos(documento)
    if not digitos:
        return set()
    cliente = cliente_por_documento(digitos)
    if cliente is None:
        return set()
    nomes = set()
    for item in cliente.get("cameras") or []:
        if not isinstance(item, dict) or item.get("ativa") is False:
            continue
        nome = str(item.get("nome") or "").strip()
        if nome:
            nomes.add(nome)
    return nomes


def pode_ver_analise(documento: str) -> bool:
    """Usuário com conta ativa navega nos painéis; o conteúdo é filtrado pelas câmeras do CPF/CNPJ."""
    digitos = _digitos(documento)
    if not digitos:
        return False
    if digitos == _digitos(DOCUMENTO_ADMIN):
        return True
    cliente = cliente_por_documento(digitos)
    return cliente is not None and cliente.get("ativo") is not False


def eh_conta_em_analise(documento: str) -> bool:
    """True se este CPF/CNPJ é a conta cujas câmeras rodam nesta máquina."""
    digitos = _digitos(documento)
    if not digitos:
        return False
    if digitos == _digitos(DOCUMENTO_ADMIN):
        return True
    ativo = cliente_ativo()
    if ativo is None:
        return False
    return _digitos(ativo.get("documento")) == digitos


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
