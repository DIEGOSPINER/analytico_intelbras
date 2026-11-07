"""Envia lotes CSV/eventos da borda para a API na nuvem."""

from __future__ import annotations

import argparse
import csv
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from db.conexao import _carregar_env, cliente_padrao

_carregar_env()


def _post(url: str, token: str, corpo: dict) -> dict:
    dados = json.dumps(corpo).encode("utf-8")
    pedido = urllib.request.Request(
        url.rstrip("/") + "/v1/ingestao",
        data=dados,
        headers={
            "Content-Type": "application/json",
            "X-Api-Key": token,
        },
        method="POST",
    )
    with urllib.request.urlopen(pedido, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _sep(caminho: Path) -> str:
    amostra = caminho.read_text(encoding="utf-8-sig", errors="replace")[:400]
    return ";" if amostra.count(";") >= amostra.count(",") else ","


def enviar_csv(arquivo: Path, tabela: str, documento: str, url: str, token: str) -> dict:
    with arquivo.open(encoding="utf-8-sig", newline="") as f:
        itens = list(csv.DictReader(f, delimiter=_sep(arquivo)))
    return _post(url, token, {
        "cliente_documento": documento,
        "tabela": tabela,
        "itens": itens[-500:],
    })


MAPA = {
    "historico_analitico.csv": "analitico",
    "historico_ocorrencias.csv": "ocorrencias",
    "historico_faces.csv": "faces",
    "historico_placas.csv": "placas",
    "historico_audio.csv": "audio",
    "historico_contagem.csv": "contagens",
}


def main():
    parser = argparse.ArgumentParser(description="Envia históricos da borda para a nuvem")
    parser.add_argument("--url", default=os.getenv("NUVEM_API_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--token", default=os.getenv("INGEST_TOKEN", ""))
    parser.add_argument("--documento", default="")
    args = parser.parse_args()
    documento = args.documento or cliente_padrao()
    if not documento:
        raise SystemExit("Informe --documento ou CLIENTE_DOCUMENTO no .env")
    if not args.token:
        raise SystemExit("Informe --token ou INGEST_TOKEN no .env")
    for nome, tabela in MAPA.items():
        caminho = Path(nome)
        if not caminho.exists():
            continue
        try:
            saida = enviar_csv(caminho, tabela, documento, args.url, args.token)
            print(nome, saida)
        except urllib.error.URLError as exc:
            print(nome, "erro", exc)


if __name__ == "__main__":
    main()
