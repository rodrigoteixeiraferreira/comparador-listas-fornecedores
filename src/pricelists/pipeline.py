"""O processamento inteiro de um mundo fictício, conferido contra o gabarito.

    python -m pricelists.pipeline --seed 1             gera, carrega e grava no banco
    python -m pricelists.pipeline --seed 1 --dry-run   faz tudo numa transação e desfaz no fim

Setembro entra, o revisor simulado responde as dúvidas (com o gabarito: uma pessoa que não erra), e outubro entra
usando o que se aprendeu. Para cada lista: o portão, a cascata e a conta que importa, pares confirmados errados.
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from .ai_reader import has_reading
from .audit import run_audit
from .db import ROOT, connect
from .load import load_catalog, process_list, run_cascade, seed_reference
from .migrate import apply_pending
from .reference import load
from .world import World, build_world, write_world
from .world.spec import PERIODS, SCHEDULE

DATA_TABLES = ("audit_item", "audit_round", "reading_disagreement", "candidate", "match", "list_line", "price_list",
               "equivalence", "rejection", "product")
REVIEWER = "revisor simulado"


@dataclass
class Score:
    """A lista conferida contra o gabarito."""

    lines: int = 0
    store_has: int = 0  # linhas cujo produto a loja tem no cadastro
    confirmed: int = 0
    wrong: list[tuple] = field(default_factory=list)  # pares confirmados errados: (código, descrição, par, certo)
    in_review: int = 0
    not_carried: int = 0  # uma pessoa já disse que a loja não tem
    unmatched: int = 0
    missed: int = 0  # a loja tem o produto e o par não foi confirmado

    @property
    def coverage(self) -> float:
        return (self.confirmed - len(self.wrong)) / self.store_has if self.store_has else 0.0


def _list_key(conn: psycopg.Connection, list_id: int) -> tuple[str, str]:
    return conn.execute("select supplier_code, period from public.price_list where id = %s", (list_id,)).fetchone()


def truth(world: World, supplier: str, period: str) -> dict[str, int | None]:
    pl = next(p for p in world.lists if p.supplier == supplier and p.period == period)
    return {ln.supplier_code: ln.catalog_id for ln in pl.lines}


def score(conn: psycopg.Connection, list_id: int, answer: dict[str, int | None]) -> Score:
    s = Score()
    rows = conn.execute("select l.item_code, l.description, m.product_id, m.level, "
                        "public.is_not_carried(pl.supplier_code, l.normalized_text) from public.list_line l "
                        "join public.price_list pl on pl.id = l.price_list_id "
                        "left join public.match m on m.list_line_id = l.id where l.price_list_id = %s",
                        (list_id,)).fetchall()
    for code, description, product, level, not_carried in rows:
        want = answer.get(code)
        s.lines += 1
        s.store_has += want is not None
        if level is not None and level <= 3:
            s.confirmed += 1
            if product != want:
                s.wrong.append((code, description, product, want))
        else:
            s.in_review += level == 4
            s.not_carried += level is None and not_carried
            s.unmatched += level is None and not not_carried
            s.missed += want is not None
    return s


def simulate_review(conn: psycopg.Connection, list_id: int, answer: dict[str, int | None]) -> int:
    """O revisor responde cada dúvida da lista. Grava o «é» e o «não é», e a cascata roda de novo."""
    supplier = conn.execute("select supplier_code from public.price_list where id = %s", (list_id,)).fetchone()[0]
    doubts = conn.execute("select l.item_code, l.normalized_text, m.product_id from public.list_line l "
                          "left join public.match m on m.list_line_id = l.id "
                          "where l.price_list_id = %s and (m.level = 4 or m.level is null)", (list_id,)).fetchall()
    decisions = 0
    for code, text, proposed in doubts:
        want = answer.get(code)
        # «é este», ou «não é nenhum do cadastro» (want vazio): a loja não tem, e a linha não volta à revisão
        conn.execute("insert into public.equivalence (supplier_code, normalized_text, product_id, decided_by) "
                     "values (%s, %s, %s, %s) on conflict do nothing", (supplier, text, want, REVIEWER))
        decisions += 1
        if proposed is not None and proposed != want:
            conn.execute("insert into public.rejection (supplier_code, normalized_text, product_id, reason, "
                         "decided_by) values (%s, %s, %s, %s, %s) on conflict do nothing",
                         (supplier, text, proposed, "not_the_same_product", REVIEWER))
            decisions += 1
    run_cascade(conn, list_id)
    return decisions


def reset_data(conn: psycopg.Connection) -> None:
    """Apaga os dados e devolve as regras ao modo de partida (as duas experimentais em teste)."""
    conn.execute("truncate " + ", ".join(f"public.{t}" for t in DATA_TABLES) + " restart identity cascade")
    conn.execute("update public.decision_rule set mode = case when code in ('price_doubt_identity', "
                 "'high_similarity') then 'trial' else 'on' end, evidence = null, changed_at = now()")


def run(conn: psycopg.Connection, world: World, folder: Path, review: bool = True, out=print) -> list[dict]:
    """Carrega o mundo no banco (dentro da transação de quem chama) e devolve o relatório de cada lista."""
    reset_data(conn)
    seed_reference(conn)
    load_catalog(conn, folder / "catalog.csv")
    ref = load()
    report = []
    for i, period in enumerate(PERIODS):
        if i > 0 and review:
            for (list_id, supplier) in conn.execute(
                    "select id, supplier_code from public.price_list where period = %s and status = 'active' "
                    "order by id", (PERIODS[i - 1],)).fetchall():
                n = simulate_review(conn, list_id, truth(world, supplier, PERIODS[i - 1]))
                out(f"  revisão de {supplier} {PERIODS[i - 1]}: {n} decisões gravadas")
        for supplier, plan in SCHEDULE.items():
            if period not in plan["periods"]:
                continue
            path = folder / "lists" / f"{supplier}_{period}.{ref.suppliers[supplier].extension}"
            if ref.suppliers[supplier].file_format == "image" and not has_reading(path):
                out(f"  {path.name}: sem leitura de IA gravada para esta foto (só a vitrine, semente 1, tem); pulada")
                continue
            result = process_list(conn, path, supplier)
            result["score"] = score(conn, result["list_id"], truth(world, supplier, period))
            report.append(result)
            _print_list(result, out)
    return report


def answer_from_key(conn: psycopg.Connection, world: World) -> Callable[[int, int], bool]:
    """O auditor simulado: responde cada item da amostra pelo gabarito, como uma pessoa que não erra."""
    def answer(list_line_id: int, product_id: int) -> bool:
        supplier, period, code = conn.execute(
            "select pl.supplier_code, pl.period, l.item_code from public.list_line l "
            "join public.price_list pl on pl.id = l.price_list_id where l.id = %s", (list_line_id,)).fetchone()
        return truth(world, supplier, period).get(code) == product_id
    return answer


def print_audit(results, out=print) -> None:
    out("  auditoria por amostra (limite: 2% de erro observado):")
    for r in results:
        change = "" if r.mode_after == r.mode_before else f" -> {r.mode_after.upper()}"
        out(f"    {r.rule:22} {r.mode_before:5}{change:7} amostra {r.sample:3} de {r.population:3}; erros {r.errors}; "
            f"observado {r.observed:.1%}; até {r.upper_95:.1%} com 95% de confiança")


def _print_list(r: dict, out) -> None:
    s: Score = r["score"]
    gate = r["gate"]
    checks = " ".join(f"{c.number}{'✓' if c.passed else ('·' if c.passed is None else '✗')}" for c in gate.checks)
    out(f"  {r['file']}: {r['status']} | portão {checks}")
    out(f"    {s.lines} linhas; a loja tem {s.store_has}; confirmadas {s.confirmed} "
        f"({s.coverage:.0%} do que a loja tem); em revisão {s.in_review}; a loja não tem (decidido) "
        f"{s.not_carried}; sem dono {s.unmatched}; PARES ERRADOS {len(s.wrong)}")
    for c in gate.checks:
        if c.passed is False:
            out(f"    portão {c.number} ({c.code}) segurou: {c.measured}")
    out("    cascata: " + ", ".join(f"{k} {v}" for k, v in r["steps"].items()))
    for code, description, got, want in s.wrong:
        out(f"    ERRADO {code} {description!r}: deu {got}, o certo é {want}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # o terminal do Windows redirecionado não é UTF-8
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true", help="faz tudo numa transação e desfaz no fim")
    parser.add_argument("--no-review", action="store_true", help="sem o revisor simulado entre os meses")
    parser.add_argument("--no-audit", action="store_true", help="sem a auditoria por amostra no fim")
    args = parser.parse_args()
    folder = ROOT / "generated" / f"seed-{args.seed}"
    world = build_world(args.seed)
    write_world(world, folder)
    with connect() as conn:
        if args.dry_run:
            applied = apply_pending(conn, record=False)
            if applied:
                print("ensaio com as migrações ainda não aplicadas:", ", ".join(applied))
        print(f"semente {args.seed}: {len(world.catalog)} produtos no cadastro")
        report = run(conn, world, folder, review=not args.no_review)
        wrong = sum(len(r["score"].wrong) for r in report)
        print(f"pares confirmados errados, todas as listas: {wrong}")
        if not args.no_audit:
            print_audit(run_audit(conn, answer_from_key(conn, world), seed=args.seed))
            after = sum(len(score(conn, r["list_id"], truth(world, *_list_key(conn, r["list_id"]))).wrong)
                        for r in report if r["status"] == "active")
            print(f"  depois da auditoria, pares confirmados errados nas listas que valem: {after}")
        if args.dry_run:
            conn.rollback()
            print("ensaio: tudo desfeito")


if __name__ == "__main__":
    main()
