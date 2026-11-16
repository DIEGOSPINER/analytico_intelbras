"""Proposta C4ISTAR B2B2C: gestores de condominio (modelo Stella Maris)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

SAIDA = Path("proposta_c4istar_gestores_condominio_brl.pdf")

# Mercado referencia (Stella Maris / similar)
RESIDENCIAS_BAIRRO = 20_000
UNIDADES_MEDIA_CONDO = 7.5  # media entre 5 e 10 casas/village
CONDOS_TEORICOS = RESIDENCIAS_BAIRRO / UNIDADES_MEDIA_CONDO  # ~2667 se 100% fosse condo

# Preco cobrado do condominio (repassado na taxa condominial)
# Gestao+ com 3 streams: area comum + garagem + entrada social
PRECO_UNIDADE_MES = 39.90
STREAMS_POR_CONDO = 3
CUSTO_POR_STREAM = 40.0    # RTMP economico compartilhado (sem ao vivo/gravacao)
CUSTO_DASH_GESTOR = 10.0   # painel sindico/admin por condo
CUSTO_POR_UNIDADE = 2.50   # alertas, multas, fatia Stive/e-mail
CUSTO_POR_CONDO = STREAMS_POR_CONDO * CUSTO_POR_STREAM + CUSTO_DASH_GESTOR  # 130
FIXO_MES = 2500.0          # VPS, CRM B2B, cobranca, suporte gestores, contingencia
MARGEM_EMPRESA_ALVO = 0.25
CARGA_TRIBUTARIA = 0.12


def fmt(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v: float) -> str:
    return f"{v * 100:.1f}%".replace(".", ",")


def _cenario(unidades: float, prolabore: float) -> dict:
    condos = unidades / UNIDADES_MEDIA_CONDO
    receita = unidades * PRECO_UNIDADE_MES
    custo_var = unidades * CUSTO_POR_UNIDADE + condos * CUSTO_POR_CONDO
    liquido = receita * (1 - CARGA_TRIBUTARIA)
    lucro = liquido - custo_var - FIXO_MES - prolabore
    return {
        "prolabore": prolabore,
        "unidades": int(round(unidades)),
        "condos": int(round(condos)),
        "receita": receita,
        "custo_var": custo_var,
        "fixo": FIXO_MES,
        "tributos": receita * CARGA_TRIBUTARIA,
        "liquido": liquido,
        "lucro": lucro,
        "margem_sobre_liquido": (lucro / liquido) if liquido else 0,
        "ticket_condo": UNIDADES_MEDIA_CONDO * PRECO_UNIDADE_MES,
        "penetracao_bairro": unidades / RESIDENCIAS_BAIRRO,
    }


def unidades_necessarias(prolabore: float) -> dict:
    lo, hi = 50.0, 50_000.0
    best = _cenario(hi, prolabore)
    for _ in range(60):
        mid = (lo + hi) / 2
        c = _cenario(mid, prolabore)
        if c["lucro"] >= MARGEM_EMPRESA_ALVO * c["liquido"]:
            best = c
            hi = mid
        else:
            lo = mid
    return best


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.cell(
            0,
            8,
            "C4ISTAR MONITOR - Modelo gestores de condominio (B2B2C)",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_font("Helvetica", "", 9)
        self.set_text_color(90, 90, 90)
        self.cell(
            0,
            6,
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} | Ref. Stella Maris (~20 mil residencias) | Indicativo",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Pagina {self.page_no()}/{{nb}} - nao substitui plano financeiro contabil", align="C")


def reset_x(pdf: PDF):
    pdf.set_x(pdf.l_margin)


def secao(pdf: PDF, titulo: str):
    reset_x(pdf)
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(25, 45, 75)
    pdf.cell(0, 8, titulo, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(30, 30, 30)


def p(pdf: PDF, texto: str):
    reset_x(pdf)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, texto)
    reset_x(pdf)


def bullet(pdf: PDF, texto: str):
    p(pdf, f"- {texto}")


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
            pdf.cell(larguras[i], 6, cel, border=1, fill=True, align="L" if i == 0 else "C")
        pdf.ln()
        fill = not fill
    reset_x(pdf)


def main():
    pdf = PDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    secao(pdf, "1. Por que gestores (e nao camera a camera)")
    p(
        pdf,
        "Em vez de vender casa a casa, o cliente e o gestor/administradora. "
        "A taxa entra na mensalidade do condominio e a administradora repassa "
        "a C4ISTAR. Um contrato fecha dezenas de unidades de uma vez. "
        "Sem ao vivo/gravacao na plataforma: o app da camera continua com isso; "
        "vendemos gestao, regras da convencao e alertas uteis ao sindico.",
    )

    secao(pdf, "2. Oferta para o gestor")
    bullet(pdf, "Painel do condominio: ocorrencias, fluxo, pessoas de interesse, historico.")
    bullet(pdf, "Multas configuraveis (ex.: animais soltos) conforme convencao.")
    bullet(pdf, "Cerca inteligente / perimetro: alerta de invasao ou abertura irregular.")
    bullet(
        pdf,
        "3 streams de area comum via RTMP so para analise: "
        "1 area comum + 1 garagem + 1 entrada social.",
    )
    bullet(pdf, "Relatorio mensal para assembleia (eventos, multas, tendencias).")
    bullet(pdf, "Grupo de moradores: avisos do sindico + alertas compartilhados.")

    secao(pdf, "3. Como o dinheiro entra")
    tabela(
        pdf,
        ["Etapa", "Quem", "O que acontece"],
        [
            ["1", "Assembleia/sindico", "Aprova taxa C4ISTAR na mensalidade"],
            ["2", "Morador", "Paga condominio (taxa embutida, ~" + fmt(PRECO_UNIDADE_MES) + "/un)"],
            ["3", "Administradora", "Repassa lote mensal a C4ISTAR (NF)"],
            ["4", "C4ISTAR", "Mantem painel, regras, alertas e suporte ao gestor"],
        ],
        [18, 42, 130],
    )
    pdf.ln(1)
    p(
        pdf,
        "Ticket medio por condominio (5-10 casas, media 7,5): "
        + fmt(UNIDADES_MEDIA_CONDO * PRECO_UNIDADE_MES)
        + "/mes. Preco por unidade baixo o suficiente para caber na taxa.",
    )

    secao(pdf, "4. Mercado referencia - Stella Maris")
    bullet(pdf, "Residencias (senso approx.): " + f"{RESIDENCIAS_BAIRRO:,}".replace(",", "."))
    bullet(pdf, "Se media 7,5 un/condo: ate ~" + f"{int(CONDOS_TEORICOS):,}".replace(",", ".") + " condominios teoricos.")
    bullet(pdf, "Nem tudo e condo gerido: use penetracao realista (ex.: 3%, 5%, 10% das residencias).")
    tabela(
        pdf,
        ["Penetracao", "Unidades", "Condos (~)", "Receita/mes", "Obs."],
        [
            ["3%", "600", "80", fmt(600 * PRECO_UNIDADE_MES), "1 bairro piloto serio"],
            ["5%", "1.000", "133", fmt(1000 * PRECO_UNIDADE_MES), "base solida local"],
            ["10%", "2.000", "267", fmt(2000 * PRECO_UNIDADE_MES), "dominancia no bairro"],
            ["20%", "4.000", "533", fmt(4000 * PRECO_UNIDADE_MES), "expansao + adjacentes"],
        ],
        [28, 28, 28, 40, 66],
    )

    secao(pdf, "5. Custos usados nesta simulacao")
    bullet(pdf, fmt(PRECO_UNIDADE_MES) + " receita por unidade/mes (Gestao+).")
    bullet(pdf, fmt(CUSTO_POR_UNIDADE) + " custo variavel/unidade (alertas, multas, painel).")
    bullet(
        pdf,
        fmt(CUSTO_POR_CONDO)
        + f" custo/condo ({STREAMS_POR_CONDO} streams x {fmt(CUSTO_POR_STREAM)} + painel gestor).",
    )
    bullet(pdf, fmt(FIXO_MES) + " fixo/mes (VPS, CRM B2B, cobranca, suporte, folga).")
    bullet(pdf, f"{int(CARGA_TRIBUTARIA*100)}% tributos sobre faturamento (Simples approx.).")
    bullet(pdf, f"Margem empresa alvo: {int(MARGEM_EMPRESA_ALVO*100)}% do liquido (apos custos e pro-labore).")

    secao(pdf, "6. Metas de pro-labore (5 / 10 / 15 / 20 mil)")
    p(
        pdf,
        "Quantas unidades (e ~condos de 7,5 un) para retirar o pro-labore "
        "e ainda deixar margem na empresa.",
    )
    linhas = []
    for valor in (5000, 10000, 15000, 20000):
        r = unidades_necessarias(float(valor))
        linhas.append([
            fmt(r["prolabore"]),
            str(r["unidades"]),
            str(r["condos"]),
            pct(r["penetracao_bairro"]),
            fmt(r["receita"]),
            fmt(r["lucro"]),
        ])
    tabela(
        pdf,
        ["Pro-labore", "Unidades", "Condos", "% Stella Maris", "Receita/mes", "Lucro empresa"],
        linhas,
        [30, 28, 24, 32, 36, 40],
    )
    pdf.ln(1)
    p(
        pdf,
        "% Stella Maris = fatia das 20 mil residencias do bairro. "
        "Se o numero passar de ~15-20%, a meta ja exige outros bairros ou "
        "administradoras com carteira multi-condominio.",
    )

    secao(pdf, "7. Pacotes sugeridos ao gestor")
    tabela(
        pdf,
        ["Pacote", "Por unidade/mes", "Streams", "Inclui"],
        [
            ["Essencial", fmt(29.90), "2", "Comum + entrada; alertas; grupo"],
            ["Gestao+ (base)", fmt(39.90), "3", "Comum + garagem + entrada; multas; cerca"],
            ["Premium", fmt(49.90), "3+", "Gestao+ + POI avancado + cam extra"],
        ],
        [32, 35, 22, 101],
    )
    pdf.ln(1)
    p(
        pdf,
        "Simulacao financeira acima usa Gestao+ ("
        + fmt(PRECO_UNIDADE_MES)
        + ", 3 streams). Ticket medio/condo ~"
        + fmt(UNIDADES_MEDIA_CONDO * PRECO_UNIDADE_MES)
        + ". Setup opcional: "
        + fmt(0)
        + " a "
        + fmt(399)
        + " (onboarding + convencao + 3 keys RTMP).",
    )

    secao(pdf, "8. Estrutura comercial intermediaria")
    bullet(pdf, "1 contrato com administradora = N condominios da carteira.")
    bullet(pdf, "Faturamento mensal consolidado (NF para a administradora ou por condo).")
    bullet(pdf, "Login gestor (sindico/admin) + logins moradores leves no grupo.")
    bullet(pdf, "SLA de suporte B2B (WhatsApp/portal) - nao suporte casa a casa.")
    bullet(pdf, "CNPJ software/SaaS; evitar CNAE de vigilancia como principal.")

    secao(pdf, "9. Proximos passos")
    bullet(pdf, "1 piloto com 1 village/condo em Stella Maris (5-10 casas).")
    bullet(pdf, "Checklist de convencao: regras de multa (animais etc.).")
    bullet(pdf, "Painel gestor + export de relatorio mensal.")
    bullet(pdf, "Proposta padrao para administradoras (1 pagina + tabela de taxa/un).")

    pdf.output(str(SAIDA))
    print(f"Gerado: {SAIDA.resolve()}")
    print(
        f"Ticket medio/condo: {fmt(UNIDADES_MEDIA_CONDO * PRECO_UNIDADE_MES)} "
        f"| preco/un: {fmt(PRECO_UNIDADE_MES)}"
    )
    for valor in (5000, 10000, 15000, 20000):
        r = unidades_necessarias(float(valor))
        print(
            f"Pro-labore {fmt(r['prolabore'])}: ~{r['unidades']} un / ~{r['condos']} condos "
            f"({pct(r['penetracao_bairro'])} Stella) | receita {fmt(r['receita'])} | lucro {fmt(r['lucro'])}"
        )
    for pen, un in ((0.03, 600), (0.05, 1000), (0.10, 2000), (0.20, 4000)):
        c = _cenario(float(un), 0)
        print(
            f"Penetracao {pct(pen)}: receita {fmt(c['receita'])} | "
            f"sobra antes pro-labore {fmt(c['lucro'])}"
        )


if __name__ == "__main__":
    main()
