"""Os leitores: cada linha do arquivo sai com o código, a descrição e o preço que o gabarito diz."""
import pytest

from pricelists.readers import parse_ars, read_list
from pricelists.world import build_world, write_world


@pytest.fixture(scope="module")
def world_on_disk(tmp_path_factory):
    out = tmp_path_factory.mktemp("seed-3")
    world = build_world(3)
    write_world(world, out)
    return world, out


def test_parse_ars():
    assert parse_ars("4.850,00") == 4850.0
    assert parse_ars("15.911,74") == 15911.74
    assert parse_ars("699,46") == 699.46


def test_every_line_is_read(world_on_disk):
    world, out = world_on_disk
    for pl in world.lists:
        ext = "xlsx" if pl.supplier == "mayorista_norte" else "pdf"
        parsed = read_list(out / "lists" / f"{pl.name}.{ext}")
        assert parsed.period == pl.period
        assert parsed.vat_included == pl.prices_include_vat
        assert len(parsed.lines) == len(pl.lines)
        for got, want in zip(parsed.lines, pl.lines):
            assert got.supplier_code == want.supplier_code
            assert got.description == want.description
            assert got.price == pytest.approx(want.price, abs=0.005)
            assert got.barcode == want.barcode
        if ext == "xlsx":
            assert set(parsed.columns) == {"section", "code", "barcode", "description", "case_units", "price"}
            assert [ln.case_units for ln in parsed.lines] == [ln.units_per_box for ln in pl.lines]


def test_photo_has_no_reader_yet(tmp_path):
    with pytest.raises(ValueError):
        read_list(tmp_path / "lista.jpg")
