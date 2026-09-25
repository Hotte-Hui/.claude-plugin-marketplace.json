"""Himmel- und Regentexturen (Phase 6).

    blender -b --factory-startup --python vb_sky_textures.py -- --out <SourceAssets/Export>

T_VB_Sky_D       Sternenhimmel (equirektangulaer 4096 x 2048): ~9000 Sterne nach Helligkeitsverteilung
                 (viele schwache, wenige helle), Sternfarben nach Temperatur, schwaches Milchstrassenband.
T_VB_RainStreaks_M  Regenschlieren (kachelbar 512 x 1024, linear): duenne, unterschiedlich lange Tropfenspuren
                 in zwei Tiefenebenen (R = nah/kraeftig, G = fern/fein).
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vb_blender_lib as lib  # noqa: E402


def star_color(temperature):
    """Grobe Schwarzkoerper-Farbe (linear) fuer 3000..12000 K."""
    t = np.clip((temperature - 3000.0) / 9000.0, 0.0, 1.0)
    red = np.interp(t, [0.0, 0.35, 1.0], [1.0, 1.0, 0.72])
    green = np.interp(t, [0.0, 0.35, 1.0], [0.62, 0.92, 0.8])
    blue = np.interp(t, [0.0, 0.35, 1.0], [0.35, 0.85, 1.0])
    return np.stack([red, green, blue], axis=-1)


def star_map(width=4096, height=2048, count=9000, seed=11):
    rng = np.random.default_rng(seed)
    image = np.zeros((height, width, 3), dtype=np.float32)

    # Gleichverteilt auf der Kugel
    z = rng.uniform(-1.0, 1.0, count)
    phi = rng.uniform(0.0, 2 * np.pi, count)
    lat = np.arcsin(z)
    u = phi / (2 * np.pi)
    v = (lat + np.pi / 2) / np.pi

    # Helligkeit: Potenzverteilung (Magnitude), wenige sehr helle Sterne
    magnitude = rng.power(0.25, count)
    brightness = 0.04 + 1.6 * magnitude ** 3
    colors = star_color(rng.normal(6000.0, 2200.0, count)) * brightness[:, None]

    xs = u * width
    ys = v * height
    for x, y, c, b in zip(xs, ys, colors, brightness):
        # Breitengrad-Verzerrung: horizontale Ausdehnung waechst Richtung Pole
        stretch = 1.0 / max(np.cos((y / height - 0.5) * np.pi), 0.08)
        radius = 0.6 + 0.9 * min(b, 1.0)
        rx = int(np.ceil(radius * stretch * 2)) + 1
        ry = int(np.ceil(radius * 2)) + 1
        x0, y0 = int(x), int(y)
        for dy in range(-ry, ry + 1):
            yy = y0 + dy
            if yy < 0 or yy >= height:
                continue
            for dx in range(-rx, rx + 1):
                xx = (x0 + dx) % width
                d2 = ((xx + 0.5 - x) / stretch) ** 2 + (yy + 0.5 - y) ** 2
                if abs(xx + 0.5 - x) > width / 2:
                    continue
                weight = np.exp(-d2 / (2 * (radius * 0.5) ** 2))
                image[yy, xx] += c * weight

    # Milchstrasse: geneigtes Band mit fleckiger Struktur
    uu, vv = np.meshgrid((np.arange(width) + 0.5) / width, (np.arange(height) + 0.5) / height)
    lon = uu * 2 * np.pi
    latg = (vv - 0.5) * np.pi
    direction = np.stack([np.cos(latg) * np.cos(lon), np.cos(latg) * np.sin(lon), np.sin(latg)], axis=-1)
    pole = np.array([0.3, -0.5, 0.81])
    pole /= np.linalg.norm(pole)
    band = np.exp(-(direction @ pole) ** 2 / (2 * 0.12 ** 2))
    clump = np.zeros_like(band)
    for octave in range(5):
        frequency = 3 * 2 ** octave
        phase = rng.uniform(0, 2 * np.pi, 3)
        clump += (np.sin(direction[..., 0] * frequency + phase[0]) * np.sin(direction[..., 1] * frequency + phase[1])
                  * np.sin(direction[..., 2] * frequency + phase[2])) / (octave + 1)
    clump = np.clip(0.45 + clump * 0.8, 0, 1)
    glow = band * clump * 0.025
    image += glow[..., None] * np.array([0.85, 0.8, 0.75])

    # Viele schwache Sterne im Band (koernige Struktur statt Schleier), je ein Pixel
    faint = 160000
    fz = rng.uniform(-1.0, 1.0, faint)
    fphi = rng.uniform(0.0, 2 * np.pi, faint)
    fdir = np.stack([np.sqrt(1 - fz ** 2) * np.cos(fphi), np.sqrt(1 - fz ** 2) * np.sin(fphi), fz], axis=-1)
    keep = rng.uniform(0, 1, faint) < np.exp(-(fdir @ pole) ** 2 / (2 * 0.1 ** 2)) * 0.9 + 0.05
    fx = ((fphi[keep] / (2 * np.pi)) * width).astype(int) % width
    fy = np.clip(((np.arcsin(fz[keep]) + np.pi / 2) / np.pi * height).astype(int), 0, height - 1)
    fb = rng.uniform(0.01, 0.08, keep.sum())
    np.add.at(image, (fy, fx), (star_color(rng.normal(5500.0, 1500.0, keep.sum())) * fb[:, None]).astype(np.float32))

    # Blender-Zeilenreihenfolge (unten zuerst) fuer write_png: v = 0 ist Suedpol -> unten
    return image


def rain_streaks(width=512, height=1024, seed=3):
    rng = np.random.default_rng(seed)
    image = np.zeros((height, width, 3), dtype=np.float32)
    for channel, count, length_range, width_px, strength in ((0, 380, (60, 190), 1.1, 1.0), (1, 900, (25, 90), 0.7, 0.6)):
        for _ in range(count):
            x = rng.uniform(0, width)
            y0 = rng.uniform(0, height)
            length = rng.uniform(*length_range)
            b = strength * rng.uniform(0.35, 1.0)
            cols = np.arange(int(x) - 2, int(x) + 3)
            for col in cols:
                weight_x = np.exp(-((col + 0.5 - x) ** 2) / (2 * (width_px * 0.5) ** 2))
                if weight_x < 0.02:
                    continue
                rows = np.arange(int(y0), int(y0 + length))
                t = (rows - y0) / length
                profile = np.sin(np.pi * np.clip(t, 0, 1)) ** 0.7 * (0.55 + 0.45 * t)   # Kopf (unten) heller
                image[rows % height, col % width, channel] += b * weight_x * profile
    return np.clip(image, 0, 1)


def main():
    args = lib.cli_args()
    out = args.get("out")
    folder = os.path.join(out, "Surfaces", "Sky")
    os.makedirs(folder, exist_ok=True)

    stars = star_map()
    lib.write_png(os.path.join(folder, "T_VB_Sky_D.png"), lib.linear_to_srgb(np.clip(stars, 0, 1)))
    rain = rain_streaks()
    lib.write_png(os.path.join(folder, "T_VB_RainStreaks_M.png"), rain)

    with open(os.path.join(folder, "surface.json"), "w", encoding="utf-8") as handle:
        json.dump({"surface": "Sky", "texture_only": True}, handle, indent=2)
    if args.get("preview"):
        lib.write_png(args["preview"], lib.linear_to_srgb(np.clip(stars[700:1400, 1500:2900] * 3, 0, 1)))
    print("Himmel-Texturen erzeugt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
