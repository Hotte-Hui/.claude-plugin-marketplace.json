"""Veyra Bay - Blender -> Unreal Export-Pipeline.

Als Add-on: Blender -> Bearbeiten -> Einstellungen -> Add-ons -> Installieren -> diese Datei.
            Danach: 3D-Ansicht -> Seitenleiste (N) -> Reiter "Veyra Bay".
Kommandozeile:
    blender -b datei.blend --python vb_blender_export.py -- --out <Projekt>/SourceAssets/Export

Konventionen (werden geprueft):
  * Jedes Asset ist ein Mesh-Objekt auf oberster Ebene mit Namen  SM_<Name>
  * Kollision: Kind-Objekte  UCX_SM_<Name>_00, _01 ... (konvexe Huellen)
  * Szene in Metern (Unit Scale 1.0) - 1 Blender-Einheit = 1 m = 100 Unreal-cm
  * Pivot (Objekt-Ursprung) unten mittig, am Scharnier bzw. bei Kit-Teilen am Anfang (X=0);
    Skalierung/Rotation angewendet
  * Vorderseite / Ausleger zeigen nach +X (bleibt in Unreal +X)
  * Mindestens eine UV-Map, alle Materialslots belegt
  * Optionale Custom Properties am Objekt (landen in <Name>.json):
      vb_category (Buildings|Roads|Props|Vegetation|Landmarks|Terrain|Vehicles)
      vb_nanite, vb_collision (auto|box|complex|none), vb_porosity, vb_wetness_response,
      vb_puddle_response, vb_uv_tiling
  * Optionale Custom Properties am Material (pro Slot): vb_surface (gebackene Oberflaeche), vb_base_color (Liste), vb_roughness,
      vb_metallic, vb_emissive_color, vb_emissive_intensity, vb_use_night_switch
"""

import json
import math
import os
import sys

import bpy
import mathutils

bl_info = {
    "name": "Veyra Bay Export",
    "author": "Veyra Bay",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "3D View > Sidebar > Veyra Bay",
    "description": "Validiert und exportiert Assets nach Unreal (FBX + Metadaten).",
    "category": "Import-Export",
}

CATEGORIES = ("Buildings", "Roads", "Props", "Vegetation", "Landmarks", "Terrain", "Vehicles")
OBJECT_KEYS = {
    "vb_nanite": "nanite",
    "vb_collision": "collision",
    "vb_porosity": "porosity",
    "vb_wetness_response": "wetness_response",
    "vb_puddle_response": "puddle_response",
    "vb_uv_tiling": "uv_tiling",
}
MATERIAL_KEYS = {
    "vb_surface": "surface",
    "vb_shared_material": "shared_material",
    "vb_base_color": "base_color",
    "vb_roughness": "roughness",
    "vb_metallic": "metallic",
    "vb_emissive_color": "emissive_color",
    "vb_emissive_intensity": "emissive_intensity",
    "vb_use_night_switch": "use_night_switch",
    "vb_porosity": "porosity",
    "vb_wetness_response": "wetness_response",
    "vb_puddle_response": "puddle_response",
}


# ---------------------------------------------------------------------------
# Validierung
# ---------------------------------------------------------------------------
def find_assets(scene):
    return [obj for obj in scene.objects if obj.type == "MESH" and obj.parent is None and obj.name.startswith("SM_")]


def collision_children(asset):
    prefix = "UCX_" + asset.name
    return [child for child in asset.children if child.type == "MESH" and child.name.startswith(prefix)]


