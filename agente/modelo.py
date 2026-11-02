"""Sessão com o GPT pela API da OpenAI."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path


MODELO_PADRAO = "gpt-6-sol"
BASE_PADRAO = "https://api.openai.com/v1"


def carregar_env(caminho=".env"):
    env_path = Path(caminho)
    if not env_path.exists():
        return
    for linha in env_path.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


class SessaoGPT:
    """Conversa local com o modelo. O histórico recente volta no próximo pedido."""

    def __init__(self, api_key=None, modelo=None, base_url=None):
        carregar_env()
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        self.modelo = modelo or os.getenv("GPT_MODEL", MODELO_PADRAO)
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", BASE_PADRAO)).rstrip("/")
        self.historico = []

    @property
    def disponivel(self) -> bool:
        return bool(self.api_key.strip())

    def perguntar(self, sistema: str, usuario: str, json_mode=True) -> str:
        if not self.disponivel:
            raise RuntimeError(
                "OPENAI_API_KEY não definida. Crie uma chave em "
                "https://platform.openai.com/api-keys e coloque no arquivo .env. "
                "A chave começa com sk-."
            )

        mensagens = [{"role": "system", "content": sistema}]
        mensagens.extend(self.historico[-6:])
        mensagens.append({"role": "user", "content": usuario})
        corpo = {"model": self.modelo, "messages": mensagens}
        if json_mode:
            corpo["response_format"] = {"type": "json_object"}

        resposta = self._post("/chat/completions", corpo)
        texto = _texto_chat(resposta)
        self.historico.append({"role": "user", "content": usuario[:4000]})
        self.historico.append({"role": "assistant", "content": texto[:4000]})
        if len(self.historico) > 8:
            self.historico = self.historico[-8:]
        return texto

    def _post(self, caminho: str, corpo: dict) -> dict:
        requisicao = urllib.request.Request(
            f"{self.base_url}{caminho}",
            data=json.dumps(corpo).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(requisicao, timeout=180) as resposta:
                return json.loads(resposta.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detalhe = exc.read().decode("utf-8", errors="replace")[:800]
            raise RuntimeError(f"GPT HTTP {exc.code}: {detalhe}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Sem conexão com o GPT: {exc.reason}") from exc


def _texto_chat(resposta: dict) -> str:
    try:
        conteudo = resposta["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return json.dumps(resposta, ensure_ascii=False)[:4000]
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        partes = []
        for bloco in conteudo:
            if isinstance(bloco, str):
                partes.append(bloco)
            elif isinstance(bloco, dict):
                partes.append(str(bloco.get("text") or ""))
        return "\n".join(parte for parte in partes if parte).strip()
    return str(conteudo or "")


def extrair_json(texto: str) -> dict:
    bruto = (texto or "").strip()
    if bruto.startswith("```"):
        bruto = bruto.strip("`")
        if bruto.lower().startswith("json"):
            bruto = bruto[4:]
        bruto = bruto.strip()
    inicio = bruto.find("{")
    fim = bruto.rfind("}")
    if inicio >= 0 and fim > inicio:
        bruto = bruto[inicio:fim + 1]
    return json.loads(bruto)
