"""O portão: nenhuma lista boa é segurada, e cada corrupção cai na conferência certa."""
import pytest

from pricelists.gate import Pair, check_continuity, check_price_vs_cost, check_zero, run_file_checks
from pricelists.readers import read_list
from pricelists.reference import load
from pricelists.world import build_world
from pricelists.world.corrupt import CORRUPTIONS, FILE_CHECKS, corrupt
from pricelists.world.files import write_list

SEEDS = (1, 2, 3)


def _months(world, supplier):
    return [pl for pl in world.lists if pl.supplier == supplier]


def _cases():
    ref = load()
    for seed in SEEDS:
        for supplier in ("mayorista_norte", "distribuidora_andina"):
            fmt = ref.suppliers[supplier].file_format
            for c in CORRUPTIONS:
                if fmt in c.formats and c.expected_check in FILE_CHECKS:
                    yield pytest.param(seed, supplier, c, id=f"{seed}-{supplier}-{c.code}")


@pytest.fixture(scope="module")
def worlds():
    return {seed: build_world(seed) for seed in SEEDS}


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("supplier", ("mayorista_norte", "distribuidora_andina"))
def test_good_lists_pass(worlds, tmp_path, seed, supplier):
    sep, oct_ = _months(worlds[seed], supplier)
    previous = read_list(write_list(sep, tmp_path / "prev"))
    new = read_list(write_list(oct_, tmp_path / "new"))
    first = run_file_checks(previous, None)  # a primeira lista: sem anterior, só as conferências do arquivo
    assert first.passed, first.checks
    result = run_file_checks(new, previous)
    assert result.passed, result.checks


@pytest.mark.parametrize("seed, supplier, corruption", list(_cases()))
def test_corruption_falls_in_the_right_check(worlds, tmp_path, seed, supplier, corruption):
    sep, oct_ = _months(worlds[seed], supplier)
    previous = read_list(write_list(sep, tmp_path / "prev"))
    new = read_list(corrupt(oct_, corruption.code, tmp_path / "bad", seed=seed))
    result = run_file_checks(new, previous)
    assert corruption.expected_check in result.failed, (corruption.what, result.checks)


def _pair(code, product, confirmed=True, compatible=True, price=100.0, cost=100.0):
    return Pair(code, product, confirmed, compatible, price, cost)


def test_price_vs_cost():
    good = [_pair(str(i), i, price=100 + i, cost=100) for i in range(10)]
    assert check_price_vs_cost(good).passed
    tenfold = [_pair(str(i), i, price=1000 + i, cost=100) for i in range(10)]
    assert check_price_vs_cost(tenfold).passed is False
    assert check_price_vs_cost(good[:3]).passed is None  # poucos pares: não se aplica


def test_continuity():
    before = [_pair(str(i), i) for i in range(20)]
    assert check_continuity(before[:19], before).passed  # 95%
    assert check_continuity(before[:13], before).passed is False  # 65%
    assert check_continuity(before, None).passed is None


def test_zero_check():
    pairs = [_pair(str(i), i) for i in range(5)]
    assert check_zero(pairs).passed
    assert check_zero(pairs + [_pair("x", 9, compatible=False, confirmed=False)]).passed  # em revisão: não conta
    assert check_zero(pairs + [_pair("x", 9, compatible=False)]).passed is False
