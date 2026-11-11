"""Monitor de armazenamento Postgres + CPU/RAM do host (perfil administrador)."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ARQUIVO = Path("historico_sistema.json")
_TRAVA = threading.Lock()
_THREAD = None
_PARAR = threading.Event()
_INTERVALO = max(30, int(os.getenv("SISTEMA_AMOSTRA_SEG", "120") or 120))
_TESTES_N = (1, 2, 4)

# Último desempenho publicado pelo main (por câmera + processo).
_DESEMPENHO_VIVO: dict = {
    "quando": "",
    "n_cameras": 0,
    "cpu_processo": 0.0,
    "ram_app_mb": 0.0,
    "cameras": [],
}


def _digitos_mb(valor: float) -> float:
    return round(float(valor or 0), 2)


def _digitos(valor: float, casas: int = 1) -> float:
    return round(float(valor or 0), casas)


def _media(valores: list[float]) -> float:
    vals = [float(v) for v in valores if v is not None]
    return (sum(vals) / len(vals)) if vals else 0.0


def _hist_base() -> dict:
    return {
        "amostras": [],
        "dias": {},
        "desempenho_amostras": [],
        "testes_capacidade": {str(n): None for n in _TESTES_N},
    }


def _host() -> dict:
    """CPU e RAM atuais. Preferência: psutil; fallback Windows/Unix."""
    try:
        import psutil

        cpu = float(psutil.cpu_percent(interval=0.2))
        mem = psutil.virtual_memory()
        disco = psutil.disk_usage(str(Path(".").resolve().anchor or "/"))
        return {
            "cpu_pct": round(cpu, 1),
            "ram_pct": round(float(mem.percent), 1),
            "ram_usada_mb": _digitos_mb(mem.used / (1024 * 1024)),
            "ram_total_mb": _digitos_mb(mem.total / (1024 * 1024)),
            "disco_usado_mb": _digitos_mb(disco.used / (1024 * 1024)),
            "disco_total_mb": _digitos_mb(disco.total / (1024 * 1024)),
        }
    except Exception:
        pass
    # Fallback mínimo sem psutil
    cpu = 0.0
    ram_usada = ram_total = 0.0
    try:
        if os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            estat = MEMORYSTATUSEX()
            estat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estat))
            ram_total = estat.ullTotalPhys / (1024 * 1024)
            ram_usada = (estat.ullTotalPhys - estat.ullAvailPhys) / (1024 * 1024)
            ram_pct = float(estat.dwMemoryLoad)
        else:
            ram_pct = 0.0
            with open("/proc/meminfo", encoding="utf-8") as arq:
                info = {}
                for linha in arq:
                    if ":" in linha:
                        k, v = linha.split(":", 1)
                        info[k] = int(v.strip().split()[0])
            total_kb = info.get("MemTotal", 0)
            disp_kb = info.get("MemAvailable", info.get("MemFree", 0))
            ram_total = total_kb / 1024
            ram_usada = (total_kb - disp_kb) / 1024
            ram_pct = (100.0 * ram_usada / ram_total) if ram_total else 0.0
    except Exception:
        ram_pct = 0.0
    try:
        import shutil

        uso = shutil.disk_usage(str(Path(".").resolve().anchor or "/"))
        disco_total = uso.total / (1024 * 1024)
        disco_usado = uso.used / (1024 * 1024)
    except Exception:
        disco_total = disco_usado = 0.0
    return {
        "cpu_pct": round(cpu, 1),
        "ram_pct": round(ram_pct, 1),
        "ram_usada_mb": _digitos_mb(ram_usada),
        "ram_total_mb": _digitos_mb(ram_total),
        "disco_usado_mb": _digitos_mb(disco_usado),
        "disco_total_mb": _digitos_mb(disco_total),
    }


def _tabelas_postgres() -> list[dict]:
    try:
        from db.conexao import conectar, disponivel

        if not disponivel():
            return []
        with conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.relname AS tabela,
                           pg_total_relation_size(c.oid) AS bytes,
                           COALESCE(s.n_live_tup, 0) AS linhas
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
                    WHERE n.nspname = 'public' AND c.relkind = 'r'
                    ORDER BY pg_total_relation_size(c.oid) DESC, c.relname
                    """
                )
                return [
                    {
                        "tabela": str(nome),
                        "bytes": int(tamanho or 0),
                        "linhas": int(linhas or 0),
                        "mb": _digitos_mb(int(tamanho or 0) / (1024 * 1024)),
                    }
                    for nome, tamanho, linhas in cur.fetchall()
                ]
    except Exception as exc:
        print(f"Monitor tabelas: {exc}")
        return []


