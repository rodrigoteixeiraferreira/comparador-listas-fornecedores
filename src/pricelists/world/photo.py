"""A lista impressa e fotografada: a página com a fonte embutida do Pillow, um pouco torta, com sombra e grão.

A foto da vitrine (semente 1) está gravada em data/showcase/, com as duas leituras da IA em data/recorded/. As outras
sementes geram a foto na hora, mas não têm leitura gravada: o processamento pula a lista de foto sem leitura.
"""
from __future__ import annotations

import hashlib
import json
import random
import shutil
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..reference import DATA_DIR, Reference
from .build import PriceList
from .spec import MONTH_NAMES_ES

SHOWCASE = DATA_DIR / "showcase"


def _ars(value: float) -> str:
    return "$ " + f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def content_hash(price_list: PriceList) -> str:
    """O que a foto mostra, independente dos bytes da imagem (que mudam de uma máquina para outra)."""
    text = "\n".join(f"{ln.supplier_code}|{ln.description}|{ln.price:.2f}" for ln in price_list.lines)
    return hashlib.sha256(f"{price_list.name}\n{text}".encode()).hexdigest()


def render_page(price_list: PriceList, ref: Reference) -> Image.Image:
    width, margin, line_h = 1400, 70, 40
    name = "".join(c for c in unicodedata.normalize("NFKD", ref.suppliers[price_list.supplier].name)
                   if not unicodedata.combining(c))  # a fonte embutida não tem acento
    title = f"{name.upper()} - Lista de precios {MONTH_NAMES_ES[price_list.period]}"
    rows = [("title", title), ("small", "Precios con IVA incluido. Consultar por cantidad."), ("gap", "")]
    section = None
    for ln in price_list.lines:
        if ln.section != section:
            section = ln.section
            rows.append(("section", ref.sections[section].name_es))
        rows.append(("line", ln))
    height = margin * 2 + line_h * (len(rows) + 1)
    page = Image.new("L", (width, height), 246)
    draw = ImageDraw.Draw(page)
    font = ImageFont.load_default(size=27)
    bold = ImageFont.load_default(size=34)
    y = margin
    for kind, item in rows:
        if kind == "title":
            draw.text((margin, y), item, fill=25, font=bold)
        elif kind in ("small", "section"):
            draw.text((margin, y + 6), item, fill=40, font=font)
            if kind == "section":
                draw.line((margin, y + line_h - 2, width - margin, y + line_h - 2), fill=120, width=2)
        elif kind == "line":
            draw.text((margin, y), item.supplier_code, fill=30, font=font)
            draw.text((margin + 90, y), item.description, fill=30, font=font)
            price = _ars(item.price)
            draw.text((width - margin - draw.textlength(price, font=font), y), price, fill=30, font=font)
        y += line_h
    return page


def photograph(page: Image.Image, seed: str) -> Image.Image:
    """A página vira foto: girada de leve sobre a mesa, com luz desigual e grão."""
    rng = random.Random(seed)
    w, h = page.size
    shade = Image.linear_gradient("L").resize((w, h)).point(lambda v: 255 - v // 6)
    lit = Image.composite(page, Image.new("L", page.size, 200), shade)
    photo = lit.rotate(rng.uniform(-1.4, 1.4), resample=Image.Resampling.BICUBIC, expand=True, fillcolor=70)
    grain = Image.frombytes("L", photo.size, rng.randbytes(photo.size[0] * photo.size[1]))
    photo = Image.blend(photo, grain, 0.06).filter(ImageFilter.GaussianBlur(0.7))
    return photo.convert("RGB")


def write_photo(price_list: PriceList, path: Path, ref: Reference) -> Path:
    """Grava a foto da lista; se ela é a da vitrine (mesmo conteúdo), copia a foto gravada, com os mesmos bytes."""
    showcase = SHOWCASE / f"{price_list.name}.json"
    if showcase.exists() and json.loads(showcase.read_text(encoding="utf-8"))["content_sha256"] == \
            content_hash(price_list):
        shutil.copyfile(SHOWCASE / f"{price_list.name}.jpg", path)
        return path
    photograph(render_page(price_list, ref), price_list.name).save(path, quality=85)
    return path
