"""Conexão Postgres do C4ISTAR (borda e nuvem)."""

from __future__ import annotations

import os
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


def disponivel() -> bool:
    try:
        import psycopg
    except ImportError:
        return False
    try:
        with conectar() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:
        return False


@contextmanager
def conectar():
    import psycopg

    conn = psycopg.connect(database_url(), autocommit=False)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def aplicar_schema(caminho: Path | None = None):
    sql = Path(caminho or Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


def cliente_padrao() -> str:
    return "".join(c for c in (os.getenv("CLIENTE_DOCUMENTO") or "") if c.isdigit())
