"""CRUD Postgres das operações do analítico (gravação em tempo real)."""

from __future__ import annotations

from datetime import date, datetime, time

from db.conexao import cliente_padrao, conectar, disponivel

_AVISOU = False


def _ok() -> bool:
    global _AVISOU
    try:
        if disponivel():
            return True
    except Exception:
        pass
    if not _AVISOU:
        print("Postgres indisponível: seguindo só com CSV.")
        _AVISOU = True
    return False


def _agora():
    agora = datetime.now()
    return agora.date(), agora.time().replace(microsecond=0)


def _doc(documento: str = "") -> str:
    return "".join(c for c in str(documento or cliente_padrao() or "") if c.isdigit())


def inserir_analitico(camera, categoria, classe, track_id, total_unicos, qtd_cena, documento=""):
    if not _ok():
        return False
    data, hora = _agora()
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO analitico
                (cliente_documento, data, hora, camera, categoria, classe, track_id, total_unicos, qtd_cena)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (_doc(documento), data, hora, camera or "", categoria or "", classe or "",
                 str(track_id or ""), int(total_unicos or 0), int(qtd_cena or 0)),
            )
    return True


def inserir_ocorrencia(
    camera, categoria, classe, track_id, total_unicos, qtd_cena,
    id_alvo="", duracao=0, confianca=0, status="", pessoas_envolvidas=0,
    detalhe="", risco="", nivel_risco=1, qualidade_pose=0.0, documento="",
):
    if not _ok():
        return False
    data, hora = _agora()
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ocorrencias
                (cliente_documento, data, hora, camera, categoria, classe, track_id, total_unicos, qtd_cena,
                 id_alvo, duracao_segundos, confianca, status, pessoas_envolvidas, detalhe, risco, nivel_risco, qualidade_pose)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    _doc(documento), data, hora, camera or "", categoria or "", classe or "",
                    str(track_id or ""), int(total_unicos or 0), int(qtd_cena or 0),
                    str(id_alvo or ""), float(duracao or 0), float(confianca or 0),
                    status or "", int(pessoas_envolvidas or 0), detalhe or "",
                    risco or "", int(nivel_risco or 1), float(qualidade_pose or 0),
                ),
            )
    return True


def inserir_face(registro: dict, documento=""):
    if not _ok():
        return False
    data, hora = _agora()
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO faces
                (cliente_documento, data, hora, camera, face_id, evento, total_passagens, track_id,
                 confianca, proximidade, caminho_foto, foto_referencia)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    _doc(documento), data, hora,
                    registro.get("camera") or "",
                    str(registro.get("face_id") or "").upper(),
                    registro.get("evento") or "",
                    int(registro.get("total_passagens") or 1),
                    str(registro.get("track_id") or ""),
                    float(registro.get("confianca") or 0),
                    float(registro.get("proximidade") or 0),
                    registro.get("caminho_foto") or "",
                    registro.get("foto_referencia") or "",
                ),
            )
    return True


def inserir_placa(registro: dict, documento=""):
    if not _ok():
        return False
    data, hora = _agora()
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO placas
                (cliente_documento, data, hora, camera, placa_id, placa, evento, total_passagens,
                 track_id_veiculo, tipo_veiculo, confianca, caminho_foto, foto_referencia)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    _doc(documento), data, hora,
                    registro.get("camera") or "",
                    str(registro.get("placa_id") or ""),
                    str(registro.get("placa") or "").upper(),
                    registro.get("evento") or "",
                    int(registro.get("total_passagens") or 1),
                    str(registro.get("track_id") or ""),
                    registro.get("tipo_veiculo") or "",
                    float(registro.get("confianca") or 0),
                    registro.get("caminho_foto") or "",
                    registro.get("foto_referencia") or "",
                ),
            )
    return True


def inserir_audio(
    camera, tipo="", categoria="", nivel=0, texto="", palavras="", confianca=0.0, detalhe="", documento="",
):
    if not _ok():
        return False
    data, hora = _agora()
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO audio
                (cliente_documento, data, hora, camera, tipo, categoria, nivel, texto, palavras, confianca, detalhe)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    _doc(documento), data, hora, camera or "", tipo or "", categoria or "",
                    int(nivel or 0), texto or "", palavras or "", float(confianca or 0), detalhe or "",
                ),
            )
    return True
