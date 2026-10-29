"""O mundo fictício: o que existe no mercado, quanto custa e como cada fornecedor escreve.

Nada aqui é conhecimento do sistema. O que o sistema sabe está em data/ (tipos, variedades, marcas, vocabulário);
este módulo descreve o mundo que o gerador inventa para pôr o sistema à prova. As escritas «desconhecidas» são, de
propósito, as que o vocabulário do sistema não tem: a linha escrita assim não pode ser confirmada sozinha.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TypeSpec:
    sizes: tuple[int, ...]  # em g, ml ou unidades, conforme o tipo
    price: float  # custo de referência com IVA, em pesos, por kg, litro ou unidade
    pack_sizes: tuple[int, ...] = ()  # os tamanhos que também se vendem em pack de 6
    brands: tuple[str, ...] = ()
    extras: tuple[str, ...] = ()  # palavras que fazem outro produto (SIN TACC): a armadilha da palavra que sobra
    box_units: tuple[int, ...] = (12,)  # unidades por caixa fechada (bulto)


PACK_UNITS = 6

TYPES: dict[str, TypeSpec] = {
    "yerba_mate": TypeSpec((500, 1000, 2000), 4500, brands=("tres_lunas", "dona_tomasa", "piedra_mora", "vientoverde"),
                           extras=("ORGANICA", "BARBACUA"), box_units=(10, 20)),
    "cookies": TypeSpec((150, 300), 7000, brands=("tres_lunas", "molino_celeste", "el_benteveo"),
                        extras=("RELLENAS", "SIN TACC"), box_units=(24, 36)),
    "crackers": TypeSpec((150, 300), 5500, brands=("tres_lunas", "molino_celeste", "el_benteveo"),
                         extras=("SALVADO", "SIN TACC"), box_units=(24, 36)),
    "sunflower_oil": TypeSpec((900, 1500, 3000), 2900, brands=("solclaro", "pradoluz"),
                              extras=("ALTO OLEICO",), box_units=(6, 12)),
    "rice": TypeSpec((500, 1000), 2000, brands=("molino_celeste", "pradoluz", "granalba"),
                     extras=("GRANO CORTO",), box_units=(10, 20)),
    "pasta": TypeSpec((500,), 2600, brands=("dona_tomasa", "molino_celeste", "granalba"),
                      extras=("AL HUEVO", "SIN TACC"), box_units=(20,)),
    "sugar": TypeSpec((1000,), 1300, brands=("piedra_mora", "pradoluz"), extras=("MASCABO",), box_units=(10,)),
    "flour": TypeSpec((1000,), 1100, brands=("dona_tomasa", "molino_celeste", "granalba"),
                      extras=("SIN TACC",), box_units=(10,)),
    "milk": TypeSpec((1000,), 1500, brands=("arroyo_manso", "fontesur"),
                     extras=("CHOCOLATADA", "ZERO LACTOSA"), box_units=(12,)),
    "mayonnaise": TypeSpec((250, 500), 5600, brands=("solclaro", "lagomar"), extras=("CON LIMON",), box_units=(12, 24)),
    "dulce_de_leche": TypeSpec((400, 1000), 6800, brands=("tres_lunas", "arroyo_manso", "fontesur"),
                               box_units=(12,)),
    "tomato_puree": TypeSpec((520,), 1900, brands=("dona_tomasa", "lagomar"), extras=("CON ALBAHACA",),
                             box_units=(12, 24)),
    "tuna": TypeSpec((170,), 15000, brands=("pradoluz", "lagomar"), extras=("LOMITOS",), box_units=(24, 48)),
    "ground_coffee": TypeSpec((250, 500), 24000, brands=("piedra_mora", "cerro_nublado"),
                              extras=("DESCAFEINADO",), box_units=(12,)),
    "tea_bags": TypeSpec((25, 50), 70, brands=("tres_lunas", "vientoverde"), extras=("SABORIZADO",),
                         box_units=(12, 24)),
    "cola": TypeSpec((500, 1500, 2250), 1300, pack_sizes=(500,), brands=("solclaro", "cumbrefria"),
                     box_units=(6, 8)),
    "water": TypeSpec((500, 1500), 700, pack_sizes=(500,), brands=("solclaro", "arroyo_manso", "cumbrefria"),
                      extras=("SABORIZADA",), box_units=(6, 12)),
    "beer": TypeSpec((473, 1000), 3200, pack_sizes=(473,), brands=("cumbrefria", "cerro_nublado"),
                     extras=("SIN ALCOHOL",), box_units=(6, 12, 24)),
    "dish_soap": TypeSpec((500, 750), 3100, brands=("nubalta", "brisa_austral"), extras=("CONCENTRADO",),
                          box_units=(12,)),
    "bleach": TypeSpec((1000, 2000), 900, brands=("nubalta", "brisa_austral"), extras=("EN GEL",),
                       box_units=(12, 6)),
    "laundry_powder": TypeSpec((800, 3000), 5200, brands=("nubalta", "brisa_austral"), extras=("MATIC",),
                               box_units=(10, 4)),
    "buns": TypeSpec((4, 6), 380, brands=("dona_tomasa", "el_benteveo"), extras=("CON SESAMO",), box_units=(10,)),
}

# preço relativo de cada marca (a mesma em todo o mundo, para o custo ser estável entre sementes)
BRAND_PRICE = {
    "tres_lunas": 1.15, "solclaro": 1.05, "arroyo_manso": 0.95, "dona_tomasa": 0.9, "molino_celeste": 1.0,
    "piedra_mora": 1.2, "el_benteveo": 0.85, "nubalta": 1.1, "pradoluz": 0.9, "vientoverde": 1.05,
    "cumbrefria": 1.0, "lagomar": 1.1, "fontesur": 1.0, "granalba": 0.88, "cerro_nublado": 1.25,
    "brisa_austral": 0.9,
}


@dataclass(frozen=True)
class Writing:
    """Como um fornecedor escreve: as escritas que o vocabulário conhece e as que ele não conhece."""

    types: dict[str, tuple[str, ...]]
    varieties: dict[tuple[str, str], tuple[str, ...]]  # (tipo, variedade) -> escritas
    brands: dict[str, tuple[str, ...]]
    unknown_types: dict[str, tuple[str, ...]]
    noise: tuple[str, ...]


# A Mayorista Norte escreve por extenso, com o tipo na frente: «YERBA TRES LUNAS SUAVE 1KG».
NORTE = Writing(
    types={
        "yerba_mate": ("YERBA MATE", "YERBA"), "cookies": ("GALLETITAS", "GALLETITAS DULCES"),
        "crackers": ("GALLETITAS DE AGUA", "GALLETITAS AGUA"), "sunflower_oil": ("ACEITE GIRASOL", "ACEITE DE GIRASOL"),
        "rice": ("ARROZ",), "pasta": ("FIDEOS", "FIDEOS SECOS"), "sugar": ("AZUCAR",),
        "flour": ("HARINA", "HARINA DE TRIGO"), "milk": ("LECHE LARGA VIDA", "LECHE UAT"), "mayonnaise": ("MAYONESA",),
        "dulce_de_leche": ("DULCE DE LECHE",), "tomato_puree": ("PURE DE TOMATE", "PURE TOMATE"), "tuna": ("ATUN",),
        "ground_coffee": ("CAFE MOLIDO",), "tea_bags": ("TE", "TE EN SAQUITOS"), "cola": ("GASEOSA COLA",),
        "water": ("AGUA MINERAL", "AGUA"), "beer": ("CERVEZA",), "dish_soap": ("DETERGENTE",),
        "bleach": ("LAVANDINA",), "laundry_powder": ("JABON EN POLVO", "JABON POLVO"), "buns": ("PAN",),
    },
    varieties={},  # escreve a variedade por extenso, como no cadastro
    brands={},  # e a marca também
    unknown_types={
        "yerba_mate": ("YRB",), "cookies": ("GLTS",), "rice": ("ARZ",), "sugar": ("AZR",), "tuna": ("ATN",),
        "beer": ("CRVZ",), "dish_soap": ("DTRG",), "bleach": ("LVDN",), "mayonnaise": ("MYNS",),
    },
    noise=("OFERTA", "NUEVO", "PROMO"),
)

# A Distribuidora Andina abrevia, com a marca na frente: «T.LUNAS YBA MATE SUAVE X 1 KG».
ANDINA = Writing(
    types={
        "yerba_mate": ("YERBA", "YBA MATE"), "cookies": ("GALLET", "GALL DULCES"), "crackers": ("GALLET AGUA", "GALL AGUA"),
        "sunflower_oil": ("ACEIT GIRAS", "AC GIRASOL"), "rice": ("ARROZ",), "pasta": ("FIDEO", "FID SECOS"),
        "sugar": ("AZUC", "AZUCAR"), "flour": ("HNA TRIGO", "HARINA"), "milk": ("LECHE L.VIDA", "LECHE LV"),
        "mayonnaise": ("MAYON", "MAYONESA"), "dulce_de_leche": ("DULCE LECHE", "D.LECHE"),
        "tomato_puree": ("PURE TOM", "PURE TOMATE"), "tuna": ("ATUN",), "ground_coffee": ("CAFE MOL", "CAFE MOLIDO"),
        "tea_bags": ("TE SAQ", "TE"), "cola": ("GSA COLA", "GASEOSA COLA"), "water": ("AGUA MIN", "AGUA"),
        "beer": ("CERV", "CERVEZA"), "dish_soap": ("DETERG", "DETERGENTE"), "bleach": ("LAVAND", "LAVANDINA"),
        "laundry_powder": ("JAB POLVO", "JAB EN POLVO"), "buns": ("PAN",),
    },
    varieties={
        ("yerba_mate", "traditional"): ("TRAD",), ("yerba_mate", "with_herbs"): ("COMP", "COMPUEST"),
        ("cookies", "chocolate"): ("CHOC", "CHOCO"), ("cookies", "vanilla"): ("VAIN",), ("cookies", "lemon"): ("LIM",),
        ("crackers", "classic"): ("CLAS",), ("crackers", "whole_wheat"): ("INTEG",),
        ("rice", "long_grain"): ("L.FINO",), ("rice", "brown"): ("INTEG",), ("rice", "parboiled"): ("PARB",),
        ("pasta", "spaghetti"): ("SPAG",), ("pasta", "fusilli"): ("TIRAB",), ("pasta", "penne"): ("MOSTACH",),
        ("flour", "self_rising"): ("LEUD",), ("milk", "whole"): ("ENT",), ("milk", "skim"): ("DESCR", "DESC"),
        ("mayonnaise", "classic"): ("CLAS",), ("dulce_de_leche", "classic"): ("CLAS",),
        ("dulce_de_leche", "baking"): ("REPOST",), ("tuna", "in_water"): ("AL NAT", "NAT"), ("tuna", "in_oil"): ("EN AC",),
        ("ground_coffee", "classic"): ("CLAS",), ("ground_coffee", "sugar_roasted"): ("TORR",),
        ("tea_bags", "black"): ("NEG",), ("water", "still"): ("S/GAS",), ("water", "sparkling"): ("C/GAS",),
        ("dish_soap", "lemon"): ("LIM",), ("buns", "hamburger"): ("HAMB",),
    },
    brands={
        "tres_lunas": ("T.LUNAS", "3 LUNAS"), "solclaro": ("SOL CLARO",), "arroyo_manso": ("A.MANSO",),
        "dona_tomasa": ("D.TOMASA",), "molino_celeste": ("M.CELESTE",), "piedra_mora": ("P.MORA",),
        "el_benteveo": ("BENTEVEO",), "pradoluz": ("PRADO LUZ",), "cumbrefria": ("CUMBRE FRIA",),
        "fontesur": ("FONTE SUR",), "cerro_nublado": ("C.NUBLADO",), "brisa_austral": ("B.AUSTRAL",),
    },
    unknown_types={
        "crackers": ("GLT AGUA",), "sunflower_oil": ("ACT GRSL",), "pasta": ("FDS",), "flour": ("HRN",),
        "milk": ("LCH LV",), "dulce_de_leche": ("DDL",), "ground_coffee": ("CF MOL",), "water": ("AG MNRL",),
        "laundry_powder": ("JBN PLV",),
    },
    noise=("PET", "LATA", "BOTELLA", "DOYPACK", "BOLSA"),
)

WRITINGS = {"mayorista_norte": NORTE, "distribuidora_andina": ANDINA}

PERIODS = ("2026-09", "2026-10")
MONTH_NAMES_ES = {"2026-09": "SEPTIEMBRE 2026", "2026-10": "OCTUBRE 2026"}
