"""Proposta C4ISTAR: escala RTMP (so analise/alertas) + metas de pro-labore."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

SAIDA = Path("proposta_c4istar_rtmp_prolabore_brl.pdf")

# Premissas de custo (sem ao vivo / sem gravacao na plataforma)
CUSTO_CAM_MES = 45.0          # ingest + fatia CPU YOLO compartilhada (stream economica)
CUSTO_CONTA_MES = 8.0         # Stive/GPT leve, e-mail, infra conta
FIXO_MES = 2500.0             # VPS base, dominio, ferramentas, contingencia
MARGEM_EMPRESA_ALVO = 0.25    # 25% do faturamento liquido operacional apos custo variavel+fixo
CARGA_TRIBUTARIA = 0.12       # Simples aproximado sobre faturamento
PRECO_COMUNIDADE = 49.90
PRECO_CAMERA_RTMP = 129.90    # plano Casa: 1 camera analise/alertas
MIX_CAM_POR_PAGANTE = 0.55    # 55% dos pagantes tem 1 camera; resto so Comunidade


def fmt(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _cenario(clientes: float, prolabore: float) -> dict:
    n_casa = clientes * MIX_CAM_POR_PAGANTE
    n_com = clientes - n_casa
    receita = n_casa * PRECO_CAMERA_RTMP + n_com * PRECO_COMUNIDADE
    custo_var = n_casa * CUSTO_CAM_MES + clientes * CUSTO_CONTA_MES
    liquido = receita * (1 - CARGA_TRIBUTARIA)
    lucro = liquido - custo_var - FIXO_MES - prolabore
    return {
        "prolabore": prolabore,
        "clientes": int(round(clientes)),
        "n_casa": int(round(n_casa)),
        "n_com": int(round(n_com)),
        "receita": receita,
        "custo_var": custo_var,
        "fixo": FIXO_MES,
        "tributos": receita * CARGA_TRIBUTARIA,
        "liquido": liquido,
        "lucro": lucro,
        "margem_sobre_liquido": (lucro / liquido) if liquido else 0,
    }


def receita_necessaria(prolabore: float) -> dict:
    """Clientes pagantes para cobrir pro-labore + margem empresa + impostos + custos."""
    # liquido = receita * (1 - tributo)
    # lucro = liquido - custo_var - fixo - prolabore
    # alvo: lucro >= margem * liquido
    lo, hi = 10.0, 2000.0
    best = _cenario(hi, prolabore)
    for _ in range(50):
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
            "C4ISTAR MONITOR - Proposta de escala RTMP e metas de pro-labore",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_font("Helvetica", "", 9)
        self.set_text_color(90, 90, 90)
        self.cell(
            0,
            6,
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} | Sem ao vivo/gravacao na plataforma | Indicativo",
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

    secao(pdf, "1. Proposta de valor (o que vendemos)")
    p(
        pdf,
        "A plataforma C4ISTAR nao compete com o app da camera (ao vivo/gravacao). "
        "O cliente ja tem isso na Mibo/Intelbras. Vendemos INTELIGENCIA: alertas, "
        "reconhecimento de interesse, ocorrencias, grupos de vizinhos, Stive e "
        "configuracao do que chega por plano. A camera Mibo envia RTMP (stream economica) "
        "so para analise; sem retransmitir ao vivo e sem gravar na nossa nuvem.",
    )
    bullet(pdf, "POC de rua / food truck: camera + Wi-Fi + URL RTMP.")
    bullet(pdf, "Casa: 1 link RTMP por camera no app Mibo (Personalizado).")
    bullet(pdf, "Sem camera: plano Comunidade (alertas de grupo, POI, ocorrencias).")

    secao(pdf, "2. Pacotes e precos sugeridos")
    tabela(
        pdf,
        ["Plano", "Inclui", "Preco/mes"],
        [
            ["Comunidade", "App/portal, POI, ocorrencias, grupos, alertas recebidos", fmt(PRECO_COMUNIDADE)],
            ["Casa (1 cam RTMP)", "Comunidade + 1 stream key + analise/alertas", fmt(PRECO_CAMERA_RTMP)],
            ["Casa +N", "Cada camera adicional RTMP", fmt(99.90) + " /cam"],
            ["Setup POC", "Gerar link + checklist Mibo (opcional)", fmt(0) + " a " + fmt(149)],
        ],
        [40, 105, 45],
    )
    pdf.ln(1)
    p(
        pdf,
        "Premissa de mix na simulacao: 55% dos pagantes no Casa (1 camera) e 45% so Comunidade.",
    )

    secao(pdf, "3. Estrutura tecnica minima (sua)")
    bullet(pdf, "1x VPS ingest MediaMTX/SRS (RTMPS) + worker YOLO compartilhado.")
    bullet(pdf, "1 stream key por camera; portal gera URL para colar no Mibo.")
    bullet(pdf, "Sem HLS/ao vivo e sem storage de video = custo bem menor.")
    bullet(pdf, "Custo medio estimado/camera: " + fmt(CUSTO_CAM_MES) + " (banda entrada + CPU).")
    bullet(pdf, "Custo medio/conta: " + fmt(CUSTO_CONTA_MES) + " (Stive/e-mail/infra).")
    bullet(pdf, "Fixo mensal base: " + fmt(FIXO_MES) + " (VPS, dominio, ferramentas).")
    bullet(pdf, "Tributos aproximados Simples: " + f"{int(CARGA_TRIBUTARIA*100)}% sobre faturamento.")
    bullet(pdf, "Margem empresarial alvo: " + f"{int(MARGEM_EMPRESA_ALVO*100)}% sobre o liquido.")

    secao(pdf, "4. Metas de pro-labore (5 / 10 / 15 / 20 mil)")
    p(
        pdf,
        "Leitura: quantos clientes pagantes (mix acima) para retirar o pro-labore "
        "e ainda sobrar margem para a empresa apos custos e tributos.",
    )
    linhas = []
    for valor in (5000, 10000, 15000, 20000):
        r = receita_necessaria(float(valor))
        linhas.append([
            fmt(r["prolabore"]),
            str(r["clientes"]),
            f"{r['n_casa']} casa / {r['n_com']} com.",
            fmt(r["receita"]),
            fmt(r["lucro"]),
            f"{r['margem_sobre_liquido']*100:.0f}%",
        ])
    tabela(
        pdf,
        ["Pro-labore", "Clientes", "Mix (aprox.)", "Receita/mes", "Lucro empresa", "Margem liq."],
        linhas,
        [30, 25, 40, 32, 33, 30],
    )
    pdf.ln(1)
    p(
        pdf,
        "Lucro empresa = o que fica na companhia apos pro-labore, custos e tributos "
        "(caixa para reinvestimento, reserva, falhas de camera, marketing).",
    )

    secao(pdf, "5. Caminho de crescimento (operacional)")
    tabela(
        pdf,
        ["Fase", "Foco", "Meta operacional"],
        [
            ["0-3 meses", "POC ruas + 1 bairro", "20-40 pagantes; validar RTMP Mibo"],
            ["3-6 meses", "Vizinhos + grupos", "80-120 pagantes; automacao de keys"],
            ["6-12 meses", "Varios bairros", "200+ pagantes; pro-labore 10-15k"],
            ["12+ meses", "Operacao enxuta", "300-450 pagantes; pro-labore 20k + margem"],
        ],
        [30, 50, 110],
    )

    secao(pdf, "6. Estrutura societaria / caixa (simples)")
    bullet(pdf, "CNPJ software/SaaS (nao CNAE de vigilancia como principal).")
    bullet(pdf, "Conta PJ: receita dos planos; pro-labore mensal fixo por meta.")
    bullet(pdf, "Reserva minima: 2 meses de fixo+custos variaveis antes de subir pro-labore.")
    bullet(pdf, "Nao incluir ao vivo/gravacao no custo - cliente usa app da camera.")
    bullet(pdf, "Upsell depois: camera extra, grupo condominio, appliance 24h pesado.")

    secao(pdf, "7. Oferta em uma frase")
    p(
        pdf,
        "\"Cole o link RTMP no app Mibo. Voce continua vendo e gravando la; "
        "a C4ISTAR avisa o que importa - pessoas de interesse, disparos, fluxo, "
        "ocorrencias e a rede de vizinhos.\"",
    )

    secao(pdf, "8. Proximos passos")
    bullet(pdf, "Subir ingest RTMPS + tela 'Copiar URL para o Mibo'.")
    bullet(pdf, "Planos Comunidade/Casa no cadastro + cobranca (Pix/Asaas).")
    bullet(pdf, "1 POC de rua (food truck) documentada.")
    bullet(pdf, "Congelar precos da secao 2 por 90 dias de piloto.")

    pdf.output(str(SAIDA))
    print(f"Gerado: {SAIDA.resolve()}")
    for valor in (5000, 10000, 15000, 20000):
        r = receita_necessaria(float(valor))
        print(
            f"Pro-labore {fmt(r['prolabore'])}: ~{r['clientes']} clientes | "
            f"receita {fmt(r['receita'])} | lucro {fmt(r['lucro'])}"
        )


if __name__ == "__main__":
    main()
