"""Vorschau Phase 3: Stadtblock exakt wie in Unreal (gleiche Logik wie AVBBuildingBuilder / AVBStreetBuilder /
vb_setup.build_city_block), gerendert mit Cycles. Dient der Kontrolle von Ausrichtung, Raster und Fassadenmodi.

    blender -b --factory-startup --python vb_preview_block.py -- --out <bild.png> [--textures SourceAssets/Export]
            [--view street|aerial]
"""

import math
import os
import random
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vb_blender_lib as lib  # noqa: E402

PROJECT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BLENDS = [os.path.join(PROJECT, "SourceAssets", "Blender", name)
          for name in ("VB_StreetKit.blend", "VB_Facades.blend", "SM_VB_StreetLight_A.blend")]

BAY, GROUND_H, FLOOR_H = 3.0, 4.5, 3.0
BLOCK_W, BLOCK_D, BUILDING_LINE = 60.0, 30.0, 9.78
STREET_X, STREET_Y = BLOCK_W / 2 + BUILDING_LINE, BLOCK_D / 2 + BUILDING_LINE
VARIANT = {"A": "Balcony", "B": "WindowPair", "C": "Panel"}
TINTS = {"A": [(0.85, 0.72, 0.55), (0.72, 0.78, 0.8), (0.86, 0.8, 0.7), (0.9, 0.62, 0.5)]}

TEMPLATES = {}


def load_templates():
    for blend in BLENDS:
        with bpy.data.libraries.load(blend, link=False) as (source, target):
            target.objects = [n for n in source.objects if n.startswith("SM_")]
        for obj in target.objects:
            if obj is not None:
                TEMPLATES[obj.name] = obj
                obj.hide_render = True


def place(name, x, y, z, yaw, material_override=None):
    """Unreal-Koordinaten -> Blender (Y und Yaw negiert)."""
    template = TEMPLATES.get(name)
    if template is None:
        return None
    obj = bpy.data.objects.new(name + "_i", template.data)
    obj.location = (x, -y, z)
    obj.rotation_euler = (0.0, 0.0, math.radians(-yaw))
    bpy.context.collection.objects.link(obj)
    if material_override:
        obj.material_slots  # noqa: B018 - Slots existieren ueber die Mesh-Daten
    return obj


def to_world(origin, yaw, lx, ly):
    rad = math.radians(yaw)
    return (origin[0] + math.cos(rad) * lx - math.sin(rad) * ly, origin[1] + math.sin(rad) * lx + math.cos(rad) * ly)


# --- AVBBuildingBuilder (gleiche Logik) -------------------------------------------
def building(style, origin, yaw, bays_x, bays_y, floors, modes, seed, shop_ratio=0.7, variant_ratio=0.35):
    rng = random.Random(seed)
    eaves = GROUND_H + (floors - 1) * FLOOR_H
    starts = [(0, 0), (bays_x * BAY, 0), (bays_x * BAY, bays_y * BAY), (0, bays_y * BAY)]
    for facade in range(4):
        mode = modes[facade]
        if mode == "None":
            continue
        fyaw = 90.0 * facade
        bays = bays_x if facade % 2 == 0 else bays_y
        plain = mode == "Plain"
        door = rng.randint(0, bays - 1)
        for bay in range(bays):
            lx = starts[facade][0] + math.cos(math.radians(fyaw)) * bay * BAY
            ly = starts[facade][1] + math.sin(math.radians(fyaw)) * bay * BAY
            wx, wy = to_world(origin, yaw, lx, ly)
            wyaw = yaw + fyaw
            if plain:
                ground = "GroundPlain"
            elif facade in (0, 2) and bay == door:
                ground = "GroundDoor"
            elif facade == 0 and rng.random() < shop_ratio:
                ground = "GroundShop"
            else:
                ground = "GroundWindow"
            place("SM_VB_Fac%s_%s" % (style, ground), wx, wy, 0, wyaw)
            variant_column = not plain and rng.random() < variant_ratio
            for floor in range(1, floors):
                kind = "Plain" if plain else (VARIANT[style] if variant_column else "Window")
                place("SM_VB_Fac%s_%s" % (style, kind), wx, wy, GROUND_H + (floor - 1) * FLOOR_H, wyaw)
            place("SM_VB_Fac%s_Cornice" % style, wx, wy, eaves, wyaw)
        cx, cy = to_world(origin, yaw, *starts[facade])
        place("SM_VB_Fac%s_CornerGround" % style, cx, cy, 0, yaw + fyaw)
        for floor in range(1, floors):
            place("SM_VB_Fac%s_CornerUpper" % style, cx, cy, GROUND_H + (floor - 1) * FLOOR_H, yaw + fyaw)
        place("SM_VB_Fac%s_CornerCornice" % style, cx, cy, eaves, yaw + fyaw)
    for i in range(bays_x):
        for j in range(bays_y):
            wx, wy = to_world(origin, yaw, i * BAY, j * BAY)
            place("SM_VB_Roof_Tile_3m", wx, wy, eaves, yaw)
    for _ in range(4):
        lx, ly = rng.uniform(1.5, bays_x * BAY - 1.5), rng.uniform(1.5, bays_y * BAY - 1.5)
        if bays_x * BAY > 3 and bays_y * BAY > 3:
            wx, wy = to_world(origin, yaw, lx, ly)
            place(rng.choice(["SM_VB_Roof_AC", "SM_VB_Roof_Vent", "SM_VB_Roof_AC", "SM_VB_Roof_Antenna"]), wx, wy, eaves + 0.05,
                  yaw + 90 * rng.randint(0, 3))


