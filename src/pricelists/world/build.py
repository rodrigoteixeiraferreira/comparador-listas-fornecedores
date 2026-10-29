"""Monta o mundo fictício a partir de uma semente: o mercado, o cadastro da loja, as listas e o gabarito.

A mesma semente dá sempre o mesmo mundo. O gabarito diz, para cada linha de cada lista, qual é o produto de verdade,
se a loja o tem no cadastro e que armadilha a linha carrega. O sistema nunca lê o gabarito: só os testes leem.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..reference import Reference, load
from .render import catalog_description, supplier_description
from .spec import BRAND_PRICE, PACK_UNITS, PERIODS, TYPES, WRITINGS

VAT = 1.21

# as armadilhas que o gerador planta (o nome é o mesmo no gabarito e nos testes)
SIZE_SIBLING = "size_sibling"  # o mesmo produto em outro tamanho: 1 kg × 2 kg
BRAND_SWAP = "brand_swap"  # o mesmo produto de outra marca
VARIETY_CONFLICT = "variety_conflict"  # a mesma marca e tamanho, outra variedade
PACK_VS_SINGLE = "pack_vs_single"  # o pack de 6 × a unidade avulsa
LEFTOVER_WORD = "leftover_word"  # uma palavra a mais que faz outro produto (SIN TACC)
UNKNOWN_WRITING = "unknown_writing"  # o tipo escrito de um jeito que o vocabulário não conhece
NOISE_WORD = "noise_word"  # uma palavra que não muda o produto (OFERTA, PET)
BOX_PRICE = "box_price"  # o preço é da caixa fechada, não da unidade
STALE_BARCODE = "stale_barcode"  # o código de barras de outro tamanho do mesmo produto
REUSED_CODE = "reused_code"  # o código do fornecedor que era de outro produto no mês anterior
PRICE_FACTOR = "price_factor"  # o preço digitado errado: × 10, ou o da caixa na coluna da unidade


@dataclass(frozen=True)
class MarketProduct:
    id: int
    type_code: str
    brand: str
    variety: str
    size: int
    pack: int  # 1, ou PACK_UNITS no pack
    extra: str  # "" ou a palavra que faz outro produto
    barcode: str
    cost: float  # custo de referência da unidade de venda (o pack inteiro, no pack), com IVA

    @property
    def key(self) -> tuple:
        return (self.type_code, self.brand, self.variety, self.size, self.pack, self.extra)


@dataclass(frozen=True)
class CatalogProduct:
    id: int  # o código interno da loja
    market_id: int
    description: str
    barcode: str  # "" quando o cadastro não tem
    cost: float  # o último custo pago, com IVA


@dataclass
class ListLine:
    row: int
    supplier_code: str
    barcode: str
    description: str
    section: str
    units_per_box: int
    price: float  # como está na lista: com ou sem IVA, da unidade ou da caixa
    # o gabarito
    market_id: int
    catalog_id: int | None
    traps: tuple[str, ...]
    price_per_box: bool
    true_unit_price: float  # o preço certo da unidade de venda, com IVA
    price_error: float  # 1.0 quando o preço está certo; o fator do erro plantado


@dataclass
class PriceList:
    supplier: str
    period: str
    prices_include_vat: bool
    lines: list[ListLine] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"{self.supplier}_{self.period}"


@dataclass
class World:
    seed: int
    market: list[MarketProduct]
    catalog: list[CatalogProduct]
    lists: list[PriceList]

    def market_by_id(self) -> dict[int, MarketProduct]:
        return {p.id: p for p in self.market}


def ean13(rng: random.Random, used: set[str]) -> str:
    """Código de barras com prefixo 2: a faixa de uso interno de loja, que nenhum produto real usa."""
    while True:
        body = "2" + "".join(str(rng.randrange(10)) for _ in range(11))
        total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(body))
        code = body + str((10 - total % 10) % 10)
        if code not in used:
            used.add(code)
            return code


def _cost(type_code: str, brand: str, variety_idx: int, size: int, pack: int, unit: str) -> float:
    spec = TYPES[type_code]
    qty = size if unit == "un" else size / 1000
    scale = 1.0 if unit == "un" else (size / min(spec.sizes)) ** -0.07  # o tamanho maior sai mais barato por kg
    pack_factor = pack * 0.95 if pack > 1 else 1.0
    return round(spec.price * qty * scale * BRAND_PRICE[brand] * (1 + 0.04 * variety_idx) * pack_factor, 2)


def build_market(ref: Reference, rng: random.Random) -> list[MarketProduct]:
    used: set[str] = set()
    base: list[tuple] = []
    for type_code, spec in TYPES.items():
        unit = ref.types[type_code].unit
        for brand in spec.brands:
            for vi, variety in enumerate(ref.varieties[type_code]):
                for size in spec.sizes:
                    packs = (1, PACK_UNITS) if size in spec.pack_sizes else (1,)
                    for pack in packs:
                        base.append((type_code, brand, variety.code, size, pack, "",
                                     _cost(type_code, brand, vi, size, pack, unit)))
    # as versões com a palavra a mais: produtos que existem no mercado e que a loja nunca tem
    extras = []
    for type_code, spec in TYPES.items():
        candidates = [b for b in base if b[0] == type_code and b[4] == 1]
        for word in spec.extras:
            t, brand, variety, size, pack, _, cost = rng.choice(candidates)
            extras.append((t, brand, variety, size, pack, word, round(cost * 1.15, 2)))
    market = []
    for i, (t, brand, variety, size, pack, extra, cost) in enumerate(base + extras, start=1):
        market.append(MarketProduct(i, t, brand, variety, size, pack, extra, ean13(rng, used), cost))
    return market


def build_catalog(market: list[MarketProduct], ref: Reference, rng: random.Random,
                  share: float = 0.7) -> list[CatalogProduct]:
    base = [p for p in market if not p.extra]
    chosen = sorted(rng.sample(base, round(len(base) * share)), key=lambda p: p.id)
    catalog = []
    for i, p in enumerate(chosen, start=1):
        barcode = p.barcode if rng.random() < 0.9 else ""
        cost = round(p.cost * rng.uniform(0.97, 1.03), 2)
        catalog.append(CatalogProduct(1000 + i, p.id, catalog_description(p, ref), barcode, cost))
    return catalog


def near_miss_traps(p: MarketProduct, catalog_keys: set[tuple]) -> tuple[str, ...]:
    """Por que um produto que a loja não tem parece um que ela tem."""
    traps = []
    same = [k for k in catalog_keys if k[0] == p.type_code]
    if p.extra and any(k[1:5] == (p.brand, p.variety, p.size, p.pack) for k in same):
        traps.append(LEFTOVER_WORD)
    if not p.extra:
        if any(k[1] == p.brand and k[2] == p.variety and k[4] == p.pack and k[3] != p.size for k in same):
            traps.append(SIZE_SIBLING)
        if any(k[1] != p.brand and k[2] == p.variety and k[3] == p.size and k[4] == p.pack for k in same):
            traps.append(BRAND_SWAP)
        if any(k[1] == p.brand and k[2] != p.variety and k[3] == p.size and k[4] == p.pack for k in same):
            traps.append(VARIETY_CONFLICT)
        if any(k[1:4] == (p.brand, p.variety, p.size) and k[4] != p.pack for k in same):
            traps.append(PACK_VS_SINGLE)
    return tuple(traps)


class _ListMaker:
    """Monta as listas de um fornecedor mês a mês, guardando o que ele mantém de um mês para o outro."""

    def __init__(self, supplier: str, world: World, ref: Reference, rng: random.Random):
        self.supplier = supplier
        self.ref = ref
        self.rng = rng
        self.market = world.market_by_id()
        self.catalog_by_market = {c.market_id: c for c in world.catalog}
        self.catalog_keys = {self.market[c.market_id].key for c in world.catalog}
        self.vat_included = ref.suppliers[supplier].prices_include_vat
        self.price_level = {"mayorista_norte": 0.96, "distribuidora_andina": 1.0}[supplier]
        self.codes_used: set[str] = set()
        # o que o fornecedor mantém entre os meses: código, descrição, caixa, preço e se vende por caixa
        self.items: dict[int, dict] = {}

    def _new_code(self) -> str:
        while True:
            if self.supplier == "mayorista_norte":
                code = str(self.rng.randrange(10000, 99999))
            else:
                code = f"A{self.rng.randrange(1000, 9999)}"
            if code not in self.codes_used:
                self.codes_used.add(code)
                return code

    def _add_item(self, market_id: int, code: str | None = None, traps: tuple[str, ...] = ()) -> None:
        p = self.market[market_id]
        writing = WRITINGS[self.supplier]
        unknown = p.type_code in writing.unknown_types and self.rng.random() < 0.04
        noise = self.rng.random() < 0.06
        spec = TYPES[p.type_code]
        units = self.rng.choice(spec.box_units)
        by_box = (self.supplier == "distribuidora_andina"
                  and self.ref.types[p.type_code].section in ("beverages", "cleaning")
                  and self.rng.random() < 0.3)
        price = round(p.cost * self.price_level * self.rng.uniform(0.94, 1.06), 2)
        traps = traps + ((UNKNOWN_WRITING,) if unknown else ()) + ((NOISE_WORD,) if noise else ())
        traps = traps + ((BOX_PRICE,) if by_box else ())
        if p.id not in self.catalog_by_market:
            traps = traps + near_miss_traps(p, self.catalog_keys)
        description = supplier_description(p, self.supplier, self.ref, self.rng, unknown=unknown, noise=noise)
        if by_box:
            description += f" CAJA X {units}"
        barcode = ""
        if self.supplier == "mayorista_norte" and self.rng.random() < 0.8:
            barcode = p.barcode
        self.items[market_id] = {"code": code or self._new_code(), "description": description, "units": units,
                                 "price": price, "by_box": by_box, "traps": traps, "barcode": barcode}

    def first_month(self, carried_share: float = 0.65, other_share: float = 0.25, extras: int = 4) -> None:
        in_catalog = sorted(self.catalog_by_market)
        not_in_catalog = sorted(m for m, p in self.market.items() if m not in self.catalog_by_market and not p.extra)
        # a palavra a mais só é armadilha quando a loja tem o produto sem ela
        extra_ids = sorted(m for m, p in self.market.items() if p.extra and near_miss_traps(p, self.catalog_keys))
        chosen = (self.rng.sample(in_catalog, round(len(in_catalog) * carried_share))
                  + self.rng.sample(not_in_catalog, round(len(not_in_catalog) * other_share))
                  + self.rng.sample(extra_ids, min(extras, len(extra_ids))))
        for market_id in chosen:
            self._add_item(market_id)
        if self.supplier == "mayorista_norte":
            self._plant_stale_barcodes(2)

    def _plant_stale_barcodes(self, n: int) -> None:
        """O fornecedor deixou na linha o código de barras de outro tamanho do mesmo produto (que a loja tem)."""
        by_key = {}
        for c in self.catalog_by_market.values():
            if c.barcode:
                p = self.market[c.market_id]
                by_key.setdefault((p.type_code, p.brand, p.variety, p.pack), []).append(c)
        candidates = []
        for market_id, item in sorted(self.items.items()):
            p = self.market[market_id]
            siblings = [c for c in by_key.get((p.type_code, p.brand, p.variety, p.pack), [])
                        if self.market[c.market_id].size != p.size]
            if market_id not in self.catalog_by_market and not p.extra and siblings:
                candidates.append((market_id, siblings[0]))
        for market_id, sibling in self.rng.sample(candidates, min(n, len(candidates))):
            self.items[market_id]["barcode"] = sibling.barcode
            self.items[market_id]["traps"] += (STALE_BARCODE,)

    def next_month(self, inflation: float, drop_share: float = 0.08, new_share: float = 0.1) -> None:
        current = sorted(self.items)
        dropped = self.rng.sample(current, round(len(current) * drop_share))
        freed_codes = [self.items[m]["code"] for m in dropped]
        for m in dropped:
            del self.items[m]
        for item in self.items.values():  # quem continua: mesmo código e descrição, preço novo
            item["price"] = round(item["price"] * inflation * self.rng.uniform(0.98, 1.02), 2)
            item["traps"] = tuple(t for t in item["traps"] if t != REUSED_CODE)
        pool = sorted(m for m, p in self.market.items() if m not in self.items and m not in dropped and not p.extra)
        new = self.rng.sample(pool, round(len(current) * new_share))
        for i, market_id in enumerate(new):
            if i < 2 and freed_codes:  # o código de um produto que saiu passa a outro produto
                self._add_item(market_id, code=freed_codes.pop(0), traps=(REUSED_CODE,))
            else:
                self._add_item(market_id)
                self.items[market_id]["price"] = round(self.items[market_id]["price"] * inflation, 2)

    def snapshot(self, period: str, plant_price_errors: bool) -> PriceList:
        rows = []
        for market_id, item in self.items.items():
            p = self.market[market_id]
            section = self.ref.types[p.type_code].section
            rows.append((section, item["description"], market_id, item))
        rows.sort(key=lambda r: (list(self.ref.sections).index(r[0]), r[1]))
        # os erros de digitação: um zero a mais; na Norte, também o preço da caixa na coluna da unidade
        errors: dict[int, str] = {}
        if plant_price_errors:
            unit_rows = [i for i, r in enumerate(rows) if not r[3]["by_box"]]
            kinds = ("x10", "x10", "box") if self.supplier == "mayorista_norte" else ("x10", "x10", "x10")
            errors = dict(zip(self.rng.sample(unit_rows, len(kinds)), kinds))
        price_list = PriceList(self.supplier, period, self.vat_included)
        for i, (section, description, market_id, item) in enumerate(rows):
            true_price = item["price"]
            units = item["units"]
            printed = true_price * units * 0.97 if item["by_box"] else true_price
            if not self.vat_included:
                printed /= VAT
            traps = item["traps"]
            error = 1.0
            if i in errors:
                error = float(units) if errors[i] == "box" else 10.0
                printed *= error
                traps = traps + (PRICE_FACTOR,)
            price_list.lines.append(ListLine(
                row=i + 1, supplier_code=item["code"], barcode=item["barcode"], description=description,
                section=section, units_per_box=units, price=round(printed, 2), market_id=market_id,
                catalog_id=self.catalog_by_market[market_id].id if market_id in self.catalog_by_market else None,
                traps=traps, price_per_box=item["by_box"], true_unit_price=true_price, price_error=error,
            ))
        return price_list


def build_world(seed: int, ref: Reference | None = None) -> World:
    ref = ref or load()
    rng = random.Random(seed)
    market = build_market(ref, rng)
    catalog = build_catalog(market, ref, rng)
    world = World(seed, market, catalog, [])
    for supplier in WRITINGS:
        maker = _ListMaker(supplier, world, ref, random.Random(f"{seed}:{supplier}"))
        maker.first_month()
        world.lists.append(maker.snapshot(PERIODS[0], plant_price_errors=False))
        inflation = 1.04 if supplier == "mayorista_norte" else 1.035
        maker.next_month(inflation)
        world.lists.append(maker.snapshot(PERIODS[1], plant_price_errors=True))
    return world
