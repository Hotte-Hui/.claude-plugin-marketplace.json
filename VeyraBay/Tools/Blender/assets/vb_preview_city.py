"""Vorschau Phase 7: Ausschnitt der ganzen Stadt (gleicher Plan und gleiche Bebauung wie vb_city.py in Unreal).

    blender -b --factory-startup --python vb_preview_city.py -- --out <bild.png> [--view altstadt|bayfront|marina|hafen]
            [--textures SourceAssets/Export]
"""

import math
import os
import random
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "Content", "Python"))
import vb_blender_lib as lib  # noqa: E402
import vb_cityplan as plan  # noqa: E402
import vb_preview_block as block  # noqa: E402
import vb_preview_district as district  # noqa: E402

# Ausschnitt (Unreal-Meter) und Kamera (Blender-Koordinaten: y negiert)
VIEWS = {
    "altstadt": dict(area=(-420.0, -110.0, 200.0, 330.0), target=(-120.0, -40.0, 0.0), camera=(-420.0, 260.0, 160.0), lens=30.0),
    "bayfront": dict(area=(-100.0, 600.0, 330.0, 880.0), target=(120.0, -760.0, 40.0), camera=(-120.0, -470.0, 90.0), lens=24.0),
    "marina": dict(area=(2200.0, -110.0, 2800.0, 350.0), target=(2480.0, -60.0, 0.0), camera=(2250.0, 250.0, 120.0), lens=28.0),
    "hafen": dict(area=(-1800.0, -110.0, -1200.0, 350.0), target=(-1500.0, -60.0, 0.0), camera=(-1750.0, 230.0, 120.0), lens=28.0),
}


def inside(area, x, y, margin=0.0):
    return area[0] - margin <= x <= area[2] + margin and area[1] - margin <= y <= area[3] + margin


def main():
    args = lib.cli_args()
    view = VIEWS[args.get("view", "altstadt")]
    area = view["area"]
    lib.reset_scene()
    block.load_templates()
    district.load_extra()

    junctions, streets, blocks = plan.network()
    for x0, y0, yaw, length, _name, _arterial in streets:
        rad = math.radians(yaw)
        xm, ym = x0 + math.cos(rad) * length / 2, y0 + math.sin(rad) * length / 2
        if inside(area, xm, ym, 60.0):
            block.street((x0, y0), yaw, length)
    for (k, j), arms in junctions.items():
        x, y = plan.line_x(k), plan.line_y(j)
        if not inside(area, x, y, 20.0):
            continue
        kind, yaw = plan.junction_kind(arms)
        name = {"4way": "SM_VB_Intersection_4Way", "t": "SM_VB_Intersection_T", "corner": "SM_VB_Intersection_Corner"}.get(kind)
        if name:
            block.place(name, x, y, 0, yaw)
        d = plan.district_at(x + 1, y + 1)
        major = k % plan.ARTERIAL_EVERY == 0 or j % plan.ARTERIAL_EVERY == 0
        if kind == "4way" and d and d.get("signals") and major:
            for arm in range(4):
                wx, wy = block.to_world((x, y), 90.0 * arm, 9.2, -7.0)
                block.place("SM_VB_TrafficLight_A", wx, wy, 0.15, 90.0 * arm)

    layout = plan.Layout(random.Random(2024)).city(blocks, None)
    for b in layout.buildings:
        if inside(area, b["x"], b["y"]):
            block.building(b["style"], (b["x"], b["y"]), b["yaw"], b["bays_x"], b["bays_y"], b["floors"], b["modes"], b["seed"],
                           b["shop"])
    names = {"plane_tree": "SM_VB_PlaneTree_A", "palm": "SM_VB_PalmTree_A"}
    for art, x, y, z, yaw, scale in layout.trees:
        if inside(area, x, y):
            obj = block.place(names[art], x, y, z, yaw)
            if obj:
                obj.scale = (scale,) * 3
    coast_names = {"promenade": "SM_VB_Promenade_5m", "quay": "SM_VB_QuayWall_10m", "bollard": "SM_VB_MooringBollard",
                   "railing": "SM_VB_Railing_2m", "palm": "SM_VB_PalmTree_A"}
    for art, x, y, z, yaw in plan.waterfront():
        if inside(area, x, y, 10.0):
            block.place(coast_names[art], x, y, z, yaw)
    block.place("SM_VB_OceanPlane", 0, 0, plan.SEA_LEVEL, 0)

    textures = os.path.abspath(args.get("textures", "SourceAssets/Export"))
    district.preview_materials(textures)
    lib.render_preview(os.path.abspath(args.get("out", "city.png")), view["target"], view["camera"], resolution=(1600, 900),
                       lens=view["lens"], samples=24, sun_angle=(40.0, 0.0, 215.0), ground=True, preview_textures_root=textures,
                       ground_size=1400.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
