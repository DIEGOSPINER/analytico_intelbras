"""API de ingestão C4ISTAR — recebe eventos da borda (PC do cliente)."""

from __future__ import annotations

import os
from datetime import date, datetime, time
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="C4ISTAR Ingestão", version="1.0.0")

TOKEN = (os.getenv("INGEST_TOKEN") or os.getenv("WEB_SENHA") or "").strip()


def _auth(authorization: str | None = Header(default=None), x_api_key: str | None = Header(default=None)):
    if not TOKEN:
        return
    enviado = (x_api_key or "").strip()
    if not enviado and authorization:
        esquema, _, resto = authorization.partition(" ")
        enviado = resto.strip() if esquema.lower() == "bearer" else authorization.strip()
    if enviado != TOKEN:
        raise HTTPException(status_code=401, detail="Token de ingestão inválido.")


class LoteIn(BaseModel):
    cliente_documento: str = Field(..., min_length=5)
    tabela: str
    itens: list[dict[str, Any]] = Field(default_factory=list)


TABELAS = {
    "analitico", "ocorrencias", "faces", "placas", "audio",
    "ocorrencias_informadas", "alertas_ia", "insights", "contagens",
}


def _data(valor) -> date | None:
    bruto = str(valor or "").strip()[:10]
    if len(bruto) < 10:
        return None
    try:
        return date.fromisoformat(bruto)
    except ValueError:
        return None


def _hora(valor) -> time | None:
    bruto = str(valor or "").strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(bruto[:8], fmt).time()
        except ValueError:
            continue
    return None


def _num(valor, tipo=float, padrao=0):
    try:
        return tipo(str(valor).replace(",", ".") or padrao)
    except (TypeError, ValueError):
        return padrao


@app.get("/saude")
def saude():
    return {"ok": True, "servico": "c4istar-ingestao"}


