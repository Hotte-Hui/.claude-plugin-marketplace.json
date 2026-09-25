"""Veyra Bay Strassen-Kit (Phase 2): modulare Strassenteile + Stadtmoebel mit echter Geometrie.

Aufruf:
    blender -b --factory-startup --python vb_asset_streetkit.py -- --out <SourceAssets/Export>
            [--blend <datei.blend>] [--preview <ordner>] [--textures <SourceAssets/Export>]

Alle Masse sind in UNREAL-Koordinaten angegeben (X vorwaerts, Y rechts); die Teile werden vor dem
Export mit lib.mirror_to_unreal() gespiegelt, weil der FBX-Import Y negiert.
Rechtsverkehr: Fahrtrichtung +X faehrt auf der +Y-Seite.

Querschnitt (Meter, Y quer zur Strasse, Strassenmitte = 0, Fahrtrichtung +X):
    Fahrbahn Asphalt  |y| <= 5.60   Wölbung: 6 cm in der Mitte, linear zum Rand
    Rinne (Beton)     5.60 .. 6.00  faellt von 0 auf -1 cm
    Bordstein Granit  6.00 .. 6.18  Oberkante +15 cm
    Gehweg            6.18 .. 9.78  Oberkante +15 cm (9 x 40-cm-Platten)
Alle Kit-Teile haben den Pivot am Anfang (X=0) und kacheln entlang +X.
"""

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vb_blender_lib as lib  # noqa: E402

ROAD_LENGTH = 10.0
ASPHALT_HALF = 5.6
GUTTER_OUTER = 6.0
CROWN = 0.06
CURB_WIDTH = 0.18
CURB_HEIGHT = 0.15
PAVER = 0.4
PAVER_JOINT = 0.004
SIDEWALK_ROWS = 9
SIDEWALK_LENGTH = 2.0
CURB_LENGTH = 2.0
CURB = GUTTER_OUTER  # Bordsteinkante (Abstand zur Strassenmitte)


def road_z(y):
    """Hoehe der Fahrbahnoberflaeche (Wölbung + Rinne)."""
    a = abs(y)
    if a <= ASPHALT_HALF:
        return CROWN * (1.0 - a / ASPHALT_HALF)
    return -0.01 * min(1.0, (a - ASPHALT_HALF) / (GUTTER_OUTER - ASPHALT_HALF))


# ---------------------------------------------------------------------------
# Materialien
# ---------------------------------------------------------------------------
def materials():
    m = {}
    m["asphalt"] = lib.make_material("Asphalt", (0.05, 0.05, 0.052), 0.85, surface="Asphalt")
    m["gutter"] = lib.make_material("Gutter", (0.3, 0.29, 0.27), 0.88, surface="Concrete")
    m["paint"] = lib.make_material("RoadPaint", (0.72, 0.72, 0.70), 0.5, porosity=0.15, puddle_response=1.0)
    m["granite"] = lib.make_material("CurbGranite", (0.3, 0.3, 0.3), 0.6, surface="Granite")
    m["paver"] = lib.make_material("Paver", (0.33, 0.32, 0.3), 0.88, surface="Concrete")
    m["joint"] = lib.make_material("PaverJoint", (0.09, 0.085, 0.08), 0.95, porosity=0.9, puddle_response=0.0)
    m["iron"] = lib.make_material("CastIron", (0.28, 0.28, 0.29), 0.5, 0.85, surface="CastIron")
    m["paint_dark"] = lib.make_material("PaintAnthracite", (0.045, 0.048, 0.05), 0.45, porosity=0.05)
    m["paint_green"] = lib.make_material("PaintGreen", (0.04, 0.08, 0.06), 0.45, porosity=0.05)
    m["paint_red"] = lib.make_material("PaintRed", (0.42, 0.035, 0.03), 0.4, porosity=0.05)
    m["steel"] = lib.make_material("Steel", (0.6, 0.6, 0.62), 0.3, 1.0, porosity=0.0)
    m["reflector"] = lib.make_material("Reflector", (0.8, 0.8, 0.78), 0.25, porosity=0.0)
    m["wood"] = lib.make_material("BenchWood", (0.3, 0.18, 0.09), 0.65, surface="Wood")
    m["sign_blue"] = lib.make_material("SignBlue", (0.02, 0.1, 0.42), 0.35, porosity=0.0)
    m["sign_red"] = lib.make_material("SignRed", (0.55, 0.025, 0.02), 0.35, porosity=0.0)
    m["signal_black"] = lib.make_material("SignalHousing", (0.018, 0.018, 0.02), 0.5, porosity=0.0)
    m["lens"] = lib.make_material("SignalLens", (0.2, 0.2, 0.2), 0.08, porosity=0.0, wetness_response=0.0,
                                  emissive_color=(1.0, 1.0, 1.0), emissive_intensity=3000.0, use_night_switch=True)
    return m


def rotated_box(bm, center, size, angle, axis="Z", material_index=0):
    faces = lib.box(bm, center, size, material_index)
    verts = list({v for f in faces for v in f.verts})
    bmesh.ops.rotate(bm, verts=verts, cent=center, matrix=Matrix.Rotation(angle, 3, axis))


