"""Registro e resumo de custos de mensagens (e-mail, WhatsApp, OpenAI)."""

from __future__ import annotations

from datetime import datetime, timezone

from db.conexao import cliente_padrao, conectar, disponivel


def _doc(documento: str = "") -> str:
    return "".join(c for c in str(documento or cliente_padrao() or "") if c.isdigit())


def registrar(
    canal: str,
    direcao: str,
    usd_estimado: float,
    unidades: float = 1.0,
    detalhe: str = "",
    referencia: str = "",
    documento: str = "",
) -> bool:
    if not disponivel():
        return False
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO custos_mensagens
                   (cliente_documento, canal, direcao, unidades, usd_estimado, detalhe, referencia)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    _doc(documento),
                    str(canal or "")[:40],
                    str(direcao or "")[:20],
                    float(unidades or 0),
                    float(usd_estimado or 0),
                    str(detalhe or "")[:500],
                    str(referencia or "")[:120],
                ),
            )
    return True


def resumo_mensal(documento: str = "", ano: int | None = None, mes: int | None = None) -> dict:
    agora = datetime.now(timezone.utc)
    ano = int(ano or agora.year)
    mes = int(mes or agora.month)
    if not disponivel():
        return {"ano": ano, "mes": mes, "itens": [], "total_usd": 0.0}
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT canal, direcao,
                          COUNT(*)::int,
                          COALESCE(SUM(unidades),0)::float,
                          COALESCE(SUM(usd_estimado),0)::float
                   FROM custos_mensagens
                   WHERE (%s = '' OR cliente_documento = %s OR cliente_documento = '')
                     AND EXTRACT(YEAR FROM quando) = %s
                     AND EXTRACT(MONTH FROM quando) = %s
                   GROUP BY canal, direcao
                   ORDER BY canal, direcao""",
                (_doc(documento), _doc(documento), ano, mes),
            )
            linhas = cur.fetchall()
    itens = [
        {
            "canal": canal,
            "direcao": direcao,
            "mensagens": int(qtd),
            "unidades": float(unidades),
            "usd": round(float(usd), 4),
        }
        for canal, direcao, qtd, unidades, usd in linhas
    ]
    total = round(sum(i["usd"] for i in itens), 4)
    return {"ano": ano, "mes": mes, "itens": itens, "total_usd": total}
