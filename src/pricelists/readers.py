"""Os leitores: o arquivo do fornecedor vira linhas (código, código de barras, descrição, preço).

O leitor não interpreta a linha (isso é do extrator) e não decide se a leitura está boa (isso é do portão). Ele acha
as colunas pelo rótulo, não pela posição, e diz de onde tirou cada coisa, para o portão poder conferir.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
from openpyxl import load_workbook

from .extract import normalize

MONTHS = {"ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
          "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12}
_PERIOD = re.compile(r"\b(" + "|".join(MONTHS) + r")\s+(\d{4})\b")
_ARS = re.compile(r"\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)")


@dataclass(frozen=True)
class RawLine:
    row: int  # a linha da planilha, ou a ordem da linha no PDF
    supplier_code: str
    barcode: str
    description: str
    price: float | None
    case_units: int | None  # unidades da caixa fechada, quando a lista informa à parte (o preço segue da unidade)
    section: str


@dataclass
class ParsedList:
    path: Path
    file_format: str
    sha256: str
    period: str | None  # «2026-10», do título da lista
    vat_included: bool | None  # o que a própria lista declara; None quando não diz
    columns: dict[str, str] = field(default_factory=dict)  # papel -> rótulo de onde saiu (planilha)
    lines: list[RawLine] = field(default_factory=list)


def file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_ars(text: str) -> float:
    """«4.850,00» ou «4850,5» -> 4850.0 / 4850.5"""
    return float(text.replace(".", "").replace(",", "."))


def _period(text: str) -> str | None:
    if m := _PERIOD.search(normalize(text)):
        return f"{m.group(2)}-{MONTHS[m.group(1)]:02d}"
    return None


def _vat(text: str) -> bool | None:
    t = normalize(text).replace(" ", "")
    if "S/IVA" in t or "SINIVA" in t:
        return False
    if "C/IVA" in t or "CONIVA" in t or "IVAINCLUIDO" in t:
        return True
    return None


# o papel de cada coluna, pelo rótulo (normalizado, sem pontuação)
_ROLES = (
    ("barcode", re.compile(r"^(EAN|EAN13|COD(IGO)? ?(DE )?BARRAS)$")),
    ("code", re.compile(r"^(COD|CODIGO|COD ART|CODIGO ARTICULO|ARTICULO COD)$")),
    ("description", re.compile(r"^(DESCRIPCION|ARTICULO|PRODUCTO|DETALLE)$")),
    ("case_units", re.compile(r"(BULTO|UNID X CAJA|UNIDADES X CAJA)")),
    ("price", re.compile(r"^PRECIO")),
    ("section", re.compile(r"^(RUBRO|SECCION|CATEGORIA)$")),
)


def _role(label: str) -> str | None:
    clean = " ".join(re.sub(r"[^A-Z0-9]+", " ", normalize(label)).split())
    return next((role for role, rx in _ROLES if rx.search(clean)), None)


def read_xlsx(path: Path) -> ParsedList:
    ws = load_workbook(path, data_only=True, read_only=True).active
    rows = list(ws.iter_rows(values_only=True))
    parsed = ParsedList(Path(path), "xlsx", file_hash(path), None, None)
    header_at = None
    for i, row in enumerate(rows):
        roles = {_role(str(v)): (j, str(v)) for j, v in enumerate(row) if v is not None and _role(str(v))}
        if "description" in roles and "price" in roles:
            header_at, columns = i, roles
            break
        text = " ".join(str(v) for v in row if v is not None)
        parsed.period = parsed.period or _period(text)
        parsed.vat_included = parsed.vat_included if parsed.vat_included is not None else _vat(text)
    if header_at is None:
        return parsed  # sem cabeçalho reconhecível: zero linhas, e o portão segura
    parsed.columns = {role: label for role, (_, label) in columns.items()}
    vat_in_header = _vat(columns["price"][1])
    if vat_in_header is not None:
        parsed.vat_included = vat_in_header

    def cell(row, role):
        j = columns.get(role, (None,))[0]
        return row[j] if j is not None and j < len(row) else None

    for n, row in enumerate(rows[header_at + 1:], start=header_at + 2):
        description = cell(row, "description")
        if description is None or not str(description).strip():
            continue
        price = cell(row, "price")
        if isinstance(price, str):
            price = parse_ars(price.replace("$", "").strip()) if price.strip() else None
        units = cell(row, "case_units")
        code = cell(row, "code")
        barcode = cell(row, "barcode")
        parsed.lines.append(RawLine(
            row=n, supplier_code="" if code is None else str(code).strip(),
            barcode="" if barcode is None else str(barcode).strip(), description=str(description).strip(),
            price=float(price) if price is not None else None,
            case_units=int(units) if isinstance(units, (int, float)) else None,
            section=str(cell(row, "section") or "").strip(),
        ))
    return parsed


_PDF_LINE = re.compile(r"^(?P<code>\S*\d\S*)\s+(?P<desc>.+?)\s+" + _ARS.pattern + r"$")


def read_pdf(path: Path) -> ParsedList:
    parsed = ParsedList(Path(path), "pdf", file_hash(path), None, None)
    section = ""
    n = 0
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for text in (page.extract_text() or "").splitlines():
                text = text.strip()
                if m := _PDF_LINE.match(text):
                    n += 1
                    parsed.lines.append(RawLine(n, m.group("code"), "", m.group("desc").strip(),
                                                parse_ars(m.group(3)), None, section))
                    continue
                parsed.period = parsed.period or _period(text)
                if parsed.vat_included is None:
                    parsed.vat_included = _vat(text)
                if text.isupper() and len(text.split()) <= 3 and not any(c.isdigit() for c in text):
                    section = text  # o título de seção: uma ou duas palavras em maiúsculas, sem preço
    return parsed


def read_list(path: Path) -> ParsedList:
    suffix = Path(path).suffix.lower()
    if suffix == ".xlsx":
        return read_xlsx(path)
    if suffix == ".pdf":
        return read_pdf(path)
    raise ValueError(f"formato sem leitor: {suffix} (a foto entra com a leitura de IA)")
