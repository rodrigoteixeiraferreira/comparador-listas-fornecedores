"""O painel, no banco: as views dão as mesmas contas do processamento, os três botões da revisão gravam como o revisor
simulado, e só para quem fez login; sem login, nada se lê nem se grava."""
import json
from contextlib import contextmanager

import psycopg
import pytest

from pricelists.audit import run_audit
from pricelists.pipeline import answer_from_key, run, score, truth
from pricelists.world import build_world, write_world

USER = {"sub": "00000000-0000-0000-0000-000000000042", "email": "revisor@demo.test", "role": "authenticated"}


@pytest.fixture
def loaded(db, tmp_path):
    world = build_world(1)
    write_world(world, tmp_path)
    run(db, world, tmp_path, out=lambda *_: None)
    return world


@contextmanager
def as_role(db, role, claims=None):
    """Como a API entraria: o papel do Postgres e as claims do JWT, só dentro do bloco."""
    with db.transaction():
        db.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims or {}),))
        db.execute(f"set local role {role}")
        yield
        db.execute("reset role")


def denied(db, sql, params=()):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.transaction():
            db.execute(sql, params)


def test_views_match_the_processing(db, loaded):
    status = db.execute("select products, with_supplier, confirmed, contradictions, in_review, compared "
                        "from public.base_status").fetchone()
    products, with_supplier, confirmed, contradictions, in_review, compared = status
    assert products == db.execute("select count(*) from public.product where active").fetchone()[0]
    assert with_supplier == db.execute("select count(distinct product_id) from public.offer").fetchone()[0]
    assert contradictions == 0  # o critério de aceite, contado pela view
    lists = db.execute("select sum(confirmed), sum(in_review + unmatched) from public.list_summary "
                       "where status = 'active'").fetchone()
    assert (confirmed, in_review) == lists
    assert compared == db.execute("select count(*) from public.product_comparison where offers >= 2").fetchone()[0]
    # o melhor preço de cada produto é a oferta de price_rank 1, e nenhuma oferta com o preço em dúvida disputa
    mismatched = db.execute(
        "select count(*) from public.product_overview p join public.comparison_offer o "
        "on o.product_id = p.product_id and o.price_rank = 1 where o.unit_price <> p.best_price").fetchone()[0]
    assert mismatched == 0
    assert db.execute("select count(*) from public.comparison_offer "
                      "where not price_ok and price_rank is not null").fetchone()[0] == 0
    # cada linha da fila tem a proposta da cascata em primeiro, quando há proposta
    assert db.execute("select count(*) from public.review_queue q join public.review_option o "
                      "on o.list_line_id = q.list_line_id and o.position = 1 "
                      "where q.proposed_product_id is not null and not o.proposed").fetchone()[0] == 0
    # a auditoria: cada regra mostra o modo de agora e a amostra que a julgou
    results = {r.rule: r for r in run_audit(db, answer_from_key(db, loaded), seed=1)}
    for code, mode, sample, errors in db.execute(
            "select code, mode, sample, errors from public.rule_status").fetchall():
        assert (mode, sample, errors) == (results[code].mode_after, results[code].sample, results[code].errors)
    assert results["high_similarity"].mode_after == "off"


def test_review_buttons_record_like_the_reviewer(db, loaded):
    queue = db.execute("select q.list_line_id, q.supplier_code, q.period, q.item_code, q.reason "
                       "from public.review_queue q order by q.list_line_id").fetchall()
    assert queue
    with as_role(db, "authenticated", USER):
        # «não é» na proposta de uma linha que a loja não tem: a proposta some das opções dessa linha
        line, supplier, period, code, _ = next(r for r in queue if truth(loaded, r[1], r[2]).get(r[3]) is None)
        proposed = db.execute("select product_id from public.review_option where list_line_id = %s and position = 1",
                              (line,)).fetchone()[0]
        db.execute("select public.review_reject(%s, %s)", (line, proposed))
        options = {r[0] for r in db.execute("select product_id from public.review_option where list_line_id = %s",
                                            (line,)).fetchall()}
        assert proposed not in options
        # depois, cada linha recebe a resposta do gabarito: «é este» ou «a loja não tem»
        for line, supplier, period, code, _ in queue:
            want = truth(loaded, supplier, period).get(code)
            if want is None:
                db.execute("select public.review_not_carried(%s)", (line,))
            else:
                db.execute("select public.review_confirm(%s, %s)", (line, want))
        assert db.execute("select count(*) from public.review_queue").fetchone()[0] == 0
        assert db.execute("select in_review, contradictions from public.base_status").fetchone() == (0, 0)
    # quem decidiu fica gravado, e nenhuma lista ativa ficou com par errado
    by = {r[0] for r in db.execute(
        "select distinct e.decided_by from public.equivalence e "
        "join public.list_line l on l.normalized_text = e.normalized_text "
        "join public.price_list pl on pl.id = l.price_list_id and pl.supplier_code = e.supplier_code "
        "where l.id = any(%s)", ([r[0] for r in queue],)).fetchall()}
    assert by == {USER["email"]}
    for list_id, supplier, period in db.execute(
            "select id, supplier_code, period from public.price_list where status = 'active'").fetchall():
        assert score(db, list_id, truth(loaded, supplier, period)).wrong == []
    # a linha do preço longe do custo: identificada pela pessoa, mas fora da disputa até alguém conferir o preço
    far = [r[0] for r in queue if r[4] == "price_far_from_cost"]
    for line in far:
        assert db.execute("select level, price_ok from public.comparison_offer where list_line_id = %s",
                          (line,)).fetchone() == (1, False)


def test_without_login_nothing_is_read_or_written(db, loaded):
    line = db.execute("select list_line_id from public.review_queue limit 1").fetchone()[0]
    with as_role(db, "anon"):
        denied(db, "select count(*) from public.product")
        denied(db, "select count(*) from public.base_status")
        denied(db, "select public.review_not_carried(%s)", (line,))
    with as_role(db, "authenticated", {"role": "authenticated"}):  # o papel sem usuário não decide
        denied(db, "select public.review_not_carried(%s)", (line,))
    with as_role(db, "authenticated", USER):
        assert db.execute("select products from public.base_status").fetchone()[0] > 0
        denied(db, "insert into public.equivalence (supplier_code, normalized_text, decided_by) "
                   "values ('mayorista_norte', 'X', 'x')")
        denied(db, "update public.product set cost = 1")
        denied(db, "select * from public.run_cascade(1)")
        denied(db, "select private.reviewer()")
