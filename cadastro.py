"""Conta do cliente e política de acesso colaborativo por rua/bairro/cidade.

Admin vê tudo. Líder de cidade vê câmeras da cidade; líder de bairro, do bairro.
Cliente com ≥1 câmera vê as próprias + mesma rua. Sem câmera, a rua fica oculta.

RF: morador/prestador/visitante computam passagem no ranking, sem alerta.
Risco (suspeito, desaparecida, mandado, ex-detento): alerta para quem cadastrou,
admin e vizinhos da rua com câmera. Medida protetiva: só quem cadastrou + admin.
"""

from __future__ import annotations

import json
import os
import unicodedata
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
CLASSES_RISCO = {
    "comportamento_suspeito",
    "mandado",
    "ex_detento",
    "mandado_judicial",
    "medida_protetiva",
    "pessoa_desaparecida",
}
CLASSES_LOCAIS = {
    "morador",
    "prestador_servico",
    "visitante",
    "acompanhamento_familiar",
}
# Stella Maris primeiro (piloto); em seguida outros logradouros de Salvador.
LOGRADOUROS_STELLA_MARIS = (
    "Rua Lidia Borja",
    "Rua Professor Carlos Ott",
    "Rua Hamilton Drumond Frank",
    "Rua Alameda do Sol",
    "Rua das Garças",
    "Rua dos Flamingos",
    "Rua dos Beija-Flores",
    "Rua das Gaivotas",
    "Rua das Orquídeas",
    "Rua das Bromélias",
    "Rua Professora Dulce Zarzur",
    "Rua Doutor José Eduardo Freire",
    "Avenida Pinto de Aguiar",
    "Rua Praia de Stella Maris",
)
LOGRADOUROS_SALVADOR = LOGRADOUROS_STELLA_MARIS + (
    "Avenida Oceânica",
    "Avenida Octávio Mangabeira",
    "Avenida Paralela",
    "Avenida Antônio Carlos Magalhães",
    "Avenida Sete de Setembro",
    "Avenida Tancredo Neves",
    "Avenida Centenário",
    "Avenida Vasco da Gama",
    "Avenida Garibaldi",
    "Avenida Joana Angélica",
    "Avenida Contorno",
    "Avenida Lafayete Coutinho",
    "Avenida Juracy Magalhães Júnior",
    "Avenida Luís Viana Filho",
    "Avenida San Martin",
    "Avenida Suburbana",
    "Rua Chile",
    "Rua Carlos Gomes",
    "Rua da Graça",
    "Rua do Imperador",
    "Rua Direita de Santo Antônio",
    "Rua Miguel Calmon",
    "Rua Portão da Atalaia",
    "Rua Dias d'Ávila",
    "Rua Ceará",
    "Rua Amazonas",
    "Rua Pará",
    "Rua Bahia",
    "Rua Alagoinhas",
    "Rua Aristides Caire",
    "Rua Conselheiro Pedro Luís",
    "Rua Saldanha da Gama",
    "Rua Tertuliano Sales",
    "Ladeira da Barra",
    "Ladeira do Bomfim",
    "Praça da Sé",
    "Praça Municipal",
    "Praça Castro Alves",
)
BAIRROS_SALVADOR = (
    "Stella Maris",
    "Itapuã",
    "Praia do Flamengo",
    "Patamares",
    "Piatã",
    "Boca do Rio",
    "Imbuí",
    "Pituba",
    "Costa Azul",
    "Itaigara",
    "Caminho das Árvores",
    "Parque Bela Vista",
    "Brotas",
    "Garcia",
    "Graça",
    "Barra",
    "Ondina",
    "Rio Vermelho",
    "Federação",
    "Campo Grande",
    "Centro",
    "Comércio",
    "Nazaré",
    "Tororó",
    "Barris",
    "Vitória",
    "Canela",
    "Engenho Velho de Brotas",
    "São Caetano",
    "Pau da Lima",
    "Cajazeiras",
    "Paripe",
    "Periperi",
    "São Tomé de Paripe",
    "Plataforma",
    "Lobato",
    "Alto de Coutos",
    "São Cristóvão",
    "Valéria",
    "Mussurunga",
    "São Marcos",
    "Tancredo Neves",
    "Sussuarana",
    "Cabula",
    "Narandiba",
    "Beiru",
    "Arenoso",
    "Resgate",
)
MUNICIPIOS_BAHIA = (
    "Salvador",
    "Lauro de Freitas",
    "Camaçari",
    "Simões Filho",
    "Candeias",
    "Dias d'Ávila",
    "Madre de Deus",
    "São Francisco do Conde",
    "Vera Cruz",
    "Itaparica",
    "Mata de São João",
    "Catu",
    "Alagoinhas",
    "Feira de Santana",
)
MARCAS_CAMERA = (
    "Intelbras",
    "Hikvision",
    "Dahua",
    "Axis",
    "Bosch",
    "Hanwha",
    "Uniview",
    "Giga",
    "Vivotek",
    "TP-Link",
)
MODELOS_CAMERA = (
    "IM3",
    "IM5",
    "VIP 1130 B G2",
    "VIP 1220 B G3",
    "VIP 1230 B G4",
    "VIP 3240 B IA",
    "VIP 3430 B IA",
    "VIP 5450 B IA",
    "VIP S 4020",
    "VIP S 4430",
    "iM4 Plus",
    "iM5 SC",
)


