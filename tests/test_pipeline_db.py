"""A prova, no banco: zero par confirmado errado, nenhuma lista boa segurada, o aprendizado de um mês para o outro, e
as conferências do portão que dependem da identificação (4, 6 e 7) caindo onde devem."""
import pytest

from pricelists.gate import check_zero
from pricelists.load import load_catalog, pairs, process_list, seed_reference
from pricelists.pipeline import reset_data, run
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
    by_period = {(r["file"].rsplit("_", 1)[1][:7]): [] for r in report}
    for r in report:
        by_period[r["file"].rsplit("_", 1)[1][:7]].append(r["score"])
    september, october = (by_period[p] for p in PERIODS)
    # depois do revisor, outubro pergunta muito menos que setembro
    assert sum(s.in_review for s in october) < 0.5 * sum(s.in_review for s in september)
    # e confirma quase tudo o que a loja tem
    assert all(s.coverage >= 0.95 for s in september + october)


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
