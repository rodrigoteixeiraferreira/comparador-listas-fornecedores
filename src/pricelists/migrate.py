"""Aplica as migrações de supabase/migrations que o banco ainda não tem, na mesma tabela de controle da CLI.

    python -m pricelists.migrate            aplica e grava
    python -m pricelists.migrate --check    só diz o que falta

Migração aplicada não se edita: o erro na 0100 vira uma 0400.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import psycopg

from .db import ROOT, connect

MIGRATIONS = ROOT / "supabase" / "migrations"


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS.glob("*.sql"))


def applied(conn: psycopg.Connection) -> set[str]:
    exists = conn.execute("select to_regclass('supabase_migrations.schema_migrations') is not null").fetchone()[0]
    if not exists:
        return set()
    return {r[0] for r in conn.execute("select version from supabase_migrations.schema_migrations")}


def apply_pending(conn: psycopg.Connection, record: bool = True) -> list[str]:
    """Aplica na transação corrente o que falta. Com record=False, não grava no controle (para o ensaio)."""
    done = applied(conn)
    names = []
    for path in migration_files():
        version, _, name = path.stem.partition("_")
        if version in done:
            continue
        conn.execute(path.read_text(encoding="utf-8"))
        if record:
            conn.execute("create schema if not exists supabase_migrations")
            conn.execute("create table if not exists supabase_migrations.schema_migrations "
                         "(version text primary key, statements text[], name text)")
            conn.execute("insert into supabase_migrations.schema_migrations (version, name) values (%s, %s)",
                         (version, name))
        names.append(path.name)
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    with connect() as conn:
        if args.check:
            done = applied(conn)
            pending = [p.name for p in migration_files() if p.stem.partition("_")[0] not in done]
            print("pendentes:", ", ".join(pending) or "nenhuma")
            return
        names = apply_pending(conn)
        print("aplicadas:", ", ".join(names) or "nenhuma")


if __name__ == "__main__":
    main()