def annulus(bm, r_inner, r_outer, z0, z1, segments=64, material_index=0):
    """Flacher, geschlossener Ring (Kreisring mit Hoehe)."""
    loops = []
    for radius in (r_outer, r_inner):
        for z in (z0, z1):
            loops.append([bm.verts.new((radius * math.cos(2 * math.pi * i / segments),
                                        radius * math.sin(2 * math.pi * i / segments), z)) for i in range(segments)])
    outer_bottom, outer_top, inner_bottom, inner_top = loops
    faces = []
    for i in range(segments):
        j = (i + 1) % segments
        faces.append(bm.faces.new((outer_bottom[i], outer_bottom[j], outer_top[j], outer_top[i])))
        faces.append(bm.faces.new((inner_bottom[j], inner_bottom[i], inner_top[i], inner_top[j])))
        faces.append(bm.faces.new((outer_top[i], outer_top[j], inner_top[j], inner_top[i])))
        faces.append(bm.faces.new((inner_bottom[i], inner_bottom[j], outer_bottom[j], outer_bottom[i])))
    for face in faces:
        face.material_index = material_index
    return faces


def surface_box(bm, x0, x1, y0, y1, zfunc, lift, depth, material_index):
    """Quader, dessen Ober- und Unterseite der Fahrbahnoberflaeche folgen (fuer Markierungen)."""
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    top = [bm.verts.new((x, y, zfunc(y) + lift)) for x, y in corners]
    bottom = [bm.verts.new((x, y, zfunc(y) - depth)) for x, y in corners]
    faces = [bm.faces.new(top), bm.faces.new(list(reversed(bottom)))]
    for i in range(4):
        j = (i + 1) % 4
        faces.append(bm.faces.new((bottom[i], bottom[j], top[j], top[i])))
    for face in faces:
        face.material_index = material_index
    return faces


# ---------------------------------------------------------------------------
# Fahrbahn
# ---------------------------------------------------------------------------
def build_road(name, m, crosswalk=False):
    bm = bmesh.new()
    ys = [-GUTTER_OUTER, -ASPHALT_HALF, -4.2, -2.8, -1.4, 0.0, 1.4, 2.8, 4.2, ASPHALT_HALF, GUTTER_OUTER]
    xs = [ROAD_LENGTH * i / 10 for i in range(11)]
    grid = [[bm.verts.new((x, y, road_z(y))) for y in ys] for x in xs]
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            face = bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
            face.material_index = 0 if abs(ys[j] + ys[j + 1]) * 0.5 < ASPHALT_HALF else 1
    # Unterbau (nicht sichtbar, schliesst die Seiten fuer Lumen/Distanzfelder)
    base = -0.3
    for x_index in (0, len(xs) - 1):
        row = grid[x_index]
        low = [bm.verts.new((row[0].co.x, y, base)) for y in ys]
        for j in range(len(ys) - 1):
            quad = (row[j], row[j + 1], low[j + 1], low[j])
            face = bm.faces.new(quad if x_index == 0 else tuple(reversed(quad)))
            face.material_index = 1
    bm.normal_update()
    for face in bm.faces:
        if face.normal.z < -0.5:
            face.normal_flip()

    paint = 2
    # Randlinien (durchgehend, 12 cm)
    for side in (-1, 1):
        y0, y1 = sorted((side * 5.29, side * 5.41))
        surface_box(bm, 0.0, ROAD_LENGTH, y0, y1, road_z, 0.003, 0.01, paint)
    if crosswalk:
        # Zebrastreifen: 50 cm breit, 4 m lang, keiner liegt auf dem First
        for k in range(10):
            yc = (k - 4.5) * 1.0
            surface_box(bm, 3.0, 7.0, yc - 0.25, yc + 0.25, road_z, 0.003, 0.01, paint)
        # Haltelinien je Fahrtrichtung (Rechtsverkehr: +X faehrt auf +Y)
        surface_box(bm, 1.5, 1.8, 0.1, 5.25, road_z, 0.003, 0.01, paint)
        surface_box(bm, 8.2, 8.5, -5.25, -0.1, road_z, 0.003, 0.01, paint)
    else:
        # Leitlinie: 4 m Strich / 6 m Luecke
        surface_box(bm, 3.0, 7.0, -0.06, 0.06, road_z, 0.003, 0.01, paint)

    obj = lib.bm_to_object(bm, name)
    lib.assign_materials(obj, [m["asphalt"], m["gutter"], m["paint"]])
    lib.uv_meters(obj)
    lib.mirror_to_unreal(obj)
    return lib.finalize(obj, "Roads", nanite=True, collision="complex", puddle_response=1.0)


