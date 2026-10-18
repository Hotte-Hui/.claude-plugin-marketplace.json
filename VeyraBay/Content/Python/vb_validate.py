"""Asset-Validierung: Namenskonventionen, Ordner, Texturen, Meshes (Nanite/LOD/Kollision).

Menue: Veyra Bay -> 3. Assets validieren
Ergebnis: Output Log + CSV-Bericht unter <Projekt>/Saved/VeyraBay/Reports/
"""

import csv
import datetime
import os

import unreal

import vb_common as vb

# Klasse -> erlaubte Praefixe
PREFIXES = {
    "StaticMesh": ("SM_",),
    "SkeletalMesh": ("SK_", "SKM_"),
    "Skeleton": ("SKEL_", "SK_"),
    "PhysicsAsset": ("PHYS_", "PA_"),
    "Material": ("M_",),
    "MaterialInstanceConstant": ("MI_",),
    "MaterialFunction": ("MF_",),
    "MaterialParameterCollection": ("MPC_",),
    "Texture2D": ("T_",),
    "TextureCube": ("T_", "HDR_"),
    "Blueprint": ("BP_",),
    "WidgetBlueprint": ("WBP_",),
    "AnimBlueprint": ("ABP_",),
    "AnimSequence": ("A_", "AS_"),
    "AnimMontage": ("AM_",),
    "BlendSpace": ("BS_",),
    "NiagaraSystem": ("NS_",),
    "NiagaraEmitter": ("NE_",),
    "SoundWave": ("SW_", "S_"),
    "SoundCue": ("SC_",),
    "MetaSoundSource": ("MS_", "MSS_"),
    "World": ("L_",),
    "DataTable": ("DT_",),
    "PhysicalMaterial": ("PM_",),
    "CurveFloat": ("Curve_", "C_"),
    "InputAction": ("IA_",),
    "InputMappingContext": ("IMC_",),
    "StateTree": ("ST_",),
}

TEXTURE_SUFFIXES = ("_D", "_N", "_ORM", "_E", "_M", "_H", "_AO", "_R", "_MSK")
LINEAR_SUFFIXES = ("_N", "_ORM", "_M", "_H", "_AO", "_R", "_MSK")
TOP_LEVEL_FOLDERS = {f.split("/")[0] for f in vb.FOLDERS}

NANITE_TRIANGLE_THRESHOLD = 5000
LOD_TRIANGLE_THRESHOLD = 2000
MAX_TEXTURE_SIZE = 8192


def _class_name(asset_data):
    try:
        return str(asset_data.asset_class_path.asset_name)
    except AttributeError:
        return str(asset_data.asset_class)


def _is_power_of_two(value):
    return value > 0 and (value & (value - 1)) == 0


class Report:
    def __init__(self):
        self.rows = []

    def add(self, severity, asset_path, rule, message):
        self.rows.append((severity, asset_path, rule, message))
        text = "%s | %s | %s" % (asset_path, rule, message)
        if severity == "ERROR":
            vb.error(text)
        elif severity == "WARN":
            vb.warn(text)

    def count(self, severity):
        return sum(1 for row in self.rows if row[0] == severity)

    def write_csv(self):
        folder = os.path.join(vb.project_dir(), "Saved", "VeyraBay", "Reports")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "Validation_%s.csv" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(["Schwere", "Asset", "Regel", "Meldung"])
            writer.writerows(self.rows)
        return path


def check_name_and_folder(report, asset_data, class_name):
    name = str(asset_data.asset_name)
    package_path = str(asset_data.package_path)
    full = str(asset_data.package_name)

    if " " in name or not all(ch.isalnum() or ch == "_" for ch in name):
        report.add("ERROR", full, "Name", "Nur Buchstaben, Ziffern und _ erlaubt.")

    prefixes = PREFIXES.get(class_name)
    if prefixes and not name.startswith(prefixes):
        report.add("WARN", full, "Praefix", "%s sollte mit %s beginnen." % (class_name, " / ".join(prefixes)))

    relative = package_path[len(vb.ROOT):].strip("/")
    top = relative.split("/")[0] if relative else ""
    if top and top not in TOP_LEVEL_FOLDERS:
        report.add("WARN", full, "Ordner", "Unbekannter Hauptordner '%s' (siehe Docs/ARCHITECTURE.md)." % top)
    if not relative:
        report.add("WARN", full, "Ordner", "Asset liegt direkt in %s - bitte einsortieren." % vb.ROOT)