# --- AVBStreetBuilder (vereinfacht: Fahrbahn, Bordstein, Gehweg) ---------------------
def street(origin, yaw, length):
    for i in range(int(math.ceil(length / 10.0))):
        place("SM_VB_Road_10m", *to_world(origin, yaw, i * 10.0, 0), 0, yaw)
    for i in range(int(math.ceil(length / 2.0))):
        for name in ("SM_VB_Curb_2m", "SM_VB_Sidewalk_2m"):
            place(name, *to_world(origin, yaw, i * 2.0, 6.0), 0, yaw)
            place(name, *to_world(origin, yaw, i * 2.0 + 2.0, -6.0), 0, yaw + 180)
    x = 7.5
    while x < length:
        for side in (-1, 1):
            place("SM_VB_StreetLight_A", *to_world(origin, yaw, x + (0 if side > 0 else 12.5), side * 7.0), 0.15,
                  yaw + (-90 if side > 0 else 90))
        x += 25.0


def block(center, rng, detailed):
    cx, cy = center
    depth = 3 if detailed else 5
    splits = [[5, 6, 4, 5], [4, 5, 6, 5], [6, 4, 5, 5], [5, 5, 5, 5], [7, 6, 7], [3, 5, 4, 4, 4]]

    def row(y_edge, north, widths):
        x = cx - BLOCK_W / 2
        for index, bays in enumerate(widths):
            first, last = index == 0, index == len(widths) - 1
            style = rng.choice("AAAAAAAAABBBBBBBCCCC")
            floors = rng.randint(4, 7)
            if north:
                origin, yaw, left_open, right_open = (x + bays * BAY, y_edge), 180.0, last, first
            else:
                origin, yaw, left_open, right_open = (x, y_edge), 0.0, first, last
            modes = ("Full", "Full" if right_open else "Plain", "Full" if detailed else "Plain", "Full" if left_open else "Plain")
            building(style, origin, yaw, bays, depth, floors, modes, rng.randint(1, 99999))
            x += bays * BAY

    row(cy - BLOCK_D / 2, False, rng.choice(splits))
    row(cy + BLOCK_D / 2, True, rng.choice(splits))
    if detailed:
        inner = int((BLOCK_D - 2 * depth * BAY) / BAY)
        building(rng.choice("AAAAAAAAABBBBBBBCCCC"), (cx + BLOCK_W / 2, cy - inner * BAY / 2), 90.0, inner, depth, rng.randint(4, 6),
                 ("Full", "Plain", "Full", "Plain"), rng.randint(1, 99999))
        building(rng.choice("AAAAAAAAABBBBBBBCCCC"), (cx - BLOCK_W / 2, cy + inner * BAY / 2), 270.0, inner, depth, rng.randint(4, 6),
                 ("Full", "Plain", "Full", "Plain"), rng.randint(1, 99999))


def main():
    args = lib.cli_args()
    lib.reset_scene()
    load_templates()
    rng = random.Random(42)
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            if args.get("view", "street") == "street" and (i, j) not in ((0, 0), (0, -1), (1, 0), (1, -1), (-1, 0), (-1, -1)):
                continue
            block((i * 2 * STREET_X, j * 2 * STREET_Y), rng, i == 0 and j == 0)
    for sy in (-1, 1):
        for i in (-1, 0, 1):
            street((i * 2 * STREET_X - BLOCK_W / 2, sy * STREET_Y), 0.0, BLOCK_W)
    for sx in (-1, 1):
        for j in (-1, 0, 1):
            street((sx * STREET_X, j * 2 * STREET_Y - BLOCK_D / 2), 90.0, BLOCK_D)
    for sx in (-1, 1):
        for sy in (-1, 1):
            place("SM_VB_Intersection_4Way", sx * STREET_X, sy * STREET_Y, 0, 0)
            for arm in range(4):
                wx, wy = to_world((sx * STREET_X, sy * STREET_Y), 90.0 * arm, 9.2, -7.0)
                place("SM_VB_TrafficLight_A", wx, wy, 0.15, 90.0 * arm)

    if args.get("view", "street") == "aerial":
        target, camera, lens = (0, 0, 0), (75, 85, 70), 30.0     # Blender-Koordinaten
    else:
        # Auf dem Gehweg der suedlichen Strasse (Unreal y = -STREET_Y + 8) Richtung Osten
        target, camera, lens = (40.0, STREET_Y - 2.0, 7.0), (-18.0, STREET_Y - 7.5, 1.7), 24.0
    lib.render_preview(os.path.abspath(args.get("out", "block.png")), target, camera, resolution=(1280, 720), lens=lens,
                       samples=32, sun_angle=(52.0, 0.0, 200.0), ground=True, preview_textures_root=args.get("textures"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
