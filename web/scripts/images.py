"""As imagens do capture.mjs, prontas para o README.

    python images.py png <arquivo.png> ...           reduz a 256 cores (a tela escura cabe nelas) e otimiza
    python images.py gif <pasta dos quadros> <.gif>  monta o GIF: quadros pela metade (saem em 2x), em loop
"""
import json
import sys
from pathlib import Path

from PIL import Image


def palette(image: Image.Image) -> Image.Image:
    return image.convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)


def png(files: list[Path]) -> None:
    for path in files:
        palette(Image.open(path)).save(path, optimize=True)
        print(f"  {path.name}: {path.stat().st_size // 1024} KB")


def gif(folder: Path, target: Path) -> None:
    durations = json.loads((folder / "durations.json").read_text(encoding="utf-8"))
    frames = []
    for i in range(len(durations)):
        image = Image.open(folder / f"{i:02d}.png")
        frames.append(palette(image.resize((image.width // 2, image.height // 2), Image.Resampling.LANCZOS)))
    frames[0].save(target, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
    print(f"  {target.name}: {len(frames)} quadros, {target.stat().st_size // 1024} KB")


if __name__ == "__main__":
    command, *rest = sys.argv[1:]
    if command == "png":
        png([Path(p) for p in rest])
    else:
        gif(Path(rest[0]), Path(rest[1]))
