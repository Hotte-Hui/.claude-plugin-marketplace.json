"""Gemeinsame Bausteine fuer prozedurale Veyra-Bay-Assets in Blender.

- Geometrie-Helfer (Kegelstuempfe, Fasen, Kollision, UVs in Metern)
- Materialien mit Unreal-Metadaten (vb_*-Properties -> JSON -> Material-Instanzen)
- Oberflaechen-Baker: prozedurale Shader -> kachelbare PBR-Texturen (D / N / ORM)
- Vorschau-Rendering (Cycles, CPU)
"""

import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import vb_blender_export  # noqa: E402


# ---------------------------------------------------------------------------
# Szene & Kommandozeile
# ---------------------------------------------------------------------------
def cli_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = {}
    index = 0
    while index < len(argv):
        if argv[index].startswith("--"):
            key = argv[index][2:]
            if index + 1 < len(argv) and not argv[index + 1].startswith("--"):
                args[key] = argv[index + 1]
                index += 2
                continue
            args[key] = True
        index += 1
    return args


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    return scene


def deselect_all():
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)


def activate(obj):
    deselect_all()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


# ---------------------------------------------------------------------------
# Materialien (Metadaten fuer den Unreal-Import)
# ---------------------------------------------------------------------------
def make_material(name, base_color=(0.5, 0.5, 0.5), roughness=0.7, metallic=0.0, surface=None, **extra):
    """Material mit Vorschau-Farben in Blender und vb_*-Properties fuer Unreal.

    surface: Name einer gebackenen Oberflaeche (z. B. "Asphalt") - Unreal nutzt dann MI_VB_Surface_<Name>.
    extra:   porosity, wetness_response, puddle_response, emissive_color, emissive_intensity, use_night_switch
    """
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if "emissive_intensity" in extra:
            color = extra.get("emissive_color", (1.0, 0.9, 0.7))
            bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
            bsdf.inputs["Emission Strength"].default_value = 5.0
    material["vb_base_color"] = list(base_color)
    material["vb_roughness"] = roughness
    material["vb_metallic"] = metallic
    if surface:
        material["vb_surface"] = surface
    for key, value in extra.items():
        material["vb_" + key] = list(value) if isinstance(value, tuple) else value
    return material


def assign_materials(obj, materials):
    """Setzt die Materialslots, OHNE die Material-Indizes der Flaechen zu verlieren
    (materials.clear() wuerde sie alle auf 0 zuruecksetzen)."""
    mesh = obj.data
    indices = [0] * len(mesh.polygons)
    mesh.polygons.foreach_get("material_index", indices)
    mesh.materials.clear()
    for material in materials:
        mesh.materials.append(material)
    mesh.polygons.foreach_set("material_index", indices)
    mesh.update()


# ---------------------------------------------------------------------------
# Geometrie
# ---------------------------------------------------------------------------
def bm_to_object(bm, name):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def box(bm, center, size, material_index=0):
    """Quader in ein BMesh; gibt die neuen Flaechen zurueck."""
    result = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(center) @ Matrix.Diagonal((*size, 1.0)))
    faces = {f for v in result["verts"] for f in v.link_faces}
    for face in faces:
        face.material_index = material_index
    return list(faces)


def cylinder(bm, center, radius, depth, segments=24, material_index=0, radius_top=None, axis="Z"):
    rotation = {"Z": Matrix.Identity(4), "X": Matrix.Rotation(math.radians(90), 4, "Y"),
                "Y": Matrix.Rotation(math.radians(90), 4, "X")}[axis]
    result = bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius,
                                   radius2=radius if radius_top is None else radius_top, depth=depth,
                                   matrix=Matrix.Translation(center) @ rotation)
    faces = {f for v in result["verts"] for f in v.link_faces}
    for face in faces:
        face.material_index = material_index
    return list(faces)


def tapered_cylinder(bm, radius_bottom, radius_top, z_bottom, z_top, segments=32, rings=1, cap_bottom=True, cap_top=True,
                     material_index=0):
    layers = []
    for ring in range(rings + 1):
        t = ring / rings
        radius = radius_bottom + (radius_top - radius_bottom) * t
        z = z_bottom + (z_top - z_bottom) * t
        layers.append([bm.verts.new((radius * math.cos(2 * math.pi * i / segments),
                                     radius * math.sin(2 * math.pi * i / segments), z)) for i in range(segments)])
    faces = []
    for ring in range(rings):
        low, high = layers[ring], layers[ring + 1]
        for i in range(segments):
            j = (i + 1) % segments
            faces.append(bm.faces.new((low[i], low[j], high[j], high[i])))
    if cap_bottom:
        faces.append(bm.faces.new(list(reversed(layers[0]))))
    if cap_top:
        faces.append(bm.faces.new(layers[-1]))
    for face in faces:
        face.material_index = material_index
    return layers