def _ler_hist() -> dict:
    base = _hist_base()
    if not ARQUIVO.exists():
        return base
    try:
        bruto = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return base
    if not isinstance(bruto, dict):
        return base
    bruto.setdefault("amostras", [])
    bruto.setdefault("dias", {})
    bruto.setdefault("desempenho_amostras", [])
    testes = dict(bruto.get("testes_capacidade") or {})
    for n in _TESTES_N:
        testes.setdefault(str(n), None)
    bruto["testes_capacidade"] = testes
    return bruto


def _enriquecer_cameras(
    cameras: list[dict],
    cpu_processo: float,
    ram_app_mb: float,
) -> list[dict]:
    n = max(1, len(cameras))
    cpu_share = _digitos(float(cpu_processo or 0) / n, 1)
    ram_share = _digitos_mb(float(ram_app_mb or 0) / n)
    saida = []
    for item in cameras:
        saida.append({
            "id": str(item.get("id") or item.get("nome") or ""),
            "nome": str(item.get("nome") or item.get("id") or ""),
            "latencia_ms": _digitos(item.get("latencia_ms"), 1),
            "fps_efetivo": _digitos(item.get("fps_efetivo"), 2),
            "cpu_processo": cpu_share,
            "ram_app": ram_share,
        })
    return saida


def publicar_desempenho(
    cameras: list[dict] | None = None,
    cpu_processo: float = 0.0,
    ram_app_mb: float = 0.0,
) -> dict:
    """Recebe métricas ao vivo do main (latência/FPS por câmera + CPU/RAM do app)."""
    global _DESEMPENHO_VIVO
    lista = _enriquecer_cameras(list(cameras or []), cpu_processo, ram_app_mb)
    vivo = {
        "quando": datetime.now().isoformat(timespec="seconds"),
        "n_cameras": len(lista),
        "cpu_processo": _digitos(cpu_processo, 1),
        "ram_app_mb": _digitos_mb(ram_app_mb),
        "cameras": lista,
        "latencia_ms_media": _digitos(_media([c["latencia_ms"] for c in lista]), 1),
        "fps_efetivo_medio": _digitos(_media([c["fps_efetivo"] for c in lista]), 2),
    }
    with _TRAVA:
        _DESEMPENHO_VIVO = vivo
    return dict(vivo)


def desempenho_vivo() -> dict:
    with _TRAVA:
        return dict(_DESEMPENHO_VIVO)


def _amostra_desempenho_de_vivo(vivo: dict) -> dict:
    cams = list(vivo.get("cameras") or [])
    return {
        "quando": vivo.get("quando") or datetime.now().isoformat(timespec="seconds"),
        "n_cameras": int(vivo.get("n_cameras") or len(cams) or 0),
        "cpu_processo": _digitos(vivo.get("cpu_processo"), 1),
        "ram_app_mb": _digitos_mb(vivo.get("ram_app_mb")),
        "latencia_ms_media": _digitos(vivo.get("latencia_ms_media"), 1),
        "fps_efetivo_medio": _digitos(vivo.get("fps_efetivo_medio"), 2),
        "cameras": cams,
    }


def registrar_teste_capacidade(n_cameras: int) -> dict:
    """Congela o desempenho atual no slot de teste 1 / 2 / 4 câmeras."""
    n = int(n_cameras or 0)
    if n not in _TESTES_N:
        return {"ok": False, "erro": "Use n_cameras = 1, 2 ou 4."}
    vivo = desempenho_vivo()
    atuais = int(vivo.get("n_cameras") or 0)
    if atuais != n:
        return {
            "ok": False,
            "erro": (
                f"Há {atuais} câmera(s) ativa(s). "
                f"Para o teste {n}, deixe exatamente {n} câmera(s) em análise e tente de novo."
            ),
            "n_cameras_ativas": atuais,
            "n_pedido": n,
        }
    if atuais <= 0:
        return {"ok": False, "erro": "Nenhuma câmera ativa para registrar o teste."}
    amostra = _amostra_desempenho_de_vivo(vivo)
    amostra["teste"] = n
    amostra["rotulo"] = f"{n} câmera(s)"
    with _TRAVA:
        hist = _ler_hist()
        hist.setdefault("testes_capacidade", {})
        hist["testes_capacidade"][str(n)] = amostra
        _gravar_hist(hist)
    _persistir_teste_pg(amostra)
    return {"ok": True, "teste": amostra, "testes_capacidade": hist["testes_capacidade"]}