# ---------------------------------------------------------------------------
# Bordstein
# ---------------------------------------------------------------------------
def build_curb(m):
    bm = bmesh.new()
    radius = 0.03
    profile = [(0.0, -0.25), (0.0, CURB_HEIGHT - radius)]
    for step in range(1, 6):
        angle = math.radians(180 - 90 * step / 6)
        profile.append((radius + radius * math.cos(angle), CURB_HEIGHT - radius + radius * math.sin(angle)))
    profile += [(radius, CURB_HEIGHT), (CURB_WIDTH, CURB_HEIGHT), (CURB_WIDTH, -0.25)]
    # Profil muss gegen den Uhrzeigersinn (von +X gesehen) laufen -> umdrehen
    lib.extrude_profile_x(bm, list(reversed(profile)), CURB_LENGTH - 0.005, segments=1, material_index=0)
    obj = lib.bm_to_object(bm, "SM_VB_Curb_2m")
    lib.add_bevel(obj, 0.004, segments=2, limit_angle=50.0)
    lib.assign_materials(obj, [m["granite"]])
    lib.apply_modifiers(obj)
    lib.uv_meters(obj)
    lib.mirror_to_unreal(obj)
    return lib.finalize(obj, "Roads", nanite=True, collision="auto", puddle_response=0.0)


# ---------------------------------------------------------------------------
# Gehweg aus Einzelplatten
# ---------------------------------------------------------------------------
def build_sidewalk(m):
    rng = random.Random(5)
    slabs = []
    columns = int(round(SIDEWALK_LENGTH / PAVER))
    for c in range(columns):
        for r in range(SIDEWALK_ROWS):
            bm = bmesh.new()
            size = PAVER - PAVER_JOINT
            top = CURB_HEIGHT + rng.uniform(-0.0015, 0.0015)
            center = (c * PAVER + PAVER * 0.5, CURB_WIDTH + r * PAVER + PAVER * 0.5, top - 0.03)
            lib.box(bm, center, (size, size, 0.06), 0)
            slab = lib.bm_to_object(bm, "Slab_%d_%d" % (c, r))
            lib.activate(slab)
            bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
            slab.rotation_euler = (math.radians(rng.uniform(-0.25, 0.25)), math.radians(rng.uniform(-0.25, 0.25)), 0.0)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            lib.add_bevel(slab, 0.004, segments=2, limit_angle=50.0)
            lib.assign_materials(slab, [m["paver"], m["joint"]])
            lib.apply_modifiers(slab)
            lib.uv_meters(slab)
            # Zufaelliger UV-Versatz je Platte -> jede Platte sieht anders aus
            du, dv = rng.random() * 1.5, rng.random() * 1.5
            for loop_uv in slab.data.uv_layers.active.data:
                loop_uv.uv = (loop_uv.uv[0] + du, loop_uv.uv[1] + dv)
            slabs.append(slab)

    # Fugensand / Bettung unter den Platten
    bm = bmesh.new()
    width = SIDEWALK_ROWS * PAVER
    lib.box(bm, (SIDEWALK_LENGTH * 0.5, CURB_WIDTH + width * 0.5, (CURB_HEIGHT - 0.012 - 0.25) * 0.5),
            (SIDEWALK_LENGTH, width, CURB_HEIGHT - 0.012 + 0.25), 1)
    bedding = lib.bm_to_object(bm, "Bedding")
    lib.assign_materials(bedding, [m["paver"], m["joint"]])
    lib.uv_meters(bedding)

    obj = lib.join(slabs + [bedding], "SM_VB_Sidewalk_2m")
    lib.mirror_to_unreal(obj)
    return lib.finalize(obj, "Roads", nanite=True, collision="auto", puddle_response=1.0)


# ---------------------------------------------------------------------------
# Kanaldeckel
# ---------------------------------------------------------------------------
def build_manhole(m):
    bm = bmesh.new()
    lib.tapered_cylinder(bm, 0.39, 0.39, -0.08, 0.004, segments=48, rings=1)          # Rahmen
    lib.tapered_cylinder(bm, 0.315, 0.315, -0.02, 0.006, segments=48, rings=1)        # Deckel
    # Relief: durchgehende konzentrische Ringe + Radialrippen, die nur ZWISCHEN den Ringen liegen
    # (keine ueberlappenden Flaechen -> keine Artefakte)
    rings = (0.09, 0.17, 0.25)
    for radius in rings:
        annulus(bm, radius - 0.007, radius + 0.007, 0.006, 0.011, segments=64)
    bounds = [0.05] + list(rings) + [0.3]
    for inner, outer in zip(bounds[:-1], bounds[1:]):
        r0, r1 = inner + (0.009 if inner in rings else 0.0), outer - (0.009 if outer in rings else 0.0)
        count = 8 if inner < 0.1 else 16
        for i in range(count):
            angle = 2 * math.pi * (i + 0.5 * (inner > 0.1)) / count
            mid = (r0 + r1) * 0.5
            rotated_box(bm, (mid * math.cos(angle), mid * math.sin(angle), 0.0085), (r1 - r0, 0.012, 0.005), angle)
    lib.cylinder(bm, (0.0, 0.0, 0.0085), 0.045, 0.005, segments=24)
    obj = lib.bm_to_object(bm, "SM_VB_Manhole_A")
    lib.add_bevel(obj, 0.0015, segments=1, limit_angle=50.0)
    lib.assign_materials(obj, [m["iron"]])
    lib.apply_modifiers(obj)
    lib.uv_meters(obj)
    return lib.finalize(obj, "Roads", nanite=True, collision="none", puddle_response=0.0)


