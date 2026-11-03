"""Relatórios, memória da rua e leitura do GPT sobre os números já calculados."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path

from agente.fontes import FonteCsv, cruzar_interesse, periodo
from agente.modelo import SessaoGPT, extrair_json


PASTA_RELATORIOS = Path("relatorios")
ARQUIVO_MEMORIA = Path("memoria_rua.json")
ARQUIVO_ALERTAS = Path("historico_alertas_ia.csv")
ARQUIVO_INSIGHTS = Path("historico_insights.csv")

COLUNAS_INSIGHTS = [
    "Data_Geracao", "Hora_Geracao", "Periodo", "Inicio_Periodo", "Fim_Periodo",
    "Tipo", "Nome", "Valor", "Descricao", "Nivel", "Modelo", "Arquivo_Relatorio",
    "Cliente_Documento",
]
COLUNAS_ALERTAS = [
    "Data_Geracao", "Hora_Geracao", "Data_Evento", "Hora_Evento", "Origem",
    "Tipo", "ID", "Nome", "Motivo", "Camera", "Evento", "Passagens",
    "Nivel", "Descricao", "Foto", "Modelo", "Arquivo_Relatorio",
    "Cliente_Documento",
]

SISTEMA = """Você é o analista do videomonitoramento. Responda em português do Brasil.
Use somente os números e eventos do JSON recebido. Não invente contagem, placa, face ou horário.
ID de rastreio do YOLO não é identidade de pessoa. Face_ID e Placa é que identificam.
Compare com a memória anterior quando ela existir e diga o que mudou na rua.
Relacione ocorrencias_informadas aos eventos, faces e placas do próprio cliente quando o nome, a placa ou a situação coincidirem.
ocorrencias_cidadao são lançamentos do aplicativo móvel. Use data, hora, natureza, descrição, endereço e o indicador emergente. Não invente lançamento ausente dessa lista.
fenomenos traz só contagens, sem nome, placa ou endereço de terceiros. Use essas contagens apenas para situar se o tipo de relato também aparece no conjunto.
Devolva apenas um JSON com as chaves:
resumo (string),
taxas (lista de {nome, valor, leitura}),
insights (lista de strings),
conclusoes (lista de strings),
alertas (lista de {nivel, titulo, detalhe} com nivel info, atencao ou critico),
aprendizado (uma frase curta sobre o padrão observado, para guardar),
assessoramento (um único parágrafo, em prosa, dirigido ao cliente. No mesmo parágrafo, escreva o resumo dissertativo do que os dados mostram, a conclusão de risco do período e o assessoramento de segurança, com orientação prática. Sem lista, sem título e sem inventar evento ausente do JSON.),
relatorio_markdown (texto em markdown, com títulos, sem cerca de código e sem repetir o parágrafo de assessoramento).
"""


def carregar_memoria() -> dict:
    if not ARQUIVO_MEMORIA.exists():
        return {"aprendizados": [], "linhas_base": {}, "cursores": {}, "alertas_vistos": []}
    try:
        dados = json.loads(ARQUIVO_MEMORIA.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"aprendizados": [], "linhas_base": {}, "cursores": {}, "alertas_vistos": []}
    dados.setdefault("aprendizados", [])
    dados.setdefault("linhas_base", {})
    dados.setdefault("cursores", {})
    dados.setdefault("alertas_vistos", [])
    return dados


def salvar_memoria(memoria: dict):
    memoria["aprendizados"] = memoria.get("aprendizados", [])[-40:]
    memoria["alertas_vistos"] = memoria.get("alertas_vistos", [])[-500:]
    ARQUIVO_MEMORIA.write_text(
        json.dumps(memoria, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def chave_alerta(alerta: dict) -> str:
    return "|".join([
        alerta.get("tipo", ""),
        alerta.get("id", ""),
        alerta.get("camera", ""),
        alerta.get("data", ""),
        alerta.get("hora", ""),
    ])


def _garantir_cabecalho(caminho: Path, colunas: list[str]):
    if caminho.exists():
        return
    with caminho.open("w", newline="", encoding="utf-8-sig") as arquivo:
        csv.DictWriter(arquivo, fieldnames=colunas, delimiter=";").writeheader()


def _anexar_csv(caminho: Path, colunas: list[str], linhas: list[dict]):
    if not linhas:
        _garantir_cabecalho(caminho, colunas)
        return
    if caminho.exists():
        with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
            cabecalho = next(csv.reader(arquivo, delimiter=";"), [])
        if cabecalho and cabecalho != colunas:
            with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
                existentes = list(csv.DictReader(arquivo, delimiter=";"))
            with caminho.open("w", encoding="utf-8-sig", newline="") as arquivo:
                escritor = csv.DictWriter(
                    arquivo, fieldnames=colunas, delimiter=";", extrasaction="ignore"
                )
                escritor.writeheader()
                escritor.writerows(existentes)
    novo = not caminho.exists()
    with caminho.open("a", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.DictWriter(
            arquivo, fieldnames=colunas, delimiter=";", extrasaction="ignore"
        )
        if novo:
            escritor.writeheader()
        escritor.writerows(linhas)


def _agora_partes():
    agora = datetime.now()
    return agora.strftime("%Y-%m-%d"), agora.strftime("%H:%M:%S")


def gravar_alertas(alertas: list[dict], modelo="", arquivo_relatorio="", documento=""):
    data_geracao, hora_geracao = _agora_partes()
    linhas = []
    for alerta in alertas:
        linhas.append({
            "Data_Geracao": data_geracao,
            "Hora_Geracao": hora_geracao,
            "Data_Evento": alerta.get("data", ""),
            "Hora_Evento": alerta.get("hora", ""),
            "Origem": alerta.get("origem") or "Interesse",
            "Tipo": alerta.get("tipo", ""),
            "ID": alerta.get("id", ""),
            "Nome": alerta.get("nome", ""),
            "Motivo": alerta.get("motivo", ""),
            "Camera": alerta.get("camera", ""),
            "Evento": alerta.get("evento", ""),
            "Passagens": alerta.get("passagens", ""),
            "Nivel": alerta.get("nivel") or "critico",
            "Descricao": alerta.get("descricao") or alerta.get("motivo") or "",
            "Foto": alerta.get("foto", ""),
            "Modelo": modelo,
            "Arquivo_Relatorio": arquivo_relatorio,
            "Cliente_Documento": documento,
        })
    _anexar_csv(ARQUIVO_ALERTAS, COLUNAS_ALERTAS, linhas)


def _filtrar_csv(caminho: Path, colunas: list[str], manter):
    if not caminho.exists():
        return
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo, delimiter=";")
        linhas = [linha for linha in leitor if manter(linha)]
    with caminho.open("w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas, delimiter=";", extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)


def gravar_insights(linhas: list[dict]):
    _anexar_csv(ARQUIVO_INSIGHTS, COLUNAS_INSIGHTS, linhas)


ARQUIVO_HISTORICO = PASTA_RELATORIOS / "historico_relatorios.json"


def _ler_historico() -> list:
    if not ARQUIVO_HISTORICO.exists():
        return []
    try:
        bruto = json.loads(ARQUIVO_HISTORICO.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(bruto, list):
        return bruto
    if isinstance(bruto, dict):
        return list(bruto.get("registros") or [])
    return []


def _chave_relatorio(registro: dict):
    return (
        registro.get("cliente_id") or "",
        registro.get("periodo") or "",
        registro.get("inicio") or "",
        registro.get("fim") or "",
    )


def _salvar_historico(registros: list):
    PASTA_RELATORIOS.mkdir(parents=True, exist_ok=True)
    ARQUIVO_HISTORICO.write_text(
        json.dumps(registros, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _montar_registro(nome_periodo, inicio, fim, pacote, alertas, leitura, caminho_relatorio, cliente):
    return {
        "cliente_id": (cliente or {}).get("id") or "",
        "documento": (cliente or {}).get("documento") or "",
        "nome_cliente": (cliente or {}).get("nome") or "",
        "periodo": nome_periodo,
        "inicio": inicio if isinstance(inicio, str) else inicio.isoformat(),
        "fim": fim if isinstance(fim, str) else fim.isoformat(),
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "arquivo_markdown": caminho_relatorio,
        "resumo": (leitura or {}).get("resumo") or "",
        "assessoramento": (leitura or {}).get("assessoramento") or "",
        "alertas": alertas or [],
        "leitura": leitura or {},
        "pacote": pacote or {},
    }


def incorporar_relatorios_antigos():
    """Traz os JSON diários já gravados para o arquivo único de histórico."""
    from cadastro import cliente_ativo, garantir_cliente_local

    garantir_cliente_local()
    cliente = cliente_ativo()
    registros = _ler_historico()
    chaves = {_chave_relatorio(item) for item in registros}
    if not PASTA_RELATORIOS.exists():
        return
    for caminho in sorted(PASTA_RELATORIOS.glob("*.json")):
        if caminho.name == ARQUIVO_HISTORICO.name:
            continue
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(dados, dict):
            continue
        pacote = dados.get("pacote") or {}
        periodo = pacote.get("periodo") or {}
        inicio = periodo.get("inicio") or ""
        fim = periodo.get("fim") or inicio
        nome = "dia"
        if caminho.name.startswith("semanal-"):
            nome = "semana"
        elif caminho.name.startswith("mensal-"):
            nome = "mes"
        registro = _montar_registro(
            nome, inicio, fim, pacote, dados.get("alertas") or [],
            dados.get("leitura") or {}, str(caminho.with_suffix(".md")).replace("\\", "/"),
            cliente,
        )
        if not registro["inicio"] or _chave_relatorio(registro) in chaves:
            continue
        registros.append(registro)
        chaves.add(_chave_relatorio(registro))
    _salvar_historico(registros)


def _acrescentar_historico(nome_periodo, inicio, fim, pacote, alertas, leitura, caminho_relatorio):
    from cadastro import cliente_ativo, garantir_cliente_local

    garantir_cliente_local()
    incorporar_relatorios_antigos()
    cliente = cliente_ativo()
    registro = _montar_registro(
        nome_periodo, inicio, fim, pacote, alertas, leitura, caminho_relatorio, cliente
    )
    registros = [
        item for item in _ler_historico()
        if _chave_relatorio(item) != _chave_relatorio(registro)
    ]
    registros.append(registro)
    _salvar_historico(registros)


def _nome_arquivo(nome_periodo: str, inicio: date, fim: date) -> str:
    if nome_periodo == "dia":
        return f"diario-{inicio.isoformat()}"
    if nome_periodo == "semana":
        return f"semanal-{fim.strftime('%G-W%V')}"
    return f"mensal-{fim.strftime('%Y-%m')}"


def _assessoramento_local(pacote: dict, alertas: list[dict]) -> str:
    volume = pacote["volume"]
    ocorrencias = pacote["ocorrencias"]
    riscos = ocorrencias["por_risco"]
    categorias = ", ".join(
        f"{quantidade} de {nome}" for nome, quantidade in volume["por_categoria"].items()
    ) or "sem detalhamento por categoria"
    risco_txt = ", ".join(
        f"{quantidade} {nome}" for nome, quantidade in riscos.items()
    ) or "sem classificação de risco"
    atencao = sum(
        quantidade for nome, quantidade in riscos.items()
        if nome in ("Atencao", "Prioritario", "Critico")
    )
    if atencao or alertas:
        conclusao = (
            f"A conclusão de risco do período é de atenção, com {atencao} ocorrência(s) "
            f"acima do nível informativo e {len(alertas)} alerta(s) de interesse."
        )
        orientacao = (
            "Recomenda-se ao cliente revisar as imagens desses horários, confirmar quem circulou na área "
            "e reforçar a observação nos pontos em que o risco se repetir."
        )
    else:
        conclusao = (
            "A conclusão de risco do período é estável, sem ocorrência prioritária nem alerta de interesse."
        )
        orientacao = (
            "Recomenda-se ao cliente manter a rotina de monitoramento e usar este dia como referência "
            "para perceber mudança de movimento nos dias seguintes."
        )
    return (
        f"No período de {pacote['periodo']['inicio']} a {pacote['periodo']['fim']}, "
        f"o monitoramento registrou {volume['deteccoes']} detecções ({categorias}), "
        f"{ocorrencias['total']} ocorrências ({risco_txt}), "
        f"{pacote['faces']['identidades']} identidade(s) de face e "
        f"{pacote['veiculos']['placas']} placa(s). "
        f"{conclusao} {orientacao}"
    )


def _markdown_local(pacote: dict, alertas: list[dict]) -> str:
    volume = pacote["volume"]
    ocorrencias = pacote["ocorrencias"]
    linhas = [
        f"# Período {pacote['periodo']['inicio']} a {pacote['periodo']['fim']}",
        "",
        f"- Detecções: {volume['deteccoes']}",
        f"- Por categoria: {volume['por_categoria']}",
        f"- Ocorrências: {ocorrencias['total']} | riscos: {ocorrencias['por_risco']}",
        f"- Faces: {pacote['faces']['identidades']} identidades em {pacote['faces']['registros']} registros",
        f"- Placas: {pacote['veiculos']['placas']} em {pacote['veiculos']['registros']} registros",
        f"- Ocorrências informadas pelo cliente: {len(pacote.get('ocorrencias_informadas') or [])}",
        f"- Ocorrências do aplicativo móvel: {len(pacote.get('ocorrencias_cidadao') or [])}",
        "",
    ]
    for informe in pacote.get("ocorrencias_informadas") or []:
        ligados = ", ".join(
            item.get("nome") or item.get("placa") or ""
            for item in (informe.get("extraido") or {}).get("pessoas", [])
            + (informe.get("extraido") or {}).get("veiculos", [])
        )
        linhas.append(
            f"- Informe {informe.get('data')} {informe.get('hora')} | {informe.get('natureza')}: "
            f"{informe.get('descricao')}"
            + (f" Vínculos: {ligados}." if ligados else "")
        )
    if pacote.get("ocorrencias_informadas"):
        linhas.append("")
    for cidadao in pacote.get("ocorrencias_cidadao") or []:
        marca = "emergente" if cidadao.get("emergente") else "registro"
        linhas.append(
            f"- Aplicativo {cidadao.get('data')} {cidadao.get('hora')} | {marca} | "
            f"{cidadao.get('natureza') or cidadao.get('titulo')}: {cidadao.get('descricao')} "
            f"{cidadao.get('endereco') or ''}"
        )
    if pacote.get("ocorrencias_cidadao"):
        linhas.append("")
    if alertas:
        linhas.append("## Alertas de interesse")
        for alerta in alertas:
            linhas.append(
                f"- {alerta['tipo']} {alerta['nome']} ({alerta['id']}) "
                f"em {alerta['camera']} às {alerta['data']} {alerta['hora']}. "
                f"{alerta.get('motivo', '')}"
            )
        linhas.append("")
    return "\n".join(linhas)


class Analista:
    def __init__(self, pasta=".", sessao: SessaoGPT | None = None):
        self.fonte = FonteCsv(pasta)
        self.sessao = sessao or SessaoGPT()
        self.pasta = Path(pasta)

    def analisar(self, nome_periodo: str, referencia: date | None = None, gravar=True) -> dict:
        inicio, fim = periodo(nome_periodo, referencia)
        pacote = self.fonte.resumo(inicio, fim)
        from cadastro import interesse_ativo

        interesse = interesse_ativo()
        faces = [
            linha for linha in self.fonte.linhas("faces")
            if inicio.isoformat() <= (linha.get("Data") or "")[:10] <= fim.isoformat()
        ]
        placas = [
            linha for linha in self.fonte.linhas("placas")
            if inicio.isoformat() <= (linha.get("Data") or "")[:10] <= fim.isoformat()
        ]
        alertas = cruzar_interesse(faces, placas, interesse)
        memoria = carregar_memoria()
        from ocorrencias import para_relatorio, resumo_fenomenos

        pacote["ocorrencias_informadas"] = para_relatorio(inicio.isoformat(), fim.isoformat())
        pacote["ocorrencias_cidadao"] = []
        try:
            from dataverse import para_relatorio as ocorrencias_do_aplicativo

            pacote["ocorrencias_cidadao"] = ocorrencias_do_aplicativo(
                inicio.isoformat(), fim.isoformat()
            )
        except Exception as exc:
            print(f"Ocorrências do aplicativo não entraram no relatório: {exc}")
        pacote["fenomenos"] = resumo_fenomenos()
        pacote["alertas_interesse"] = alertas
        pacote["memoria_anterior"] = {
            "aprendizados": memoria.get("aprendizados", [])[-8:],
            "linhas_base": memoria.get("linhas_base", {}),
        }

        leitura = None
        if self.sessao.disponivel:
            texto = self.sessao.perguntar(SISTEMA, json.dumps(pacote, ensure_ascii=False))
            try:
                leitura = extrair_json(texto)
            except json.JSONDecodeError:
                leitura = {
                    "resumo": texto,
                    "taxas": [],
                    "insights": [],
                    "conclusoes": [],
                    "alertas": [],
                    "aprendizado": "",
                    "assessoramento": "",
                    "relatorio_markdown": texto,
                }
            aprendizado = (leitura.get("aprendizado") or "").strip()
            if aprendizado:
                memoria["aprendizados"].append({
                    "quando": datetime.now().isoformat(timespec="seconds"),
                    "periodo": pacote["periodo"],
                    "texto": aprendizado,
                })
        else:
            leitura = {
                "resumo": "Análise numérica local. O GPT não foi chamado porque OPENAI_API_KEY não está definida.",
                "taxas": [],
                "insights": [],
                "conclusoes": [],
                "alertas": [],
                "aprendizado": "",
                "assessoramento": "",
                "relatorio_markdown": "",
            }
        if not (leitura.get("assessoramento") or "").strip():
            leitura["assessoramento"] = _assessoramento_local(pacote, alertas)

        memoria["linhas_base"][fim.isoformat()] = {
            "deteccoes": pacote["volume"]["deteccoes"],
            "ocorrencias": pacote["ocorrencias"]["total"],
            "riscos": pacote["ocorrencias"]["por_risco"],
            "faces": pacote["faces"]["identidades"],
            "placas": pacote["veiculos"]["placas"],
        }
        if gravar:
            salvar_memoria(memoria)
            self._gravar(nome_periodo, inicio, fim, pacote, alertas, leitura)
        return {"pacote": pacote, "alertas": alertas, "leitura": leitura}

    def narrar_alerta(self, alerta: dict) -> str:
        if not self.sessao.disponivel:
            return ""
        pedido = (
            "Redija um alerta curto, em uma frase, para a equipe de monitoramento. "
            "Não invente dados além deste JSON:\n"
            + json.dumps(alerta, ensure_ascii=False)
        )
        return self.sessao.perguntar(
            "Você redige alertas operacionais curtos em português. Responda só a frase.",
            pedido,
            json_mode=False,
        ).strip()

    def _gravar(self, nome_periodo, inicio, fim, pacote, alertas, leitura):
        PASTA_RELATORIOS.mkdir(parents=True, exist_ok=True)
        base = PASTA_RELATORIOS / _nome_arquivo(nome_periodo, inicio, fim)
        markdown = _markdown_local(pacote, alertas)
        assessoramento = (leitura.get("assessoramento") or "").strip()
        if assessoramento:
            markdown += "\n## Assessoramento de segurança\n\n" + assessoramento + "\n"
        texto_modelo = (leitura.get("relatorio_markdown") or "").strip()
        if texto_modelo:
            markdown += "\n## Leitura do GPT\n\n" + texto_modelo + "\n"
        elif leitura.get("resumo"):
            markdown += "\n## Leitura\n\n" + leitura["resumo"] + "\n"
        base.with_suffix(".md").write_text(markdown, encoding="utf-8")
        caminho_relatorio = str(base.with_suffix(".md")).replace("\\", "/")
        _acrescentar_historico(nome_periodo, inicio, fim, pacote, alertas, leitura, caminho_relatorio)
        self._exportar_power_bi(
            nome_periodo, inicio, fim, pacote, alertas, leitura, caminho_relatorio
        )

    def _exportar_power_bi(self, nome_periodo, inicio, fim, pacote, alertas, leitura, caminho_relatorio):
        data_geracao, hora_geracao = _agora_partes()
        from cadastro import cliente_ativo

        modelo = self.sessao.modelo if self.sessao.disponivel else ""
        documento = (cliente_ativo() or {}).get("documento") or ""
        base = {
            "Data_Geracao": data_geracao,
            "Hora_Geracao": hora_geracao,
            "Periodo": nome_periodo,
            "Inicio_Periodo": inicio.isoformat(),
            "Fim_Periodo": fim.isoformat(),
            "Modelo": modelo,
            "Arquivo_Relatorio": caminho_relatorio,
            "Cliente_Documento": documento,
            "Nivel": "",
            "Valor": "",
            "Nome": "",
        }
        linhas = []

        def adicionar(tipo, nome="", valor="", descricao="", nivel=""):
            linhas.append({
                **base,
                "Tipo": tipo,
                "Nome": nome,
                "Valor": valor,
                "Descricao": descricao,
                "Nivel": nivel,
            })

        volume = pacote["volume"]
        adicionar("Volume", "Deteccoes", volume["deteccoes"], "Total de detecções no período.")
        for categoria, quantidade in volume["por_categoria"].items():
            adicionar("Volume", categoria, quantidade, f"Detecções de {categoria}.")
        for risco, quantidade in pacote["ocorrencias"]["por_risco"].items():
            adicionar("Risco", risco, quantidade, f"Ocorrências classificadas como {risco}.")
        adicionar(
            "Volume", "Faces", pacote["faces"]["identidades"],
            f"{pacote['faces']['registros']} registros de face.",
        )
        adicionar(
            "Volume", "Placas", pacote["veiculos"]["placas"],
            f"{pacote['veiculos']['registros']} registros de placa.",
        )
        for face in pacote["faces"]["mais_recorrentes"]:
            adicionar(
                "Face", face["face_id"], face["total_passagens"],
                f"Câmeras: {', '.join(face['cameras'])}. Última vez: {face['ultimo']}.",
            )
        for veiculo in pacote["veiculos"]["mais_recorrentes"]:
            adicionar(
                "Placa", veiculo["placa"], veiculo["total_passagens"],
                f"{veiculo['tipo']} em {', '.join(veiculo['cameras'])}. Última vez: {veiculo['ultimo']}.",
            )
        for cidadao in pacote.get("ocorrencias_cidadao") or []:
            adicionar(
                "Aplicativo",
                cidadao.get("natureza") or cidadao.get("titulo") or "",
                "emergente" if cidadao.get("emergente") else "registro",
                (
                    f"{cidadao.get('data', '')} {cidadao.get('hora', '')}. "
                    f"{cidadao.get('endereco', '')} {cidadao.get('descricao', '')}"
                ).strip(),
            )
        for informe in pacote.get("ocorrencias_informadas") or []:
            adicionar(
                "Informe",
                informe.get("natureza") or "",
                informe.get("placa") or informe.get("pessoa") or "",
                (
                    f"{informe.get('data', '')} {informe.get('hora', '')}. "
                    f"{informe.get('endereco', '')} {informe.get('descricao', '')}"
                ).strip(),
            )
        for ocorrencia in pacote["ocorrencias"]["prioritarias"]:
            adicionar(
                "Ocorrencia", ocorrencia["classe"], ocorrencia["nivel"],
                (
                    f"{ocorrencia['camera']} {ocorrencia['data']} {ocorrencia['hora']}. "
                    f"{ocorrencia['detalhe']}"
                ).strip(),
                ocorrencia["risco"],
            )

        adicionar("Assessoramento", "Cliente", "", leitura.get("assessoramento") or "")
        adicionar("Resumo", "Resumo", "", leitura.get("resumo") or "")
        for taxa in leitura.get("taxas") or []:
            if isinstance(taxa, dict):
                adicionar("Taxa", taxa.get("nome") or "", taxa.get("valor") or "", taxa.get("leitura") or "")
            else:
                adicionar("Taxa", "", "", str(taxa))
        for insight in leitura.get("insights") or []:
            adicionar("Insight", "", "", str(insight))
        for conclusao in leitura.get("conclusoes") or []:
            adicionar("Conclusao", "", "", str(conclusao))
        if leitura.get("aprendizado"):
            adicionar("Aprendizado", "", "", leitura["aprendizado"])
        if leitura.get("relatorio_markdown"):
            adicionar("Relatorio", nome_periodo, "", leitura["relatorio_markdown"])

        for alerta in alertas:
            adicionar(
                "Alerta",
                alerta.get("nome") or alerta.get("id") or "",
                alerta.get("id") or "",
                (
                    f"{alerta.get('camera', '')} {alerta.get('data', '')} {alerta.get('hora', '')}. "
                    f"{alerta.get('motivo', '')} {alerta.get('descricao', '')}"
                ).strip(),
                alerta.get("nivel") or "critico",
            )
        _filtrar_csv(
            ARQUIVO_INSIGHTS,
            COLUNAS_INSIGHTS,
            lambda linha: not (
                linha.get("Periodo") == nome_periodo
                and linha.get("Inicio_Periodo") == inicio.isoformat()
                and linha.get("Fim_Periodo") == fim.isoformat()
            ),
        )
        gravar_insights(linhas)

        alertas_modelo = []
        for alerta in leitura.get("alertas") or []:
            if not isinstance(alerta, dict):
                continue
            alertas_modelo.append({
                "origem": "GPT",
                "tipo": "analise",
                "id": "",
                "nome": alerta.get("titulo") or "",
                "motivo": "",
                "data": fim.isoformat(),
                "hora": hora_geracao,
                "camera": "",
                "evento": nome_periodo,
                "passagens": "",
                "nivel": alerta.get("nivel") or "info",
                "descricao": alerta.get("detalhe") or "",
                "foto": "",
            })
        _filtrar_csv(
            ARQUIVO_ALERTAS,
            COLUNAS_ALERTAS,
            lambda linha: not (
                linha.get("Origem") == "GPT" and linha.get("Arquivo_Relatorio") == caminho_relatorio
            ),
        )
        gravar_alertas(alertas_modelo, modelo, caminho_relatorio, documento)
        _garantir_cabecalho(ARQUIVO_ALERTAS, COLUNAS_ALERTAS)
