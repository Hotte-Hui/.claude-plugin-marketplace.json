"""Veyra Bay Fahrzeuge (Phase 5): acht fiktive Modelle, prozedural modelliert.

    blender -b --factory-startup --python vb_asset_vehicles.py -- --out <SourceAssets/Export>
            [--blend <datei.blend>] [--preview <ordner>] [--textures SourceAssets/Export]

Je Auto entstehen:
    SM_VB_Car_<Typ>        Karosserie ohne Raeder (KI-Verkehr, geparkte Deko)
    SK_VB_Car_<Typ>        dieselbe Karosserie als Skeletal Mesh mit Radknochen (Chaos Vehicle, fahrbar)
    SM_VB_Wheel_<Typ>      ein Rad (Reifen + Felge), Achse = Y, Pivot = Radmitte, Felge zeigt nach +Y
Koordinaten: UNREAL (X vorne, Y rechts, Z oben), Pivot = Mitte des Radstands auf dem Boden.
Materialzonen (Karosserie): Lack (Farbe per Custom Primitive Data 6..8), Glas, Scheinwerfer (CPD 3),
Rueck-/Bremslicht (CPD 2), Blinker links/rechts (CPD 4/5), Kunststoff, Grill, Innenraum.
Keine echten Marken oder Designs - generische, fiktive Formen.
"""

import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vb_blender_lib as lib  # noqa: E402

# Seitenprofil: (x relativ -1 = Heck .. +1 = Front, Hoehe m) der Oberkante; Guertellinie; Scheibenbereich
SPECS = {
    "Sport": dict(length=4.45, width=1.92, clearance=0.12, wheelbase=2.62, radius=0.34, wheel_width=0.27, mass=1450,
                  top=[(-1.0, 0.62), (-0.93, 0.78), (-0.6, 0.93), (-0.25, 1.22), (0.12, 1.24), (0.42, 0.9), (0.8, 0.72), (1.0, 0.55)],
                  belt=0.86, glass=(-0.52, 0.45), pillars=(-0.28, 0.16), trim_h=0.22, lights=(0.62, 0.74), class_="Car"),
    "Sedan": dict(length=4.85, width=1.86, clearance=0.15, wheelbase=2.85, radius=0.33, wheel_width=0.23, mass=1550,
                  top=[(-1.0, 0.72), (-0.92, 0.98), (-0.62, 1.02), (-0.4, 1.42), (0.18, 1.46), (0.42, 1.04), (0.85, 0.9), (1.0, 0.7)],
                  belt=1.0, glass=(-0.6, 0.44), pillars=(-0.42, -0.08, 0.2), trim_h=0.26, lights=(0.74, 0.86), class_="Car"),
    "SUV": dict(length=4.75, width=1.96, clearance=0.22, wheelbase=2.85, radius=0.38, wheel_width=0.26, mass=2050,
                top=[(-1.0, 1.0), (-0.95, 1.55), (-0.85, 1.74), (0.25, 1.76), (0.46, 1.25), (0.85, 1.12), (1.0, 0.95)],
                belt=1.2, glass=(-0.9, 0.46), pillars=(-0.84, -0.3, 0.12), trim_h=0.36, lights=(0.95, 1.08), class_="Car"),
    "Pickup": dict(length=5.35, width=1.98, clearance=0.24, wheelbase=3.25, radius=0.39, wheel_width=0.27, mass=2250,
                   top=[(-1.0, 1.05), (-0.3, 1.08), (-0.29, 1.82), (0.2, 1.84), (0.38, 1.3), (0.85, 1.2), (1.0, 1.0)],
                   belt=1.28, glass=(-0.27, 0.36), pillars=(-0.25, 0.0), trim_h=0.4, lights=(1.0, 1.14), class_="Car", bed=(-1.0, -0.3)),
    "Van": dict(length=5.1, width=2.0, clearance=0.18, wheelbase=3.1, radius=0.34, wheel_width=0.23, mass=2300,
                top=[(-1.0, 1.95), (-0.96, 2.05), (0.5, 2.07), (0.62, 1.55), (0.88, 1.05), (1.0, 0.9)],
                belt=1.15, glass=(-0.9, 0.87), pillars=(-0.35, 0.3, 0.6), trim_h=0.3, lights=(0.9, 1.02), class_="Car"),
    "Bus": dict(length=12.0, width=2.55, clearance=0.3, wheelbase=6.0, radius=0.5, wheel_width=0.3, mass=12000,
                top=[(-1.0, 3.05), (-0.98, 3.15), (0.97, 3.15), (1.0, 3.0)],
                belt=1.25, glass=(-0.95, 0.99), pillars=(-0.7, -0.45, -0.2, 0.05, 0.3, 0.55, 0.8), trim_h=0.4, lights=(0.55, 0.7),
                class_="Bus"),
}
PAINT = {"Sport": (0.5, 0.03, 0.02), "Sedan": (0.12, 0.14, 0.16), "SUV": (0.05, 0.05, 0.06), "Pickup": (0.35, 0.36, 0.37),
         "Van": (0.75, 0.75, 0.74), "Bus": (0.08, 0.22, 0.35), "Taxi": (0.85, 0.62, 0.05)}