# ---------------------------------------------------------------------------
# Stadtmoebel
# ---------------------------------------------------------------------------
def build_bollard(m):
    bm = bmesh.new()
    lib.tapered_cylinder(bm, 0.11, 0.11, 0.0, 0.015, segments=32)                        # Fussflansch
    lib.tapered_cylinder(bm, 0.07, 0.068, 0.015, 0.86, segments=32, rings=4)
    dome = bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=12, radius=0.068,
                                     matrix=Matrix.Translation((0, 0, 0.86)))
    for vert in dome["verts"]:
        if vert.co.z < 0.86:
            vert.co.z = 0.86
    reflective = []
    for z in (0.66, 0.74):
        reflective += lib.cylinder(bm, (0, 0, z), 0.0715, 0.045, segments=32, material_index=1)
    obj = lib.bm_to_object(bm, "SM_VB_Bollard_A")
    lib.add_bevel(obj, 0.003, segments=2)
    lib.assign_materials(obj, [m["paint_dark"], m["reflector"]])
    lib.apply_modifiers(obj)
    lib.shade_smooth(obj)
    lib.uv_meters(obj)
    lib.add_box_collision(obj, [((0, 0, 0.46), (0.15, 0.15, 0.92))])
    return lib.finalize(obj, "Props", nanite=True)


def build_bench(m):
    parts = []
    # Seitenteile (Gusseisen-Profil), 5 cm stark
    side_profile = [(0.0, 0.0), (0.06, 0.0), (0.12, 0.38), (0.5, 0.38), (0.48, 0.0), (0.54, 0.0),
                    (0.55, 0.43), (0.12, 0.45), (0.05, 0.86), (0.0, 0.86), (0.06, 0.43)]
    for x in (0.12, 1.68):
        bm = bmesh.new()
        verts_front = [bm.verts.new((x - 0.025, y - 0.27, z)) for y, z in side_profile]
        verts_back = [bm.verts.new((x + 0.025, y - 0.27, z)) for y, z in side_profile]
        bm.faces.new(verts_front)
        bm.faces.new(list(reversed(verts_back)))
        count = len(side_profile)
        for i in range(count):
            j = (i + 1) % count
            bm.faces.new((verts_front[i], verts_front[j], verts_back[j], verts_back[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        leg = lib.bm_to_object(bm, "BenchLeg")
        lib.add_bevel(leg, 0.006, segments=2)
        lib.assign_materials(leg, [m["paint_green"], m["wood"]])
        lib.apply_modifiers(leg)
        parts.append(leg)
    # Holzlatten: 3 Sitz, 2 Lehne
    slats = [((0.9, -0.2, 0.46), 0.0), ((0.9, -0.06, 0.465), 0.0), ((0.9, 0.08, 0.47), 0.0),
             ((0.9, 0.2, 0.62), 72.0), ((0.9, 0.24, 0.76), 72.0)]
    for center, tilt in slats:
        bm = bmesh.new()
        lib.box(bm, (0, 0, 0), (1.9, 0.1, 0.035), 1)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(tilt), 3, "X"))
        bmesh.ops.translate(bm, verts=bm.verts, vec=center)
        slat = lib.bm_to_object(bm, "BenchSlat")
        lib.add_bevel(slat, 0.007, segments=3)
        lib.assign_materials(slat, [m["paint_green"], m["wood"]])
        lib.apply_modifiers(slat)
        parts.append(slat)
    obj = lib.join(parts, "SM_VB_Bench_A")
    lib.uv_meters(obj)
    # Pivot mittig unten, Sitzflaeche (bisher -Y) nach +X drehen (Kit-Konvention: Vorderseite = +X)
    rotation = Matrix.Rotation(math.radians(90.0), 4, "Z")
    for vert in obj.data.vertices:
        vert.co.x -= 0.9
        vert.co = rotation @ vert.co
    obj.data.update()
    lib.add_box_collision(obj, [((0.0, 0.0, 0.45), (0.55, 1.9, 0.9))])
    return lib.finalize(obj, "Props", nanite=True)


def build_trash_bin(m):
    bm = bmesh.new()
    lib.tapered_cylinder(bm, 0.24, 0.24, 0.0, 0.03, segments=32)                         # Boden
    lib.tapered_cylinder(bm, 0.255, 0.255, 0.8, 0.85, segments=32)                       # Deckelring
    lib.tapered_cylinder(bm, 0.2, 0.2, 0.85, 0.86, segments=32)                          # Einwurf
    for i in range(28):                                                                  # Lamellen
        angle = 2 * math.pi * i / 28
        center = (0.245 * math.cos(angle), 0.245 * math.sin(angle), 0.415)
        rotated_box(bm, center, (0.012, 0.035, 0.77), angle)
    lib.tapered_cylinder(bm, 0.225, 0.225, 0.03, 0.8, segments=32, rings=1, material_index=1)  # Einsatz
    obj = lib.bm_to_object(bm, "SM_VB_TrashBin_A")
    lib.add_bevel(obj, 0.003, segments=2)
    lib.assign_materials(obj, [m["paint_dark"], m["steel"]])
    lib.apply_modifiers(obj)
    lib.uv_meters(obj)
    lib.add_box_collision(obj, [((0, 0, 0.43), (0.52, 0.52, 0.86))])
    return lib.finalize(obj, "Props", nanite=True)


def build_hydrant(m):
    bm = bmesh.new()
    lib.tapered_cylinder(bm, 0.16, 0.16, 0.0, 0.04, segments=32)                         # Flansch
    for i in range(8):                                                                   # Schrauben
        angle = 2 * math.pi * i / 8
        lib.cylinder(bm, (0.135 * math.cos(angle), 0.135 * math.sin(angle), 0.05), 0.012, 0.02, segments=6, material_index=1)
    lib.tapered_cylinder(bm, 0.105, 0.095, 0.04, 0.62, segments=32, rings=3)
    lib.tapered_cylinder(bm, 0.12, 0.12, 0.62, 0.66, segments=32)                        # Kopfring
    dome = bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=12, radius=0.1, matrix=Matrix.Translation((0, 0, 0.66)))
    for vert in dome["verts"]:
        vert.co.z = max(vert.co.z, 0.66)
    lib.cylinder(bm, (0, 0, 0.78), 0.025, 0.05, segments=5, material_index=1)            # Betaetigungsmutter
    for side in (-1, 1):                                                                 # Abgaenge
        lib.cylinder(bm, (0, side * 0.14, 0.42), 0.045, 0.1, segments=24, axis="Y")
        lib.cylinder(bm, (0, side * 0.2, 0.42), 0.055, 0.03, segments=24, material_index=1, axis="Y")
    lib.cylinder(bm, (0.14, 0, 0.36), 0.06, 0.1, segments=24, axis="X")
    lib.cylinder(bm, (0.2, 0, 0.36), 0.07, 0.035, segments=24, material_index=1, axis="X")
    obj = lib.bm_to_object(bm, "SM_VB_Hydrant_A")
    lib.add_bevel(obj, 0.003, segments=2)
    lib.assign_materials(obj, [m["paint_red"], m["steel"]])
    lib.apply_modifiers(obj)
    lib.shade_smooth(obj)
    lib.uv_meters(obj)
    lib.add_box_collision(obj, [((0.03, 0, 0.4), (0.34, 0.46, 0.8))])
    return lib.finalize(obj, "Props", nanite=True)


