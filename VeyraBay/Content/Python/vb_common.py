"""Gemeinsame Hilfsfunktionen fuer die Veyra-Bay-Editor-Tools.

Alle Tools laufen im Unreal Editor (Python Editor Script Plugin) und werden ueber
das Menue "Veyra Bay" in der Hauptmenueleiste gestartet (siehe init_unreal.py).
"""

import os
import struct
import zlib

import unreal

ROOT = "/Game/VeyraBay"

# Ordnerstruktur laut Docs/ARCHITECTURE.md
FOLDERS = [
    "Core/Blueprints", "Core/Data", "Core/Input",
    "Characters/Player", "Characters/MetaHumans", "Characters/NPC_Wardrobe", "Characters/Animations",
    "Vehicles",
    "Environment/Buildings", "Environment/Roads", "Environment/Props", "Environment/Vegetation",
    "Environment/Landmarks", "Environment/Terrain",
    "Materials/Global", "Materials/Master", "Materials/Shared", "Materials/Surfaces", "Materials/Kit", "Materials/Functions", "Materials/Instances", "Materials/Decals",
    "Textures/Default", "Textures/Surfaces",
    "FX", "Weather", "AI/StateTree", "AI/SmartObjects", "AI/ZoneGraph",
    "UI", "Audio", "Systems",
    "World/Maps", "World/DataLayers", "World/HLOD", "World/Districts",
    "Dev",
]

MAP_DEV = ROOT + "/World/Maps/L_VB_Dev"
MPC_WORLD = ROOT + "/Materials/Global/MPC_VB_World"
MASTER_SURFACE = ROOT + "/Materials/Master/M_VB_Surface"

SHARED_MATERIALS = ROOT + "/Materials/Shared"


def shared_material_path(name):
    """Gemeinsame, vom Setup erzeugte Material-Instanzen (z. B. Window, WindowShop)."""
    return "%s/MI_VB_%s" % (SHARED_MATERIALS, name)


GENERATED_TAG = "VB_Generated"
PROTOTYPE_TAG = "VB_Prototype"


def log(message):
    unreal.log("[VeyraBay] " + str(message))


def warn(message):
    unreal.log_warning("[VeyraBay] " + str(message))


def error(message):
    unreal.log_error("[VeyraBay] " + str(message))


def asset_tools():
    return unreal.AssetToolsHelpers.get_asset_tools()


def project_dir():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def generated_dir():
    path = os.path.join(project_dir(), "Saved", "VeyraBay", "Generated")
    os.makedirs(path, exist_ok=True)
    return path


def ensure_folders():
    for folder in FOLDERS:
        unreal.EditorAssetLibrary.make_directory(ROOT + "/" + folder)


def split_path(asset_path):
    folder, name = asset_path.rsplit("/", 1)
    return folder, name


def load_or_create(asset_path, asset_class, factory):
    """Laedt ein Asset oder legt es neu an. Gibt (asset, created) zurueck."""
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        return unreal.load_asset(asset_path), False
    folder, name = split_path(asset_path)
    unreal.EditorAssetLibrary.make_directory(folder)
    asset = asset_tools().create_asset(name, folder, asset_class, factory)
    return asset, True


def save_asset(asset):
    if asset is not None:
        unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False)


# Unbeaufsichtigter Lauf (vb_headless.py / Kommandozeile): keine Dialogfenster, nur Log
HEADLESS = os.environ.get("VB_HEADLESS") == "1"


def show_message(title, message):
    if HEADLESS:
        unreal.log("[VeyraBay] %s: %s" % (title, message))
        return
    unreal.EditorDialog.show_message(title, message, unreal.AppMsgType.OK)


def ask_yes_no(title, message):
    if HEADLESS:
        return True
    result = unreal.EditorDialog.show_message(title, message, unreal.AppMsgType.YES_NO)
    return result == unreal.AppReturnType.YES


