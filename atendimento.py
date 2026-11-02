"""Opções que o chat do WhatsApp vai oferecer ao cliente identificado.

1. Cadastrar veículo de interesse e o motivo.
2. Cadastrar pessoa de interesse e o motivo, com base legal.
3. Cadastrar nomes e números de contato.
4. Informar uma ocorrência.
"""

from __future__ import annotations

from cadastro import cadastrar_contato, cadastrar_pessoa, cadastrar_veiculo
from ocorrencias import anexar_midia, informar_ocorrencia


OPCOES = (
    ("1", "Cadastrar veículo de interesse e o motivo"),
    ("2", "Cadastrar pessoa de interesse e o motivo"),
    ("3", "Cadastrar nomes e números de contato"),
    ("4", "Informar uma ocorrência"),
)


def texto_menu() -> str:
    linhas = ["O que você deseja fazer?"]
    linhas.extend(f"{numero}. {rotulo}" for numero, rotulo in OPCOES)
    return "\n".join(linhas)


def atender(documento: str, opcao: str, dados: dict | None = None) -> dict:
    dados = dict(dados or {})
    escolha = str(opcao or "").strip().lower()
    if escolha in ("1", "veiculo"):
        if not str(dados.get("motivo") or "").strip():
            raise ValueError("Informe o motivo do veículo de interesse.")
        return {"opcao": "veiculo", "registro": cadastrar_veiculo(documento, dados)}
    if escolha in ("2", "pessoa"):
        if not str(dados.get("motivo") or "").strip():
            raise ValueError("Informe o motivo da pessoa de interesse.")
        return {"opcao": "pessoa", "registro": cadastrar_pessoa(documento, dados)}
    if escolha in ("3", "contato"):
        return {"opcao": "contato", "registro": cadastrar_contato(documento, dados)}
    if escolha in ("4", "ocorrencia"):
        registro = informar_ocorrencia(documento, dados)
        return {"opcao": "ocorrencia", "registro": registro}
    raise ValueError("Escolha 1, 2, 3 ou 4.")


def anexar_na_ocorrencia(documento: str, ocorrencia_id: str, origem, tipo: str) -> str:
    return anexar_midia(documento, ocorrencia_id, origem, tipo)