def build_sign(m):
    bm = bmesh.new()
    lib.tapered_cylinder(bm, 0.03, 0.03, 0.0, 2.55, segments=20, rings=2, material_index=2)
    # Schild: Halteverbot (blau mit rotem Rand und rotem Kreuz), Vorderseite zeigt nach +X
    lib.cylinder(bm, (0.035, 0, 2.2), 0.3, 0.008, segments=48, material_index=2, axis="X")        # Traeger
    lib.cylinder(bm, (0.041, 0, 2.2), 0.3, 0.004, segments=48, material_index=1, axis="X")        # roter Rand
    lib.cylinder(bm, (0.044, 0, 2.2), 0.25, 0.004, segments=48, material_index=0, axis="X")       # blaues Feld
    for angle in (45.0, -45.0):
        rotated_box(bm, (0.047, 0, 2.2), (0.004, 0.5, 0.055), math.radians(angle), axis="X", material_index=1)
    for z in (2.05, 2.35):                                                                        # Schellen
        lib.cylinder(bm, (0, 0, z), 0.036, 0.04, segments=20, material_index=2)
    obj = lib.bm_to_object(bm, "SM_VB_Sign_NoStopping")
    lib.add_bevel(obj, 0.0015, segments=1)
    lib.assign_materials(obj, [m["sign_blue"], m["sign_red"], m["steel"]])
    lib.apply_modifiers(obj)
    lib.uv_meters(obj)
    lib.add_box_collision(obj, [((0, 0, 1.28), (0.08, 0.08, 2.56))])
    return lib.finalize(obj, "Props", nanite=True)


# Ampel: Gehaeuse X 0.08..0.32, Linsen-Front X=0.325 bei Z 3.2 / 2.9 / 2.6 (muss zu AVBTrafficLight passen)
SIGNAL_LENS_X = 0.325
SIGNAL_LENS_Z = (3.2, 2.9, 2.6)