def check_texture(report, asset_data):
    full = str(asset_data.package_name)
    name = str(asset_data.asset_name)
    texture = unreal.load_asset(full)
    if texture is None:
        return

    if not name.endswith(TEXTURE_SUFFIXES):
        report.add("WARN", full, "Textur-Suffix", "Erwartet einen Suffix: %s" % ", ".join(TEXTURE_SUFFIXES))

    try:
        width = texture.blueprint_get_size_x()
        height = texture.blueprint_get_size_y()
        if not (_is_power_of_two(width) and _is_power_of_two(height)):
            report.add("WARN", full, "Textur-Groesse", "%dx%d ist keine Zweierpotenz (Mips/Streaming)." % (width, height))
        if max(width, height) > MAX_TEXTURE_SIZE:
            report.add("ERROR", full, "Textur-Groesse", "%dx%d ist groesser als %d." % (width, height, MAX_TEXTURE_SIZE))
    except Exception:  # noqa: BLE001
        pass

    srgb = texture.get_editor_property("srgb")
    compression = texture.get_editor_property("compression_settings")
    if name.endswith("_N"):
        if compression != unreal.TextureCompressionSettings.TC_NORMALMAP:
            report.add("ERROR", full, "Normal Map", "Kompression muss 'Normalmap' sein.")
        if srgb:
            report.add("ERROR", full, "Normal Map", "sRGB muss aus sein.")
    elif name.endswith(LINEAR_SUFFIXES) and srgb:
        report.add("ERROR", full, "Linear", "Masken/ORM-Texturen muessen sRGB=aus haben.")
    elif name.endswith("_D") and not srgb:
        report.add("WARN", full, "Farbe", "BaseColor-Texturen sollten sRGB=an haben.")


def check_static_mesh(report, asset_data):
    full = str(asset_data.package_name)
    mesh = unreal.load_asset(full)
    if mesh is None:
        return

    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)

    triangles = 0
    try:
        triangles = mesh.get_num_triangles(0)
    except Exception:  # noqa: BLE001
        try:
            triangles = subsystem.get_number_verts(mesh, 0) // 2
        except Exception:  # noqa: BLE001
            triangles = 0

    nanite_enabled = False
    try:
        nanite_enabled = mesh.get_editor_property("nanite_settings").get_editor_property("enabled")
    except Exception:  # noqa: BLE001
        pass

    is_environment = "/Environment/" in full or "/Vehicles/" in full
    if is_environment and triangles > NANITE_TRIANGLE_THRESHOLD and not nanite_enabled:
        report.add("WARN", full, "Nanite", "%d Dreiecke ohne Nanite - aktivieren." % triangles)

    if not nanite_enabled and triangles > LOD_TRIANGLE_THRESHOLD:
        try:
            lods = subsystem.get_lod_count(mesh)
            if lods < 2:
                report.add("WARN", full, "LOD", "%d Dreiecke, kein Nanite und nur %d LOD." % (triangles, lods))
        except Exception:  # noqa: BLE001
            pass

    if is_environment:
        simple = 0
        try:
            simple = subsystem.get_simple_collision_count(mesh)
        except Exception:  # noqa: BLE001
            pass
        complex_as_simple = False
        try:
            body = mesh.get_editor_property("body_setup")
            complex_as_simple = body.get_editor_property("collision_trace_flag") == unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
        except Exception:  # noqa: BLE001
            pass
        if simple == 0 and not complex_as_simple:
            report.add("WARN", full, "Kollision", "Keine Kollision (UCX_ in Blender anlegen oder Import-Tool nutzen).")

    try:
        for index, slot in enumerate(mesh.get_editor_property("static_materials")):
            material = slot.get_editor_property("material_interface")
            if material is None:
                report.add("ERROR", full, "Material", "Slot %d hat kein Material." % index)
            elif material.get_path_name().startswith("/Engine/"):
                report.add("WARN", full, "Material", "Slot %d nutzt ein Engine-Standardmaterial." % index)
    except Exception:  # noqa: BLE001
        pass


def run(show_dialog=True):
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = registry.get_assets_by_path(vb.ROOT, recursive=True)
    report = Report()

    with unreal.ScopedSlowTask(len(assets), "Veyra Bay: Assets werden geprueft ...") as task:
        task.make_dialog(True)
        for asset_data in assets:
            if task.should_cancel():
                break
            task.enter_progress_frame(1)
            class_name = _class_name(asset_data)
            check_name_and_folder(report, asset_data, class_name)
            if class_name == "Texture2D":
                check_texture(report, asset_data)
            elif class_name == "StaticMesh":
                check_static_mesh(report, asset_data)

    csv_path = report.write_csv()
    summary = "%d Assets geprueft\n%d Fehler\n%d Warnungen\n\nBericht: %s" % (
        len(assets), report.count("ERROR"), report.count("WARN"), csv_path)
    vb.log(summary.replace("\n", " | "))
    if show_dialog:
        vb.show_message("Veyra Bay - Validierung", summary)
    return report
