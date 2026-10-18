"""Vorschau: setzt das Strassen-Kit wie AVBStreetBuilder zusammen und rendert eine Strassenansicht.

    blender -b --factory-startup --python vb_preview_street.py -- --out <bild.png> [--textures SourceAssets/Export]
            [--night]

Dient nur der Kontrolle ausserhalb von Unreal (Cycles, CPU).
"""

import math
import os
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vb_blender_lib as lib  # noqa: E402

PROJECT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KIT_BLEND = os.path.join(PROJECT, "SourceAssets", "Blender", "VB_StreetKit.blend")
LAMP_BLEND = os.path.join(PROJECT, "SourceAssets", "Blender", "SM_VB_StreetLight_A.blend")
LENGTH = 60.0
CURB = 6.0


def append_objects(blend, names):
    with bpy.data.libraries.load(blend, link=False) as (source, target):
        target.objects = [n for n in source.objects if n in names]
    result = {}
    for obj in target.objects:
        if obj is not None:
            result[obj.name] = obj
    return result


def place(template, location, yaw=0.0):
    """Platziert in UNREAL-Koordinaten (wie AVBStreetBuilder) und rechnet nach Blender um (Y und Yaw negiert)."""
    copy = bpy.data.objects.new(template.name + "_inst", template.data)
    copy.location = (location[0], -location[1], location[2])
    copy.rotation_euler = (0.0, 0.0, math.radians(-yaw))
    bpy.context.collection.objects.link(copy)
    return copy


def main():
    args = lib.cli_args()
    lib.reset_scene()
    kit = append_objects(KIT_BLEND, ["SM_VB_Road_10m", "SM_VB_Road_10m_Crosswalk", "SM_VB_Curb_2m", "SM_VB_Sidewalk_2m",
                                     "SM_VB_Manhole_A", "SM_VB_Bollard_A", "SM_VB_Bench_A", "SM_VB_TrashBin_A",
                                     "SM_VB_Hydrant_A", "SM_VB_Sign_NoStopping", "SM_VB_TrafficLight_A"])
    kit.update(append_objects(LAMP_BLEND, ["SM_VB_StreetLight_A"]))
    for obj in kit.values():
        obj.hide_render = True  # Vorlagen selbst nicht rendern

    for i in range(int(LENGTH / 10)):
        place(kit["SM_VB_Road_10m_Crosswalk" if i == 3 else "SM_VB_Road_10m"], (i * 10.0, 0, 0))
    for i in range(int(LENGTH / 2)):
        for name in ("SM_VB_Curb_2m", "SM_VB_Sidewalk_2m"):
            place(kit[name], (i * 2.0, CURB, 0))                # wie AVBStreetBuilder::BuildEdges
            place(kit[name], (i * 2.0 + 2.0, -CURB, 0), 180)

    rng = random.Random(3)
    for x in range(8, int(LENGTH), 17):
        place(kit["SM_VB_Manhole_A"], (x + rng.uniform(-2, 2), 2.8 * rng.choice((-1, 1)), 0.03))
    for x in (6.0, 18.0, 42.0, 54.0):
        place(kit["SM_VB_Bollard_A"], (x, 6.5, 0.15), -90)
    for x in (12.0, 47.0):
        place(kit["SM_VB_Bench_A"], (x, -9.3, 0.15), 90)  # Vorderseite +X -> zur Fahrbahn (+Y)
    for x in (19.0, 44.0):
        place(kit["SM_VB_TrashBin_A"], (x, -6.9, 0.15), 90)
    place(kit["SM_VB_Hydrant_A"], (27.0, 7.0, 0.15), -90)
    place(kit["SM_VB_Sign_NoStopping"], (23.0, -6.7, 0.15), 0)
    place(kit["SM_VB_TrafficLight_A"], (31.0, 7.0, 0.15), 180)   # wie vb_setup (Unreal-Koordinaten)
    place(kit["SM_VB_TrafficLight_A"], (39.0, -7.0, 0.15), 0)
    for x in (2.5, 27.5, 52.5):
        place(kit["SM_VB_StreetLight_A"], (x, 7.0, 0.15), -90)
    for x in (15.0, 40.0):
        place(kit["SM_VB_StreetLight_A"], (x, -7.0, 0.15), 90)

    # Graubox-Fassaden wie in der Dev-Karte
    for side in (-1, 1):
        x = -10.0
        while x < LENGTH + 10:
            width = rng.uniform(14, 28)
            height = rng.choice([9, 12, 15, 18, 24, 32])
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x + width / 2, -side * (9.78 + 10), height / 2))
            building = bpy.context.active_object
            building.scale = (width, 20, height)
            material = bpy.data.materials.new("Facade")
            material.use_nodes = True
            tone = rng.choice([(0.33, 0.32, 0.3), (0.52, 0.42, 0.32), (0.62, 0.6, 0.56), (0.3, 0.14, 0.1)])
            material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*tone, 1)
            material.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
            building.data.materials.append(material)
            x += width + rng.choice([0, 0, 1.5])

    camera_target = (40.0, 1.0, 1.4)
    camera_location = (-2.0, -4.2, 1.65)
    lib.render_preview(os.path.abspath(args.get("out", "street.png")), camera_target, camera_location,
                       resolution=(1280, 720), lens=28.0, samples=48, sun_angle=(58.0, 0.0, 140.0), ground=True,
                       preview_textures_root=args.get("textures"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
