"""O portão: sete conferências antes de a lista nova substituir a anterior do mesmo fornecedor.

Enquanto a lista nova não passa, a anterior continua valendo. As conferências 1, 2, 3 e 5 olham o arquivo (e a lista
anterior); a 4, a 6 e a 7 olham o que a cascata identificou na lista nova, que fica em espera até o portão decidir.

| # | conferência | passa quando |
|---|---|---|
| 1 | count: linhas lidas ÷ linhas contadas sem o leitor | ± 5%, e pelo menos uma |
| 2 | fidelity: 10 linhas relidas por um caminho independente do leitor | 10 de 10 iguais |
| 3 | structure: a forma da lista contra a anterior | linhas 0,6 a 1,8 ×; código de barras ± 25 pp; sem preço + 15 pp; códigos em comum ≥ 50% |
| 4 | price_vs_cost: mediana preço ÷ custo nos pares confirmados | 0,8 a 1,5 |
| 5 | price_change: as mesmas linhas, preço novo ÷ anterior | mediana 0,92 a 1,5; nenhum fator exato (× 10, × 12, IVA…) em 30% ou mais |
| 6 | continuity: os confirmados da anterior que seguem confirmados | bloqueia abaixo de 70% (a meta é 95%) |
| 7 | zero_check: pares confirmados com marca, tamanho ou unidade incompatível | 0 |
"""
from __future__ import annotations

import random
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
from openpyxl import load_workbook

from .readers import ParsedList, parse_ars

SUSPICIOUS_FACTORS = (10.0, 100.0, 0.1, 0.01, 12.0, 1 / 12, 1.21, 1 / 1.21)
_MONEY = re.compile(r"^\$?\d{1,3}(?:\.\d{3})*,\d{2}$|^\$?\d+,\d{2}$")


@dataclass(frozen=True)
class CheckResult:
    number: int
    code: str
    passed: bool | None  # None: não se aplica (a primeira lista do fornecedor não tem anterior)
    measured: dict
    detail: str = ""


@dataclass
class GateResult:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed is not False for c in self.checks)

    @property
    def failed(self) -> list[int]:
        return [c.number for c in self.checks if c.passed is False]


# --- 1. contagem ------------------------------------------------------------------------------------------------

def independent_count(path: Path) -> int:
    """Quantas linhas de produto o arquivo tem, contadas sem o leitor."""
    if path.suffix.lower() == ".xlsx":
        ws = load_workbook(path, data_only=True, read_only=True).active
        n = 0
        for row in ws.iter_rows(values_only=True):
            has_number = any(isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 for v in row)
            has_text = any(isinstance(v, str) and sum(c.isalpha() for c in v) >= 3 for v in row)
            n += has_number and has_text
        return n
    with pdfplumber.open(path) as pdf:
        return sum(1 for page in pdf.pages for line in (page.extract_text() or "").splitlines()
                   if re.search(r"\$\s*\d", line))


def check_count(new: ParsedList, tolerance: float = 0.05) -> CheckResult:
    if new.file_format == "image":
        # na foto, o que entra são as linhas em que as duas leituras concordam, contra a leitura mais longa
        counted, tolerance = new.counted or 0, 0.10
    else:
        counted = independent_count(new.path)
    read = len(new.lines)
    ok = read >= 1 and abs(read - counted) <= max(1, tolerance * counted)
    return CheckResult(1, "count", ok, {"read": read, "counted": counted})


# --- 2. fidelidade ----------------------------------------------------------------------------------------------

def _independent_rows(path: Path) -> dict:
    """A releitura independente: código -> (descrição, preço), achando o preço pelo conteúdo, não pelo rótulo."""
    rows: dict = {}
    if path.suffix.lower() == ".xlsx":
        data = [r for r in load_workbook(path, data_only=True, read_only=True).active.iter_rows(values_only=True)]
        width = max((len(r) for r in data), default=0)
        cents = [sum(1 for r in data if j < len(r) and isinstance(r[j], float) and r[j] != int(r[j]))
                 for j in range(width)]
        if not cents or max(cents) == 0:
            return {}
        price_col = cents.index(max(cents))
        for n, r in enumerate(data, start=1):
            texts = [v for v in r if isinstance(v, str) and sum(c.isalpha() for c in v) >= 3]
            if texts and price_col < len(r) and isinstance(r[price_col], (int, float)):
                rows[n] = (max(texts, key=len), float(r[price_col]))
        return rows
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            lines: dict[int, list] = {}
            for w in page.extract_words():
                lines.setdefault(round(w["top"]), []).append(w)
            for words in lines.values():
                words.sort(key=lambda w: w["x0"])
                money = [i for i, w in enumerate(words) if _MONEY.match(w["text"])]
                if not money:
                    continue
                i = money[-1]
                start = i - 1 if i > 0 and words[i - 1]["text"] == "$" else i
                code = words[0]["text"]
                rows[code] = (" ".join(w["text"] for w in words[1:start]), parse_ars(words[i]["text"].lstrip("$")))
    return rows


def check_fidelity(new: ParsedList, sample: int = 10) -> CheckResult:
    if new.file_format == "image":
        return CheckResult(2, "fidelity", None, {}, "na foto, a releitura é a segunda leitura da IA")
    if not new.lines:
        return CheckResult(2, "fidelity", False, {"compared": 0, "equal": 0}, "nenhuma linha lida")
    rows = _independent_rows(new.path)
    rng = random.Random(new.sha256)
    chosen = rng.sample(new.lines, min(sample, len(new.lines)))
    equal = 0
    for line in chosen:
        key = line.row if new.file_format == "xlsx" else line.supplier_code
        got = rows.get(key)
        if got and got[0] == line.description and line.price is not None and abs(got[1] - line.price) < 0.005:
            equal += 1
    return CheckResult(2, "fidelity", equal == len(chosen), {"compared": len(chosen), "equal": equal})


