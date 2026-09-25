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

import os
import random

import unreal

import vb_common as vb
import vb_import

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
class MaterialGraph:
    """Kleiner Helfer, um Material-Graphen lesbar per Python aufzubauen."""

    def __init__(self, material):
        self.material = material
        self.failed_links = 0

    def node(self, expression_class, x, y, **props):
        expression = MEL.create_material_expression(self.material, expression_class, x, y)
        for key, value in props.items():
            expression.set_editor_property(key, value)
        return expression

    def scalar(self, name, default, x, y, group="Surface"):
        return self.node(unreal.MaterialExpressionScalarParameter, x, y,
                         parameter_name=name, default_value=default, group=group)

    def link(self, source, source_output, target, target_input):
        if not MEL.connect_material_expressions(source, source_output, target, target_input):
            self.failed_links += 1
            vb.warn("Verbindung fehlgeschlagen: %s.%s -> %s.%s" % (
                source.get_class().get_name(), source_output, target.get_class().get_name(), target_input))

    def output(self, source, source_output, material_property):
        if not MEL.connect_material_property(source, source_output, material_property):
            self.failed_links += 1
            vb.warn("Ausgang fehlgeschlagen: %s -> %s" % (source.get_class().get_name(), material_property))

    def mpc(self, collection, name, x, y):
        expression = self.node(unreal.MaterialExpressionCollectionParameter, x, y)
        expression.set_editor_property("collection", collection)
        expression.set_editor_property("parameter_name", name)
        return expression


def build_master_material(mpc):
    """M_VB_Surface: PBR (BaseColor/Normal/ORM) + globale Naesse + Pfuetzen aus der MPC."""
    material, created = vb.load_or_create(vb.MASTER_SURFACE, unreal.Material, unreal.MaterialFactoryNew())
    if not created:
        MEL.delete_all_material_expressions(material)

    for usage_name in ("MATL_NANITE", "MATL_INSTANCED_STATIC_MESHES"):
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
    base_color = g.node(unreal.MaterialExpressionMultiply, -1450, -450)
    g.link(base_tex, "RGB", base_color, "A")
    g.link(tint, "", base_color, "B")

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
    switch = g.node(unreal.MaterialExpressionLinearInterpolate, -450, 1850, const_a=1.0)
    g.link(light_on, "", switch, "B")
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
    builder.set_editor_property("props", rules)
    vb.tag_actor(builder, "Street_Main", "Street", prototype=False)

    # Ampeln am Zebrastreifen (Welt-X 0..10 m): je Fahrtrichtung rechts, vor der Haltelinie
    if kit["signal"] and kit["signal_lens"]:
        crossing_x = origin_x + crosswalk_index * 1000.0
        for label, x, y, yaw in (("TrafficLight_East", crossing_x + 100, 700, 180.0),
                                 ("TrafficLight_West", crossing_x + 900, -700, 0.0)):
            signal = actors.spawn_actor_from_class(unreal.VBTrafficLight, unreal.Vector(x, y, 15),
                                                   unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
            signal.set_editor_property("model", kit["signal"])
            signal.set_editor_property("lens_model", kit["signal_lens"])
            vb.tag_actor(signal, label, "Street/TrafficLights", prototype=False)
    return builder


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

    # --- Boden ------------------------------------------------------------------
    box("Ground", "Dev/Greybox/Ground", (0, 0, -50), (40000, 40000, 100), instances["MI_VB_Dev_Ground"])

    # --- Strasse: finales Kit (Phase 2) oder Graubox-Fallback --------------------
    kit = {key: load_kit(path) for key, path in KIT.items()}
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
