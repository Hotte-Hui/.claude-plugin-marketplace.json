"""Phase-4-Materialien: Gelaende, Meer (Single Layer Water) und Vegetation (Foliage).

Werden von vb_setup.run() vor dem Asset-Import erzeugt, weil Gelaende/Meer/Baeume sie als gemeinsame
Materialien (MI_VB_Terrain, MI_VB_Ocean) bzw. als Eltern-Material (M_VB_Foliage) verwenden.
"""

import unreal

import vb_common as vb

MEL = unreal.MaterialEditingLibrary
TEX = vb.ROOT + "/Textures/Surfaces"
TERRAIN_MASTER = vb.ROOT + "/Materials/Master/M_VB_Terrain"
OCEAN_MASTER = vb.ROOT + "/Materials/Master/M_VB_Ocean"
FOLIAGE_MASTER = vb.ROOT + "/Materials/Master/M_VB_Foliage"

SEA_LEVEL_CM = -250.0
TERRAIN_EXTENT_CM = 80000.0            # muss zu vb_asset_coast.py passen (EXTENT 800 m)
HEIGHT_MIN_CM, HEIGHT_RANGE_CM = -3000.0, 6000.0


def _texture(surface, suffix):
    path = "%s/%s/T_VB_%s_%s" % (TEX, surface, surface, suffix)
    return unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None


def _new_material(path):
    material, created = vb.load_or_create(path, unreal.Material, unreal.MaterialFactoryNew())
    if not created:
        MEL.delete_all_material_expressions(material)
    for usage_name in ("MATL_NANITE", "MATL_INSTANCED_STATIC_MESHES"):
        usage = getattr(unreal.MaterialUsage, usage_name, None)
        if usage is not None:
            try:
                MEL.set_material_usage(material, usage)
            except Exception:  # noqa: BLE001
                pass
    return material


def _finish(material, graph, shared_name=None):
    MEL.recompile_material(material)
    vb.save_asset(material)
    if graph.failed_links:
        vb.warn("%s: %d Verbindungen fehlgeschlagen." % (material.get_name(), graph.failed_links))
    if shared_name:
        mi, _ = vb.load_or_create(vb.shared_material_path(shared_name), unreal.MaterialInstanceConstant,
                                  unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, material)
        MEL.update_material_instance(mi)
        vb.save_asset(mi)
        return mi
    return material