def testes_capacidade() -> dict:
    with _TRAVA:
        hist = _ler_hist()
        return dict(hist.get("testes_capacidade") or {})


def _gravar_hist(dados: dict):
    ARQUIVO.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _persistir_pg(amostra: dict, tabelas: list[dict], desempenho: dict | None = None):
    try:
        from db.conexao import conectar, disponivel

        if not disponivel():
            return
        with conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO metricas_sistema
                    (cpu_pct, ram_pct, ram_usada_mb, ram_total_mb, disco_usado_mb, disco_total_mb, tabelas_bytes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        amostra.get("cpu_pct"),
                        amostra.get("ram_pct"),
                        amostra.get("ram_usada_mb"),
                        amostra.get("ram_total_mb"),
                        amostra.get("disco_usado_mb"),
                        amostra.get("disco_total_mb"),
                        int(amostra.get("tabelas_bytes") or 0),
                    ),
                )
                dia = date.today().isoformat()
                for item in tabelas:
                    cur.execute(
                        """
                        INSERT INTO metricas_tabelas_dia (dia, tabela, bytes, linhas)
                        VALUES (%s,%s,%s,%s)
                        ON CONFLICT (dia, tabela) DO UPDATE
                        SET bytes = EXCLUDED.bytes, linhas = EXCLUDED.linhas
                        """,
                        (dia, item["tabela"], item["bytes"], item["linhas"]),
                    )
                if desempenho and int(desempenho.get("n_cameras") or 0) > 0:
                    cur.execute(
                        """
                        INSERT INTO metricas_desempenho
                        (n_cameras, cpu_processo, ram_app_mb, latencia_ms_media, fps_efetivo_medio, cameras_json)
                        VALUES (%s,%s,%s,%s,%s,%s::jsonb)
                        """,
                        (
                            int(desempenho.get("n_cameras") or 0),
                            float(desempenho.get("cpu_processo") or 0),
                            float(desempenho.get("ram_app_mb") or 0),
                            float(desempenho.get("latencia_ms_media") or 0),
                            float(desempenho.get("fps_efetivo_medio") or 0),
                            json.dumps(desempenho.get("cameras") or [], ensure_ascii=False),
                        ),
                    )
            conn.commit()
    except Exception:
        pass


