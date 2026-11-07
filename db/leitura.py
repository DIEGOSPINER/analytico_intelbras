"""Leituras do Postgres para o portal (preferência sobre CSV)."""

from __future__ import annotations

from db.conexao import cliente_padrao, conectar, disponivel


def _doc(documento: str = "") -> str:
    return "".join(c for c in str(documento or cliente_padrao() or "") if c.isdigit())


def contagem_faces(face_ids: set[str] | list[str] | None = None, documento: str = "") -> list[tuple[str, int]]:
    if not disponivel():
        return []
    ids = {str(i).upper() for i in (face_ids or []) if i}
    with conectar() as conn:
        with conn.cursor() as cur:
            if ids:
                cur.execute(
                    """SELECT face_id, COUNT(*)::int
                       FROM faces
                       WHERE (%s = '' OR cliente_documento = %s OR cliente_documento = '')
                         AND face_id = ANY(%s)
                       GROUP BY face_id
                       ORDER BY COUNT(*) DESC, face_id""",
                    (_doc(documento), _doc(documento), list(ids)),
                )
            else:
                cur.execute(
                    """SELECT face_id, COUNT(*)::int
                       FROM faces
                       WHERE (%s = '' OR cliente_documento = %s OR cliente_documento = '')
                       GROUP BY face_id
                       ORDER BY COUNT(*) DESC, face_id
                       LIMIT 200""",
                    (_doc(documento), _doc(documento)),
                )
            return [(str(r[0]), int(r[1])) for r in cur.fetchall()]


def rastros_faces(face_ids: dict[str, str], locais: dict, documento: str = "", limite: int = 240) -> list[dict]:
    """Rastros georreferenciados para o mapa RF/LPR."""
    if not disponivel() or not face_ids:
        return []
    ids = list(face_ids.keys())
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT face_id, camera, data, hora, caminho_foto, foto_referencia
                   FROM faces
                   WHERE (%s = '' OR cliente_documento = %s OR cliente_documento = '')
                     AND face_id = ANY(%s)
                   ORDER BY data, hora
                   LIMIT %s""",
                (_doc(documento), _doc(documento), ids, max(limite * 3, 500)),
            )
            linhas = cur.fetchall()
    rastros = []
    for face_id, camera, data, hora, caminho, ref in linhas:
        camera = str(camera or "").strip()
        local = locais.get(camera.lower()) or {}
        lat, lon = local.get("latitude"), local.get("longitude")
        if lat is None or lon is None:
            continue
        ident = str(face_id or "").upper()
        rastros.append({
            "id": ident,
            "nome": face_ids.get(ident) or ident,
            "camera": camera,
            "quando": f"{data or ''} {hora or ''}".strip(),
            "lat": float(lat),
            "lon": float(lon),
            "foto": f"/rosto/{ident}.jpg",
            "caminho_foto": caminho or "",
            "foto_referencia": ref or "",
            "valor": 1,
        })
    return rastros[-limite:]


def historico_matches(face_ids: set[str] | None = None, documento: str = "", limite: int = 40) -> list[dict]:
    """Últimos alertas de face/placa para a tela de Alertas."""
    if not disponivel():
        return []
    ids = {str(i).upper() for i in (face_ids or []) if i}
    saida = []
    with conectar() as conn:
        with conn.cursor() as cur:
            if ids:
                cur.execute(
                    """SELECT data, hora, camera, face_id, evento, total_passagens, confianca
                       FROM faces
                       WHERE (%s = '' OR cliente_documento = %s OR cliente_documento = '')
                         AND face_id = ANY(%s)
                       ORDER BY data DESC, hora DESC
                       LIMIT %s""",
                    (_doc(documento), _doc(documento), list(ids), limite),
                )
            else:
                cur.execute(
                    """SELECT data, hora, camera, face_id, evento, total_passagens, confianca
                       FROM faces
                       WHERE (%s = '' OR cliente_documento = %s OR cliente_documento = '')
                       ORDER BY data DESC, hora DESC
                       LIMIT %s""",
                    (_doc(documento), _doc(documento), limite),
                )
            for data, hora, camera, face_id, evento, passagens, conf in cur.fetchall():
                saida.append({
                    "quando": f"{data or ''} {hora or ''}".strip(),
                    "tipo": "FACE",
                    "id": str(face_id or "").upper(),
                    "nome": "",
                    "camera": camera or "",
                    "rotulo": evento or "FACE",
                    "taxa": float(conf or 0),
                    "ref": f"/rosto/{str(face_id or '').upper()}.jpg",
                    "agora": f"/rosto/{str(face_id or '').upper()}.jpg",
                })
            cur.execute(
                """SELECT data, hora, camera, placa, evento, total_passagens, confianca
                   FROM placas
                   WHERE (%s = '' OR cliente_documento = %s OR cliente_documento = '')
                   ORDER BY data DESC, hora DESC
                   LIMIT %s""",
                (_doc(documento), _doc(documento), max(10, limite // 2)),
            )
            for data, hora, camera, placa, evento, passagens, conf in cur.fetchall():
                saida.append({
                    "quando": f"{data or ''} {hora or ''}".strip(),
                    "tipo": "PLACA",
                    "id": str(placa or "").upper(),
                    "nome": str(placa or "").upper(),
                    "camera": camera or "",
                    "rotulo": evento or "PLACA",
                    "taxa": float(conf or 0),
                    "ref": "",
                    "agora": "",
                })
    saida.sort(key=lambda item: str(item.get("quando") or ""), reverse=True)
    return saida[:limite]


def audio_esteira(documento: str = "", limite: int = 80) -> list[dict]:
    if not disponivel():
        return []
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT data, hora, camera, tipo, categoria, nivel, texto, palavras, confianca, detalhe
                   FROM audio
                   WHERE (%s = '' OR cliente_documento = %s OR cliente_documento = '')
                   ORDER BY data DESC, hora DESC
                   LIMIT %s""",
                (_doc(documento), _doc(documento), limite),
            )
            linhas = cur.fetchall()
    esteira = []
    for data, hora, camera, tipo, categoria, nivel, texto, palavras, conf, detalhe in linhas:
        nivel_i = int(nivel or 0)
        esteira.append({
            "quando": f"{data or ''} {hora or ''}".strip(),
            "camera": camera or "",
            "tipo": tipo or "",
            "categoria": categoria or "",
            "nivel": nivel_i,
            "texto": texto or "",
            "palavras": [p.strip() for p in str(palavras or "").split(",") if p.strip()],
            "confianca": float(conf or 0),
            "detalhe": detalhe or "",
            "risco": nivel_i >= 2,
        })
    return esteira
