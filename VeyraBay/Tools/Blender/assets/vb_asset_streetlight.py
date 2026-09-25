"""SM_VB_StreetLight_A - moderne LED-Strassenleuchte (8 m), prozedural in Blender erzeugt.

Aufruf (Blender im Hintergrund):
    blender -b --factory-startup --python vb_asset_streetlight.py -- --out <SourceAssets/Export> [--blend <datei.blend>]

Masse passen exakt zu AVBStreetLight (Lichtquelle bei X=1.50 m, Z=7.70 m, Ausleger zeigt nach +X).
Echte Geometrie statt Normal-Map-Tricks: Fase an allen Kanten, Fussplatte mit Ankerschrauben,
Wartungsklappe, konischer Mast, gebogener Ausleger, flacher LED-Kopf mit eingelassener Linse.
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vb_blender_export  # noqa: E402

ASSET = "SM_VB_StreetLight_A"
POLE_HEIGHT = 7.9
LAMP_X = 1.5
LAMP_Z = 7.72


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    return scene


def make_material(name, base_color, roughness, metallic=0.0, **extra):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
    material["vb_base_color"] = list(base_color)
    material["vb_roughness"] = roughness
    material["vb_metallic"] = metallic
    for key, value in extra.items():
        material["vb_" + key] = value
    return material


def bm_to_object(bm, name, material_index_map=None):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def add_bevel(obj, width, segments=2, limit_angle=35.0):
    modifier = obj.modifiers.new("Bevel", "BEVEL")
    modifier.width = width
    modifier.segments = segments
    modifier.limit_method = "ANGLE"
    modifier.angle_limit = math.radians(limit_angle)
    modifier.harden_normals = True
    return modifier


def apply_modifiers(obj):
    bpy.context.view_layer.objects.active = obj
    for modifier in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=modifier.name)


def tapered_cylinder(bm, radius_bottom, radius_top, z_bottom, z_top, segments=32, rings=1, cap_bottom=True, cap_top=True):
    """Konischer Zylinder (Kegelstumpf) direkt in ein BMesh."""
    layers = []
    for ring in range(rings + 1):
        t = ring / rings
        radius = radius_bottom + (radius_top - radius_bottom) * t
        z = z_bottom + (z_top - z_bottom) * t
        layers.append([bm.verts.new((radius * math.cos(2 * math.pi * i / segments),
                                     radius * math.sin(2 * math.pi * i / segments), z)) for i in range(segments)])
    for ring in range(rings):
        low, high = layers[ring], layers[ring + 1]
        for i in range(segments):
            j = (i + 1) % segments
            bm.faces.new((low[i], low[j], high[j], high[i]))
    if cap_bottom:
        bm.faces.new(list(reversed(layers[0])))
    if cap_top:
        bm.faces.new(layers[-1])
    return layers


def build_pole():
    bm = bmesh.new()
    # Fussverkleidung (Kegelstumpf) + konischer Mast in einem Stueck
    tapered_cylinder(bm, 0.16, 0.10, 0.02, 0.62, segments=32, rings=2, cap_top=False)
    tapered_cylinder(bm, 0.085, 0.056, 0.62, POLE_HEIGHT, segments=32, rings=12, cap_bottom=False)
    # Ringfuge zwischen Fuss und Mast
    tapered_cylinder(bm, 0.105, 0.105, 0.60, 0.64, segments=32, rings=1)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    obj = bm_to_object(bm, "Pole")
    add_bevel(obj, 0.004, segments=2)
    return obj


def build_base_plate():
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Diagonal((0.42, 0.42, 0.025, 1.0)) @ Matrix.Translation((0, 0, 0.5)))
    # Ankerschrauben mit Muttern (echte Geometrie)
    for sx in (-1, 1):
        for sy in (-1, 1):
            center = Vector((sx * 0.16, sy * 0.16, 0.025))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.022, radius2=0.022, depth=0.018,
                                  matrix=Matrix.Translation(center + Vector((0, 0, 0.009))))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.009, radius2=0.009, depth=0.03,
                                  matrix=Matrix.Translation(center + Vector((0, 0, 0.03))))
    obj = bm_to_object(bm, "BasePlate")
    add_bevel(obj, 0.003, segments=2)
    return obj


def build_service_door():
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0.086, 0.0, 1.05)) @ Matrix.Diagonal((0.012, 0.075, 0.28, 1.0)))
    obj = bm_to_object(bm, "ServiceDoor")
    add_bevel(obj, 0.003, segments=2)
    return obj


def build_arm():
    """Gebogener Ausleger als Kurve mit rundem Profil."""
    curve = bpy.data.curves.new("ArmCurve", type="CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.038
    curve.bevel_resolution = 6
    curve.resolution_u = 24
    curve.use_fill_caps = True
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(1)
    start, end = spline.bezier_points
    start.co = (0.0, 0.0, POLE_HEIGHT - 0.35)
    start.handle_left = (0.0, 0.0, POLE_HEIGHT - 0.6)
    start.handle_right = (0.0, 0.0, POLE_HEIGHT + 0.05)
    end.co = (LAMP_X - 0.28, 0.0, LAMP_Z + 0.07)
    end.handle_left = (LAMP_X - 0.9, 0.0, LAMP_Z + 0.12)
    end.handle_right = (LAMP_X - 0.1, 0.0, LAMP_Z + 0.06)
    obj = bpy.data.objects.new("Arm", curve)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    return bpy.context.view_layer.objects.active


def build_head(lens_material_index):
    bm = bmesh.new()
    # Gehaeuse: flacher Koerper, vorne leicht verjuengt
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((LAMP_X, 0.0, LAMP_Z + 0.045)) @ Matrix.Diagonal((0.62, 0.27, 0.07, 1.0)))
    front_verts = [v for v in bm.verts if v.co.x > LAMP_X]
    for vert in front_verts:
        vert.co.y *= 0.82
        if vert.co.z > LAMP_Z + 0.045:
            vert.co.z -= 0.02
    bm.normal_update()
    # Linse: Unterseite einlassen
    bottom = [f for f in bm.faces if f.normal.z < -0.9]
    inset = bmesh.ops.inset_region(bm, faces=bottom, thickness=0.03, depth=0.0)
    lens_faces = bottom
    bmesh.ops.inset_region(bm, faces=lens_faces, thickness=0.0, depth=0.008)
    for face in lens_faces:
        face.material_index = lens_material_index
    obj = bm_to_object(bm, "Head")
    add_bevel(obj, 0.006, segments=3, limit_angle=30.0)
    return obj, inset


def join(objects, name):
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    result = bpy.context.view_layer.objects.active
    result.name = name
    result.data.name = name
    return result


def add_collision(asset):
    colliders = []
    boxes = [
        ((0.0, 0.0, POLE_HEIGHT * 0.5), (0.2, 0.2, POLE_HEIGHT)),
        ((0.0, 0.0, 0.0125), (0.42, 0.42, 0.025)),
        ((LAMP_X * 0.5, 0.0, LAMP_Z + 0.05), (LAMP_X + 0.35, 0.3, 0.2)),
    ]
    for index, (center, size) in enumerate(boxes):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(center) @ Matrix.Diagonal((*size, 1.0)))
        collider = bm_to_object(bm, "UCX_%s_%02d" % (asset.name, index))
        collider.parent = asset
        collider.display_type = "WIRE"
        colliders.append(collider)
    return colliders


def uv_unwrap(obj):
    bpy.context.view_layer.objects.active = obj
    for other in bpy.context.view_layer.objects:
        other.select_set(other == obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.003, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def build():
    reset_scene()

    paint = make_material("Paint", (0.16, 0.17, 0.18), 0.42, 0.0, porosity=0.05, wetness_response=1.0)
    lens = make_material("Lens", (0.85, 0.85, 0.82), 0.08, 0.0,
                         emissive_color=[1.0, 0.86, 0.68], emissive_intensity=8000.0, use_night_switch=True,
                         wetness_response=0.0)

    parts = [build_pole(), build_base_plate(), build_service_door(), build_arm()]
    head, _ = build_head(lens_material_index=1)
    parts.append(head)

    for part in parts:
        part.data.materials.clear()
        part.data.materials.append(paint)
        part.data.materials.append(lens)
        apply_modifiers(part)

    # Nur der Kopf nutzt Slot 1 (Linse); alle anderen Flaechen Slot 0
    asset = join(parts, ASSET)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40.0))
    uv_unwrap(asset)

    asset["vb_category"] = "Props"
    asset["vb_nanite"] = True
    asset["vb_collision"] = "auto"
    asset["vb_porosity"] = 0.05
    asset["vb_puddle_response"] = 0.0

    add_collision(asset)
    return asset


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out_root = argv[argv.index("--out") + 1] if "--out" in argv else None
    blend_path = argv[argv.index("--blend") + 1] if "--blend" in argv else None

    asset = build()
    print("%s: %d Dreiecke" % (asset.name, vb_blender_export.triangle_count(asset)))

    if blend_path:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(blend_path))
    if out_root:
        exported, report = vb_blender_export.export_all(bpy.context, os.path.abspath(out_root))
        for line in report:
            print(line)
        return 0 if exported == 1 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
