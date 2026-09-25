"""Gelaende der ganzen Stadt (Phase 7): 12 x 7 Nanite-Kacheln a 600 m, Hoehenkarte fuer Meer/Schaum, Hoehenraster
fuer die Platzierung (Villen am Hang).

    blender -b --factory-startup --python vb_asset_cityterrain.py -- --out <SourceAssets/Export> [--preview <bild.png>]

Die Stadtebene (alle Bezirke ausser Monte Veyra) ist exakt flach (z = -0.05 m, Strassen liegen auf 0);
ebene Flaechen werden per "Planar Dissolve" zu wenigen grossen Dreiecken zusammengefasst -> kleine Dateien.
Plan und Masse kommen aus Content/Python/vb_cityplan.py (gleiche Quelle wie der Aufbau in Unreal).
"""

import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "Content", "Python"))
import vb_blender_lib as lib  # noqa: E402
import vb_cityplan as plan  # noqa: E402
from vb_asset_coast import fbm, smoothstep  # noqa: E402

CELL = 5.0
HEIGHT_MIN, HEIGHT_RANGE = -30.0, 180.0      # Kodierung der Hoehenkarte (m)
MAP_EXTENT = 3600.0                           # Hoehenkarte deckt +/- 3600 m ab (quadratisch)


def plateau_distance(x, y):
    distance = np.full_like(x, np.inf)
    for district in plan.DISTRICTS:
        if district.get("hills"):
            continue
        x0, x1, y0, y1 = district["rect"]
        if y0 <= -79.0:
            y0 = plan.QUAY_Y       # Promenade bis zur Kaimauer gehoert zur Ebene
        dx = np.maximum(np.maximum(x0 - x, x - x1), 0.0)
        dy = np.maximum(np.maximum(y0 - y, y - y1), 0.0)
        distance = np.minimum(distance, np.hypot(dx, dy))
    return distance


def terrain_height(x, y):
    d_plateau = plateau_distance(x, y)

    # Hinterland: Huegelkette im Norden, Monte Veyra im Nordosten, Anhoehe im Westen
    base = 1.5 + 2.5 * fbm(x, y, 150.0, seed=3) + 0.012 * np.maximum(y - 1900.0, 0.0)
    north = 70.0 * smoothstep(1950.0, 2600.0, y) * (0.7 + 0.6 * fbm(x, y, 400.0, seed=9))
    monte = 115.0 * np.exp(-(((x - 2350.0) / 750.0) ** 2 + ((y - 1750.0) / 620.0) ** 2)) * (0.85 + 0.3 * fbm(x, y, 220.0, seed=13))
    west = 45.0 * np.exp(-(((x + 3500.0) / 500.0) ** 2 + ((y - 1400.0) / 700.0) ** 2))
    inland = base + north + monte + west
    land = -0.05 + (inland + 0.05) * smoothstep(0.0, 70.0, d_plateau)

    # Kueste (Meer im Sueden)
    s_quay = y - plan.QUAY_Y
    natural = plan.QUAY_Y + 20.0 * np.sin(x / 60.0) + 8.0 * np.sin(x / 23.0 + 1.3) - 10.0
    s_nat = y - natural

    def seabed(dist):
        return np.maximum(-6.0 - 0.03 * dist - 6.0 * smoothstep(0.0, 400.0, dist), -28.0)

    h_quay = np.where(s_quay >= 0, land, seabed(np.maximum(-s_quay, 0.0)))
    beach_profile = -0.6 - 0.07 * np.maximum(-s_quay, 0.0)
    h_beach = np.where(s_quay >= 0, land, np.maximum(beach_profile, seabed(np.maximum(-s_quay, 0.0))))
    cliff_top = np.maximum(land, 3.0 + 4.0 * fbm(x, y, 40.0, seed=21))
    h_cliff = np.where(s_nat >= 0, cliff_top,
                       cliff_top + (seabed(np.maximum(-s_nat, 0.0)) - cliff_top) * smoothstep(0.0, 12.0, -s_nat))

    def band(a, b, soft=30.0):
        return smoothstep(a - soft, a, x) * (1.0 - smoothstep(b, b + soft, x))

    # Gewichte ohne Luecken: Stadtkueste (Kai + Strand) zwischen Hafen-Anfang und Marina-Ende, sonst Fels
    w_city = band(plan.HARBOR[0], plan.MARINA[1])
    w_beach = band(plan.BEACH[0] + 30.0, plan.BEACH[1] - 30.0) * w_city
    w_quay = w_city - w_beach
    w_cliff = 1.0 - w_city
    return w_quay * h_quay + w_beach * h_beach + w_cliff * h_cliff