def classe_pessoa(pessoa: dict) -> str:
    return str((pessoa or {}).get("classe") or (pessoa or {}).get("base_legal") or "").strip()


def pessoa_de_risco(pessoa: dict) -> bool:
    return classe_pessoa(pessoa) in CLASSES_RISCO


def pessoa_local(pessoa: dict) -> bool:
    return classe_pessoa(pessoa) in CLASSES_LOCAIS


def _sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(caractere for caractere in normalizado if not unicodedata.combining(caractere))


def normalizar_rua(rua: str) -> str:
    """Chave comparável de logradouro (sem acento, minúscula, espaços colapsados)."""
    texto = _sem_acento(rua).lower().replace(".", " ")
    texto = " ".join(texto.split())
    return texto


def _canonico_lista(valor: str, opcoes: tuple[str, ...] | list[str]) -> str:
    chave = normalizar_rua(valor)
    if not chave:
        return str(valor or "").strip()
    for item in opcoes:
        if normalizar_rua(item) == chave:
            return item
    return str(valor or "").strip()


def rua_canonica(rua: str) -> str:
    """Devolve o rótulo oficial da lista de logradouros quando houver correspondência."""
    return _canonico_lista(rua, LOGRADOUROS_SALVADOR)


def bairro_canonico(bairro: str) -> str:
    return _canonico_lista(bairro, BAIRROS_SALVADOR) or "Stella Maris"


def municipio_canonico(cidade: str) -> str:
    return _canonico_lista(cidade, MUNICIPIOS_BAHIA) or "Salvador"


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
        "foto_face_id": "",
        "eh_proprio": False,
        "cameras": [],
        "pessoas": [],
        "veiculos": [],
        "contatos_apoio": [],
    }


def _nome_norm(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.casefold().split())


def definir_foto_cliente(documento: str, face_id: str, *, eh_proprio: bool = True) -> dict:
    """Associa a foto do próprio cliente (morador da rua) ao cadastro da conta."""
    cliente = _exigir(documento)
    face = str(face_id or "").strip().upper()
    if not face:
        raise ValueError("Informe o código da foto do cliente.")
    cliente["foto_face_id"] = face
    cliente["eh_proprio"] = bool(eh_proprio)
    # Garante pessoa de interesse "morador" apontando para a própria face.
    pessoas = list(cliente.get("pessoas") or [])
    achou = False
    for pessoa in pessoas:
        if str(pessoa.get("face_id") or "").strip().upper() != face:
            continue
        pessoa["eh_proprio"] = True
        pessoa["classe"] = pessoa.get("classe") or "morador"
        pessoa["base_legal"] = pessoa.get("base_legal") or pessoa["classe"]
        if not str(pessoa.get("nome") or "").strip():
            pessoa["nome"] = str(cliente.get("nome") or face)
        achou = True
        break
    if not achou:
        pessoas.append({
            "face_id": face,
            "nome": str(cliente.get("nome") or face),
            "classe": "morador",
            "base_legal": "morador",
            "referencia": "Foto do próprio cliente",
            "motivo": "",
            "eh_proprio": True,
        })
    cliente["pessoas"] = pessoas
    _substituir(cliente)
    try:
        from grafo_relacoes import garantir_pessoa, garantir_usuario, relacionar

        digitos = _digitos(cliente.get("documento"))
        garantir_usuario(digitos, cliente.get("nome") or "", cliente.get("email") or "")
        garantir_pessoa(
            face,
            nome=str(cliente.get("nome") or face),
            classe="morador",
            documento_cliente=digitos,
        )
        relacionar(
            digitos,
            face,
            "proprio",
            nome_pessoa=str(cliente.get("nome") or face),
            classe="morador",
            nome_usuario=str(cliente.get("nome") or ""),
            email=str(cliente.get("email") or ""),
            meta={"fonte": "foto_cliente", "documento": digitos},
        )
    except Exception as exc:
        print(f"Grafo foto cliente: {exc}")
    return cliente


def garantir_identidades_proprias() -> list[dict]:
    """Diego/Vanessa: morador de interesse = o próprio cliente da conta."""
    # documento → face canônica conhecida no piloto
    mapa = (
        ("02401001581", "F0001", "diego"),
        ("01123242585", "F2553", "vanessa"),
    )
    atualizados = []
    for digitos, face_padrao, chave_nome in mapa:
        cliente = cliente_por_documento(digitos)
        if not cliente:
            continue
        face = str(cliente.get("foto_face_id") or "").strip().upper()
        if not face:
            # Preferência: pessoa morador cujo nome bate com o cliente.
            nome_cli = _nome_norm(cliente.get("nome") or "")
            for pessoa in cliente.get("pessoas") or []:
                if str(pessoa.get("classe") or pessoa.get("base_legal") or "") != "morador":
                    continue
                nome_p = _nome_norm(pessoa.get("nome") or "")
                if chave_nome in nome_p or (nome_cli and (nome_cli in nome_p or nome_p in nome_cli)):
                    face = str(pessoa.get("face_id") or "").strip().upper()
                    break
            if not face:
                face = face_padrao
        if not face:
            continue
        ja_ok = (
            str(cliente.get("foto_face_id") or "").strip().upper() == face
            and cliente.get("eh_proprio") is True
            and any(
                str(p.get("face_id") or "").strip().upper() == face and p.get("eh_proprio") is True
                for p in (cliente.get("pessoas") or [])
            )
        )
        if ja_ok:
            continue
        definir_foto_cliente(digitos, face, eh_proprio=True)
        atualizados.append({"documento": digitos, "foto_face_id": face})
    return atualizados


