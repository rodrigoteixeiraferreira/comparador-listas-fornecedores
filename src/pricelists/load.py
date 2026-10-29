"""A carga: dados de referência, cadastro e listas. Cada lista passa pela cascata e pelo portão antes de valer.

As funções recebem a conexão e não fazem commit: quem chama decide (o ensaio desfaz tudo no fim).
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

import psycopg

from .extract import extract, tokens
from .gate import GateResult, Pair, run_gate
from .readers import ParsedList, RawLine, read_list
from .reference import DATA_DIR, Reference, load


def normalized_text(description: str) -> str:
    return " ".join(tokens(description))


def seed_reference(conn: psycopg.Connection, ref: Reference | None = None) -> None:
    ref = ref or load()
    with conn.cursor() as cur:
        cur.executemany(
            "insert into public.section (code, name_es, name_pt, name_en) values (%s, %s, %s, %s) "
            "on conflict (code) do update set name_es = excluded.name_es, name_pt = excluded.name_pt, "
            "name_en = excluded.name_en",
            [(s.code, s.name_es, s.name_pt, s.name_en) for s in ref.sections.values()])
        cur.executemany(
            "insert into public.product_type (code, section_code, unit, name_es, name_pt, name_en) "
            "values (%s, %s, %s, %s, %s, %s) on conflict (code) do update set section_code = excluded.section_code, "
            "unit = excluded.unit, name_es = excluded.name_es, name_pt = excluded.name_pt, name_en = excluded.name_en",
            [(t.code, t.section, t.unit, t.name_es, t.name_pt, t.name_en) for t in ref.types.values()])
        cur.executemany(
            "insert into public.variety (type_code, code, is_default, name_es, name_pt, name_en) "
            "values (%s, %s, %s, %s, %s, %s) on conflict (type_code, code) do update set "
            "is_default = excluded.is_default, name_es = excluded.name_es, name_pt = excluded.name_pt, "
            "name_en = excluded.name_en",
            [(v.type_code, v.code, v.is_default, v.name_es, v.name_pt, v.name_en)
             for vs in ref.varieties.values() for v in vs])
        cur.executemany(
            "insert into public.brand (code, name, display) values (%s, %s, %s) "
            "on conflict (code) do update set name = excluded.name, display = excluded.display",
            [(b.code, b.name, b.display) for b in ref.brands.values()])
        cur.executemany(
            "insert into public.supplier (code, name, file_format, prices_include_vat) values (%s, %s, %s, %s) "
            "on conflict (code) do update set name = excluded.name, file_format = excluded.file_format, "
            "prices_include_vat = excluded.prices_include_vat",
            [(s.code, s.name, s.file_format, s.prices_include_vat) for s in ref.suppliers.values()])
        with open(DATA_DIR / "vocabulary.csv", encoding="utf-8", newline="") as f:
            terms = [(r["kind"], " ".join(tokens(r["term"])), r["canonical"] or None, r["type_code"] or None)
                     for r in csv.DictReader(f)]
        cur.executemany(
            "insert into public.vocabulary_term (kind, term, canonical, type_code) values (%s, %s, %s, %s) "
            "on conflict (kind, term, canonical, type_code) do nothing", terms)


def load_catalog(conn: psycopg.Connection, catalog_csv: Path) -> int:
    """O cadastro da loja: cada produto com os atributos que o extrator lê na descrição."""
    with open(catalog_csv, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    params = []
    for r in rows:
        a = extract(r["description"])
        params.append((int(r["product_id"]), r["barcode"] or None, r["description"], r["cost"] or None,
                       normalized_text(r["description"]), a.type_code, a.brand, a.variety, a.size, a.unit, a.pack,
                       sorted(a.leftover)))
    with conn.cursor() as cur:
        cur.executemany(
            "insert into public.product (id, barcode, description, cost, normalized_text, type_code, brand_code, "
            "variety_code, size, unit, pack, leftover) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "on conflict (id) do update set barcode = excluded.barcode, description = excluded.description, "
            "cost = excluded.cost, normalized_text = excluded.normalized_text, type_code = excluded.type_code, "
            "brand_code = excluded.brand_code, variety_code = excluded.variety_code, size = excluded.size, "
            "unit = excluded.unit, pack = excluded.pack, leftover = excluded.leftover, updated_at = now()", params)
    return len(params)


def insert_list(conn: psycopg.Connection, parsed: ParsedList, supplier: str, period: str | None = None) -> int:
    """Grava a lista como «pending», com o que o extrator leu em cada linha."""
    default_vat = conn.execute("select prices_include_vat from public.supplier where code = %s",
                               (supplier,)).fetchone()[0]
    vat = parsed.vat_included if parsed.vat_included is not None else default_vat
    list_id = conn.execute(
        "insert into public.price_list (supplier_code, period, file_name, file_sha256, file_format, vat_included) "
        "values (%s, %s, %s, %s, %s, %s) returning id",
        (supplier, period or parsed.period, parsed.path.name, parsed.sha256, parsed.file_format, vat)).fetchone()[0]
    params = []
    for ln in parsed.lines:
        a = extract(ln.description)
        params.append((list_id, ln.row, ln.supplier_code, ln.barcode or None, ln.description,
                       normalized_text(ln.description), ln.price, ln.case_units, ln.section, a.type_code, a.brand,
                       a.variety, a.size, a.unit, a.pack, a.units_per_box, sorted(a.leftover), list(a.noise),
                       list(a.ambiguous)))
    with conn.cursor() as cur:
        cur.executemany(
            "insert into public.list_line (price_list_id, source_row, item_code, barcode, description, "
            "normalized_text, price, case_units, section, type_code, brand_code, variety_code, size, unit, pack, "
            "units_per_box, leftover, noise, ambiguous) "
            "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", params)
    return list_id


def run_cascade(conn: psycopg.Connection, list_id: int) -> dict[str, int]:
    return dict(conn.execute("select cascade_step, matched from public.run_cascade(%s)", (list_id,)).fetchall())


def pairs(conn: psycopg.Connection, list_id: int) -> list[Pair]:
    rows = conn.execute(
        "select item_code, product_id, confirmed, coalesce(compatible, true), unit_price, cost, level, reason "
        "from public.line_pair where price_list_id = %s", (list_id,)).fetchall()
    return [Pair(r[0], r[1], r[2], r[3], float(r[4]) if r[4] is not None else None,
                 float(r[5]) if r[5] is not None else None, r[6], r[7]) for r in rows]


def lines_as_parsed(conn: psycopg.Connection, list_id: int) -> ParsedList:
    """A lista gravada, na forma que o portão compara (para a anterior, que não se relê do arquivo)."""
    meta = conn.execute("select file_name, file_sha256, file_format, period, vat_included from public.price_list "
                        "where id = %s", (list_id,)).fetchone()
    parsed = ParsedList(Path(meta[0]), meta[2], meta[1], meta[3], meta[4])
    for r in conn.execute("select source_row, item_code, coalesce(barcode, ''), description, price, case_units, "
                          "section from public.list_line where price_list_id = %s order by source_row", (list_id,)):
        parsed.lines.append(RawLine(r[0], r[1], r[2], r[3], float(r[4]) if r[4] is not None else None, r[5], r[6]))
    return parsed


def active_list(conn: psycopg.Connection, supplier: str) -> int | None:
    row = conn.execute("select id from public.price_list where supplier_code = %s and status = 'active'",
                       (supplier,)).fetchone()
    return row[0] if row else None


def decide(conn: psycopg.Connection, list_id: int, supplier: str, result: GateResult) -> str:
    """Passou: a nova vale e a anterior fica «replaced». Não passou: «held», e a anterior continua valendo."""
    gate = json.dumps([asdict(c) for c in result.checks], ensure_ascii=False)
    if result.passed:
        conn.execute("update public.price_list set status = 'replaced' where supplier_code = %s and status = 'active'",
                     (supplier,))
        status = "active"
    else:
        status = "held"
    conn.execute("update public.price_list set status = %s, gate = %s, decided_at = now() where id = %s",
                 (status, gate, list_id))
    return status


def process_list(conn: psycopg.Connection, path: Path, supplier: str) -> dict:
    """Uma lista do começo ao fim: leitura, gravação em espera, cascata, portão e decisão."""
    parsed = read_list(path)
    previous_id = active_list(conn, supplier)
    list_id = insert_list(conn, parsed, supplier)
    steps = run_cascade(conn, list_id)
    previous = lines_as_parsed(conn, previous_id) if previous_id else None
    result = run_gate(parsed, previous, pairs(conn, list_id), pairs(conn, previous_id) if previous_id else None)
    status = decide(conn, list_id, supplier, result)
    return {"list_id": list_id, "file": path.name, "status": status, "steps": steps, "gate": result}