def build_tiles(material):
    x_min, x_max = plan.TERRAIN_X
    y_min, y_max = plan.TERRAIN_Y
    tile = plan.TERRAIN_TILE
    per_tile = int(tile / CELL)
    nx, ny = int((x_max - x_min) / tile), int((y_max - y_min) / tile)
    tiles = []
    for ti in range(nx):
        for tj in range(ny):
            xs = x_min + ti * tile + np.arange(per_tile + 1) * CELL
            ys = y_min + tj * tile + np.arange(per_tile + 1) * CELL
            gx, gy = np.meshgrid(xs, ys, indexing="ij")
            heights = terrain_height(gx, gy)
            bm = bmesh.new()
            uv = bm.loops.layers.uv.new("UVMap")
            verts = [[bm.verts.new((float(xs[i]), float(ys[j]), float(heights[i, j]))) for j in range(per_tile + 1)]
                     for i in range(per_tile + 1)]
            for i in range(per_tile):
                for j in range(per_tile):
                    face = bm.faces.new((verts[i][j], verts[i + 1][j], verts[i + 1][j + 1], verts[i][j + 1]))
                    for loop in face.loops:
                        loop[uv].uv = (loop.vert.co.x, loop.vert.co.y)
            # Ebene Flaechen zusammenfassen (Stadtebene, gleichmaessige Haenge); braucht aktuelle Normalen
            bm.normal_update()
            bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.25), use_dissolve_boundaries=False,
                                     verts=bm.verts, edges=bm.edges)
            obj = lib.bm_to_object(bm, "SM_VB_CityTerrain_%d_%d" % (ti, tj))
            obj.data.materials.append(material)
            lib.shade_smooth(obj, 180.0)
            lib.mirror_to_unreal(obj)
            tiles.append(lib.finalize(obj, "Terrain", nanite=True, collision="complex"))
    return tiles


def write_maps(out_root):
    folder = os.path.join(out_root, "Surfaces", "CityTerrain")
    os.makedirs(folder, exist_ok=True)
    size = 1024
    sample = np.linspace(-MAP_EXTENT, MAP_EXTENT, size)
    sx, sy = np.meshgrid(sample, sample, indexing="xy")
    encoded = np.clip((terrain_height(sx, sy) - HEIGHT_MIN) / HEIGHT_RANGE, 0.0, 1.0)
    rgb = np.stack([encoded, encoded, encoded], axis=-1)
    lib.write_png(os.path.join(folder, "T_VB_CityTerrain_H.png"), np.flipud(rgb), sixteen_bit=True)
    with open(os.path.join(folder, "surface.json"), "w", encoding="utf-8") as handle:
        json.dump({"surface": "CityTerrain", "texture_only": True, "extent_m": MAP_EXTENT, "height_min_m": HEIGHT_MIN,
                   "height_range_m": HEIGHT_RANGE, "sea_level_m": plan.SEA_LEVEL}, handle, indent=2)

    # Hoehenraster (16 m) fuer die Platzierung in Unreal
    step = 16.0
    xs = np.arange(plan.TERRAIN_X[0], plan.TERRAIN_X[1] + 0.1, step)
    ys = np.arange(plan.TERRAIN_Y[0], plan.TERRAIN_Y[1] + 0.1, step)
    gx, gy = np.meshgrid(xs, ys, indexing="xy")
    heights = np.round(terrain_height(gx, gy), 2)
    terrain_dir = os.path.join(out_root, "Terrain")
    os.makedirs(terrain_dir, exist_ok=True)
    with open(os.path.join(terrain_dir, "city_heights.json"), "w", encoding="utf-8") as handle:
        json.dump({"x0": float(xs[0]), "y0": float(ys[0]), "step": step, "nx": len(xs), "ny": len(ys),
                   "heights": heights.flatten().tolist()}, handle, separators=(",", ":"))


def preview(path):
    """Hoehenrelief als Bild (Draufsicht, Norden oben)."""
    w, h = 1440, 840
    xs = np.linspace(plan.TERRAIN_X[0], plan.TERRAIN_X[1], w)
    ys = np.linspace(plan.TERRAIN_Y[0], plan.TERRAIN_Y[1], h)
    gx, gy = np.meshgrid(xs, ys, indexing="xy")
    z = terrain_height(gx, gy)
    dzdx = np.gradient(z, axis=1) / (xs[1] - xs[0])
    dzdy = np.gradient(z, axis=0) / (ys[1] - ys[0])
    shade = np.clip(0.6 + (-dzdx * 0.7 + dzdy * 0.7) * 1.5, 0.2, 1.0)
    color = np.where(z[..., None] < plan.SEA_LEVEL, np.array([0.1, 0.25, 0.4]),
                     np.where(z[..., None] < 0.5, np.array([0.75, 0.72, 0.62]),
                              np.array([0.35, 0.5, 0.25]) * (1.0 - np.clip(z[..., None] / 150.0, 0, 0.6))
                              + np.array([0.5, 0.45, 0.4]) * np.clip(z[..., None] / 150.0, 0, 0.6)))
    lib.write_png(path, lib.linear_to_srgb(color * shade[..., None]))


def main():
    args = lib.cli_args()
    lib.reset_scene()
    if args.get("preview"):
        preview(os.path.abspath(args["preview"]))
        if not args.get("out"):
            return 0
    material = lib.make_material("Terrain", (0.3, 0.3, 0.2), 0.9, shared_material="Terrain")
    out = os.path.abspath(args.get("out", os.path.join(os.getcwd(), "SourceAssets", "Export")))
    tiles = build_tiles(material)
    total = sum(lib.vb_blender_export.triangle_count(t) for t in tiles)
    print("%d Kacheln, %d Dreiecke" % (len(tiles), total))
    write_maps(out)
    if args.get("out"):
        exported, _ = lib.export(out, only=[t.name for t in tiles])
        return 0 if exported == len(tiles) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