def cliente_por_foto_face(face_id: str) -> dict | None:
    ident = str(face_id or "").strip().upper()
    if not ident:
        return None
    for cliente in listar_clientes():
        if cliente.get("ativo") is False:
            continue
        if str(cliente.get("foto_face_id") or "").strip().upper() == ident:
            return cliente
        for pessoa in cliente.get("pessoas") or []:
            if str(pessoa.get("face_id") or "").strip().upper() != ident:
                continue
            if pessoa.get("eh_proprio") is True:
                return cliente
    return None


def candidatos_face_por_nome(nome: str) -> list[dict]:
    """Clientes/pessoas cujo nome bate — usados para match facial na associação Stive."""
    alvo = _nome_norm(nome)
    if not alvo or len(alvo) < 2:
        return []
    saida = []
    vistos = set()
    for cliente in listar_clientes():
        if cliente.get("ativo") is False:
            continue
        digitos = _digitos(cliente.get("documento"))
        nome_cli = _nome_norm(cliente.get("nome") or "")
        foto = str(cliente.get("foto_face_id") or "").strip().upper()
        if foto and nome_cli and (alvo in nome_cli or nome_cli in alvo or alvo.split()[0] in nome_cli):
            chave = f"{digitos}:{foto}"
            if chave not in vistos:
                vistos.add(chave)
                saida.append({
                    "documento": digitos,
                    "nome": str(cliente.get("nome") or ""),
                    "face_id": foto,
                    "origem": "cliente",
                })
        for pessoa in cliente.get("pessoas") or []:
            face = str(pessoa.get("face_id") or "").strip().upper()
            if not face:
                continue
            nome_p = _nome_norm(pessoa.get("nome") or "")
            if not nome_p:
                continue
            if not (alvo in nome_p or nome_p in alvo or alvo.split()[0] in nome_p):
                continue
            chave = f"{digitos}:{face}"
            if chave in vistos:
                continue
            vistos.add(chave)
            saida.append({
                "documento": digitos,
                "nome": str(pessoa.get("nome") or cliente.get("nome") or face),
                "face_id": face,
                "origem": "pessoa",
                "eh_proprio": pessoa.get("eh_proprio") is True or face == foto,
            })
    return saida


