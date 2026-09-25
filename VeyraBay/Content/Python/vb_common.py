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
    "Materials/Global", "Materials/Master", "Materials/Functions", "Materials/Instances", "Materials/Decals",
    "Textures/Default", "Textures/Surfaces",
    "FX", "Weather", "AI/StateTree", "AI/SmartObjects", "AI/ZoneGraph",
    "UI", "Audio", "Systems",
    "World/Maps", "World/DataLayers", "World/HLOD", "World/Districts",
    "Dev",
]

MAP_DEV = ROOT + "/World/Maps/L_VB_Dev"
MPC_WORLD = ROOT + "/Materials/Global/MPC_VB_World"
MASTER_SURFACE = ROOT + "/Materials/Master/M_VB_Surface"

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


def show_message(title, message):
    unreal.EditorDialog.show_message(title, message, unreal.AppMsgType.OK)


def ask_yes_no(title, message):
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