def materials():
    m = {
        "paint": lib.make_material("CarPaint", (0.5, 0.5, 0.5), 0.28, 0.55, porosity=0.0, use_paint_data=True),
        "glass": lib.make_material("CarGlass", (0.02, 0.022, 0.025), 0.03, 0.0, porosity=0.0),
        "trim": lib.make_material("CarPlastic", (0.03, 0.03, 0.032), 0.6, porosity=0.0),
        "grille": lib.make_material("CarGrille", (0.015, 0.015, 0.016), 0.45, 0.3, porosity=0.0),
        "interior": lib.make_material("CarInterior", (0.035, 0.034, 0.033), 0.75, porosity=0.0, wetness_response=0.0),
        "chrome": lib.make_material("CarChrome", (0.9, 0.9, 0.9), 0.08, 1.0, porosity=0.0),
        "headlight": lib.make_material("CarHeadlight", (0.8, 0.8, 0.8), 0.05, porosity=0.0, wetness_response=0.0,
                                       emissive_color=(1.0, 0.95, 0.88), emissive_intensity=20000.0, use_night_switch=True,
                                       light_channel=3),
        "taillight": lib.make_material("CarTaillight", (0.25, 0.01, 0.01), 0.1, porosity=0.0, wetness_response=0.0,
                                       emissive_color=(1.0, 0.02, 0.01), emissive_intensity=4000.0, use_night_switch=True,
                                       light_channel=2),
        "indicator_l": lib.make_material("CarIndicatorLeft", (0.4, 0.2, 0.02), 0.1, porosity=0.0, wetness_response=0.0,
                                         emissive_color=(1.0, 0.4, 0.02), emissive_intensity=6000.0, use_night_switch=True,
                                         light_channel=4),
        "indicator_r": lib.make_material("CarIndicatorRight", (0.4, 0.2, 0.02), 0.1, porosity=0.0, wetness_response=0.0,
                                         emissive_color=(1.0, 0.4, 0.02), emissive_intensity=6000.0, use_night_switch=True,
                                         light_channel=5),
        "tire": lib.make_material("CarTire", (0.025, 0.025, 0.025), 0.88, porosity=0.2),
        "rim": lib.make_material("CarRim", (0.55, 0.56, 0.57), 0.25, 1.0, porosity=0.0),
        "sign": lib.make_material("TaxiSign", (0.9, 0.85, 0.6), 0.3, porosity=0.0, emissive_color=(1.0, 0.85, 0.5),
                                  emissive_intensity=800.0, use_night_switch=False),
    }
    return m


SLOTS = ["paint", "glass", "trim", "grille", "interior", "chrome", "headlight", "taillight", "indicator_l", "indicator_r", "sign"]


def profile_height(spec, u):
    points = spec["top"]
    for (u0, z0), (u1, z1) in zip(points[:-1], points[1:]):
        if u0 <= u <= u1:
            t = (u - u0) / max(u1 - u0, 1e-6)
            return z0 + (z1 - z0) * t
    return points[-1][1]


