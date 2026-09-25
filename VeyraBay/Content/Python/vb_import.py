"""Automatischer Import der Blender-Exporte nach Unreal.

Menue: Veyra Bay -> 2. Assets importieren (Blender-Export)

Erwartete Struktur (erzeugt vom Blender-Tool Tools/Blender/vb_blender_export.py):

    <Projekt>/SourceAssets/Export/<Kategorie>/<SM_Name>/
        SM_Name.fbx          Mesh (+ UCX_SM_Name_## Kollision)
        SM_Name.json         Metadaten (Nanite, Kollision, Materialparameter)
        T_Name_D.png         BaseColor   (optional, auch pro Slot: T_Name_<Slot>_D.png)
        T_Name_N.png         Normal      (OpenGL/Blender-Format, wird fuer Unreal gespiegelt)
        T_Name_ORM.png       AO / Roughness / Metallic

Gebackene Oberflaechen: SourceAssets/Export/Surfaces/<Name>/T_VB_<Name>_D/_N/_ORM.png + surface.json
-> MI_VB_Surface_<Name>. Materialslots mit "surface" in den Metadaten verwenden diese gemeinsame Instanz.

Pro Asset: FBX-Import -> Texturen (korrekte Kompression/sRGB) -> Material-Instanz von
M_VB_Surface -> Slot-Zuweisung -> Nanite -> Kollision -> LODs (falls kein Nanite) -> Speichern.
"""

import json
import os

import unreal

import vb_common as vb

CATEGORY_TARGETS = {
    "Buildings": vb.ROOT + "/Environment/Buildings",
    "Roads": vb.ROOT + "/Environment/Roads",
    "Props": vb.ROOT + "/Environment/Props",
    "Vegetation": vb.ROOT + "/Environment/Vegetation",
    "Landmarks": vb.ROOT + "/Environment/Landmarks",
    "Terrain": vb.ROOT + "/Environment/Terrain",
    "Vehicles": vb.ROOT + "/Vehicles",
}

DEFAULT_META = {
    "nanite": True,
    "collision": "auto",       # auto | box | complex | none
    "porosity": 0.5,
    "wetness_response": 1.0,
    "puddle_response": 0.0,
    "uv_tiling": 1.0,
    "roughness": 0.7,          # nur ohne ORM-Textur
    "metallic": 0.0,           # nur ohne ORM-Textur
    "base_color": [0.5, 0.5, 0.5],
    "lods": [1.0, 0.5, 0.25, 0.12],
    "slots": {},               # optionale Parameter pro Materialslot
}


def source_root():
    return os.path.join(vb.project_dir(), "SourceAssets", "Export")


def find_exports():
    root = source_root()
    exports = []
    if not os.path.isdir(root):
        return exports
    for category in sorted(os.listdir(root)):
        category_dir = os.path.join(root, category)
        if not os.path.isdir(category_dir) or category not in CATEGORY_TARGETS:
            continue
        for asset_name in sorted(os.listdir(category_dir)):
            asset_dir = os.path.join(category_dir, asset_name)
            fbx = os.path.join(asset_dir, asset_name + ".fbx")
            if os.path.isfile(fbx):
                exports.append((category, asset_name, asset_dir, fbx))
    return exports


def load_meta(asset_dir, asset_name):
    meta = dict(DEFAULT_META)
    path = os.path.join(asset_dir, asset_name + ".json")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as handle:
            meta.update(json.load(handle))
    return meta