# ---------------------------------------------------------------------------
# PNG-Erzeugung ohne externe Bibliotheken (fuer Standard- und Maskentexturen)
# ---------------------------------------------------------------------------
def write_png(path, width, height, pixels):
    """Schreibt ein RGBA-PNG. pixels: Liste von (r, g, b, a) Zeilenweise, Laenge width*height."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # Filter: None
        row = pixels[y * width:(y + 1) * width]
        for r, g, b, a in row:
            raw.extend((r, g, b, a))

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as handle:
        handle.write(png)


def solid_png(path, rgba, size=4):
    write_png(path, size, size, [tuple(rgba)] * (size * size))


def tileable_noise(size=256, octaves=5, base_cells=4, seed=1337):
    """Kachelbares fBm-Value-Noise (0..1) als Liste von floats (Zeilenweise)."""
    import random

    rng = random.Random(seed)
    result = [0.0] * (size * size)
    amplitude = 1.0
    total_amplitude = 0.0
    cells = base_cells
    for _ in range(octaves):
        lattice = [[rng.random() for _ in range(cells)] for _ in range(cells)]
        step = size / float(cells)
        for y in range(size):
            fy = y / step
            y0 = int(fy) % cells
            y1 = (y0 + 1) % cells
            ty = fy - int(fy)
            ty = ty * ty * (3 - 2 * ty)
            for x in range(size):
                fx = x / step
                x0 = int(fx) % cells
                x1 = (x0 + 1) % cells
                tx = fx - int(fx)
                tx = tx * tx * (3 - 2 * tx)
                top = lattice[y0][x0] + (lattice[y0][x1] - lattice[y0][x0]) * tx
                bottom = lattice[y1][x0] + (lattice[y1][x1] - lattice[y1][x0]) * tx
                result[y * size + x] += (top + (bottom - top) * ty) * amplitude
        total_amplitude += amplitude
        amplitude *= 0.5
        cells *= 2
    return [value / total_amplitude for value in result]


def import_texture(file_path, asset_path, srgb=True, compression=None, lod_group=None):
    folder, name = split_path(asset_path)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", file_path)
    task.set_editor_property("destination_path", folder)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    asset_tools().import_asset_tasks([task])

    texture = unreal.load_asset(asset_path)
    if texture is None:
        error("Textur-Import fehlgeschlagen: " + file_path)
        return None

    texture.set_editor_property("srgb", srgb)
    if compression is not None:
        texture.set_editor_property("compression_settings", compression)
    if lod_group is not None:
        texture.set_editor_property("lod_group", lod_group)
    save_asset(texture)
    return texture


def tag_actor(actor, label=None, folder=None, prototype=True):
    if label:
        actor.set_actor_label(label)
    if folder:
        actor.set_folder_path(folder)
    tags = list(actor.get_editor_property("tags"))
    tags.append(unreal.Name(GENERATED_TAG))
    if prototype:
        tags.append(unreal.Name(PROTOTYPE_TAG))
    actor.set_editor_property("tags", tags)
    try:
        actor.set_editor_property("is_spatially_loaded", False)
    except Exception:  # aeltere/neuere Engine-Versionen: Eigenschaft evtl. nicht editierbar
        pass
    return actor


# ---------------------------------------------------------------------------
# Material-Graph-Helfer (gemeinsam fuer alle Material-Skripte)
# ---------------------------------------------------------------------------
class MaterialGraph:
    """Kleiner Helfer, um Material-Graphen lesbar per Python aufzubauen."""

    def __init__(self, material):
        self.material = material
        self.failed_links = 0

    def node(self, expression_class, x, y, **props):
        expression = unreal.MaterialEditingLibrary.create_material_expression(self.material, expression_class, x, y)
        for key, value in props.items():
            expression.set_editor_property(key, value)
        return expression

    def scalar(self, name, default, x, y, group="Surface"):
        return self.node(unreal.MaterialExpressionScalarParameter, x, y,
                         parameter_name=name, default_value=default, group=group)

    def link(self, source, source_output, target, target_input):
        if not unreal.MaterialEditingLibrary.connect_material_expressions(source, source_output, target, target_input):
            self.failed_links += 1
            warn("Verbindung fehlgeschlagen: %s.%s -> %s.%s" % (
                source.get_class().get_name(), source_output, target.get_class().get_name(), target_input))

    def output(self, source, source_output, material_property):
        if not unreal.MaterialEditingLibrary.connect_material_property(source, source_output, material_property):
            self.failed_links += 1
            warn("Ausgang fehlgeschlagen: %s -> %s" % (source.get_class().get_name(), material_property))

    def link_any(self, source, source_output, target, target_inputs):
        """Verbindet mit dem ersten passenden Eingangsnamen (Namen unterscheiden sich zwischen Engine-Versionen)."""
        for name in target_inputs:
            if unreal.MaterialEditingLibrary.connect_material_expressions(source, source_output, target, name):
                return True
        self.failed_links += 1
        warn("Keine der Verbindungen %s an %s moeglich." % (target_inputs, target.get_class().get_name()))
        return False

    def texture(self, texture, uv_node, x, y, sampler=None, uv_output=""):
        node = self.node(unreal.MaterialExpressionTextureSample, x, y, texture=texture)
        if sampler is not None:
            node.set_editor_property("sampler_type", sampler)
        self.link(uv_node, uv_output, node, "UVs")
        return node

    def op(self, expression_class, a, b=None, x=0, y=0, a_out="", b_out="", **props):
        """Zwei-Eingangs-Operation (Add/Multiply/...); b kann ein Knoten oder eine Zahl sein (const_b)."""
        if b is not None and not hasattr(b, "get_class"):
            props["const_b"] = float(b)
        node = self.node(expression_class, x, y, **props)
        self.link(a, a_out, node, "A")
        if b is not None and hasattr(b, "get_class"):
            self.link(b, b_out, node, "B")
        return node

    def lerp(self, a, b, alpha, x=0, y=0, a_out="", b_out="", alpha_out=""):
        props = {}
        for key, value in (("const_a", a), ("const_b", b), ("const_alpha", alpha)):
            if value is not None and not hasattr(value, "get_class"):
                props[key] = float(value)
        node = self.node(unreal.MaterialExpressionLinearInterpolate, x, y, **props)
        for value, pin, out in ((a, "A", a_out), (b, "B", b_out), (alpha, "Alpha", alpha_out)):
            if hasattr(value, "get_class"):
                self.link(value, out, node, pin)
        return node

    def mask(self, source, channels, x=0, y=0, source_out=""):
        node = self.node(unreal.MaterialExpressionComponentMask, x, y, r="r" in channels, g="g" in channels,
                         b="b" in channels, a="a" in channels)
        self.link(source, source_out, node, "")
        return node

    def unary(self, expression_class, source, x=0, y=0, source_out=""):
        node = self.node(expression_class, x, y)
        self.link(source, source_out, node, "")
        return node

    def mpc(self, collection, name, x, y):
        expression = self.node(unreal.MaterialExpressionCollectionParameter, x, y)
        expression.set_editor_property("collection", collection)
        expression.set_editor_property("parameter_name", name)
        return expression