def associar_rosto_conhecido(
    documento_operador: str,
    face_id: str,
    nome: str,
    vinculo: str,
    *,
    faces_engine=None,
) -> dict:
    """Nomeia o rosto reaparecido, tenta casar com foto de cliente e cria vínculo usuário↔usuário."""
    face = str(face_id or "").strip().upper()
    nome_limpo = " ".join(str(nome or "").split())
    vinculo = str(vinculo or "").strip().lower() or "conhecido"
    digitos_op = _digitos(documento_operador)
    if not face or not digitos_op:
        raise ValueError("Informe o rosto e o documento do operador.")
    operador = cliente_por_documento(digitos_op) or {}
    resultado = {
        "face_id": face,
        "nome": nome_limpo or face,
        "vinculo": vinculo,
        "cliente_associado": None,
        "face_canonica": face,
        "score": None,
        "fundiu": False,
    }
    candidatos = candidatos_face_por_nome(nome_limpo) if nome_limpo else []
    # Remove o próprio operador da lista de match (não associar a si mesmo).
    candidatos = [c for c in candidatos if c.get("documento") != digitos_op and c.get("face_id") != face]

    melhor = None
    melhor_score = -1.0
    if faces_engine is not None and candidatos:
        for cand in candidatos:
            try:
                score = float(faces_engine.score_entre_ids(face, cand["face_id"]))
            except Exception:
                score = -1.0
            if score > melhor_score:
                melhor_score = score
                melhor = cand
        limiar = getattr(faces_engine, "limiar_fundir", None) or getattr(faces_engine, "limiar_match", 0.55)
        try:
            limiar = float(limiar)
        except (TypeError, ValueError):
            limiar = 0.55
        if melhor is not None and melhor_score >= limiar:
            resultado["cliente_associado"] = melhor
            resultado["score"] = round(melhor_score, 4)
            canon = str(melhor["face_id"]).upper()
            resultado["face_canonica"] = canon
            if canon != face:
                try:
                    faces_engine.fundir_em(canon, face)
                    resultado["fundiu"] = True
                    face = canon
                    resultado["face_id"] = canon
                except Exception as exc:
                    print(f"Fusão facial na associação: {exc}")

    try:
        from grafo_relacoes import garantir_pessoa, relacionar, relacionar_usuarios

        garantir_pessoa(
            resultado["face_canonica"],
            nome=resultado["nome"],
            documento_cliente=(resultado["cliente_associado"] or {}).get("documento") or "",
        )
        relacionar(
            digitos_op,
            resultado["face_canonica"],
            vinculo,
            nome_pessoa=resultado["nome"],
            nome_usuario=str(operador.get("nome") or ""),
            email=str(operador.get("email") or ""),
            meta={
                "fonte": "stive_conhece",
                "documento": digitos_op,
                "nome_informado": nome_limpo,
                "cliente_associado": (resultado["cliente_associado"] or {}).get("documento") or "",
                "score": resultado["score"],
            },
        )
        associado = resultado["cliente_associado"]
        if associado and associado.get("documento"):
            relacionar_usuarios(
                digitos_op,
                associado["documento"],
                vinculo,
                nome_origem=str(operador.get("nome") or ""),
                email_origem=str(operador.get("email") or ""),
                nome_destino=str(associado.get("nome") or ""),
                meta={
                    "fonte": "stive_face_match",
                    "face_id": resultado["face_canonica"],
                    "score": resultado["score"],
                    "nome_informado": nome_limpo,
                },
            )
    except Exception as exc:
        print(f"Associação grafo: {exc}")
        resultado["erro_grafo"] = str(exc)
    return resultado


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
    if classe == "medida_protetiva":
        favorecido = str(pessoa.get("favorecido") or "").strip().lower()
        if favorecido not in ("eu", "amigo"):
            raise ValueError(
                "Medida protetiva deve favorecer você ou um amigo(a) perseguido e protegido pela justiça."
            )
        if favorecido == "amigo" and not str(pessoa.get("nome_protegido") or "").strip():
            raise ValueError("Informe o nome do amigo(a) protegido pela medida.")
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
    if registro["classe"] == "medida_protetiva":
        registro["favorecido"] = str(pessoa.get("favorecido") or "").strip().lower()
        registro["nome_protegido"] = str(pessoa.get("nome_protegido") or "").strip()
    pessoas = [item for item in cliente["pessoas"] if str(item.get("face_id") or "").upper() != face_id]
    pessoas.append(registro)
    cliente["pessoas"] = pessoas
    _substituir(cliente)
    if registro["classe"] == "medida_protetiva":
        try:
            from grafo_relacoes import relacionar

            relacionar(
                documento,
                face_id,
                "medida_protege",
                nome_pessoa=str(registro.get("nome") or face_id),
                classe="medida_protetiva",
                nome_usuario=str(cliente.get("nome") or ""),
                email=str(cliente.get("email") or ""),
                meta={
                    "favorecido": registro.get("favorecido") or "",
                    "nome_protegido": registro.get("nome_protegido") or "",
                    "referencia": registro.get("referencia") or "",
                },
            )
        except Exception as exc:
            print(f"Grafo medida protetiva: {exc}")
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
    placa = "".join(c for c in str(veiculo.get("placa") or "").upper() if c.isalnum())
    if len(placa) < 6:
        raise ValueError("Informe uma placa válida.")
    registro = dict(veiculo)
    registro["placa"] = placa
    registro["nome"] = str(veiculo.get("nome") or "").strip() or placa
    registro["motivo"] = str(veiculo.get("motivo") or "").strip()
    veiculos = [item for item in cliente.get("veiculos") or [] if str(item.get("placa") or "").upper() != placa]
    veiculos.append(registro)
    cliente["veiculos"] = veiculos
    _substituir(cliente)
    return registro


def remover_veiculo(documento: str, placa: str) -> str:
    cliente = _exigir(documento)
    ident = "".join(c for c in str(placa or "").upper() if c.isalnum())
    if not ident:
        raise ValueError("Informe a placa.")
    antes = len(cliente.get("veiculos") or [])
    cliente["veiculos"] = [
        item for item in (cliente.get("veiculos") or [])
        if str(item.get("placa") or "").upper() != ident
    ]
    if len(cliente["veiculos"]) == antes:
        raise ValueError("Placa não encontrada nesta conta.")
    _substituir(cliente)
    return ident


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


