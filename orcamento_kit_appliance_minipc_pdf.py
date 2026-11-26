"""PDF de orcamento: appliance mini-PC C4ISTAR (computador bloqueado, so a aplicacao)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

SAIDA = Path("orcamento_kit_appliance_c4istar_brl.pdf")


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
            "C4ISTAR MONITOR - Orcamento Kit Appliance (mini-PC bloqueado)",
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
                "Valores indicativos Brasil (consultar frete/estoque) | Documento comercial interno"
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
            f"Pagina {self.page_no()}/{{nb}} - nao substitui cotacao formal de fornecedor",
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

    secao(pdf, "1. Decisao de produto")
    paragrafo(
        pdf,
        "Em vez de Raspberry ou instalador para o vizinho, entregamos um COMPUTADOR APLICACAO: "
        "mini-PC ja configurado, bloqueado para uso apenas do C4ISTAR MONITOR. "
        "O cliente liga na tomada e no roteador; o app/portal e so para alertas, POI e ocorrencias. "
        "Equivalente comercial ao NVR/appliance: hardware seu + software seu + conta na plataforma.",
    )
    bullet(pdf, "Usuario comum: nao instala Python, Tailscale nem edita .env.")
    bullet(pdf, "Voce (ou a fabrica de imagem): grava, provisiona e envia o kit.")
    bullet(pdf, "Celular do cliente: somente consumo (app). Analise fica no appliance.")

    secao(pdf, "2. Especificacao tecnica alvo (1 a 2 cameras)")
    tabela(
        pdf,
        ["Item", "Especificacao"],
        [
            ["CPU", "Intel N100 / N305 (baixo consumo, 24h)"],
            ["RAM", "16 GB (obrigatorio para YOLO + portal)"],
            ["Disco", "SSD NVMe 512 GB"],
            ["Rede", "Ethernet Gigabit (preferencial) + Wi-Fi reserva"],
            ["SO", "Windows 11 Pro OU Ubuntu 24.04 LTS (imagem locked)"],
            ["Video", "Analise 1 camera confortavel; 2 com perfil leve"],
            ["Extras", "Auto-start C4ISTAR, Tailscale, watchdog, sem desktop livre"],
        ],
        [40, 150],
    )

    secao(pdf, "3. BOM - custo de aquisicao (indicativo BR)")
    tabela(
        pdf,
        ["Item", "Qtd", "Faixa baixa", "Faixa alta", "Obs."],
        [
            ["Mini-PC N100 16GB/512GB", "1", fmt_brl(1800), fmt_brl(3000), "Beelink/GMKtec/equiv."],
            ["Cabo Ethernet Cat6 3-5m", "1", fmt_brl(25), fmt_brl(50), "Evitar Wi-Fi no RTSP"],
            ["Filtro de linha / tomada", "1", fmt_brl(40), fmt_brl(90), "Estabilidade"],
            ["Embalagem + etiqueta", "1", fmt_brl(30), fmt_brl(80), "Kit Casa"],
            ["Provisionamento (mao de obra)", "1", fmt_brl(200), fmt_brl(450), "Imagem + teste"],
            ["Suporte 90 dias (reserva)", "1", fmt_brl(100), fmt_brl(250), "Troca/ Remoto"],
        ],
        [55, 15, 30, 30, 60],
    )
    pdf.ln(1)
    paragrafo(
        pdf,
        f"Subtotal appliance SEM camera: cerca de {fmt_brl(2195)} a {fmt_brl(3920)}. "
        f"Referencias de mercado observadas ~{fmt_brl(1800)} a {fmt_brl(3000)} so o mini-PC.",
    )

    secao(pdf, "4. SKUs comerciais")
    tabela(
        pdf,
        ["SKU", "Conteudo", "Custo seu", "Setup sugerido", "Mensalidade"],
        [
            [
                "Appliance Casa",
                "Mini-PC locked + cabos",
                f"{fmt_brl(2200)}-{fmt_brl(3900)}",
                f"{fmt_brl(3490)}-{fmt_brl(4990)}",
                "Plano Casa",
            ],
            [
                "Kit Casa+",
                "Appliance + camera RTSP",
                f"{fmt_brl(2600)}-{fmt_brl(4700)}",
                f"{fmt_brl(4490)}-{fmt_brl(6490)}",
                "Plano Casa",
            ],
            [
                "So conta",
                "Sem hardware",
                fmt_brl(0),
                fmt_brl(0),
                "Plano Comunidade",
            ],
        ],
        [32, 48, 35, 40, 35],
    )
    pdf.ln(1)
    paragrafo(
        pdf,
        "Camera Intelbras iM3/equiv. (se inclusa): some ~"
        f"{fmt_brl(350)} a {fmt_brl(700)} + fonte/cabo.",
    )

    secao(pdf, "5. Bloqueio do computador (kiosk / appliance)")
    paragrafo(pdf, "Objetivo: o cliente nao usa como PC pessoal.")
    bullet(pdf, "Usuario Windows sem direitos de admin; conta 'c4istar' auto-login.")
    bullet(pdf, "Shell de inicializacao: so iniciar.bat / servico C4ISTAR (sem Explorer livre).")
    bullet(pdf, "Politica: bloquear loja, USB de instalacao, navegador generico (ou so URL do portal).")
    bullet(pdf, "Atualizacao so via seu canal (script assinado / Tailscale).")
    bullet(pdf, "Tailscale pre-enrolado com chave unica por cliente + CLIENTE_DOCUMENTO.")
    bullet(pdf, "Watchdog: se o analítico cair, reinicia o servico; LED/status 'Online'.")
    bullet(pdf, "Etiqueta no aparelho: 'Equipamento C4ISTAR - nao formatar'.")

    secao(pdf, "6. Fluxo de entrega ao vizinho leigo")
    tabela(
        pdf,
        ["Passo", "Quem", "Acao"],
        [
            ["1", "Voce", "Grava imagem, testa 1 camera, gera chave Tailscale"],
            ["2", "Voce", "Envia/leva a caixa + cartao 'Ligue tomada + cabo de rede'"],
            ["3", "Cliente", "Pluga no roteador e na tomada"],
            ["4", "Sistema", "Sobe, conecta na plataforma, aparece Online"],
            ["5", "Cliente", "Abre app/portal com e-mail e senha (plano ativo)"],
        ],
        [20, 25, 145],
    )

    secao(pdf, "7. Por que nao Raspberry neste SKU")
    paragrafo(
        pdf,
        "Raspberry cabe em prototipo, mas o cliente percebe e recebe um computador. "
        "Mini-PC N100 entrega melhor YOLO/pose/audio, suporte Windows familiar, "
        "SSD confiavel 24h e posicionamento de 'aparelho da operadora' (como NVR), "
        "com custo de hardware na mesma ordem de grandeza do kit Pi 'completo + dor de imagem'.",
    )

    secao(pdf, "8. Checklist de imagem (provisionamento)")
    for item in (
        "SO limpo + drivers rede",
        "C4ISTAR em C:\\C4ISTAR (venv, modelos, cameras.json template)",
        "Servico/auto-start + watchdog",
        "Tailscale instalado e autenticado (tag do cliente)",
        "WEB_SENHA/usuarios iniciais OU so ingestao para nuvem",
        "CLIENTE_DOCUMENTO e NUVEM_API_URL/INGEST_TOKEN",
        "Firewall so portas necessarias",
        "Teste: 30 min RTSP + 1 alerta + heartbeat na plataforma",
        "Remover ferramentas de desenvolvimento da imagem de producao",
    ):
        bullet(pdf, item)

    secao(pdf, "9. Resumo executivo")
    paragrafo(
        pdf,
        "Produto a vender: APPLIANCE C4ISTAR (mini-PC bloqueado), nao 'instalacao avancada'. "
        "Custo seu tipico ~2,2 a 3,9 mil sem camera; venda de setup ~3,5 a 5,0 mil + mensalidade Casa. "
        "Plano Comunidade continua sem hardware. Proximo passo: escolher 1 modelo de mini-PC, "
        "congelar imagem v1 e testar com o primeiro vizinho.",
    )

    pdf.output(str(SAIDA))
    print(f"Gerado: {SAIDA.resolve()}")


if __name__ == "__main__":
    main()
