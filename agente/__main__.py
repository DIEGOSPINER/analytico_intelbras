"""Linha de comando do agente.

Exemplos:
  python -m agente relatorio dia
  python -m agente relatorio semana
  python -m agente relatorio mes
  python -m agente vigiar
"""

from __future__ import annotations

import argparse
from datetime import date, datetime

from agente.analista import Analista
from agente.modelo import SessaoGPT, carregar_env
from agente.vigia import Vigia


def _data(texto: str) -> date:
    return datetime.strptime(texto, "%Y-%m-%d").date()


def main():
    carregar_env()
    parser = argparse.ArgumentParser(description="Analisa os históricos com o GPT.")
    sub = parser.add_subparsers(dest="comando", required=True)

    relatorio = sub.add_parser("relatorio", help="Gera relatório diário, semanal ou mensal.")
    relatorio.add_argument("periodo", choices=("dia", "semana", "mes"))
    relatorio.add_argument("--data", type=_data, default=None, help="Data de referência AAAA-MM-DD.")

    sub.add_parser("analisar", help="O mesmo que relatorio dia, usando hoje.")
    sub.add_parser("vigiar", help="Fica lendo os CSVs, alerta interesse e atualiza o relatório.")

    args = parser.parse_args()
    if args.comando == "vigiar":
        vigia = Vigia()
        if not vigia.analista.sessao.disponivel:
            print("OPENAI_API_KEY ausente. A vigia local de interesse segue; o GPT fica em espera.")
        print("Vigia ativa. Ctrl+C encerra.")
        vigia.loop()
        return

    nome = "dia" if args.comando == "analisar" else args.periodo
    referencia = None if args.comando == "analisar" else args.data
    analista = Analista(sessao=SessaoGPT())
    resultado = analista.analisar(nome, referencia)
    leitura = resultado["leitura"]
    print(leitura.get("resumo") or "Relatório gravado em relatorios/.")
    for alerta in resultado["alertas"]:
        print(
            f"ALERTA {alerta['tipo']} | {alerta['nome']} ({alerta['id']}) | "
            f"{alerta['camera']} {alerta['data']} {alerta['hora']}"
        )


if __name__ == "__main__":
    main()
