"""PDF com propostas comerciais para 2, 10 e 20 cameras."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from fpdf import FPDF

SAIDA = Path("proposta_comercial_c4istar_2_10_20_cameras.pdf")
VALIDADE_DIAS = 15

# Precos lista (BRL)
PRECO_CAM = 349.0
PRECO_SETUP_BASE = {
    2: 2500.0,
    10: 4500.0,
    20: 6000.0,
}
FRANQUIA_GB_POR_CAM = 2.0
EXCEDENTE_MB = 0.15
MANUT_ONPREM = 129.0
LICENCA_ONPREM = {
    2: 14000.0,
    10: 22000.0,
    20: 30000.0,
}


def fmt_brl(valor: float) -> str:
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(25, 45, 75)
        self.cell(0, 7, "C4ISTAR MONITOR", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(90, 90, 90)
        self.cell(
            0,
            5,
            "Proposta comercial - analise inteligente de cameras, BI e integracoes",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_draw_color(35, 55, 85)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1)
        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0,
            8,
            f"Pagina {self.page_no()}/{{nb}} | Validade {VALIDADE_DIAS} dias | Proposta indicativa",
            align="C",
        )


def reset_x(pdf: PDF):
    pdf.set_x(pdf.l_margin)


def secao(pdf: PDF, titulo: str):
    reset_x(pdf)
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(25, 45, 75)
    pdf.cell(0, 7, titulo, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(30, 30, 30)


def p(pdf: PDF, texto: str, tamanho: int = 9):
    reset_x(pdf)
    pdf.set_font("Helvetica", "", tamanho)
    pdf.multi_cell(0, 4.8, texto)
    reset_x(pdf)


def tabela(pdf: PDF, cabecalho: list[str], linhas: list[list[str]], larguras: list[float]):
    reset_x(pdf)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(35, 55, 85)
    pdf.set_text_color(255, 255, 255)
    for i, h in enumerate(cabecalho):
        pdf.cell(larguras[i], 6.2, h, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(30, 30, 30)
    fill = False
    for linha in linhas:
        reset_x(pdf)
        pdf.set_fill_color(245, 247, 250) if fill else pdf.set_fill_color(255, 255, 255)
        for i, cel in enumerate(linha):
            align = "L" if i == 0 else "R" if i == len(linha) - 1 or i > 0 else "C"
            if len(linha) == 2 and i == 1:
                align = "R"
            elif i == 0:
                align = "L"
            else:
                align = "C" if i < len(linha) - 1 else "R"
            pdf.cell(larguras[i], 5.8, cel, border=1, fill=True, align=align)
        pdf.ln()
        fill = not fill
    reset_x(pdf)


def bloco_proposta(pdf: PDF, n: int):
    setup = PRECO_SETUP_BASE[n]
    mensal_cloud = n * PRECO_CAM
    franquia = n * FRANQUIA_GB_POR_CAM
    anual_cloud = mensal_cloud * 12 + setup
    licenca = LICENCA_ONPREM[n]
    mensal_onprem = n * MANUT_ONPREM
    ano1_onprem = licenca + mensal_onprem * 12

    secao(pdf, f"Proposta {n} cameras")
    p(
        pdf,
        f"Pacote Inteligencia: deteccao de pessoas/veiculos, comportamentos, faces, LPR, "
        f"alertas, portal web, mapas/risco e apoio do agente Stive. Franquia de dados "
        f"analiticos: {franquia:.0f} GB/mes ({FRANQUIA_GB_POR_CAM:.0f} GB por camera).",
    )

    pdf.set_font("Helvetica", "B", 9)
    reset_x(pdf)
    pdf.cell(0, 6, "Opcao A - Cloud (processamento na nossa infraestrutura)", new_x="LMARGIN", new_y="NEXT")
    tabela(
        pdf,
        ["Item", "Quantidade", "Unitario", "Total"],
        [
            ["Implantacao / setup (1x)", "1", fmt_brl(setup), fmt_brl(setup)],
            [
                "Assinatura mensal por camera",
                str(n),
                fmt_brl(PRECO_CAM),
                fmt_brl(mensal_cloud),
            ],
            ["Excedente de armazenamento analitico", "sob demanda", fmt_brl(EXCEDENTE_MB) + "/MB", "-"],
        ],
        [78, 28, 42, 42],
    )
    pdf.ln(1)
    tabela(
        pdf,
        ["Resumo Cloud", "Valor"],
        [
            ["Setup (pagamento unico)", fmt_brl(setup)],
            ["Mensalidade", fmt_brl(mensal_cloud)],
            ["Investimento 1o ano (setup + 12 mensalidades)", fmt_brl(anual_cloud)],
            ["Custo medio / camera / mes (so assinatura)", fmt_brl(PRECO_CAM)],
        ],
        [130, 60],
    )

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 9)
    reset_x(pdf)
    pdf.cell(0, 6, "Opcao B - On-premise (software no ambiente do cliente)", new_x="LMARGIN", new_y="NEXT")
    tabela(
        pdf,
        ["Item", "Quantidade", "Unitario", "Total"],
        [
            ["Licenca / projeto base (1x)", "1", fmt_brl(licenca), fmt_brl(licenca)],
            [
                "Manutencao e atualizacao mensal / camera",
                str(n),
                fmt_brl(MANUT_ONPREM),
                fmt_brl(mensal_onprem),
            ],
            ["Horas extras de integracao/BI", "sob escopo", fmt_brl(220) + "/h", "-"],
        ],
        [78, 28, 42, 42],
    )
    pdf.ln(1)
    tabela(
        pdf,
        ["Resumo On-premise", "Valor"],
        [
            ["Licenca / projeto (pagamento unico)", fmt_brl(licenca)],
            ["Mensalidade de manutencao", fmt_brl(mensal_onprem)],
            ["Investimento 1o ano (licenca + 12 mensalidades)", fmt_brl(ano1_onprem)],
            ["Custo medio / camera / mes (so manutencao)", fmt_brl(MANUT_ONPREM)],
        ],
        [130, 60],
    )
    pdf.ln(2)


def main():
    validade = (datetime.now() + timedelta(days=VALIDADE_DIAS)).strftime("%d/%m/%Y")
    pdf = PDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    secao(pdf, "1. Apresentacao")
    p(
        pdf,
        "Proposta comercial do C4ISTAR MONITOR para analise inteligente de cameras, "
        "integracao com bases/subsistemas do cliente e painel de business intelligence. "
        "Tres cenarios: 2, 10 e 20 cameras, cada um com opcao Cloud e On-premise.",
    )
    p(
        pdf,
        f"Data: {datetime.now().strftime('%d/%m/%Y')} | Validade: {VALIDADE_DIAS} dias "
        f"(ate {validade}). Valores em reais (BRL), sem impostos municipais/retencoes "
        f"especificas do tomador, quando aplicaveis.",
    )

    secao(pdf, "2. Escopo incluido (todas as propostas)")
    for item in [
        "Deteccao e contagem de pessoas, veiculos e eventos de comportamento.",
        "Reconhecimento facial e LPR conforme cadastro/interesse do cliente.",
        "Alertas (e-mail e canais configurados), portal web e visao de risco/mapas.",
        "Agente Stive para apoio operacional e consultas.",
        "Implantacao, treinamento basico e suporte padrao em horario comercial.",
        "Personalizacoes leves de cadastro, regras e painel; projetos BI/integracao profundos sob escopo.",
    ]:
        p(pdf, f"- {item}")

    secao(pdf, "3. Condicoes comerciais gerais")
    tabela(
        pdf,
        ["Condicao", "Detalhe"],
        [
            ["Pacote de referencia", "Inteligencia - " + fmt_brl(PRECO_CAM) + " / camera / mes (cloud)"],
            ["Franquia de dados", f"{FRANQUIA_GB_POR_CAM:.0f} GB analiticos / camera / mes"],
            ["Excedente", fmt_brl(EXCEDENTE_MB) + " / MB"],
            ["Pagamento setup/licenca", "50% no aceite e 50% na entrega/go-live"],
            ["Mensalidade", "Antecipada, ate o dia 10 de cada mes"],
            ["Reajuste", "Anual pelo IPCA ou indice acordado em contrato"],
            ["Prazo de implantacao", "7 a 20 dias uteis apos acesso as cameras/dados"],
        ],
        [55, 135],
    )

    pdf.add_page()
    bloco_proposta(pdf, 2)
    bloco_proposta(pdf, 10)

    pdf.add_page()
    bloco_proposta(pdf, 20)

    secao(pdf, "4. Comparativo rapido (Cloud)")
    tabela(
        pdf,
        ["Cenario", "Setup", "Mensal", "1o ano"],
        [
            [
                "2 cameras",
                fmt_brl(PRECO_SETUP_BASE[2]),
                fmt_brl(2 * PRECO_CAM),
                fmt_brl(PRECO_SETUP_BASE[2] + 2 * PRECO_CAM * 12),
            ],
            [
                "10 cameras",
                fmt_brl(PRECO_SETUP_BASE[10]),
                fmt_brl(10 * PRECO_CAM),
                fmt_brl(PRECO_SETUP_BASE[10] + 10 * PRECO_CAM * 12),
            ],
            [
                "20 cameras",
                fmt_brl(PRECO_SETUP_BASE[20]),
                fmt_brl(20 * PRECO_CAM),
                fmt_brl(PRECO_SETUP_BASE[20] + 20 * PRECO_CAM * 12),
            ],
        ],
        [40, 45, 50, 55],
    )

    pdf.ln(2)
    secao(pdf, "5. Comparativo rapido (On-premise)")
    tabela(
        pdf,
        ["Cenario", "Licenca", "Mensal", "1o ano"],
        [
            [
                "2 cameras",
                fmt_brl(LICENCA_ONPREM[2]),
                fmt_brl(2 * MANUT_ONPREM),
                fmt_brl(LICENCA_ONPREM[2] + 2 * MANUT_ONPREM * 12),
            ],
            [
                "10 cameras",
                fmt_brl(LICENCA_ONPREM[10]),
                fmt_brl(10 * MANUT_ONPREM),
                fmt_brl(LICENCA_ONPREM[10] + 10 * MANUT_ONPREM * 12),
            ],
            [
                "20 cameras",
                fmt_brl(LICENCA_ONPREM[20]),
                fmt_brl(20 * MANUT_ONPREM),
                fmt_brl(LICENCA_ONPREM[20] + 20 * MANUT_ONPREM * 12),
            ],
        ],
        [40, 45, 50, 55],
    )

    secao(pdf, "6. Recomendacao")
    p(
        pdf,
        "2 cameras: Cloud e mais simples para piloto; On-premise faz sentido se ja houver "
        "servidor no local e necessidade de dados 100% internos.",
    )
    p(
        pdf,
        "10 e 20 cameras: Cloud escala com menos CAPEX do cliente; On-premise tende a "
        "menor custo recorrente apos o 1o ano e maior controle operacional.",
    )
    p(
        pdf,
        "Proximo passo: escolha do cenario, acesso as cameras/rede e assinatura do aceite "
        "comercial. Personalizacoes profundas de BI e integracao a ERPs/CRM entram em "
        "aditivo de escopo.",
    )

    secao(pdf, "7. Aceite")
    p(pdf, "Cliente: ____________________________________________  CNPJ: ____________________")
    pdf.ln(2)
    p(pdf, "Responsavel: ______________________________________  E-mail: ____________________")
    pdf.ln(2)
    p(pdf, "Cenario escolhido: ( ) 2 cams  ( ) 10 cams  ( ) 20 cams")
    p(pdf, "Modelo: ( ) Cloud  ( ) On-premise")
    pdf.ln(3)
    p(pdf, "Local/Data: _______________________    Assinatura: _______________________________")

    pdf.output(str(SAIDA))
    print(SAIDA.resolve())
    for n in (2, 10, 20):
        print(
            n,
            "cloud_mensal",
            n * PRECO_CAM,
            "cloud_ano1",
            PRECO_SETUP_BASE[n] + n * PRECO_CAM * 12,
            "onprem_mensal",
            n * MANUT_ONPREM,
            "onprem_ano1",
            LICENCA_ONPREM[n] + n * MANUT_ONPREM * 12,
        )


if __name__ == "__main__":
    main()
