"""Gera o mundo fictício em disco.

    python -m pricelists.world --seed 1 --out generated/seed-1
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from . import build_world, write_world


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    out = args.out or Path("generated") / f"seed-{args.seed}"
    world = build_world(args.seed)
    write_world(world, out)
    print(f"semente {args.seed}: {len(world.market)} produtos no mercado, {len(world.catalog)} no cadastro da loja")
    for pl in world.lists:
        traps = Counter(t for line in pl.lines for t in line.traps)
        matched = sum(1 for line in pl.lines if line.catalog_id)
        print(f"  {pl.name}: {len(pl.lines)} linhas, {matched} da loja; armadilhas: "
              + ", ".join(f"{k} {v}" for k, v in sorted(traps.items())))
    print(f"gravado em {out}")


if __name__ == "__main__":
    main()
