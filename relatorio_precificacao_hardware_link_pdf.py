"""PDF: precificacao com instalacao, comodato/venda de camera e link de dados."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

SAIDA = Path("relatorio_precificacao_camera_instalacao_link_brl.pdf")

# Custos e precos de referencia (BRL) - equipamento corporativo Full HD IP
CUSTO_CAMERA = 280.0          # seu custo de aquisicao (revenda)
PRECO_VENDA_CAMERA = 449.0    # venda no setup
COMODATO_CAMERA_MES = 45.0    # mensalidade do equipamento em comodato
CUSTO_INSTAL_INT = 160.0      # seu custo medio (tecnico + deslocamento parcial)
PRECO_INSTAL = 280.0          # cobrado do cliente por camera (padrao)
MATERIAIS_POR_CAM = 40.0      # buchas, cabo curto, conectores (medio)

# Software analitico (lista anterior)
SOFT_CLOUD = 349.0
SOFT_ONPREM = 129.0

# Link de dados - pago pelo CLIENTE ao provedor (nao e sua receita, salvo revenda)
LINK_FIBRA_MES = 149.90       # fibra empresarial ~200-300 Mbps (referencia)
LINK_IP_FIXO_MES = 60.0       # opcional
LINK_4G_SITE_MES = 119.0      # backup/site sem fibra
MBPS_POR_CAM = 1.5            # upload medio analitico (substream)


def fmt_brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(25, 45, 75)
        self.cell(
            0,
            7,
            "C4ISTAR MONITOR - Precificacao com camera, instalacao e link de dados",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_font("Helvetica", "", 8)
        self.set_text_color(90, 90, 90)
        self.cell(
            0,
            5,
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} | Analise indicativa de custos e precos em BRL",
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
            f"Pagina {self.page_no()}/{{nb}} | Precos de hardware/link variam por regiao e fornecedor",
            align="C",
        )


def rx(pdf: PDF):
    pdf.set_x(pdf.l_margin)


def secao(pdf: PDF, t: str):
    rx(pdf)
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(25, 45, 75)
    pdf.cell(0, 7, t, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(30, 30, 30)


def p(pdf: PDF, t: str):
    rx(pdf)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 4.7, t)
    rx(pdf)


def tab(pdf: PDF, heads: list[str], rows: list[list[str]], widths: list[float]):
    rx(pdf)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(35, 55, 85)
    pdf.set_text_color(255, 255, 255)
    for i, h in enumerate(heads):
        pdf.cell(widths[i], 6, h, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(30, 30, 30)
    fill = False
    for row in rows:
        rx(pdf)
        pdf.set_fill_color(245, 247, 250) if fill else pdf.set_fill_color(255, 255, 255)
        for i, c in enumerate(row):
            align = "L" if i == 0 else "R"
            pdf.cell(widths[i], 5.6, c, border=1, fill=True, align=align)
        pdf.ln()
        fill = not fill
    rx(pdf)


def totais(n: int) -> dict:
    setup_venda = n * (PRECO_VENDA_CAMERA + PRECO_INSTAL + MATERIAIS_POR_CAM)
    # materiais embutidos na instalacao cobrada; na pratica somamos instal+camera
    setup_venda = n * (PRECO_VENDA_CAMERA + PRECO_INSTAL)
    setup_comodato = n * PRECO_INSTAL  # so instalacao; camera fica em comodato
    mensal_venda_cloud = n * SOFT_CLOUD
    mensal_comodato_cloud = n * (SOFT_CLOUD + COMODATO_CAMERA_MES)
    mensal_venda_onprem = n * SOFT_ONPREM
    mensal_comodato_onprem = n * (SOFT_ONPREM + COMODATO_CAMERA_MES)

    # seus custos
    custo_setup_venda = n * (CUSTO_CAMERA + CUSTO_INSTAL_INT + MATERIAIS_POR_CAM)
    custo_setup_comodato = n * (CUSTO_CAMERA + CUSTO_INSTAL_INT + MATERIAIS_POR_CAM)  # voce compra a camera
    margem_setup_venda = setup_venda - custo_setup_venda
    # no comodato o setup so cobre instal; camera e CAPEX seu
    margem_setup_comodato = setup_comodato - n * (CUSTO_INSTAL_INT + MATERIAIS_POR_CAM)
    capex_comodato = n * CUSTO_CAMERA

    link_fibra = LINK_FIBRA_MES
    link_4g = LINK_4G_SITE_MES
    upload_mbps = n * MBPS_POR_CAM

    return {
        "n": n,
        "setup_venda": setup_venda,
        "setup_comodato": setup_comodato,
        "mensal_venda_cloud": mensal_venda_cloud,
        "mensal_comodato_cloud": mensal_comodato_cloud,
        "mensal_venda_onprem": mensal_venda_onprem,
        "mensal_comodato_onprem": mensal_comodato_onprem,
        "ano1_venda_cloud": setup_venda + mensal_venda_cloud * 12,
        "ano1_comodato_cloud": setup_comodato + mensal_comodato_cloud * 12,
        "custo_setup_venda": custo_setup_venda,
        "margem_setup_venda": margem_setup_venda,
        "margem_setup_comodato": margem_setup_comodato,
        "capex_comodato": capex_comodato,
        "link_fibra": link_fibra,
        "link_4g": link_4g,
        "upload_mbps": upload_mbps,
        "payback_comodato_meses": (
            capex_comodato / (n * COMODATO_CAMERA_MES) if n * COMODATO_CAMERA_MES else 0
        ),
    }


def bloco_cenario(pdf: PDF, n: int):
    t = totais(n)
    secao(pdf, f"Cenario {n} cameras")
    p(
        pdf,
        f"Upload analitico estimado: ~{t['upload_mbps']:.1f} Mbps "
        f"({MBPS_POR_CAM} Mbps/camera em substream). Link de dados e responsabilidade do cliente "
        f"se ainda nao houver banda adequada.",
    )

    pdf.set_font("Helvetica", "B", 9)
    rx(pdf)
    pdf.cell(0, 6, "A) Venda da camera + instalacao + software cloud", new_x="LMARGIN", new_y="NEXT")
    tab(
        pdf,
        ["Item", "Total"],
        [
            [f"Cameras (venda {n} x {fmt_brl(PRECO_VENDA_CAMERA)})", fmt_brl(n * PRECO_VENDA_CAMERA)],
            [f"Instalacao ({n} x {fmt_brl(PRECO_INSTAL)})", fmt_brl(n * PRECO_INSTAL)],
            ["Setup total (unico)", fmt_brl(t["setup_venda"])],
            [f"Software cloud mensal ({n} x {fmt_brl(SOFT_CLOUD)})", fmt_brl(t["mensal_venda_cloud"])],
            ["Investimento cliente 1o ano (setup+12x software)", fmt_brl(t["ano1_venda_cloud"])],
            ["Sua margem bruta no setup (aprox.)", fmt_brl(t["margem_setup_venda"])],
        ],
        [130, 60],
    )

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 9)
    rx(pdf)
    pdf.cell(0, 6, "B) Comodato da camera + instalacao + software cloud", new_x="LMARGIN", new_y="NEXT")
    tab(
        pdf,
        ["Item", "Total"],
        [
            [f"Instalacao ({n} x {fmt_brl(PRECO_INSTAL)})", fmt_brl(t["setup_comodato"])],
            [
                f"Mensal software+comodato ({n} x {fmt_brl(SOFT_CLOUD + COMODATO_CAMERA_MES)})",
                fmt_brl(t["mensal_comodato_cloud"]),
            ],
            ["  sendo software", fmt_brl(t["mensal_venda_cloud"])],
            ["  sendo comodato equipamento", fmt_brl(n * COMODATO_CAMERA_MES)],
            ["Investimento cliente 1o ano", fmt_brl(t["ano1_comodato_cloud"])],
            ["Seu CAPEX inicial nas cameras", fmt_brl(t["capex_comodato"])],
            ["Payback so do comodato (meses)", f"{t['payback_comodato_meses']:.1f}"],
            ["Margem bruta no setup (so instalacao)", fmt_brl(t["margem_setup_comodato"])],
        ],
        [130, 60],
    )

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 9)
    rx(pdf)
    pdf.cell(0, 6, "C) Link de dados (cliente paga ao provedor)", new_x="LMARGIN", new_y="NEXT")
    tab(
        pdf,
        ["Situacao do cliente", "Custo mensal estimado"],
        [
            ["Ja tem fibra adequada (>= upload necessario)", fmt_brl(0)],
            [f"Contratar fibra empresarial (~200-300 Mbps)", fmt_brl(t["link_fibra"])],
            ["IP fixo (opcional, acesso remoto)", fmt_brl(LINK_IP_FIXO_MES)],
            ["Site sem fibra: 4G/5G empresarial (referencia)", fmt_brl(t["link_4g"])],
            ["Fibra + IP fixo", fmt_brl(t["link_fibra"] + LINK_IP_FIXO_MES)],
        ],
        [130, 60],
    )
    pdf.ln(2)


def main():
    pdf = PDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    secao(pdf, "1. Objetivo desta analise")
    p(
        pdf,
        "Nova camada de precificacao e custos empresariais considerando que voce entra com: "
        "(1) instalacao da camera, (2) comodato OU venda da camera no setup, e (3) o link de dados "
        "que o cliente precisa arcar caso ainda nao tenha conectividade suficiente para o analitico.",
    )

    secao(pdf, "2. Premissas de hardware e instalacao")
    tab(
        pdf,
        ["Item", "Seu custo", "Preco ao cliente"],
        [
            ["Camera IP Full HD (ref. linha Intelbras/corp.)", fmt_brl(CUSTO_CAMERA), fmt_brl(PRECO_VENDA_CAMERA)],
            ["Comodato da camera / mes", "(CAPEX seu)", fmt_brl(COMODATO_CAMERA_MES)],
            ["Instalacao padrao / camera", fmt_brl(CUSTO_INSTAL_INT), fmt_brl(PRECO_INSTAL)],
            ["Materiais medios / camera", fmt_brl(MATERIAIS_POR_CAM), "embutido na instalacao"],
        ],
        [80, 50, 60],
    )
    pdf.ln(1)
    p(
        pdf,
        "Referencias de mercado usadas: IM3/IM5 e afins na faixa de R$ 180 a R$ 360; "
        "instalacao Wi-Fi oficial Intelbras ~R$ 180/camera; instalacao IP/PoE profissional "
        "tipicamente R$ 200 a R$ 400/camera conforme cabeamento. Adotei valores medios comerciais.",
    )

    secao(pdf, "3. Premissas de link de dados (custo do cliente)")
    tab(
        pdf,
        ["Tipo de link", "Faixa mensal", "Quando usar"],
        [
            ["Fibra empresarial 200-300 Mbps", fmt_brl(100) + "-" + fmt_brl(170), "Padrao urbano/comercial"],
            ["IP fixo adicional", fmt_brl(40) + "-" + fmt_brl(80), "Acesso remoto estavel"],
            ["4G/5G site / backup", fmt_brl(80) + "-" + fmt_brl(150), "Sem fibra ou redundancia"],
            ["Upload por camera (analitico)", f"~{MBPS_POR_CAM} Mbps", "Substream para IA/cloud"],
        ],
        [70, 45, 75],
    )
    pdf.ln(1)
    p(
        pdf,
        "O link NAO entra na sua receita, salvo se voce revender conectividade. "
        "Na proposta, deixe explicito: 'conectividade por conta do cliente'. "
        "Para 20 cameras (~30 Mbps de upload), fibra 200 Mbps simetrica costuma bastar; "
        "Wi-Fi residencial fraco e risco operacional.",
    )

    secao(pdf, "4. Dois modelos de negocio de hardware")
    p(
        pdf,
        "VENDA: recupera CAPEX no setup, mensalidade menor, cliente dono do equipamento. "
        "Melhor para caixa curto e projetos pontuais.",
    )
    p(
        pdf,
        "COMODATO: voce financia as cameras, mensalidade maior (software + aluguel), "
        "maior retencao e LTV. Exige capital de giro e contrato com devolucao/reposicao. "
        "Payback tipico do equipamento sozinho: "
        + f"{CUSTO_CAMERA / COMODATO_CAMERA_MES:.0f} meses "
        + f"({fmt_brl(CUSTO_CAMERA)} / {fmt_brl(COMODATO_CAMERA_MES)}).",
    )

    pdf.add_page()
    bloco_cenario(pdf, 2)
    bloco_cenario(pdf, 10)

    pdf.add_page()
    bloco_cenario(pdf, 20)

    secao(pdf, "5. Comparativo consolidado - Cloud + hardware")
    rows = []
    for n in (2, 10, 20):
        t = totais(n)
        rows.append(
            [
                f"{n} cams",
                fmt_brl(t["setup_venda"]),
                fmt_brl(t["mensal_venda_cloud"]),
                fmt_brl(t["setup_comodato"]),
                fmt_brl(t["mensal_comodato_cloud"]),
            ]
        )
    tab(
        pdf,
        ["Cenario", "Setup venda", "Mensal venda", "Setup comodato", "Mensal comodato"],
        rows,
        [28, 38, 40, 42, 42],
    )
    pdf.ln(1)
    p(
        pdf,
        "Mensal venda = so software. Mensal comodato = software + "
        + fmt_brl(COMODATO_CAMERA_MES)
        + "/camera de equipamento.",
    )

    secao(pdf, "6. Total mensal do cliente com link (se precisar contratar fibra)")
    rows = []
    for n in (2, 10, 20):
        t = totais(n)
        rows.append(
            [
                f"{n} cams",
                fmt_brl(t["mensal_venda_cloud"] + LINK_FIBRA_MES),
                fmt_brl(t["mensal_comodato_cloud"] + LINK_FIBRA_MES),
                fmt_brl(LINK_FIBRA_MES),
            ]
        )
    tab(
        pdf,
        ["Cenario", "Venda+soft+fibra", "Comodato+soft+fibra", "So fibra (cliente)"],
        rows,
        [30, 50, 55, 55],
    )

    secao(pdf, "7. Impacto no seu caixa empresarial")
    tab(
        pdf,
        ["Tema", "Venda", "Comodato"],
        [
            ["Desembolso inicial (2 cams)", fmt_brl(totais(2)["custo_setup_venda"]), fmt_brl(totais(2)["capex_comodato"] + 2 * (CUSTO_INSTAL_INT + MATERIAIS_POR_CAM))],
            ["Desembolso inicial (10 cams)", fmt_brl(totais(10)["custo_setup_venda"]), fmt_brl(totais(10)["capex_comodato"] + 10 * (CUSTO_INSTAL_INT + MATERIAIS_POR_CAM))],
            ["Desembolso inicial (20 cams)", fmt_brl(totais(20)["custo_setup_venda"]), fmt_brl(totais(20)["capex_comodato"] + 20 * (CUSTO_INSTAL_INT + MATERIAIS_POR_CAM))],
            ["Recuperacao no setup", "Sim (margem imediata)", "Parcial (so instalacao)"],
            ["Risco de inadimplencia", "Menor no hardware", "Maior (ativo seu no cliente)"],
            ["Retencao / LTV", "Media", "Alta"],
        ],
        [55, 65, 70],
    )
    pdf.ln(1)
    p(
        pdf,
        "Recomendacao de mix: venda para clientes com CAPEX; comodato para assinatura "
        "recorrente (condominios, varejo, clinicas). Limite de comodato ativo ao capital "
        "disponivel (ex.: no maximo 30-50 cameras em comodato ate ter reserva).",
    )

    secao(pdf, "8. Precos de lista sugeridos (pacote completo)")
    tab(
        pdf,
        ["Componente", "Preco"],
        [
            ["Camera (venda unitaria)", fmt_brl(PRECO_VENDA_CAMERA)],
            ["Camera (comodato / mes)", fmt_brl(COMODATO_CAMERA_MES)],
            ["Instalacao / camera", fmt_brl(PRECO_INSTAL)],
            ["Software cloud / camera / mes", fmt_brl(SOFT_CLOUD)],
            ["Software on-prem manutencao / camera / mes", fmt_brl(SOFT_ONPREM)],
            ["Combo cloud+comodato / camera / mes", fmt_brl(SOFT_CLOUD + COMODATO_CAMERA_MES)],
        ],
        [110, 80],
    )

    secao(pdf, "9. Texto sugerido na proposta ao cliente")
    p(
        pdf,
        "\"Incluso: fornecimento da camera (venda ou comodato, conforme opcao), instalacao "
        "padrao e plataforma analitica C4ISTAR. Nao incluso: link de internet/dados do local, "
        "obras civis especiais, postes acima do padrao, energia dedicada fora de ate 3 m e "
        "cabos excedentes. Caso o local nao possua banda com upload suficiente "
        f"(cerca de {MBPS_POR_CAM} Mbps por camera), o contratante devera providenciar fibra "
        f"empresarial ou 4G/5G adequado, estimada entre {fmt_brl(100)} e {fmt_brl(170)}/mes "
        f"em fibra urbana, ou {fmt_brl(80)} a {fmt_brl(150)}/mes em link movel, conforme regiao.\"",
    )

    secao(pdf, "10. Avisos")
    p(
        pdf,
        "Valores de camera, instalacao e internet variam por cidade, altura, distancia de cabo, "
        "marca e negociacao com distribuidor. Documento indicativo para precificacao interna e "
        "propostas; valide custos reais de compra e viabilidade de link no endereco do cliente "
        "antes de fechar contrato. Comodato exige clausulas de extravio, furto, manutencao e devolucao.",
    )

    pdf.output(str(SAIDA))
    print(SAIDA.resolve())
    for n in (2, 10, 20):
        t = totais(n)
        print(
            n,
            "setup_v",
            round(t["setup_venda"], 2),
            "men_v",
            round(t["mensal_venda_cloud"], 2),
            "setup_c",
            round(t["setup_comodato"], 2),
            "men_c",
            round(t["mensal_comodato_cloud"], 2),
            "ano1_c",
            round(t["ano1_comodato_cloud"], 2),
        )


if __name__ == "__main__":
    main()