def _persistir_teste_pg(amostra: dict):
    try:
        from db.conexao import conectar, disponivel

        if not disponivel():
            return
        with conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO testes_capacidade
                    (n_cameras, quando, cpu_processo, ram_app_mb, latencia_ms_media, fps_efetivo_medio, cameras_json)
                    VALUES (%s, NOW(), %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (n_cameras) DO UPDATE SET
                        quando = EXCLUDED.quando,
                        cpu_processo = EXCLUDED.cpu_processo,
                        ram_app_mb = EXCLUDED.ram_app_mb,
                        latencia_ms_media = EXCLUDED.latencia_ms_media,
                        fps_efetivo_medio = EXCLUDED.fps_efetivo_medio,
                        cameras_json = EXCLUDED.cameras_json
                    """,
                    (
                        int(amostra.get("teste") or amostra.get("n_cameras") or 0),
                        float(amostra.get("cpu_processo") or 0),
                        float(amostra.get("ram_app_mb") or 0),
                        float(amostra.get("latencia_ms_media") or 0),
                        float(amostra.get("fps_efetivo_medio") or 0),
                        json.dumps(amostra.get("cameras") or [], ensure_ascii=False),
                    ),
                )
            conn.commit()
    except Exception:
        pass


def amostrar() -> dict:
    host = _host()
    tabelas = _tabelas_postgres()
    total_bytes = sum(int(item.get("bytes") or 0) for item in tabelas)
    amostra = {
        **host,
        "quando": datetime.now().isoformat(timespec="seconds"),
        "tabelas_bytes": total_bytes,
        "tabelas_mb": _digitos_mb(total_bytes / (1024 * 1024)),
        "tabelas": len(tabelas),
    }
    vivo = desempenho_vivo()
    desempenho = _amostra_desempenho_de_vivo(vivo) if int(vivo.get("n_cameras") or 0) > 0 else None
    with _TRAVA:
        hist = _ler_hist()
        hist["amostras"].append(amostra)
        hist["amostras"] = hist["amostras"][-2000:]
        if desempenho:
            hist.setdefault("desempenho_amostras", [])
            hist["desempenho_amostras"].append(desempenho)
            hist["desempenho_amostras"] = hist["desempenho_amostras"][-2000:]
            amostra["n_cameras"] = desempenho["n_cameras"]
            amostra["cpu_processo"] = desempenho["cpu_processo"]
            amostra["ram_app_mb"] = desempenho["ram_app_mb"]
            amostra["latencia_ms_media"] = desempenho["latencia_ms_media"]
            amostra["fps_efetivo_medio"] = desempenho["fps_efetivo_medio"]
        dia = date.today().isoformat()
        hist["dias"][dia] = {
            "cpu_pct": amostra["cpu_pct"],
            "ram_pct": amostra["ram_pct"],
            "tabelas_mb": amostra["tabelas_mb"],
            "disco_usado_mb": amostra["disco_usado_mb"],
            "cpu_processo": amostra.get("cpu_processo"),
            "ram_app_mb": amostra.get("ram_app_mb"),
            "latencia_ms_media": amostra.get("latencia_ms_media"),
            "fps_efetivo_medio": amostra.get("fps_efetivo_medio"),
            "n_cameras": amostra.get("n_cameras"),
            "tabelas": {item["tabela"]: {"bytes": item["bytes"], "linhas": item["linhas"]} for item in tabelas},
        }
        _gravar_hist(hist)
    _persistir_pg(amostra, tabelas, desempenho)
    return {"agora": amostra, "tabelas": tabelas, "desempenho": desempenho}


def _serie_dias(chave: str, dias: int = 30) -> list[dict]:
    with _TRAVA:
        hist = _ler_hist()
        mapa = dict(hist.get("dias") or {})
    hoje = date.today()
    saida = []
    acumulado = 0.0
    for i in range(dias - 1, -1, -1):
        dia = hoje - timedelta(days=i)
        chave_dia = dia.isoformat()
        bloco = mapa.get(chave_dia) or {}
        valor = float(bloco.get(chave) or 0)
        if chave == "tabelas_mb" and valor:
            acumulado = valor
        elif chave == "tabelas_mb":
            valor = acumulado
        saida.append({"rotulo": dia.strftime("%d/%m"), "dia": chave_dia, "valor": round(valor, 2)})
    return saida


def _serie_mes(chave: str, meses: int = 12) -> list[dict]:
    with _TRAVA:
        hist = _ler_hist()
        mapa = dict(hist.get("dias") or {})
    por_mes: dict[str, list[float]] = {}
    for dia, bloco in mapa.items():
        mes = str(dia)[:7]
        por_mes.setdefault(mes, []).append(float(bloco.get(chave) or 0))
    hoje = date.today().replace(day=1)
    saida = []
    for i in range(meses - 1, -1, -1):
        ano = hoje.year
        mes = hoje.month - i
        while mes <= 0:
            mes += 12
            ano -= 1
        chave_mes = f"{ano:04d}-{mes:02d}"
        vals = [v for v in por_mes.get(chave_mes, []) if v]
        media = round(sum(vals) / len(vals), 2) if vals else 0.0
        saida.append({"rotulo": f"{mes:02d}/{ano}", "mes": chave_mes, "valor": media})
    return saida


def _escalar_serie(serie: list[dict], fator: float) -> list[dict]:
    fator = max(0.0, min(float(fator or 0), 1.0))
    return [
        {
            **item,
            "valor": round(float(item.get("valor") or 0) * fator, 2),
        }
        for item in (serie or [])
    ]


def resumo(fator: float = 1.0, escopo: str = "cluster") -> dict:
    """Pacote para /sistema. fator<1 estima fatia do host para um cliente."""
    host = _host()
    tabelas = _tabelas_postgres()
    total_bytes = sum(int(item.get("bytes") or 0) for item in tabelas)
    fator = 1.0 if fator is None else max(0.0, min(float(fator), 1.0))
    with _TRAVA:
        hist = _ler_hist()
        amostras = list(hist.get("amostras") or [])[-288:]
        desempenho_amostras = list(hist.get("desempenho_amostras") or [])[-288:]
        testes = dict(hist.get("testes_capacidade") or {})
    for n in _TESTES_N:
        testes.setdefault(str(n), None)

    def _escala_host(bloco: dict) -> dict:
        if fator >= 0.999:
            return dict(bloco)
        saida = dict(bloco)
        for chave in ("cpu_pct", "ram_pct", "ram_usada_mb", "disco_usado_mb", "tabelas_mb", "tabelas_bytes"):
            if chave in saida and saida[chave] is not None:
                saida[chave] = round(float(saida[chave]) * fator, 2) if chave != "tabelas_bytes" else int(float(saida[chave]) * fator)
        return saida

    agora = _escala_host({
        **host,
        "tabelas_bytes": total_bytes,
        "tabelas_mb": _digitos_mb(total_bytes / (1024 * 1024)),
        "tabelas": len(tabelas),
        "quando": datetime.now().isoformat(timespec="seconds"),
    })
    tabelas_vista = []
    for item in tabelas:
        bytes_i = int(item.get("bytes") or 0)
        if fator < 0.999:
            bytes_i = int(bytes_i * fator)
        tabelas_vista.append({
            **item,
            "bytes": bytes_i,
            "mb": _digitos_mb(bytes_i / (1024 * 1024)),
            "linhas": int(round(int(item.get("linhas") or 0) * fator)),
        })
    vivo = desempenho_vivo()

    return {
        "agora": agora,
        "tabelas": tabelas_vista,
        "total_armazenado_mb": float(agora.get("tabelas_mb") or 0),
        "crescimento_diario": _escalar_serie(_serie_dias("tabelas_mb", 30), fator),
        "crescimento_mensal": _escalar_serie(_serie_mes("tabelas_mb", 12), fator),
        "crescimento_acumulado": _escalar_serie(_serie_dias("tabelas_mb", 90), fator),
        "cpu_diario": _escalar_serie(_serie_dias("cpu_pct", 30), fator),
        "ram_diario": _escalar_serie(_serie_dias("ram_pct", 30), fator),
        "disco_diario": _escalar_serie(_serie_dias("disco_usado_mb", 30), fator),
        "cpu_processo_diario": _serie_dias("cpu_processo", 30),
        "ram_app_diario": _serie_dias("ram_app_mb", 30),
        "latencia_diaria": _serie_dias("latencia_ms_media", 30),
        "fps_diario": _serie_dias("fps_efetivo_medio", 30),
        "amostras": [
            _escala_host({
                "quando": item.get("quando"),
                "cpu_pct": item.get("cpu_pct"),
                "ram_pct": item.get("ram_pct"),
                "tabelas_mb": item.get("tabelas_mb"),
            })
            for item in amostras
        ],
        "desempenho": vivo,
        "desempenho_amostras": desempenho_amostras,
        "testes_capacidade": testes,
        "testes_capacidade_n": list(_TESTES_N),
        "escopo": escopo,
        "fator_escopo": round(fator, 4),
    }


def _loop():
    while not _PARAR.wait(_INTERVALO):
        try:
            amostrar()
        except Exception as exc:
            print(f"Monitor sistema: {exc}")


def _garantir_schema():
    try:
        from db.conexao import aplicar_schema, disponivel

        if disponivel():
            aplicar_schema(Path(__file__).resolve().parent / "db" / "schema_sistema.sql")
    except Exception as exc:
        print(f"Schema sistema: {exc}")


def iniciar():
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return
    _PARAR.clear()
    _garantir_schema()
    try:
        amostrar()
    except Exception as exc:
        print(f"Primeira amostra do sistema: {exc}")
    _THREAD = threading.Thread(target=_loop, name="monitor-sistema", daemon=True)
    _THREAD.start()


def parar():
    _PARAR.set()
