"""A conexão com o banco. A string vem de DATABASE_URL, no ambiente ou no arquivo .env (fora do git)."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

os.environ.setdefault("PSYCOPG_IMPL", "python")  # o psycopg em Python puro (o binário é barrado no Windows)

import psycopg  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    env_file = ROOT / ".env"
    if not url and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "DATABASE_URL":
                url = value.strip().strip('"').strip("'")
    if not url:
        raise RuntimeError("DATABASE_URL vazio: ver .env.example")
    return url


def connect(**kwargs) -> psycopg.Connection:
    """Passa usuário e senha à parte: a senha com @, & ou ! colada na URL sem codificar quebraria a conexão."""
    parts = urlsplit(database_url())
    params = {"host": parts.hostname, "port": parts.port or 5432, "dbname": parts.path.lstrip("/") or "postgres",
              "user": unquote(parts.username or ""), "password": unquote(parts.password or "")}
    return psycopg.connect(**params, **kwargs)