def extrude_profile_x(bm, profile_yz, length, segments=1, material_index=0, cap=True):
    """Extrudiert ein geschlossenes Profil (Liste (y, z), gegen den Uhrzeigersinn) entlang +X von 0 bis length."""
    rings = []
    for s in range(segments + 1):
        x = length * s / segments
        rings.append([bm.verts.new((x, y, z)) for (y, z) in profile_yz])
    count = len(profile_yz)
    faces = []
    for s in range(segments):
        a, b = rings[s], rings[s + 1]
        for i in range(count):
            j = (i + 1) % count
            faces.append(bm.faces.new((a[i], a[j], b[j], b[i])))
    if cap:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
        faces.append(bm.faces.new(rings[-1]))
    for face in faces:
        face.material_index = material_index
    bm.normal_update()
    return faces


def mirror_to_unreal(obj):
    """Der FBX-Import von Unreal negiert Y (Blender +Y -> Unreal -Y). Kit-Teile, deren Seite zaehlt
    (Bordsteine, Fahrspuren, Fassaden), werden in Unreal-Koordinaten modelliert und hier einmal
    gespiegelt, damit sie in Unreal exakt so liegen wie entworfen."""
    obj.data.transform(Matrix.Scale(-1.0, 4, (0.0, 1.0, 0.0)))
    obj.data.flip_normals()
    obj.data.update()
    return obj


def add_bevel(obj, width, segments=2, limit_angle=35.0):
    modifier = obj.modifiers.new("Bevel", "BEVEL")
    modifier.width = width
    modifier.segments = segments
    modifier.limit_method = "ANGLE"
    modifier.angle_limit = math.radians(limit_angle)
    modifier.harden_normals = True
    modifier.miter_outer = "MITER_ARC"
    return modifier


def apply_modifiers(obj):
    activate(obj)
    for modifier in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=modifier.name)


def join(objects, name):
    deselect_all()
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    result = bpy.context.view_layer.objects.active
    result.name = name
    result.data.name = name
    return result


def shade_smooth(obj, angle=40.0):
    activate(obj)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))


