"""Veyra Bay Kueste (Phase 4): Gelaende-Kacheln, Hoehenkarte, Meeresflaeche, Kaimauer, Poller, Gelaender, Promenade.

    blender -b --factory-startup --python vb_asset_coast.py -- --out <SourceAssets/Export> [--blend <datei.blend>]

Alle Masse in UNREAL-Koordinaten (Meter): X Osten, Y Norden... genauer: +Y = Richtung Innenstadt/Hinterland,
das Meer liegt im Sueden (-Y). Meeresspiegel -2.5 m (Strassen bei 0).
Stadtraster (muss zu vb_setup/vb_district passen):
    Ring-Gehweg aussen:    |x| <= 129.12, y <= 84.12
    Promenade:             y zwischen -94.12 (Kaimauer) und -84.12
    Hafenkai:              x < 40 ; Sandstrand: 40 <= x <= 420 ; sonst Felskueste
"""

import json
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vb_blender_lib as lib  # noqa: E402

EXTENT = 800.0          # Gelaende von -800 .. +800 m
CELL = 4.0              # Rasterweite
TILES = 4               # 4 x 4 Kacheln
SEA_LEVEL = -2.5
CITY_X = 129.12
CITY_NORTH = 84.12
QUAY_Y = -94.12
HARBOR_EAST = 40.0
BEACH_EAST = 420.0
HEIGHT_MIN, HEIGHT_RANGE = -30.0, 60.0   # Kodierung der Hoehenkarte


# ---------------------------------------------------------------------------
# Gelaendefunktion (vektorisiert)
# ---------------------------------------------------------------------------
def _value_noise(x, y, scale, seed):
    rng = np.random.default_rng(seed)
    table = rng.random((64, 64))
    fx, fy = x / scale, y / scale
    ix, iy = np.floor(fx).astype(int), np.floor(fy).astype(int)
    tx, ty = fx - ix, fy - iy
    tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)

    def t(a, b):
        return table[a % 64, b % 64]

    top = t(ix, iy) + (t(ix + 1, iy) - t(ix, iy)) * tx
    bottom = t(ix, iy + 1) + (t(ix + 1, iy + 1) - t(ix, iy + 1)) * tx
    return top + (bottom - top) * ty


def fbm(x, y, scale, octaves=5, seed=1):
    total, amplitude, norm = np.zeros_like(x), 1.0, 0.0
    for octave in range(octaves):
        total += _value_noise(x, y, scale / (2 ** octave), seed + octave) * amplitude
        norm += amplitude
        amplitude *= 0.5
    return total / norm


