"""A dupla leitura da foto: duas transcrições independentes, por modelos diferentes; só segue o que as duas dizem igual.

As transcrições ficam gravadas em data/recorded/<sha256 da imagem>.json, com o prompt que as produziu
(prompts/transcribe_price_list.md). Assim a demo roda sem chave de API e o teste falha se a foto mudar sem uma leitura
nova. A linha em que as leituras discordam, ou que uma delas marcou com dúvida, não entra: vai à fila de suporte.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .extract import normalize
from .readers import ParsedList, RawLine, _period, _vat, file_hash, parse_ars
from .reference import DATA_DIR

RECORDED = DATA_DIR / "recorded"


@dataclass(frozen=True)
class Disagreement:
    item_code: str
    reading_a: dict | None
    reading_b: dict | None
    why: str  # «only_one_reading», «description», «price», «doubt»


def recorded_for(path: Path) -> Path:
    return RECORDED / f"{file_hash(path)}.json"


def has_reading(path: Path) -> bool:
    return recorded_for(path).exists()


def compare(a: dict, b: dict) -> tuple[list[tuple[dict, dict]], list[Disagreement]]:
    """Alinha as duas leituras pelo código. Devolve as linhas iguais e as discordâncias."""
    by_a = {x["code"].strip(): x for x in a["lines"]}
    by_b = {x["code"].strip(): x for x in b["lines"]}
    agreed, disagreements = [], []
    for code in list(by_a) + [c for c in by_b if c not in by_a]:
        x, y = by_a.get(code), by_b.get(code)
        if x is None or y is None:
            disagreements.append(Disagreement(code, x, y, "only_one_reading"))
        elif x.get("doubt") or y.get("doubt"):
            disagreements.append(Disagreement(code, x, y, "doubt"))
        elif normalize(x["description"]) != normalize(y["description"]):
            disagreements.append(Disagreement(code, x, y, "description"))
        elif parse_ars(x["price"]) != parse_ars(y["price"]):
            disagreements.append(Disagreement(code, x, y, "price"))
        else:
            agreed.append((x, y))
    return agreed, disagreements


def double_read(path: Path) -> ParsedList:
    record_path = recorded_for(path)
    if not record_path.exists():
        raise FileNotFoundError(f"sem leitura gravada para {Path(path).name}: rodar as duas leituras da IA "
                                f"(prompts/transcribe_price_list.md) e gravar em {record_path.name}")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    a, b = record["readings"]
    agreed, disagreements = compare(a, b)
    header = " ".join(a.get("header", []))
    parsed = ParsedList(Path(path), "image", record["image_sha256"], _period(header), _vat(header))
    for n, (x, _) in enumerate(agreed, start=1):
        parsed.lines.append(RawLine(n, x["code"].strip(), "", " ".join(x["description"].split()),
                                    parse_ars(x["price"]), None, x.get("section", "")))
    parsed.disagreements = disagreements
    parsed.counted = max(len(a["lines"]), len(b["lines"]))  # a contagem da conferência 1: a leitura mais longa
    return parsed
