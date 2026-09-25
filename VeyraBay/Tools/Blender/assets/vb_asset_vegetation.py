"""Veyra Bay Vegetation (Phase 4): Palme (Promenade) und Platane (Strassen/Hoefe) + Blatt-Texturen.

    blender -b --factory-startup --python vb_asset_vegetation.py -- --out <SourceAssets/Export>
            [--blend <datei.blend>] [--preview <ordner>]

Blaetter/Wedel sind Alpha-Karten mit dem Unreal-Master "Foliage" (maskiert, zweiseitig, Wind aus der MPC).
Texturen (RGBA) werden hier mit numpy erzeugt und neben die FBX gelegt (T_<Name>_<Slot>_D.png).
"""

import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vb_blender_lib as lib  # noqa: E402


# ---------------------------------------------------------------------------
# Texturen
# ---------------------------------------------------------------------------
def frond_texture(width=256, height=1024, seed=3, dead=False):
    """Palmwedel: Mittelrippe + schraege Fiederblaetter, Alpha-Kanal. Zeile 0 = Wedelbasis."""
    rng = np.random.default_rng(seed)
    img = np.zeros((height, width, 4), dtype=np.float32)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    u = (xx + 0.5) / width * 2.0 - 1.0          # -1 .. 1 quer
    v = (yy + 0.5) / height                     # 0 .. 1 entlang (0 = Basis)
    alpha = np.zeros((height, width), dtype=np.float32)
    shade = np.zeros((height, width), dtype=np.float32)
    count = 70
    for i in range(count):
        start = 0.08 + 0.9 * i / count
        side = 1 if i % 2 else -1
        length = 0.95 * math.sin(math.pi * min(start, 0.98)) ** 0.6
        for s in np.linspace(0.0, 1.0, 40):
            cu = side * s * length
            cv = start + s * 0.12
            w = 0.022 * (1.0 - s) ** 0.7 + 0.004
            mask = np.exp(-(((u - cu) / 0.06) ** 2 + ((v - cv) / w) ** 2))
            alpha = np.maximum(alpha, mask)
            shade = np.maximum(shade, mask * (0.7 + 0.3 * s))
    rib = np.exp(-(u / 0.035) ** 2) * (v > 0.02)
    alpha = np.clip(np.maximum(alpha * 1.6, rib), 0.0, 1.0)
    base = np.array([0.16, 0.24, 0.06]) if not dead else np.array([0.42, 0.32, 0.18])
    tip = np.array([0.24, 0.30, 0.09]) if not dead else np.array([0.52, 0.42, 0.26])
    variation = rng.normal(0.0, 0.03, (height, width))
    color = base[None, None, :] * (1 - v[..., None]) + tip[None, None, :] * v[..., None]
    color = color * (0.75 + 0.35 * shade[..., None]) + variation[..., None]
    color = np.where(rib[..., None] > 0.5, color * 1.2 + 0.05, color)
    img[..., :3] = np.clip(color, 0, 1)
    img[..., 3] = alpha
    return img


def leaf_cluster_texture(size=512, seed=8):
    """Blattbuschel (Platane): viele gelappte Blaetter mit Farbvariation, Alpha-Kanal."""
    rng = np.random.default_rng(seed)
    img = np.zeros((size, size, 4), dtype=np.float32)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    for _ in range(170):
        cx, cy = rng.uniform(0.08, 0.92), rng.uniform(0.08, 0.92)
        r = np.hypot(cx - 0.5, cy - 0.5)
        if r > 0.47:
            continue
        radius = rng.uniform(0.035, 0.06)
        angle = rng.uniform(0, 2 * np.pi)
        dx, dy = xx - cx, yy - cy
        rx = dx * np.cos(angle) + dy * np.sin(angle)
        ry = -dx * np.sin(angle) + dy * np.cos(angle)
        theta = np.arctan2(ry, rx)
        lobes = radius * (0.75 + 0.25 * np.abs(np.cos(2.5 * theta)))
        mask = np.clip((lobes - np.hypot(rx, ry)) / 0.004, 0.0, 1.0)
        tone = rng.uniform(0.0, 1.0)
        color = np.array([0.12, 0.2, 0.05]) * (1 - tone) + np.array([0.26, 0.34, 0.09]) * tone
        light = 0.8 + 0.4 * np.clip(rx / radius, -1, 1)
        vein = 1.0 - 0.25 * np.exp(-(ry / 0.002) ** 2)
        layer = color[None, None, :] * (light * vein)[..., None]
        img[..., :3] = img[..., :3] * (1 - mask[..., None]) + layer * mask[..., None]
        img[..., 3] = np.maximum(img[..., 3], mask)
    return img


