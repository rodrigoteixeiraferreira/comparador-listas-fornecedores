"""O banco dos testes: cada teste roda numa transação que se desfaz no fim. Nada fica gravado.

Sem DATABASE_URL, os testes de banco são pulados; com REQUIRE_DB=1 (no CI), a falta do banco é falha, não pulo.
"""
import os

import pytest


@pytest.fixture
def db():
    from pricelists.db import connect, database_url
    from pricelists.migrate import apply_pending

    try:
        database_url()
    except RuntimeError:
        if os.environ.get("REQUIRE_DB") == "1":
            raise
        pytest.skip("sem DATABASE_URL")
    conn = connect()
    try:
        apply_pending(conn, record=False)  # no banco ainda sem as migrações, o ensaio as aplica e desfaz
        yield conn
    finally:
        conn.rollback()
        conn.close()
