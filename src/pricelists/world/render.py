"""Como cada um escreve um produto: o cadastro da loja e os fornecedores, cada um no seu estilo."""
from __future__ import annotations

import random
import unicodedata

from ..reference import Reference
from .spec import PACK_UNITS, WRITINGS


def format_size(size: int, unit: str, style: str) -> str:
    """O conteúdo escrito como cada um escreve: «1 KG» no cadastro, «1KG» na Norte, «X 1 KG» na Andina."""
    if unit == "un":
        return {"catalog": f"X {size} U", "mayorista_norte": f"X{size}", "distribuidora_andina": f"X {size} U",
                "mercantil_ombu": f"x {size} u"}[style]
    big = size >= 1000
    value = size / 1000 if big else size
    text = f"{value:g}"
    if style == "mercantil_ombu":
        return f"{text.replace('.', ',')} {('kg' if big else 'g') if unit == 'g' else ('L' if big else 'ml')}"
    if style == "catalog":
        return f"{text.replace('.', ',')} {('KG' if big else 'G') if unit == 'g' else ('L' if big else 'ML')}"
    if style == "mayorista_norte":
        return f"{text}{('KG' if big else 'GR') if unit == 'g' else ('LT' if big else 'CC')}"
    return f"X {text.replace('.', ',')} {('KG' if big else 'G') if unit == 'g' else ('L' if big else 'ML')}"


def format_pack(style: str) -> str:
    return {"catalog": f"PACK X {PACK_UNITS}", "mayorista_norte": f"PACK X{PACK_UNITS}",
            "distribuidora_andina": f"PACK X {PACK_UNITS}", "mercantil_ombu": f"Pack x {PACK_UNITS}"}[style]


def _title(text: str) -> str:
    """Maiúsculas e minúsculas, sem acento: a impressora do Mercantil Ombú não tem Ñ nem acento."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return " ".join(w.capitalize() for w in plain.split())


def catalog_description(p, ref: Reference) -> str:
    """O cadastro escreve sempre igual: TIPO VARIEDADE MARCA CONTEÚDO [PACK]."""
    t = ref.types[p.type_code]
    v = ref.variety(p.type_code, p.variety)
    parts = [t.name_es, v.name_es, ref.brands[p.brand].name, format_size(p.size, t.unit, "catalog")]
    if p.pack > 1:
        parts.append(format_pack("catalog"))
    return " ".join(x for x in parts if x)


def supplier_description(p, supplier: str, ref: Reference, rng: random.Random,
                         unknown: bool = False, noise: bool = False) -> str:
    """A linha como o fornecedor escreve. `unknown`: o tipo numa escrita que o vocabulário não conhece."""
    w = WRITINGS[supplier]
    t = ref.types[p.type_code]
    v = ref.variety(p.type_code, p.variety)
    type_text = rng.choice(w.unknown_types[p.type_code] if unknown else w.types[p.type_code])
    if v.is_default:
        variety_text = v.name_es if v.name_es and rng.random() < 0.3 else ""
    else:
        variety_text = rng.choice(w.varieties.get((p.type_code, p.variety), (v.name_es,)))
    brand = ref.brands[p.brand].name
    brand_text = rng.choice((brand, *w.brands.get(p.brand, ()))) if supplier == "distribuidora_andina" else brand
    size_text = format_size(p.size, t.unit, supplier)
    if supplier == "distribuidora_andina":
        parts = [brand_text, type_text, variety_text, p.extra, size_text]
    elif supplier == "mercantil_ombu":
        parts = [_title(type_text), _title(brand_text), _title(variety_text), _title(p.extra), size_text]
    else:
        parts = [type_text, brand_text, variety_text, p.extra, size_text]
    if p.pack > 1:
        parts.append(format_pack(supplier))
    if noise:
        parts.append(rng.choice(w.noise))
    return " ".join(x for x in parts if x)
