"""Wasser-Texturen: kachelbare Ozean-Normal-Map (Wellenspektrum) + Schaum-Maske.

    blender -b --factory-startup --python vb_water_textures.py -- --out <SourceAssets/Export>

Wellen: Summe vieler gerichteter Sinuswellen mit ganzzahligen Wellenzahlen (dadurch nahtlos kachelbar),
Amplituden nach einem Phillips-aehnlichen Spektrum (lange Wellen gross, kurze klein), Hauptrichtung Wind.
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vb_blender_lib as lib  # noqa: E402

SIZE = 1024


def ocean_height(rng, u, v, waves=180, wind=(1.0, 0.35)):
    wind = np.array(wind) / np.linalg.norm(wind)
    height = np.zeros_like(u)
    for _ in range(waves):
        while True:
            kx, ky = rng.integers(-24, 25), rng.integers(-24, 25)
            k = np.hypot(kx, ky)
            if k >= 1:
                break
        direction = np.array([kx, ky]) / k
        alignment = max(np.dot(direction, wind), 0.0) ** 2 + 0.05
        amplitude = alignment / (k ** 1.6)
        phase = rng.uniform(0, 2 * np.pi)
        height += amplitude * np.sin(2 * np.pi * (kx * u + ky * v) + phase)
    return height


def main():
    args = lib.cli_args()
    out = args.get("out")
    rng = np.random.default_rng(77)
    coords = (np.arange(SIZE) + 0.5) / SIZE
    u, v = np.meshgrid(coords, coords)

    height = ocean_height(rng, u, v)
    step = 1.0 / SIZE
    dhdx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) / (2 * step)
    dhdy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) / (2 * step)
    scale = 0.9 / np.percentile(np.hypot(dhdx, dhdy), 99)
    n = np.stack([-dhdx * scale, -dhdy * scale, np.ones_like(height)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)

    folder = os.path.join(out, "Surfaces", "Ocean")
    os.makedirs(folder, exist_ok=True)
    rgb = np.concatenate([n * 0.5 + 0.5, np.ones_like(height)[..., None]], axis=-1)
    lib.write_png(os.path.join(folder, "T_VB_Ocean_N.png"), rgb)

    # Schaum: Wellenkaemme (hohe Stellen) + feines Rauschen, R-Kanal
    crest = np.clip((height - np.percentile(height, 70)) / (np.percentile(height, 99) - np.percentile(height, 70)), 0, 1)
    fine = ocean_height(np.random.default_rng(5), u * 1.0, v * 1.0, waves=120)
    fine = (fine - fine.min()) / (fine.max() - fine.min())
    foam = np.clip(crest * 0.7 + (fine > 0.62) * 0.5, 0, 1)
    mask = np.stack([foam, foam, foam, np.ones_like(foam)], axis=-1)
    lib.write_png(os.path.join(folder, "T_VB_OceanFoam_M.png"), mask)

    with open(os.path.join(folder, "surface.json"), "w", encoding="utf-8") as handle:
        json.dump({"surface": "Ocean", "texture_only": True, "tile_meters": 40.0}, handle, indent=2)
    print("Ozean-Texturen erzeugt (%d px)" % SIZE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
