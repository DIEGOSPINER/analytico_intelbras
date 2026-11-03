"""Ocorrências lançadas no Power Apps, lidas na tabela do Dataverse.

A senha fica no .env. Este módulo só pede o token e devolve os campos de texto.
Quando a fonte for trocada pelo aplicativo definitivo ou pelo WhatsApp, o
relatório continua recebendo a mesma lista normalizada.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from agente.modelo import carregar_env

# Aplicativo público de exemplo do Dataverse, documentado pela Microsoft
# para entrada com usuário e senha sem um cadastro próprio.
APP_ID = "51f81489-12ee-4a9e-aaae-a2591f45987d"
SINAIS_EMERGENCIA = (
    "emerg",
    "urgent",
    "socorro",
)
FUSO = ZoneInfo("America/Bahia")


def _erro_http(exc: urllib.error.HTTPError) -> str:
    try:
        corpo = exc.read().decode("utf-8", errors="replace")
        dados = json.loads(corpo)
    except Exception:
        return f"HTTP {exc.code}"
    if isinstance(dados, dict):
        detalhe = dados.get("error_description") or dados.get("error") or dados
        if isinstance(detalhe, dict):
            detalhe = detalhe.get("message") or detalhe
        return f"HTTP {exc.code}: {str(detalhe)[:240]}"
    return f"HTTP {exc.code}"


class ClienteDataverse:
    def __init__(self):
        carregar_env()
        self.url = os.getenv("DATAVERSE_URL", "").strip().rstrip("/")
        self.tabela = os.getenv("DATAVERSE_TABELA", "cr3d0_ocorrencia").strip()
        self.usuario = os.getenv("DATAVERSE_USUARIO", "").strip()
        self.senha = os.getenv("DATAVERSE_SENHA", "")
        self._token = ""
        self._expira = 0.0
        self._conjunto = ""
        self._id = ""
        self._nome = ""

    def configurado(self) -> bool:
        return bool(self.url and self.usuario and self.senha and self.tabela)

    def _token_acesso(self) -> str:
        if self._token and time_restante(self._expira):
            return self._token
        corpo = urllib.parse.urlencode({
            "grant_type": "password",
            "client_id": APP_ID,
            "username": self.usuario,
            "password": self.senha,
            "resource": self.url,
        }).encode()
        pedido = urllib.request.Request(
            "https://login.microsoftonline.com/organizations/oauth2/token",
            data=corpo,
            method="POST",
        )
        try:
            with urllib.request.urlopen(pedido, timeout=30) as resposta:
                dados = json.loads(resposta.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Dataverse recusou a entrada. {_erro_http(exc)}") from exc
        self._token = str(dados.get("access_token") or "")
        if not self._token:
            raise RuntimeError("Dataverse não devolveu um token de acesso.")
        self._expira = datetime.now(timezone.utc).timestamp() + int(dados.get("expires_in") or 3600)
        return self._token

    def _get(self, caminho: str) -> dict:
        pedido = urllib.request.Request(
            self.url + caminho,
            headers={
                "Authorization": f"Bearer {self._token_acesso()}",
                "Accept": "application/json",
                "OData-MaxVersion": "4.0",
                "OData-Version": "4.0",
                "Prefer": 'odata.include-annotations="OData.Community.Display.V1.FormattedValue"',
            },
        )
        try:
            with urllib.request.urlopen(pedido, timeout=40) as resposta:
                return json.loads(resposta.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Dataverse não entregou a tabela. {_erro_http(exc)}") from exc

    def _metadados(self):
        if self._conjunto:
            return
        dados = self._get(
            "/api/data/v9.2/EntityDefinitions"
            f"(LogicalName='{self.tabela}')"
            "?$select=EntitySetName,PrimaryIdAttribute,PrimaryNameAttribute"
        )
        self._conjunto = str(dados.get("EntitySetName") or "")
        self._id = str(dados.get("PrimaryIdAttribute") or "")
        self._nome = str(dados.get("PrimaryNameAttribute") or "")
        if not self._conjunto:
            raise RuntimeError(f"A tabela {self.tabela} não foi encontrada neste ambiente.")

    def listar(self, inicio: str = "", fim: str = "", desde: str = "") -> list[dict]:
        self._metadados()
        filtros = []
        if desde:
            filtros.append(f"createdon gt {desde}")
        elif inicio:
            filtros.append(f"createdon ge {inicio}T00:00:00Z")
        consulta = {
            "$orderby": "createdon asc",
            "$top": "100",
        }
        if filtros:
            consulta["$filter"] = " and ".join(filtros)
        caminho = f"/api/data/v9.2/{self._conjunto}?{urllib.parse.urlencode(consulta)}"
        registros = []
        while caminho and len(registros) < 300:
            dados = self._get(caminho)
            registros.extend(dados.get("value") or [])
            seguinte = str(dados.get("@odata.nextLink") or "")
            caminho = seguinte[len(self.url):] if seguinte.startswith(self.url) else ""
        linhas = [self._normalizar(item) for item in registros]
        if inicio or fim:
            linhas = [
                item for item in linhas
                if (not inicio or item["data"] >= inicio) and (not fim or item["data"] <= fim)
            ]
        return linhas

    def _normalizar(self, item: dict) -> dict:
        criado = str(item.get("createdon") or "")
        evento = str(item.get("cr3d0_dataehora") or criado)
        data, hora = _data_local(evento)
        resumo = str(item.get("cr3d0_descricaoresumida") or "").strip()
        detalhe = str(item.get("cr3d0_descricaodetalhada") or "").strip()
        natureza = _legivel(item, "cr3d0_natureza") or str(item.get("cr3d0_naturezaname") or "").strip()
        endereco = ", ".join(
            parte.strip()
            for parte in (
                str(item.get("cr3d0_logradouro") or ""),
                str(item.get("cr3d0_bairro") or ""),
                str(item.get("cr3d0_cidade") or ""),
            )
            if parte.strip()
        )
        descricao = detalhe or resumo
        return {
            "id": str(item.get("cr3d0_ocorrenciaid") or item.get(self._id) or ""),
            "quando": criado,
            "data": data,
            "hora": hora,
            "titulo": natureza or resumo[:80] or "Ocorrência",
            "natureza": natureza,
            "resumo": resumo[:240],
            "descricao": descricao[:800],
            "endereco": endereco,
            "latitude": item.get("cr3d0_latitude"),
            "longitude": item.get("cr3d0_longitude"),
            "emergente": _emergente_texto(" ".join((natureza, resumo, detalhe))),
            "origem": "Power Apps",
        }


def time_restante(expira: float) -> bool:
    return expira - datetime.now(timezone.utc).timestamp() > 60


def _legivel(item: dict, chave: str) -> str:
    formato = item.get(f"{chave}@OData.Community.Display.V1.FormattedValue")
    if formato not in (None, ""):
        return str(formato)
    valor = item.get(chave)
    if valor in (None, ""):
        return ""
    return str(valor)


def _data_local(iso: str) -> tuple[str, str]:
    if not iso:
        return "", ""
    try:
        instante = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso[:10], iso[11:19]
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    local = instante.astimezone(FUSO)
    return local.strftime("%Y-%m-%d"), local.strftime("%H:%M:%S")


def _emergente_texto(texto: str) -> bool:
    baixo = (texto or "").lower()
    return any(sinal in baixo for sinal in SINAIS_EMERGENCIA)


def para_relatorio(inicio: str, fim: str) -> list[dict]:
    cliente = ClienteDataverse()
    if not cliente.configurado():
        return []
    return cliente.listar(inicio=inicio, fim=fim)
