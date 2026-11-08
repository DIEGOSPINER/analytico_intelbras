"""Ajusta limiares de detecção com likes/dislikes e sim/não do Stive."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

ARQUIVO = Path("ajustes_feedback.json")
_TRAVA = threading.Lock()

# Valores-base do sistema; o feedback desloca estes parâmetros com tetos seguros.
_BASE = {
    "audio_disparo_pico": 0.45,
    "audio_disparo_mult": 20.0,
    "audio_cooldown_seg": 90.0,
    "permanencia_parado_seg": 20.0,
    "permanencia_cena_seg": 10.0,
    "tempo_parado_comportamento": 30.0,
    "conf_pessoa_delta": 0.0,
    "conf_veiculo_delta": 0.0,
    "limiar_face_delta": 0.0,
    "limiar_placa_delta": 0.0,
    "frames_confirmacao_delta": 0,
}

_LIMITES = {
    "audio_disparo_pico": (0.35, 0.85),
    "audio_disparo_mult": (12.0, 40.0),
    "audio_cooldown_seg": (60.0, 240.0),
    "permanencia_parado_seg": (15.0, 90.0),
    "permanencia_cena_seg": (8.0, 60.0),
    "tempo_parado_comportamento": (20.0, 90.0),
    "conf_pessoa_delta": (-0.05, 0.20),
    "conf_veiculo_delta": (-0.05, 0.20),
    "limiar_face_delta": (-0.04, 0.15),
    "limiar_placa_delta": (-0.04, 0.15),
    "frames_confirmacao_delta": (0, 4),
}


def classificar_assunto(texto: str = "", tipo: str = "", titulo: str = "") -> str:
    baixo = f"{tipo} {titulo} {texto}".lower()
    if any(t in baixo for t in ("disparo", "tiro", "arma", "pico curto")):
        return "disparo"
    if any(t in baixo for t in ("áudio", "audio", "briga", "socorro", "xing")):
        return "audio"
    if any(t in baixo for t in ("placa", "lpr", "veículo de interesse", "veiculo de interesse")):
        return "placa"
    if any(t in baixo for t in ("face", "facial", "reconhecimento", "rf", "pessoa de risco", "match")):
        return "face"
    if any(t in baixo for t in ("veícul", "veicul", "carro", "moto")) and any(
        t in baixo for t in ("parada", "parado", "perman", "confirma")
    ):
        return "permanencia_veiculo"
    if any(t in baixo for t in ("pessoa",)) and any(
        t in baixo for t in ("parada", "parado", "perman", "confirma")
    ):
        return "permanencia_pessoa"
    if any(t in baixo for t in ("comport", "queda", "deitad", "correndo", "interaç", "interac", "aglomer")):
        return "comportamento"
    if "veícul" in baixo or "veicul" in baixo:
        return "veiculo"
    if "pessoa" in baixo:
        return "pessoa"
    return "geral"


def aplicar_feedback(
    sinal: int,
    texto: str = "",
    tipo: str = "",
    titulo: str = "",
    camera: str = "",
    documento: str = "",
) -> dict:
    """sinal +1 = correto (sim/like); -1 = falso positivo (não/dislike)."""
    try:
        voto = int(sinal)
    except (TypeError, ValueError):
        voto = 0
    if voto not in (-1, 1):
        return ler_ajustes()
    dominio = classificar_assunto(texto, tipo, titulo)
    with _TRAVA:
        bruto = _ler()
        ajustes = dict(_BASE)
        ajustes.update(bruto.get("ajustes") or {})
        _deslocar(ajustes, dominio, voto)
        bruto["ajustes"] = ajustes
        bruto.setdefault("historico", []).append({
            "quando": datetime.now().isoformat(timespec="seconds"),
            "sinal": voto,
            "dominio": dominio,
            "tipo": str(tipo or "")[:40],
            "camera": str(camera or "")[:60],
            "documento": str(documento or "")[:40],
            "texto": str(texto or "")[:180],
        })
        bruto["historico"] = bruto["historico"][-500:]
        bruto["resumo"] = _resumo(bruto["historico"])
        _gravar(bruto)
        return dict(ajustes)


def ler_ajustes() -> dict:
    with _TRAVA:
        bruto = _ler()
        saida = dict(_BASE)
        saida.update(bruto.get("ajustes") or {})
        return saida


def obter(chave: str, padrao=None):
    ajustes = ler_ajustes()
    if chave in ajustes:
        return ajustes[chave]
    return padrao if padrao is not None else _BASE.get(chave)


def limiar_audio_disparo() -> tuple[float, float, float]:
    """Retorna (pico_min, multiplicador_base, cooldown_seg)."""
    a = ler_ajustes()
    return (
        float(a["audio_disparo_pico"]),
        float(a["audio_disparo_mult"]),
        float(a["audio_cooldown_seg"]),
    )


def tempos_permanencia() -> tuple[float, float]:
    a = ler_ajustes()
    return float(a["permanencia_parado_seg"]), float(a["permanencia_cena_seg"])


def tempo_parado_comportamento() -> float:
    return float(ler_ajustes()["tempo_parado_comportamento"])


def conf_deteccao(pessoa: float, veiculo: float) -> tuple[float, float]:
    a = ler_ajustes()
    return (
        max(0.25, min(0.85, float(pessoa) + float(a["conf_pessoa_delta"]))),
        max(0.20, min(0.85, float(veiculo) + float(a["conf_veiculo_delta"]))),
    )


def limiar_face(base: float) -> float:
    return max(0.45, min(0.85, float(base) + float(ler_ajustes()["limiar_face_delta"])))


def limiar_placa(base: float) -> float:
    return max(0.40, min(0.85, float(base) + float(ler_ajustes()["limiar_placa_delta"])))


def frames_confirmacao(base: int) -> int:
    return int(max(2, min(8, int(base) + int(ler_ajustes()["frames_confirmacao_delta"]))))


def _deslocar(ajustes: dict, dominio: str, voto: int):
    # voto -1 = falso positivo → endurece; +1 = confirma → afrouxa um pouco / estabiliza
    if dominio == "disparo":
        _passo(ajustes, "audio_disparo_pico", 0.04 if voto < 0 else -0.01)
        _passo(ajustes, "audio_disparo_mult", 2.0 if voto < 0 else -0.5)
        _passo(ajustes, "audio_cooldown_seg", 15.0 if voto < 0 else -5.0)
    elif dominio == "audio":
        _passo(ajustes, "audio_disparo_pico", 0.02 if voto < 0 else -0.005)
        _passo(ajustes, "audio_cooldown_seg", 10.0 if voto < 0 else -3.0)
    elif dominio == "permanencia_pessoa":
        _passo(ajustes, "permanencia_parado_seg", 8.0 if voto < 0 else -2.0)
        _passo(ajustes, "permanencia_cena_seg", 5.0 if voto < 0 else -1.0)
        _passo(ajustes, "conf_pessoa_delta", 0.02 if voto < 0 else -0.005)
    elif dominio == "permanencia_veiculo":
        _passo(ajustes, "permanencia_parado_seg", 8.0 if voto < 0 else -2.0)
        _passo(ajustes, "permanencia_cena_seg", 5.0 if voto < 0 else -1.0)
        _passo(ajustes, "conf_veiculo_delta", 0.02 if voto < 0 else -0.005)
    elif dominio == "comportamento":
        _passo(ajustes, "tempo_parado_comportamento", 8.0 if voto < 0 else -2.0)
        _passo(ajustes, "frames_confirmacao_delta", 1 if voto < 0 else 0)
    elif dominio == "face":
        _passo(ajustes, "limiar_face_delta", 0.02 if voto < 0 else -0.005)
        _passo(ajustes, "conf_pessoa_delta", 0.01 if voto < 0 else -0.002)
    elif dominio == "placa":
        _passo(ajustes, "limiar_placa_delta", 0.02 if voto < 0 else -0.005)
        _passo(ajustes, "conf_veiculo_delta", 0.01 if voto < 0 else -0.002)
    elif dominio in ("pessoa", "veiculo"):
        chave = "conf_pessoa_delta" if dominio == "pessoa" else "conf_veiculo_delta"
        _passo(ajustes, chave, 0.015 if voto < 0 else -0.004)
    else:
        # Feedback genérico de risco: endurece um pouco áudio e permanência (FP frequentes).
        if voto < 0:
            _passo(ajustes, "audio_disparo_pico", 0.015)
            _passo(ajustes, "permanencia_parado_seg", 3.0)


def _passo(ajustes: dict, chave: str, delta: float):
    minimo, maximo = _LIMITES[chave]
    atual = float(ajustes.get(chave, _BASE[chave]))
    novo = atual + float(delta)
    if isinstance(_BASE[chave], int):
        ajustes[chave] = int(max(minimo, min(maximo, round(novo))))
    else:
        ajustes[chave] = round(max(minimo, min(maximo, novo)), 4)


def _resumo(historico: list) -> dict:
    por = {}
    for item in historico[-200:]:
        dom = item.get("dominio") or "geral"
        slot = por.setdefault(dom, {"positivos": 0, "negativos": 0})
        if int(item.get("sinal") or 0) > 0:
            slot["positivos"] += 1
        else:
            slot["negativos"] += 1
    return por


def _ler() -> dict:
    if not ARQUIVO.exists():
        return {"ajustes": dict(_BASE), "historico": [], "resumo": {}}
    try:
        bruto = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"ajustes": dict(_BASE), "historico": [], "resumo": {}}
    if not isinstance(bruto, dict):
        return {"ajustes": dict(_BASE), "historico": [], "resumo": {}}
    bruto.setdefault("ajustes", dict(_BASE))
    bruto.setdefault("historico", [])
    bruto.setdefault("resumo", {})
    return bruto


def _gravar(bruto: dict):
    ARQUIVO.write_text(json.dumps(bruto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
