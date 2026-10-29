"""Os dados de referência do sistema (pasta data/): seções, tipos de produto, variedades, marcas e fornecedores.

É o que o sistema sabe de antemão, nos três idiomas da tela. O gerador do mundo fictício e o extrator leem daqui.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@dataclass(frozen=True)
class Section:
    code: str
    name_es: str
    name_pt: str
    name_en: str


@dataclass(frozen=True)
class ProductType:
    code: str
    section: str
    unit: str  # g, ml ou un: a unidade em que o conteúdo se mede
    name_es: str
    name_pt: str
    name_en: str


@dataclass(frozen=True)
class Variety:
    type_code: str
    code: str
    is_default: bool  # a variedade que se subentende quando a linha não diz nenhuma
    name_es: str
    name_pt: str
    name_en: str


@dataclass(frozen=True)
class Brand:
    code: str
    name: str
    display: str


@dataclass(frozen=True)
class Supplier:
    code: str
    name: str
    file_format: str
    prices_include_vat: bool


@dataclass(frozen=True)
class Reference:
    sections: dict[str, Section]
    types: dict[str, ProductType]
    varieties: dict[str, tuple[Variety, ...]]  # por tipo, na ordem do arquivo
    brands: dict[str, Brand]
    suppliers: dict[str, Supplier]

    def variety(self, type_code: str, code: str) -> Variety:
        return next(v for v in self.varieties[type_code] if v.code == code)

    def default_variety(self, type_code: str) -> Variety | None:
        return next((v for v in self.varieties[type_code] if v.is_default), None)


def _rows(name: str, data_dir: Path) -> list[dict[str, str]]:
    with open(data_dir / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _bool(value: str) -> bool:
    return value.strip().lower() == "true"


@cache
def load(data_dir: Path = DATA_DIR) -> Reference:
    sections = {r["code"]: Section(**r) for r in _rows("sections.csv", data_dir)}
    types = {r["code"]: ProductType(**r) for r in _rows("product_types.csv", data_dir)}
    varieties: dict[str, list[Variety]] = {code: [] for code in types}
    for r in _rows("varieties.csv", data_dir):
        varieties[r["type_code"]].append(Variety(**{**r, "is_default": _bool(r["is_default"])}))
    brands = {r["code"]: Brand(**r) for r in _rows("brands.csv", data_dir)}
    suppliers = {
        r["code"]: Supplier(**{**r, "prices_include_vat": _bool(r["prices_include_vat"])})
        for r in _rows("suppliers.csv", data_dir)
    }
    ref = Reference(sections, types, {k: tuple(v) for k, v in varieties.items()}, brands, suppliers)
    _validate(ref)
    return ref


def _validate(ref: Reference) -> None:
    for t in ref.types.values():
        if t.section not in ref.sections:
            raise ValueError(f"tipo {t.code}: seção desconhecida {t.section}")
        if t.unit not in ("g", "ml", "un"):
            raise ValueError(f"tipo {t.code}: unidade {t.unit}")
        vs = ref.varieties[t.code]
        if not vs:
            raise ValueError(f"tipo {t.code} sem variedade")
        if sum(v.is_default for v in vs) > 1:
            raise ValueError(f"tipo {t.code}: mais de uma variedade padrão")
        if any(not v.name_es and not v.is_default for v in vs):
            raise ValueError(f"tipo {t.code}: só a variedade padrão pode não ter nome")