def import_mesh(fbx_path, target_folder, asset_name, meta):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", fbx_path)
    task.set_editor_property("destination_path", target_folder)
    task.set_editor_property("destination_name", asset_name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)

    # Optionen fuer den klassischen FBX-Importer (Interchange ignoriert sie; Nachbearbeitung unten greift immer)
    try:
        options = unreal.FbxImportUI()
        options.set_editor_property("import_as_skeletal", False)
        options.set_editor_property("import_materials", False)
        options.set_editor_property("import_textures", False)
        options.set_editor_property("import_animations", False)
        mesh_data = options.get_editor_property("static_mesh_import_data")
        mesh_data.set_editor_property("combine_meshes", True)
        mesh_data.set_editor_property("generate_lightmap_u_vs", False)
        mesh_data.set_editor_property("auto_generate_collision", False)
        try:
            mesh_data.set_editor_property("build_nanite", bool(meta.get("nanite", True)))
        except Exception:  # noqa: BLE001
            pass
        task.set_editor_property("options", options)
    except Exception:  # noqa: BLE001
        pass

    vb.asset_tools().import_asset_tasks([task])
    mesh = unreal.load_asset(target_folder + "/" + asset_name)
    if mesh is None or not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("FBX-Import fehlgeschlagen: " + fbx_path)
    return mesh


def texture_base_name(asset_name):
    return asset_name[3:] if asset_name.startswith("SM_") else asset_name


SURFACE_TEXTURES = vb.ROOT + "/Textures/Surfaces"
SURFACE_MATERIALS = vb.ROOT + "/Materials/Surfaces"


def import_textures(asset_dir, target_folder, base, slot=None, stem=None):
    """Sucht <stem>_D/N/ORM.png (Standard: T_<Base>[_<Slot>]) und importiert sie mit korrekten Einstellungen."""
    if stem is None:
        stem = "T_%s_%s" % (base, slot) if slot else "T_%s" % base
    tcs = unreal.TextureCompressionSettings
    result = {}
    for suffix, srgb, compression in (("_D", True, None), ("_N", False, tcs.TC_NORMALMAP), ("_ORM", False, tcs.TC_MASKS)):
        for ext in (".png", ".tga", ".exr"):
            file_path = os.path.join(asset_dir, stem + suffix + ext)
            if os.path.isfile(file_path):
                texture = vb.import_texture(file_path, target_folder + "/" + stem + suffix, srgb=srgb, compression=compression)
                if texture is not None and suffix == "_N":
                    # Blender backt OpenGL-Normalen (Y+), Unreal erwartet DirectX (Y-)
                    texture.set_editor_property("flip_green_channel", True)
                    vb.save_asset(texture)
                result[suffix] = texture
                break
    return result


def create_material_instance(target_folder, name, textures, params):
    mel = unreal.MaterialEditingLibrary
    master = unreal.load_asset(vb.MASTER_SURFACE)
    if master is None:
        raise RuntimeError("M_VB_Surface fehlt - zuerst 'Projekt einrichten' ausfuehren.")

    mi, _ = vb.load_or_create(target_folder + "/" + name, unreal.MaterialInstanceConstant,
                              unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, master)

    if "_D" in textures:
        mel.set_material_instance_texture_parameter_value(mi, "BaseColorMap", textures["_D"])
        mel.set_material_instance_vector_parameter_value(mi, "BaseColorTint", unreal.LinearColor(1, 1, 1, 1))
    else:
        color = params.get("base_color", [0.5, 0.5, 0.5])
        mel.set_material_instance_vector_parameter_value(mi, "BaseColorTint", unreal.LinearColor(color[0], color[1], color[2], 1))
    if "_N" in textures:
        mel.set_material_instance_texture_parameter_value(mi, "NormalMap", textures["_N"])
    if "_ORM" in textures:
        mel.set_material_instance_texture_parameter_value(mi, "ORMMap", textures["_ORM"])
        mel.set_material_instance_scalar_parameter_value(mi, "Roughness", 1.0)
        mel.set_material_instance_scalar_parameter_value(mi, "Metallic", 1.0)
    else:
        mel.set_material_instance_scalar_parameter_value(mi, "Roughness", float(params.get("roughness", 0.7)))
        mel.set_material_instance_scalar_parameter_value(mi, "Metallic", float(params.get("metallic", 0.0)))

    mel.set_material_instance_scalar_parameter_value(mi, "UVTiling", float(params.get("uv_tiling", 1.0)))
    mel.set_material_instance_scalar_parameter_value(mi, "Porosity", float(params.get("porosity", 0.5)))
    mel.set_material_instance_scalar_parameter_value(mi, "WetnessResponse", float(params.get("wetness_response", 1.0)))
    mel.set_material_instance_scalar_parameter_value(mi, "PuddleResponse", float(params.get("puddle_response", 0.0)))
    if "emissive_intensity" in params:
        color = params.get("emissive_color", [1.0, 0.85, 0.6])
        mel.set_material_instance_vector_parameter_value(mi, "EmissiveColor", unreal.LinearColor(color[0], color[1], color[2], 1))
        mel.set_material_instance_scalar_parameter_value(mi, "EmissiveIntensity", float(params["emissive_intensity"]))
        mel.set_material_instance_scalar_parameter_value(mi, "UseNightSwitch", 1.0 if params.get("use_night_switch") else 0.0)
    mel.update_material_instance(mi)
    vb.save_asset(mi)
    return mi