# --- 3. estrutura -----------------------------------------------------------------------------------------------

def _shares(pl: ParsedList) -> dict:
    n = len(pl.lines) or 1
    return {"lines": len(pl.lines), "barcode": sum(1 for ln in pl.lines if ln.barcode) / n,
            "no_price": sum(1 for ln in pl.lines if ln.price is None) / n}


def check_structure(new: ParsedList, previous: ParsedList | None) -> CheckResult:
    if previous is None or not previous.lines:
        return CheckResult(3, "structure", None, {}, "primeira lista do fornecedor")
    a, b = _shares(new), _shares(previous)
    ratio = a["lines"] / b["lines"]
    prev_codes = {ln.supplier_code for ln in previous.lines}
    common = len(prev_codes & {ln.supplier_code for ln in new.lines}) / len(prev_codes)
    measured = {"lines_ratio": round(ratio, 3), "barcode_pp": round(100 * (a["barcode"] - b["barcode"]), 1),
                "no_price_pp": round(100 * (a["no_price"] - b["no_price"]), 1), "codes_in_common": round(common, 3)}
    ok = (0.6 <= ratio <= 1.8 and abs(measured["barcode_pp"]) <= 25 and measured["no_price_pp"] <= 15
          and common >= 0.5)
    return CheckResult(3, "structure", ok, measured)


# --- 5. variação das mesmas linhas ------------------------------------------------------------------------------

def check_price_change(new: ParsedList, previous: ParsedList | None) -> CheckResult:
    if previous is None or not previous.lines:
        return CheckResult(5, "price_change", None, {}, "primeira lista do fornecedor")
    before = {(ln.supplier_code, ln.description): ln.price for ln in previous.lines if ln.price}
    ratios = [ln.price / before[(ln.supplier_code, ln.description)] for ln in new.lines
              if ln.price and (ln.supplier_code, ln.description) in before]
    if len(ratios) < 5:
        return CheckResult(5, "price_change", None, {"same_lines": len(ratios)}, "poucas linhas em comum")
    median = statistics.median(ratios)
    factor_share = max(sum(1 for r in ratios if abs(r / f - 1) <= 0.05) / len(ratios) for f in SUSPICIOUS_FACTORS)
    ok = 0.92 <= median <= 1.5 and factor_share < 0.3
    return CheckResult(5, "price_change", ok, {"same_lines": len(ratios), "median": round(median, 3),
                                               "factor_share": round(factor_share, 3)})


# --- 4, 6 e 7: sobre o que a cascata identificou -----------------------------------------------------------------

@dataclass(frozen=True)
class Pair:
    """O que a cascata disse de uma linha: o produto, se confirmou, se os atributos são compatíveis."""

    supplier_code: str
    product_id: int | None
    confirmed: bool
    compatible: bool  # o que a linha diz (marca, tamanho, unidade…) bate com o produto
    unit_price: float | None  # preço da unidade de venda, com IVA
    cost: float | None  # custo do produto no cadastro
    level: int | None = None  # 1 é decisão humana: não é confirmação automática
    reason: str | None = None  # «price_far_from_cost»: a identidade bateu, só o preço destoou do custo

    @property
    def identified(self) -> bool:
        return self.confirmed or self.reason == "price_far_from_cost"


def check_price_vs_cost(pairs: list[Pair]) -> CheckResult:
    """Mede também os pares que a cascata deixou em revisão só pelo preço: se medisse só os confirmados, a lista
    inteira com um zero a mais não teria par confirmado nenhum e passaria sem ser medida."""
    ratios = [p.unit_price / p.cost for p in pairs if p.identified and p.unit_price and p.cost]
    if len(ratios) < 5:
        return CheckResult(4, "price_vs_cost", None, {"pairs": len(ratios)}, "poucos pares identificados")
    median = statistics.median(ratios)
    return CheckResult(4, "price_vs_cost", 0.8 <= median <= 1.5, {"pairs": len(ratios), "median": round(median, 3)})


def check_continuity(pairs: list[Pair], previous_pairs: list[Pair] | None) -> CheckResult:
    if not previous_pairs:
        return CheckResult(6, "continuity", None, {}, "primeira lista do fornecedor")
    before = {p.product_id for p in previous_pairs if p.confirmed}
    if not before:
        return CheckResult(6, "continuity", None, {}, "a anterior não tinha pares confirmados")
    now = {p.product_id for p in pairs if p.confirmed}
    share = len(before & now) / len(before)
    return CheckResult(6, "continuity", share >= 0.7, {"share": round(share, 3), "target": 0.95})


def check_zero(pairs: list[Pair]) -> CheckResult:
    """O critério de aceite: nenhum par confirmado automaticamente que contradiga o produto. A decisão humana
    (nível 1) fica fora: quando ela contradiz a leitura, quem errou foi o extrator, não o par."""
    bad = sum(1 for p in pairs if p.confirmed and p.level != 1 and not p.compatible)
    return CheckResult(7, "zero_check", bad == 0, {"incompatible_confirmed": bad})


def run_file_checks(new: ParsedList, previous: ParsedList | None) -> GateResult:
    return GateResult([check_count(new), check_fidelity(new), check_structure(new, previous),
                       check_price_change(new, previous)])


def run_gate(new: ParsedList, previous: ParsedList | None, pairs: list[Pair],
             previous_pairs: list[Pair] | None) -> GateResult:
    result = run_file_checks(new, previous)
    result.checks += [check_price_vs_cost(pairs), check_continuity(pairs, previous_pairs), check_zero(pairs)]
    result.checks.sort(key=lambda c: c.number)
    return result