def _plain(value):
    """Blender-IDProperty (Array/Gruppe) in JSON-faehige Python-Werte umwandeln."""
    if hasattr(value, "to_list"):
        return value.to_list()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def validate_asset(asset, scene):
    """Gibt (fehler, warnungen) als Listen von Texten zurueck."""
    errors, warnings = [], []

    unit = scene.unit_settings
    if unit.system != "METRIC" or abs(unit.scale_length - 1.0) > 1e-6:
        errors.append("Szene muss metrisch mit Unit Scale 1.0 sein.")

    if any(abs(s - 1.0) > 1e-4 for s in asset.scale):
        errors.append("Skalierung nicht angewendet (Strg+A -> Skalierung).")
    if any(abs(r) > 1e-4 for r in asset.rotation_euler):
        warnings.append("Rotation nicht angewendet (Strg+A -> Rotation).")

    mesh = asset.data
    if not mesh.uv_layers:
        errors.append("Keine UV-Map.")
    if not asset.material_slots or any(slot.material is None for slot in asset.material_slots):
        errors.append("Leere Materialslots.")

    # Pivot: Objekt darf nicht ueber dem Ursprung schweben (Unterbau unter der Oberflaeche ist erlaubt)
    min_z = min((v.co.z for v in mesh.vertices), default=0.0)
    if min_z > 0.01:
        warnings.append("Objekt schwebt %.3f m ueber dem Pivot - Pivot an die Unterkante setzen." % min_z)

    category = asset.get("vb_category", "Props")
    if category not in CATEGORIES:
        errors.append("vb_category '%s' unbekannt (%s)." % (category, ", ".join(CATEGORIES)))

    for child in asset.children:
        if child.type == "MESH" and not child.name.startswith("UCX_" + asset.name):
            warnings.append("Kind-Objekt '%s' ist keine Kollision und wird nicht exportiert." % child.name)

    return errors, warnings


def triangle_count(asset):
    return sum(len(poly.vertices) - 2 for poly in asset.data.polygons)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def build_metadata(asset):
    meta = {"category": asset.get("vb_category", "Props"), "triangles": triangle_count(asset)}
    for key, target in OBJECT_KEYS.items():
        if key in asset:
            meta[target] = _plain(asset[key])
    meta.setdefault("nanite", meta["triangles"] > 500)
    if collision_children(asset):
        meta.setdefault("collision", "auto")

    slots = {}
    for slot in asset.material_slots:
        material = slot.material
        if material is None:
            continue
        params = {target: _plain(material[key]) for key, target in MATERIAL_KEYS.items() if key in material}
        if params:
            slots[material.name] = params
    if slots:
        meta["slots"] = slots
    return meta