@app.post("/v1/ingestao")
def ingestao(lote: LoteIn, _=Depends(_auth)):
    tabela = (lote.tabela or "").strip().lower()
    if tabela not in TABELAS:
        raise HTTPException(status_code=400, detail=f"Tabela inválida. Use: {sorted(TABELAS)}")
    if not lote.itens:
        return {"ok": True, "inseridos": 0}

    import sys
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    if str(raiz) not in sys.path:
        sys.path.insert(0, str(raiz))
    from db.conexao import conectar

    documento = "".join(c for c in lote.cliente_documento if c.isdigit())
    inseridos = 0
    with conectar() as conn:
        cur = conn.cursor()
        for item in lote.itens[:2000]:
            try:
                if tabela == "analitico":
                    d = _data(item.get("data") or item.get("Data"))
                    if not d:
                        continue
                    cur.execute(
                        """INSERT INTO analitico
                        (cliente_documento, data, hora, camera, categoria, classe, track_id, total_unicos, qtd_cena)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            documento, d, _hora(item.get("hora") or item.get("Hora")),
                            item.get("camera") or item.get("Camera") or "",
                            item.get("categoria") or item.get("Categoria") or "",
                            item.get("classe") or item.get("Classe") or "",
                            str(item.get("track_id") or item.get("ID") or ""),
                            _num(item.get("total_unicos") or item.get("Total_Unicos_Categoria"), int),
                            _num(item.get("qtd_cena") or item.get("Quantidade_Categoria_Na_Cena"), int),
                        ),
                    )
                elif tabela == "ocorrencias":
                    d = _data(item.get("data") or item.get("Data"))
                    if not d:
                        continue
                    cur.execute(
                        """INSERT INTO ocorrencias
                        (cliente_documento, data, hora, camera, categoria, classe, track_id, total_unicos, qtd_cena,
                         id_alvo, duracao_segundos, confianca, status, pessoas_envolvidas, detalhe, risco, nivel_risco, qualidade_pose)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            documento, d, _hora(item.get("hora") or item.get("Hora")),
                            item.get("camera") or item.get("Camera") or "",
                            item.get("categoria") or item.get("Categoria") or "",
                            item.get("classe") or item.get("Classe") or "",
                            str(item.get("track_id") or item.get("ID") or ""),
                            _num(item.get("total_unicos") or item.get("Total_Unicos_Categoria"), int),
                            _num(item.get("qtd_cena") or item.get("Quantidade_Categoria_Na_Cena"), int),
                            str(item.get("id_alvo") or item.get("ID_Alvo") or ""),
                            _num(item.get("duracao_segundos") or item.get("Duracao_Segundos")),
                            _num(item.get("confianca") or item.get("Confianca")),
                            item.get("status") or item.get("Status") or "",
                            _num(item.get("pessoas_envolvidas") or item.get("Pessoas_Envolvidas"), int),
                            item.get("detalhe") or item.get("Detalhe") or "",
                            item.get("risco") or item.get("Risco") or "",
                            _num(item.get("nivel_risco") or item.get("Nivel_Risco"), int, 1),
                            _num(item.get("qualidade_pose") or item.get("Qualidade_Pose")),
                        ),
                    )
                elif tabela == "faces":
                    d = _data(item.get("data") or item.get("Data"))
                    if not d:
                        continue
                    cur.execute(
                        """INSERT INTO faces
                        (cliente_documento, data, hora, camera, face_id, evento, total_passagens, track_id,
                         confianca, proximidade, caminho_foto, foto_referencia)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            documento, d, _hora(item.get("hora") or item.get("Hora")),
                            item.get("camera") or item.get("Camera") or "",
                            str(item.get("face_id") or item.get("Face_ID") or "").upper(),
                            item.get("evento") or item.get("Evento") or "",
                            _num(item.get("total_passagens") or item.get("Total_Passagens"), int),
                            str(item.get("track_id") or item.get("Track_ID") or ""),
                            _num(item.get("confianca") or item.get("Confianca")),
                            _num(item.get("proximidade") or item.get("Proximidade")),
                            item.get("caminho_foto") or item.get("Caminho_Foto") or "",
                            item.get("foto_referencia") or item.get("Foto_Referencia") or "",
                        ),
                    )
                elif tabela == "placas":
                    d = _data(item.get("data") or item.get("Data"))
                    if not d:
                        continue
                    cur.execute(
                        """INSERT INTO placas
                        (cliente_documento, data, hora, camera, placa_id, placa, evento, total_passagens,
                         track_id_veiculo, tipo_veiculo, confianca, caminho_foto, foto_referencia)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            documento, d, _hora(item.get("hora") or item.get("Hora")),
                            item.get("camera") or item.get("Camera") or "",
                            str(item.get("placa_id") or item.get("Placa_ID") or ""),
                            str(item.get("placa") or item.get("Placa") or "").upper(),
                            item.get("evento") or item.get("Evento") or "",
                            _num(item.get("total_passagens") or item.get("Total_Passagens"), int),
                            str(item.get("track_id_veiculo") or item.get("Track_ID_Veiculo") or ""),
                            item.get("tipo_veiculo") or item.get("Tipo_Veiculo") or "",
                            _num(item.get("confianca") or item.get("Confianca")),
                            item.get("caminho_foto") or item.get("Caminho_Foto") or "",
                            item.get("foto_referencia") or item.get("Foto_Referencia") or "",
                        ),
                    )
                elif tabela == "audio":
                    d = _data(item.get("data") or item.get("Data"))
                    if not d:
                        continue
                    cur.execute(
                        """INSERT INTO audio
                        (cliente_documento, data, hora, camera, tipo, categoria, nivel, texto, palavras, confianca, detalhe)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            documento, d, _hora(item.get("hora") or item.get("Hora")),
                            item.get("camera") or item.get("Camera") or "",
                            item.get("tipo") or item.get("Tipo") or "",
                            item.get("categoria") or item.get("Categoria") or "",
                            _num(item.get("nivel") or item.get("Nivel"), int),
                            item.get("texto") or item.get("Texto") or "",
                            item.get("palavras") or item.get("Palavras") or "",
                            _num(item.get("confianca") or item.get("Confianca")),
                            item.get("detalhe") or item.get("Detalhe") or "",
                        ),
                    )
                elif tabela == "contagens":
                    d = _data(item.get("data") or item.get("Data"))
                    if not d:
                        continue
                    cur.execute(
                        """INSERT INTO contagens (cliente_documento, data, hora, camera, pessoas, veiculos)
                        VALUES (%s,%s,%s,%s,%s,%s)""",
                        (
                            documento, d, _hora(item.get("hora") or item.get("Hora")),
                            item.get("camera") or item.get("Camera") or "",
                            _num(item.get("pessoas") or item.get("Pessoas"), int),
                            _num(item.get("veiculos") or item.get("Veiculos"), int),
                        ),
                    )
                else:
                    continue
                inseridos += 1
            except Exception:
                continue
        cur.execute(
            """INSERT INTO ingestao_lote (cliente_documento, origem, tabela, quantidade)
            VALUES (%s,'borda',%s,%s)""",
            (documento, tabela, inseridos),
        )
        cur.execute(
            """INSERT INTO clientes (documento, nome) VALUES (%s,%s)
            ON CONFLICT (documento) DO UPDATE SET atualizado_em = NOW()""",
            (documento, documento),
        )
    return {"ok": True, "tabela": tabela, "inseridos": inseridos}
