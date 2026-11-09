"""Registro e resumo de custos de mensagens (e-mail, WhatsApp, OpenAI)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from db.conexao import cliente_padrao, conectar, disponivel


def _doc(documento: str = "") -> str:
    return "".join(c for c in str(documento or "") if c.isdigit()) or ""


def _doc_ou_padrao(documento: str = "") -> str:
    return _doc(documento) or _doc(cliente_padrao() or "")


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
                    _doc_ou_padrao(documento),
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
    digitos = _doc(documento)
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
                   WHERE (%s = '' OR cliente_documento = %s)
                     AND EXTRACT(YEAR FROM quando) = %s
                     AND EXTRACT(MONTH FROM quando) = %s
                   GROUP BY canal, direcao
                   ORDER BY canal, direcao""",
                (digitos, digitos, ano, mes),
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


def _serie_vazia(dias: int) -> list[dict]:
    hoje = date.today()
    return [
        {"rotulo": (hoje - timedelta(days=i)).strftime("%d/%m"), "dia": (hoje - timedelta(days=i)).isoformat(), "valor": 0.0}
        for i in range(dias - 1, -1, -1)
    ]


def serie_diaria(documento: str = "", canal: str = "", dias: int = 30, metrica: str = "usd") -> list[dict]:
    """Série diária de USD ou unidades (tokens/chamadas) para o monitor financeiro."""
    digitos = _doc(documento)
    dias = max(7, min(int(dias or 30), 120))
    campo = "COALESCE(SUM(unidades),0)" if metrica == "unidades" else "COALESCE(SUM(usd_estimado),0)"
    if not disponivel():
        return _serie_vazia(dias)
    inicio = date.today() - timedelta(days=dias - 1)
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT (quando AT TIME ZONE 'UTC')::date AS dia,
                           {campo}::float
                    FROM custos_mensagens
                    WHERE (%s = '' OR cliente_documento = %s)
                      AND (%s = '' OR lower(canal) = lower(%s) OR (lower(%s) = 'openai' AND lower(canal) IN ('openai','stive')))
                      AND quando >= %s
                    GROUP BY 1
                    ORDER BY 1""",
                (digitos, digitos, canal, canal, canal, datetime.combine(inicio, datetime.min.time(), tzinfo=timezone.utc)),
            )
            mapa = {str(dia): float(valor or 0) for dia, valor in cur.fetchall()}
    saida = []
    for i in range(dias - 1, -1, -1):
        dia = date.today() - timedelta(days=i)
        chave = dia.isoformat()
        saida.append({
            "rotulo": dia.strftime("%d/%m"),
            "dia": chave,
            "valor": round(float(mapa.get(chave) or 0), 4),
        })
    return saida


def por_cliente(ano: int | None = None, mes: int | None = None, canal: str = "") -> list[dict]:
    agora = datetime.now(timezone.utc)
    ano = int(ano or agora.year)
    mes = int(mes or agora.month)
    if not disponivel():
        return []
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COALESCE(NULLIF(cliente_documento,''), '(sem documento)') AS doc,
                          COUNT(*)::int,
                          COALESCE(SUM(unidades),0)::float,
                          COALESCE(SUM(usd_estimado),0)::float
                   FROM custos_mensagens
                   WHERE EXTRACT(YEAR FROM quando) = %s
                     AND EXTRACT(MONTH FROM quando) = %s
                     AND (%s = '' OR lower(canal) = lower(%s) OR (lower(%s) = 'openai' AND lower(canal) IN ('openai','stive')))
                   GROUP BY 1
                   ORDER BY 4 DESC, 1""",
                (ano, mes, canal, canal, canal),
            )
            linhas = cur.fetchall()
    return [
        {
            "documento": str(doc or ""),
            "mensagens": int(qtd or 0),
            "unidades": round(float(unidades or 0), 4),
            "usd": round(float(usd or 0), 4),
        }
        for doc, qtd, unidades, usd in linhas
    ]


def monitor_financeiro(documento: str = "", dias: int = 30) -> dict:
    """Pacote para a tela admin: GPT geral e por cliente + totais do mês."""
    agora = datetime.now(timezone.utc)
    digitos = _doc(documento)
    mensal = resumo_mensal(digitos, agora.year, agora.month)
    openai = [i for i in mensal.get("itens") or [] if str(i.get("canal") or "").lower() in ("openai", "stive")]
    tokens_mes = round(sum(float(i.get("unidades") or 0) for i in openai), 4)
    usd_openai_mes = round(sum(float(i.get("usd") or 0) for i in openai), 4)
    return {
        "ano": mensal.get("ano"),
        "mes": mensal.get("mes"),
        "filtro_documento": digitos,
        "total_usd_mes": mensal.get("total_usd") or 0.0,
        "openai_usd_mes": usd_openai_mes,
        "openai_tokens_mes": tokens_mes,
        "itens_mes": mensal.get("itens") or [],
        "gpt_usd_diario": serie_diaria(digitos, canal="openai", dias=dias, metrica="usd"),
        "gpt_tokens_diario": serie_diaria(digitos, canal="openai", dias=dias, metrica="unidades"),
        "por_cliente_mes": [] if digitos else por_cliente(agora.year, agora.month, canal="openai"),
        "todos_canais_por_cliente": [] if digitos else por_cliente(agora.year, agora.month, canal=""),
    }
