"""Phase-1-Setup: richtet das Projekt vollautomatisch ein.

Menue: Veyra Bay -> 1. Projekt einrichten

Schritte (idempotent - kann jederzeit erneut ausgefuehrt werden):
  1. Ordnerstruktur anlegen
  2. Standard-Texturen + Pfuetzenmaske erzeugen
  3. Globale Material Parameter Collection (MPC_VB_World)
  4. Master-Material M_VB_Surface (PBR + Naesse + Pfuetzen) und Material-Instanzen
  5. Spielfigur (Mannequin) automatisch finden und eintragen
  6. Entwicklungskarte L_VB_Dev (World Partition) mit Himmel, Testsstrasse, Laternen, Kalibrierung
"""

import math
import os
import random

import unreal

import vb_common as vb
import vb_import
import vb_district
import vb_vehicles
import vb_materials_nature

MEL = unreal.MaterialEditingLibrary

TEX_DEFAULT_D = vb.ROOT + "/Textures/Default/T_VB_Default_D"
TEX_DEFAULT_N = vb.ROOT + "/Textures/Default/T_VB_Default_N"
TEX_DEFAULT_ORM = vb.ROOT + "/Textures/Default/T_VB_Default_ORM"
TEX_PUDDLE_MASK = vb.ROOT + "/Textures/Default/T_VB_PuddleMask_M"
TEX_RAIN_RIPPLES = vb.ROOT + "/Textures/Surfaces/RainRipples/T_VB_RainRipples_N"
STREETLIGHT_MODEL = vb.ROOT + "/Environment/Props/SM_VB_StreetLight_A/SM_VB_StreetLight_A"

# Skalare Parameter der globalen MPC (muessen mit VBWorldParams.cpp uebereinstimmen)
MPC_SCALARS = [
    ("TimeOfDay01", 0.4),
    ("NightFactor", 0.0),
    ("SunElevation", 0.5),
    ("Wetness", 0.0),
    ("Puddles", 0.0),
    ("RainIntensity", 0.0),
    ("WindStrength", 0.2),
    ("CloudCoverage", 0.15),
    ("FogAmount", 0.0),
    ("LightningFlash", 0.0),
]
MPC_VECTORS = [
    ("WindDirection", unreal.LinearColor(0.7, 0.7, 0.0, 0.2)),
]

# Material-Instanzen: Name -> (Farbe linear, Rauheit, Metallic, Porositaet, Nass-Reaktion, Pfuetzen-Reaktion)
# Albedo-Werte orientieren sich an gemessenen PBR-Referenzen (Asphalt ~0.04-0.08, Beton ~0.25-0.4).
MATERIAL_INSTANCES = {
    "MI_VB_Dev_Asphalt":      ((0.050, 0.050, 0.052), 0.82, 0.0, 0.85, 1.0, 1.0),
    "MI_VB_Dev_Sidewalk":     ((0.280, 0.270, 0.255), 0.88, 0.0, 0.60, 1.0, 1.0),
    "MI_VB_Dev_Ground":       ((0.180, 0.170, 0.150), 0.92, 0.0, 0.70, 1.0, 1.0),
    "MI_VB_Dev_Concrete":     ((0.330, 0.320, 0.300), 0.90, 0.0, 0.55, 1.0, 0.0),
    "MI_VB_Dev_PlasterWarm":  ((0.520, 0.420, 0.320), 0.85, 0.0, 0.50, 1.0, 0.0),
    "MI_VB_Dev_PlasterLight": ((0.620, 0.600, 0.560), 0.85, 0.0, 0.50, 1.0, 0.0),
    "MI_VB_Dev_Brick":        ((0.300, 0.140, 0.095), 0.88, 0.0, 0.65, 1.0, 0.0),
    "MI_VB_Dev_DarkFacade":   ((0.060, 0.065, 0.075), 0.35, 0.6, 0.05, 1.0, 0.0),
    "MI_VB_Dev_Metal":        ((0.560, 0.570, 0.580), 0.35, 1.0, 0.00, 1.0, 0.0),
    "MI_VB_Calib_Grey18":     ((0.180, 0.180, 0.180), 0.50, 0.0, 0.00, 0.0, 0.0),
    "MI_VB_Calib_White80":    ((0.800, 0.800, 0.800), 0.50, 0.0, 0.00, 0.0, 0.0),
    "MI_VB_Calib_Black04":    ((0.040, 0.040, 0.040), 0.50, 0.0, 0.00, 0.0, 0.0),
    "MI_VB_Calib_Chrome":     ((0.950, 0.950, 0.950), 0.03, 1.0, 0.00, 0.0, 0.0),
}


# ---------------------------------------------------------------------------
# 2. Texturen
# ---------------------------------------------------------------------------
def create_default_textures():
    out = vb.generated_dir()
    files = {
        "d": os.path.join(out, "T_VB_Default_D.png"),
        "n": os.path.join(out, "T_VB_Default_N.png"),
        "orm": os.path.join(out, "T_VB_Default_ORM.png"),
        "puddle": os.path.join(out, "T_VB_PuddleMask_M.png"),
    }
    vb.solid_png(files["d"], (255, 255, 255, 255))
    vb.solid_png(files["n"], (128, 128, 255, 255))
    vb.solid_png(files["orm"], (255, 255, 0, 255))  # AO=1, Rauheit=1 (wird skaliert), Metallic=0

    if not unreal.EditorAssetLibrary.does_asset_exist(TEX_PUDDLE_MASK):
        size = 256
        noise = vb.tileable_noise(size=size, octaves=5, base_cells=4, seed=2024)
        pixels = []
        for value in noise:
            # Kontrast erhoehen: Pfuetzen sammeln sich in Senken
            v = max(0.0, min(1.0, (value - 0.5) * 2.2 + 0.5))
            byte = int(v * 255)
            pixels.append((byte, byte, byte, 255))
        vb.write_png(files["puddle"], size, size, pixels)

    tcs = unreal.TextureCompressionSettings
    vb.import_texture(files["d"], TEX_DEFAULT_D, srgb=True)
    vb.import_texture(files["n"], TEX_DEFAULT_N, srgb=False, compression=tcs.TC_NORMALMAP,
                      lod_group=unreal.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP)
    vb.import_texture(files["orm"], TEX_DEFAULT_ORM, srgb=False, compression=tcs.TC_MASKS)
    if not unreal.EditorAssetLibrary.does_asset_exist(TEX_PUDDLE_MASK):
        vb.import_texture(files["puddle"], TEX_PUDDLE_MASK, srgb=False, compression=tcs.TC_MASKS)


# ---------------------------------------------------------------------------
# 3. Material Parameter Collection
# ---------------------------------------------------------------------------
def create_world_mpc():
    mpc, _ = vb.load_or_create(vb.MPC_WORLD, unreal.MaterialParameterCollection,
                               unreal.MaterialParameterCollectionFactoryNew())

    existing = {str(p.get_editor_property("parameter_name")) for p in mpc.get_editor_property("scalar_parameters")}
    scalars = list(mpc.get_editor_property("scalar_parameters"))
    for name, default in MPC_SCALARS:
        if name in existing:
            continue
        param = unreal.CollectionScalarParameter()
        param.set_editor_property("parameter_name", name)
        param.set_editor_property("default_value", default)
        scalars.append(param)
    mpc.set_editor_property("scalar_parameters", scalars)

    existing_vec = {str(p.get_editor_property("parameter_name")) for p in mpc.get_editor_property("vector_parameters")}
    vectors = list(mpc.get_editor_property("vector_parameters"))
    for name, default in MPC_VECTORS:
        if name in existing_vec:
            continue
        param = unreal.CollectionVectorParameter()
        param.set_editor_property("parameter_name", name)
        param.set_editor_property("default_value", default)
        vectors.append(param)
    mpc.set_editor_property("vector_parameters", vectors)

    vb.save_asset(mpc)
    return mpc


# ---------------------------------------------------------------------------
# 4. Master-Material
# ---------------------------------------------------------------------------
MaterialGraph = vb.MaterialGraph


