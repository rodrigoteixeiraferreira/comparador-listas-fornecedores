"""O extrator de atributos: a linha de texto vira tipo, marca, variedade, conteúdo, pack e caixa.

Só reconhece o que está nos dados de referência e no vocabulário (data/vocabulary.csv). O que não reconhece não é
adivinhado: fica em `leftover`, a palavra que sobra, e a cascata não confirma sozinha um par com palavra sobrando.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from .reference import DATA_DIR, Reference, load

STOPWORDS = frozenset({"DE", "DEL", "LA", "LAS", "EL", "LOS", "EN", "Y"})

_UNIT = {"KG": ("g", 1000), "KGS": ("g", 1000), "K": ("g", 1000), "GR": ("g", 1), "GRS": ("g", 1), "G": ("g", 1),
         "GRAMOS": ("g", 1), "L": ("ml", 1000), "LT": ("ml", 1000), "LTS": ("ml", 1000), "LITRO": ("ml", 1000),
         "LITROS": ("ml", 1000), "ML": ("ml", 1), "CC": ("ml", 1)}
_SIZE = re.compile(r"\bX?\s*(\d+(?:[.,]\d+)?)\s*(" + "|".join(sorted(_UNIT, key=len, reverse=True)) + r")\b")
_PACK = re.compile(r"\bPACK\s*X?\s*(\d+)\b")
_BOX = re.compile(r"\b(?:CAJA|BULTO)\s*X?\s*(\d+)\b")
_COUNT = re.compile(r"\bX\s*(\d+)\s*(?:U|UN|UNID|UNIDADES)?\b")


def normalize(text: str) -> str:
    """Maiúsculas, sem acento, espaços simples. A pontuação fica: o conteúdo (1.5LT) ainda precisa dela."""
    text = unicodedata.normalize("NFKD", text.upper())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.split())


def tokens(text: str) -> list[str]:
    """As palavras, sem pontuação e sem as palavras vazias (DE, LA, EN…)."""
    words = re.sub(r"[^A-Z0-9]+", " ", normalize(text)).split()
    return [w for w in words if w not in STOPWORDS]


@dataclass(frozen=True)
class Attributes:
    type_code: str | None
    brand: str | None
    variety: str | None
    size: int | None  # em g, ml ou unidades
    unit: str | None
    pack: int  # unidades no pack; 1 quando a linha não diz
    units_per_box: int | None  # «CAJA X 12» na própria linha: o preço é da caixa
    leftover: tuple[str, ...]  # a palavra que sobra: o que não se reconheceu e não é ruído
    noise: tuple[str, ...]
    ambiguous: tuple[str, ...]  # o que ficou ambíguo (type, brand, variety, size)


@dataclass(frozen=True)
class Vocabulary:
    types: dict[tuple[str, ...], set[str]]
    brands: dict[tuple[str, ...], set[str]]
    varieties: dict[str, dict[tuple[str, ...], set[str]]]  # por tipo
    noise: frozenset[tuple[str, ...]]
    defaults: dict[str, str]  # a variedade subentendida de cada tipo
    units: dict[str, str]


@cache
def vocabulary(data_dir: Path = DATA_DIR) -> Vocabulary:
    ref: Reference = load(data_dir)
    types: dict[tuple[str, ...], set[str]] = {}
    brands: dict[tuple[str, ...], set[str]] = {}
    varieties: dict[str, dict[tuple[str, ...], set[str]]] = {t: {} for t in ref.types}
    noise: set[tuple[str, ...]] = set()

    def add(table: dict, term: str, canonical: str) -> None:
        key = tuple(tokens(term))
        if key:
            table.setdefault(key, set()).add(canonical)

    for t in ref.types.values():
        add(types, t.name_es, t.code)
        for v in ref.varieties[t.code]:
            add(varieties[t.code], v.name_es, v.code)
    for b in ref.brands.values():
        add(brands, b.name, b.code)
    with open(data_dir / "vocabulary.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            kind, term, canonical = r["kind"], r["term"], r["canonical"]
            if kind == "type":
                add(types, term, canonical)
            elif kind == "brand":
                add(brands, term, canonical)
            elif kind == "variety":
                add(varieties[r["type_code"]], term, canonical)
            elif kind == "noise":
                noise.add(tuple(tokens(term)))
            else:
                raise ValueError(f"vocabulário: tipo de termo desconhecido {kind!r}")
    defaults = {t: v.code for t in ref.types if (v := ref.default_variety(t))}
    return Vocabulary(types, brands, varieties, frozenset(noise), defaults,
                      {t.code: t.unit for t in ref.types.values()})


def _find(words: list[str], used: list[bool], table: dict[tuple[str, ...], set[str]]):
    """O termo mais longo da tabela entre as palavras livres. Devolve (código, posições) ou (None, ambíguo)."""
    longest = max((len(k) for k in table), default=0)
    found: list[tuple[int, int, frozenset[str]]] = []
    for size in range(longest, 0, -1):
        for i in range(len(words) - size + 1):
            if any(used[i:i + size]):
                continue
            hit = table.get(tuple(words[i:i + size]))
            if hit:
                found.append((i, size, frozenset(hit)))
        if found:
            break
    codes = {code for _, _, hit in found for code in hit}
    if len(codes) != 1:
        return None, bool(codes)
    return next(iter(codes)), [range(i, i + size) for i, size, _ in found]


def _number(text: str) -> float:
    return float(text.replace(",", "."))


def extract(description: str, vocab: Vocabulary | None = None) -> Attributes:
    vocab = vocab or vocabulary()
    text = normalize(description)
    ambiguous: list[str] = []

    pack = 1
    units_per_box = None
    if m := _BOX.search(text):
        units_per_box = int(m.group(1))
        text = text[:m.start()] + " " + text[m.end():]
    if m := _PACK.search(text):
        pack = int(m.group(1))
        text = text[:m.start()] + " " + text[m.end():]

    size = unit = None
    sizes = list(_SIZE.finditer(text))
    if len(sizes) == 1:
        m = sizes[0]
        unit, factor = _UNIT[m.group(2)]
        size = round(_number(m.group(1)) * factor)
        text = text[:m.start()] + " " + text[m.end():]
    elif sizes:
        ambiguous.append("size")
    count = None  # «X 25 U»: o conteúdo dos tipos que se contam por unidade
    if size is None and (m := _COUNT.search(text)):
        count = int(m.group(1))
        text = text[:m.start()] + " " + text[m.end():]

    words = tokens(text)
    used = [False] * len(words)

    def take(table, label):
        code, where = _find(words, used, table)
        if code is None:
            if where:
                ambiguous.append(label)
            return None
        for span in where:
            for i in span:
                used[i] = True
        return code

    type_code = take(vocab.types, "type")
    brand = take(vocab.brands, "brand")
    variety = None
    if type_code:
        variety = take(vocab.varieties[type_code], "variety") or vocab.defaults.get(type_code)
    stray = ()
    if count is not None:
        if type_code and vocab.units[type_code] == "un":
            size, unit = count, "un"
        else:
            stray = (f"X{count}",)  # uma contagem onde o tipo se mede em peso ou volume: não se adivinha
    noise = []
    for i, w in enumerate(words):
        if not used[i] and (w,) in vocab.noise:
            used[i] = True
            noise.append(w)
    leftover = tuple(w for w, u in zip(words, used) if not u) + stray
    return Attributes(type_code, brand, variety, size, unit, pack, units_per_box, leftover, tuple(noise),
                      tuple(ambiguous))
