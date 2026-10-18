"""Regenkraeuseln: animierter, kachelbarer Normal-Map-Flipbook (4 x 4 Frames) fuer Pfuetzen.

Aufruf:
    blender -b --factory-startup --python vb_rain_ripples.py -- --out <SourceAssets/Export>

Physikalisch motiviert: Jeder Tropfen erzeugt einen gedaempften, sich ausbreitenden Wellenring.
Tropfen starten zeitversetzt, damit die Schleife (16 Frames) nahtlos laeuft; Positionen wickeln
an den Kachelkanten um (nahtlos kachelbar).
Ergebnis: SourceAssets/Export/Surfaces/RainRipples/T_VB_RainRipples_N.png (+ surface.json)
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vb_blender_lib as lib  # noqa: E402

FRAME_SIZE = 256          # Pixel pro Frame
GRID = 4                  # 4 x 4 Frames
TILE_METERS = 0.6         # eine Kachel = 60 cm
DROPS = 46                # Tropfen pro Kachel und Zyklus
LIFETIME = 0.55           # Anteil des Zyklus, in dem ein Ring sichtbar ist
MAX_RADIUS = 0.11         # Ringradius am Lebensende (Kachel-Einheiten ~ 6.6 cm)
WAVELENGTH = 0.022
RING_WIDTH = 0.018
NORMAL_STRENGTH = 2.2


def frame_height(u, v, t, drops):
    height = np.zeros_like(u)
    for x, y, phase, strength in drops:
        age = (t + phase) % 1.0
        if age > LIFETIME:
            continue
        life = age / LIFETIME
        dx = u - x
        dy = v - y
        dx -= np.round(dx)
        dy -= np.round(dy)
        r = np.sqrt(dx * dx + dy * dy)
        radius = life * MAX_RADIUS
        offset = r - radius
        envelope = np.exp(-(offset / RING_WIDTH) ** 2) * (1.0 - life) ** 2 * strength
        height += np.sin(offset * 2.0 * np.pi / WAVELENGTH) * envelope
    return height


def height_to_normal(height):
    step = 1.0 / FRAME_SIZE
    dhdx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) / (2.0 * step)
    dhdy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) / (2.0 * step)
    scale = NORMAL_STRENGTH * 0.004
    nx, ny, nz = -dhdx * scale, -dhdy * scale, np.ones_like(height)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx / length, ny / length, nz / length], axis=-1) * 0.5 + 0.5


def main():
    args = lib.cli_args()
    out_root = args.get("out")
    if not out_root:
        print("Aufruf: ... -- --out <SourceAssets/Export>")
        return 2

    rng = np.random.default_rng(311)
    drops = [(rng.random(), rng.random(), rng.random(), rng.uniform(0.5, 1.0)) for _ in range(DROPS)]

    coords = (np.arange(FRAME_SIZE) + 0.5) / FRAME_SIZE
    u, v = np.meshgrid(coords, coords)  # Zeile 0 = v klein (Blender-Konvention: unten)

    frames = GRID * GRID
    atlas_size = FRAME_SIZE * GRID
    atlas = np.zeros((atlas_size, atlas_size, 3), dtype=np.float32)
    for frame in range(frames):
        normal = height_to_normal(frame_height(u, v, frame / frames, drops))
        col, row = frame % GRID, frame // GRID
        # Atlas in Bildkoordinaten (Zeile 0 = oben), Frame 0 oben links - passt zu Unreal-UVs
        top = row * FRAME_SIZE
        atlas[top:top + FRAME_SIZE, col * FRAME_SIZE:(col + 1) * FRAME_SIZE] = np.flipud(normal)

    out_dir = os.path.join(out_root, "Surfaces", "RainRipples")
    os.makedirs(out_dir, exist_ok=True)
    # write_png erwartet Blender-Reihenfolge (unten zuerst) -> einmal spiegeln
    lib.write_png(os.path.join(out_dir, "T_VB_RainRipples_N.png"), np.flipud(atlas))
    with open(os.path.join(out_dir, "surface.json"), "w", encoding="utf-8") as handle:
        json.dump({"surface": "RainRipples", "flipbook": GRID, "frames": frames, "tile_meters": TILE_METERS,
                   "texture_only": True}, handle, indent=2)
    print("Regenkraeuseln erzeugt: %d Frames, %d px Atlas" % (frames, atlas_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