def uv_meters(obj, cube_size=1.0):
    """Wuerfelprojektion: 1 UV-Einheit = cube_size Meter -> kachelnde Oberflaechen passen massstabsgetreu."""
    activate(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=cube_size, correct_aspect=False, clip_to_bounds=False, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def uv_smart(obj, angle=66.0, margin=0.003):
    activate(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def add_box_collision(asset, boxes):
    """boxes: Liste (center, size). Erzeugt UCX_<Asset>_## als Kinder."""
    for index, (center, size) in enumerate(boxes):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(center) @ Matrix.Diagonal((*size, 1.0)))
        collider = bm_to_object(bm, "UCX_%s_%02d" % (asset.name, index))
        collider.parent = asset
        collider.display_type = "WIRE"


def finalize(asset, category, nanite=True, collision="auto", **props):
    asset["vb_category"] = category
    asset["vb_nanite"] = nanite
    asset["vb_collision"] = collision
    for key, value in props.items():
        asset["vb_" + key] = value
    return asset


def export(out_root, only=None):
    """Exportiert alle SM_-Assets der Szene (oder nur die Namen in `only`)."""
    context = bpy.context
    if only:
        deselect_all()
        for name in only:
            bpy.data.objects[name].select_set(True)
    exported, report = vb_blender_export.export_all(context, os.path.abspath(out_root), only_selected=bool(only))
    for line in report:
        print(line)
    return exported, report


# ---------------------------------------------------------------------------
# Oberflaechen-Baker (prozedurale Shader -> kachelbare Texturen)
# ---------------------------------------------------------------------------
class Shader:
    """Kleiner Node-Baukasten. Alle Muster sind nahtlos kachelbar (4D-Torus-Koordinaten)."""

    def __init__(self, material):
        self.tree = material.node_tree
        self.nodes = self.tree.nodes
        self.links = self.tree.links
        self.nodes.clear()
        self.output = self.nodes.new("ShaderNodeOutputMaterial")
        self._torus = None

    def node(self, kind, **values):
        node = self.nodes.new(kind)
        for key, value in values.items():
            if hasattr(node, key):
                setattr(node, key, value)
            else:
                node.inputs[key].default_value = value
        return node

    def link(self, source, target):
        self.links.new(source, target)

    def _socket(self, value, node, index):
        if isinstance(value, (int, float)):
            node.inputs[index].default_value = value
        else:
            self.link(value, node.inputs[index])

    def math(self, operation, a, b=0.0, clamp=False):
        node = self.nodes.new("ShaderNodeMath")
        node.operation = operation
        node.use_clamp = clamp
        self._socket(a, node, 0)
        self._socket(b, node, 1)
        return node.outputs[0]

    def mix(self, a, b, factor):
        """Lineare Interpolation fuer Farben (Tupel oder Sockets)."""
        node = self.nodes.new("ShaderNodeMix")
        node.data_type = "RGBA"
        for value, socket in ((a, node.inputs[6]), (b, node.inputs[7])):
            if isinstance(value, tuple):
                socket.default_value = (*value, 1.0)
            else:
                self.link(value, socket)
        self._socket(factor, node, 0)
        return node.outputs[2]

    def lerp(self, a, b, factor):
        """Lineare Interpolation fuer Skalare."""
        node = self.nodes.new("ShaderNodeMix")
        node.data_type = "FLOAT"
        self._socket(factor, node, 0)
        self._socket(a, node, 2)
        self._socket(b, node, 3)
        return node.outputs[0]

    def smoothstep(self, edge0, edge1, value):
        node = self.nodes.new("ShaderNodeMapRange")
        node.interpolation_type = "SMOOTHSTEP"
        self._socket(value, node, 0)
        node.inputs[1].default_value = edge0
        node.inputs[2].default_value = edge1
        node.inputs[3].default_value = 0.0
        node.inputs[4].default_value = 1.0
        return node.outputs[0]

    def ramp(self, value, stops, interpolation="LINEAR"):
        """Farbverlauf: stops = [(position, (r, g, b)), ...]"""
        node = self.nodes.new("ShaderNodeValToRGB")
        node.color_ramp.interpolation = interpolation
        elements = node.color_ramp.elements
        while len(elements) < len(stops):
            elements.new(0.5)
        for element, (position, color) in zip(elements, stops):
            element.position = position
            element.color = (*color, 1.0)
        self._socket(value, node, 0)
        return node.outputs["Color"]

    def value(self, socket, scale=1.0, offset=0.0):
        """a * scale + offset"""
        return self.math("ADD", self.math("MULTIPLY", socket, scale), offset)

    def torus(self):
        """(vector3, w) auf einem 4D-Torus mit Umfang 1 -> Scale = Anzahl Merkmale pro Kachel."""
        if self._torus:
            return self._torus
        coords = self.nodes.new("ShaderNodeTexCoord")
        separate = self.nodes.new("ShaderNodeSeparateXYZ")
        self.link(coords.outputs["UV"], separate.inputs[0])
        radius = 1.0 / (2.0 * math.pi)
        parts = []
        for axis in (0, 1):
            angle = self.math("MULTIPLY", separate.outputs[axis], 2.0 * math.pi)
            parts.append(self.math("MULTIPLY", self.math("COSINE", angle), radius))
            parts.append(self.math("MULTIPLY", self.math("SINE", angle), radius))
        combine = self.nodes.new("ShaderNodeCombineXYZ")
        for index in range(3):
            self.link(parts[index], combine.inputs[index])
        self._torus = (combine.outputs[0], parts[3], separate)
        return self._torus

    def torus_aniso(self, freq_u, freq_v):
        """Anisotroper Torus: freq_u / freq_v Merkmale pro Kachel in U bzw. V (fuer Streifen, Schlieren)."""
        _, _, separate = self.torus()
        parts = []
        for axis, freq in ((0, freq_u), (1, freq_v)):
            angle = self.math("MULTIPLY", separate.outputs[axis], 2.0 * math.pi)
            radius = freq / (2.0 * math.pi)
            parts.append(self.math("MULTIPLY", self.math("COSINE", angle), radius))
            parts.append(self.math("MULTIPLY", self.math("SINE", angle), radius))
        combine = self.nodes.new("ShaderNodeCombineXYZ")
        for index in range(3):
            self.link(parts[index], combine.inputs[index])
        return combine.outputs[0], parts[3]

    def noise_aniso(self, freq_u, freq_v, detail=4.0, roughness=0.5):
        vector, w = self.torus_aniso(freq_u, freq_v)
        node = self.node("ShaderNodeTexNoise", noise_dimensions="4D")
        self.link(vector, node.inputs["Vector"])
        self.link(w, node.inputs["W"])
        node.inputs["Scale"].default_value = 1.0
        node.inputs["Detail"].default_value = detail
        node.inputs["Roughness"].default_value = roughness
        return node

    def white_noise(self, vector_socket):
        """Zufallswert je (ganzzahliger) Zelle - fuer Ziegel, Platten usw."""
        node = self.node("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
        self.link(vector_socket, node.inputs["Vector"])
        return node.outputs["Value"]

    def combine(self, x, y, z=0.0):
        node = self.nodes.new("ShaderNodeCombineXYZ")
        for index, value in enumerate((x, y, z)):
            self._socket(value, node, index)
        return node.outputs[0]

    def noise(self, scale, detail=4.0, roughness=0.5, distortion=0.0):
        vector, w, _ = self.torus()
        node = self.node("ShaderNodeTexNoise", noise_dimensions="4D")
        self.link(vector, node.inputs["Vector"])
        self.link(w, node.inputs["W"])
        node.inputs["Scale"].default_value = scale
        node.inputs["Detail"].default_value = detail
        node.inputs["Roughness"].default_value = roughness
        node.inputs["Distortion"].default_value = distortion
        return node

    def voronoi(self, scale, feature="F1", randomness=1.0):
        vector, w, _ = self.torus()
        node = self.node("ShaderNodeTexVoronoi", voronoi_dimensions="4D", feature=feature)
        self.link(vector, node.inputs["Vector"])
        self.link(w, node.inputs["W"])
        node.inputs["Scale"].default_value = scale
        node.inputs["Randomness"].default_value = randomness
        return node

    def voronoi_warped(self, scale, feature="F1", warp=0.25, warp_scale=3.0):
        """Voronoi mit verzerrten Koordinaten (organische statt polygonale Zellen), weiterhin kachelbar."""
        vector, w, _ = self.torus()
        warp_noise = self.noise(warp_scale, 3, 0.5)
        offset = self.nodes.new("ShaderNodeVectorMath")
        offset.operation = "SCALE"
        centered = self.nodes.new("ShaderNodeVectorMath")
        centered.operation = "SUBTRACT"
        self.link(warp_noise.outputs["Color"], centered.inputs[0])
        centered.inputs[1].default_value = (0.5, 0.5, 0.5)
        self.link(centered.outputs[0], offset.inputs[0])
        offset.inputs["Scale"].default_value = warp / (2.0 * math.pi)
        warped = self.nodes.new("ShaderNodeVectorMath")
        warped.operation = "ADD"
        self.link(vector, warped.inputs[0])
        self.link(offset.outputs[0], warped.inputs[1])
        node = self.node("ShaderNodeTexVoronoi", voronoi_dimensions="4D", feature=feature)
        self.link(warped.outputs[0], node.inputs["Vector"])
        self.link(w, node.inputs["W"])
        node.inputs["Scale"].default_value = scale
        return node

    def uv(self, axis):
        _, _, separate = self.torus()
        return separate.outputs[axis]


def _new_image(name, size, non_color, float_buffer=False):
    image = bpy.data.images.new(name, size, size, alpha=False, float_buffer=float_buffer)
    image.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    return image


def _bake_emit(obj, material, shader, socket, image):
    """Backt einen Farb- oder Skalar-Socket ueber Emission in ein Bild."""
    emission = shader.nodes.new("ShaderNodeEmission")
    shader.link(socket, emission.inputs["Color"])
    shader.link(emission.outputs[0], shader.output.inputs["Surface"])
    target = shader.nodes.new("ShaderNodeTexImage")
    target.image = image
    shader.nodes.active = target
    activate(obj)
    bpy.ops.object.bake(type="EMIT", margin=0, use_clear=True)
    shader.nodes.remove(target)
    shader.nodes.remove(emission)


def _bake_normal(obj, shader, height_socket, strength, distance, image):
    bsdf = shader.nodes.new("ShaderNodeBsdfPrincipled")
    bump = shader.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    shader.link(height_socket, bump.inputs["Height"])
    shader.link(bump.outputs["Normal"], bsdf.inputs["Normal"])
    shader.link(bsdf.outputs[0], shader.output.inputs["Surface"])
    target = shader.nodes.new("ShaderNodeTexImage")
    target.image = image
    shader.nodes.active = target
    activate(obj)
    bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", margin=0, use_clear=True)
    shader.nodes.remove(target)
    shader.nodes.remove(bump)
    shader.nodes.remove(bsdf)


def _pixels(image):
    size = image.size[0]
    array = np.empty(size * size * 4, dtype=np.float32)
    image.pixels.foreach_get(array)
    return array.reshape(size, size, 4)


def write_png(path, pixels, sixteen_bit=False, alpha=False):
    """Schreibt ein RGB-PNG aus einem (H, W, >=3) float-Array 0..1 (Blender-Zeilenreihenfolge: unten zuerst)."""
    import struct
    import zlib

    channels = 4 if alpha and pixels.shape[2] >= 4 else 3
    data = np.clip(np.flipud(pixels[:, :, :channels]), 0.0, 1.0)
    height, width = data.shape[:2]
    if sixteen_bit:
        raw_rows = (np.round(data * 65535.0).astype(">u2")).reshape(height, width * channels)
        depth = 16
    else:
        raw_rows = np.round(data * 255.0).astype(np.uint8).reshape(height, width * channels)
        depth = 8
    raw = b"".join(b"\x00" + raw_rows[row].tobytes() for row in range(height))

    def chunk(tag, payload):
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, depth, 6 if channels == 4 else 2, 0, 0, 0)
    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def linear_to_srgb(values):
    values = np.clip(values, 0.0, 1.0)
    return np.where(values <= 0.0031308, values * 12.92, 1.055 * np.power(values, 1.0 / 2.4) - 0.055)


def bake_surface(name, build, out_root, size=1024, tile_meters=1.0, normal_strength=1.0, bump_distance=0.02, params=None):
    """Backt eine prozedurale Oberflaeche in T_VB_<Name>_D/_N/_ORM.png + surface.json.

    build(shader) -> dict mit Sockets: color, roughness, height (0..1), optional metallic, ao.
    """
    reset_scene()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 4
    scene.render.bake.margin = 0
    scene.view_settings.view_transform = "Standard"

    bpy.ops.mesh.primitive_plane_add(size=1.0)
    plane = bpy.context.active_object
    material = bpy.data.materials.new("Bake_" + name)
    material.use_nodes = True
    plane.data.materials.append(material)

    shader = Shader(material)
    sockets = build(shader)

    out_dir = os.path.join(out_root, "Surfaces", name)
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, "T_VB_%s" % name)

    color_image = _new_image(name + "_D", size, non_color=True, float_buffer=True)
    _bake_emit(plane, material, shader, sockets["color"], color_image)
    color = _pixels(color_image)
    color[:, :, :3] = linear_to_srgb(color[:, :, :3])
    write_png(stem + "_D.png", color)

    channels = {}
    for key in ("ao", "roughness", "metallic"):
        socket = sockets.get(key)
        if socket is None or isinstance(socket, (int, float)):
            channels[key] = np.full((size, size), float(socket if socket is not None else (1.0 if key == "ao" else 0.0)))
            continue
        image = _new_image("%s_%s" % (name, key), size, non_color=True, float_buffer=True)
        _bake_emit(plane, material, shader, socket, image)
        channels[key] = _pixels(image)[:, :, 0]

    orm = np.ones((size, size, 4), dtype=np.float32)
    orm[:, :, 0] = np.clip(channels["ao"], 0, 1)
    orm[:, :, 1] = np.clip(channels["roughness"], 0, 1)
    orm[:, :, 2] = np.clip(channels["metallic"], 0, 1)
    write_png(stem + "_ORM.png", orm)

    normal_image = _new_image(name + "_N", size, non_color=True, float_buffer=True)
    _bake_normal(plane, shader, sockets["height"], normal_strength, bump_distance, normal_image)
    write_png(stem + "_N.png", _pixels(normal_image))  # 8 bit reicht: Unreal komprimiert nach BC5

    meta = {"surface": name, "tile_meters": tile_meters, "uv_tiling": 1.0 / tile_meters}
    meta.update(params or {})
    with open(os.path.join(out_dir, "surface.json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2)
    print("Oberflaeche %s gebacken (%dpx, %.2f m Kachel)" % (name, size, tile_meters))
    return out_dir


# ---------------------------------------------------------------------------
# Vorschau
# ---------------------------------------------------------------------------
def render_preview(path, target, camera_location, resolution=(900, 600), lens=50.0, samples=32, sun_angle=(50.0, 0.0, 30.0),
                   ground=True, preview_textures_root=None):
    scene = bpy.context.scene
    for obj in scene.objects:
        if obj.name.startswith("UCX_"):
            obj.hide_render = True
    if preview_textures_root:
        apply_surface_previews(preview_textures_root)
    if ground:
        bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, -0.001))
        ground_obj = bpy.context.active_object
        material = bpy.data.materials.new("PreviewGround")
        material.use_nodes = True
        material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.06, 0.06, 0.062, 1)
        material.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
        ground_obj.data.materials.append(material)
    camera = bpy.data.objects.new("PreviewCamera", bpy.data.cameras.new("PreviewCamera"))
    camera.data.lens = lens
    scene.collection.objects.link(camera)
    camera.location = camera_location
    camera.rotation_euler = (Vector(target) - Vector(camera_location)).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    sun = bpy.data.objects.new("PreviewSun", bpy.data.lights.new("PreviewSun", "SUN"))
    sun.data.energy = 4.0
    sun.data.angle = math.radians(1.0)
    sun.rotation_euler = tuple(math.radians(a) for a in sun_angle)
    scene.collection.objects.link(sun)
    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.5, 0.6, 0.75, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.filepath = path
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "AgX"
    bpy.ops.render.render(write_still=True)