def build_traffic_light(m):
    bm = bmesh.new()
    lib.tapered_cylinder(bm, 0.14, 0.14, 0.0, 0.02, segments=32, material_index=0)          # Fussplatte
    lib.tapered_cylinder(bm, 0.062, 0.058, 0.02, 3.6, segments=32, rings=4, material_index=0)
    lib.box(bm, (0.075, 0, 2.9), (0.015, 0.42, 1.02), 1)                                    # Kontrastblende
    lib.box(bm, (0.2, 0, 2.9), (0.24, 0.3, 0.92), 1)                                        # Gehaeuse
    for z in SIGNAL_LENS_Z:
        lib.cylinder(bm, (SIGNAL_LENS_X - 0.006, 0, z), 0.112, 0.012, segments=32, material_index=1, axis="X")
    body = lib.bm_to_object(bm, "SignalBody")
    lib.add_bevel(body, 0.003, segments=2)
    lib.assign_materials(body, [m["paint_dark"], m["signal_black"]])
    lib.apply_modifiers(body)

    # Schuten (Blenden ueber den Linsen): offene Halbzylinder mit Materialstaerke
    bm = bmesh.new()
    for z in SIGNAL_LENS_Z:
        visor = bmesh.ops.create_cone(bm, cap_ends=False, segments=24, radius1=0.125, radius2=0.125, depth=0.17,
                                      matrix=Matrix.Translation((SIGNAL_LENS_X + 0.085, 0, z)) @ Matrix.Rotation(math.radians(90), 4, "Y"))
        remove = [v for v in visor["verts"] if v.co.z < z - 0.03]
        bmesh.ops.delete(bm, geom=remove, context="VERTS")
    visors = lib.bm_to_object(bm, "SignalVisors")
    solidify = visors.modifiers.new("Solidify", "SOLIDIFY")
    solidify.thickness = 0.004
    lib.assign_materials(visors, [m["paint_dark"], m["signal_black"]])
    for polygon in visors.data.polygons:
        polygon.material_index = 1
    lib.apply_modifiers(visors)

    obj = lib.join([body, visors], "SM_VB_TrafficLight_A")
    lib.uv_meters(obj)
    lib.add_box_collision(obj, [((0, 0, 1.8), (0.14, 0.14, 3.6)), ((0.2, 0, 2.9), (0.3, 0.42, 1.02))])
    return lib.finalize(obj, "Props", nanite=True)


def build_signal_lens(m):
    bm = bmesh.new()
    sphere = bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.1)
    for vert in sphere["verts"]:
        vert.co.x = max(vert.co.x, 0.0) * 0.18  # flache Kuppel nach +X
    obj = lib.bm_to_object(bm, "SM_VB_SignalLens")
    lib.assign_materials(obj, [m["lens"]])
    lib.shade_smooth(obj, 60.0)
    lib.uv_smart(obj)
    return lib.finalize(obj, "Props", nanite=False, collision="none")


# ---------------------------------------------------------------------------
# Kreuzung (4 Arme, Bordsteinradius 3 m, Zebrastreifen + Haltelinien)
# ---------------------------------------------------------------------------
INTERSECTION_HALF = CURB + CURB_WIDTH + SIDEWALK_ROWS * PAVER   # 9.78 m bis zur Gebaeudeflucht
CORNER_RADIUS = 3.0


# Arme: "+X", "-X", "+Y", "-Y". Fehlende Arme -> dort laeuft der Bordstein gerade durch (T- und L-Stuecke).
ALL_ARMS = ("+X", "-X", "+Y", "-Y")


def _arm(sign, axis):
    return ("+" if sign > 0 else "-") + axis


def quadrant_has_corner(arms, sx, sy):
    """Abgerundete Ecke nur, wenn beide angrenzenden Arme existieren."""
    return _arm(sx, "X") in arms and _arm(sy, "Y") in arms


def is_road(x, y, arms=ALL_ARMS):
    ax, ay = abs(x), abs(y)
    if ax <= CURB and ay <= CURB:
        return True                                        # Kreuzungskern
    if ay <= CURB and ax > CURB:
        return _arm(x, "X") in arms                        # Arm entlang X
    if ax <= CURB and ay > CURB:
        return _arm(y, "Y") in arms                        # Arm entlang Y
    if not quadrant_has_corner(arms, x, y):
        return False
    corner = CURB + CORNER_RADIUS
    return ax < corner and ay < corner and math.hypot(ax - corner, ay - corner) > CORNER_RADIUS


def is_sidewalk(x, y, margin=CURB_WIDTH, arms=ALL_ARMS):
    """Gehweg = keine Fahrbahn im Umkreis der Bordsteinbreite (robust fuer alle Arm-Kombinationen)."""
    if is_road(x, y, arms):
        return False
    for i in range(16):
        angle = 2.0 * math.pi * i / 16
        if is_road(x + math.cos(angle) * margin, y + math.sin(angle) * margin, arms):
            return False
    return True


def intersection_z(x, y, arms=ALL_ARMS):
    profiles = [0.0]
    if "+X" in arms or "-X" in arms:
        profiles.append(1.0 - abs(y) / ASPHALT_HALF)
    if "+Y" in arms or "-Y" in arms:
        profiles.append(1.0 - abs(x) / ASPHALT_HALF)
    return CROWN * max(profiles)


