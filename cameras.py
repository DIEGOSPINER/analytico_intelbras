"""
Cadastro de câmeras fora do código.

O arquivo cameras.json é a lista que o analítico lê. Um formulário Django
pode gravar o mesmo arquivo (ou a mesma lista) para incluir, desativar ou
remover câmeras sem alterar o programa.

Cada câmera aceita o endereço completo ou os campos de acesso Intelbras:

{
  "cameras": [
    {
      "id": "cam-portaria",
      "nome": "Portaria",
      "ativa": true,
      "host": "192.168.0.21",
      "porta": 554,
      "usuario": "admin",
      "senha": "senha",
      "canal": 1,
      "subtype": 0,
      "rua": "Rua da camera",
      "bairro": "Bairro",
      "cidade": "Cidade/UF",
      "latitude": 0.0,
      "longitude": 0.0
    }
  ]
}

"url" substitui host/usuario/senha quando o RTSP já vier pronto.
"ativa": false tira a câmera da análise e mantém o cadastro.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote, urlparse


ARQUIVO_CAMERAS = "cameras.json"


def montar_url_rtsp(camera: dict) -> str:
    """Monta a URL RTSP Intelbras a partir dos dados de acesso."""
    host = str(camera.get("host") or "").strip()
    if not host:
        raise ValueError("host ausente")

    porta = int(camera.get("porta") or 554)
    canal = int(camera.get("canal") or 1)
    subtype = camera.get("subtype")
    subtype = 0 if subtype is None or subtype == "" else int(subtype)
    usuario = quote(str(camera.get("usuario") or ""), safe="")
    senha = quote(str(camera.get("senha") or ""), safe="")

    if usuario and senha:
        auth = f"{usuario}:{senha}@"
    elif usuario:
        auth = f"{usuario}@"
    else:
        auth = ""

    return (
        f"rtsp://{auth}{host}:{porta}/cam/realmonitor"
        f"?channel={canal}&subtype={subtype}"
    )


def destino_publico(url: str) -> str:
    """Host da câmera, sem usuário nem senha, para mensagens de log."""
    try:
        parsed = urlparse(url)
    except Exception:
        return ""
    if not parsed.hostname:
        return ""
    porta = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.hostname}{porta}"


def _coordenada(valor):
    if valor in (None, ""):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if not -180 <= numero <= 180:
        return None
    return numero


def _como_bool(valor, padrao=True) -> bool:
    if valor is None:
        return padrao
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return bool(valor)
    texto = str(valor).strip().lower()
    if texto in ("1", "true", "sim", "yes", "on"):
        return True
    if texto in ("0", "false", "nao", "não", "no", "off"):
        return False
    return padrao


def _normalizar(item, indice: int):
    if not isinstance(item, dict):
        print(f"Câmera na posição {indice + 1} ignorada: registro inválido.")
        return None

    ident = str(item.get("id") if item.get("id") not in (None, "") else indice + 1).strip()
    if not ident:
        print(f"Câmera na posição {indice + 1} ignorada: id vazio.")
        return None

    nome = str(item.get("nome") or f"CAMERA {ident}").strip() or f"CAMERA {ident}"
    url = str(item.get("url") or "").strip()
    if not url:
        try:
            url = montar_url_rtsp(item)
        except (TypeError, ValueError):
            print(f"Câmera {ident} ignorada: informe host ou url.")
            return None

    return {
        "id": ident,
        "nome": nome,
        "url": url,
        "ativa": _como_bool(item.get("ativa"), True),
        "modelo": str(item.get("modelo") or item.get("perfil") or "").strip(),
        "rua": str(item.get("rua") or "").strip(),
        "bairro": str(item.get("bairro") or "").strip(),
        "cidade": str(item.get("cidade") or "").strip(),
        "latitude": _coordenada(item.get("latitude")),
        "longitude": _coordenada(item.get("longitude")),
    }


def filtrar_ativas(registros) -> list[dict]:
    """Normaliza uma lista de câmeras e devolve só as ativas."""
    if not isinstance(registros, list):
        raise ValueError("A chave cameras deve ser uma lista.")
    ativas = []
    vistos = set()
    for indice, item in enumerate(registros):
        camera = _normalizar(item, indice)
        if camera is None:
            continue
        if camera["id"] in vistos:
            print(f"Câmera duplicada ignorada: {camera['id']}")
            continue
        vistos.add(camera["id"])
        if camera["ativa"]:
            ativas.append(camera)
    return ativas


def ler_cameras(caminho=ARQUIVO_CAMERAS):
    """
    Lê o cadastro e devolve só as câmeras ativas.
    O arquivo pode ser uma lista ou um objeto {"cameras": [...]}.
    """
    path = Path(caminho)
    if not path.exists():
        return []

    try:
        bruto = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"cameras.json inválido: {exc}") from exc

    if isinstance(bruto, dict):
        registros = bruto.get("cameras", [])
    elif isinstance(bruto, list):
        registros = bruto
    else:
        raise ValueError("cameras.json deve ser uma lista ou um objeto com a chave cameras.")

    return filtrar_ativas(registros)


def cameras_do_ambiente():
    """Compatibilidade com RTSP_CAM_1, RTSP_CAM_2... quando o JSON ainda não existe."""
    encontradas = []
    for chave in sorted(os.environ):
        if not chave.startswith("RTSP_CAM_"):
            continue
        url = os.environ.get(chave, "").strip()
        if not url:
            continue
        numero = chave.removeprefix("RTSP_CAM_").strip() or str(len(encontradas) + 1)
        encontradas.append({
            "id": f"cam-{numero}",
            "nome": f"CAMERA {numero}",
            "ativa": True,
            "url": url,
        })
    return encontradas


def garantir_arquivo_cameras(caminho=ARQUIVO_CAMERAS):
    """Cria cameras.json a partir do .env só na primeira execução."""
    path = Path(caminho)
    if path.exists():
        return

    cameras = cameras_do_ambiente()
    conteudo = {"cameras": cameras}
    path.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if cameras:
        print(
            f"Cadastro de câmeras criado em {caminho} "
            f"({len(cameras)} a partir do ambiente)."
        )
    else:
        print(
            f"Cadastro de câmeras criado em {caminho}. "
            "Inclua as câmeras nesse arquivo para iniciar a análise."
        )