def setup_collision(mesh, mode):
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    existing = subsystem.get_simple_collision_count(mesh)
    if mode == "none":
        return "keine"
    if mode == "complex":
        body = mesh.get_editor_property("body_setup")
        body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        return "komplex"
    if existing > 0:
        return "UCX (%d)" % existing
    subsystem.add_simple_collisions(mesh, unreal.ScriptCollisionShapeType.BOX)
    return "Box (automatisch)"


def setup_nanite_and_lods(mesh, meta):
    use_nanite = bool(meta.get("nanite", True))
    settings = mesh.get_editor_property("nanite_settings")
    if settings.get_editor_property("enabled") != use_nanite:
        settings.set_editor_property("enabled", use_nanite)
        mesh.set_editor_property("nanite_settings", settings)
    if use_nanite:
        return "Nanite"

    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    options_class = getattr(unreal, "StaticMeshReductionOptions", None) or getattr(unreal, "EditorScriptingMeshReductionOptions")
    settings_class = getattr(unreal, "StaticMeshReductionSettings", None) or getattr(unreal, "EditorScriptingMeshReductionSettings")
    options = options_class()
    options.set_editor_property("auto_compute_lod_screen_size", True)
    options.set_editor_property("reduction_settings", [settings_class(percent_triangles=p, screen_size=0.0) for p in meta["lods"]])
    count = subsystem.set_lods(mesh, options)
    return "%d LODs" % count


def delete_unused_imported_materials(target_folder, keep):
    for path in unreal.EditorAssetLibrary.list_assets(target_folder, recursive=False, include_folder=False):
        package = path.split(".")[0]
        if package in keep:
            continue
        asset = unreal.load_asset(package)
        if isinstance(asset, (unreal.Material, unreal.MaterialInstanceConstant)) and not asset.get_name().startswith("MI_"):
            if not unreal.EditorAssetLibrary.find_package_referencers_for_asset(package, False):
                unreal.EditorAssetLibrary.delete_asset(package)


def surface_material_path(name):
    return "%s/MI_VB_Surface_%s" % (SURFACE_MATERIALS, name)


def import_surfaces(textures_only=False):
    """Importiert gebackene Oberflaechen (SourceAssets/Export/Surfaces/<Name>) und erzeugt MI_VB_Surface_<Name>."""
    root = os.path.join(source_root(), "Surfaces")
    results = []
    if not os.path.isdir(root):
        return results
    for name in sorted(os.listdir(root)):
        folder = os.path.join(root, name)
        meta_path = os.path.join(folder, "surface.json")
        if not os.path.isfile(meta_path):
            continue
        with open(meta_path, "r", encoding="utf-8") as handle:
            meta = json.load(handle)
        target = "%s/%s" % (SURFACE_TEXTURES, name)
        unreal.EditorAssetLibrary.make_directory(target)
        textures = import_textures(folder, target, name, stem="T_VB_%s" % name)
        if textures_only or meta.get("texture_only"):
            results.append("Oberflaeche %s: %d Textur(en)" % (name, len(textures)))
            continue
        folder_asset, mi_name = vb.split_path(surface_material_path(name))
        create_material_instance(folder_asset, mi_name, textures, meta)
        results.append("Oberflaeche %s: MI_VB_Surface_%s" % (name, name))
    return results


