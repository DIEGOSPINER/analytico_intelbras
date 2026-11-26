"""PDF: arquitetura do banco Postgres C4ISTAR MONITOR."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

SAIDA = Path("arquitetura_banco_c4istar.pdf")


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.cell(
            0,
            8,
            "C4ISTAR MONITOR - Arquitetura do banco de dados (Postgres)",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_font("Helvetica", "", 9)
        self.set_text_color(90, 90, 90)
        self.cell(
            0,
            6,
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} | schema.sql + schema_sistema.sql | Indicativo",
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
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_fill_color(35, 55, 85)
    pdf.set_text_color(255, 255, 255)
    for i, h in enumerate(cabecalho):
        pdf.cell(larguras[i], 6, h, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(30, 30, 30)
    fill = False
    for linha in linhas:
        reset_x(pdf)
        pdf.set_fill_color(245, 247, 250) if fill else pdf.set_fill_color(255, 255, 255)
        for i, cel in enumerate(linha):
            pdf.cell(larguras[i], 5.5, cel[:90], border=1, fill=True, align="L")
        pdf.ln()
        fill = not fill
        if pdf.get_y() > 270:
            pdf.add_page()
    reset_x(pdf)


def main():
    pdf = PDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    secao(pdf, "1. Visao geral")
    p(
        pdf,
        "O C4ISTAR usa Postgres 16 como banco analitico multi-cliente. "
        "A chave de isolamento e cliente_documento (CPF/CNPJ) na maioria das tabelas. "
        "Cadastro operacional (contas, cameras, grupos, chat de vizinhos, config de alertas) "
        "ainda vive em arquivos JSON na aplicacao; o Postgres concentra historico de deteccoes, "
        "ocorrencias, faces, placas, audio, insights e metricas de sistema.",
    )
    bullet(pdf, "SGBD: PostgreSQL 16 (+ extensao pgcrypto).")
    bullet(pdf, "Schemas: db/schema.sql (negocio) e db/schema_sistema.sql (admin/capacidade).")
    bullet(pdf, "Acesso: DATABASE_URL / PG* via psycopg.")

    secao(pdf, "2. Arquitetura logica")
    p(
        pdf,
        "Camada borda/analitico (main.py) -> insert em tabelas de eventos -> "
        "portal/API le agregados para dashboards. "
        "Opcional: API de ingestao (nuvem) grava no mesmo modelo e registra ingestao_lote.",
    )
    bullet(pdf, "Dominio eventos: analitico, ocorrencias, faces, placas, audio, contagens.")
    bullet(pdf, "Dominio inteligencia: alertas_ia, insights.")
    bullet(pdf, "Dominio operacional humano: ocorrencias_informadas.")
    bullet(pdf, "Dominio custo: custos_mensagens.")
    bullet(pdf, "Dominio plataforma: metricas_sistema, metricas_tabelas_dia, metricas_desempenho, testes_capacidade.")
    bullet(pdf, "Fora do Postgres (JSON): clientes.json, cameras.json, grupos_seguranca.json, vizinhos_chat.json, config_alertas.json.")

    secao(pdf, "3. Catalogo de tabelas (negocio)")
    tabela(
        pdf,
        ["Tabela", "Papel", "Chaves / indices principais"],
        [
            ["clientes", "Cadastro minimo no PG", "PK documento"],
            ["analitico", "Deteccoes YOLO (classe/track)", "ix (cliente,data) (camera,data)"],
            ["ocorrencias", "Comportamentos / risco", "ix (cliente,data) (nivel_risco,data)"],
            ["faces", "Reconhecimento facial", "ix (cliente,face_id,data)"],
            ["placas", "LPR / placas", "ix (cliente,placa,data)"],
            ["audio", "Eventos de audio/transcricao", "ix (cliente,data) (nivel,data)"],
            ["ocorrencias_informadas", "Ocorrencias lancadas no app", "ix (cliente,data)"],
            ["alertas_ia", "Alertas gerados pela IA", "id + cliente_documento"],
            ["insights", "Insights/relatorios GPT", "id + cliente_documento"],
            ["contagens", "Snapshot pessoas/veiculos", "cliente + data + camera"],
            ["ingestao_lote", "Auditoria de lotes borda->nuvem", "id + cliente"],
            ["custos_mensagens", "Custo e-mail/WhatsApp/GPT", "ix (cliente,quando)"],
        ],
        [42, 70, 68],
    )

    secao(pdf, "4. Catalogo de tabelas (sistema / admin)")
    tabela(
        pdf,
        ["Tabela", "Papel", "Chaves / indices"],
        [
            ["metricas_sistema", "CPU/RAM/disco do host", "ix quando DESC"],
            ["metricas_tabelas_dia", "Tamanho por tabela/dia", "PK (dia, tabela)"],
            ["metricas_desempenho", "Latencia/FPS por amostra", "ix quando; cameras_json JSONB"],
            ["testes_capacidade", "Testes 1/2/4 cameras", "PK n_cameras; cameras_json"],
        ],
        [45, 75, 60],
    )

    pdf.add_page()
    secao(pdf, "5. Estrutura detalhada - eventos")

    p(pdf, "analitico: id BIGSERIAL, cliente_documento, data DATE, hora TIME, camera, categoria, classe, track_id, total_unicos, qtd_cena, criado_em.")
    p(pdf, "ocorrencias: campos do analitico + id_alvo, duracao_segundos, confianca, status, pessoas_envolvidas, detalhe, risco, nivel_risco, qualidade_pose.")
    p(pdf, "faces: cliente_documento, data/hora, camera, face_id, evento, total_passagens, track_id, confianca, proximidade, caminho_foto, foto_referencia.")
    p(pdf, "placas: cliente_documento, data/hora, camera, placa_id, placa, evento, total_passagens, track_id_veiculo, tipo_veiculo, confianca, fotos.")
    p(pdf, "audio: cliente_documento, data/hora, camera, tipo, categoria, nivel, texto, palavras, confianca, detalhe.")
    p(pdf, "contagens: cliente_documento, data/hora, camera, pessoas, veiculos.")

    secao(pdf, "6. Estrutura detalhada - inteligencia e custo")
    p(pdf, "alertas_ia: datas de geracao/evento, origem, tipo, ident, nome, motivo, camera, evento, passagens, nivel, descricao, foto, modelo, arquivo_relatorio.")
    p(pdf, "insights: periodo, inicio/fim, tipo, nome, valor, descricao, nivel, modelo, arquivo_relatorio.")
    p(pdf, "ocorrencias_informadas: id_externo, natureza, descricao, endereco, lat/long, placa, pessoa, ligacoes, situacoes, foto, video.")
    p(pdf, "custos_mensagens: canal, direcao, unidades, usd_estimado, detalhe, referencia, quando.")
    p(pdf, "ingestao_lote: origem (borda), tabela destino, quantidade, recebido_em.")

    secao(pdf, "7. Modelo multi-cliente")
    bullet(pdf, "Quase todas as tabelas de negocio trazem cliente_documento VARCHAR(20).")
    bullet(pdf, "Filtros do portal e da API agregam por documento da sessao (admin ve tudo).")
    bullet(pdf, "clientes no PG e espelho minimo; o cadastro rico (cameras, pessoas, veiculos) esta em clientes.json.")
    bullet(pdf, "Nao ha FK formal entre eventos e clientes (inserção resiliente sem ordem estrita).")

    secao(pdf, "8. Indices e performance")
    bullet(pdf, "Consultas de dashboard: (cliente_documento, data) em analitico/ocorrencias/audio.")
    bullet(pdf, "Consulta por camera: ix_analitico_camera (camera, data).")
    bullet(pdf, "Risco: ix_ocorrencias_risco (nivel_risco, data).")
    bullet(pdf, "Faces/placas: indices compostos com id + data.")
    bullet(pdf, "Metricas admin: ordenacao por quando DESC.")
    bullet(pdf, "JSONB em desempenho/capacidade para detalhe por camera sem normalizar.")

    secao(pdf, "9. Dados fora do Postgres (complemento)")
    tabela(
        pdf,
        ["Arquivo JSON", "Conteudo"],
        [
            ["clientes.json", "Contas, cameras, pessoas, veiculos, avisos"],
            ["cameras.json", "Espelho das cameras ativas para o analitico"],
            ["grupos_seguranca.json", "Grupos, membros, cameras compartilhadas, alertas"],
            ["vizinhos_chat.json", "Contatos, chats 1:1 e chat de grupo"],
            ["config_alertas.json", "Preferencias de alerta por usuario"],
            ["interesse.json / grafo", "POI e relacoes (quando ativos)"],
        ],
        [55, 125],
    )
    pdf.ln(1)
    p(
        pdf,
        "Estrategia: JSON para configuracao mutavel de produto; Postgres para serie temporal "
        "e auditoria de eventos em volume.",
    )

    secao(pdf, "10. Diagrama textual de fluxo")
    p(
        pdf,
        "Camera (RTSP/RTMP) -> analitico GPU -> INSERT analitico/ocorrencias/faces/placas/audio "
        "-> (opcional) ingestao_lote via API -> SELECT agregado no portal (/dados.json) "
        "-> cards, mapas, Stive. Em paralelo: metricas_sistema/desempenho alimentam /sistema.",
    )

    secao(pdf, "11. Requisitos de deploy do banco")
    bullet(pdf, "Imagem: postgres:16-alpine (compose em nuvem/docker-compose.yml).")
    bullet(pdf, "Init: montar db/schema.sql (+ schema_sistema.sql na subida da app).")
    bullet(pdf, "Volume persistente pgdata; backup diario recomendado.")
    bullet(pdf, "Porta 5432 apenas na rede interna dos containers.")
    bullet(pdf, "Credenciais via DATABASE_URL / POSTGRES_PASSWORD.")

    pdf.output(str(SAIDA))
    print(f"Gerado: {SAIDA.resolve()}")


if __name__ == "__main__":
    main()
