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
    "vizinho": "Vizinho(a)",
    "colega": "Colega",
    "medida_protege": "Medida protetiva (protege)",
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


def garantir_pessoa(face_id: str, nome: str = "", classe: str = "") -> str:
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
    with _TRAVA:
        dados = _ler()
        _upsert_no_local(dados, no_id, "pessoa", props)
        _gravar(dados)
    _neo_upsert(no_id, "pessoa", props)
    return no_id


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
    destino = garantir_pessoa(face_id, nome_pessoa, classe)
    if not origem or not destino:
        raise ValueError("Não foi possível montar o vínculo.")
    props = {
        "tipo": tipo,
        "rotulo": TIPOS_VINCULO[tipo],
        "quando": _agora(),
        **(meta or {}),
    }
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
        aresta = {"origem": origem, "destino": destino, "tipo": tipo, **props}
        restantes.append(aresta)
        dados["arestas"] = restantes[-2000:]
        _gravar(dados)
    _neo_aresta(origem, destino, tipo, props)
    return aresta


def sincronizar_cadastros() -> None:
    """Espelha clientes/pessoas no grafo local."""
    try:
        from cadastro import listar_clientes
    except Exception:
        return
    with _TRAVA:
        dados = _ler()
        for cliente in listar_clientes():
            if cliente.get("ativo") is False:
                continue
            digitos = _digitos(cliente.get("documento"))
            if not digitos:
                continue
            u = f"U:{digitos}"
            _upsert_no_local(dados, u, "usuario", {
                "documento": digitos,
                "nome": str(cliente.get("nome") or digitos),
                "email": str(cliente.get("email") or ""),
                "atualizado": _agora(),
            })
            for pessoa in cliente.get("pessoas") or []:
                face = str((pessoa or {}).get("face_id") or "").strip().upper()
                if not face:
                    continue
                f = f"F:{face}"
                _upsert_no_local(dados, f, "pessoa", {
                    "face_id": face,
                    "nome": str(pessoa.get("nome") or face),
                    "classe": str(pessoa.get("classe") or pessoa.get("base_legal") or ""),
                    "atualizado": _agora(),
                })
                # Dono cadastrou a pessoa: vínculo implícito de monitoramento.
                if not any(
                    a.get("origem") == u and a.get("destino") == f and a.get("tipo") == "monitora"
                    for a in dados["arestas"]
                ):
                    dados["arestas"].append({
                        "origem": u,
                        "destino": f,
                        "tipo": "monitora",
                        "rotulo": "Monitora",
                        "quando": _agora(),
                    })
        _gravar(dados)


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
    arestas = []
    for idx, a in enumerate(dados.get("arestas") or []):
        arestas.append({
            "id": idx + 1,
            "from": a.get("origem"),
            "to": a.get("destino"),
            "label": a.get("rotulo") or a.get("tipo") or "",
            "arrows": "to",
            "tipo": a.get("tipo") or "",
            "title": a.get("rotulo") or a.get("tipo") or "",
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

    return {
        "nodes": nos,
        "edges": arestas,
        "motor": "neo4j" if _neo4j() else "json",
        "tipos": TIPOS_VINCULO,
        "total_nos": len(nos),
        "total_arestas": len(arestas),
        "filtro": {"documento": digitos, "face_id": face},
        "opcoes_clientes": todos_clientes,
        "opcoes_pessoas": todas_pessoas,
        "clientes_visiveis": clientes,
    }