def smoothstep(e0, e1, v):
    t = np.clip((v - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def terrain_height(x, y):
    # Abstand zum Stadtrechteck (inkl. Promenade)
    dx = np.maximum(np.abs(x) - CITY_X, 0.0)
    dy = np.maximum(y - CITY_NORTH, 0.0) + np.maximum(QUAY_Y - y, 0.0)
    city_distance = np.hypot(dx, dy)

    # Hinterland: sanft ansteigend, Huegel im Norden
    inland = 1.5 + 2.5 * fbm(x, y, 120.0, seed=3) + 0.05 * np.maximum(y - CITY_NORTH, 0.0)
    inland += 38.0 * smoothstep(180.0, 650.0, y) * (0.6 + 0.8 * fbm(x, y, 260.0, seed=9))
    land = -0.05 + (inland + 0.05) * smoothstep(0.0, 70.0, city_distance)

    # Drei vollstaendige Kuestenprofile, entlang X weich gewichtet (keine Spruenge an den Uebergaengen)
    s_quay = y - QUAY_Y                                            # > 0 an Land
    natural_coast = QUAY_Y + 14.0 * np.sin(x / 45.0) + 7.0 * np.sin(x / 17.0 + 1.3) - 6.0
    s_nat = y - natural_coast

    def seabed(dist):
        return np.maximum(-6.0 - 0.03 * dist - 6.0 * smoothstep(0.0, 400.0, dist), -28.0)

    # Hafen: senkrechte Kaimauer (Asset) -> Meeresboden direkt davor
    h_harbor = np.where(s_quay >= 0, land, seabed(np.maximum(-s_quay, 0.0)))
    # Strand: Sand faellt mit 7 % vom Mauerfuss (-0.6 m) ins Meer
    beach_profile = -0.6 - 0.07 * np.maximum(-s_quay, 0.0)
    h_beach = np.where(s_quay >= 0, land, np.maximum(beach_profile, seabed(np.maximum(-s_quay, 0.0))))
    # Felskueste: Steilabfall ueber ~12 m
    cliff_top = np.maximum(land, 3.0 + 4.0 * fbm(x, y, 40.0, seed=21))
    h_cliff = np.where(s_nat >= 0, cliff_top,
                       cliff_top + (seabed(np.maximum(-s_nat, 0.0)) - cliff_top) * smoothstep(0.0, 12.0, -s_nat))

    w_harbor = smoothstep(-CITY_X - 25.0, -CITY_X, x) * (1.0 - smoothstep(HARBOR_EAST, HARBOR_EAST + 35.0, x))
    w_beach = smoothstep(HARBOR_EAST, HARBOR_EAST + 35.0, x) * (1.0 - smoothstep(BEACH_EAST - 30.0, BEACH_EAST + 30.0, x))
    w_cliff = np.clip(1.0 - w_harbor - w_beach, 0.0, 1.0)
    return w_harbor * h_harbor + w_beach * h_beach + w_cliff * h_cliff


# ---------------------------------------------------------------------------
# Gelaende-Kacheln
# ---------------------------------------------------------------------------
def build_terrain(m, out_root):
    cells = int(2 * EXTENT / CELL)
    coords = np.linspace(-EXTENT, EXTENT, cells + 1)
    gx, gy = np.meshgrid(coords, coords, indexing="xy")   # gy[row] = y
    heights = terrain_height(gx, gy)

    per_tile = cells // TILES
    tiles = []
    for ti in range(TILES):
        for tj in range(TILES):
            bm = bmesh.new()
            uv = bm.loops.layers.uv.new("UVMap")
            i0, j0 = ti * per_tile, tj * per_tile
            verts = {}
            for i in range(i0, i0 + per_tile + 1):
                for j in range(j0, j0 + per_tile + 1):
                    verts[(i, j)] = bm.verts.new((coords[i], coords[j], float(heights[j, i])))
            for i in range(i0, i0 + per_tile):
                for j in range(j0, j0 + per_tile):
                    face = bm.faces.new((verts[(i, j)], verts[(i + 1, j)], verts[(i + 1, j + 1)], verts[(i, j + 1)]))
                    for loop in face.loops:
                        loop[uv].uv = (loop.vert.co.x, loop.vert.co.y)
            obj = lib.bm_to_object(bm, "SM_VB_Terrain_%d_%d" % (ti, tj))
            lib.assign_materials(obj, [m["terrain"]])
            lib.shade_smooth(obj, 180.0)
            lib.mirror_to_unreal(obj)
            tiles.append(lib.finalize(obj, "Terrain", nanite=True, collision="complex"))

    # Hoehenkarte fuer Wasser (Tiefe, Schaum) - Zeile 0 = y = -EXTENT (Unreal-UV v = 0)
    size = 512
    sample = np.linspace(-EXTENT, EXTENT, size)
    sx, sy = np.meshgrid(sample, sample, indexing="xy")
    encoded = np.clip((terrain_height(sx, sy) - HEIGHT_MIN) / HEIGHT_RANGE, 0.0, 1.0)
    folder = os.path.join(out_root, "Surfaces", "Terrain")
    os.makedirs(folder, exist_ok=True)
    rgb = np.stack([encoded, encoded, encoded], axis=-1)
    lib.write_png(os.path.join(folder, "T_VB_TerrainHeight_H.png"), np.flipud(rgb), sixteen_bit=True)
    with open(os.path.join(folder, "surface.json"), "w", encoding="utf-8") as handle:
        json.dump({"surface": "Terrain", "texture_only": True, "extent_m": EXTENT, "height_min_m": HEIGHT_MIN,
                   "height_range_m": HEIGHT_RANGE, "sea_level_m": SEA_LEVEL}, handle, indent=2)
    return tiles


def build_ocean(m):
    bm = bmesh.new()
    size = 5000.0
    verts = [bm.verts.new((x, y, 0.0)) for x, y in ((-size, -size), (size, -size), (size, size), (-size, size))]
    bm.faces.new(verts)
    obj = lib.bm_to_object(bm, "SM_VB_OceanPlane")
    lib.assign_materials(obj, [m["ocean"]])
    lib.uv_meters(obj)
    return lib.finalize(obj, "Terrain", nanite=False, collision="none")


# ---------------------------------------------------------------------------
# Kaimauer, Poller, Gelaender, Promenade (Unreal-Koordinaten)
# ---------------------------------------------------------------------------
def build_quay_wall(m):
    """10 m Kaimauer: Wasserseite bei Y = 0 (Meer = -Y), Oberkante +0.15 m, Fuss -7 m. Pivot am Anfang."""
    bm = bmesh.new()
    rng = random.Random(9)
    length, bottom, top = 10.0, -7.0, 0.0
    lib.box(bm, (length / 2, 0.55, (bottom + top) / 2), (length, 1.1, top - bottom), 1)     # Kern
    z, row = bottom, 0
    while z < top - 0.05:
        height = min(0.6, top - z)
        x = -0.45 if row % 2 else 0.0
        while x < length:
            block = rng.choice([1.2, 0.9, 1.05, 1.35])
            x0, x1 = max(x, 0.0), min(x + block, length)
            if x1 - x0 > 0.1:
                proud = rng.uniform(0.02, 0.05)
                lib.box(bm, ((x0 + x1) / 2 + 0.0, -proud / 2, z + height / 2), (x1 - x0 - 0.025, proud, height - 0.025), 1)
            x += block
        z += height
        row += 1
    lib.box(bm, (length / 2, 0.3, 0.075), (length, 0.9, 0.15), 0)                            # Deckstein Granit
    obj = lib.bm_to_object(bm, "SM_VB_QuayWall_10m")
    lib.add_bevel(obj, 0.015, segments=2, limit_angle=50.0)
    lib.assign_materials(obj, [m["granite"], m["stone"]])
    lib.apply_modifiers(obj)
    lib.uv_meters(obj)
    lib.mirror_to_unreal(obj)
    return lib.finalize(obj, "Landmarks", nanite=True, collision="auto")


def build_mooring_bollard(m):
    bm = bmesh.new()
    lib.tapered_cylinder(bm, 0.24, 0.24, 0.0, 0.04, segments=32)
    lib.tapered_cylinder(bm, 0.14, 0.11, 0.04, 0.42, segments=32, rings=3)
    lib.tapered_cylinder(bm, 0.11, 0.2, 0.42, 0.5, segments=32)
    lib.tapered_cylinder(bm, 0.2, 0.19, 0.5, 0.56, segments=32)
    obj = lib.bm_to_object(bm, "SM_VB_MooringBollard")
    lib.add_bevel(obj, 0.01, segments=2)
    lib.assign_materials(obj, [m["iron"]])
    lib.apply_modifiers(obj)
    lib.shade_smooth(obj)
    lib.uv_meters(obj)
    lib.add_box_collision(obj, [((0, 0, 0.28), (0.45, 0.45, 0.56))])
    return lib.finalize(obj, "Props", nanite=True)


def build_railing(m):
    """2 m Promenadengelaender, Pfosten bei X = 0 (naechster Pfosten kommt vom Nachbarstueck)."""
    bm = bmesh.new()
    lib.cylinder(bm, (0.0, 0.0, 0.55), 0.03, 1.1, segments=16)
    lib.box(bm, (0.0, 0.0, 0.01), (0.12, 0.12, 0.02), 0)
    for z, radius in ((1.1, 0.03), (0.75, 0.014), (0.4, 0.014)):
        lib.cylinder(bm, (1.0, 0.0, z), radius, 2.0, segments=16, axis="X")
    obj = lib.bm_to_object(bm, "SM_VB_Railing_2m")
    lib.assign_materials(obj, [m["paint"]])
    lib.shade_smooth(obj, 50.0)
    lib.uv_meters(obj)
    lib.mirror_to_unreal(obj)
    lib.add_box_collision(obj, [((1.0, 0.0, 0.55), (2.0, 0.08, 1.1))])
    return lib.finalize(obj, "Props", nanite=True)


def build_promenade_tile(m):
    """5 x 5 m Promenadenbelag (50-cm-Platten), Oberkante +0.15 m, X 0..5, Y 0..5."""
    rng = random.Random(4)
    slabs = []
    for a in range(10):
        for b in range(10):
            sbm = bmesh.new()
            top = 0.15 + rng.uniform(-0.002, 0.002)
            lib.box(sbm, (a * 0.5 + 0.25, b * 0.5 + 0.25, top - 0.04), (0.494, 0.494, 0.08), 0)
            slab = lib.bm_to_object(sbm, "Slab")
            lib.add_bevel(slab, 0.005, segments=2, limit_angle=50.0)
            lib.assign_materials(slab, [m["promenade"], m["joint"]])
            lib.apply_modifiers(slab)
            lib.uv_meters(slab)
            du, dv = rng.random() * 1.5, rng.random() * 1.5
            for loop_uv in slab.data.uv_layers.active.data:
                loop_uv.uv = (loop_uv.uv[0] + du, loop_uv.uv[1] + dv)
            slabs.append(slab)
    bm = bmesh.new()
    lib.box(bm, (2.5, 2.5, (0.138 - 0.4) / 2), (5.0, 5.0, 0.138 + 0.4), 1)
    bedding = lib.bm_to_object(bm, "Bedding")
    lib.assign_materials(bedding, [m["promenade"], m["joint"]])
    lib.uv_meters(bedding)
    obj = lib.join(slabs + [bedding], "SM_VB_Promenade_5m")
    lib.mirror_to_unreal(obj)
    return lib.finalize(obj, "Roads", nanite=True, collision="auto", puddle_response=1.0)


def materials():
    return {
        "terrain": lib.make_material("Terrain", (0.3, 0.3, 0.2), 0.9, shared_material="Terrain"),
        "ocean": lib.make_material("Ocean", (0.02, 0.06, 0.07), 0.03, shared_material="Ocean"),
        "granite": lib.make_material("CurbGranite", (0.3, 0.3, 0.3), 0.6, surface="Granite"),
        "stone": lib.make_material("QuayStone", (0.5, 0.45, 0.38), 0.8, surface="Sandstone"),
        "iron": lib.make_material("CastIron", (0.28, 0.28, 0.29), 0.5, 0.85, surface="CastIron"),
        "paint": lib.make_material("PaintRailingWhite", (0.78, 0.78, 0.76), 0.35, porosity=0.0),
        "promenade": lib.make_material("PromenadeStone", (0.5, 0.47, 0.42), 0.8, surface="Sandstone"),
        "joint": lib.make_material("PaverJoint", (0.09, 0.085, 0.08), 0.95, porosity=0.9, puddle_response=0.0),
    }


def main():
    args = lib.cli_args()
    lib.reset_scene()
    m = materials()
    out = args.get("out", os.path.join(os.getcwd(), "SourceAssets", "Export"))
    assets = build_terrain(m, out)
    assets += [build_ocean(m), build_quay_wall(m), build_mooring_bollard(m), build_railing(m), build_promenade_tile(m)]
    for asset in assets:
        print("%-28s %8d Dreiecke" % (asset.name, lib.vb_blender_export.triangle_count(asset)))
    if args.get("blend"):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args["blend"]))
    if args.get("out"):
        exported, _ = lib.export(args["out"])
        return 0 if exported == len(assets) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
