"""Conexão Postgres do C4ISTAR (borda e nuvem) com pool leve."""

from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path


def _carregar_env(caminho: str = ".env"):
    env_path = Path(caminho)
    if not env_path.exists():
        return
    for linha in env_path.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


_carregar_env()

_POOL: list = []
_POOL_MAX = 4
_TRAVA = threading.Lock()
_DISPONIVEL_CACHE = (False, 0.0)


def database_url() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if url:
        return url
    host = os.getenv("PGHOST", "127.0.0.1").strip() or "127.0.0.1"
    porta = os.getenv("PGPORT", "5432").strip() or "5432"
    base = os.getenv("PGDATABASE", "c4istar").strip() or "c4istar"
    user = os.getenv("PGUSER", "c4istar").strip() or "c4istar"
    senha = os.getenv("PGPASSWORD", "c4istar").strip() or "c4istar"
    return f"postgresql://{user}:{senha}@{host}:{porta}/{base}"


def _nova_conexao():
    import psycopg

    return psycopg.connect(database_url(), autocommit=False)


def _pegar_conexao():
    with _TRAVA:
        while _POOL:
            conn = _POOL.pop()
            try:
                if conn.closed:
                    continue
                return conn
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
    return _nova_conexao()


def _devolver_conexao(conn):
    if conn is None:
        return
    try:
        if conn.closed:
            return
        with _TRAVA:
            if len(_POOL) < _POOL_MAX:
                _POOL.append(conn)
                return
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def disponivel() -> bool:
    """Cache curto: evita SELECT 1 a cada insert/poll."""
    global _DISPONIVEL_CACHE
    ok, quando = _DISPONIVEL_CACHE
    agora = time.time()
    if agora - quando < 8.0:
        return ok
    try:
        import psycopg  # noqa: F401
    except ImportError:
        _DISPONIVEL_CACHE = (False, agora)
        return False
    try:
        with conectar() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        _DISPONIVEL_CACHE = (True, agora)
        return True
    except Exception:
        _DISPONIVEL_CACHE = (False, agora)
        return False


@contextmanager
def conectar():
    conn = _pegar_conexao()
    try:
        yield conn
        conn.commit()
        _devolver_conexao(conn)
        conn = None
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        conn = None
        raise
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def aplicar_schema(caminho: Path | None = None):
    sql = Path(caminho or Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


def cliente_padrao() -> str:
    return "".join(c for c in (os.getenv("CLIENTE_DOCUMENTO") or "") if c.isdigit())