def curb_path(arms, sx, sy):
    """Bordsteinkante eines Quadranten als [(Punkt, Normale zum Gehweg, Gehrungsfaktor)].
    Regel: Die Normale liegt rechts der Laufrichtung (im Quadranten +,+); gespiegelte Quadranten drehen die Flaechen."""
    half, corner = INTERSECTION_HALF, CURB + CORNER_RADIUS
    arm_x, arm_y = _arm(sx, "X") in arms, _arm(sy, "Y") in arms
    if arm_x and arm_y:
        points = [((half, CURB), (0.0, 1.0), 1.0), ((corner, CURB), (0.0, 1.0), 1.0)]
        steps = 16
        for i in range(1, steps):
            angle = math.radians(-90.0 - 90.0 * i / steps)
            px, py = corner + CORNER_RADIUS * math.cos(angle), corner + CORNER_RADIUS * math.sin(angle)
            points.append(((px, py), ((corner - px) / CORNER_RADIUS, (corner - py) / CORNER_RADIUS), 1.0))
        points += [((CURB, corner), (1.0, 0.0), 1.0), ((CURB, half), (1.0, 0.0), 1.0)]
    elif arm_x:
        points = [((half, CURB), (0.0, 1.0), 1.0), ((0.0, CURB), (0.0, 1.0), 1.0)]
    elif arm_y:
        points = [((CURB, 0.0), (1.0, 0.0), 1.0), ((CURB, half), (1.0, 0.0), 1.0)]
    else:
        diag = 1.0 / math.sqrt(2.0)
        points = [((CURB, 0.0), (1.0, 0.0), 1.0), ((CURB, CURB), (diag, diag), math.sqrt(2.0)), ((0.0, CURB), (0.0, 1.0), 1.0)]
    return [((px * sx, py * sy), (nx * sx, ny * sy), k) for (px, py), (nx, ny), k in points]


def sweep_curb(bm, path, flip, material_index):
    radius = 0.03
    profile = [(0.0, -0.25), (0.0, CURB_HEIGHT - radius)]
    for step in range(1, 6):
        angle = math.radians(180 - 90 * step / 6)
        profile.append((radius + radius * math.cos(angle), CURB_HEIGHT - radius + radius * math.sin(angle)))
    profile += [(radius, CURB_HEIGHT), (CURB_WIDTH, CURB_HEIGHT), (CURB_WIDTH, -0.25)]
    rings = [[bm.verts.new((px + nx * d * k, py + ny * d * k, z)) for d, z in profile] for (px, py), (nx, ny), k in path]
    count = len(profile)
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(count):
            j = (i + 1) % count
            quad = (a[i], a[j], b[j], b[i])
            face = bm.faces.new(tuple(reversed(quad)) if flip else quad)
            face.material_index = material_index


def build_intersection(m, name="SM_VB_Intersection_4Way", arms=ALL_ARMS):
    """Kreuzung (4 Arme), T-Stueck (3 Arme) oder Ecke (2 Arme). Unreal-Koordinaten, Pivot = Mitte."""
    bm = bmesh.new()
    half, cell = INTERSECTION_HALF, 0.25
    count = int(round(2 * half / cell))
    grid = {}

    def vert(i, j):
        key = (i, j)
        if key not in grid:
            x, y = -half + i * cell, -half + j * cell
            grid[key] = bm.verts.new((x, y, intersection_z(x, y, arms)))
        return grid[key]

    for i in range(count):
        for j in range(count):
            x0, y0 = -half + i * cell, -half + j * cell
            corners = [(x0, y0), (x0 + cell, y0), (x0 + cell, y0 + cell), (x0, y0 + cell)]
            if any(is_road(x, y, arms) for x, y in corners):
                face = bm.faces.new((vert(i, j), vert(i + 1, j), vert(i + 1, j + 1), vert(i, j + 1)))
                face.material_index = 0

    def arm_z(y):
        return CROWN * max(1.0 - abs(y) / ASPHALT_HALF, 0.0)

    # Markierungen nur auf vorhandenen Armen (fuer Arm +X gebaut, dann gedreht)
    for index, arm in enumerate(("+X", "+Y", "-X", "-Y")):
        if arm not in arms:
            continue
        before = set(bm.faces)
        for k in range(10):
            yc = (k - 4.5) * 1.0
            surface_box(bm, 6.4, 9.2, yc - 0.25, yc + 0.25, arm_z, 0.003, 0.01, 1)
        # Haltelinie fuer Fahrzeuge, die auf diesem Arm zur Kreuzung fahren (-X): rechte Spur = -Y
        surface_box(bm, 9.35, 9.65, -5.25, -0.1, arm_z, 0.003, 0.01, 1)
        new_verts = {v for f in set(bm.faces) - before for v in f.verts}
        bmesh.ops.rotate(bm, verts=list(new_verts), cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90 * index), 3, "Z"))

    for sx in (-1, 1):
        for sy in (-1, 1):
            sweep_curb(bm, curb_path(arms, sx, sy), flip=(sx * sy < 0), material_index=2)

    road = lib.bm_to_object(bm, "IntersectionRoad")
    slots = [m["asphalt"], m["paint"], m["granite"], m["paver"], m["joint"]]
    lib.assign_materials(road, slots)
    lib.uv_meters(road)

    # Gehwegplatten (nur ganze Platten) + gegossene Passstuecke darunter
    rng = random.Random(11 + len(arms))
    slabs = []
    rows = int(round(2 * half / PAVER))
    for a in range(rows):
        for b in range(rows):
            x0, y0 = -half + a * PAVER, -half + b * PAVER
            corners = [(x0, y0), (x0 + PAVER, y0), (x0 + PAVER, y0 + PAVER), (x0, y0 + PAVER)]
            if not all(is_sidewalk(x, y, arms=arms) for x, y in corners):
                continue
            sbm = bmesh.new()
            size = PAVER - PAVER_JOINT
            top = CURB_HEIGHT + rng.uniform(-0.0015, 0.0015)
            lib.box(sbm, (x0 + PAVER / 2, y0 + PAVER / 2, top - 0.03), (size, size, 0.06), 3)
            slab = lib.bm_to_object(sbm, "Slab")
            lib.add_bevel(slab, 0.004, segments=2, limit_angle=50.0)
            lib.assign_materials(slab, slots)
            lib.apply_modifiers(slab)
            lib.uv_meters(slab)
            du, dv = rng.random() * 1.5, rng.random() * 1.5
            for loop_uv in slab.data.uv_layers.active.data:
                loop_uv.uv = (loop_uv.uv[0] + du, loop_uv.uv[1] + dv)
            slabs.append(slab)

    fill = bmesh.new()
    fcell = 0.1
    steps = int(round(2 * half / fcell))
    for a in range(steps):
        for b in range(steps):
            x0, y0 = -half + a * fcell, -half + b * fcell
            if not is_sidewalk(x0 + fcell / 2, y0 + fcell / 2, margin=CURB_WIDTH * 0.5, arms=arms):
                continue
            quad = [fill.verts.new((x, y, CURB_HEIGHT - 0.012))
                    for x, y in ((x0, y0), (x0 + fcell, y0), (x0 + fcell, y0 + fcell), (x0, y0 + fcell))]
            fill.faces.new(quad).material_index = 3  # gegossener Beton als Passstueck
    bmesh.ops.remove_doubles(fill, verts=fill.verts, dist=1e-5)
    bedding = lib.bm_to_object(fill, "Bedding")
    lib.assign_materials(bedding, slots)
    lib.uv_meters(bedding)

    obj = lib.join([road, bedding] + slabs, name)
    lib.mirror_to_unreal(obj)
    return lib.finalize(obj, "Roads", nanite=True, collision="complex", puddle_response=1.0)