def _espelhar_cameras(cliente: dict | None = None):
    """Espelha todas as câmeras ativas das contas em cameras.json."""
    from cameras import ARQUIVO_CAMERAS

    registros = []
    vistos = set()
    for conta in listar_clientes():
        if conta.get("ativo") is False:
            continue
        for item in conta.get("cameras") or []:
            if not isinstance(item, dict):
                continue
            ident = str(item.get("id") or "").strip()
            nome = str(item.get("nome") or "").strip()
            chave = ident or nome
            if not chave or chave in vistos:
                continue
            vistos.add(chave)
            registros.append(item)
    Path(ARQUIVO_CAMERAS).write_text(
        json.dumps({"cameras": registros}, ensure_ascii=False, indent=2) + "\n",
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
        "rua": rua_canonica(str(campos.get("rua") or "").strip()),
        "bairro": bairro_canonico(str(campos.get("bairro") or "").strip()),
        "cidade": municipio_canonico(str(campos.get("cidade") or "").strip()),
        "latitude": _coordenada_campo(campos.get("latitude"), "a latitude"),
        "longitude": _coordenada_campo(campos.get("longitude"), "a longitude"),
    })
    if not registro["rua"]:
        raise ValueError("Informe o logradouro da câmera.")
    host = str(campos.get("host") or "").strip()
    if host:
        porta = _inteiro(campos.get("porta"), 554, "a porta")
        # Formulário às vezes manda "IP:554" no host.
        if ":" in host and not host.startswith("["):
            base, _, sufixo = host.rpartition(":")
            if base and sufixo.isdigit():
                host = base
                if str(campos.get("porta") or "").strip() == "":
                    porta = int(sufixo)
        registro["host"] = host
        registro["porta"] = porta
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
    """Rua e coordenadas das câmeras ativas de todas as contas, sem endereço de acesso."""
    garantir_cliente_local()
    registros = []
    vistos = set()
    for cliente in listar_clientes():
        if cliente.get("ativo") is False:
            continue
        for item in cliente.get("cameras") or []:
            if not isinstance(item, dict) or item.get("ativa") is False:
                continue
            nome = str(item.get("nome") or "").strip()
            if not nome or nome in vistos:
                continue
            vistos.add(nome)
            registros.append(item)
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
    """Todas as câmeras ativas das contas desta instalação (admin + clientes)."""
    from cameras import filtrar_ativas, ler_cameras

    garantir_cliente_local()
    registros = []
    vistos = set()
    for cliente in listar_clientes():
        if cliente.get("ativo") is False:
            continue
        for item in cliente.get("cameras") or []:
            if not isinstance(item, dict):
                continue
            ident = str(item.get("id") or "").strip()
            nome = str(item.get("nome") or "").strip()
            chave = ident or nome
            if not chave or chave in vistos:
                continue
            vistos.add(chave)
            registros.append(item)
    if registros:
        return filtrar_ativas(registros)
    return ler_cameras()


def interesse_ativo() -> dict:
    """Interesse da conta em análise local (compatibilidade). Prefira interesse_para_camera."""
    from agente.fontes import carregar_interesse

    garantir_cliente_local()
    cliente = cliente_ativo()
    if cliente is None:
        return carregar_interesse()
    return {
        "pessoas": list(cliente.get("pessoas") or []),
        "veiculos": list(cliente.get("veiculos") or []),
    }


def _anexar_dono(pessoa: dict, documento: str) -> dict:
    saida = dict(pessoa or {})
    saida["documento_dono"] = _digitos(documento)
    return saida


def dono_da_camera(camera_ref: str) -> dict | None:
    ref = str(camera_ref or "").strip().lower()
    if not ref:
        return None
    for cliente in listar_clientes():
        for item in cliente.get("cameras") or []:
            if not isinstance(item, dict):
                continue
            nome = str(item.get("nome") or "").strip().lower()
            ident = str(item.get("id") or "").strip().lower()
            if ref in (nome, ident):
                return cliente
    return None


def _rua_da_camera(camera_ref: str) -> str:
    dono = dono_da_camera(camera_ref)
    if not dono:
        return ""
    ref = str(camera_ref or "").strip().lower()
    for item in _cameras_cliente(dono):
        nome = str(item.get("nome") or "").strip().lower()
        ident = str(item.get("id") or "").strip().lower()
        if ref and ref not in (nome, ident):
            continue
        return normalizar_rua(item.get("rua"))
    return ""


def interesse_para_camera(camera_ref: str) -> dict:
    """Risco: todas as câmeras. Locais (morador/prestador/visitante): dono + mesma rua."""
    garantir_cliente_local()
    dono = dono_da_camera(camera_ref)
    dono_id = (dono or {}).get("id")
    rua_cam = _rua_da_camera(camera_ref)
    pessoas = []
    veiculos = []
    vistos_face = set()
    vistos_placa = set()
    for cliente in listar_clientes():
        if cliente.get("ativo") is False:
            continue
        digitos = _digitos(cliente.get("documento"))
        ruas_cli = ruas_compartilhadas(digitos) if digitos else set()
        na_rua = bool(rua_cam and rua_cam in ruas_cli)
        dono_desta = bool(dono_id and cliente.get("id") == dono_id)
        for pessoa in cliente.get("pessoas") or []:
            if not isinstance(pessoa, dict):
                continue
            face = str(pessoa.get("face_id") or "").strip().upper()
            if not face or face in vistos_face:
                continue
            if pessoa_de_risco(pessoa) or dono_desta or (pessoa_local(pessoa) and na_rua):
                vistos_face.add(face)
                pessoas.append(_anexar_dono(pessoa, digitos))
        if dono_desta or na_rua:
            for veiculo in cliente.get("veiculos") or []:
                if not isinstance(veiculo, dict):
                    continue
                placa = str(veiculo.get("placa") or "").strip().upper()
                if not placa or placa in vistos_placa:
                    continue
                vistos_placa.add(placa)
                item = dict(veiculo)
                item["documento_dono"] = digitos
                veiculos.append(item)
    return {"pessoas": pessoas, "veiculos": veiculos}


