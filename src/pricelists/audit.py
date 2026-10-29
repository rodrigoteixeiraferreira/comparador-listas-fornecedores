"""A auditoria por amostra: mede a taxa de erro de cada tipo de decisão automática e decide se ele segue sozinho.

As regras são combinadas antes do sorteio e não mudam durante a rodada:

1. por regra ligada ou em teste, uma amostra sorteada com semente fixa, congelada antes da primeira resposta;
2. alguém responde cada item: «certo» ou «errado» (aqui, o auditor simulado, que responde pelo gabarito);
3. a taxa é por regra, com o limite superior de 95% (Clopper-Pearson, unilateral);
4. a regra cuja taxa observada passa de 2% é desligada. O limite largo de uma amostra pequena não desliga nada;
5. a regra em teste com taxa observada até 2% e pelo menos 20 itens na amostra é ligada. Com menos, segue em teste.
"""
from __future__ import annotations

import json
import random
from collections.abc import Callable
from dataclasses import asdict, dataclass
from math import comb

import psycopg

from .load import run_cascade

ERROR_LIMIT = 0.02
MIN_SAMPLE_TO_PROMOTE = 20


def upper_bound(errors: int, n: int, confidence: float = 0.95) -> float:
    """O maior erro real compatível com o que a amostra viu: P(X <= errors | n, p) = 1 - confiança."""
    if n == 0 or errors >= n:
        return 1.0
    alpha = 1 - confidence
    lo, hi = errors / n, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        cdf = sum(comb(n, k) * mid ** k * (1 - mid) ** (n - k) for k in range(errors + 1))
        lo, hi = (mid, hi) if cdf > alpha else (lo, mid)
    return hi


@dataclass(frozen=True)
class RuleResult:
    rule: str
    mode_before: str
    population: int
    sample: int
    errors: int
    observed: float
    upper_95: float
    mode_after: str


def decide(mode: str, sample: int, errors: int) -> str:
    observed = errors / sample if sample else 0.0
    if sample and observed > ERROR_LIMIT:
        return "off"
    if mode == "trial" and sample >= MIN_SAMPLE_TO_PROMOTE:
        return "on"
    return mode


def run_audit(conn: psycopg.Connection, answer: Callable[[int, int], bool], seed: int = 1,
              sample_per_rule: int = 50, answered_by: str = "auditor simulado") -> list[RuleResult]:
    """Uma rodada sobre as listas que valem. `answer(list_line_id, product_id)` diz se o par está certo."""
    round_id = conn.execute("insert into public.audit_round (seed, sample_per_rule, error_limit) values (%s, %s, %s) "
                            "returning id", (seed, sample_per_rule, ERROR_LIMIT)).fetchone()[0]
    rules = conn.execute("select code, mode from public.decision_rule where mode <> 'off' order by code").fetchall()
    rng = random.Random(f"audit:{seed}")
    frozen: dict[str, list[tuple[int, int]]] = {}
    population: dict[str, int] = {}
    for rule, mode in rules:
        # ligada: os pares que ela confirmou; em teste: as decisões que ela tomaria (deixadas no nível 4)
        rows = conn.execute(
            "select m.list_line_id, m.product_id from public.match m "
            "join public.list_line l on l.id = m.list_line_id "
            "join public.price_list pl on pl.id = l.price_list_id "
            "where pl.status = 'active' and m.rule_code = %s and (case when %s = 'on' then m.confirmed "
            "else m.level = 4 end) order by m.list_line_id", (rule, mode)).fetchall()
        population[rule] = len(rows)
        frozen[rule] = rng.sample(rows, min(sample_per_rule, len(rows)))
        with conn.cursor() as cur:
            cur.executemany("insert into public.audit_item (round_id, list_line_id, product_id, rule_code) "
                            "values (%s, %s, %s, %s)", [(round_id, line, product, rule)
                                                        for line, product in frozen[rule]])
    # a amostra está congelada; agora as respostas
    results = []
    for rule, mode in rules:
        errors = 0
        for line, product in frozen[rule]:
            right = answer(line, product)
            errors += not right
            conn.execute("update public.audit_item set answer = %s, answered_by = %s, answered_at = now() "
                         "where round_id = %s and list_line_id = %s",
                         ("right" if right else "wrong", answered_by, round_id, line))
        n = len(frozen[rule])
        after = decide(mode, n, errors)
        results.append(RuleResult(rule, mode, population[rule], n, errors, round(errors / n, 4) if n else 0.0,
                                  round(upper_bound(errors, n), 4), after))
    for r in results:
        if r.mode_after != r.mode_before:
            conn.execute("update public.decision_rule set mode = %s, changed_at = now(), evidence = %s "
                         "where code = %s", (r.mode_after, json.dumps(asdict(r)), r.rule))
    conn.execute("update public.audit_round set finished_at = now(), result = %s where id = %s",
                 (json.dumps([asdict(r) for r in results]), round_id))
    # o que mudou de modo vale já: a cascata roda de novo nas listas que valem
    for (list_id,) in conn.execute("select id from public.price_list where status = 'active' order by id").fetchall():
        run_cascade(conn, list_id)
    return results
