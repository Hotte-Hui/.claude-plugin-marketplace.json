"""Vorschau Phase 4: Uferpromenade des Kuestenbezirks (gleiche Platzierung wie vb_district.py).

    blender -b --factory-startup --python vb_preview_district.py -- --out <bild.png> [--textures SourceAssets/Export]
            [--view promenade|aerial]
"""

import math
import os
import random
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vb_blender_lib as lib  # noqa: E402
import vb_preview_block as block  # noqa: E402

PROJECT = block.PROJECT
EXTRA_BLENDS = [os.path.join(PROJECT, "SourceAssets", "Blender", n) for n in ("VB_Coast.blend", "VB_Vegetation.blend")]
PITCH_X, PITCH_Y = 2 * block.STREET_X, 2 * block.STREET_Y
RING_X, RING_Y = block.STREET_X + PITCH_X, block.STREET_Y + PITCH_Y
QUAY_Y = -94.12
SEA = -2.5


def load_extra():
    for blend in EXTRA_BLENDS:
        with bpy.data.libraries.load(blend, link=False) as (source, target):
            target.objects = [n for n in source.objects if n.startswith("SM_")]
        for obj in target.objects:
            if obj is not None:
                block.TEMPLATES[obj.name] = obj
                obj.hide_render = True


def preview_materials(textures_root):
    """Gelaende/Meer/Laub bekommen in der Vorschau einfache Ersatzmaterialien (in Unreal: eigene Master-Materialien)."""
    terrain = bpy.data.materials.get("Terrain")
    if terrain:
        tree = terrain.node_tree
        bsdf = tree.nodes["Principled BSDF"]
        geo = tree.nodes.new("ShaderNodeNewGeometry")
        sep = tree.nodes.new("ShaderNodeSeparateXYZ")
        tree.links.new(geo.outputs["Position"], sep.inputs[0])
        ramp = tree.nodes.new("ShaderNodeValToRGB")
        mr = tree.nodes.new("ShaderNodeMapRange")
        mr.inputs[1].default_value, mr.inputs[2].default_value = -3.0, 6.0
        tree.links.new(sep.outputs[2], mr.inputs[0])
        tree.links.new(mr.outputs[0], ramp.inputs[0])
        e = ramp.color_ramp.elements
        e[0].color, e[0].position = (0.55, 0.48, 0.36, 1), 0.2
        e[1].color, e[1].position = (0.22, 0.24, 0.1, 1), 0.3
        tree.links.new(ramp.outputs[0], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.95
    ocean = bpy.data.materials.get("Ocean")
    if ocean:
        bsdf = ocean.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (0.01, 0.045, 0.055, 1)
        bsdf.inputs["Roughness"].default_value = 0.06
        tex = ocean.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(os.path.join(textures_root, "Surfaces", "Ocean", "T_VB_Ocean_N.png"))
        tex.image.colorspace_settings.name = "Non-Color"
        coords = ocean.node_tree.nodes.new("ShaderNodeTexCoord")
        mapping = ocean.node_tree.nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (1 / 40.0, 1 / 40.0, 1)
        ocean.node_tree.links.new(coords.outputs["Object"], mapping.inputs["Vector"])
        ocean.node_tree.links.new(mapping.outputs[0], tex.inputs["Vector"])
        nmap = ocean.node_tree.nodes.new("ShaderNodeNormalMap")
        nmap.inputs["Strength"].default_value = 0.35
        ocean.node_tree.links.new(tex.outputs["Color"], nmap.inputs["Color"])
        ocean.node_tree.links.new(nmap.outputs[0], bsdf.inputs["Normal"])
    for material_name, path in (("PalmFrond", "Vegetation/SM_VB_PalmTree_A/T_VB_PalmTree_A_PalmFrond_D.png"),
                                ("PalmFrondDead", "Vegetation/SM_VB_PalmTree_A/T_VB_PalmTree_A_PalmFrondDead_D.png"),
                                ("PlaneLeaves", "Vegetation/SM_VB_PlaneTree_A/T_VB_PlaneTree_A_PlaneLeaves_D.png")):
        material = bpy.data.materials.get(material_name)
        if material is None:
            continue
        tree = material.node_tree
        bsdf = tree.nodes["Principled BSDF"]
        node = tree.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(os.path.join(textures_root, path))
        tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
        tree.links.new(node.outputs["Alpha"], bsdf.inputs["Alpha"])


def main():
    args = lib.cli_args()
    lib.reset_scene()
    block.load_templates()
    load_extra()
    rng = random.Random(42)
    place = block.place

    # Stadt: suedliche Blockreihe + Mitte
    for i in (-1, 0, 1):
        for j in (-1, 0):
            block.block((i * PITCH_X, j * PITCH_Y), rng, i == 0 and j == 0)
    for i in (-1, 0, 1):
        block.street((i * PITCH_X - block.BLOCK_W / 2, -RING_Y), 0.0, block.BLOCK_W)
        block.street((i * PITCH_X - block.BLOCK_W / 2, -block.STREET_Y), 0.0, block.BLOCK_W)
    for sx in (-1, 1):
        place("SM_VB_Intersection_T", sx * block.STREET_X, -RING_Y, 0, 0)
        place("SM_VB_Intersection_Corner", sx * RING_X, -RING_Y, 0, 90.0 if sx > 0 else 0.0)
        block.street((sx * block.STREET_X, -PITCH_Y - block.BLOCK_D / 2), 90.0, block.BLOCK_D)
        place("SM_VB_Intersection_4Way", sx * block.STREET_X, -block.STREET_Y, 0, 0)

    # Gelaende + Meer
    for i in range(4):
        for j in range(4):
            place("SM_VB_Terrain_%d_%d" % (i, j), 0, 0, 0, 0)
    place("SM_VB_OceanPlane", 0, 0, SEA, 0)

    # Promenade, Kaimauer, Poller, Gelaender, Palmen (wie vb_district.py, in Metern)
    edge = RING_X + block.BUILDING_LINE
    x = -edge
    while x < edge:
        place("SM_VB_Promenade_5m", x, QUAY_Y, 0, 0)
        place("SM_VB_Promenade_5m", x, QUAY_Y + 5.0, 0, 0)
        x += 5.0
    x = -edge
    while x < edge:
        place("SM_VB_QuayWall_10m", x, QUAY_Y, 0, 0)
        x += 10.0
    for px in range(int(-edge + 4), 35, 12):
        place("SM_VB_MooringBollard", px, QUAY_Y + 0.55, 0.15, rng.uniform(0, 360))
    x = 40.0
    while x < edge:
        place("SM_VB_Railing_2m", x, QUAY_Y + 0.2, 0.15, 0)
        x += 2.0
    for px in range(int(-edge + 6), int(edge), 15):
        obj = place("SM_VB_PalmTree_A", px + rng.uniform(-0.8, 0.8), QUAY_Y + 4.8, 0.15, rng.uniform(0, 360))
        if obj:
            obj.scale = (rng.uniform(0.9, 1.15),) * 3

    preview_materials(os.path.abspath(args.get("textures", "SourceAssets/Export")))
    if args.get("view", "promenade") == "aerial":
        target, camera, lens = (10.0, 70.0, 0.0), (140.0, 260.0, 90.0), 26.0
    else:
        # Auf der Promenade (Unreal y = QUAY_Y + 7) Richtung Osten, Meer rechts
        target, camera, lens = (60.0, -(QUAY_Y + 3.0), 4.0), (-25.0, -(QUAY_Y + 7.5), 1.7), 22.0
    lib.render_preview(os.path.abspath(args.get("out", "district.png")), target, camera, resolution=(1280, 720), lens=lens,
                       samples=40, sun_angle=(38.0, 0.0, 215.0), ground=False,
                       preview_textures_root=os.path.abspath(args.get("textures", "SourceAssets/Export")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
