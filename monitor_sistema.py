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


def _digitos_mb(valor: float) -> float:
    return round(float(valor or 0), 2)


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
    if not ARQUIVO.exists():
        return {"amostras": [], "dias": {}}
    try:
        bruto = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"amostras": [], "dias": {}}
    if not isinstance(bruto, dict):
        return {"amostras": [], "dias": {}}
    bruto.setdefault("amostras", [])
    bruto.setdefault("dias", {})
    return bruto


def _gravar_hist(dados: dict):
    ARQUIVO.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _persistir_pg(amostra: dict, tabelas: list[dict]):
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
    with _TRAVA:
        hist = _ler_hist()
        hist["amostras"].append(amostra)
        hist["amostras"] = hist["amostras"][-2000:]
        dia = date.today().isoformat()
        hist["dias"][dia] = {
            "cpu_pct": amostra["cpu_pct"],
            "ram_pct": amostra["ram_pct"],
            "tabelas_mb": amostra["tabelas_mb"],
            "disco_usado_mb": amostra["disco_usado_mb"],
            "tabelas": {item["tabela"]: {"bytes": item["bytes"], "linhas": item["linhas"]} for item in tabelas},
        }
        _gravar_hist(hist)
    _persistir_pg(amostra, tabelas)
    return {"agora": amostra, "tabelas": tabelas}


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
        "amostras": [
            _escala_host({
                "quando": item.get("quando"),
                "cpu_pct": item.get("cpu_pct"),
                "ram_pct": item.get("ram_pct"),
                "tabelas_mb": item.get("tabelas_mb"),
            })
            for item in amostras
        ],
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