# ---------------------------------------------------------------------------
# Geometrie-Helfer
# ---------------------------------------------------------------------------
def tube(bm, points, radii, segments, material_index, cap=True):
    """Rohr entlang einer Punktliste (Stamm/Ast)."""
    rings = []
    up = Vector((0, 0, 1))
    for i, (point, radius) in enumerate(zip(points, radii)):
        tangent = (points[min(i + 1, len(points) - 1)] - points[max(i - 1, 0)]).normalized()
        side = tangent.cross(up if abs(tangent.dot(up)) < 0.95 else Vector((1, 0, 0))).normalized()
        other = tangent.cross(side).normalized()
        rings.append([bm.verts.new(point + (side * math.cos(a) + other * math.sin(a)) * radius)
                      for a in (2 * math.pi * k / segments for k in range(segments))])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(segments):
            j = (k + 1) % segments
            bm.faces.new((a[k], a[j], b[j], b[k])).material_index = material_index
    if cap:
        bm.faces.new(list(reversed(rings[0]))).material_index = material_index
        bm.faces.new(rings[-1]).material_index = material_index


def card(bm, uv_layer, center, normal, up, width, height, material_index, uv_rect=(0, 0, 1, 1)):
    normal, up = normal.normalized(), up.normalized()
    right = up.cross(normal).normalized()
    up = normal.cross(right).normalized()
    corners = [center + right * (-width / 2) + up * (-height / 2), center + right * (width / 2) + up * (-height / 2),
               center + right * (width / 2) + up * (height / 2), center + right * (-width / 2) + up * (height / 2)]
    face = bm.faces.new([bm.verts.new(c) for c in corners])
    face.material_index = material_index
    u0, v0, u1, v1 = uv_rect
    for loop, uv in zip(face.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
        loop[uv_layer].uv = uv


# ---------------------------------------------------------------------------
# Palme
# ---------------------------------------------------------------------------
def build_palm(m, name="SM_VB_PalmTree_A", seed=1, height=9.0):
    rng = random.Random(seed)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    lean = Vector((rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), 0))
    points, radii = [], []
    steps = 60
    for i in range(steps + 1):
        t = i / steps
        base = Vector((0, 0, t * height)) + lean * (t ** 2)
        ring = 1.0 + 0.06 * math.sin(t * height / 0.12 * math.pi)          # Blattnarben-Ringe
        points.append(base)
        radii.append((0.24 - 0.07 * t) * ring + (0.1 * max(0.0, 0.08 - t) * 6))  # verdickter Fuss
    tube(bm, points, radii, 16, 0)
    top = points[-1]
    # Krone: 16 gruene Wedel + 4 haengende, trockene
    fronds = [(i, False) for i in range(16)] + [(i, True) for i in range(4)]
    for index, dead in fronds:
        azimuth = 2 * math.pi * (index / (4 if dead else 16)) + rng.uniform(-0.15, 0.15) + (0.4 if dead else 0)
        pitch = math.radians(rng.uniform(-75, -60) if dead else rng.uniform(-10, 45))
        length = rng.uniform(2.6, 3.4) if dead else rng.uniform(3.2, 3.8)
        direction = Vector((math.cos(azimuth) * math.cos(pitch), math.sin(azimuth) * math.cos(pitch), math.sin(pitch)))
        side = Vector((-math.sin(azimuth), math.cos(azimuth), 0))
        segs = 8
        prev = None
        for k in range(segs + 1):
            t = k / segs
            droop = Vector((0, 0, -1.6 * t * t)) if not dead else Vector((0, 0, -0.2 * t))
            center = top + direction * (length * t) + droop
            fold = Vector((0, 0, 0.18 * math.sin(math.pi * t)))
            half = 0.62 * math.sin(math.pi * min(t * 1.1 + 0.05, 1.0)) + 0.05
            ring = [bm.verts.new(center + side * -half - fold), bm.verts.new(center + fold * 0.3), bm.verts.new(center + side * half - fold)]
            if prev:
                for a, b, u0, u1 in ((0, 1, 0.0, 0.5), (1, 2, 0.5, 1.0)):
                    face = bm.faces.new((prev[a], ring[a], ring[b], prev[b]))
                    face.material_index = 2 if dead else 1
                    for loop, (uu, vv) in zip(face.loops, ((u0, (k - 1) / segs), (u0, t), (u1, t), (u1, (k - 1) / segs))):
                        loop[uv].uv = (uu, vv)
            prev = ring
    obj = lib.bm_to_object(bm, name)
    lib.assign_materials(obj, [m["palm_trunk"], m["frond"], m["frond_dead"]])
    lib.shade_smooth(obj, 60)
    # Stamm-UVs in Metern (Rinde), Wedel behalten ihre 0..1-UVs
    trunk_faces = [p for p in obj.data.polygons if p.material_index == 0]
    uv_data = obj.data.uv_layers.active.data
    for poly in trunk_faces:
        for li in poly.loop_indices:
            co = obj.data.vertices[obj.data.loops[li].vertex_index].co
            uv_data[li].uv = (math.atan2(co.y, co.x) / math.pi * 0.35, co.z)
    lib.add_box_collision(obj, [((0, 0, height / 2), (0.5, 0.5, height))])
    return lib.finalize(obj, "Vegetation", nanite=True, collision="auto")


