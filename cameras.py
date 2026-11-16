"""
Cadastro de câmeras fora do código.

O arquivo cameras.json é a lista que o analítico lê. O portal grava o mesmo
arquivo (via cadastro) para incluir, desativar ou remover câmeras.

Protocolos suportados:
  - rtsp: analítico puxa o stream (LAN / Tailscale / URL pronta).
  - rtmp: câmera envia (push) para o ingest; analítico lê a URL local de play.

    {
  "cameras": [
    {
      "id": "cam-portaria",
      "nome": "Portaria",
      "ativa": true,
      "protocolo": "rtsp",
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
    },
    {
      "id": "cam-vizinho-rtmp",
      "nome": "Entrada vizinho",
      "ativa": true,
      "protocolo": "rtmp",
      "stream_key": "abc123",
      "rua": "Rua vizinha",
      "bairro": "Stella Maris",
      "cidade": "Salvador"
    }
  ]
}

"url" é o que o OpenCV abre (RTSP pull ou play local do RTMP).
"ativa": false tira a câmera da análise e mantém o cadastro.
"""

from __future__ import annotations

import json
import os
import secrets
import re
from pathlib import Path
from urllib.parse import quote, urlparse


ARQUIVO_CAMERAS = "cameras.json"
PROTOCOLOS = ("rtsp", "rtmp")


def gerar_stream_key(tamanho: int = 16) -> str:
    """Chave única para path RTMP (Mibo Personalizado / MediaMTX)."""
    return secrets.token_hex(max(8, tamanho // 2))


def _ler_env_arquivo(caminho: str = ".env") -> dict[str, str]:
    """Lê .env sem depender do processo ter chamado carregar_env."""
    lidos: dict[str, str] = {}
    path = Path(caminho)
    if not path.exists():
        return lidos
    try:
        for linha in path.read_text(encoding="utf-8").splitlines():
            texto = linha.strip()
            if not texto or texto.startswith("#") or "=" not in texto:
                continue
            chave, valor = texto.split("=", 1)
            lidos[chave.strip()] = valor.strip().strip('"').strip("'")
    except OSError:
        return lidos
    return lidos


def _env(nome: str, padrao: str = "") -> str:
    valor = str(os.getenv(nome) or "").strip()
    if valor:
        return valor
    arquivo = _ler_env_arquivo().get(nome, "")
    if arquivo:
        return str(arquivo).strip()
    return str(padrao or "").strip()


def config_rtmp() -> dict:
    """Hosts públicos (push da câmera) e locais (play do analítico)."""
    app = _env("RTMP_APP", "live") or "live"
    return {
        "app": app.strip("/"),
        "public_host": _env("RTMP_PUBLIC_HOST", "127.0.0.1") or "127.0.0.1",
        "public_port": int(_env("RTMP_PUBLIC_PORT", "1935") or "1935"),
        "public_scheme": (_env("RTMP_PUBLIC_SCHEME", "rtmp") or "rtmp").lower(),
        "play_host": _env("RTMP_PLAY_HOST", "127.0.0.1") or "127.0.0.1",
        "play_port": int(_env("RTMP_PLAY_PORT", "8554") or "8554"),
        "play_scheme": (_env("RTMP_PLAY_SCHEME", "rtsp") or "rtsp").lower(),
    }


def montar_url_rtmp_publicar(stream_key: str, cfg: dict | None = None) -> str:
    """URL que o cliente cola no app Mibo (Personalizado)."""
    chave = str(stream_key or "").strip().strip("/")
    if not chave:
        raise ValueError("stream_key ausente")
    c = cfg or config_rtmp()
    return f"{c['public_scheme']}://{c['public_host']}:{c['public_port']}/{c['app']}/{chave}"


def _ip_lan() -> str:
    host = _env("RTMP_LAN_HOST", "")
    if host:
        return host
    try:
        import socket

        ips = [
            ip
            for ip in socket.gethostbyname_ex(socket.gethostname())[2]
            if ip and not ip.startswith("127.")
        ]
        # Prefere Wi-Fi domestica 192.168.x; evita VPN/Tailscale (10.x / 100.x).
        for ip in ips:
            if ip.startswith("192.168."):
                return ip
        if ips:
            return ips[0]
    except OSError:
        pass
    return "192.168.0.3"


def montar_url_rtmp_lan(stream_key: str, cfg: dict | None = None) -> str:
    """URL para teste com a câmera na mesma rede local (evita NAT loopback)."""
    chave = str(stream_key or "").strip().strip("/")
    if not chave:
        raise ValueError("stream_key ausente")
    c = cfg or config_rtmp()
    return f"{c['public_scheme']}://{_ip_lan()}:{c['public_port']}/{c['app']}/{chave}"


def montar_url_rtmp_play(stream_key: str, cfg: dict | None = None) -> str:
    """URL local que o analítico abre (MediaMTX republica RTSP)."""
    chave = str(stream_key or "").strip().strip("/")
    if not chave:
        raise ValueError("stream_key ausente")
    c = cfg or config_rtmp()
    return f"{c['play_scheme']}://{c['play_host']}:{c['play_port']}/{c['app']}/{chave}"


def normalizar_protocolo(valor) -> str:
    texto = str(valor or "rtsp").strip().lower()
    if texto in ("rtmp", "rtmps"):
        return "rtmp"
    return "rtsp"


def montar_url_rtsp(camera: dict) -> str:
    """Monta a URL RTSP Intelbras a partir dos dados de acesso."""
    host = str(camera.get("host") or "").strip()
    if not host:
        raise ValueError("host ausente")

    porta = int(camera.get("porta") or 554)
    # Host no formulário às vezes vem como "IP:554"; evita rtsp://...:554:554/...
    if ":" in host and not host.startswith("["):
        base, _, sufixo = host.rpartition(":")
        if base and sufixo.isdigit():
            host = base
            porta = int(sufixo)
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
    protocolo = normalizar_protocolo(item.get("protocolo"))
    # Heurística: URL já gravada como rtmp → trata como push
    url_bruta = str(item.get("url") or "").strip()
    if protocolo == "rtsp" and url_bruta.lower().startswith("rtmp"):
        protocolo = "rtmp"

    stream_key = str(item.get("stream_key") or "").strip()
    rtmp_publicar = str(item.get("rtmp_url_publicar") or "").strip()
    url = url_bruta

    if protocolo == "rtmp":
        if not stream_key:
            # Extrai a chave do path .../live/CHAVE se já veio na URL
            for candidata in (rtmp_publicar, url_bruta):
                m = re.search(r"/([^/]+)/?$", candidata.strip())
                if m and m.group(1).lower() not in ("live", "app", "stream"):
                    stream_key = m.group(1)
                    break
        if not stream_key:
            print(f"Câmera {ident} ignorada: RTMP sem stream_key.")
            return None
        try:
            rtmp_publicar = rtmp_publicar or montar_url_rtmp_publicar(stream_key)
            url = montar_url_rtmp_play(stream_key)
        except (TypeError, ValueError):
            print(f"Câmera {ident} ignorada: não montou URL RTMP.")
            return None
    else:
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
        "protocolo": protocolo,
        "stream_key": stream_key,
        "rtmp_url_publicar": rtmp_publicar,
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