def build_body(name, spec, m, taxi=False):
    """Loft der Karosserie, Subdivision, Radhaeuser, Materialzonen, Innenraum."""
    length, width = spec["length"], spec["width"]
    half_l, half_w = length / 2, width / 2
    bus = spec["class_"] == "Bus"
    stations = 64
    ring = []
    bm = bmesh.new()
    rings = []
    for i in range(stations + 1):
        u = -1.0 + 2.0 * i / stations
        x = u * half_l
        # Grundriss: superelliptisch gerundete Enden
        plan = (1.0 - abs(u) ** (8 if bus else 5)) ** (1.0 / (8 if bus else 5))
        w = half_w * max(plan, 0.35)
        top = profile_height(spec, u)
        bottom = spec["clearance"] + (0.08 if abs(u) > 0.8 and not bus else 0.0) * (abs(u) - 0.8) / 0.2
        belt = min(spec["belt"], top - 0.05)
        roof_w = w * (0.93 if bus else 0.78)
        bed = spec.get("bed")
        if bed and bed[0] <= u <= bed[1]:
            top = min(top, spec["belt"] - 0.05)
            belt = top
            roof_w = w
        section = [(0.0, bottom), (w * 0.9, bottom), (w * 0.99, bottom + 0.12), (w, (bottom + belt) * 0.5), (w, belt),
                   (roof_w + (w - roof_w) * 0.35, belt + (top - belt) * 0.45), (roof_w, top - 0.04), (roof_w * 0.55, top)]
        pts = section + [(-y, z) for y, z in reversed(section[1:])]
        rings.append([bm.verts.new((x, y, z)) for y, z in pts[:-1]])
    count = len(rings[0])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(count):
            j = (k + 1) % count
            bm.faces.new((a[k], b[k], b[j], a[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    body = lib.bm_to_object(bm, name)
    subsurf = body.modifiers.new("Subsurf", "SUBSURF")
    subsurf.levels = 2
    lib.apply_modifiers(body)

    # Radhaeuser
    axle_x = spec["wheelbase"] / 2
    for x in (-axle_x, axle_x):
        bpy.ops.mesh.primitive_cylinder_add(radius=spec["radius"] + 0.06, depth=width * 1.4, vertices=48,
                                            location=(x, 0, spec["radius"]), rotation=(math.pi / 2, 0, 0))
        cutter = bpy.context.active_object
        boolean = body.modifiers.new("Arch", "BOOLEAN")
        boolean.operation = "DIFFERENCE"
        boolean.object = cutter
        boolean.solver = "EXACT"
        lib.apply_modifiers(body)
        bpy.data.objects.remove(cutter, do_unlink=True)
    # Radhausschale (dunkel) als innere Flaeche
    liners = []
    for x in (-axle_x, axle_x):
        lbm = bmesh.new()
        lib.tapered_cylinder(lbm, spec["radius"] + 0.055, spec["radius"] + 0.055, -width * 0.35, width * 0.35, segments=40,
                             cap_bottom=False, cap_top=False)
        bmesh.ops.rotate(lbm, verts=lbm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
        bmesh.ops.translate(lbm, verts=lbm.verts, vec=(x, 0, spec["radius"]))
        remove = [v for v in lbm.verts if v.co.z < spec["radius"] - 0.02]
        bmesh.ops.delete(lbm, geom=remove, context="VERTS")
        bmesh.ops.reverse_faces(lbm, faces=lbm.faces)
        liner = lib.bm_to_object(lbm, "Liner")
        liners.append(liner)

    # Materialzonen nach Lage und Normale
    lib.assign_materials(body, [m[k] for k in SLOTS])
    idx = {k: i for i, k in enumerate(SLOTS)}
    g0, g1 = spec["glass"]
    pillar_w = 0.05
    lo, hi = spec["lights"]
    mesh = body.data
    for poly in mesh.polygons:
        c, n = poly.center, poly.normal
        u = c.x / half_l
        top = profile_height(spec, u)
        belt = min(spec["belt"], top - 0.05)
        slot = "paint"
        in_bed = spec.get("bed") and spec["bed"][0] <= u <= spec["bed"][1]
        if c.z > belt + 0.03 and c.z < top - 0.06 and g0 <= u <= g1 and abs(n.z) < 0.85 and not in_bed:
            if not any(abs(u - p) < pillar_w for p in spec["pillars"]):
                slot = "glass"
        if c.z < spec["clearance"] + 0.07:
            slot = "trim"
        if abs(u) > (axle_x + spec["radius"]) / half_l and c.z < spec["clearance"] + spec["trim_h"]:
            slot = "trim"
        if n.x > 0.35 and u > 0.85 and lo <= c.z <= hi:
            if abs(c.y) > half_w * 0.82:
                slot = "indicator_r" if c.y > 0 else "indicator_l"
            elif abs(c.y) > half_w * 0.42:
                slot = "headlight"
        if n.x > 0.5 and u > 0.9 and spec["clearance"] + spec["trim_h"] < c.z < lo and abs(c.y) < half_w * 0.5:
            slot = "grille"
        if n.x < -0.35 and u < -0.85 and lo - 0.05 <= c.z <= hi + 0.05 and abs(c.y) > half_w * 0.5:
            slot = "taillight" if abs(c.y) < half_w * 0.88 else ("indicator_r" if c.y > 0 else "indicator_l")
        poly.material_index = idx[slot]

    # Innenraum: Sitze, Armaturenbrett, Lenkrad (durch die Scheiben sichtbar)
    ibm = bmesh.new()
    ii = SLOTS.index("interior")
    floor_z = spec["clearance"] + 0.18
    if bus:
        for k in range(10):
            x = -half_l + 1.8 + k * 0.95
            for side in (-1, 1):
                lib.box(ibm, (x, side * 0.7, floor_z + 0.25), (0.45, 0.45, 0.1), ii)
                lib.box(ibm, (x - 0.2, side * 0.7, floor_z + 0.55), (0.08, 0.45, 0.6), ii)
        lib.box(ibm, (half_l - 0.9, -0.6, floor_z + 0.7), (0.5, 0.6, 0.5), ii)
    else:
        seat_x = -0.15 + (0.25 if spec.get("bed") else 0.0)
        for side in (-1, 1):
            lib.box(ibm, (seat_x, side * 0.38, floor_z + 0.25), (0.5, 0.5, 0.12), ii)
            front_top = min(floor_z + 0.925, profile_height(spec, (seat_x - 0.28) / half_l) - 0.12)
            lib.box(ibm, (seat_x - 0.28, side * 0.38, (floor_z + 0.3 + front_top) / 2), (0.1, 0.5, front_top - floor_z - 0.3), ii)
        if not spec.get("bed") and spec["class_"] == "Car" and spec not in (SPECS["Van"], SPECS["Sport"]):
            # Rueckbank; Lehne unter der Dachlinie halten
            back_x = seat_x - 1.05
            back_top = min(floor_z + 0.8, profile_height(spec, back_x / half_l) - 0.12)
            lib.box(ibm, (seat_x - 0.8, 0.0, floor_z + 0.25), (0.5, width * 0.7, 0.12), ii)
            lib.box(ibm, (back_x, 0.0, (floor_z + 0.3 + back_top) / 2), (0.1, width * 0.7, back_top - floor_z - 0.3), ii)
        dash_x = seat_x + 0.85
        lib.box(ibm, (dash_x, 0.0, spec["belt"] - 0.12), (0.4, width * 0.8, 0.22), ii)
        wheel_c = Vector((dash_x - 0.3, -0.38, spec["belt"] - 0.02))
        rim = bmesh.ops.create_cone(ibm, cap_ends=False, segments=24, radius1=0.19, radius2=0.19, depth=0.03,
                                    matrix=Matrix.Translation(wheel_c) @ Matrix.Rotation(math.radians(70), 4, "Y"))
        for f in {f for v in rim["verts"] for f in v.link_faces}:
            f.material_index = ii
    interior = lib.bm_to_object(ibm, "Interior")
    lib.assign_materials(interior, [m[k] for k in SLOTS])

    # Aussenspiegel
    mbm = bmesh.new()
    if not bus:
        for side in (-1, 1):
            x = (spec["glass"][1] - 0.05) * half_l
            lib.box(mbm, (x, side * (half_w + 0.1), spec["belt"] + 0.1), (0.1, 0.2, 0.12), SLOTS.index("paint"))
            lib.box(mbm, (x - 0.051, side * (half_w + 0.12), spec["belt"] + 0.1), (0.005, 0.16, 0.09), SLOTS.index("chrome"))
    else:
        for side in (-1, 1):
            lib.box(mbm, (half_l + 0.15, side * (half_w + 0.15), 2.2), (0.08, 0.1, 0.35), SLOTS.index("trim"))
            lib.box(mbm, (half_l - 0.05, side * (half_w + 0.02), 2.5), (0.45, 0.04, 0.04), SLOTS.index("trim"))  # Spiegelarm
    mirrors = lib.bm_to_object(mbm, "Mirrors")
    lib.assign_materials(mirrors, [m[k] for k in SLOTS])

    parts = [body, interior, mirrors] + liners
    if taxi:
        tbm = bmesh.new()
        lib.box(tbm, (-0.1, 0.0, spec["top"][4][1] + 0.1), (0.55, 0.22, 0.16), SLOTS.index("sign"))
        sign = lib.bm_to_object(tbm, "TaxiSign")
        lib.add_bevel(sign, 0.02, segments=2)
        lib.assign_materials(sign, [m[k] for k in SLOTS])
        lib.apply_modifiers(sign)
        parts.append(sign)
    for liner in liners:
        lib.assign_materials(liner, [m[k] for k in SLOTS])
        for poly in liner.data.polygons:
            poly.material_index = SLOTS.index("trim")
    obj = lib.join(parts, name)
    lib.shade_smooth(obj, 35.0)
    lib.uv_meters(obj)
    return obj


def build_wheel(name, spec, m):
    """Rad: Reifen (Rotationsprofil) + Felge mit 5 Speichen. Achse = Y, Aussenseite = +Y."""
    r, w = spec["radius"], spec["wheel_width"]
    rim_r = r * 0.66
    bm = bmesh.new()
    segments = 48
    profile = [(rim_r, -w / 2), (r * 0.95, -w / 2), (r, -w * 0.38), (r, w * 0.38), (r * 0.95, w / 2), (rim_r, w / 2)]
    rings = []
    for k in range(segments):
        a = 2 * math.pi * k / segments
        rings.append([bm.verts.new((math.cos(a) * rr, yy, math.sin(a) * rr)) for rr, yy in profile])
    for k in range(segments):
        nxt = (k + 1) % segments
        for p in range(len(profile) - 1):
            face = bm.faces.new((rings[k][p], rings[k][p + 1], rings[nxt][p + 1], rings[nxt][p]))
            face.material_index = 0
    # Felge: Scheibe, Nabe, Speichen
    lib.cylinder(bm, (0, w * 0.1, 0), rim_r, w * 0.9, segments=48, material_index=1, axis="Y")
    lib.cylinder(bm, (0, w * 0.46, 0), rim_r * 0.3, 0.05, segments=24, material_index=1, axis="Y")
    for k in range(5):
        a = 2 * math.pi * k / 5
        center = (math.cos(a) * rim_r * 0.55, w * 0.5, math.sin(a) * rim_r * 0.55)
        faces = lib.box(bm, center, (rim_r * 0.75, 0.035, 0.06), 1)
        verts = list({v for f in faces for v in f.verts})
        bmesh.ops.rotate(bm, verts=verts, cent=center, matrix=Matrix.Rotation(-a, 3, "Y"))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = lib.bm_to_object(bm, name)
    lib.assign_materials(obj, [m["tire"], m["rim"]])
    lib.shade_smooth(obj, 40.0)
    lib.uv_meters(obj)
    lib.mirror_to_unreal(obj)
    return lib.finalize(obj, "Vehicles", nanite=True, collision="none")


def make_skeletal(body, spec, name):
    """Kopie der Karosserie mit Armature: root + 4 Radknochen (Karosserie zu 100 % an root)."""
    mesh = body.data.copy()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    arm_data = bpy.data.armatures.new(name + "_Skeleton")
    armature = bpy.data.objects.new("root_" + name, arm_data)
    bpy.context.collection.objects.link(armature)
    lib.activate(armature)
    bpy.ops.object.mode_set(mode="EDIT")
    root = arm_data.edit_bones.new("root")
    root.head, root.tail = (0, 0, 0), (0, 0.3, 0)
    axle = spec["wheelbase"] / 2
    track = spec["width"] / 2 - spec["wheel_width"] * 0.55
    # Unreal-Koordinaten (Y rechts); Armature wird nicht gespiegelt -> Blender-Y = -Unreal-Y
    for bone_name, x, y in (("wheel_fl", axle, -track), ("wheel_fr", axle, track), ("wheel_rl", -axle, -track), ("wheel_rr", -axle, track)):
        bone = arm_data.edit_bones.new(bone_name)
        bone.head = (x, -y, spec["radius"])
        bone.tail = (x, -y + 0.2, spec["radius"])
        bone.parent = root
    bpy.ops.object.mode_set(mode="OBJECT")
    group = obj.vertex_groups.new(name="root")
    group.add(list(range(len(mesh.vertices))), 1.0, "REPLACE")
    modifier = obj.modifiers.new("Armature", "ARMATURE")
    modifier.object = armature
    obj.parent = armature
    return obj, armature


def export_skeletal(obj, armature, spec, out_root, kind):
    folder = os.path.join(out_root, "Vehicles", obj.name)
    os.makedirs(folder, exist_ok=True)
    lib.deselect_all()
    # Unreal legt fuer den Armature-Knoten keinen eigenen Knochen an, wenn er "Armature" heisst
    original_name = armature.name
    armature.name = "Armature"
    obj.select_set(True)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.export_scene.fbx(filepath=os.path.join(folder, obj.name + ".fbx"), use_selection=True,
                             object_types={"ARMATURE", "MESH"}, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             axis_forward="-Z", axis_up="Y", add_leaf_bones=False, use_armature_deform_only=False,
                             bake_anim=False, mesh_smooth_type="FACE", use_triangles=True, use_tspace=True, path_mode="STRIP")
    armature.name = original_name
    meta = {"category": "Vehicles", "skeletal": True, "vehicle": kind, "nanite": False, "collision": "none",
            "slots": {mat.name: {k[3:]: (v.to_list() if hasattr(v, "to_list") else v) for k, v in mat.items() if k.startswith("vb_")}
                      for mat in obj.data.materials if mat},
            "spec": {k: v for k, v in spec.items() if k in ("length", "width", "wheelbase", "radius", "wheel_width", "mass", "clearance")}}
    with open(os.path.join(folder, obj.name + ".json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2)


def build_motorcycle(m):
    bm = bmesh.new()
    idx = {k: i for i, k in enumerate(SLOTS)}
    for x in (-0.72, 0.72):
        lib.cylinder(bm, (x, 0, 0.31), 0.31, 0.12, segments=32, material_index=idx["trim"], axis="Y")
        lib.cylinder(bm, (x, 0, 0.31), 0.2, 0.13, segments=24, material_index=idx["chrome"], axis="Y")
    lib.box(bm, (0.0, 0, 0.55), (0.9, 0.3, 0.35), idx["paint"])            # Tank/Motorblock
    lib.box(bm, (-0.35, 0, 0.78), (0.6, 0.28, 0.1), idx["interior"])        # Sitzbank
    lib.box(bm, (0.3, 0, 0.8), (0.45, 0.32, 0.22), idx["paint"])            # Tank
    lib.box(bm, (0.72, 0, 0.62), (0.06, 0.05, 0.62), idx["chrome"])         # Gabel
    lib.box(bm, (0.68, 0, 1.0), (0.06, 0.7, 0.04), idx["trim"])             # Lenker
    lib.box(bm, (0.8, 0, 0.9), (0.08, 0.16, 0.14), idx["headlight"])
    lib.box(bm, (-0.8, 0, 0.8), (0.05, 0.14, 0.06), idx["taillight"])
    obj = lib.bm_to_object(bm, "SM_VB_Moto_Street")
    lib.add_bevel(obj, 0.01, segments=2)
    lib.assign_materials(obj, [m[k] for k in SLOTS])
    lib.apply_modifiers(obj)
    lib.uv_meters(obj)
    lib.mirror_to_unreal(obj)
    lib.add_box_collision(obj, [((0, 0, 0.55), (2.0, 0.6, 1.1))])
    return lib.finalize(obj, "Vehicles", nanite=True)


def main():
    args = lib.cli_args()
    lib.reset_scene()
    m = materials()
    statics, skeletal = [], []
    models = [("Sport", "Sport", False), ("Sedan", "Sedan", False), ("Taxi", "Sedan", True), ("SUV", "SUV", False),
              ("Pickup", "Pickup", False), ("Van", "Van", False), ("Bus", "Bus", False)]
    for label, spec_name, taxi in models:
        spec = SPECS[spec_name]
        body = build_body("SM_VB_Car_%s" % label, spec, m, taxi=taxi)
        lib.mirror_to_unreal(body)
        lib.finalize(body, "Vehicles", nanite=True, collision="auto")
        body["vb_paint"] = list(PAINT[label])
        body["vb_vehicle_spec"] = json.dumps({k: v for k, v in spec.items() if k in ("length", "width", "wheelbase", "radius",
                                                                                  "wheel_width", "mass", "clearance")})
        statics.append(body)
        if spec_name == label:
            statics.append(build_wheel("SM_VB_Wheel_%s" % label, spec, m))
        if spec["class_"] == "Car":
            skeletal.append((make_skeletal(body, spec, "SK_VB_Car_%s" % label), spec, label))
    statics.append(build_motorcycle(m))
    for obj in statics:
        print("%-24s %7d Dreiecke" % (obj.name, lib.vb_blender_export.triangle_count(obj)))
    if args.get("blend"):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args["blend"]))
    status = 0
    if args.get("out"):
        out = os.path.abspath(args["out"])
        exported, _ = lib.export(out, only=[o.name for o in statics])
        for (obj, armature), spec, label in skeletal:
            export_skeletal(obj, armature, spec, out, label)
        # Fahrzeugdaten fuer Unreal (Masse, Rad- und Achsmasse, Lackfarbe)
        catalog = {}
        for label, spec_name, _taxi in models:
            spec = SPECS[spec_name]
            catalog[label] = {"spec": {k: spec[k] for k in ("length", "width", "wheelbase", "radius", "wheel_width", "mass", "clearance")},
                              "paint": PAINT[label], "wheel": "SM_VB_Wheel_%s" % spec_name, "class": spec["class_"]}
        with open(os.path.join(out, "Vehicles", "vehicles.json"), "w", encoding="utf-8") as handle:
            json.dump(catalog, handle, indent=2)
        status = 0 if exported == len(statics) else 1
    if args.get("preview"):
        os.makedirs(args["preview"], exist_ok=True)
        for (obj, armature), _spec, _label in skeletal:
            obj.hide_render = True
        x = 0.0
        for obj in statics:
            if obj.name.startswith("SM_VB_Car_"):
                label = obj.name[len("SM_VB_Car_"):]
                spec = SPECS["Sedan" if label == "Taxi" else label]
                x += spec["length"] / 2
                obj.location = (x, 0, 0)
                wheel = bpy.data.objects.get("SM_VB_Wheel_%s" % ("Sedan" if label == "Taxi" else label))
                track = spec["width"] / 2 - spec["wheel_width"] * 0.55
                for wx in (spec["wheelbase"] / 2, -spec["wheelbase"] / 2):
                    for side in (-1, 1):
                        inst = bpy.data.objects.new("w", wheel.data)
                        inst.location = (x + wx, side * track, spec["radius"])
                        inst.rotation_euler = (0, 0, 0 if side < 0 else math.pi)
                        bpy.context.collection.objects.link(inst)
                paint = bpy.data.materials["CarPaint"].copy()
                paint.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*PAINT[label], 1)
                obj.material_slots[0].link = "OBJECT"
                obj.material_slots[0].material = paint
                x += spec["length"] / 2 + 1.5
            elif obj.name.startswith("SM_VB_Wheel_") or obj.name.startswith("SM_VB_Moto"):
                obj.hide_render = obj.name.startswith("SM_VB_Wheel_")
                if obj.name.startswith("SM_VB_Moto"):
                    obj.location = (x + 1.0, 0, 0)
        x += 2.0
        lib.render_preview(os.path.join(args["preview"], "vehicles.png"), (x * 0.5, 0, 1.0), (x * 0.5, 38, 7),
                           resolution=(1800, 560), lens=24, samples=40)
    return status


if __name__ == "__main__":
    sys.exit(main())