# ---------------------------------------------------------------------------
# Platane
# ---------------------------------------------------------------------------
def build_plane_tree(m, name="SM_VB_PlaneTree_A", seed=2):
    rng = random.Random(seed)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    tips = []

    def branch(start, direction, length, radius, depth):
        points, radii = [], []
        steps = 6
        d = direction.normalized()
        for i in range(steps + 1):
            t = i / steps
            wobble = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.3, 0.5))) * 0.08 * t
            points.append(start + d * (length * t) + wobble * length)
            radii.append(radius * (1.0 - 0.6 * t))
        tube(bm, points, radii, 10 if depth == 0 else 6, 0, cap=depth > 0)
        end = points[-1]
        if depth >= 3:
            tips.append((end, d))
            return
        children = 3 if depth < 2 else 3
        for c in range(children):
            azimuth = rng.uniform(0, 2 * math.pi)
            spread = math.radians(rng.uniform(25, 50))
            axis = d.cross(Vector((math.cos(azimuth), math.sin(azimuth), 0)))
            new_dir = (Matrix.Rotation(spread, 3, axis if axis.length > 1e-4 else Vector((1, 0, 0))) @ d)
            new_dir.z = max(new_dir.z, 0.15)
            origin = points[rng.randint(3, steps)]
            branch(origin, new_dir, length * rng.uniform(0.55, 0.75), radius * 0.55, depth + 1)

    trunk_height = 3.2
    tube(bm, [Vector((0, 0, 0)), Vector((0, 0, trunk_height * 0.5)), Vector((0.05, 0.02, trunk_height))], [0.28, 0.22, 0.2], 14, 0, cap=True)
    for c in range(4):
        azimuth = 2 * math.pi * c / 4 + rng.uniform(-0.3, 0.3)
        direction = Vector((math.cos(azimuth) * 0.6, math.sin(azimuth) * 0.6, 1.0))
        branch(Vector((0.05, 0.02, trunk_height - 0.2)), direction, rng.uniform(3.4, 4.2), 0.14, 1)

    # Blattbueschel an den Zweigspitzen (je 7 Karten, zufaellig orientiert)
    for end, d in tips:
        for _ in range(7):
            offset = Vector((rng.uniform(-0.7, 0.7), rng.uniform(-0.7, 0.7), rng.uniform(-0.4, 0.6)))
            normal = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.2, 1)))
            card(bm, uv, end + offset, normal, Vector((0, 0, 1)) + d * 0.5, 1.5, 1.5, 1)
    obj = lib.bm_to_object(bm, name)
    lib.assign_materials(obj, [m["bark"], m["leaves"]])
    lib.shade_smooth(obj, 60)
    uv_data = obj.data.uv_layers.active.data
    for poly in obj.data.polygons:
        if poly.material_index != 0:
            continue
        for li in poly.loop_indices:
            co = obj.data.vertices[obj.data.loops[li].vertex_index].co
            uv_data[li].uv = (math.atan2(co.y, co.x) / math.pi * 0.5, co.z)
    lib.add_box_collision(obj, [((0, 0, trunk_height / 2), (0.55, 0.55, trunk_height))])
    return lib.finalize(obj, "Vegetation", nanite=True, collision="auto")