def risco_visivel_para(documento: str) -> list[dict]:
    """POIs de risco (exceto medida protetiva) de contas no mesmo bairro do CPF."""
    digitos = _digitos(documento)
    if not digitos:
        return []
    _ruas, bairros, _cidades = _escopos_geograficos(digitos)
    if digitos == _digitos(DOCUMENTO_ADMIN):
        bairros = set()  # admin: todos
        for cli in listar_clientes():
            for cam in _cameras_cliente(cli):
                b = normalizar_rua(cam.get("bairro") or "")
                if b:
                    bairros.add(b)
    if not bairros and digitos != _digitos(DOCUMENTO_ADMIN):
        return []
    saida = []
    vistos = set()
    for cliente in listar_clientes():
        if cliente.get("ativo") is False:
            continue
        outro = _digitos(cliente.get("documento"))
        if not outro:
            continue
        _r, bairros_cli, _c = _escopos_geograficos(outro)
        if digitos != _digitos(DOCUMENTO_ADMIN) and not (bairros_cli & bairros):
            continue
        for pessoa in cliente.get("pessoas") or []:
            if not isinstance(pessoa, dict) or not pessoa_de_risco(pessoa):
                continue
            if classe_pessoa(pessoa) == "medida_protetiva":
                continue
            face = str(pessoa.get("face_id") or "").strip().upper()
            if not face or face in vistos:
                continue
            vistos.add(face)
            saida.append(_anexar_dono(pessoa, outro))
    return saida


def interesse_deteccao_global() -> dict:
    """Todas as faces/placas cadastradas (para histórico e painéis agregados)."""
    garantir_cliente_local()
    try:
        garantir_identidades_proprias()
    except Exception:
        pass
    pessoas = []
    veiculos = []
    vistos_face = set()
    vistos_placa = set()
    for cliente in listar_clientes():
        if cliente.get("ativo") is False:
            continue
        digitos = _digitos(cliente.get("documento"))
        foto_cli = str(cliente.get("foto_face_id") or "").strip().upper()
        if foto_cli and foto_cli not in vistos_face:
            vistos_face.add(foto_cli)
            pessoas.append(_anexar_dono({
                "face_id": foto_cli,
                "nome": str(cliente.get("nome") or foto_cli),
                "classe": "morador",
                "base_legal": "morador",
                "referencia": "Foto do próprio cliente",
                "motivo": "",
                "eh_proprio": True,
            }, digitos))
        for pessoa in cliente.get("pessoas") or []:
            if not isinstance(pessoa, dict):
                continue
            face = str(pessoa.get("face_id") or "").strip().upper()
            if not face or face in vistos_face:
                continue
            vistos_face.add(face)
            pessoas.append(_anexar_dono(pessoa, digitos))
        for veiculo in cliente.get("veiculos") or []:
            if not isinstance(veiculo, dict):
                continue
            placa = str(veiculo.get("placa") or "").strip().upper()
            if not placa or placa in vistos_placa:
                continue
            vistos_placa.add(placa)
            item = dict(veiculo)
            item["documento_dono"] = digitos
            veiculos.append(item)
    return {"pessoas": pessoas, "veiculos": veiculos}


def pessoa_por_face(face_id: str) -> tuple[dict | None, dict | None]:
    ident = str(face_id or "").strip().upper()
    if not ident:
        return None, None
    for cliente in listar_clientes():
        for pessoa in cliente.get("pessoas") or []:
            if str((pessoa or {}).get("face_id") or "").strip().upper() == ident:
                return cliente, pessoa
    return None, None


def veiculo_por_placa(placa: str) -> tuple[dict | None, dict | None]:
    ident = str(placa or "").strip().upper()
    if not ident:
        return None, None
    for cliente in listar_clientes():
        for veiculo in cliente.get("veiculos") or []:
            if str((veiculo or {}).get("placa") or "").strip().upper() == ident:
                return cliente, veiculo
    return None, None


def emails_admin() -> list[str]:
    return _emails_da_conta(cliente_por_documento(DOCUMENTO_ADMIN))


def _bairro_da_camera(camera_ref: str) -> str:
    dono = dono_da_camera(camera_ref)
    if not dono:
        return ""
    ref = str(camera_ref or "").strip().lower()
    for item in _cameras_cliente(dono):
        nome = str(item.get("nome") or "").strip().lower()
        ident = str(item.get("id") or "").strip().lower()
        if ref and ref not in (nome, ident):
            continue
        return normalizar_rua(item.get("bairro") or "")
    return ""


def _emails_vizinhos_rua_camera(camera_ref: str) -> list[str]:
    """Contas que compartilham câmera no mesmo logradouro da câmera do evento."""
    dono = dono_da_camera(camera_ref)
    if not dono:
        return []
    digitos = _digitos(dono.get("documento"))
    ruas = ruas_compartilhadas(digitos)
    if not ruas:
        return []
    emails = []
    for cliente in listar_clientes():
        if cliente.get("ativo") is False:
            continue
        outro = _digitos(cliente.get("documento"))
        if not outro or not compartilha_camera(outro):
            continue
        if not (ruas_compartilhadas(outro) & ruas):
            continue
        emails.extend(_emails_da_conta(cliente))
        emails.extend(_emails_avisos(cliente, camera_ref, somente_alerta=True))
    return emails


