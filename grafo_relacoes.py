"""Grafo de relacionamentos entre contas e faces (Neo4j opcional + JSON local).

Nós: usuario (CPF), pessoa (face_id).
Arestas: conhecido, amigo, familiar, vizinho, colega, medida_protege.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

ARQUIVO = Path("grafo_relacoes.json")
TIPOS_VINCULO = {
    "conhecido": "Conhecido",
    "amigo": "Amigo(a)",
    "familiar": "Familiar",
    "irmao": "Irmão(ã)",
    "pai": "Pai",
    "mae": "Mãe",
    "esposa": "Esposa",
    "marido": "Marido",
    "namorado": "Namorado(a)",
    "primo": "Primo(a)",
    "tio": "Tio(a)",
    "vizinho": "Vizinho(a)",
    "colega": "Colega",
    "proprio": "Próprio usuário",
    "monitora": "Monitora",
    "mesmo_individuo": "Mesmo indivíduo",
    "interesse_compartilhado": "Interesse compartilhado",
    "medida_protege": "Medida protetiva (protege)",
}

# Opções exibidas no Stive (vínculos pessoais; sem tipos de sistema).
VINCULOS_STIVE = {
    chave: rotulo
    for chave, rotulo in TIPOS_VINCULO.items()
    if chave not in {
        "medida_protege",
        "proprio",
        "monitora",
        "mesmo_individuo",
        "interesse_compartilhado",
    }
}
_TRAVA = threading.RLock()
_neo = None
_neo_ok = False
_neo_tentou = False


def _agora() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _digitos(valor: str) -> str:
    return "".join(c for c in str(valor or "") if c.isdigit())


def _ler() -> dict:
    if not ARQUIVO.exists():
        return {"nos": {}, "arestas": []}
    try:
        bruto = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"nos": {}, "arestas": []}
    if not isinstance(bruto, dict):
        return {"nos": {}, "arestas": []}
    bruto.setdefault("nos", {})
    bruto.setdefault("arestas", [])
    return bruto


def _gravar(dados: dict) -> None:
    ARQUIVO.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def _neo4j():
    """Conecta no Neo4j se NEO4J_URI estiver definido; senão usa só o JSON."""
    global _neo, _neo_ok, _neo_tentou
    if _neo_tentou:
        return _neo if _neo_ok else None
    _neo_tentou = True
    uri = (os.getenv("NEO4J_URI") or "").strip()
    if not uri:
        return None
    try:
        from neo4j import GraphDatabase

        user = os.getenv("NEO4J_USER") or "neo4j"
        password = os.getenv("NEO4J_PASSWORD") or "neo4j"
        _neo = GraphDatabase.driver(uri, auth=(user, password))
        with _neo.session() as sessao:
            sessao.run("RETURN 1")
        _neo_ok = True
    except Exception as exc:
        print(f"Neo4j indisponível — usando grafo local JSON: {exc}")
        _neo = None
        _neo_ok = False
    return _neo if _neo_ok else None


def _upsert_no_local(dados: dict, no_id: str, rotulo: str, props: dict) -> None:
    atual = dict(dados["nos"].get(no_id) or {})
    atual.update(props or {})
    atual["id"] = no_id
    atual["rotulo"] = rotulo or atual.get("rotulo") or "No"
    dados["nos"][no_id] = atual


def _neo_upsert(no_id: str, rotulo: str, props: dict) -> None:
    driver = _neo4j()
    if not driver:
        return
    props = dict(props or {})
    props["id"] = no_id
    label = "Usuario" if rotulo == "usuario" else "Pessoa"
    with driver.session() as sessao:
        sessao.run(
            f"MERGE (n:{label} {{id: $id}}) SET n += $props, n.rotulo = $rotulo",
            id=no_id,
            props=props,
            rotulo=rotulo,
        )


def _neo_aresta(origem: str, destino: str, tipo: str, props: dict) -> None:
    driver = _neo4j()
    if not driver:
        return
    with driver.session() as sessao:
        sessao.run(
            """
            MATCH (a {id: $origem}), (b {id: $destino})
            MERGE (a)-[r:RELACIONADO {tipo: $tipo}]->(b)
            SET r += $props
            """,
            origem=origem,
            destino=destino,
            tipo=tipo,
            props=dict(props or {}),
        )


def garantir_usuario(documento: str, nome: str = "", email: str = "") -> str:
    digitos = _digitos(documento)
    if not digitos:
        return ""
    no_id = f"U:{digitos}"
    props = {
        "documento": digitos,
        "nome": str(nome or digitos),
        "email": str(email or ""),
        "atualizado": _agora(),
    }
    with _TRAVA:
        dados = _ler()
        _upsert_no_local(dados, no_id, "usuario", props)
        _gravar(dados)
    _neo_upsert(no_id, "usuario", props)
    return no_id


def garantir_pessoa(
    face_id: str,
    nome: str = "",
    classe: str = "",
    documento_cliente: str = "",
) -> str:
    face = str(face_id or "").strip().upper()
    if not face:
        return ""
    no_id = f"F:{face}"
    props = {
        "face_id": face,
        "nome": str(nome or face),
        "classe": str(classe or ""),
        "atualizado": _agora(),
    }
    digitos_cli = _digitos(documento_cliente)
    if digitos_cli:
        props["documento_cliente"] = digitos_cli
    with _TRAVA:
        dados = _ler()
        _upsert_no_local(dados, no_id, "pessoa", props)
        _gravar(dados)
    _neo_upsert(no_id, "pessoa", props)
    return no_id


def _gravar_aresta(origem: str, destino: str, tipo: str, props: dict) -> dict:
    with _TRAVA:
        dados = _ler()
        restantes = [
            a for a in dados["arestas"]
            if not (
                a.get("origem") == origem
                and a.get("destino") == destino
                and a.get("tipo") == tipo
            )
        ]
        aresta = {**props, "origem": origem, "destino": destino, "tipo": tipo}
        restantes.append(aresta)
        dados["arestas"] = restantes[-2000:]
        _gravar(dados)
    _neo_aresta(origem, destino, tipo, props)
    return aresta


def relacionar(
    documento: str,
    face_id: str,
    tipo: str,
    *,
    nome_pessoa: str = "",
    classe: str = "",
    nome_usuario: str = "",
    email: str = "",
    meta: dict | None = None,
) -> dict:
    tipo = str(tipo or "").strip().lower()
    if tipo not in TIPOS_VINCULO:
        raise ValueError("Escolha um tipo de vínculo válido.")
    origem = garantir_usuario(documento, nome_usuario, email)
    destino = garantir_pessoa(
        face_id,
        nome_pessoa,
        classe,
        documento_cliente=str((meta or {}).get("cliente_associado") or ""),
    )
    if not origem or not destino:
        raise ValueError("Não foi possível montar o vínculo.")
    meta_limpo = {
        chave: valor
        for chave, valor in dict(meta or {}).items()
        if chave not in {"origem", "destino", "tipo", "rotulo", "from", "to", "id"}
    }
    props = {
        "tipo": tipo,
        "rotulo": TIPOS_VINCULO[tipo],
        "quando": _agora(),
        **meta_limpo,
    }
    return _gravar_aresta(origem, destino, tipo, props)


def relacionar_usuarios(
    documento_origem: str,
    documento_destino: str,
    tipo: str,
    *,
    nome_origem: str = "",
    email_origem: str = "",
    nome_destino: str = "",
    email_destino: str = "",
    meta: dict | None = None,
) -> dict:
    """Vínculo entre duas contas (ex.: Diego —esposa→ Vanessa)."""
    tipo = str(tipo or "").strip().lower()
    if tipo not in TIPOS_VINCULO:
        raise ValueError("Escolha um tipo de vínculo válido.")
    origem = garantir_usuario(documento_origem, nome_origem, email_origem)
    destino = garantir_usuario(documento_destino, nome_destino, email_destino)
    if not origem or not destino:
        raise ValueError("Não foi possível montar o vínculo entre usuários.")
    if origem == destino:
        raise ValueError("Origem e destino são a mesma conta.")
    meta_limpo = {
        chave: valor
        for chave, valor in dict(meta or {}).items()
        if chave not in {"origem", "destino", "tipo", "rotulo", "from", "to", "id"}
    }
    props = {
        "tipo": tipo,
        "rotulo": TIPOS_VINCULO.get(tipo, tipo),
        "quando": _agora(),
        "entre_usuarios": True,
        **meta_limpo,
    }
    return _gravar_aresta(origem, destino, tipo, props)


def relacionar_faces(
    face_a: str,
    face_b: str,
    tipo: str = "mesmo_individuo",
    *,
    nome_a: str = "",
    nome_b: str = "",
    classe_a: str = "",
    classe_b: str = "",
    meta: dict | None = None,
) -> dict:
    """Liga duas faces reconhecidas como o mesmo indivíduo (colaborativo entre contas)."""
    tipo = str(tipo or "mesmo_individuo").strip().lower() or "mesmo_individuo"
    if tipo not in TIPOS_VINCULO:
        raise ValueError("Escolha um tipo de vínculo válido.")
    a = str(face_a or "").strip().upper()
    b = str(face_b or "").strip().upper()
    if not a or not b or a == b:
        raise ValueError("Informe duas faces distintas.")
    # Ordem estável evita aresta duplicada invertida.
    if a > b:
        a, b = b, a
        nome_a, nome_b = nome_b, nome_a
        classe_a, classe_b = classe_b, classe_a
    origem = garantir_pessoa(a, nome_a, classe_a)
    destino = garantir_pessoa(b, nome_b, classe_b)
    meta_limpo = {
        chave: valor
        for chave, valor in dict(meta or {}).items()
        if chave not in {"origem", "destino", "tipo", "rotulo", "from", "to", "id"}
    }
    props = {
        "tipo": tipo,
        "rotulo": TIPOS_VINCULO.get(tipo, tipo),
        "quando": _agora(),
        "entre_faces": True,
        **meta_limpo,
    }
    return _gravar_aresta(origem, destino, tipo, props)


def _reparar_arestas(dados: dict) -> bool:
    """Corrige arestas em que meta.origem sobrescreveu o usuário (ex.: stive_conhece)."""
    mudou = False
    novas = []
    for a in list(dados.get("arestas") or []):
        origem = a.get("origem")
        destino = a.get("destino")
        if isinstance(origem, str) and origem.startswith(("U:", "F:")):
            novas.append(a)
            continue
        doc = _digitos(a.get("documento") or "")
        if not doc:
            usuarios = [k for k in (dados.get("nos") or {}) if str(k).startswith("U:")]
            if len(usuarios) == 1:
                doc = str(usuarios[0]).replace("U:", "", 1)
        if doc and destino:
            a = dict(a)
            a["origem"] = f"U:{doc}"
            mudou = True
            novas.append(a)
        else:
            mudou = True
    if mudou:
        dados["arestas"] = novas
    return mudou


def sincronizar_cadastros() -> None:
    """Espelha clientes/pessoas no grafo local e no Neo4j (se configurado)."""
    try:
        from cadastro import listar_clientes
    except Exception:
        return
    nos_neo: list[tuple[str, str, dict]] = []
    arestas_neo: list[tuple[str, str, str, dict]] = []
    with _TRAVA:
        dados = _ler()
        _reparar_arestas(dados)
        for cliente in listar_clientes():
            if cliente.get("ativo") is False:
                continue
            digitos = _digitos(cliente.get("documento"))
            if not digitos:
                continue
            u = f"U:{digitos}"
            props_u = {
                "documento": digitos,
                "nome": str(cliente.get("nome") or digitos),
                "email": str(cliente.get("email") or ""),
                "atualizado": _agora(),
            }
            _upsert_no_local(dados, u, "usuario", props_u)
            nos_neo.append((u, "usuario", props_u))
            foto_cli = str(cliente.get("foto_face_id") or "").strip().upper()
            if foto_cli:
                f_foto = f"F:{foto_cli}"
                props_foto = {
                    "face_id": foto_cli,
                    "nome": str(cliente.get("nome") or foto_cli),
                    "classe": "morador",
                    "documento_cliente": digitos,
                    "atualizado": _agora(),
                }
                _upsert_no_local(dados, f_foto, "pessoa", props_foto)
                nos_neo.append((f_foto, "pessoa", props_foto))
                if not any(
                    a.get("origem") == u and a.get("destino") == f_foto and a.get("tipo") == "proprio"
                    for a in dados["arestas"]
                ):
                    aresta_p = {
                        "origem": u,
                        "destino": f_foto,
                        "tipo": "proprio",
                        "rotulo": TIPOS_VINCULO["proprio"],
                        "quando": _agora(),
                        "fonte": "foto_cliente",
                    }
                    dados["arestas"].append(aresta_p)
                arestas_neo.append((u, f_foto, "proprio", {
                    "tipo": "proprio",
                    "rotulo": TIPOS_VINCULO["proprio"],
                    "fonte": "foto_cliente",
                }))
            for pessoa in cliente.get("pessoas") or []:
                face = str((pessoa or {}).get("face_id") or "").strip().upper()
                if not face:
                    continue
                f = f"F:{face}"
                props_p = {
                    "face_id": face,
                    "nome": str(pessoa.get("nome") or face),
                    "classe": str(pessoa.get("classe") or pessoa.get("base_legal") or ""),
                    "atualizado": _agora(),
                }
                if pessoa.get("eh_proprio") is True or face == foto_cli:
                    props_p["documento_cliente"] = digitos
                _upsert_no_local(dados, f, "pessoa", props_p)
                nos_neo.append((f, "pessoa", props_p))
                # Dono cadastrou a pessoa: vínculo implícito de monitoramento.
                if not any(
                    a.get("origem") == u and a.get("destino") == f and a.get("tipo") == "monitora"
                    for a in dados["arestas"]
                ):
                    dados["arestas"].append({
                        "origem": u,
                        "destino": f,
                        "tipo": "monitora",
                        "rotulo": TIPOS_VINCULO.get("monitora", "Monitora"),
                        "quando": _agora(),
                    })
                arestas_neo.append((u, f, "monitora", {
                    "tipo": "monitora",
                    "rotulo": TIPOS_VINCULO.get("monitora", "Monitora"),
                }))
        # Espelha também arestas já existentes (Stive, cruzamentos, etc.).
        for a in dados.get("arestas") or []:
            o, d, t = a.get("origem"), a.get("destino"), str(a.get("tipo") or "")
            if not o or not d or not t:
                continue
            props_a = {
                chave: valor
                for chave, valor in dict(a).items()
                if chave not in {"origem", "destino"}
            }
            arestas_neo.append((o, d, t, props_a))
        _gravar(dados)
    for no_id, rotulo, props in nos_neo:
        _neo_upsert(no_id, rotulo, props)
    for origem, destino, tipo, props in arestas_neo:
        _neo_aresta(origem, destino, tipo, props)


def _subgrafo(nos: list[dict], arestas: list[dict], foco: set[str]) -> tuple[list[dict], list[dict]]:
    """Mantém o nó foco e vizinhos ligados por qualquer aresta."""
    if not foco:
        return nos, arestas
    ligados = set(foco)
    for a in arestas:
        o, d = a.get("from"), a.get("to")
        if o in foco or d in foco:
            if o:
                ligados.add(o)
            if d:
                ligados.add(d)
    nos_f = [n for n in nos if n.get("id") in ligados]
    arestas_f = [a for a in arestas if a.get("from") in ligados and a.get("to") in ligados]
    return nos_f, arestas_f


def exportar_vis(documento: str = "", face_id: str = "") -> dict:
    """Payload para vis-network: nodes + edges. Filtros opcionais de cliente/pessoa."""
    sincronizar_cadastros()
    with _TRAVA:
        dados = _ler()
    nos = []
    for no_id, props in (dados.get("nos") or {}).items():
        rotulo = props.get("rotulo") or "No"
        nome = props.get("nome") or no_id
        cor = "#4c8dff" if rotulo == "usuario" else "#ff5c7a"
        if str(props.get("classe") or "") in {
            "comportamento_suspeito", "mandado", "ex_detento",
            "pessoa_desaparecida", "mandado_judicial",
        }:
            cor = "#ff3b3b"
        if str(props.get("classe") or "") == "medida_protetiva":
            cor = "#c084fc"
        nos.append({
            "id": no_id,
            "label": nome,
            "group": rotulo,
            "color": cor,
            "title": f"{rotulo}: {nome}",
            "face_id": props.get("face_id") or "",
            "documento": props.get("documento") or "",
            "classe": props.get("classe") or "",
        })
    cores_aresta = {
        "conhecido": "#8fa3bf",
        "amigo": "#3ddc97",
        "familiar": "#ff8c28",
        "irmao": "#ffb020",
        "pai": "#f59e0b",
        "mae": "#fb7185",
        "esposa": "#ec4899",
        "marido": "#a855f7",
        "namorado": "#e879f9",
        "primo": "#f97316",
        "tio": "#d97706",
        "vizinho": "#38bdf8",
        "colega": "#22d3ee",
        "medida_protege": "#c084fc",
        "monitora": "#64748b",
        "proprio": "#3ddc97",
        "mesmo_individuo": "#fbbf24",
        "interesse_compartilhado": "#60a5fa",
    }
    arestas = []
    contagem_tipos: dict[str, int] = {}
    for idx, a in enumerate(dados.get("arestas") or []):
        tipo_a = str(a.get("tipo") or "")
        # Corrige arestas antigas em que meta.origem sobrescreveu o usuário.
        origem_a = a.get("origem")
        if origem_a in (None, "", "stive_conhece") or (
            isinstance(origem_a, str) and not origem_a.startswith(("U:", "F:"))
        ):
            # tenta recuperar pelo documento no meta, senão descarta do desenho
            doc_meta = _digitos(a.get("documento") or "")
            origem_a = f"U:{doc_meta}" if doc_meta else None
        if not origem_a or not a.get("destino"):
            continue
        rotulo_a = a.get("rotulo") or TIPOS_VINCULO.get(tipo_a) or tipo_a or ""
        contagem_tipos[tipo_a or "outro"] = contagem_tipos.get(tipo_a or "outro", 0) + 1
        entre_usuarios = bool(a.get("entre_usuarios")) or (
            str(origem_a).startswith("U:") and str(a.get("destino") or "").startswith("U:")
        )
        arestas.append({
            "id": idx + 1,
            "from": origem_a,
            "to": a.get("destino"),
            "label": rotulo_a,
            "arrows": "to",
            "tipo": tipo_a,
            "title": f"{rotulo_a}" + (f" · {a.get('quando')}" if a.get("quando") else ""),
            "color": {"color": cores_aresta.get(tipo_a, "#7a8799"), "highlight": "#e8eefc"},
            "width": 3 if entre_usuarios or tipo_a in {"mesmo_individuo", "interesse_compartilhado"} else (
                2 if tipo_a in VINCULOS_STIVE or tipo_a in {"medida_protege", "proprio", "monitora"} else 1
            ),
            "font": {"color": cores_aresta.get(tipo_a, "#a7b3c7"), "size": 12, "strokeWidth": 0},
        })

    digitos = _digitos(documento)
    face = str(face_id or "").strip().upper()
    foco: set[str] = set()
    if digitos:
        foco.add(f"U:{digitos}")
    if face:
        foco.add(f"F:{face}")
    if foco:
        nos, arestas = _subgrafo(nos, arestas, foco)

    clientes = sorted(
        [
            {"id": n["id"], "documento": n.get("documento") or "", "nome": n.get("label") or ""}
            for n in nos if n.get("group") == "usuario" or (n.get("id") or "").startswith("U:")
        ] if not digitos else [
            {"id": f"U:{digitos}", "documento": digitos, "nome": next((n.get("label") for n in nos if n.get("id") == f"U:{digitos}"), digitos)}
        ],
        key=lambda c: (c.get("nome") or "").lower(),
    )
    # Opções de filtro: lista completa sempre (para popular selects), mesmo com subgrafo.
    todos_clientes = []
    todas_pessoas = []
    for no_id, props in (dados.get("nos") or {}).items():
        if (props.get("rotulo") == "usuario") or no_id.startswith("U:"):
            todos_clientes.append({
                "id": no_id,
                "documento": props.get("documento") or no_id.replace("U:", ""),
                "nome": props.get("nome") or no_id,
            })
        if (props.get("rotulo") == "pessoa") or no_id.startswith("F:"):
            todas_pessoas.append({
                "id": no_id,
                "face_id": props.get("face_id") or no_id.replace("F:", ""),
                "nome": props.get("nome") or no_id,
                "classe": props.get("classe") or "",
            })
    todos_clientes.sort(key=lambda c: (c.get("nome") or "").lower())
    todas_pessoas.sort(key=lambda c: (c.get("nome") or "").lower())

    # Reconta após filtro de subgrafo.
    contagem_filtrada: dict[str, int] = {}
    for a in arestas:
        tipo_a = str(a.get("tipo") or "outro")
        contagem_filtrada[tipo_a] = contagem_filtrada.get(tipo_a, 0) + 1
    resumo_vinculos = [
        {
            "tipo": tipo,
            "rotulo": TIPOS_VINCULO.get(tipo) or ("Monitora" if tipo == "monitora" else tipo),
            "total": total,
            "cor": cores_aresta.get(tipo, "#7a8799"),
        }
        for tipo, total in sorted(contagem_filtrada.items(), key=lambda item: (-item[1], item[0]))
    ]

    geo = {}
    try:
        from cadastro import indice_geo_colaborativo

        bruto_geo = indice_geo_colaborativo()
        geo = {
            "piloto_bairro": bruto_geo.get("piloto_bairro"),
            "piloto_cidade": bruto_geo.get("piloto_cidade"),
            "logradouros_stella_maris": bruto_geo.get("logradouros_stella_maris") or [],
            "total_ruas": len(bruto_geo.get("ruas") or {}),
            "total_bairros": len(bruto_geo.get("bairros") or {}),
            "ruas": {
                chave: len(itens)
                for chave, itens in (bruto_geo.get("ruas") or {}).items()
            },
            "bairros": {
                chave: len(itens)
                for chave, itens in (bruto_geo.get("bairros") or {}).items()
            },
        }
    except Exception:
        geo = {}

    return {
        "nodes": nos,
        "edges": arestas,
        "motor": "neo4j" if _neo4j() else "json",
        "tipos": dict(TIPOS_VINCULO),
        "vinculos_stive": VINCULOS_STIVE,
        "resumo_vinculos": resumo_vinculos,
        "total_nos": len(nos),
        "total_arestas": len(arestas),
        "filtro": {"documento": digitos, "face_id": face},
        "opcoes_clientes": todos_clientes,
        "opcoes_pessoas": todas_pessoas,
        "clientes_visiveis": clientes,
        "geo_colaborativo": geo,
    }