BUILDERS = [
    lambda m: build_road("SM_VB_Road_10m", m),
    lambda m: build_road("SM_VB_Road_10m_Crosswalk", m, crosswalk=True),
    build_curb, build_sidewalk, build_manhole, build_bollard, build_bench, build_trash_bin,
    build_hydrant, build_sign, build_traffic_light, build_signal_lens, build_intersection,
    # T-Stueck: Arm -Y fehlt (Bordstein laeuft unten durch); Ecke: nur Arme +X und +Y
    lambda m: build_intersection(m, "SM_VB_Intersection_T", ("+X", "-X", "+Y")),
    lambda m: build_intersection(m, "SM_VB_Intersection_Corner", ("+X", "+Y")),
]

# Kamera je Asset: (Ziel, Kameraposition)
PREVIEWS = {
    "SM_VB_Intersection_4Way": ((0, 0, 0), (14, -16, 12)),
    "SM_VB_Intersection_T": ((0, 0, 0), (14, -16, 12)),
    "SM_VB_Intersection_Corner": ((0, 0, 0), (14, -16, 12)),
    "SM_VB_Road_10m_Crosswalk": ((5, 0, 0), (-4, -9, 5)),
    "SM_VB_Curb_2m": ((1, 0.1, 0.05), (2.2, -0.9, 0.5)),
    "SM_VB_Sidewalk_2m": ((1, 1.5, 0.15), (2.6, -0.8, 1.3)),
    "SM_VB_Manhole_A": ((0, 0, 0), (0.7, -0.7, 0.8)),
    "SM_VB_Bollard_A": ((0, 0, 0.5), (1.2, -1.4, 1.0)),
    "SM_VB_Bench_A": ((0, 0, 0.45), (2.2, 1.6, 1.3)),
    "SM_VB_TrashBin_A": ((0, 0, 0.45), (1.1, -1.3, 1.1)),
    "SM_VB_Hydrant_A": ((0, 0, 0.4), (0.9, -0.9, 0.8)),
    "SM_VB_Sign_NoStopping": ((0, 0, 1.9), (2.4, -1.6, 2.2)),
    "SM_VB_TrafficLight_A": ((0.1, 0, 2.3), (3.2, -2.6, 2.6)),
}


def main():
    args = lib.cli_args()
    lib.reset_scene()
    m = materials()
    assets = [build(m) for build in BUILDERS]
    for asset in assets:
        asset.location = (0, 0, 0)
        print("%-28s %6d Dreiecke" % (asset.name, lib.vb_blender_export.triangle_count(asset)))

    if args.get("blend"):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args["blend"]))
    status = 0
    if args.get("out"):
        exported, report = lib.export(args["out"])
        status = 0 if exported == len(assets) else 1

    preview_dir = args.get("preview")
    if preview_dir:
        os.makedirs(preview_dir, exist_ok=True)
        blend = os.path.abspath(args["blend"]) if args.get("blend") else None
        for name, (target, camera) in PREVIEWS.items():
            if blend:
                bpy.ops.wm.open_mainfile(filepath=blend)
            for obj in bpy.data.objects:
                obj.hide_render = obj.name != name and obj.parent is None
            lib.render_preview(os.path.join(preview_dir, name + ".png"), target, camera, resolution=(640, 420),
                               samples=24, preview_textures_root=args.get("textures"))
    return status


if __name__ == "__main__":
    sys.exit(main())