def apply_surface_previews(textures_root):
    """Ersetzt in der Vorschau Materialien mit vb_surface durch die gebackenen Texturen (UV in Metern)."""
    for material in bpy.data.materials:
        surface = material.get("vb_surface")
        if not surface:
            continue
        folder = os.path.join(textures_root, "Surfaces", surface)
        meta_path = os.path.join(folder, "surface.json")
        if not os.path.isfile(meta_path):
            continue
        with open(meta_path, "r", encoding="utf-8") as handle:
            tiling = json.load(handle).get("uv_tiling", 1.0)
        tree = material.node_tree
        bsdf = tree.nodes.get("Principled BSDF")
        coords = tree.nodes.new("ShaderNodeTexCoord")
        mapping = tree.nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (tiling, tiling, tiling)
        tree.links.new(coords.outputs["UV"], mapping.inputs["Vector"])

        def texture(suffix, non_color):
            node = tree.nodes.new("ShaderNodeTexImage")
            node.image = bpy.data.images.load(os.path.join(folder, "T_VB_%s%s.png" % (surface, suffix)))
            node.image.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
            tree.links.new(mapping.outputs[0], node.inputs["Vector"])
            return node

        color = texture("_D", False)
        tint = material.get("vb_base_color")
        if tint is not None and material.get("vb_surface_tint", False):
            multiply = tree.nodes.new("ShaderNodeMix")
            multiply.data_type = "RGBA"
            multiply.blend_type = "MULTIPLY"
            multiply.inputs[0].default_value = 1.0
            tree.links.new(color.outputs[0], multiply.inputs[6])
            multiply.inputs[7].default_value = (*tint, 1.0)
            tree.links.new(multiply.outputs[2], bsdf.inputs["Base Color"])
        else:
            tree.links.new(color.outputs[0], bsdf.inputs["Base Color"])
        orm = texture("_ORM", True)
        separate = tree.nodes.new("ShaderNodeSeparateColor")
        tree.links.new(orm.outputs[0], separate.inputs[0])
        tree.links.new(separate.outputs[1], bsdf.inputs["Roughness"])
        tree.links.new(separate.outputs[2], bsdf.inputs["Metallic"])
        normal = texture("_N", True)
        normal_map = tree.nodes.new("ShaderNodeNormalMap")
        tree.links.new(normal.outputs[0], normal_map.inputs["Color"])
        tree.links.new(normal_map.outputs[0], bsdf.inputs["Normal"])
