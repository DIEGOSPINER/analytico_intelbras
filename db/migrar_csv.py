"""Carga dos CSVs históricos para o Postgres."""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, time
from pathlib import Path

from db.conexao import aplicar_schema, cliente_padrao, conectar, disponivel

PASTA = Path(".")


def _sep(caminho: Path) -> str:
    amostra = caminho.read_text(encoding="utf-8-sig", errors="replace")[:400]
    return ";" if amostra.count(";") >= amostra.count(",") else ","


def _ler(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo, delimiter=_sep(caminho)))


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
    if not bruto:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(bruto[:8], fmt).time()
        except ValueError:
            continue
    return None


def _int(valor, padrao=0) -> int:
    try:
        return int(float(str(valor).replace(",", ".") or padrao))
    except (TypeError, ValueError):
        return padrao


def _float(valor, padrao=0.0) -> float:
    try:
        return float(str(valor).replace(",", ".") or padrao)
    except (TypeError, ValueError):
        return padrao


def _cli(linha: dict, padrao: str) -> str:
    digitos = "".join(c for c in str(linha.get("Cliente_Documento") or linha.get("cliente_documento") or "") if c.isdigit())
    return digitos or padrao


def carregar(pasta: Path | None = None, documento: str = "") -> dict:
    if not disponivel():
        raise RuntimeError("Postgres indisponível. Suba o docker-compose ou configure DATABASE_URL.")
    raiz = Path(pasta or PASTA)
    padrao = documento or cliente_padrao()
    aplicar_schema()
    totais = {}

    with conectar() as conn:
        cur = conn.cursor()

        # analitico
        n = 0
        for linha in _ler(raiz / "historico_analitico.csv"):
            d = _data(linha.get("Data"))
            if not d:
                continue
            cur.execute(
                """INSERT INTO analitico
                (cliente_documento, data, hora, camera, categoria, classe, track_id, total_unicos, qtd_cena)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    _cli(linha, padrao), d, _hora(linha.get("Hora")),
                    linha.get("Camera") or "", linha.get("Categoria") or "", linha.get("Classe") or "",
                    str(linha.get("ID") or ""), _int(linha.get("Total_Unicos_Categoria")),
                    _int(linha.get("Quantidade_Categoria_Na_Cena")),
                ),
            )
            n += 1
        totais["analitico"] = n

        n = 0
        for linha in _ler(raiz / "historico_ocorrencias.csv"):
            d = _data(linha.get("Data"))
            if not d:
                continue
            cur.execute(
                """INSERT INTO ocorrencias
                (cliente_documento, data, hora, camera, categoria, classe, track_id, total_unicos, qtd_cena,
                 id_alvo, duracao_segundos, confianca, status, pessoas_envolvidas, detalhe, risco, nivel_risco, qualidade_pose)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    _cli(linha, padrao), d, _hora(linha.get("Hora")),
                    linha.get("Camera") or "", linha.get("Categoria") or "", linha.get("Classe") or "",
                    str(linha.get("ID") or ""), _int(linha.get("Total_Unicos_Categoria")),
                    _int(linha.get("Quantidade_Categoria_Na_Cena")), str(linha.get("ID_Alvo") or ""),
                    _float(linha.get("Duracao_Segundos")), _float(linha.get("Confianca")),
                    linha.get("Status") or "", _int(linha.get("Pessoas_Envolvidas")),
                    linha.get("Detalhe") or "", linha.get("Risco") or "",
                    _int(linha.get("Nivel_Risco"), 1), _float(linha.get("Qualidade_Pose")),
                ),
            )
            n += 1
        totais["ocorrencias"] = n

        n = 0
        for linha in _ler(raiz / "historico_faces.csv"):
            d = _data(linha.get("Data"))
            if not d:
                continue
            cur.execute(
                """INSERT INTO faces
                (cliente_documento, data, hora, camera, face_id, evento, total_passagens, track_id,
                 confianca, proximidade, caminho_foto, foto_referencia)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    _cli(linha, padrao), d, _hora(linha.get("Hora")), linha.get("Camera") or "",
                    str(linha.get("Face_ID") or "").upper(), linha.get("Evento") or "",
                    _int(linha.get("Total_Passagens")), str(linha.get("Track_ID") or ""),
                    _float(linha.get("Confianca")), _float(linha.get("Proximidade")),
                    linha.get("Caminho_Foto") or "", linha.get("Foto_Referencia") or "",
                ),
            )
            n += 1
        totais["faces"] = n

        n = 0
        for linha in _ler(raiz / "historico_placas.csv"):
            d = _data(linha.get("Data"))
            if not d:
                continue
            cur.execute(
                """INSERT INTO placas
                (cliente_documento, data, hora, camera, placa_id, placa, evento, total_passagens,
                 track_id_veiculo, tipo_veiculo, confianca, caminho_foto, foto_referencia)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    _cli(linha, padrao), d, _hora(linha.get("Hora")), linha.get("Camera") or "",
                    str(linha.get("Placa_ID") or ""), str(linha.get("Placa") or "").upper(),
                    linha.get("Evento") or "", _int(linha.get("Total_Passagens")),
                    str(linha.get("Track_ID_Veiculo") or ""), linha.get("Tipo_Veiculo") or "",
                    _float(linha.get("Confianca")), linha.get("Caminho_Foto") or "",
                    linha.get("Foto_Referencia") or "",
                ),
            )
            n += 1
        totais["placas"] = n

        n = 0
        for linha in _ler(raiz / "historico_audio.csv"):
            d = _data(linha.get("Data"))
            if not d:
                continue
            cur.execute(
                """INSERT INTO audio
                (cliente_documento, data, hora, camera, tipo, categoria, nivel, texto, palavras, confianca, detalhe)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    _cli(linha, padrao), d, _hora(linha.get("Hora")), linha.get("Camera") or "",
                    linha.get("Tipo") or "", linha.get("Categoria") or "", _int(linha.get("Nivel")),
                    linha.get("Texto") or "", linha.get("Palavras") or "",
                    _float(linha.get("Confianca")), linha.get("Detalhe") or "",
                ),
            )
            n += 1
        totais["audio"] = n

        n = 0
        for linha in _ler(raiz / "historico_ocorrencias_informadas.csv"):
            cur.execute(
                """INSERT INTO ocorrencias_informadas
                (cliente_documento, id_externo, data, hora, natureza, descricao, endereco, latitude, longitude,
                 placa, pessoa, pessoas_ligadas, veiculos_ligados, situacoes, foto, video)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    _cli(linha, padrao), str(linha.get("Id") or ""),
                    _data(linha.get("Data")), _hora(linha.get("Hora")),
                    linha.get("Natureza") or "", linha.get("Descricao") or "", linha.get("Endereco") or "",
                    _float(linha.get("Latitude")) if str(linha.get("Latitude") or "").strip() else None,
                    _float(linha.get("Longitude")) if str(linha.get("Longitude") or "").strip() else None,
                    linha.get("Placa") or "", linha.get("Pessoa") or "",
                    linha.get("Pessoas_Ligadas") or "", linha.get("Veiculos_Ligados") or "",
                    linha.get("Situacoes") or "", linha.get("Foto") or "", linha.get("Video") or "",
                ),
            )
            n += 1
        totais["ocorrencias_informadas"] = n

        n = 0
        for linha in _ler(raiz / "historico_alertas_ia.csv"):
            cur.execute(
                """INSERT INTO alertas_ia
                (cliente_documento, data_geracao, hora_geracao, data_evento, hora_evento, origem, tipo, ident,
                 nome, motivo, camera, evento, passagens, nivel, descricao, foto, modelo, arquivo_relatorio)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    _cli(linha, padrao), _data(linha.get("Data_Geracao")), _hora(linha.get("Hora_Geracao")),
                    _data(linha.get("Data_Evento")), _hora(linha.get("Hora_Evento")),
                    linha.get("Origem") or "", linha.get("Tipo") or "", str(linha.get("ID") or ""),
                    linha.get("Nome") or "", linha.get("Motivo") or "", linha.get("Camera") or "",
                    linha.get("Evento") or "", str(linha.get("Passagens") or ""), str(linha.get("Nivel") or ""),
                    linha.get("Descricao") or "", linha.get("Foto") or "", linha.get("Modelo") or "",
                    linha.get("Arquivo_Relatorio") or "",
                ),
            )
            n += 1
        totais["alertas_ia"] = n

        n = 0
        for linha in _ler(raiz / "historico_insights.csv"):
            cur.execute(
                """INSERT INTO insights
                (cliente_documento, data_geracao, hora_geracao, periodo, inicio_periodo, fim_periodo,
                 tipo, nome, valor, descricao, nivel, modelo, arquivo_relatorio)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    _cli(linha, padrao), _data(linha.get("Data_Geracao")), _hora(linha.get("Hora_Geracao")),
                    linha.get("Periodo") or "", _data(linha.get("Inicio_Periodo")), _data(linha.get("Fim_Periodo")),
                    linha.get("Tipo") or "", linha.get("Nome") or "", str(linha.get("Valor") or ""),
                    linha.get("Descricao") or "", linha.get("Nivel") or "", linha.get("Modelo") or "",
                    linha.get("Arquivo_Relatorio") or "",
                ),
            )
            n += 1
        totais["insights"] = n

        n = 0
        for linha in _ler(raiz / "historico_contagem.csv"):
            d = _data(linha.get("Data"))
            if not d:
                continue
            cur.execute(
                """INSERT INTO contagens (cliente_documento, data, hora, camera, pessoas, veiculos)
                VALUES (%s,%s,%s,%s,%s,%s)""",
                (
                    _cli(linha, padrao), d, _hora(linha.get("Hora")), linha.get("Camera") or "",
                    _int(linha.get("Pessoas")), _int(linha.get("Veiculos")),
                ),
            )
            n += 1
        totais["contagens"] = n

        if padrao:
            cur.execute(
                """INSERT INTO clientes (documento, nome) VALUES (%s, %s)
                ON CONFLICT (documento) DO UPDATE SET atualizado_em = NOW()""",
                (padrao, padrao),
            )

    return totais


def main():
    parser = argparse.ArgumentParser(description="Migra CSVs do C4ISTAR para Postgres")
    parser.add_argument("--pasta", default=".", help="Pasta com os historico_*.csv")
    parser.add_argument("--documento", default="", help="CPF/CNPJ padrão do cliente")
    args = parser.parse_args()
    totais = carregar(Path(args.pasta), args.documento)
    print("Carga concluída:")
    for tabela, qtd in totais.items():
        print(f"  {tabela}: {qtd}")


if __name__ == "__main__":
    main()
