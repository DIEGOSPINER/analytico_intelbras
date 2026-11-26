"""PDF de precificacao por cliente, tributacao, CNPJ, pro-labore e margem."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

CAMBIO = 5.5606
DATA_CAMBIO = "11/11/2026"
SAIDA = Path("relatorio_precificacao_cliente_brl.pdf")


def fmt_brl(valor: float) -> str:
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.cell(
            0,
            8,
            "C4ISTAR MONITOR - Precificacao, CNPJ e tributacao",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_font("Helvetica", "", 9)
        self.set_text_color(90, 90, 90)
        self.cell(
            0,
            6,
            (
                f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} | "
                f"Referencia PTAX venda {DATA_CAMBIO}: US$ 1 = R$ {CAMBIO:.4f}".replace(".", ",")
                + " | Documento indicativo"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0,
            8,
            f"Pagina {self.page_no()}/{{nb}} - nao substitui parecer contabil ou juridico",
            align="C",
        )


def reset_x(pdf: PDF):
    pdf.set_x(pdf.l_margin)


def secao(pdf: PDF, titulo: str):
    reset_x(pdf)
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(25, 45, 75)
    pdf.cell(0, 8, titulo, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(30, 30, 30)


def paragrafo(pdf: PDF, texto: str):
    reset_x(pdf)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, texto)
    reset_x(pdf)


def bullet(pdf: PDF, texto: str):
    paragrafo(pdf, f"- {texto}")


def tabela(pdf: PDF, cabecalho: list[str], linhas: list[list[str]], larguras: list[float]):
    reset_x(pdf)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(35, 55, 85)
    pdf.set_text_color(255, 255, 255)
    for i, h in enumerate(cabecalho):
        pdf.cell(larguras[i], 6.5, h, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(30, 30, 30)
    fill = False
    for linha in linhas:
        reset_x(pdf)
        pdf.set_fill_color(245, 247, 250) if fill else pdf.set_fill_color(255, 255, 255)
        for i, cel in enumerate(linha):
            align = "L" if i == 0 else "C"
            pdf.cell(larguras[i], 6, cel, border=1, fill=True, align=align)
        pdf.ln()
        fill = not fill
    reset_x(pdf)


def main():
    pdf = PDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    secao(pdf, "1. Resumo executivo")
    paragrafo(
        pdf,
        "Este relatorio consolida a estimativa de precificacao por cliente para o C4ISTAR MONITOR, "
        "considerando: tipo de CNPJ, regime tributario, CNAEs, modelos cloud e on-premise, "
        "preco por camera, preco por MB, pro-labore e margem de lucro. Valores em reais.",
    )
    paragrafo(
        pdf,
        "Posicionamento recomendado: software de analise, BI e integracao de dados "
        "(nao empresa de vigilancia/monitoramento de seguranca privada), com adaptacoes "
        "personalizadas por cliente.",
    )

    secao(pdf, "2. Tipo de empresa e CNPJ")
    tabela(
        pdf,
        ["Tema", "Recomendacao"],
        [
            ["Forma juridica", "SLU (Ltda unipessoal) ou LTDA"],
            ["Porte inicial", "ME (ate R$ 360 mil/ano) e depois EPP"],
            ["MEI", "Nao permitido para software"],
            ["Objeto social", "Software analitico / BI / integracao de dados"],
        ],
        [45, 145],
    )
    pdf.ln(2)
    paragrafo(pdf, "CNAEs sugeridos:")
    tabela(
        pdf,
        ["Papel", "CNAE", "Descricao"],
        [
            ["Principal", "6202-3/00", "Licenciamento de programas customizaveis"],
            ["Secundario", "6201-5/01", "Desenvolvimento sob encomenda"],
            ["Secundario", "6311-9/00", "Tratamento de dados / SaaS / hospedagem"],
            ["Secundario", "6204-0/00", "Consultoria em TI (implantacao/integracao)"],
        ],
        [30, 30, 130],
    )
    pdf.ln(1)
    paragrafo(
        pdf,
        "Evitar CNAE 8020-0/01 como principal (monitoramento de seguranca eletronica): "
        "exige autorizacao da Policia Federal e estrutura de operadores. So use se o negocio "
        "for de fato monitoramento de seguranca privada.",
    )

    secao(pdf, "3. Regime de tributacao")
    tabela(
        pdf,
        ["Fase", "Regime", "Carga estimada"],
        [
            ["Inicio", "Simples Nacional", "8% a 12% efetiva bem enquadrado"],
            ["Meta de anexo", "Anexo III", "Faixas iniciais ~6% a ~10%"],
            ["Risco", "Anexo V (consultoria/suporte)", "~15,5% sem Fator R >= 28%"],
            ["Alternativa", "Lucro Presumido", "~13% a 16% com ISS"],
        ],
        [35, 75, 80],
    )
    pdf.ln(1)
    bullet(
        pdf,
        "Fator R: folha + pro-labore (12 meses) / receita (12 meses). Se >= 28%, atividades "
        "de consultoria/suporte podem subir do Anexo V para o III.",
    )
    bullet(
        pdf,
        "Contratos preferenciais: licenca/SaaS + customizacao do produto (6202), com projetos "
        "sob encomenda e consultoria como linhas complementares.",
    )
    bullet(
        pdf,
        "Planeje impostos em 8-12% no Simples; use ~14% como stress no Lucro Presumido.",
    )

    secao(pdf, "4. Pro-labore e custos fixos")
    tabela(
        pdf,
        ["Item", "Faixa sugerida / mes"],
        [
            ["Pro-labore (ano 1-2)", fmt_brl(6000) + " a " + fmt_brl(8000)],
            ["Pro-labore (20-40 cameras)", fmt_brl(10000) + " a " + fmt_brl(12000)],
            ["Piso previdenciario (so formal)", "Salario minimo vigente"],
            ["Contador + ferramentas", fmt_brl(500) + " a " + fmt_brl(900)],
            ["Margem liquida alvo", "30% a 40% da receita"],
        ],
        [70, 120],
    )
    pdf.ln(1)
    paragrafo(
        pdf,
        "Distribuicao de lucros e linha distinta do pro-labore e nao substitui INSS/Fator R. "
        "Custo de infra cloud por camera (escala 10-40 cams, GPU T4): cerca de "
        + fmt_brl(450)
        + " a "
        + fmt_brl(750)
        + " / camera / mes. On-premise: quase zero de GPU sua (~"
        + fmt_brl(0)
        + " a "
        + fmt_brl(50)
        + " de apoio/LLM).",
    )

    pdf.add_page()
    secao(pdf, "5. Preco por camera - modelo cloud")
    paragrafo(
        pdf,
        "Voce opera a IA; o cliente entrega RTSP/API/eventos (dados do sistema do cliente).",
    )
    tabela(
        pdf,
        ["Pacote", "Preco / camera / mes", "Escopo"],
        [
            ["Essencial", fmt_brl(249), "Deteccao + alertas + portal"],
            ["Inteligencia (lista)", fmt_brl(349), "Faces/LPR/comportamento + Stive basico"],
            ["Enterprise", fmt_brl(449) + "-" + fmt_brl(599), "SLA, custom leve, multi-site"],
        ],
        [45, 50, 95],
    )
    pdf.ln(1)
    paragrafo(
        pdf,
        "Setup / implantacao por cliente (1x): "
        + fmt_brl(2500)
        + " a "
        + fmt_brl(6000)
        + ". Break-even aproximado no pacote "
        + fmt_brl(349)
        + ": cerca de 25 a 35 cameras, com imposto ~10% e pro-labore ~"
        + fmt_brl(7000)
        + ".",
    )

    secao(pdf, "6. Preco por camera - modelo on-premise")
    tabela(
        pdf,
        ["Item", "Valor sugerido"],
        [
            ["Licenca / projeto base (1x)", fmt_brl(12000) + " a " + fmt_brl(35000)],
            ["Manutencao / camera / mes", fmt_brl(99) + " a " + fmt_brl(179)],
            ["Hora de adaptacao / integracao", fmt_brl(180) + " a " + fmt_brl(280)],
        ],
        [70, 120],
    )
    pdf.ln(1)
    paragrafo(
        pdf,
        "On-premise melhora margem no inicio (sem frota T4 sua) e combina com integracao a "
        "subsistemas e BI personalizado.",
    )

    secao(pdf, "7. Preco por MB analisado / armazenado")
    paragrafo(
        pdf,
        "O processamento continuo ja deve estar no mensal da camera. Cobrar excedente so de "
        "artefatos analiticos (eventos, crops, metadados), nao de video bruto continuo.",
    )
    tabela(
        pdf,
        ["Metrica", "Sugestao"],
        [
            ["Franquia inclusa", "2 GB / camera / mes"],
            ["Excedente", fmt_brl(0.12) + " a " + fmt_brl(0.25) + " / MB"],
            ["Equivalente por GB", fmt_brl(120) + " a " + fmt_brl(250) + " / GB"],
            ["Retencao extra 30/90 dias", fmt_brl(39) + " a " + fmt_brl(89) + " / camera / mes"],
        ],
        [55, 135],
    )

    secao(pdf, "8. Exemplos de proposta comercial")
    pdf.set_font("Helvetica", "B", 9)
    reset_x(pdf)
    pdf.cell(0, 6, "Cliente tipico - 8 cameras em cloud", new_x="LMARGIN", new_y="NEXT")
    tabela(
        pdf,
        ["Item", "Valor"],
        [
            ["Setup", fmt_brl(4000)],
            ["Mensal (8 x " + fmt_brl(349) + ")", fmt_brl(2792)],
            ["Franquia", "16 GB de eventos/metadados"],
            ["Excedente", fmt_brl(0.15) + " / MB"],
            ["Integracao BI", "Escopo a parte (pacote ou hora)"],
        ],
        [70, 120],
    )
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 9)
    reset_x(pdf)
    pdf.cell(0, 6, "Mesmo cliente - 8 cameras on-premise", new_x="LMARGIN", new_y="NEXT")
    tabela(
        pdf,
        ["Item", "Valor"],
        [
            ["Projeto / licenca", fmt_brl(18000) + " a " + fmt_brl(28000)],
            ["Mensal (8 x " + fmt_brl(129) + ")", fmt_brl(1032)],
            ["Infra GPU sua", "Nao aplicavel (roda no cliente)"],
        ],
        [70, 120],
    )

    pdf.add_page()
    secao(pdf, "9. Metas de receita, pro-labore e lucro")
    tabela(
        pdf,
        ["Receita mensal", "Pro-labore", "Meta lucro liquido"],
        [
            [fmt_brl(15000), fmt_brl(6000), fmt_brl(2000) + " a " + fmt_brl(3000)],
            [fmt_brl(30000), fmt_brl(8000), fmt_brl(6000) + " a " + fmt_brl(9000)],
            [fmt_brl(60000), fmt_brl(12000), fmt_brl(15000) + " a " + fmt_brl(20000)],
        ],
        [55, 55, 80],
    )
    pdf.ln(1)
    paragrafo(
        pdf,
        "Estrategia ano 1: hibrido (on-premise dominante + poucos pilotos cloud), setup alto, "
        "lista cloud em "
        + fmt_brl(349)
        + "-"
        + fmt_brl(449)
        + " pensando em escala >= 30 cameras e GPU com contrato de 1 ano. "
        "Meta de margem liquida ~30% apos impostos com >= 40 cameras ou mix on-prem forte.",
    )

    secao(pdf, "10. Decisoes recomendadas")
    tabela(
        pdf,
        ["Tema", "Decisao"],
        [
            ["Empresa", "SLU/LTDA ME (nao MEI)"],
            ["CNAEs", "6202 principal + 6201 + 6311 + 6204"],
            ["Evitar como foco", "8020 (salvo negocio de seguranca)"],
            ["Tributacao", "Simples mirando Anexo III; buffer 8-12%"],
            ["Pro-labore", fmt_brl(6000) + " a " + fmt_brl(8000) + " no inicio"],
            ["Cloud / camera", fmt_brl(349) + " lista | " + fmt_brl(249) + " entrada | " + fmt_brl(449) + "+ enterprise"],
            ["On-prem / camera", fmt_brl(99) + "-" + fmt_brl(179) + "/mes + licenca " + fmt_brl(12000) + "-" + fmt_brl(35000)],
            ["MB", "Franquia 2 GB/cam + " + fmt_brl(0.12) + "-" + fmt_brl(0.25) + "/MB excedente"],
            ["Margem", "30-40% liquida na escala; hibrido no comeco"],
        ],
        [40, 150],
    )

    secao(pdf, "11. Avisos")
    paragrafo(
        pdf,
        "Documento indicativo para planejamento comercial e conversa com contador/advogado. "
        "Nao e parecer juridico, contabil ou fiscal. Enquadramento de CNAE, anexo do Simples, "
        "ISS municipal e eventual atividade de seguranca privada dependem do contrato real, "
        "do municipio e da analise profissional. Precos de nuvem usados como base vieram da "
        "estimativa anterior (AWS/GCP/Azure, GPU T4, sem video continuo).",
    )

    pdf.output(str(SAIDA))
    print(SAIDA.resolve())


if __name__ == "__main__":
    main()