def _emails_vizinhos_bairro_camera(camera_ref: str) -> list[str]:
    """Risco/aglomeração/mancha: todos com câmera no mesmo bairro + admin."""
    bairro = _bairro_da_camera(camera_ref)
    emails = list(emails_admin())
    if not bairro:
        emails.extend(_emails_vizinhos_rua_camera(camera_ref))
        return _emails_unicos(emails)
    for cliente in listar_clientes():
        if cliente.get("ativo") is False:
            continue
        outro = _digitos(cliente.get("documento"))
        if not outro or not compartilha_camera(outro):
            continue
        _ruas, bairros, _cidades = _escopos_geograficos(outro)
        if bairro not in bairros:
            continue
        emails.extend(_emails_da_conta(cliente))
        emails.extend(_emails_avisos(cliente, camera_ref, somente_alerta=True))
    return _emails_unicos(emails)


def emails_alerta_interesse(tipo: str, ident: str, camera_ref: str = "") -> list[str]:
    """Placa → dono. Local → sem alerta.

    Mandado/suspeito/desaparecida/ex-detento → dono + todos do bairro com câmera + admin.
    Medida protetiva → só quem cadastrou + admin.
    """
    emails = []
    if str(tipo or "").upper() == "PLACA":
        cliente, _veiculo = veiculo_por_placa(ident)
        if cliente:
            emails.extend(_emails_da_conta(cliente))
            emails.extend(_emails_avisos(cliente, camera_ref, somente_alerta=True))
        return _emails_unicos(emails)
    cliente, pessoa = pessoa_por_face(ident)
    if cliente is None:
        return emails_do_alerta(camera_ref)
    if pessoa is not None and not pessoa_de_risco(pessoa):
        # Morador/prestador/visitante: só contabiliza passagem, sem e-mail/alerta.
        return []
    emails.extend(_emails_da_conta(cliente))
    emails.extend(_emails_avisos(cliente, camera_ref, somente_alerta=True))
    emails.extend(emails_admin())
    classe = classe_pessoa(pessoa or {})
    # Bairro (ex.: Stella Maris): Vanessa na Lidia Borja recebe invasor visto na Carlos Ott.
    if classe != "medida_protetiva":
        emails.extend(_emails_vizinhos_bairro_camera(camera_ref))
    return _emails_unicos(emails)


def emails_ocorrencia_rua(endereco_ou_rua: str) -> list[str]:
    """Ocorrências/app e mancha: avisa quem tem câmera no bairro (e na rua) + admin."""
    chave = normalizar_rua(endereco_ou_rua)
    emails = list(emails_admin())
    if not chave:
        return _emails_unicos(emails)
    for cliente in listar_clientes():
        if cliente.get("ativo") is False:
            continue
        digitos = _digitos(cliente.get("documento"))
        if not compartilha_camera(digitos):
            continue
        for camera in cliente.get("cameras") or []:
            if not isinstance(camera, dict) or camera.get("ativa") is False:
                continue
            rua = normalizar_rua(camera.get("rua"))
            bairro = normalizar_rua(camera.get("bairro") or "")
            if (rua and (rua in chave or chave in rua)) or (
                bairro and (bairro in chave or chave in bairro)
            ):
                emails.extend(_emails_da_conta(cliente))
                break
    return _emails_unicos(emails)


def pode_ver_match_interesse(documento: str, match: dict | None) -> bool:
    """Admin vê tudo. Dono vê o próprio.

    Mandado, suspeito, desaparecida e ex-detento: todos com câmera no mesmo bairro.
    Medida protetiva: só quem cadastrou (+ admin).
    """
    digitos = _digitos(documento)
    if not digitos or not isinstance(match, dict):
        return False
    if digitos == _digitos(DOCUMENTO_ADMIN):
        return True
    tipo = str(match.get("tipo") or "").upper()
    ident = str(match.get("id") or "")
    pessoa = None
    if tipo == "PLACA":
        cliente, _veiculo = veiculo_por_placa(ident)
    else:
        cliente, pessoa = pessoa_por_face(ident)
    if cliente is None:
        return True
    if _digitos(cliente.get("documento")) == digitos:
        return True
    if tipo == "PLACA":
        return False
    if pessoa is None or not pessoa_de_risco(pessoa):
        return False
    if classe_pessoa(pessoa) == "medida_protetiva":
        return False
    camera = str(match.get("camera") or "")
    if not camera:
        return False
    # Mesmo bairro do evento (Lidia Borja ↔ Carlos Ott em Stella Maris).
    bairro = _bairro_da_camera(camera)
    _ruas, bairros, _cidades = _escopos_geograficos(digitos)
    if bairro and bairro in bairros:
        return True
    rua = _rua_da_camera(camera)
    if rua and rua in ruas_compartilhadas(digitos):
        return True
    return camera in nomes_cameras_visiveis(digitos)


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
    """Aglomeração, mancha e riscos analíticos: todos do bairro com câmera + admin."""
    if not str(camera_ref or "").strip():
        return destinatarios(cliente_ativo())
    return _emails_vizinhos_bairro_camera(camera_ref)