def import_one(category, asset_name, asset_dir, fbx):
    meta = load_meta(asset_dir, asset_name)
    target = CATEGORY_TARGETS[category] + "/" + asset_name
    unreal.EditorAssetLibrary.make_directory(target)

    mesh = import_mesh(fbx, target, asset_name, meta)
    base = texture_base_name(asset_name)
    shared_textures = import_textures(asset_dir, target, base)

    keep = {target + "/" + asset_name}
    slots = mesh.get_editor_property("static_materials")
    for index, slot in enumerate(slots):
        slot_name = str(slot.get_editor_property("material_slot_name"))
        slot_meta = meta.get("slots", {}).get(slot_name, {})
        surface = slot_meta.get("surface")
        if surface:
            surface_mi = unreal.load_asset(surface_material_path(surface))
            if surface_mi is not None:
                mesh.set_material(index, surface_mi)
                continue
            vb.warn("%s: Oberflaeche '%s' fehlt - Slot bekommt eigenes Material." % (asset_name, surface))
        slot_textures = import_textures(asset_dir, target, base, slot_name) if len(slots) > 1 else {}
        textures = slot_textures or shared_textures
        params = dict(meta)
        params.update(meta.get("slots", {}).get(slot_name, {}))
        mi_name = "MI_%s_%s" % (base, slot_name) if len(slots) > 1 else "MI_%s" % base
        mi = create_material_instance(target, mi_name, textures, params)
        mesh.set_material(index, mi)
        keep.add(target + "/" + mi_name)
        for texture in textures.values():
            if texture is not None:
                keep.add(texture.get_path_name().split(".")[0])

    collision = setup_collision(mesh, meta.get("collision", "auto"))
    geometry = setup_nanite_and_lods(mesh, meta)
    vb.save_asset(mesh)
    delete_unused_imported_materials(target, keep)
    return "%s/%s: %d Slot(s), %s, Kollision %s" % (category, asset_name, len(slots), geometry, collision)


def run(show_dialog=True):
    exports = find_exports()
    has_surfaces = os.path.isdir(os.path.join(source_root(), "Surfaces"))
    if not exports and not has_surfaces:
        if show_dialog:
            vb.show_message("Veyra Bay - Import",
                            "Keine Exporte gefunden in:\n%s\n\nIn Blender das Veyra-Bay-Export-Tool nutzen." % source_root())
        return []

    results, failures = [], []
    try:
        results.extend(import_surfaces())
    except Exception as exc:  # noqa: BLE001
        failures.append("Oberflaechen: %s" % exc)
        vb.error(failures[-1])
    with unreal.ScopedSlowTask(len(exports), "Veyra Bay: Assets werden importiert ...") as task:
        task.make_dialog(True)
        for category, asset_name, asset_dir, fbx in exports:
            if task.should_cancel():
                break
            task.enter_progress_frame(1, asset_name)
            try:
                results.append(import_one(category, asset_name, asset_dir, fbx))
                vb.log(results[-1])
            except Exception as exc:  # noqa: BLE001
                failures.append("%s: %s" % (asset_name, exc))
                vb.error(failures[-1])

    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(False, True)
    message = "%d importiert, %d Fehler.\n\n%s" % (len(results), len(failures), "\n".join(results + failures)[:3000])
    if show_dialog:
        vb.show_message("Veyra Bay - Import", message)
    return results
