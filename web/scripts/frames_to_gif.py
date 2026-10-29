"""Monta o GIF da revisão a partir dos quadros do capture.mjs: reduz à metade (os quadros saem em 2x) e grava em loop.

    python frames_to_gif.py <pasta dos quadros> <arquivo .gif>
"""
import json
import sys
from pathlib import Path

from PIL import Image


def main(folder: Path, target: Path) -> None:
    durations = json.loads((folder / "durations.json").read_text(encoding="utf-8"))
    frames = []
    for i in range(len(durations)):
        image = Image.open(folder / f"{i:02d}.png").convert("RGB")
        image = image.resize((image.width // 2, image.height // 2), Image.Resampling.LANCZOS)
        frames.append(image.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    frames[0].save(target, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
    print(f"  {len(frames)} quadros, {target.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