# ---------------------------------------------------------------------------
# Gelaende
# ---------------------------------------------------------------------------
def build_terrain_material(mpc):
    """Sand (unter 1.5 m ueber dem Meer), Gras (flach), Fels (steil, seitlich projiziert). Weltkoordinaten-UVs."""
    surfaces = {name: {s: _texture(name, s) for s in ("D", "N", "ORM")} for name in ("Sand", "Grass", "Rock")}
    if any(tex is None for maps in surfaces.values() for tex in maps.values()):
        vb.warn("Gelaende-Texturen fehlen (Sand/Grass/Rock) - M_VB_Terrain wird nicht gebaut.")
        return None

    material = _new_material(TERRAIN_MASTER)
    g = vb.MaterialGraph(material)
    sampler = unreal.MaterialSamplerType
    world = g.node(unreal.MaterialExpressionWorldPosition, -2600, 0)
    world_xy = g.mask(world, "rg", -2450, 0)
    world_xz = g.mask(world, "rb", -2450, 120)
    world_yz = g.mask(world, "gb", -2450, 240)
    height = g.mask(world, "b", -2450, 360)
    normal = g.node(unreal.MaterialExpressionVertexNormalWS, -2600, 500)
    up = g.mask(normal, "b", -2450, 500)
    nx = g.unary(unreal.MaterialExpressionAbs, g.mask(normal, "r", -2450, 600), -2300, 600)
    ny = g.unary(unreal.MaterialExpressionAbs, g.mask(normal, "g", -2450, 680), -2300, 680)

    tiles = {"Sand": 300.0, "Grass": 300.0, "Rock": 400.0}
    samples = {}
    y = -900
    for name in ("Sand", "Grass"):
        uv = g.op(unreal.MaterialExpressionDivide, world_xy, tiles[name], -2200, y)
        samples[name] = {
            "D": g.texture(surfaces[name]["D"], uv, -1900, y, sampler.SAMPLERTYPE_COLOR),
            "N": g.texture(surfaces[name]["N"], uv, -1900, y + 150, sampler.SAMPLERTYPE_NORMAL),
            "ORM": g.texture(surfaces[name]["ORM"], uv, -1900, y + 300, sampler.SAMPLERTYPE_MASKS),
        }
        y += 500
    # Fels: seitliche Projektion (XZ oder YZ, je nach dominanter Normalen-Achse) gegen Verzerrung an Steilhaengen
    choose = g.node(unreal.MaterialExpressionIf, -2200, y)
    g.link(nx, "", choose, "A")
    g.link(ny, "", choose, "B")
    g.link_any(world_yz, "", choose, ["A > B", "AGreaterThanB"])
    g.link_any(world_yz, "", choose, ["A == B", "AEqualsB"])
    g.link_any(world_xz, "", choose, ["A < B", "ALessThanB"])
    rock_uv = g.op(unreal.MaterialExpressionDivide, choose, tiles["Rock"], -2050, y)
    samples["Rock"] = {
        "D": g.texture(surfaces["Rock"]["D"], rock_uv, -1900, y, sampler.SAMPLERTYPE_COLOR),
        "N": g.texture(surfaces["Rock"]["N"], rock_uv, -1900, y + 150, sampler.SAMPLERTYPE_NORMAL),
        "ORM": g.texture(surfaces["Rock"]["ORM"], rock_uv, -1900, y + 300, sampler.SAMPLERTYPE_MASKS),
    }

    # Gewichte
    noise_tex = unreal.load_asset(vb.ROOT + "/Textures/Default/T_VB_PuddleMask_M")
    noise_uv = g.op(unreal.MaterialExpressionDivide, world_xy, 1500.0, -2200, 900)
    noise = g.texture(noise_tex, noise_uv, -2050, 900, sampler.SAMPLERTYPE_MASKS)
    sand_line = g.scalar("SandTopCm", -100.0, -2050, 1050, group="Terrain")
    jitter = g.op(unreal.MaterialExpressionMultiply, noise, 160.0, -1900, 950, a_out="R")
    h_jit = g.op(unreal.MaterialExpressionAdd, height, jitter, -1750, 950)
    h_rel = g.op(unreal.MaterialExpressionSubtract, h_jit, sand_line, -1600, 950)
    sand_w = g.unary(unreal.MaterialExpressionSaturate, g.op(unreal.MaterialExpressionDivide, h_rel, -60.0, -1450, 950), -1300, 950)
    rock_steep = g.op(unreal.MaterialExpressionSubtract, up, 0.82, -2300, 800)
    rock_w = g.unary(unreal.MaterialExpressionSaturate, g.op(unreal.MaterialExpressionMultiply, rock_steep, -7.0, -2150, 800), -2000, 800)

    def blend(key, output, x):
        ground = g.lerp(samples["Grass"][key], samples["Sand"][key], sand_w, x, -200, a_out=output, b_out=output)
        return g.lerp(ground, samples["Rock"][key], rock_w, x + 150, -200, b_out=output)

    color = blend("D", "RGB", -1100)
    orm = blend("ORM", "RGB", -1100)
    normal_out = blend("N", "RGB", -1100)

    # Grossflaechige Variation + Naesse
    macro = g.op(unreal.MaterialExpressionAdd, g.op(unreal.MaterialExpressionMultiply, noise, 0.35, -900, 900, a_out="G"), 0.82, -750, 900)
    color_macro = g.op(unreal.MaterialExpressionMultiply, color, macro, -700, -200)
    wet = g.mpc(mpc, "Wetness", -900, 1100)
    darken = g.lerp(1.0, 0.6, wet, -700, 1100)
    color_final = g.op(unreal.MaterialExpressionMultiply, color_macro, darken, -500, -200)
    roughness = g.lerp(g.mask(orm, "g", -700, 100), 0.35, wet, -500, 100)

    g.output(color_final, "", unreal.MaterialProperty.MP_BASE_COLOR)
    g.output(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
    g.output(normal_out, "", unreal.MaterialProperty.MP_NORMAL)
    g.output(g.mask(orm, "r", -700, 200), "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    return _finish(material, g, "Terrain")


# ---------------------------------------------------------------------------
# Meer
# ---------------------------------------------------------------------------
def build_ocean_material(mpc):
    normal_tex = _texture("Ocean", "N")
    foam_tex = _texture("Ocean", "M") or unreal.load_asset("%s/Ocean/T_VB_OceanFoam_M" % TEX)
    height_tex = unreal.load_asset("%s/Terrain/T_VB_TerrainHeight_H" % TEX)
    if normal_tex is None:
        vb.warn("Ozean-Texturen fehlen - M_VB_Ocean wird nicht gebaut.")
        return None

    material = _new_material(OCEAN_MASTER)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_SINGLE_LAYER_WATER)
    g = vb.MaterialGraph(material)
    sampler = unreal.MaterialSamplerType
    world = g.node(unreal.MaterialExpressionWorldPosition, -2400, 0)
    world_xy = g.mask(world, "rg", -2250, 0)
    time = g.node(unreal.MaterialExpressionTime, -2400, 200)
    wind = g.mpc(mpc, "WindStrength", -2400, 300)

    def wave_layer(size, pan, y):
        uv = g.op(unreal.MaterialExpressionDivide, world_xy, size, -2100, y)
        pan_node = g.node(unreal.MaterialExpressionConstant2Vector, -2100, y + 80, r=pan[0], g=pan[1])
        offset = g.op(unreal.MaterialExpressionMultiply, time, pan_node, -1950, y + 60)
        moved = g.op(unreal.MaterialExpressionAdd, uv, offset, -1800, y)
        return g.texture(normal_tex, moved, -1650, y, sampler.SAMPLERTYPE_NORMAL)

    n1 = wave_layer(4000.0, (0.010, 0.004), -300)
    n2 = wave_layer(1300.0, (-0.007, 0.012), -50)
    xy = g.op(unreal.MaterialExpressionAdd, g.mask(n1, "rg", -1500, -300, source_out="RGB"),
              g.mask(n2, "rg", -1500, -50, source_out="RGB"), -1350, -200)
    combined = g.op(unreal.MaterialExpressionAppendVector, xy, g.mask(n1, "b", -1500, 50, source_out="RGB"), -1200, -200)
    normal = g.unary(unreal.MaterialExpressionNormalize, combined, -1050, -200)
    flat = g.node(unreal.MaterialExpressionConstant3Vector, -1050, -100, constant=unreal.LinearColor(0, 0, 1, 0))
    strength = g.op(unreal.MaterialExpressionAdd, g.op(unreal.MaterialExpressionMultiply, wind, 0.65, -1200, 300), 0.35, -1050, 300)
    depth_fade = g.unary(unreal.MaterialExpressionSaturate,
                         g.op(unreal.MaterialExpressionDivide, g.node(unreal.MaterialExpressionPixelDepth, -1200, 400), 60000.0, -1050, 400),
                         -900, 400)
    strength_far = g.op(unreal.MaterialExpressionMultiply, strength, g.lerp(1.0, 0.3, depth_fade, -800, 400), -700, 300)
    normal_final = g.lerp(flat, normal, strength_far, -600, -200)

    # Kuestenschaum aus der Gelaende-Hoehenkarte (Wassertiefe < ~1.2 m)
    foam = None
    if height_tex is not None and foam_tex is not None:
        # Als Parameter, damit die grosse Stadtkarte (Phase 7) eine eigene Hoehenkarte nutzen kann (MI_VB_OceanCity)
        extent = g.scalar("TerrainExtentCm", TERRAIN_EXTENT_CM, -2400, 600, group="Shore")
        height_min = g.scalar("HeightMinCm", HEIGHT_MIN_CM, -1800, 760, group="Shore")
        height_range = g.scalar("HeightRangeCm", HEIGHT_RANGE_CM, -1800, 680, group="Shore")
        terrain_uv = g.op(unreal.MaterialExpressionDivide, g.op(unreal.MaterialExpressionAdd, world_xy, extent, -2100, 600),
                          g.op(unreal.MaterialExpressionMultiply, extent, 2.0, -2250, 680), -1950, 600)
        terrain_h = g.node(unreal.MaterialExpressionTextureSampleParameter2D, -1800, 600, parameter_name="TerrainHeightMap",
                           texture=height_tex, sampler_type=sampler.SAMPLERTYPE_LINEAR_GRAYSCALE, group="Shore")
        g.link(terrain_uv, "", terrain_h, "UVs")
        ground = g.op(unreal.MaterialExpressionAdd, g.op(unreal.MaterialExpressionMultiply, terrain_h, height_range, -1650, 600, a_out="R"),
                      height_min, -1500, 600)
        water_depth = g.op(unreal.MaterialExpressionSubtract, g.node(unreal.MaterialExpressionConstant, -1500, 700, r=SEA_LEVEL_CM), ground,
                           -1350, 650)
        shallow = g.unary(unreal.MaterialExpressionSaturate, g.op(unreal.MaterialExpressionDivide, water_depth, 120.0, -1200, 650),
                          -1050, 650)
        shore = g.unary(unreal.MaterialExpressionOneMinus, shallow, -900, 650)
        foam_uv = g.op(unreal.MaterialExpressionAdd, g.op(unreal.MaterialExpressionDivide, world_xy, 700.0, -1350, 800),
                       g.op(unreal.MaterialExpressionMultiply, time, g.node(unreal.MaterialExpressionConstant2Vector, -1350, 900, r=0.02, g=0.03),
                            -1200, 880), -1050, 800)
        foam_sample = g.texture(foam_tex, foam_uv, -900, 800, sampler.SAMPLERTYPE_MASKS)
        foam = g.unary(unreal.MaterialExpressionSaturate,
                       g.op(unreal.MaterialExpressionMultiply, shore, foam_sample, -750, 700, b_out="R"), -600, 700)

    water_color = g.node(unreal.MaterialExpressionVectorParameter, -600, -500, parameter_name="SurfaceColor",
                         default_value=unreal.LinearColor(0.015, 0.035, 0.04, 1.0), group="Water")
    if foam is not None:
        base = g.lerp(water_color, g.node(unreal.MaterialExpressionConstant3Vector, -600, -400,
                                          constant=unreal.LinearColor(0.8, 0.82, 0.82, 0)), foam, -400, -450)
        rough = g.lerp(0.03, 0.6, foam, -400, -300)
        g.output(foam, "", unreal.MaterialProperty.MP_OPACITY)
    else:
        base, rough = water_color, g.node(unreal.MaterialExpressionConstant, -400, -300, r=0.03)
    g.output(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    g.output(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    g.output(g.node(unreal.MaterialExpressionConstant, -400, -200, r=0.255), "", unreal.MaterialProperty.MP_SPECULAR)
    g.output(normal_final, "", unreal.MaterialProperty.MP_NORMAL)

    # Volumen-Eigenschaften des Wassers (pro cm): kuestennahes, leicht gruenliches Wasser
    output_class = getattr(unreal, "MaterialExpressionSingleLayerWaterMaterialOutput", None)
    if output_class is not None:
        out = g.node(output_class, 0, 400)
        scattering = g.node(unreal.MaterialExpressionVectorParameter, -400, 400, parameter_name="ScatteringCoefficients",
                            default_value=unreal.LinearColor(0.0003, 0.0009, 0.0008, 1.0), group="Water")
        absorption = g.node(unreal.MaterialExpressionVectorParameter, -400, 520, parameter_name="AbsorptionCoefficients",
                            default_value=unreal.LinearColor(0.0045, 0.0009, 0.0005, 1.0), group="Water")
        phase = g.scalar("PhaseG", 0.2, -400, 640, group="Water")
        g.link_any(scattering, "", out, ["ScatteringCoefficients", "Scattering Coefficients", "Scattering Coefficients (Albedo)"])
        g.link_any(absorption, "", out, ["AbsorptionCoefficients", "Absorption Coefficients"])
        g.link_any(phase, "", out, ["PhaseG", "Phase G"])
    else:
        vb.warn("SingleLayerWaterMaterialOutput nicht gefunden - Wasser ohne Volumenparameter.")
    return _finish(material, g, "Ocean")


# ---------------------------------------------------------------------------
# Vegetation
# ---------------------------------------------------------------------------
def build_foliage_material(mpc):
    """M_VB_Foliage: maskiert, zweiseitig (TwoSidedFoliage), Wind-Schwingung nach Hoehe (MPC WindStrength)."""
    material = _new_material(FOLIAGE_MASTER)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    material.set_editor_property("two_sided", True)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
    try:
        material.set_editor_property("opacity_mask_clip_value", 0.35)
    except Exception:  # noqa: BLE001
        pass
    g = vb.MaterialGraph(material)
    sampler = unreal.MaterialSamplerType
    white = unreal.load_asset(vb.ROOT + "/Textures/Default/T_VB_Default_D")
    uv = g.node(unreal.MaterialExpressionTextureCoordinate, -1600, 0)
    tex = g.node(unreal.MaterialExpressionTextureSampleParameter2D, -1400, 0, parameter_name="BaseColorMap", texture=white,
                 sampler_type=sampler.SAMPLERTYPE_COLOR, group="Foliage")
    g.link(uv, "", tex, "UVs")
    tint = g.node(unreal.MaterialExpressionVectorParameter, -1400, -200, parameter_name="BaseColorTint",
                  default_value=unreal.LinearColor(1, 1, 1, 1), group="Foliage")
    rand = g.node(unreal.MaterialExpressionPerInstanceRandom, -1400, 250)
    variation = g.lerp(0.85, 1.15, rand, -1200, 250)
    color = g.op(unreal.MaterialExpressionMultiply, g.op(unreal.MaterialExpressionMultiply, tex, tint, -1200, 0, a_out="RGB"),
                 variation, -1050, 0)
    wet = g.mpc(mpc, "Wetness", -1200, 350)
    color = g.op(unreal.MaterialExpressionMultiply, color, g.lerp(1.0, 0.75, wet, -1050, 350), -900, 0)
    g.output(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    g.output(g.op(unreal.MaterialExpressionMultiply, color, 0.7, -750, 100), "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    g.output(tex, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
    g.output(g.lerp(0.55, 0.25, wet, -750, 200), "", unreal.MaterialProperty.MP_ROUGHNESS)

    # Wind: Schwingung waechst quadratisch mit der Hoehe ueber dem Pivot
    local_class = getattr(unreal, "MaterialExpressionLocalPosition", None)
    if local_class is not None:
        local = g.node(local_class, -1600, 600)
        tree_height = g.scalar("SwayHeightCm", 900.0, -1600, 700, group="Wind")
        hf = g.unary(unreal.MaterialExpressionSaturate, g.op(unreal.MaterialExpressionDivide, g.mask(local, "b", -1450, 600), tree_height,
                                                          -1300, 650), -1150, 650)
        hf2 = g.op(unreal.MaterialExpressionMultiply, hf, hf, -1000, 650)
        time = g.node(unreal.MaterialExpressionTime, -1600, 800)
        speed = g.op(unreal.MaterialExpressionAdd, g.op(unreal.MaterialExpressionMultiply, rand, 0.4, -1450, 850), 0.9, -1300, 850)
        phase = g.op(unreal.MaterialExpressionAdd, g.op(unreal.MaterialExpressionMultiply, time, speed, -1150, 800),
                     g.op(unreal.MaterialExpressionMultiply, rand, 6.28, -1150, 900), -1000, 820)
        sway = g.unary(unreal.MaterialExpressionSine, phase, -850, 820)
        wind = g.mpc(mpc, "WindStrength", -1000, 950)
        amplitude = g.op(unreal.MaterialExpressionAdd, g.op(unreal.MaterialExpressionMultiply, wind, 30.0, -850, 950), 3.0, -700, 950)
        magnitude = g.op(unreal.MaterialExpressionMultiply, g.op(unreal.MaterialExpressionMultiply, sway, amplitude, -700, 820), hf2,
                         -550, 750)
        direction = g.mpc(mpc, "WindDirection", -850, 1050)
        dir3 = g.op(unreal.MaterialExpressionAppendVector, g.mask(direction, "rg", -700, 1050),
                    g.node(unreal.MaterialExpressionConstant, -700, 1150, r=0.0), -550, 1050)
        offset = g.op(unreal.MaterialExpressionMultiply, dir3, magnitude, -400, 900)
        g.output(offset, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    return _finish(material, g)


def build_all(mpc):
    results = {}
    for name, builder in (("Terrain", build_terrain_material), ("Ocean", build_ocean_material), ("Foliage", build_foliage_material)):
        try:
            results[name] = builder(mpc)
        except Exception as exc:  # noqa: BLE001 - ein Material darf die anderen nicht verhindern
            vb.error("%s-Material: %s" % (name, exc))
            results[name] = None
    return results
