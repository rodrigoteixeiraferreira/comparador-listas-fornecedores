"""A prova, no banco: zero par confirmado errado, nenhuma lista boa segurada, o aprendizado de um mês para o outro, e
as conferências do portão que dependem da identificação (4, 6 e 7) caindo onde devem."""
import pytest

from pricelists.audit import run_audit
from pricelists.gate import check_zero
from pricelists.load import load_catalog, pairs, process_list, seed_reference
from pricelists.pipeline import answer_from_key, reset_data, run, score, truth
from pricelists.world import build_world, write_world
from pricelists.world.corrupt import corrupt
from pricelists.world.files import write_list
from pricelists.world.spec import PERIODS

SEEDS = (1, 2, 3, 4, 5)
SUPPLIERS = ("mayorista_norte", "distribuidora_andina")


def _world(seed, tmp_path):
    world = build_world(seed)
    write_world(world, tmp_path)
    return world


@pytest.mark.parametrize("seed", SEEDS)
def test_zero_wrong_pairs_and_learning(db, tmp_path, seed):
    world = _world(seed, tmp_path)
    report = run(db, world, tmp_path, out=lambda *_: None)
    wrong = [w for r in report for w in r["score"].wrong]
    assert wrong == [], wrong  # o critério de aceite
    assert all(r["status"] == "active" for r in report), [(r["file"], r["gate"].failed) for r in report]
    # depois do revisor, outubro pergunta muito menos que setembro (nos fornecedores que mandaram os dois meses)
    review = {}
    for r in report:
        supplier, period = r["file"].rsplit(".", 1)[0].rsplit("_", 1)
        review.setdefault(supplier, {})[period] = r["score"].in_review
    both = [months for months in review.values() if set(months) == set(PERIODS)]
    assert sum(m[PERIODS[1]] for m in both) < 0.5 * sum(m[PERIODS[0]] for m in both)
    # e confirma quase tudo o que a loja tem
    assert all(r["score"].coverage >= 0.95 for r in report)
    # a foto da vitrine (semente 1) entra pela dupla leitura; as outras sementes não têm leitura gravada
    assert any(r["file"].startswith("mercantil_ombu") for r in report) == (seed == 1)


def test_audit_switches_off_and_promotes(db, tmp_path):
    """A regra experimental que erra é desligada; a que acerta com amostra suficiente é ligada; nada fica errado."""
    world = _world(1, tmp_path)
    run(db, world, tmp_path, out=lambda *_: None)
    db.execute("update public.decision_rule set mode = 'trial' where code = 'attributes'")  # volta a ser testada
    for (list_id,) in db.execute("select id from public.price_list where status = 'active'").fetchall():
        db.execute("select * from public.run_cascade(%s)", (list_id,))
    results = {r.rule: r for r in run_audit(db, answer_from_key(db, world), seed=1)}
    assert results["high_similarity"].mode_after == "off" and results["high_similarity"].errors > 0
    assert results["attributes"].mode_after == "on" and results["attributes"].errors == 0
    assert results["barcode"].errors == results["supplier_code"].errors == 0
    assert results["price_doubt_identity"].mode_after == "trial"  # amostra pequena demais para decidir
    modes = dict(db.execute("select code, mode from public.decision_rule").fetchall())
    assert modes["high_similarity"] == "off" and modes["attributes"] == "on"
    for (list_id, supplier, period) in db.execute(
            "select id, supplier_code, period from public.price_list where status = 'active'").fetchall():
        assert score(db, list_id, truth(world, supplier, period)).wrong == []


def _first_months(db, world, tmp_path):
    reset_data(db)
    seed_reference(db)
    load_catalog(db, tmp_path / "catalog.csv")
    return {pl.supplier: pl for pl in world.lists if pl.period == PERIODS[0]}, \
           {pl.supplier: pl for pl in world.lists if pl.period == PERIODS[1]}


@pytest.mark.parametrize("seed", (1, 2, 3))
@pytest.mark.parametrize("supplier", SUPPLIERS)
def test_first_list_tenfold_falls_in_check_4(db, tmp_path, seed, supplier):
    """A primeira lista do fornecedor não tem anterior para comparar: quem segura o zero a mais é o custo."""
    world = _world(seed, tmp_path)
    september, _ = _first_months(db, world, tmp_path)
    result = process_list(db, corrupt(september[supplier], "prices_x10", tmp_path / "bad", seed=seed), supplier)
    assert result["status"] == "held" and 4 in result["gate"].failed, result["gate"].checks


@pytest.mark.parametrize("seed", (1, 2, 3))
@pytest.mark.parametrize("supplier", SUPPLIERS)
def test_truncated_descriptions_fall_in_check_6(db, tmp_path, seed, supplier):
    """O arquivo chega inteiro e com os preços certos, mas as descrições cortadas: só a continuidade vê."""
    world = _world(seed, tmp_path)
    september, october = _first_months(db, world, tmp_path)
    process_list(db, write_list(september[supplier], tmp_path / "prev"), supplier)
    result = process_list(db, corrupt(october[supplier], "descriptions_truncated", tmp_path / "bad", seed=seed),
                          supplier)
    assert result["status"] == "held" and 6 in result["gate"].failed, result["gate"].checks
    still_active = db.execute("select period from public.price_list where supplier_code = %s and status = 'active'",
                              (supplier,)).fetchone()
    assert still_active == (PERIODS[0],)  # a anterior continua valendo


@pytest.mark.parametrize("seed", (1, 2, 3))
@pytest.mark.parametrize("supplier", SUPPLIERS)
def test_injected_wrong_pair_falls_in_check_7(db, tmp_path, seed, supplier):
    """Um defeito na cascata que confirmasse um par contraditório: a checagem de zero segura."""
    world = _world(seed, tmp_path)
    september, _ = _first_months(db, world, tmp_path)
    list_id = process_list(db, write_list(september[supplier], tmp_path / "prev"), supplier)["list_id"]
    assert check_zero(pairs(db, list_id)).passed
    db.execute(
        "update public.match m set product_id = other.id from public.list_line l, public.product p, "
        "lateral (select o.id from public.product o where o.size <> p.size order by o.id limit 1) other "
        "where m.list_line_id = l.id and l.price_list_id = %s and p.id = m.product_id and m.level in (2, 3) "
        "and m.list_line_id = (select min(m2.list_line_id) from public.match m2 join public.list_line l2 "
        "on l2.id = m2.list_line_id where l2.price_list_id = %s and m2.level in (2, 3))", (list_id, list_id))
    assert check_zero(pairs(db, list_id)).passed is False
