"""A conta da auditoria, a regra que liga e desliga, e a dupla leitura da foto (com as leituras gravadas)."""
import pytest

from pricelists.ai_reader import compare, double_read
from pricelists.audit import decide, upper_bound
from pricelists.world import build_world, write_world
from pricelists.world.photo import SHOWCASE


def test_upper_bound():
    assert upper_bound(0, 50) == pytest.approx(1 - 0.05 ** (1 / 50), abs=1e-6)  # 5,8%
    assert upper_bound(1, 145) == pytest.approx(0.0326, abs=0.0005)  # um erro em 145: até ~3%
    assert upper_bound(0, 0) == 1.0
    assert upper_bound(3, 3) == 1.0


@pytest.mark.parametrize("mode, sample, errors, after", [
    ("on", 50, 0, "on"),
    ("on", 50, 2, "off"),  # 4% observado: desliga
    ("on", 50, 1, "on"),  # 2% observado: no limite, segue
    ("trial", 40, 0, "on"),  # a amostra promove
    ("trial", 1, 0, "trial"),  # amostra pequena não decide
    ("trial", 18, 18, "off"),  # erro de verdade desliga, mesmo com amostra pequena
    ("on", 0, 0, "on"),
])
def test_decide(mode, sample, errors, after):
    assert decide(mode, sample, errors) == after


def _reading(*lines):
    return {"header": [], "lines": [dict(code=c, description=d, price=p, section="", doubt=doubt)
                                    for c, d, p, doubt in lines]}


def test_compare_keeps_only_what_both_read_alike():
    a = _reading(("1", "Yerba Tres Lunas 1 kg", "4.739,11", False), ("2", "Arroz Granalba 1 kg", "1.870,43", False),
                 ("3", "Te Vientoverde x 50 u", "3.512,38", False), ("4", "Cerveza Cumbrefria 1 L", "3.115,51", True),
                 ("5", "Pan El Benteveo Pancho x 6 u", "2.073,56", False))
    b = _reading(("1", "YERBA TRES LUNAS 1 KG", "4.739,11", False), ("2", "Arroz Granalba 1 kg", "1.870,48", False),
                 ("3", "Te Vientoverde x 30 u", "3.512,38", False), ("4", "Cerveza Cumbrefria 1 L", "3.115,51", False))
    agreed, disagreements = compare(a, b)
    assert [x["code"] for x, _ in agreed] == ["1"]  # a caixa alta não é discordância; o resto é
    assert {d.item_code: d.why for d in disagreements} == {"2": "price", "3": "description", "4": "doubt",
                                                           "5": "only_one_reading"}


def test_showcase_photo_double_reading(tmp_path):
    world = build_world(1)
    write_world(world, tmp_path)
    photo = tmp_path / "lists" / "mercantil_ombu_2026-10.jpg"
    assert photo.read_bytes() == (SHOWCASE / photo.name).read_bytes()  # a vitrine sai com os mesmos bytes
    parsed = double_read(photo)
    truth = next(pl for pl in world.lists if pl.supplier == "mercantil_ombu")
    assert parsed.period == "2026-10" and parsed.vat_included is True
    assert parsed.disagreements == [] and parsed.counted == len(truth.lines)
    got = {ln.supplier_code: (ln.description, ln.price) for ln in parsed.lines}
    assert got == {ln.supplier_code: (ln.description, ln.price) for ln in truth.lines}


def test_other_seeds_have_no_recorded_reading(tmp_path):
    world = build_world(2)
    write_world(world, tmp_path)
    with pytest.raises(FileNotFoundError):
        double_read(tmp_path / "lists" / "mercantil_ombu_2026-10.jpg")
