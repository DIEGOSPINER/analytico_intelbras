"""Vigia os CSVs: um relatório por dia, alertas quando há ação e resumo no WhatsApp."""

from __future__ import annotations

import os
import threading
import time
from collections import Counter
from datetime import date, datetime, timedelta

from agente.analista import Analista, carregar_memoria, chave_alerta, gravar_alertas, salvar_memoria
from agente.envio import email_configurado, enviar_email, enviar_whatsapp, whatsapp_configurado
from agente.fontes import FonteCsv, carregar_interesse, cruzar_interesse
from agente.modelo import SessaoGPT, carregar_env


def _hora_relatorio() -> tuple[int, int]:
    bruto = os.getenv("RELATORIO_HORA", "21").strip()
    if ":" in bruto:
        hora, minuto = bruto.split(":", 1)
        return int(hora), int(minuto)
    return int(bruto), 0


def _instante(linha: dict):
    bruto = f"{linha.get('Data') or ''} {linha.get('Hora') or ''}"[:19]
    try:
        return datetime.strptime(bruto, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


class Vigia:
    def __init__(self, pasta="."):
        carregar_env()
        self.pasta = pasta
        self.fonte = FonteCsv(pasta)
        self.analista = Analista(pasta, SessaoGPT())
        self._parar = threading.Event()
        self._thread = None
        self._avisou = False
        self._ultima_tentativa_relatorio = 0.0
        self._ultima_tentativa_email = 0.0
        self._ultima_tentativa_whatsapp = 0.0

    def iniciar(self):
        if os.getenv("AGENTE_ATIVO", "1").strip().lower() in ("0", "false", "nao", "não"):
            print("Agente de análise desligado (AGENTE_ATIVO=0).")
            return
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self.loop, name="agente-gpt", daemon=True)
        self._thread.start()
        hora, minuto = _hora_relatorio()
        print(
            "Agente de análise em execução. "
            f"Relatório diário às {hora:02d}:{minuto:02d} por e-mail. "
            "Alertas de interesse e de atenção saem no mesmo e-mail."
        )

    def parar(self):
        self._parar.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def loop(self):
        self._marcar_cursores_iniciais()
        while not self._parar.is_set():
            try:
                self.varrer_novidades()
                self._enviar_resumo_whatsapp()
                self._relatorio_diario()
            except Exception as exc:
                print(f"Agente: {exc}")
            self._parar.wait(20)

    def _marcar_cursores_iniciais(self):
        memoria = carregar_memoria()
        cursores = memoria.setdefault("cursores", {})
        for chave, arquivo in (
            ("faces", "historico_faces.csv"),
            ("placas", "historico_placas.csv"),
            ("ocorrencias", "historico_ocorrencias.csv"),
        ):
            if arquivo not in cursores:
                cursores[arquivo] = len(self.fonte.linhas(chave))
        if not memoria.get("ultimo_whatsapp"):
            memoria["ultimo_whatsapp"] = datetime.now().isoformat(timespec="seconds")
        salvar_memoria(memoria)
        if self._avisou:
            return
        self._avisou = True
        if not self.analista.sessao.disponivel:
            print("Agente sem OPENAI_API_KEY. O relatório do dia sai só com os números locais.")
        if not email_configurado():
            print("E-mail diário espera SMTP_SENHA no .env (senha de app do Gmail).")

    def _relatorio_diario(self):
        agora = datetime.now()
        hora, minuto = _hora_relatorio()
        marco = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
        if agora < marco:
            return
        hoje = date.today().isoformat()
        memoria = carregar_memoria()
        caminho = f"relatorios/diario-{hoje}.md"
        if memoria.get("ultimo_relatorio") != hoje:
            if time.time() - self._ultima_tentativa_relatorio < 15 * 60:
                return
            self._ultima_tentativa_relatorio = time.time()
            self.analista.analisar("dia", date.today())
            memoria = carregar_memoria()
            memoria["ultimo_relatorio"] = hoje
            salvar_memoria(memoria)
            print(f"Relatório diário gravado em relatorios/ ({self.analista.sessao.modelo or 'local'}).")
        if memoria.get("ultimo_email") == hoje or not email_configurado() or not os.path.exists(caminho):
            return
        if time.time() - self._ultima_tentativa_email < 15 * 60:
            return
        self._ultima_tentativa_email = time.time()
        with open(caminho, encoding="utf-8") as arquivo:
            texto = arquivo.read()
        if enviar_email(f"Relatório diário {hoje}", texto, caminho):
            memoria = carregar_memoria()
            memoria["ultimo_email"] = hoje
            salvar_memoria(memoria)

    def _enviar_resumo_whatsapp(self):
        if not whatsapp_configurado():
            return
        memoria = carregar_memoria()
        horas = max(1, int(os.getenv("WHATSAPP_INTERVALO_HORAS", "6")))
        try:
            ultimo = datetime.fromisoformat(memoria.get("ultimo_whatsapp"))
        except (TypeError, ValueError):
            ultimo = datetime.now() - timedelta(hours=horas)
        if datetime.now() - ultimo < timedelta(hours=horas):
            return
        if time.time() - self._ultima_tentativa_whatsapp < 15 * 60:
            return
        self._ultima_tentativa_whatsapp = time.time()
        if enviar_whatsapp(self._texto_resumo(ultimo)):
            memoria = carregar_memoria()
            memoria["ultimo_whatsapp"] = datetime.now().isoformat(timespec="seconds")
            salvar_memoria(memoria)

    def _texto_resumo(self, desde: datetime) -> str:
        def no_intervalo(chave):
            return [
                linha for linha in self.fonte.linhas(chave)
                if (instante := _instante(linha)) and instante >= desde
            ]

        analitico = no_intervalo("analitico")
        ocorrencias = no_intervalo("ocorrencias")
        categorias = Counter((linha.get("Categoria") or "Outro") for linha in analitico)
        riscos = Counter((linha.get("Risco") or "Sem risco") for linha in ocorrencias)
        partes = [
            f"Analítico {datetime.now().strftime('%d/%m %H:%M')}",
            f"Desde {desde.strftime('%d/%m %H:%M')}",
            f"Detecções: {len(analitico)}",
        ]
        if categorias:
            partes.append(", ".join(f"{nome} {quantidade}" for nome, quantidade in categorias.most_common(4)))
        partes.append(f"Ocorrências: {len(ocorrencias)}")
        if riscos:
            partes.append(", ".join(f"{nome} {quantidade}" for nome, quantidade in riscos.most_common()))
        atencao = sum(quantidade for nome, quantidade in riscos.items() if nome in ("Atencao", "Prioritario"))
        partes.append(f"Situações de atenção ou prioridade: {atencao}")
        return "\n".join(partes)

    def varrer_novidades(self):
        memoria = carregar_memoria()
        cursores = memoria.setdefault("cursores", {})
        vistos = set(memoria.get("alertas_vistos") or [])
        interesse = carregar_interesse()
        novos_alertas = []
        agora = datetime.now()
        cooldowns = memoria.setdefault("cooldowns", {})

        for chave, arquivo in (("faces", "historico_faces.csv"), ("placas", "historico_placas.csv")):
            linhas = self.fonte.linhas(chave)
            inicio = int(cursores.get(arquivo, len(linhas)))
            if inicio > len(linhas):
                inicio = 0
            trecho = linhas[inicio:]
            cursores[arquivo] = len(linhas)
            if chave == "faces":
                encontrados = cruzar_interesse(trecho, [], interesse)
            else:
                encontrados = cruzar_interesse([], trecho, interesse)
            for alerta in encontrados:
                codigo = chave_alerta(alerta)
                if codigo in vistos:
                    continue
                vistos.add(codigo)
                novos_alertas.append(alerta)

        arquivo = "historico_ocorrencias.csv"
        linhas = self.fonte.linhas("ocorrencias")
        inicio = int(cursores.get(arquivo, len(linhas)))
        if inicio > len(linhas):
            inicio = 0
        for linha in linhas[inicio:]:
            try:
                nivel = int(float(linha.get("Nivel_Risco") or 0))
            except ValueError:
                nivel = 0
            if nivel < 2:
                continue
            alerta = {
                "tipo": "ocorrencia",
                "id": linha.get("ID") or linha.get("Classe") or "",
                "nome": linha.get("Classe") or "",
                "motivo": linha.get("Risco") or "",
                "camera": linha.get("Camera") or "",
                "data": linha.get("Data") or "",
                "hora": linha.get("Hora") or "",
                "evento": linha.get("Categoria") or "",
                "passagens": "",
                "foto": "",
                "origem": "Ocorrencia",
                "nivel": "critico" if nivel >= 3 else "atencao",
                "descricao": (linha.get("Detalhe") or linha.get("Risco") or "").strip(),
            }
            codigo = chave_alerta(alerta)
            if codigo in vistos:
                continue
            repeticao = f"{alerta['nome']}|{alerta['camera']}"
            try:
                liberado = datetime.fromisoformat(cooldowns.get(repeticao, ""))
            except ValueError:
                liberado = datetime.min
            if agora < liberado:
                vistos.add(codigo)
                continue
            vistos.add(codigo)
            cooldowns[repeticao] = (agora + timedelta(minutes=30)).isoformat(timespec="seconds")
            novos_alertas.append(alerta)
        cursores[arquivo] = len(linhas)

        if novos_alertas:
            for alerta in novos_alertas:
                if alerta.get("origem") == "Ocorrencia":
                    continue
                frase = ""
                try:
                    frase = self.analista.narrar_alerta(alerta)
                except Exception as exc:
                    print(f"Agente não narrou o alerta: {exc}")
                alerta["origem"] = "Interesse"
                alerta["nivel"] = "critico"
                alerta["descricao"] = frase or alerta.get("motivo") or ""
            for alerta in novos_alertas:
                print(
                    f"ALERTA {alerta['tipo']} | {alerta['nome']} ({alerta['id']}) | "
                    f"{alerta['camera']} {alerta['data']} {alerta['hora']}"
                )
            gravar_alertas(
                novos_alertas,
                self.analista.sessao.modelo if self.analista.sessao.disponivel else "",
            )
            self._avisar(novos_alertas)
        memoria["alertas_vistos"] = list(vistos)[-500:]
        salvar_memoria(memoria)
        return novos_alertas

    def _avisar(self, alertas: list[dict]):
        linhas = ["Alerta do analítico"]
        for alerta in alertas:
            linhas.append(
                f"{alerta.get('nivel', '')}: {alerta.get('nome', '')} ({alerta.get('id', '')}) | "
                f"{alerta.get('camera', '')} {alerta.get('data', '')} {alerta.get('hora', '')}"
            )
            if alerta.get("descricao"):
                linhas.append(alerta["descricao"])
        texto = "\n".join(linhas)
        assunto = f"Alerta analítico: {alertas[0].get('nome') or alertas[0].get('tipo')}"
        enviar_email(assunto, texto)
        if whatsapp_configurado():
            enviar_whatsapp(texto)
