"""PDF: requisitos de VM NVIDIA / containers para C4ISTAR MONITOR."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

SAIDA = Path("requisitos_infra_c4istar_vm_nvidia.pdf")


def fmt_agora() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.cell(
            0,
            8,
            "C4ISTAR MONITOR - Requisitos de infraestrutura (VM NVIDIA / containers)",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_font("Helvetica", "", 9)
        self.set_text_color(90, 90, 90)
        self.cell(
            0,
            6,
            f"Gerado em {fmt_agora()} | Para equipe de infra / DevOps | Indicativo",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Pagina {self.page_no()}/{{nb}} - C4ISTAR MONITOR", align="C")


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
        if fill:
            pdf.set_fill_color(245, 247, 250)
        else:
            pdf.set_fill_color(255, 255, 255)
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

    secao(pdf, "1. Objetivo")
    p(
        pdf,
        "Especificacao para provisionar uma maquina virtual com GPU NVIDIA e containers "
        "Docker para o C4ISTAR MONITOR: analitico de video (YOLO/pose/faces), portal web, "
        "ingest RTMP (MediaMTX) e Postgres. Destinado a equipe de infraestrutura / DevOps.",
    )

    secao(pdf, "2. Servicos na VM")
    tabela(
        pdf,
        ["Servico", "Funcao", "GPU"],
        [
            ["analitico", "YOLO + pose + faces/placas + portal (main.py)", "Sim"],
            ["mediamtx", "Ingest RTMP / play RTSP para cameras remotas", "Nao"],
            ["postgres", "Banco de eventos e cadastros", "Nao"],
            ["api (opcional)", "Ingest nuvem FastAPI (nuvem/)", "Nao"],
        ],
        [35, 115, 30],
    )
    pdf.ln(1)
    p(
        pdf,
        "Nota: o docker-compose atual em nuvem/ cobre db + api. Analitico e MediaMTX "
        "precisam de imagens/compose com NVIDIA Container Toolkit (ou rodar no host).",
    )

    secao(pdf, "3. Hardware sugerido")
    p(pdf, "Piloto (ate cerca de 4 cameras simultaneas):")
    bullet(pdf, "GPU: NVIDIA T4 (16 GB) ou equivalente (A10 / L4).")
    bullet(pdf, "vCPU: 8.")
    bullet(pdf, "RAM: 32 GB (minimo aceitavel 16 GB).")
    bullet(pdf, "Disco: 200 GB SSD (SO + modelos + evidencias + Postgres).")
    bullet(pdf, "Rede: 1 Gbps; IP publico ou NAT com portas liberadas.")
    pdf.ln(1)
    p(
        pdf,
        "Escala (orientacao): cerca de 4 cameras por T4 no stack completo "
        "(YOLO + pose + faces + LPR + audio). Acima disso: mais GPU ou replicas de worker.",
    )
    bullet(pdf, "Driver NVIDIA >= 535 + CUDA 12.x compativel com PyTorch/Ultralytics.")

    secao(pdf, "4. Software base (host / imagens)")
    bullet(pdf, "SO: Ubuntu 22.04 LTS (preferencial).")
    bullet(pdf, "Docker Engine + Compose v2.")
    bullet(pdf, "NVIDIA Container Toolkit (nvidia-container-toolkit) - GPU no container.")
    bullet(pdf, "FFmpeg no container do analitico ou sidecar (audio/RTSP).")
    bullet(pdf, "Python da app: 3.11 ou 3.12.")
    bullet(pdf, "Modelos no 1o start: yolov8n.pt, MediaPipe pose, SFace/OCR (cache em volume).")
    p(
        pdf,
        "Pacotes Python principais: ultralytics, opencv-python, mediapipe, numpy, "
        "rapidocr-onnxruntime, onnxruntime (ideal onnxruntime-gpu na VM), psycopg, "
        "fastapi, uvicorn, folium, psutil, neo4j (opcional).",
    )

    secao(pdf, "5. Arquitetura de containers")
    p(
        pdf,
        "Internet -> TCP 1935 (RTMP cameras) e TCP 443/8787 (portal) -> "
        "mediamtx (:1935/:8554) -> analitico GPU (portal :8787) -> postgres (:5432).",
    )
    tabela(
        pdf,
        ["Container", "Base sugerida", "Deploy"],
        [
            ["c4istar-analitico", "nvidia/cuda:12.x-runtime + Python", "runtime nvidia"],
            ["c4istar-mediamtx", "bluenviron/mediamtx:latest", "CPU"],
            ["c4istar-db", "postgres:16-alpine", "volume persistente"],
            ["c4istar-api", "nuvem/Dockerfile.api (existente)", "opcional"],
        ],
        [42, 85, 53],
    )
    pdf.ln(1)
    p(pdf, "Volumes persistentes:")
    bullet(pdf, "pgdata - Postgres.")
    bullet(pdf, "app-data - clientes/cameras JSON, evidencias, .env.")
    bullet(pdf, "models - pesos YOLO/pose (evita redownload).")

    secao(pdf, "6. Portas (firewall / security group)")
    tabela(
        pdf,
        ["Porta", "Proto", "Servico", "Exposicao"],
        [
            ["1935", "TCP", "MediaMTX RTMP (push camera)", "Publica (ou VPN)"],
            ["8787", "TCP", "Portal web", "Preferir 443 via proxy"],
            ["8554", "TCP", "RTSP play (analitico<->MediaMTX)", "So rede interna"],
            ["5432", "TCP", "Postgres", "So rede interna"],
            ["8080", "TCP", "API ingest (se usada)", "Interna + token"],
        ],
        [22, 22, 85, 51],
    )
    pdf.ln(1)
    bullet(pdf, "Nao expor RTSP das cameras do cliente (554) na VM.")

    secao(pdf, "7. Variaveis de ambiente (resumo)")
    bullet(pdf, "WEB_HOST=0.0.0.0 | WEB_PORT=8787 | WEB_HTTPS=1 (se TLS na frente).")
    bullet(pdf, "WEB_SENHA / usuarios da aplicacao.")
    bullet(pdf, "DATABASE_URL=postgresql://...")
    bullet(pdf, "RTMP_PUBLIC_HOST=<IP_ou_DNS_publico> | RTMP_PUBLIC_PORT=1935.")
    bullet(pdf, "RTMP_PLAY_HOST=mediamtx | RTMP_PLAY_PORT=8554.")
    bullet(pdf, "OPENAI_API_KEY (Stive), SMTP se e-mail.")
    bullet(pdf, "INGEST_TOKEN (se API nuvem).")

    secao(pdf, "8. Rede / DNS / operacao")
    bullet(pdf, "DNS ou IP estavel para portal e URL RTMP das cameras (Mibo/Intelbras).")
    bullet(pdf, "Camera empurrar para a VM (1935); nao abrir 554 do cliente.")
    bullet(pdf, "Reverse proxy (nginx/Traefik/Cloudflare) com TLS no portal.")
    bullet(pdf, "Healthcheck: GET portal /, pg_isready, nvidia-smi no host/container.")
    bullet(pdf, "Backup diario do volume Postgres + app-data.")
    bullet(pdf, "Logs stdout dos containers; retencao sugerida >= 14 dias.")
    bullet(pdf, "Disponibilidade piloto 24x7 do ingest + analitico.")

    secao(pdf, "9. Checklist para a equipe de infra")
    bullet(pdf, "1) VM Ubuntu 22.04 + GPU NVIDIA (T4/L4) + 32 GB RAM + 200 GB SSD.")
    bullet(pdf, "2) Driver NVIDIA + NVIDIA Container Toolkit.")
    bullet(pdf, "3) Docker Compose com runtime GPU.")
    bullet(pdf, "4) Liberar TCP 1935 e 443 (ou 8787).")
    bullet(pdf, "5) Volumes persistentes para DB e dados da app.")
    bullet(pdf, "6) Entregar: IP/DNS publico, SSH, confirmacao de nvidia-smi no container GPU.")

    secao(pdf, "10. Observacao comercial / capacidade")
    p(
        pdf,
        "Sem gravacao/ao vivo na plataforma (cliente usa app da camera). A VM processa "
        "stream economico RTMP so para analise e alertas. Orientacao interna de sizing: "
        "~4 cameras por GPU T4 no stack completo; validar com teste de capacidade 1/2/4 cameras.",
    )

    pdf.output(str(SAIDA))
    print(f"Gerado: {SAIDA.resolve()}")


if __name__ == "__main__":
    main()