def nomes_cameras_conta(documento: str) -> set[str]:
    """Nomes das câmeras do CPF/CNPJ (próprias)."""
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


def compartilha_camera(documento: str) -> bool:
    """Condição da política: só enxerga a rua quem cadastrou ao menos uma câmera."""
    return bool(nomes_cameras_conta(documento))


def ruas_compartilhadas(documento: str) -> set[str]:
    """Logradouros normalizados das câmeras ativas da conta."""
    digitos = _digitos(documento)
    if not digitos:
        return set()
    cliente = cliente_por_documento(digitos)
    if cliente is None:
        return set()
    ruas = set()
    for item in cliente.get("cameras") or []:
        if not isinstance(item, dict) or item.get("ativa") is False:
            continue
        chave = normalizar_rua(item.get("rua"))
        if chave:
            ruas.add(chave)
    return ruas


def _cameras_cliente(cliente: dict) -> list[dict]:
    return [
        item for item in (cliente.get("cameras") or [])
        if isinstance(item, dict) and item.get("ativa") is not False
    ]


def _escopos_geograficos(documento: str) -> tuple[set[str], set[str], set[str]]:
    """Ruas, bairros e municípios das câmeras da conta."""
    digitos = _digitos(documento)
    ruas, bairros, cidades = set(), set(), set()
    cliente = cliente_por_documento(digitos)
    if not cliente:
        return ruas, bairros, cidades
    for item in _cameras_cliente(cliente):
        rua = normalizar_rua(item.get("rua"))
        if rua:
            ruas.add(rua)
        bairro = normalizar_rua(item.get("bairro") or "")
        if bairro:
            bairros.add(bairro)
        cidade = normalizar_rua(item.get("cidade") or "")
        if cidade:
            cidades.add(cidade)
    return ruas, bairros, cidades


def nomes_cameras_visiveis(documento: str, perfil: str = "") -> set[str]:
    """Admin: todas. Líder cidade/bairro: escopo geográfico. Cliente: próprias + rua."""
    digitos = _digitos(documento)
    perfil = (perfil or "").strip().lower()
    cliente = cliente_por_documento(digitos)
    if cliente and not perfil:
        perfil = str(cliente.get("perfil") or "").strip().lower()
    if perfil == "administrador" or digitos == _digitos(DOCUMENTO_ADMIN):
        nomes = set()
        for item_cli in listar_clientes():
            if item_cli.get("ativo") is False:
                continue
            for item in _cameras_cliente(item_cli):
                nome = str(item.get("nome") or "").strip()
                if nome:
                    nomes.add(nome)
        return nomes
    proprias = nomes_cameras_conta(digitos)
    if not proprias and perfil not in ("lider_cidade", "lider_bairro"):
        return set()
    ruas, bairros, cidades = _escopos_geograficos(digitos)
    visiveis = set(proprias)
    for item_cli in listar_clientes():
        if item_cli.get("ativo") is False:
            continue
        for item in _cameras_cliente(item_cli):
            nome = str(item.get("nome") or "").strip()
            if not nome:
                continue
            rua = normalizar_rua(item.get("rua"))
            bairro = normalizar_rua(item.get("bairro") or "")
            cidade = normalizar_rua(item.get("cidade") or "")
            if perfil == "lider_cidade" and cidade and cidade in cidades:
                visiveis.add(nome)
            elif perfil == "lider_bairro" and bairro and bairro in bairros:
                visiveis.add(nome)
            elif rua and rua in ruas:
                visiveis.add(nome)
    return visiveis


def item_na_rua_visivel(documento: str, camera: str = "", rua: str = "") -> bool:
    """True se câmera ou logradouro do item está no escopo de rua do CPF."""
    digitos = _digitos(documento)
    if digitos == _digitos(DOCUMENTO_ADMIN):
        return True
    permitidas = nomes_cameras_visiveis(digitos)
    cam = str(camera or "").strip()
    if cam and cam in permitidas:
        return True
    ruas = ruas_compartilhadas(digitos)
    if not ruas:
        return False
    chave = normalizar_rua(rua) or normalizar_rua(cam)
    if not chave:
        return False
    return any(rua_conta in chave or chave in rua_conta for rua_conta in ruas)


def item_no_bairro_visivel(documento: str, camera: str = "", local: str = "") -> bool:
    """Mancha/ocorrências de risco: visível a quem tem câmera no mesmo bairro (ou rua)."""
    digitos = _digitos(documento)
    if digitos == _digitos(DOCUMENTO_ADMIN):
        return True
    if item_na_rua_visivel(documento, camera, local):
        return True
    _ruas, bairros, _cidades = _escopos_geograficos(digitos)
    if not bairros:
        return False
    chave = normalizar_rua(local) or normalizar_rua(camera)
    if chave and any(b in chave or chave in b for b in bairros):
        return True
    bairro_cam = _bairro_da_camera(camera) if camera else ""
    return bool(bairro_cam and bairro_cam in bairros)


def pode_ver_analise(documento: str) -> bool:
    """Usuário com conta ativa navega nos painéis; o conteúdo é filtrado pela política de rua."""
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