def build_master_material(mpc):
    """M_VB_Surface: PBR (BaseColor/Normal/ORM) + globale Naesse + Pfuetzen aus der MPC."""
    material, created = vb.load_or_create(vb.MASTER_SURFACE, unreal.Material, unreal.MaterialFactoryNew())
    if not created:
        MEL.delete_all_material_expressions(material)

    for usage_name in ("MATL_NANITE", "MATL_INSTANCED_STATIC_MESHES", "MATL_SKELETAL_MESH"):
        usage = getattr(unreal.MaterialUsage, usage_name, None)
        if usage is not None:
            try:
                MEL.set_material_usage(material, usage)
            except Exception:
                pass

    tex_d = unreal.load_asset(TEX_DEFAULT_D)
    tex_n = unreal.load_asset(TEX_DEFAULT_N)
    tex_orm = unreal.load_asset(TEX_DEFAULT_ORM)
    tex_puddle = unreal.load_asset(TEX_PUDDLE_MASK)
    sampler = unreal.MaterialSamplerType

    g = MaterialGraph(material)

    # --- UVs ----------------------------------------------------------------
    texcoord = g.node(unreal.MaterialExpressionTextureCoordinate, -2200, 0)
    tiling = g.scalar("UVTiling", 1.0, -2200, 120, group="UV")
    uv = g.node(unreal.MaterialExpressionMultiply, -2000, 40)
    g.link(texcoord, "", uv, "A")
    g.link(tiling, "", uv, "B")

    # --- Texturen -----------------------------------------------------------
    base_tex = g.node(unreal.MaterialExpressionTextureSampleParameter2D, -1750, -400,
                      parameter_name="BaseColorMap", texture=tex_d, sampler_type=sampler.SAMPLERTYPE_COLOR, group="Textures")
    normal_tex = g.node(unreal.MaterialExpressionTextureSampleParameter2D, -1750, 400,
                        parameter_name="NormalMap", texture=tex_n, sampler_type=sampler.SAMPLERTYPE_NORMAL, group="Textures")
    orm_tex = g.node(unreal.MaterialExpressionTextureSampleParameter2D, -1750, 0,
                     parameter_name="ORMMap", texture=tex_orm, sampler_type=sampler.SAMPLERTYPE_MASKS, group="Textures")
    for texture_node in (base_tex, normal_tex, orm_tex):
        g.link(uv, "", texture_node, "UVs")

    # --- Grundwerte -----------------------------------------------------------
    tint = g.node(unreal.MaterialExpressionVectorParameter, -1750, -600,
                  parameter_name="BaseColorTint", default_value=unreal.LinearColor(0.5, 0.5, 0.5, 1.0), group="Surface")
    # Zweiter Farbton je Gebaeude: Custom Primitive Data [1] ("TintBlend") * TintVariation
    tint2 = g.node(unreal.MaterialExpressionVectorParameter, -1750, -760,
                   parameter_name="BaseColorTint2", default_value=unreal.LinearColor(0.5, 0.5, 0.5, 1.0), group="Surface")
    tint_blend = g.scalar("TintBlend", 0.0, -1750, -860, group="Surface")
    try:
        tint_blend.set_editor_property("use_custom_primitive_data", True)
        tint_blend.set_editor_property("primitive_data_index", 1)
    except Exception:  # noqa: BLE001
        pass
    tint_variation = g.scalar("TintVariation", 0.0, -1750, -940, group="Surface")
    tint_alpha = g.node(unreal.MaterialExpressionMultiply, -1600, -880)
    g.link(tint_blend, "", tint_alpha, "A")
    g.link(tint_variation, "", tint_alpha, "B")
    tint_final = g.node(unreal.MaterialExpressionLinearInterpolate, -1550, -650)
    g.link(tint, "", tint_final, "A")
    g.link(tint2, "", tint_final, "B")
    g.link(tint_alpha, "", tint_final, "Alpha")
    # Lackfarbe je Fahrzeug aus Custom Primitive Data 6..8 (nur wenn UsePaintData = 1, z. B. Karosserie)
    paint = []
    for index, channel_name in ((6, "PaintR"), (7, "PaintG"), (8, "PaintB")):
        node = g.scalar(channel_name, 0.5, -1900, -1100 + index * 40, group="Paint")
        try:
            node.set_editor_property("use_custom_primitive_data", True)
            node.set_editor_property("primitive_data_index", index)
        except Exception:  # noqa: BLE001
            pass
        paint.append(node)
    paint_rg = g.op(unreal.MaterialExpressionAppendVector, paint[0], paint[1], -1750, -1000)
    paint_rgb = g.op(unreal.MaterialExpressionAppendVector, paint_rg, paint[2], -1650, -1000)
    use_paint = g.scalar("UsePaintData", 0.0, -1750, -900, group="Paint")
    tint_paint = g.lerp(tint_final, paint_rgb, use_paint, -1500, -800)
    base_color = g.node(unreal.MaterialExpressionMultiply, -1450, -450)
    g.link(base_tex, "RGB", base_color, "A")
    g.link(tint_paint, "", base_color, "B")

    roughness_scale = g.scalar("Roughness", 0.7, -1750, 200)
    roughness = g.node(unreal.MaterialExpressionMultiply, -1450, 100)
    g.link(orm_tex, "G", roughness, "A")
    g.link(roughness_scale, "", roughness, "B")

    metallic_scale = g.scalar("Metallic", 0.0, -1750, 280)
    metallic = g.node(unreal.MaterialExpressionMultiply, -1450, 250)
    g.link(orm_tex, "B", metallic, "A")
    g.link(metallic_scale, "", metallic, "B")

    # --- Naesse: MPC.Wetness * (Oberseiten staerker als Waende) * WetnessResponse ----
    wetness = g.mpc(mpc, "Wetness", -1750, 700)
    normal_ws = g.node(unreal.MaterialExpressionVertexNormalWS, -1750, 820)
    up = g.node(unreal.MaterialExpressionComponentMask, -1550, 820, r=False, g=False, b=True, a=False)
    g.link(normal_ws, "", up, "")
    up_sat = g.node(unreal.MaterialExpressionSaturate, -1400, 820)
    g.link(up, "", up_sat, "")
    exposure = g.node(unreal.MaterialExpressionLinearInterpolate, -1250, 800, const_a=0.35, const_b=1.0)
    g.link(up_sat, "", exposure, "Alpha")

    wet_response = g.scalar("WetnessResponse", 1.0, -1400, 950, group="Weather")
    wet_a = g.node(unreal.MaterialExpressionMultiply, -1050, 720)
    g.link(wetness, "", wet_a, "A")
    g.link(exposure, "", wet_a, "B")
    wet_mask = g.node(unreal.MaterialExpressionMultiply, -900, 760)
    g.link(wet_a, "", wet_mask, "A")
    g.link(wet_response, "", wet_mask, "B")

    # --- Pfuetzen: Welt-ausgerichtete Maske (unabhaengig von UVs), nur auf flachen Flaechen ----
    world_pos = g.node(unreal.MaterialExpressionWorldPosition, -1750, 1150)
    world_xy = g.node(unreal.MaterialExpressionComponentMask, -1550, 1150, r=True, g=True, b=False, a=False)
    g.link(world_pos, "", world_xy, "")
    puddle_scale = g.scalar("PuddleWorldSize", 900.0, -1550, 1260, group="Weather")
    puddle_uv = g.node(unreal.MaterialExpressionDivide, -1400, 1170)
    g.link(world_xy, "", puddle_uv, "A")
    g.link(puddle_scale, "", puddle_uv, "B")
    puddle_tex = g.node(unreal.MaterialExpressionTextureSampleParameter2D, -1250, 1150,
                        parameter_name="PuddleMask", texture=tex_puddle, sampler_type=sampler.SAMPLERTYPE_MASKS, group="Weather")
    g.link(puddle_uv, "", puddle_tex, "UVs")

    # Bei maximaler Pfuetzenmenge ~55 % der flachen Flaechen bedeckt (Senken zuerst)
    puddles = g.mpc(mpc, "Puddles", -1250, 1350)
    puddles_scaled = g.node(unreal.MaterialExpressionMultiply, -1100, 1350, const_b=0.55)
    g.link(puddles, "", puddles_scaled, "A")
    puddle_add = g.node(unreal.MaterialExpressionAdd, -1000, 1200)
    g.link(puddle_tex, "R", puddle_add, "A")
    g.link(puddles_scaled, "", puddle_add, "B")
    puddle_shift = g.node(unreal.MaterialExpressionAdd, -850, 1200, const_b=-1.0)
    g.link(puddle_add, "", puddle_shift, "A")
    puddle_sharp = g.node(unreal.MaterialExpressionMultiply, -700, 1200, const_b=6.0)
    g.link(puddle_shift, "", puddle_sharp, "A")
    puddle_sat = g.node(unreal.MaterialExpressionSaturate, -550, 1200)
    g.link(puddle_sharp, "", puddle_sat, "")

    flat_shift = g.node(unreal.MaterialExpressionAdd, -1250, 900, const_b=-0.92)
    g.link(up, "", flat_shift, "A")
    flat_sharp = g.node(unreal.MaterialExpressionMultiply, -1100, 900, const_b=12.5)
    g.link(flat_shift, "", flat_sharp, "A")
    flat_mask = g.node(unreal.MaterialExpressionSaturate, -950, 900)
    g.link(flat_sharp, "", flat_mask, "")

    puddle_response = g.scalar("PuddleResponse", 1.0, -700, 1350, group="Weather")
    puddle_a = g.node(unreal.MaterialExpressionMultiply, -400, 1150)
    g.link(puddle_sat, "", puddle_a, "A")
    g.link(flat_mask, "", puddle_a, "B")
    puddle_mask = g.node(unreal.MaterialExpressionMultiply, -250, 1200)
    g.link(puddle_a, "", puddle_mask, "A")
    g.link(puddle_response, "", puddle_mask, "B")

    # --- Anti-Tiling: grossflaechige, weltbasierte Helligkeitsvariation ------------
    # Verhindert, dass sich kachelnde Oberflaechen (Asphalt, Pflaster) sichtbar wiederholen.
    macro_size = g.scalar("MacroWorldSize", 2300.0, -1250, -900, group="AntiTiling")
    macro_amount = g.scalar("MacroVariation", 0.18, -1250, -800, group="AntiTiling")
    macro_uv = g.node(unreal.MaterialExpressionDivide, -1100, -950)
    g.link(world_xy, "", macro_uv, "A")
    g.link(macro_size, "", macro_uv, "B")
    macro_tex = g.node(unreal.MaterialExpressionTextureSample, -950, -950, texture=tex_puddle,
                       sampler_type=sampler.SAMPLERTYPE_MASKS)
    g.link(macro_uv, "", macro_tex, "UVs")
    macro_centered = g.node(unreal.MaterialExpressionAdd, -800, -950, const_b=-0.5)
    g.link(macro_tex, "G", macro_centered, "A")
    macro_scaled = g.node(unreal.MaterialExpressionMultiply, -680, -950, const_b=2.0)
    g.link(macro_centered, "", macro_scaled, "A")
    macro_weighted = g.node(unreal.MaterialExpressionMultiply, -560, -950)
    g.link(macro_scaled, "", macro_weighted, "A")
    g.link(macro_amount, "", macro_weighted, "B")
    macro_factor = g.node(unreal.MaterialExpressionAdd, -440, -950, const_b=1.0)
    g.link(macro_weighted, "", macro_factor, "A")
    base_macro = g.node(unreal.MaterialExpressionMultiply, -300, -600)
    g.link(base_color, "", base_macro, "A")
    g.link(macro_factor, "", base_macro, "B")

    # --- Kombination -----------------------------------------------------------
    # Nasse, poroese Oberflaechen werden dunkler (Wasser fuellt Poren)
    porosity = g.scalar("Porosity", 0.5, -1100, -250, group="Weather")
    porosity_half = g.node(unreal.MaterialExpressionMultiply, -950, -250, const_b=0.55)
    g.link(porosity, "", porosity_half, "A")
    wet_dark = g.node(unreal.MaterialExpressionOneMinus, -800, -250)
    g.link(porosity_half, "", wet_dark, "")
    wet_factor = g.node(unreal.MaterialExpressionLinearInterpolate, -650, -300, const_a=1.0)
    g.link(wet_dark, "", wet_factor, "B")
    g.link(wet_mask, "", wet_factor, "Alpha")
    base_wet = g.node(unreal.MaterialExpressionMultiply, -450, -400)
    g.link(base_macro, "", base_wet, "A")
    g.link(wet_factor, "", base_wet, "B")
    base_puddle_dark = g.node(unreal.MaterialExpressionMultiply, -300, -300, const_b=0.6)
    g.link(base_wet, "", base_puddle_dark, "A")
    base_final = g.node(unreal.MaterialExpressionLinearInterpolate, -150, -400)
    g.link(base_wet, "", base_final, "A")
    g.link(base_puddle_dark, "", base_final, "B")
    g.link(puddle_mask, "", base_final, "Alpha")

    # Rauheit: nass -> 0.12, Pfuetze -> spiegelnd 0.03
    rough_wet = g.node(unreal.MaterialExpressionLinearInterpolate, -450, 100, const_b=0.12)
    g.link(roughness, "", rough_wet, "A")
    g.link(wet_mask, "", rough_wet, "Alpha")
    rough_final = g.node(unreal.MaterialExpressionLinearInterpolate, -150, 100, const_b=0.03)
    g.link(rough_wet, "", rough_final, "A")
    g.link(puddle_mask, "", rough_final, "Alpha")

    # Normalen: Pfuetzen sind glatte Wasserflaechen, bei Regen mit animierten Tropfenringen
    flat_normal = g.node(unreal.MaterialExpressionConstant3Vector, -450, 520,
                         constant=unreal.LinearColor(0.0, 0.0, 1.0, 0.0))
    ripple_texture = unreal.load_asset(TEX_RAIN_RIPPLES) if unreal.EditorAssetLibrary.does_asset_exist(TEX_RAIN_RIPPLES) else None
    if ripple_texture is not None:
        # Flipbook 4 x 4: Frame = floor(frac(Zeit * Tempo) * 16), UV = (frac(Welt / Groesse) + (Spalte, Zeile)) / 4
        time = g.node(unreal.MaterialExpressionTime, -1750, 2100)
        speed = g.scalar("RippleSpeed", 1.3, -1750, 2200, group="Weather")
        cycles = g.node(unreal.MaterialExpressionMultiply, -1600, 2120)
        g.link(time, "", cycles, "A")
        g.link(speed, "", cycles, "B")
        phase = g.node(unreal.MaterialExpressionFrac, -1480, 2120)
        g.link(cycles, "", phase, "")
        frame_f = g.node(unreal.MaterialExpressionMultiply, -1380, 2120, const_b=16.0)
        g.link(phase, "", frame_f, "A")
        frame = g.node(unreal.MaterialExpressionFloor, -1260, 2120)
        g.link(frame_f, "", frame, "")
        four = g.node(unreal.MaterialExpressionConstant, -1260, 2220, r=4.0)
        column = g.node(unreal.MaterialExpressionFmod, -1140, 2100)
        g.link(frame, "", column, "A")
        g.link(four, "", column, "B")
        row_f = g.node(unreal.MaterialExpressionDivide, -1140, 2200, const_b=4.0)
        g.link(frame, "", row_f, "A")
        row = g.node(unreal.MaterialExpressionFloor, -1020, 2200)
        g.link(row_f, "", row, "")
        offset = g.node(unreal.MaterialExpressionAppendVector, -900, 2150)
        g.link(column, "", offset, "A")
        g.link(row, "", offset, "B")

        ripple_size = g.scalar("RippleWorldSize", 60.0, -1400, 1950, group="Weather")
        ripple_uv = g.node(unreal.MaterialExpressionDivide, -1250, 1950)
        g.link(world_xy, "", ripple_uv, "A")
        g.link(ripple_size, "", ripple_uv, "B")
        cell = g.node(unreal.MaterialExpressionFrac, -1100, 1950)
        g.link(ripple_uv, "", cell, "")
        cell_offset = g.node(unreal.MaterialExpressionAdd, -800, 2000)
        g.link(cell, "", cell_offset, "A")
        g.link(offset, "", cell_offset, "B")
        atlas_uv = g.node(unreal.MaterialExpressionDivide, -680, 2000, const_b=4.0)
        g.link(cell_offset, "", atlas_uv, "A")

        ripple_sample = g.node(unreal.MaterialExpressionTextureSample, -540, 2000, texture=ripple_texture,
                               sampler_type=sampler.SAMPLERTYPE_NORMAL)
        g.link(atlas_uv, "", ripple_sample, "UVs")
        # Mip-Stufe aus der kontinuierlichen UV ableiten -> keine Naehte an den Frame-Grenzen
        try:
            ripple_sample.set_editor_property("mip_value_mode", unreal.TextureMipValueMode.TMVM_DERIVATIVE)
            continuous = g.node(unreal.MaterialExpressionDivide, -900, 1900, const_b=4.0)
            g.link(ripple_uv, "", continuous, "A")
            ddx = g.node(unreal.MaterialExpressionDDX, -760, 1880)
            ddy = g.node(unreal.MaterialExpressionDDY, -760, 1940)
            g.link(continuous, "", ddx, "Value")
            g.link(continuous, "", ddy, "Value")
            g.link(ddx, "", ripple_sample, "DDX(UVs)")
            g.link(ddy, "", ripple_sample, "DDY(UVs)")
        except Exception:  # noqa: BLE001
            vb.warn("Derivative-Mip fuer Regenkraeusel nicht verfuegbar - Standard-Mips werden genutzt.")

        rain = g.mpc(mpc, "RainIntensity", -540, 2150)
        ripple_amount = g.node(unreal.MaterialExpressionMultiply, -400, 2150, const_b=1.5)
        g.link(rain, "", ripple_amount, "A")
        ripple_amount_sat = g.node(unreal.MaterialExpressionSaturate, -300, 2150)
        g.link(ripple_amount, "", ripple_amount_sat, "")
        puddle_normal = g.node(unreal.MaterialExpressionLinearInterpolate, -300, 600)
        g.link(flat_normal, "", puddle_normal, "A")
        g.link(ripple_sample, "RGB", puddle_normal, "B")
        g.link(ripple_amount_sat, "", puddle_normal, "Alpha")
    else:
        vb.warn("Regenkraeusel-Textur fehlt - Pfuetzen bleiben ohne Tropfenringe.")
        puddle_normal = flat_normal

    normal_final = g.node(unreal.MaterialExpressionLinearInterpolate, -150, 450)
    g.link(normal_tex, "RGB", normal_final, "A")
    g.link(puddle_normal, "", normal_final, "B")
    g.link(puddle_mask, "", normal_final, "Alpha")

    # --- Emissive (Leuchten, Fenster, Neon) mit optionalem Daemmerungsschalter ----------
    # "LightOn" liest Custom Primitive Data [0], das UVBNightLightComponent auf 1/0 setzt.
    emissive_color = g.node(unreal.MaterialExpressionVectorParameter, -700, 1600, parameter_name="EmissiveColor",
                            default_value=unreal.LinearColor(1.0, 0.85, 0.6, 1.0), group="Emissive")
    emissive_intensity = g.scalar("EmissiveIntensity", 0.0, -700, 1720, group="Emissive")
    light_on = g.scalar("LightOn", 1.0, -700, 1820, group="Emissive")
    try:
        light_on.set_editor_property("use_custom_primitive_data", True)
        light_on.set_editor_property("primitive_data_index", 0)
    except Exception:  # noqa: BLE001
        vb.warn("Custom Primitive Data fuer LightOn nicht verfuegbar - Daemmerungsschalter wirkt nur auf Lichter.")
    use_switch = g.scalar("UseNightSwitch", 0.0, -700, 1920, group="Emissive")
    # Lichtkanal: 0 = LightOn (CPD 0, Daemmerungsschalter/Ampel), 2..5 = Fahrzeuglichter (CPD 2..5:
    # Bremslicht, Scheinwerfer, Blinker links, Blinker rechts). Auswahl per MI-Parameter "LightChannel".
    channel = g.scalar("LightChannel", 0.0, -950, 2050, group="Emissive")
    selected = None
    for index, source in ((0, light_on),) + tuple((k, None) for k in (2, 3, 4, 5)):
        if source is None:
            source = g.scalar("VehicleLight%d" % index, 0.0, -950, 2150 + index * 60, group="Emissive")
            try:
                source.set_editor_property("use_custom_primitive_data", True)
                source.set_editor_property("primitive_data_index", index)
            except Exception:  # noqa: BLE001
                pass
        # Gewicht = 1 - saturate(|Kanal - index|)
        diff = g.op(unreal.MaterialExpressionSubtract, channel, float(index), -820, 2100 + index * 60)
        weight = g.unary(unreal.MaterialExpressionOneMinus, g.unary(unreal.MaterialExpressionSaturate,
                         g.unary(unreal.MaterialExpressionAbs, diff, -760, 2100 + index * 60), -700, 2100 + index * 60),
                         -640, 2100 + index * 60)
        term = g.op(unreal.MaterialExpressionMultiply, source, weight, -580, 2100 + index * 60)
        selected = term if selected is None else g.op(unreal.MaterialExpressionAdd, selected, term, -520, 2100 + index * 60)
    switch = g.node(unreal.MaterialExpressionLinearInterpolate, -450, 1850, const_a=1.0)
    g.link(selected, "", switch, "B")
    g.link(use_switch, "", switch, "Alpha")
    emissive_raw = g.node(unreal.MaterialExpressionMultiply, -450, 1650)
    g.link(emissive_color, "", emissive_raw, "A")
    g.link(emissive_intensity, "", emissive_raw, "B")
    emissive = g.node(unreal.MaterialExpressionMultiply, -250, 1700)
    g.link(emissive_raw, "", emissive, "A")
    g.link(switch, "", emissive, "B")
    g.output(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    g.output(base_final, "", unreal.MaterialProperty.MP_BASE_COLOR)
    g.output(rough_final, "", unreal.MaterialProperty.MP_ROUGHNESS)
    g.output(metallic, "", unreal.MaterialProperty.MP_METALLIC)
    g.output(normal_final, "", unreal.MaterialProperty.MP_NORMAL)
    g.output(orm_tex, "R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)

    MEL.recompile_material(material)
    vb.save_asset(material)

    if g.failed_links:
        vb.warn("M_VB_Surface: %d Verbindungen fehlgeschlagen (siehe Output Log)." % g.failed_links)
    else:
        vb.log("M_VB_Surface erstellt.")
    return material


WINDOW_MASTER = vb.ROOT + "/Materials/Master/M_VB_Window"

# Interior Mapping (J. van Dongen): Strahl durch einen virtuellen Raum hinter der Scheibe.
# Tangentenraum: UV (Kanal 1) laeuft 0..1 ueber die ganze Scheibe. Raumfarben, Jalousien und
# Beleuchtung werden je Fenster aus einem Zufallswert abgeleitet; nachts brennt Licht abhaengig
# von der Uhrzeit (Abends viele, spaet nachts wenige Fenster).
WINDOW_HLSL = r"""
float2 p = frac(UV) * 2.0 - 1.0;
p.y *= FlipY;
float3 v = normalize(ViewTS);
float3 dir = normalize(float3(-v.x, -v.y * FlipY, -max(abs(v.z), 0.05)));
dir += float3(1e-5, 1e-5, 1e-5) * step(abs(dir), float3(1e-5, 1e-5, 1e-5));
float3 inv = 1.0 / dir;
float3 pos = float3(p, 0.0);
float tx = ((dir.x > 0.0 ? 1.0 : -1.0) - pos.x) * inv.x;
float ty = ((dir.y > 0.0 ? 1.0 : -1.0) - pos.y) * inv.y;
float tz = (-2.0 * Depth - pos.z) * inv.z;
float t = min(min(tx, ty), tz);
float3 hit = pos + dir * t;

float seed = Rand + frac(sin(dot(floor(LocalPos / 150.0), float3(12.9898, 78.233, 37.719))) * 43758.5453);
float h1 = frac(sin(seed * 91.345 + 3.1) * 43758.5453);
float h2 = frac(sin(seed * 17.123 + 1.7) * 24634.6345);
float h3 = frac(sin(seed * 53.770 + 9.2) * 13758.9370);

float3 wallColor = lerp(float3(0.62, 0.56, 0.47), float3(0.42, 0.47, 0.52), h1);
float3 floorColor = lerp(float3(0.26, 0.17, 0.10), float3(0.33, 0.32, 0.31), h2);
float3 ceilingColor = float3(0.78, 0.78, 0.76);
float3 color = wallColor * 0.85;
if (t == ty) { color = (hit.y < 0.0) ? floorColor : ceilingColor; }
else if (t == tz) { color = wallColor; }
// Moebel-Silhouette an der Rueckwand
if (t == tz && hit.y < -0.35 && abs(hit.x - (h3 - 0.5)) < 0.45) { color *= 0.35; }
color *= saturate(1.0 + hit.z / (2.0 * Depth) * 0.55);

float hour = TimeOfDay * 24.0;
float occupancy = (hour > 17.0 && hour < 23.5) ? 0.75 : ((hour >= 23.5 || hour < 5.5) ? 0.12 : ((hour < 8.5) ? 0.45 : 0.25));
float open = (hour > 7.5 && hour < 21.0) ? 1.0 : 0.15;
occupancy = lerp(occupancy, open, IsShop);
float lightOn = step(h2, occupancy);
float3 warm = lerp(float3(1.0, 0.76, 0.48), float3(0.86, 0.92, 1.0), step(0.72, h1));
float dayLum = lerp(DayLuminance, DayLuminance * 3.0, IsShop * lightOn);
float nightLum = NightLuminance * lightOn * (1.0 + IsShop * 2.0);
float lum = lerp(dayLum, nightLum, Night);
float3 interior = color * lerp(float3(1.0, 1.0, 1.0), warm, Night * lightOn) * lum;

// Jalousie (nicht bei Laeden)
float blindHeight = h3 * 0.9 * (1.0 - IsShop);
float blind = step(1.0 - blindHeight, p.y * 0.5 + 0.5);
float3 blindColor = lerp(float3(0.82, 0.8, 0.72), float3(0.35, 0.35, 0.37), step(0.5, h1)) * lum * 0.5;
float3 result = lerp(interior, blindColor, blind);

// Fresnel: unter flachem Blickwinkel dominiert die Spiegelung der Scheibe
float fresnel = 0.04 + 0.96 * pow(1.0 - saturate(abs(v.z)), 5.0);
return result * (1.0 - fresnel);
"""


def build_window_material(mpc):
    """M_VB_Window: spiegelnde Scheibe + Interior Mapping als Emissive (Tag gedaempft, nachts beleuchtet)."""
    material, created = vb.load_or_create(WINDOW_MASTER, unreal.Material, unreal.MaterialFactoryNew())
    if not created:
        MEL.delete_all_material_expressions(material)
    for usage_name in ("MATL_NANITE", "MATL_INSTANCED_STATIC_MESHES"):
        usage = getattr(unreal.MaterialUsage, usage_name, None)
        if usage is not None:
            try:
                MEL.set_material_usage(material, usage)
            except Exception:  # noqa: BLE001
                pass

    g = MaterialGraph(material)
    uv = g.node(unreal.MaterialExpressionTextureCoordinate, -1200, 0, coordinate_index=1)
    camera = g.node(unreal.MaterialExpressionCameraVectorWS, -1400, 150)
    to_tangent = g.node(unreal.MaterialExpressionTransform, -1200, 150)
    try:
        to_tangent.set_editor_property("transform_source_type", unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD)
        to_tangent.set_editor_property("transform_type", unreal.MaterialVectorCoordTransform.TRANSFORM_TANGENT)
    except Exception as exc:  # noqa: BLE001
        vb.warn("Transform-Knoten: %s" % exc)
    g.link(camera, "", to_tangent, "")
    rand = g.node(unreal.MaterialExpressionPerInstanceRandom, -1200, 300)
    # Lokale Position (float, keine Large-World-Coordinates im Custom-Node) + Zufall je Instanz
    local_class = getattr(unreal, "MaterialExpressionLocalPosition", None)
    if local_class is not None:
        local = g.node(local_class, -1200, 380)
    else:
        local = g.node(unreal.MaterialExpressionConstant3Vector, -1200, 380, constant=unreal.LinearColor(0, 0, 0, 0))
    night = g.mpc(mpc, "NightFactor", -1200, 460)
    time = g.mpc(mpc, "TimeOfDay01", -1200, 540)
    depth = g.scalar("RoomDepth", 1.0, -1200, 620, group="Interior")
    day_lum = g.scalar("DayLuminance", 350.0, -1200, 700, group="Interior")
    night_lum = g.scalar("NightLuminance", 18.0, -1200, 780, group="Interior")
    is_shop = g.scalar("IsShop", 0.0, -1200, 860, group="Interior")
    flip_y = g.scalar("FlipY", 1.0, -1200, 940, group="Interior")

    custom = g.node(unreal.MaterialExpressionCustom, -800, 300)
    custom.set_editor_property("code", WINDOW_HLSL)
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    custom.set_editor_property("description", "VB Interior Mapping")
    names = ["UV", "ViewTS", "Rand", "LocalPos", "Night", "TimeOfDay", "Depth", "DayLuminance", "NightLuminance", "IsShop", "FlipY"]
    custom.set_editor_property("inputs", [unreal.CustomInput(input_name=name) for name in names])
    for name, source in zip(names, [uv, to_tangent, rand, local, night, time, depth, day_lum, night_lum, is_shop, flip_y]):
        g.link(source, "", custom, name)

    glass_color = g.node(unreal.MaterialExpressionVectorParameter, -500, 0, parameter_name="GlassColor",
                         default_value=unreal.LinearColor(0.02, 0.025, 0.028, 1.0), group="Glass")
    glass_rough = g.scalar("GlassRoughness", 0.04, -500, 120, group="Glass")
    g.output(glass_color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    g.output(glass_rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    g.output(custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    MEL.recompile_material(material)
    vb.save_asset(material)
    if g.failed_links:
        vb.warn("M_VB_Window: %d Verbindungen fehlgeschlagen." % g.failed_links)

    instances = {}
    for name, params in (("Window", {}), ("WindowShop", {"IsShop": 1.0, "RoomDepth": 1.6, "DayLuminance": 500.0})):
        mi, _ = vb.load_or_create(vb.shared_material_path(name), unreal.MaterialInstanceConstant,
                                  unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, material)
        for key, value in params.items():
            MEL.set_material_instance_scalar_parameter_value(mi, key, value)
        MEL.update_material_instance(mi)
        vb.save_asset(mi)
        instances[name] = mi
    return instances


def create_material_instances(master):
    instances = {}
    folder = vb.ROOT + "/Materials/Instances"
    for name, (color, rough, metal, porosity, wet_response, puddle_response) in MATERIAL_INSTANCES.items():
        mi, _ = vb.load_or_create(folder + "/" + name, unreal.MaterialInstanceConstant,
                                  unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, master)
        MEL.set_material_instance_vector_parameter_value(mi, "BaseColorTint", unreal.LinearColor(color[0], color[1], color[2], 1.0))
        MEL.set_material_instance_scalar_parameter_value(mi, "Roughness", rough)
        MEL.set_material_instance_scalar_parameter_value(mi, "Metallic", metal)
        MEL.set_material_instance_scalar_parameter_value(mi, "Porosity", porosity)
        MEL.set_material_instance_scalar_parameter_value(mi, "WetnessResponse", wet_response)
        MEL.set_material_instance_scalar_parameter_value(mi, "PuddleResponse", puddle_response)
        MEL.update_material_instance(mi)
        vb.save_asset(mi)
        instances[name] = mi
    return instances


# ---------------------------------------------------------------------------
# 5. Spielfigur
# ---------------------------------------------------------------------------
PREFERRED_MESHES = ["SKM_Manny", "SKM_Quinn", "SKM_Manny_Simple", "SKM_UEFN_Mannequin"]
PREFERRED_ANIMBPS = ["ABP_Unarmed", "ABP_Manny", "ABP_Quinn", "ABP_Mannequin"]


def find_assets_by_names(names, search_root="/Game"):
    found = {}
    for path in unreal.EditorAssetLibrary.list_assets(search_root, recursive=True, include_folder=False):
        base = path.rsplit("/", 1)[-1].split(".")[0]
        if base in names and base not in found:
            found[base] = path.split(".")[0]
    for name in names:
        if name in found:
            return found[name]
    return None


def configure_player():
    mesh_path = find_assets_by_names(PREFERRED_MESHES)
    anim_path = find_assets_by_names(PREFERRED_ANIMBPS)
    if not mesh_path:
        vb.warn("Kein Mannequin gefunden. Content Browser -> Hinzufuegen -> 'Feature oder Content Pack' -> Third Person.")
        return None

    settings = unreal.get_default_object(unreal.VBGameSettings)
    try:
        settings.set_editor_property("player_mesh", unreal.load_asset(mesh_path))
        if anim_path:
            anim_class = unreal.EditorAssetLibrary.load_blueprint_class(anim_path)
            if anim_class:
                settings.set_editor_property("player_anim_class", anim_class)
        settings.save_to_default_config()
    except Exception as exc:  # noqa: BLE001 - dem Nutzer klar melden
        vb.error("Spieler-Einstellungen konnten nicht gespeichert werden: %s" % exc)
        return None

    vb.log("Spielfigur: %s | Animation: %s" % (mesh_path, anim_path or "-"))
    return mesh_path


# ---------------------------------------------------------------------------
# 6. Entwicklungskarte
# ---------------------------------------------------------------------------
LIGHTING_CLASSES = ("DirectionalLight", "SkyAtmosphere", "SkyLight", "ExponentialHeightFog", "VolumetricCloud")


def open_or_create_dev_map():
    level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if unreal.EditorAssetLibrary.does_asset_exist(vb.MAP_DEV):
        level_editor.load_level(vb.MAP_DEV)
        return False

    created = False
    try:
        created = level_editor.new_level(vb.MAP_DEV, True)  # True = World Partition
    except TypeError:
        created = False
    if not created:
        try:
            created = level_editor.new_level_from_template(vb.MAP_DEV, "/Engine/Maps/Templates/OpenWorld")
        except Exception:  # noqa: BLE001
            created = False
    if not created:
        created = level_editor.new_level(vb.MAP_DEV)
    if not created:
        raise RuntimeError("Karte %s konnte nicht erstellt werden." % vb.MAP_DEV)
    return True


def clear_generated_actors(actor_subsystem, remove_template_lighting):
    for actor in actor_subsystem.get_all_level_actors():
        class_name = actor.get_class().get_name()
        if actor.actor_has_tag(vb.GENERATED_TAG):
            actor_subsystem.destroy_actor(actor)
        elif remove_template_lighting and class_name in LIGHTING_CLASSES:
            actor_subsystem.destroy_actor(actor)


KIT_ROOT = vb.ROOT + "/Environment"
KIT = {
    "road": KIT_ROOT + "/Roads/SM_VB_Road_10m/SM_VB_Road_10m",
    "crosswalk": KIT_ROOT + "/Roads/SM_VB_Road_10m_Crosswalk/SM_VB_Road_10m_Crosswalk",
    "curb": KIT_ROOT + "/Roads/SM_VB_Curb_2m/SM_VB_Curb_2m",
    "sidewalk": KIT_ROOT + "/Roads/SM_VB_Sidewalk_2m/SM_VB_Sidewalk_2m",
    "manhole": KIT_ROOT + "/Roads/SM_VB_Manhole_A/SM_VB_Manhole_A",
    "bollard": KIT_ROOT + "/Props/SM_VB_Bollard_A/SM_VB_Bollard_A",
    "bench": KIT_ROOT + "/Props/SM_VB_Bench_A/SM_VB_Bench_A",
    "bin": KIT_ROOT + "/Props/SM_VB_TrashBin_A/SM_VB_TrashBin_A",
    "hydrant": KIT_ROOT + "/Props/SM_VB_Hydrant_A/SM_VB_Hydrant_A",
    "sign": KIT_ROOT + "/Props/SM_VB_Sign_NoStopping/SM_VB_Sign_NoStopping",
    "signal": KIT_ROOT + "/Props/SM_VB_TrafficLight_A/SM_VB_TrafficLight_A",
    "signal_lens": KIT_ROOT + "/Props/SM_VB_SignalLens/SM_VB_SignalLens",
}
KIT["intersection"] = KIT_ROOT + "/Roads/SM_VB_Intersection_4Way/SM_VB_Intersection_4Way"
ROOF_TILE = KIT_ROOT + "/Buildings/SM_VB_Roof_Tile_3m/SM_VB_Roof_Tile_3m"
ROOF_PROPS = [KIT_ROOT + "/Props/SM_VB_Roof_%s/SM_VB_Roof_%s" % (n, n) for n in ("AC", "Vent", "Antenna", "StairHouse")]
BUILDING_LINE = 978.0  # Gehweg-Hinterkante (cm von der Strassenmitte)


def load_kit(path):
    return unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None


def prop_rule(mesh, spacing, start, lateral, height=15.0, yaw=0.0, jitter=0.0, probability=1.0,
              on_road=False, left=True, right=True):
    rule = unreal.VBStreetPropRule()
    rule.set_editor_property("mesh", mesh)
    rule.set_editor_property("spacing", spacing)
    rule.set_editor_property("start_offset", start)
    rule.set_editor_property("lateral_offset", lateral)
    rule.set_editor_property("height", height)
    rule.set_editor_property("yaw_offset", yaw)
    rule.set_editor_property("position_jitter", jitter)
    rule.set_editor_property("probability", probability)
    rule.set_editor_property("on_road_surface", on_road)
    rule.set_editor_property("left_side", left)
    rule.set_editor_property("right_side", right)
    return rule


def build_kit_street(actors, kit, length):
    """Phase 2: 120 m Strasse aus dem Blender-Kit mit Zebrastreifen, Ampeln und Stadtmoebeln."""
    origin_x = -length * 0.5
    builder = actors.spawn_actor_from_class(unreal.VBStreetBuilder, unreal.Vector(origin_x, 0, 0))
    builder.set_editor_property("length", length)
    builder.set_editor_property("road_mesh", kit["road"])
    builder.set_editor_property("crosswalk_mesh", kit["crosswalk"])
    builder.set_editor_property("curb_mesh", kit["curb"])
    builder.set_editor_property("sidewalk_mesh", kit["sidewalk"])
    crosswalk_index = int(length * 0.5 // 1000)  # Fahrbahnstueck bei X = 0 .. 10 m
    builder.set_editor_property("crosswalk_piece_index", crosswalk_index)

    builder.set_editor_property("props", street_prop_rules(kit))
    vb.tag_actor(builder, "Street_Main", "Street", prototype=False)

    # Ampeln am Zebrastreifen (Welt-X 0..10 m): je Fahrtrichtung rechts, vor der Haltelinie
    if kit["signal"] and kit["signal_lens"]:
        crossing_x = origin_x + crosswalk_index * 1000.0
        for label, x, y, yaw in (("TrafficLight_East", crossing_x + 100, 700, 180.0),
                                 ("TrafficLight_West", crossing_x + 900, -700, 0.0)):
            spawn_signal(actors, kit, label, unreal.Vector(x, y, 15), yaw, 0.0)
    return builder


def street_prop_rules(kit):
    rules = []
    if kit["manhole"]:
        rules.append(prop_rule(kit["manhole"], 3500, 1500, 280, jitter=500, probability=0.8, on_road=True))
    if kit["bollard"]:
        rules.append(prop_rule(kit["bollard"], 1200, 600, 650, probability=0.5))
    if kit["bench"]:
        rules.append(prop_rule(kit["bench"], 2500, 1200, 930, probability=0.7))
    if kit["bin"]:
        rules.append(prop_rule(kit["bin"], 2500, 1900, 690, jitter=150, probability=0.9))
    if kit["hydrant"]:
        rules.append(prop_rule(kit["hydrant"], 5000, 3100, 700, probability=0.7))
    if kit["sign"]:
        # Schilder schauen dem Verkehr entgegen
        rules.append(prop_rule(kit["sign"], 4000, 2300, 670, yaw=-90.0, probability=0.8))
    return rules


def spawn_signal(actors, kit, label, location, yaw, cycle_offset):
    signal = actors.spawn_actor_from_class(unreal.VBTrafficLight, location, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    signal.set_editor_property("model", kit["signal"])
    signal.set_editor_property("lens_model", kit["signal_lens"])
    signal.set_editor_property("cycle_offset", cycle_offset)
    vb.tag_actor(signal, label, "Street/TrafficLights", prototype=False)
    return signal


# ---------------------------------------------------------------------------
# Phase 3: Stadtblock (3 x 3 Bloecke, Mittelblock mit Blockrandbebauung und Innenhof)
# ---------------------------------------------------------------------------
BLOCK_W, BLOCK_D = 6000.0, 3000.0            # Bauflucht-Rechteck eines Blocks (cm)
STREET_X = BLOCK_W / 2 + BUILDING_LINE      # Mittellinie der Nord-Sued-Strassen (x = +/- 3978)
STREET_Y = BLOCK_D / 2 + BUILDING_LINE      # Mittellinie der Ost-West-Strassen (y = +/- 2478)
PITCH_X, PITCH_Y = 2 * STREET_X, 2 * STREET_Y
SIGNAL_CYCLE_OFFSET_CROSS = 18.5            # Querrichtung gegenphasig (1 s Alles-Rot)


STYLE_WEIGHTS = {"A": 9, "B": 7, "C": 4}   # Altbau praegt die Kuestenstadt, moderne Bauten als Akzent


def pick_style(rng, styles):
    pool = [letter for letter in styles for _ in range(STYLE_WEIGHTS.get(letter, 1))]
    return rng.choice(pool)


def facade_style(letter):
    base = KIT_ROOT + "/Buildings/SM_VB_Fac%s_%%s/SM_VB_Fac%s_%%s" % (letter, letter)
    variant = {"A": "Balcony", "B": "WindowPair", "C": "Panel"}[letter]
    style = unreal.VBFacadeStyle()
    for prop, kind in (("window", "Window"), ("variant", variant), ("plain", "Plain"), ("ground_shop", "GroundShop"),
                       ("ground_door", "GroundDoor"), ("ground_window", "GroundWindow"), ("ground_plain", "GroundPlain"),
                       ("cornice", "Cornice"), ("corner_ground", "CornerGround"), ("corner_upper", "CornerUpper"),
                       ("corner_cornice", "CornerCornice")):
        mesh = load_kit(base % (kind, kind))
        if mesh is None:
            return None
        style.set_editor_property(prop, mesh)
    return style


def spawn_building(actors, label, folder, origin, yaw, style, bays_x, bays_y, floors, modes, seed, roof, roof_props,
                   shop_ratio=0.7):
    building = actors.spawn_actor_from_class(unreal.VBBuildingBuilder, origin, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    building.set_editor_property("style", style)
    building.set_editor_property("bays_x", bays_x)
    building.set_editor_property("bays_y", bays_y)
    building.set_editor_property("floors", floors)
    mode = unreal.VBFacadeMode
    for prop, value in zip(("front", "right", "back", "left"), modes):
        building.set_editor_property(prop, getattr(mode, value.upper()))
    building.set_editor_property("seed", seed)
    building.set_editor_property("shop_ratio", shop_ratio)
    building.set_editor_property("roof_tile", roof)
    building.set_editor_property("roof_props", roof_props)
    vb.tag_actor(building, label, folder, prototype=False)
    return building


def build_block(actors, center, styles, roof, roof_props, rng, label, detailed):
    """Blockrandbebauung: Nord- und Suedzeile ueber die volle Breite, Ost-/Westzeile dazwischen.
    detailed=False: nur zwei Zeilen (Nachbarbloecke, guenstiger)."""
    cx, cy = center
    half_w, half_d = BLOCK_W / 2, BLOCK_D / 2
    bay = 300.0
    row_depth = 3 if detailed else 5
    count = 0

    def row(y_edge, outward_north, widths):
        nonlocal count
        x = cx - half_w
        for index, bays in enumerate(widths):
            first, last = index == 0, index == len(widths) - 1
            letter = pick_style(rng, styles)
            floors = rng.randint(4, 7) if detailed else rng.randint(4, 8)
            if outward_north:   # Front zeigt nach +Y -> Yaw 180, Ursprung am oestlichen Ende
                origin = unreal.Vector(x + bays * bay, y_edge, 0)
                yaw, left_open, right_open = 180.0, last, first
            else:               # Front zeigt nach -Y -> Yaw 0, Ursprung am westlichen Ende
                origin = unreal.Vector(x, y_edge, 0)
                yaw, left_open, right_open = 0.0, first, last
            modes = ("Full", "Full" if right_open else "Plain", "Full" if detailed else "Plain", "Full" if left_open else "Plain")
            spawn_building(actors, "%s_B%02d" % (label, count), "City/%s" % label, origin, yaw, styles[letter], bays,
                           row_depth, floors, modes, rng.randint(1, 99999), roof, roof_props)
            count += 1
            x += bays * bay

    splits = [[5, 6, 4, 5], [4, 5, 6, 5], [6, 4, 5, 5], [5, 5, 5, 5], [7, 6, 7], [3, 5, 4, 4, 4]]
    row(cy - half_d, False, rng.choice(splits))
    row(cy + half_d, True, rng.choice(splits))
    if detailed:
        # Ost- und Westzeile zwischen Nord- und Suedzeile (Laenge 4 Achsen, Tiefe 3 Achsen), Stirnseiten = Brandwaende
        inner = int((BLOCK_D - 2 * row_depth * bay) / bay)
        for east in (True, False):
            letter = pick_style(rng, styles)
            if east:
                origin, yaw = unreal.Vector(cx + half_w, cy - inner * bay / 2, 0), 90.0
            else:
                origin, yaw = unreal.Vector(cx - half_w, cy + inner * bay / 2, 0), 270.0
            spawn_building(actors, "%s_B%02d" % (label, count), "City/%s" % label, origin, yaw, styles[letter], inner,
                           row_depth, rng.randint(4, 6), ("Full", "Plain", "Full", "Plain"), rng.randint(1, 99999), roof,
                           roof_props)
            count += 1
    return count


def spawn_street(actors, kit, label, origin, yaw, length):
    builder = actors.spawn_actor_from_class(unreal.VBStreetBuilder, origin, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    builder.set_editor_property("length", length)
    builder.set_editor_property("road_mesh", kit["road"])
    builder.set_editor_property("curb_mesh", kit["curb"])
    builder.set_editor_property("sidewalk_mesh", kit["sidewalk"])
    builder.set_editor_property("crosswalk_piece_index", -1)
    builder.set_editor_property("seed", abs(hash(label)) % 10000)
    builder.set_editor_property("props", street_prop_rules(kit))
    vb.tag_actor(builder, label, "Street", prototype=False)
    return builder


def street_lamps(actors, lamp_model, origin, yaw, length, label, spacing=2500.0):
    """Laternen beidseitig versetzt, in Strassen-Koordinaten (x entlang, y quer) -> Welt."""
    count = 0
    rad = math.radians(yaw)
    fx, fy = math.cos(rad), math.sin(rad)
    for side in (-1, 1):
        x = spacing * (0.3 if side > 0 else 0.8)
        while x < length - 100:
            lx, ly = x, side * 700.0
            world = unreal.Vector(origin.x + fx * lx - fy * ly, origin.y + fy * lx + fx * ly, 15)
            lamp = actors.spawn_actor_from_class(unreal.VBStreetLight, world,
                                                 unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw + (-90.0 if side > 0 else 90.0)))
            if lamp_model is not None:
                lamp.set_editor_property("model", lamp_model)
            vb.tag_actor(lamp, "%s_Lamp%02d" % (label, count), "Street/StreetLights", prototype=lamp_model is None)
            count += 1
            x += spacing
    return count


def build_city_block(actors, kit, styles, roof, roof_props):
    rng = random.Random(42)
    lamp_model = load_kit(STREETLIGHT_MODEL)
    counts = {"buildings": 0, "streets": 0, "lamps": 0, "signals": 0}

    # Bloecke: Mitte detailliert, 8 Nachbarn
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            detailed = (i == 0 and j == 0)
            counts["buildings"] += build_block(actors, (i * PITCH_X, j * PITCH_Y), styles, roof, roof_props, rng,
                                               "Block_%d_%d" % (i + 1, j + 1), detailed)

    # Ost-West-Strassen (y = +/- STREET_Y), je 3 Abschnitte zwischen den Kreuzungen
    segments = []
    for sy in (-1, 1):
        for i in (-1, 0, 1):
            segments.append(("Street_EW_%d_%d" % (sy + 1, i + 1), unreal.Vector(i * PITCH_X - BLOCK_W / 2, sy * STREET_Y, 0), 0.0, BLOCK_W))
    for sx in (-1, 1):
        for j in (-1, 0, 1):
            segments.append(("Street_NS_%d_%d" % (sx + 1, j + 1), unreal.Vector(sx * STREET_X, j * PITCH_Y - BLOCK_D / 2, 0), 90.0, BLOCK_D))
    for label, origin, yaw, length in segments:
        spawn_street(actors, kit, label, origin, yaw, length)
        counts["lamps"] += street_lamps(actors, lamp_model, origin, yaw, length, label)
        counts["streets"] += 1

    # Kreuzungen + Ampeln (je Zufahrt rechts vor der Haltelinie, Querrichtung gegenphasig)
    for sx in (-1, 1):
        for sy in (-1, 1):
            center = unreal.Vector(sx * STREET_X, sy * STREET_Y, 0)
            crossing = actors.spawn_actor_from_object(kit["intersection"], center)
            vb.tag_actor(crossing, "Intersection_%d_%d" % (sx + 1, sy + 1), "Street/Intersections", prototype=False)
            if kit["signal"] and kit["signal_lens"]:
                for arm in range(4):
                    angle = math.radians(90.0 * arm)
                    lx, ly = 920.0, -700.0          # Arm-Koordinaten: Zufahrt kommt aus +X, rechte Seite = -Y
                    world = unreal.Vector(center.x + math.cos(angle) * lx - math.sin(angle) * ly,
                                          center.y + math.sin(angle) * lx + math.cos(angle) * ly, 15)
                    offset = 0.0 if arm % 2 == 0 else SIGNAL_CYCLE_OFFSET_CROSS
                    spawn_signal(actors, kit, "Signal_%d_%d_%d" % (sx + 1, sy + 1, arm), world, 90.0 * arm, offset)
                    counts["signals"] += 1
    return counts


def build_dev_map(instances):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    is_new = open_or_create_dev_map()
    clear_generated_actors(actors, remove_template_lighting=is_new)

    cube = unreal.load_asset("/Engine/BasicShapes/Cube")
    sphere = unreal.load_asset("/Engine/BasicShapes/Sphere")

    def box(label, folder, center, size_cm, material, yaw=0.0):
        actor = actors.spawn_actor_from_object(cube, unreal.Vector(*center), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        actor.set_actor_scale3d(unreal.Vector(size_cm[0] / 100.0, size_cm[1] / 100.0, size_cm[2] / 100.0))
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        component.set_material(0, material)
        vb.tag_actor(actor, label, folder)
        return actor

    # --- Himmel & Licht --------------------------------------------------------
    sky = actors.spawn_actor_from_class(unreal.VBSkyEnvironment, unreal.Vector(0, 0, 0))
    vb.tag_actor(sky, "VB_SkyEnvironment", "Lighting", prototype=False)

    # --- Phase 4: Kuestenbezirk (Gelaende, Meer, Ringstrasse, Promenade), falls importiert ---
    if vb_district.available():
        counts = vb_district.build(actors, instances, sphere)
        return counts["buildings"], counts["lamps"]

    # --- Boden ------------------------------------------------------------------
    box("Ground", "Dev/Greybox/Ground", (0, 0, -50), (40000, 40000, 100), instances["MI_VB_Dev_Ground"])

    # --- Phase 3: kompletter Stadtblock, falls Fassaden- und Kreuzungs-Kit importiert sind ---
    kit = {key: load_kit(path) for key, path in KIT.items()}
    styles = {letter: facade_style(letter) for letter in ("A", "B", "C")}
    styles = {k: v for k, v in styles.items() if v is not None}
    roof = load_kit(ROOF_TILE)
    if styles and roof and kit["intersection"] and kit["road"]:
        roof_props = [p for p in (load_kit(path) for path in ROOF_PROPS) if p is not None]
        counts = build_city_block(actors, kit, styles, roof, roof_props)
        # Kalibrierung + Tuer im Innenhof, Spielerstart auf dem suedlichen Gehweg
        for index, name in enumerate(["MI_VB_Calib_Grey18", "MI_VB_Calib_White80", "MI_VB_Calib_Black04", "MI_VB_Calib_Chrome"]):
            ball = actors.spawn_actor_from_object(sphere, unreal.Vector(-200 + index * 120, 0, 50))
            ball.get_component_by_class(unreal.StaticMeshComponent).set_material(0, instances[name])
            vb.tag_actor(ball, "Calibration_" + name.replace("MI_VB_Calib_", ""), "Dev/Calibration")
        start = actors.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(-1500, -STREET_Y + 800, 120),
                                              unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        vb.tag_actor(start, "PlayerStart", "Gameplay", prototype=False)
        vb_vehicles.populate(actors, [(-2400.0 + k * 720.0, -STREET_Y + 455.0, 0.0) for k in range(6)])
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        vb.log("Stadtblock: %(buildings)d Gebaeude, %(streets)d Strassen, %(lamps)d Laternen, %(signals)d Ampeln" % counts)
        return counts["buildings"], counts["lamps"]

    # --- Phase 2: Strasse aus dem Kit oder Graubox-Fallback --------------------
    use_kit = kit["road"] is not None and kit["curb"] is not None and kit["sidewalk"] is not None
    street_length = 12000.0 if use_kit else 30000.0
    if use_kit:
        build_kit_street(actors, kit, street_length)
    else:
        box("Road", "Dev/Greybox/Street", (0, 0, -4), (street_length, 1200, 10), instances["MI_VB_Dev_Asphalt"])
        for side in (-1, 1):
            box("Sidewalk_%s" % ("N" if side > 0 else "S"), "Dev/Greybox/Street",
                (0, side * 800, 7.5), (street_length, 400, 15), instances["MI_VB_Dev_Sidewalk"])

    # --- Gebaeude (Graubox bis Phase 3): Fassaden an der Gehweg-Hinterkante (9.78 m) ---
    rng = random.Random(7)
    facade_materials = ["MI_VB_Dev_Concrete", "MI_VB_Dev_PlasterWarm", "MI_VB_Dev_PlasterLight",
                        "MI_VB_Dev_Brick", "MI_VB_Dev_DarkFacade"]
    building_count = 0
    for side in (-1, 1):
        x = -street_length * 0.5 - 2000.0
        while x < street_length * 0.5 + 2000.0:
            width = rng.uniform(1400, 2800)
            height = rng.choice([900, 1200, 1500, 1800, 2400, 3200, 4500, 6000])
            depth = rng.uniform(1600, 2200)
            material = instances[rng.choice(facade_materials)]
            center_y = side * (BUILDING_LINE + depth * 0.5)
            box("Building_%s_%02d" % ("N" if side > 0 else "S", building_count), "Dev/Greybox/Buildings",
                (x + width * 0.5, center_y, height * 0.5), (width, depth, height), material)
            building_count += 1
            x += width + rng.choice([0, 0, 0, 150, 300])  # gelegentlich Gassen

    # --- Strassenlaternen alle 25 m, versetzt auf beiden Seiten -------------------
    # Finales Blender-Modell verwenden, falls importiert (sonst Prototyp-Grundformen)
    lamp_model = unreal.load_asset(STREETLIGHT_MODEL) if unreal.EditorAssetLibrary.does_asset_exist(STREETLIGHT_MODEL) else None
    lamp_count = 0
    for side in (-1, 1):
        x = -street_length * 0.5 + (1250.0 if side > 0 else 2500.0)
        while x < street_length * 0.5:
            yaw = -90.0 if side > 0 else 90.0  # Ausleger zeigt zur Fahrbahn
            lamp = actors.spawn_actor_from_class(unreal.VBStreetLight, unreal.Vector(x, side * 700, 15),
                                                 unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
            if lamp_model is not None:
                lamp.set_editor_property("model", lamp_model)
            else:
                for component in lamp.get_components_by_class(unreal.StaticMeshComponent):
                    component.set_material(0, instances["MI_VB_Dev_Metal"])
            vb.tag_actor(lamp, "StreetLight_%02d" % lamp_count, "Street/StreetLights", prototype=lamp_model is None)
            lamp_count += 1
            x += 2500.0

    # --- Beleuchtungs-Kalibrierung (18 % Grau, Weiss, Schwarz, Chrom) -------------
    for index, name in enumerate(["MI_VB_Calib_Grey18", "MI_VB_Calib_White80", "MI_VB_Calib_Black04", "MI_VB_Calib_Chrome"]):
        ball = actors.spawn_actor_from_object(sphere, unreal.Vector(-4200 + index * 120, -880, 65))
        ball.set_actor_scale3d(unreal.Vector(1.0, 1.0, 1.0))
        ball.get_component_by_class(unreal.StaticMeshComponent).set_material(0, instances[name])
        vb.tag_actor(ball, "Calibration_" + name.replace("MI_VB_Calib_", ""), "Dev/Calibration")

    # --- Interaktionstest: Tuer in freistehendem Rahmen ---------------------------
    frame_x, frame_y = -3600.0, -880.0
    box("DoorFrame_L", "Dev/Interaction", (frame_x, frame_y - 10, 125), (20, 20, 220), instances["MI_VB_Dev_Metal"])
    box("DoorFrame_R", "Dev/Interaction", (frame_x, frame_y + 105, 125), (20, 20, 220), instances["MI_VB_Dev_Metal"])
    box("DoorFrame_Top", "Dev/Interaction", (frame_x, frame_y + 47.5, 245), (20, 135, 20), instances["MI_VB_Dev_Metal"])
    door = actors.spawn_actor_from_class(unreal.VBDoor, unreal.Vector(frame_x, frame_y, 15))
    panel = door.get_component_by_class(unreal.StaticMeshComponent)
    if panel:
        panel.set_material(0, instances["MI_VB_Dev_PlasterWarm"])
    vb.tag_actor(door, "TestDoor", "Dev/Interaction")

    # --- Spielerstart auf dem Gehweg, Blick die Strasse entlang ---------------------
    start = actors.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(-1500, -800, 120))
    vb.tag_actor(start, "PlayerStart", "Gameplay", prototype=False)

    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    vb.log("Dev-Karte: %d Gebaeude, %d Laternen." % (building_count, lamp_count))
    return building_count, lamp_count


# ---------------------------------------------------------------------------
def run():
    steps = 7
    report = []
    with unreal.ScopedSlowTask(steps, "Veyra Bay: Projekt wird eingerichtet ...") as task:
        task.make_dialog(True)

        task.enter_progress_frame(1, "Ordnerstruktur")
        vb.ensure_folders()

        task.enter_progress_frame(1, "Standard-Texturen & Pfuetzenmaske")
        create_default_textures()

        task.enter_progress_frame(1, "Globale Material-Parameter (MPC_VB_World)")
        mpc = create_world_mpc()

        task.enter_progress_frame(1, "Master-Material & Instanzen")
        vb_import.import_surfaces(textures_only=True)  # Regenkraeusel-Textur wird vom Master-Material gebraucht
        master = build_master_material(mpc)
        instances = create_material_instances(master)
        build_window_material(mpc)
        vb_materials_nature.build_all(mpc)

        task.enter_progress_frame(1, "Blender-Assets importieren (SourceAssets/Export)")
        imported = vb_import.run(show_dialog=False)
        report.append("Blender-Assets importiert: %d" % len(imported))

        task.enter_progress_frame(1, "Spielfigur")
        mesh = configure_player()
        report.append("Spielfigur: " + (mesh or "NICHT gefunden (Third Person Pack hinzufuegen, dann Setup erneut starten)"))

        task.enter_progress_frame(1, "Entwicklungskarte L_VB_Dev")
        buildings, lamps = build_dev_map(instances)
        report.append("Karte: L_VB_Dev mit %d Test-Gebaeuden und %d Laternen" % (buildings, lamps))

    vb.show_message(
        "Veyra Bay - Setup fertig",
        "\n".join(report) + "\n\nJetzt 'Play' druecken (Alt+P).\n"
        "F3 = Infos, F5 = Wetter, F6/F7 = Uhrzeit, F2 = Performance.\n\n"
        "Der erste Start kompiliert Shader - das kann einige Minuten dauern.")
