"""Gera PDF de estimativa de custo em nuvem (AWS / GCP / Azure) em BRL."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

# PTAX venda 11/11/2026 (BCB)
CAMBIO = 5.5606
DATA_CAMBIO = "11/11/2026"
SAIDA = Path("relatorio_estimativa_custo_nuvem_brl.pdf")

# Totais mensais on-demand (USD) — mesma estimativa já apresentada
ON_DEMAND = {
    2: {"aws": 490, "gcp": 505, "azure": 490},
    10: {"aws": 1360, "gcp": 1400, "azure": 1360},
    100: {"aws": 10600, "gcp": 10900, "azure": 10600},
}

# Faixa com compromisso 1 ano (média da faixa)
ANO1 = {
    2: {"min": 320, "max": 360},
    10: {"min": 900, "max": 1000},
    100: {"min": 6800, "max": 7400},
}

# Detalhe AWS on-demand (USD)
DETALHE_AWS = {
    2: {
        "gpu": 384,
        "disco_db": 70,
        "storage": 3,
        "egress": 25,
        "gpt": 5,
    },
    10: {
        "gpu": 1152,
        "disco_db": 130,
        "storage": 5,
        "egress": 50,
        "gpt": 20,
    },
    100: {
        "gpu": 9600,
        "disco_db": 650,
        "storage": 15,
        "egress": 240,
        "gpt": 100,
    },
}

NOS_T4 = {2: 1, 10: 3, 100: 25}


def brl(usd: float) -> float:
    return float(usd) * CAMBIO


def fmt_brl(valor: float) -> str:
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_usd(valor: float) -> str:
    return f"US$ {valor:,.0f}".replace(",", ".")


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.cell(0, 8, "C4ISTAR MONITOR - Estimativa de custo em nuvem", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(90, 90, 90)
        self.cell(
            0,
            6,
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} | Cambio PTAX venda {DATA_CAMBIO}: US$ 1 = R$ {CAMBIO:.4f}".replace(".", ","),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Pagina {self.page_no()}/{{nb}} - estimativa indicativa, nao e cotacao comercial", align="C")


def tabela(pdf: PDF, cabecalho: list[str], linhas: list[list[str]], larguras: list[float]):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(35, 55, 85)
    pdf.set_text_color(255, 255, 255)
    for i, h in enumerate(cabecalho):
        pdf.cell(larguras[i], 7, h, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(30, 30, 30)
    fill = False
    for linha in linhas:
        pdf.set_x(pdf.l_margin)
        pdf.set_fill_color(245, 247, 250) if fill else pdf.set_fill_color(255, 255, 255)
        for i, cel in enumerate(linha):
            align = "R" if i > 0 else "L"
            pdf.cell(larguras[i], 6.5, cel, border=1, fill=True, align=align)
        pdf.ln()
        fill = not fill
    pdf.set_x(pdf.l_margin)


def secao(pdf: PDF, titulo: str):
    pdf.set_x(pdf.l_margin)
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(25, 45, 75)
    pdf.cell(0, 8, titulo, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(30, 30, 30)


def paragrafo(pdf: PDF, texto: str):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, texto)
    pdf.set_x(pdf.l_margin)


def main():
    pdf = PDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    secao(pdf, "1. Resumo executivo")
    paragrafo(
        pdf,
        "Estimativa mensal para processamento de IA (YOLO, pose, faces, LPR/OCR) + armazenamento "
        "de eventos/metadados + GPT (Stive), em AWS, Google Cloud e Azure, para 2, 10 e 100 cameras. "
        "Valores totais abaixo ja convertidos para reais com PTAX venda do Banco Central.",
    )
    paragrafo(
        pdf,
        "Melhor custo-beneficio: self-host em GPU NVIDIA T4 com compromisso de 1 ano "
        "(Savings Plan / Reserved / CUD). AWS e Azure empatam no T4; GCP fica no mesmo patamar. "
        "Evitar Vision APIs gerenciadas em fluxo continuo e operar so em CPU na nuvem.",
    )

    secao(pdf, "2. Totais mensais on-demand (R$)")
    linhas = []
    for n in (2, 10, 100):
        a = ON_DEMAND[n]
        linhas.append([
            f"{n} cameras",
            fmt_brl(brl(a["aws"])),
            fmt_brl(brl(a["gcp"])),
            fmt_brl(brl(a["azure"])),
            f"{NOS_T4[n]} no(s) T4",
        ])
    tabela(
        pdf,
        ["Escala", "AWS", "GCP", "Azure", "Capacidade"],
        linhas,
        [28, 38, 38, 38, 48],
    )
    paragrafo(
        pdf,
        "Referencia USD embutida: 2 cams AWS/Azure US$ 490 | GCP US$ 505; "
        "10 cams US$ 1.360 / 1.400 / 1.360; 100 cams US$ 10.600 / 10.900 / 10.600.",
    )

    secao(pdf, "3. Totais com compromisso 1 ano (R$)")
    linhas = []
    for n in (2, 10, 100):
        faixa = ANO1[n]
        linhas.append([
            f"{n} cameras",
            fmt_brl(brl(faixa["min"])),
            fmt_brl(brl(faixa["max"])),
            "AWS / Azure / GCP",
        ])
    tabela(
        pdf,
        ["Escala", "Minimo", "Maximo", "Provedores"],
        linhas,
        [35, 45, 45, 65],
    )
    paragrafo(
        pdf,
        "Desconto estimado de 35-40% apenas no compute GPU; storage, egress e GPT permanecem semelhantes.",
    )

    secao(pdf, "4. Custo por camera / mes (on-demand, pacote completo)")
    linhas = []
    for n in (2, 10, 100):
        total = ON_DEMAND[n]["aws"]
        por_cam = total / n
        linhas.append([
            f"{n} cameras",
            fmt_usd(por_cam),
            fmt_brl(brl(por_cam)),
        ])
    tabela(pdf, ["Escala", "USD / camera", "R$ / camera"], linhas, [40, 50, 50])

    secao(pdf, "5. Detalhe por bloco - AWS on-demand (referencia)")
    for n in (2, 10, 100):
        d = DETALHE_AWS[n]
        total = sum(d.values())
        # alinhar ao total redondo da tabela principal
        alvo = ON_DEMAND[n]["aws"]
        misc = max(0, alvo - total)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, f"{n} cameras ({NOS_T4[n]} x T4)", new_x="LMARGIN", new_y="NEXT")
        linhas = [
            ["GPU T4 (IA visao)", fmt_usd(d["gpu"]), fmt_brl(brl(d["gpu"]))],
            ["Disco + DB Postgres", fmt_usd(d["disco_db"]), fmt_brl(brl(d["disco_db"]))],
            ["Object storage", fmt_usd(d["storage"]), fmt_brl(brl(d["storage"]))],
            ["Egress / rede", fmt_usd(d["egress"]), fmt_brl(brl(d["egress"]))],
            ["GPT / Stive (LLM)", fmt_usd(d["gpt"]), fmt_brl(brl(d["gpt"]))],
            ["Misc / margem", fmt_usd(misc), fmt_brl(brl(misc))],
            ["TOTAL", fmt_usd(alvo), fmt_brl(brl(alvo))],
        ]
        tabela(pdf, ["Item", "USD", "R$"], linhas, [70, 40, 50])
        pdf.ln(1)

    pdf.add_page()
    secao(pdf, "6. Premissas tecnicas")
    for item in [
        "- Pipeline self-hosted 24x7: YOLO + pose + faces (SFace) + LPR/OCR + audio.",
        "- Capacidade observada hoje: 2 cameras saturam CPU local (~100%); PyTorch/ORT em CPU.",
        "- Planejamento GPU: ~4 cameras por NVIDIA T4 (conservador para o stack completo).",
        "- Nos T4: 2 cams = 1; 10 cams = 3; 100 cams = 25.",
        "- Armazenamento: eventos, crops, metadados e DB (~5 GB/camera/mes), sem video continuo.",
        "- LLM (Stive): GPT-4o-mini, cerca de US$ 1-2 por camera/mes.",
        "- Regiao de preco: US East, lista on-demand, 730 horas/mes.",
        "- Fora do escopo: gravacao continua RTSP, impostos BR, IOF, margem de cambio, regiao Brasil (+20-40%).",
    ]:
        paragrafo(pdf, item)

    secao(pdf, "7. Recomendacao")
    paragrafo(
        pdf,
        "1) Self-host da IA de visao em T4 (nao usar Rekognition/Vision/Azure AI Vision por frame continuo).",
    )
    paragrafo(
        pdf,
        "2) Fechar compromisso de 1 ano para reduzir o maior item da conta (GPU).",
    )
    paragrafo(
        pdf,
        "3) AWS e Azure empatam no T4; GCP e equivalente e pode melhorar com CUD+SUD. "
        "Escolha pratica: AWS se priorizar S3/RDS; GCP se CUD for agressivo; Azure se houver credito Microsoft.",
    )
    paragrafo(
        pdf,
        "4) Em 100 cameras o orcamento e dominado por GPU; storage de eventos e residual.",
    )

    secao(pdf, "8. Totais consolidados em reais (destaque)")
    linhas = []
    for n in (2, 10, 100):
        od = ON_DEMAND[n]["aws"]
        a1 = ANO1[n]
        linhas.append([
            f"{n} cameras",
            fmt_brl(brl(od)),
            f"{fmt_brl(brl(a1['min']))} a {fmt_brl(brl(a1['max']))}",
        ])
    tabela(
        pdf,
        ["Escala", "On-demand (AWS/Azure ref.)", "1 ano (faixa)"],
        linhas,
        [30, 70, 90],
    )

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.ln(4)
    pdf.multi_cell(
        0,
        4.5,
        "Aviso: valores indicativos com base em precos publicos de lista (US East) e cambio PTAX. "
        "Nao incluem impostos brasileiros, descontos privados, Spot/preemptible, nem cotacao comercial de provedor. "
        "Revise na calculadora oficial antes de contratar.",
    )

    pdf.output(str(SAIDA))
    print(SAIDA.resolve())
    print(f"cambio={CAMBIO}")
    for n in (2, 10, 100):
        print(n, "OD_BRL", round(brl(ON_DEMAND[n]["aws"]), 2), "ANO1", round(brl(ANO1[n]["min"]), 2), "-", round(brl(ANO1[n]["max"]), 2))


if __name__ == "__main__":
    main()