def materials():
    return {
        "palm_trunk": lib.make_material("PalmTrunk", (0.3, 0.26, 0.2), 0.85, surface="Bark"),
        "bark": lib.make_material("TreeBark", (0.3, 0.27, 0.2), 0.85, surface="Bark"),
        "frond": lib.make_material("PalmFrond", (0.2, 0.28, 0.08), 0.6, master="Foliage"),
        "frond_dead": lib.make_material("PalmFrondDead", (0.45, 0.35, 0.2), 0.7, master="Foliage"),
        "leaves": lib.make_material("PlaneLeaves", (0.18, 0.26, 0.07), 0.6, master="Foliage"),
    }


TEXTURES = {
    # Asset: {Slot: Textur}
    "SM_VB_PalmTree_A": {"PalmFrond": lambda: frond_texture(seed=3), "PalmFrondDead": lambda: frond_texture(seed=4, dead=True)},
    "SM_VB_PlaneTree_A": {"PlaneLeaves": lambda: leaf_cluster_texture(seed=8)},
}


def write_textures(out_root):
    for asset, slots in TEXTURES.items():
        folder = os.path.join(out_root, "Vegetation", asset)
        os.makedirs(folder, exist_ok=True)
        base = asset[3:]
        for slot, make in slots.items():
            image = make()
            path = os.path.join(folder, "T_%s_%s_D.png" % (base, slot))
            # write_png erwartet Blender-Zeilenfolge (unten zuerst): Zeile 0 der Textur = v = 0
            lib.write_png(path, image, alpha=True)


def main():
    args = lib.cli_args()
    lib.reset_scene()
    m = materials()
    assets = [build_palm(m), build_plane_tree(m)]
    for asset in assets:
        print("%-24s %7d Dreiecke" % (asset.name, lib.vb_blender_export.triangle_count(asset)))
    if args.get("blend"):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args["blend"]))
    status = 0
    if args.get("out"):
        exported, _ = lib.export(args["out"])
        write_textures(os.path.abspath(args["out"]))
        status = 0 if exported == len(assets) else 1
    if args.get("preview") and args.get("out"):
        for asset in assets:
            asset.location.x = -3.0 if "Palm" in asset.name else 4.0
        textures = {slot: os.path.join(os.path.abspath(args["out"]), "Vegetation", asset, "T_%s_%s_D.png" % (asset[3:], slot))
                    for asset, slots in TEXTURES.items() for slot in slots}
        for material in bpy.data.materials:
            path = textures.get(material.name)
            if not path:
                continue
            tree = material.node_tree
            bsdf = tree.nodes["Principled BSDF"]
            node = tree.nodes.new("ShaderNodeTexImage")
            node.image = bpy.data.images.load(path)
            tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
            tree.links.new(node.outputs["Alpha"], bsdf.inputs["Alpha"])
            bsdf.inputs["Emission Strength"].default_value = 0.0
        lib.apply_surface_previews(os.path.abspath(args["out"]))
        os.makedirs(args["preview"], exist_ok=True)
        lib.render_preview(os.path.join(args["preview"], "vegetation.png"), (0.5, 0, 4.5), (1, -17, 3.5), resolution=(1100, 720),
                           lens=35, samples=48)
    return status


if __name__ == "__main__":
    sys.exit(main())
