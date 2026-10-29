"""O extrator: acerta o que o vocabulário conhece e deixa sobrando o que não conhece. Nunca adivinha."""
import pytest

from pricelists.extract import extract, tokens, vocabulary
from pricelists.world import build_world
from pricelists.world import build as b
from pricelists.world.spec import WRITINGS

SEEDS = range(1, 6)


@pytest.mark.parametrize("text, expected", [
    ("YERBA TRES LUNAS SUAVE 1KG", ("yerba_mate", "tres_lunas", "mild", 1000, "g", 1)),
    ("T.LUNAS YBA MATE X 2 KG", ("yerba_mate", "tres_lunas", "traditional", 2000, "g", 1)),
    ("GALLETITAS DE AGUA EL BENTEVEO 150 G", ("crackers", "el_benteveo", "classic", 150, "g", 1)),
    ("BENTEVEO GALLET AGUA INTEG X 300 G", ("crackers", "el_benteveo", "whole_wheat", 300, "g", 1)),
    ("ACEITE GIRASOL SOLCLARO 1.5LT", ("sunflower_oil", "solclaro", "standard", 1500, "ml", 1)),
    ("LAGOMAR ATUN EN AC X 170 G", ("tuna", "lagomar", "in_oil", 170, "g", 1)),
    ("AGUA MINERAL CUMBREFRIA SIN GAS 500CC PACK X6", ("water", "cumbrefria", "still", 500, "ml", 6)),
    ("TE EN SAQUITOS VERDE VIENTOVERDE X 50 U", ("tea_bags", "vientoverde", "green", 50, "un", 1)),
    ("PAN EL BENTEVEO PANCHO X4", ("buns", "el_benteveo", "hot_dog", 4, "un", 1)),
    ("HARINA DE TRIGO 0000 GRANALBA 1 KG", ("flour", "granalba", "type_0000", 1000, "g", 1)),
])
def test_known_writings(text, expected):
    a = extract(text)
    assert (a.type_code, a.brand, a.variety, a.size, a.unit, a.pack) == expected
    assert a.leftover == ()


def test_box_and_noise_are_not_leftover():
    a = extract("CUMBRE FRIA CERV NEGRA X 473 ML LATA CAJA X 24")
    assert (a.type_code, a.brand, a.variety, a.size, a.units_per_box) == ("beer", "cumbrefria", "dark", 473, 24)
    assert a.noise == ("LATA",) and a.leftover == ()


def test_leftover_word_is_kept():
    a = extract("FIDEOS MOLINO CELESTE SPAGHETTI AL HUEVO 500GR")
    assert a.type_code == "pasta" and a.leftover == ("AL", "HUEVO")


def test_unknown_writing_is_not_guessed():
    a = extract("MYNS LAGOMAR 500GR")
    assert a.type_code is None and a.leftover == ("MYNS",)


def test_count_on_weight_type_is_not_guessed():
    a = extract("ARROZ GRANALBA X 6")
    assert a.size is None and "X6" in a.leftover


def test_vocabulary_knows_every_known_writing():
    """O contrato entre o mundo e o sistema: as escritas «conhecidas» estão no vocabulário; as outras não."""
    vocab = vocabulary()
    for supplier, w in WRITINGS.items():
        for type_code, writings in w.types.items():
            for text in writings:
                assert vocab.types.get(tuple(tokens(text))) == {type_code}, (supplier, text)
        for type_code, writings in w.unknown_types.items():
            for text in writings:
                assert tuple(tokens(text)) not in vocab.types, (supplier, text)
        for (type_code, variety), writings in w.varieties.items():
            for text in writings:
                assert variety in vocab.varieties[type_code].get(tuple(tokens(text)), set()), (supplier, text)
        for brand, writings in w.brands.items():
            for text in writings:
                assert vocab.brands.get(tuple(tokens(text))) == {brand}, (supplier, text)


@pytest.mark.parametrize("seed", SEEDS)
def test_catalog_is_read_exactly(seed):
    world = build_world(seed)
    market = world.market_by_id()
    for c in world.catalog:
        p = market[c.market_id]
        a = extract(c.description)
        assert (a.type_code, a.brand, a.variety, a.size, a.pack, a.leftover) == \
            (p.type_code, p.brand, p.variety, p.size, p.pack, ()), c.description


@pytest.mark.parametrize("seed", SEEDS)
def test_list_lines_against_answer_key(seed):
    world = build_world(seed)
    market = world.market_by_id()
    for pl in world.lists:
        for ln in pl.lines:
            p = market[ln.market_id]
            a = extract(ln.description)
            exact = ((a.type_code, a.brand, a.variety, a.size, a.pack) == (p.type_code, p.brand, p.variety, p.size,
                                                                          p.pack) and not a.leftover)
            if b.UNKNOWN_WRITING in ln.traps or p.extra:
                assert not exact, ln.description  # o que o sistema não conhece nunca sai como certo
            else:
                assert exact, ln.description
            if ln.price_per_box:
                assert a.units_per_box == ln.units_per_box