def export_asset(asset, out_root, context):
    category = asset.get("vb_category", "Props")
    target_dir = os.path.join(out_root, category, asset.name)
    os.makedirs(target_dir, exist_ok=True)
    fbx_path = os.path.join(target_dir, asset.name + ".fbx")

    colliders = collision_children(asset)
    original_matrix = asset.matrix_world.copy()

    # Asset temporaer in den Ursprung setzen, damit der Pivot in Unreal stimmt
    asset.matrix_world = mathutils.Matrix.Identity(4)
    context.view_layer.update()

    for obj in context.view_layer.objects:
        obj.select_set(False)
    asset.select_set(True)
    for collider in colliders:
        collider.hide_set(False)
        collider.select_set(True)
    context.view_layer.objects.active = asset

    try:
        bpy.ops.export_scene.fbx(
            filepath=fbx_path,
            use_selection=True,
            object_types={"MESH"},
            apply_unit_scale=True,
            apply_scale_options="FBX_SCALE_UNITS",
            axis_forward="-Z",
            axis_up="Y",
            use_mesh_modifiers=True,
            mesh_smooth_type="FACE",
            use_tspace=True,
            use_triangles=True,  # Tangenten auch fuer N-Gons korrekt berechnen
            add_leaf_bones=False,
            bake_anim=False,
            path_mode="STRIP",
            embed_textures=False,
        )
    finally:
        asset.matrix_world = original_matrix
        context.view_layer.update()

    meta = build_metadata(asset)
    with open(os.path.join(target_dir, asset.name + ".json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2)

    return fbx_path, meta


def export_all(context, out_root, only_selected=False):
    scene = context.scene
    assets = find_assets(scene)
    if only_selected:
        assets = [a for a in assets if a.select_get()]

    report = []
    exported = 0
    for asset in assets:
        errors, warnings = validate_asset(asset, scene)
        for text in warnings:
            report.append("WARNUNG %s: %s" % (asset.name, text))
        if errors:
            for text in errors:
                report.append("FEHLER  %s: %s" % (asset.name, text))
            continue
        fbx_path, meta = export_asset(asset, out_root, context)
        exported += 1
        report.append("OK      %s -> %s (%d Dreiecke, Nanite=%s)" % (asset.name, fbx_path, meta["triangles"], meta["nanite"]))
    return exported, report


# ---------------------------------------------------------------------------
# Add-on UI
# ---------------------------------------------------------------------------
class VB_OT_export(bpy.types.Operator):
    bl_idname = "veyrabay.export"
    bl_label = "Nach Unreal exportieren"
    bl_description = "Alle SM_-Assets validieren und nach SourceAssets/Export schreiben"

    only_selected: bpy.props.BoolProperty(name="Nur Auswahl", default=False)

    def execute(self, context):
        out_root = bpy.path.abspath(context.scene.vb_export_root)
        if not out_root:
            self.report({"ERROR"}, "Exportordner setzen (Projekt/SourceAssets/Export).")
            return {"CANCELLED"}
        exported, report = export_all(context, out_root, self.only_selected)
        for line in report:
            print(line)
        level = {"WARNING"} if any(line.startswith("FEHLER") for line in report) else {"INFO"}
        self.report(level, "%d Asset(s) exportiert - Details in der Systemkonsole." % exported)
        return {"FINISHED"}


class VB_OT_validate(bpy.types.Operator):
    bl_idname = "veyrabay.validate"
    bl_label = "Pruefen"

    def execute(self, context):
        problems = 0
        for asset in find_assets(context.scene):
            errors, warnings = validate_asset(asset, context.scene)
            for text in errors + warnings:
                print("%s: %s" % (asset.name, text))
            problems += len(errors)
        self.report({"WARNING"} if problems else {"INFO"}, "%d Fehler (Details in der Systemkonsole)." % problems)
        return {"FINISHED"}


class VB_PT_panel(bpy.types.Panel):
    bl_label = "Veyra Bay"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Veyra Bay"

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "vb_export_root", text="Export")
        obj = context.active_object
        if obj is not None and obj.name.startswith("SM_"):
            box = layout.box()
            box.label(text="%s  (%d Dreiecke)" % (obj.name, triangle_count(obj)))
            box.label(text="Kategorie: %s" % obj.get("vb_category", "Props"))
        layout.operator("veyrabay.validate", icon="CHECKMARK")
        layout.operator("veyrabay.export", icon="EXPORT").only_selected = False
        layout.operator("veyrabay.export", text="Nur Auswahl exportieren").only_selected = True


CLASSES = (VB_OT_export, VB_OT_validate, VB_PT_panel)


def register():
    bpy.types.Scene.vb_export_root = bpy.props.StringProperty(name="Exportordner", subtype="DIR_PATH", default="")
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.vb_export_root


# ---------------------------------------------------------------------------
# Kommandozeile
# ---------------------------------------------------------------------------
def _cli():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out_root = None
    for index, arg in enumerate(argv):
        if arg == "--out" and index + 1 < len(argv):
            out_root = argv[index + 1]
    if not out_root:
        print("Aufruf: blender -b datei.blend --python vb_blender_export.py -- --out <SourceAssets/Export>")
        return 2
    exported, report = export_all(bpy.context, os.path.abspath(out_root))
    for line in report:
        print(line)
    print("Veyra Bay: %d Asset(s) exportiert." % exported)
    return 0 if not any(line.startswith("FEHLER") for line in report) else 1


if __name__ == "__main__":
    if bpy.app.background:
        sys.exit(_cli())
    else:
        register()
