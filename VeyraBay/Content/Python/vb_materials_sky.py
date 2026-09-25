"""Phase-6-Materialien: volumetrische Wolken, Regenschlieren, Sternenhimmel.

M_VB_Clouds  Volume-Material fuer die Volumetric-Cloud-Komponente: Bedeckung, Wind und Gewitterleuchten aus der
             MPC (CloudCoverage, WindDirection/WindStrength, LightningFlash). Schoenwetter = flache Haufenwolken,
             hohe Bedeckung = geschlossene, hoch aufragende Decke.
M_VB_Rain    Durchscheinende, beleuchtete Regenschlieren fuer die drei Regenzylinder um die Kamera (AVBSkyEnvironment),
             Deckkraft folgt RainIntensity; Straßenlaternen beleuchten den Regen (Translucency Lighting Volume).
M_VB_Stars   Additiver Sternenhimmel auf der Himmelskuppel; wird von Wolken und Nebel verdeckt.
"""

import unreal

import vb_common as vb

MEL = unreal.MaterialEditingLibrary
SKY = vb.ROOT + "/Materials/Sky"
TEX = vb.ROOT + "/Textures/Surfaces/Sky"
CLOUDS = SKY + "/M_VB_Clouds"
RAIN = SKY + "/M_VB_Rain"
STARS = SKY + "/M_VB_Stars"
MP = unreal.MaterialProperty


def _material(path):
    material, created = vb.load_or_create(path, unreal.Material, unreal.MaterialFactoryNew())
    if not created:
        MEL.delete_all_material_expressions(material)
    return material


def _set(material, **props):
    for key, value in props.items():
        try:
            material.set_editor_property(key, value)
        except Exception as exc:  # noqa: BLE001 - Eigenschaft je nach Engine-Version anders benannt
            vb.warn("%s: Eigenschaft %s nicht gesetzt (%s)" % (material.get_name(), key, exc))


def _finish(material, graph):
    MEL.recompile_material(material)
    vb.save_asset(material)
    if graph.failed_links:
        vb.warn("%s: %d Verbindungen fehlgeschlagen." % (material.get_name(), graph.failed_links))
    return material


def _texture(name):
    path = "%s/%s" % (TEX, name)
    return unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None


def _noise_function():
    names = ("NOISEFUNCTION_GRADIENT_TEX3D", "NOISEFUNCTION_GRADIENT_TEX", "NOISEFUNCTION_SIMPLEX_TEX")
    for name in names:
        value = getattr(unreal.NoiseFunction, name, None)
        if value is not None:
            return value
    return None


def _noise(g, position, scale, levels, x, y):
    props = dict(scale=scale, levels=levels, output_min=0.0, output_max=1.0, turbulence=False, quality=1)
    function = _noise_function()
    if function is not None:
        props["noise_function"] = function
    node = g.node(unreal.MaterialExpressionNoise, x, y)
    for key, value in props.items():
        try:
            node.set_editor_property(key, value)
        except Exception:  # noqa: BLE001
            pass
    g.link(position, "", node, "Position")
    return node


def _const(g, value, x, y):
    return g.node(unreal.MaterialExpressionConstant, x, y, r=value)


# ---------------------------------------------------------------------------
# Wolken
# ---------------------------------------------------------------------------
def build_clouds(mpc):
    material = _material(CLOUDS)
    _set(material, material_domain=unreal.MaterialDomain.MD_VOLUME, blend_mode=unreal.BlendMode.BLEND_ADDITIVE)
    g = vb.MaterialGraph(material)
    op = g.op

    world = g.node(unreal.MaterialExpressionWorldPosition, -2400, 0)
    meters = op(unreal.MaterialExpressionDivide, world, 100.0, x=-2200, y=0)

    # Wind: Wolken ziehen mit 4..24 m/s in Windrichtung
    wind_dir = g.mask(g.mpc(mpc, "WindDirection", -2400, 200), "rg", -2200, 200)
    wind_strength = g.mpc(mpc, "WindStrength", -2400, 300)
    speed = op(unreal.MaterialExpressionAdd, op(unreal.MaterialExpressionMultiply, wind_strength, 20.0, x=-2200, y=300),
               4.0, x=-2050, y=300)
    time = g.node(unreal.MaterialExpressionTime, -2400, 400)
    drift = op(unreal.MaterialExpressionMultiply, op(unreal.MaterialExpressionMultiply, wind_dir, speed, x=-1900, y=220),
               time, x=-1750, y=260)
    drift3 = g.node(unreal.MaterialExpressionAppendVector, -1600, 260)
    g.link(drift, "", drift3, "A")
    g.link(_const(g, 0.0, -1750, 360), "", drift3, "B")
    position = op(unreal.MaterialExpressionSubtract, meters, drift3, x=-1450, y=100)

    base = _noise(g, position, 1.0 / 4500.0, 4, -1250, 0)
    detail = _noise(g, position, 1.0 / 420.0, 3, -1250, 300)

    # Bedeckung: Schwelle sinkt mit CloudCoverage
    coverage = g.mpc(mpc, "CloudCoverage", -1450, 500)
    threshold = g.unary(unreal.MaterialExpressionOneMinus, op(unreal.MaterialExpressionMultiply, coverage, 0.95, x=-1250, y=500),
                        -1100, 500)
    shape = g.unary(unreal.MaterialExpressionSaturate,
                    op(unreal.MaterialExpressionMultiply, op(unreal.MaterialExpressionSubtract, base, threshold, x=-950, y=40),
                       4.0, x=-800, y=40), -650, 40)

    # Hoehenprofil in der Schicht (Parameter passend zu AVBSkyEnvironment::CloudBottomKm / CloudLayerHeightKm)
    bottom = g.scalar("CloudBottomKm", 1.5, -1450, 700, group="Clouds")
    height = g.scalar("CloudHeightKm", 6.0, -1450, 800, group="Clouds")
    altitude_km = op(unreal.MaterialExpressionDivide, g.mask(world, "b", -2200, 700), 100000.0, x=-1250, y=650)
    norm_alt = g.unary(unreal.MaterialExpressionSaturate,
                       op(unreal.MaterialExpressionDivide, op(unreal.MaterialExpressionSubtract, altitude_km, bottom, x=-1100, y=700),
                          height, x=-950, y=700), -800, 700)
    top = g.lerp(0.3, 1.0, coverage, x=-950, y=850)
    top_local = op(unreal.MaterialExpressionMultiply, top, shape, x=-800, y=850)
    lower = g.unary(unreal.MaterialExpressionSaturate, op(unreal.MaterialExpressionMultiply, norm_alt, 6.0, x=-650, y=700), -500, 700)
    upper = g.unary(unreal.MaterialExpressionSaturate,
                    op(unreal.MaterialExpressionMultiply, op(unreal.MaterialExpressionSubtract, top_local, norm_alt, x=-650, y=850),
                       5.0, x=-500, y=850), -350, 850)
    profile = op(unreal.MaterialExpressionMultiply, lower, upper, x=-200, y=750)

    density = g.unary(unreal.MaterialExpressionSaturate,
                      op(unreal.MaterialExpressionSubtract,
                         op(unreal.MaterialExpressionMultiply, op(unreal.MaterialExpressionMultiply, shape, profile, x=-350, y=200),
                            1.5, x=-200, y=200),
                         op(unreal.MaterialExpressionMultiply, detail, 0.4, x=-950, y=320), x=-50, y=250), 100, 250)

    extinction_scale = g.scalar("CloudExtinction", 0.05, 100, 400, group="Clouds")
    extinction = op(unreal.MaterialExpressionMultiply, density, extinction_scale, x=300, y=300)
    albedo = g.node(unreal.MaterialExpressionConstant3Vector, 300, 0, constant=unreal.LinearColor(0.95, 0.95, 0.96, 1.0))

    # Gewitter: Wolken leuchten beim Blitz von innen
    flash = g.mpc(mpc, "LightningFlash", 100, 550)
    glow = op(unreal.MaterialExpressionMultiply, op(unreal.MaterialExpressionMultiply, density, flash, x=300, y=550),
              g.scalar("LightningGlow", 40.0, 100, 650, group="Clouds"), x=450, y=550)

    g.output(albedo, "", MP.MP_BASE_COLOR)
    g.output(extinction, "", MP.MP_SUBSURFACE_COLOR)      # Volume-Domain: "Extinction"
    g.output(glow, "", MP.MP_EMISSIVE_COLOR)
    return _finish(material, g)


# ---------------------------------------------------------------------------
# Regen
# ---------------------------------------------------------------------------
def build_rain(mpc):
    streaks = _texture("T_VB_RainStreaks_M")
    if streaks is None:
        vb.warn("T_VB_RainStreaks_M fehlt (Blender: vb_sky_textures.py) - M_VB_Rain wird nicht gebaut.")
        return None
    material = _material(RAIN)
    _set(material, blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT, shading_model=unreal.MaterialShadingModel.MSM_DEFAULT_LIT,
         two_sided=True)
    try:
        material.set_editor_property("translucency_lighting_mode",
                                     unreal.TranslucencyLightingMode.TLM_VOLUMETRIC_NON_DIRECTIONAL)
    except Exception:  # noqa: BLE001
        pass
    g = vb.MaterialGraph(material)
    op = g.op

    uv = g.node(unreal.MaterialExpressionTextureCoordinate, -1800, 0)
    tiling = g.node(unreal.MaterialExpressionAppendVector, -1600, 120)
    g.link(g.scalar("TilingU", 6.0, -1800, 100, group="Rain"), "", tiling, "A")
    g.link(g.scalar("TilingV", 2.0, -1800, 200, group="Rain"), "", tiling, "B")
    fall = op(unreal.MaterialExpressionMultiply, g.node(unreal.MaterialExpressionTime, -1800, 300),
              g.scalar("FallSpeed", 1.5, -1800, 380, group="Rain"), x=-1600, y=320)
    pan = g.node(unreal.MaterialExpressionAppendVector, -1450, 320)
    g.link(_const(g, 0.0, -1600, 420), "", pan, "A")
    g.link(fall, "", pan, "B")
    uv_a = op(unreal.MaterialExpressionAdd, op(unreal.MaterialExpressionMultiply, uv, tiling, x=-1450, y=60), pan, x=-1300, y=100)
    # Zweite Ebene: dichter, langsamer, versetzt
    uv_b = op(unreal.MaterialExpressionAdd, op(unreal.MaterialExpressionMultiply, uv_a, 1.7, x=-1150, y=260), 0.37, x=-1000, y=260)

    sample_a = g.texture(streaks, uv_a, -1100, 0, sampler=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    sample_b = g.texture(streaks, uv_b, -850, 260, sampler=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    streak = op(unreal.MaterialExpressionAdd, g.mask(sample_a, "r", -800, 0),
                op(unreal.MaterialExpressionMultiply, g.mask(sample_b, "g", -600, 260), 0.6, x=-450, y=260), x=-300, y=80)

    # Weich ausblenden: oben/unten am Zylinder und an Geometrie
    v = g.mask(uv, "g", -1600, 600)
    edge = g.node(unreal.MaterialExpressionSine, -1450, 600, period=2.0)
    g.link(v, "", edge, "")
    depth = g.node(unreal.MaterialExpressionDepthFade, -1450, 750)
    try:
        depth.set_editor_property("fade_distance_default", 120.0)
    except Exception:  # noqa: BLE001
        pass
    rain = g.mpc(mpc, "RainIntensity", -1450, 900)
    fades = op(unreal.MaterialExpressionMultiply, op(unreal.MaterialExpressionMultiply, edge, depth, x=-1250, y=680),
               rain, x=-1100, y=760)
    opacity = g.unary(unreal.MaterialExpressionSaturate,
                      op(unreal.MaterialExpressionMultiply, op(unreal.MaterialExpressionMultiply, streak, fades, x=-150, y=300),
                         g.scalar("OpacityScale", 0.5, -300, 450, group="Rain"), x=0, y=350), 150, 350)

    g.output(g.node(unreal.MaterialExpressionConstant3Vector, 150, 0, constant=unreal.LinearColor(0.55, 0.58, 0.62, 1.0)), "",
             MP.MP_BASE_COLOR)
    g.output(_const(g, 0.15, 150, 120), "", MP.MP_ROUGHNESS)
    g.output(opacity, "", MP.MP_OPACITY)
    return _finish(material, g)


# ---------------------------------------------------------------------------
# Sterne
# ---------------------------------------------------------------------------
def build_stars(mpc):
    star_map = _texture("T_VB_Sky_D")
    if star_map is None:
        vb.warn("T_VB_Sky_D fehlt (Blender: vb_sky_textures.py) - M_VB_Stars wird nicht gebaut.")
        return None
    material = _material(STARS)
    _set(material, blend_mode=unreal.BlendMode.BLEND_ADDITIVE, shading_model=unreal.MaterialShadingModel.MSM_UNLIT,
         two_sided=True)
    for key in ("use_translucency_vertex_fog", "apply_cloud_fogging"):
        try:
            material.set_editor_property(key, True)
        except Exception:  # noqa: BLE001
            pass
    g = vb.MaterialGraph(material)
    op = g.op
    uv = g.node(unreal.MaterialExpressionTextureCoordinate, -1200, 0)
    sample = g.texture(star_map, uv, -1000, 0)
    night = g.mpc(mpc, "NightFactor", -1200, 300)
    visible = g.unary(unreal.MaterialExpressionSaturate,
                      op(unreal.MaterialExpressionMultiply, op(unreal.MaterialExpressionSubtract, night, 0.4, x=-1000, y=300),
                         2.5, x=-850, y=300), -700, 300)
    coverage = g.mpc(mpc, "CloudCoverage", -1200, 450)
    clear = g.unary(unreal.MaterialExpressionOneMinus, op(unreal.MaterialExpressionMultiply, coverage, 0.85, x=-1000, y=450),
                    -850, 450)
    intensity = g.scalar("StarIntensity", 0.6, -850, 550, group="Stars")
    factor = op(unreal.MaterialExpressionMultiply, op(unreal.MaterialExpressionMultiply, visible, clear, x=-550, y=380),
                intensity, x=-400, y=420)
    g.output(op(unreal.MaterialExpressionMultiply, sample, factor, x=-200, y=100), "", MP.MP_EMISSIVE_COLOR)
    return _finish(material, g)


# ---------------------------------------------------------------------------
# Missionsmarker und Feuerwerksfunken (Phase 9)
# ---------------------------------------------------------------------------
MARKER = SKY.replace("/Sky", "/Gameplay") + "/M_VB_MissionMarker"
SPARK = SKY.replace("/Sky", "/Gameplay") + "/M_VB_Spark"


def build_marker(mpc):
    """Leuchtender Zylinder: nach oben ausblendend, pulsierend, Farbe als Parameter."""
    material = _material(MARKER)
    _set(material, blend_mode=unreal.BlendMode.BLEND_ADDITIVE, shading_model=unreal.MaterialShadingModel.MSM_UNLIT, two_sided=True)
    g = vb.MaterialGraph(material)
    op = g.op
    uv = g.node(unreal.MaterialExpressionTextureCoordinate, -900, 0)
    v = g.mask(uv, "g", -750, 0)
    height_fade = g.unary(unreal.MaterialExpressionOneMinus, v, -600, 0)
    pulse = op(unreal.MaterialExpressionAdd, op(unreal.MaterialExpressionMultiply,
               g.unary(unreal.MaterialExpressionSine, op(unreal.MaterialExpressionMultiply, g.node(unreal.MaterialExpressionTime, -900, 200),
                                                         1.5, x=-750, y=200), -600, 200), 0.25, x=-450, y=200), 0.75, x=-300, y=200)
    color = g.node(unreal.MaterialExpressionVectorParameter, -600, -200, parameter_name="Color",
                   default_value=unreal.LinearColor(1.0, 0.75, 0.2, 1.0), group="Marker")
    intensity = g.scalar("Intensity", 8.0, -450, -100, group="Marker")
    emissive = op(unreal.MaterialExpressionMultiply,
                  op(unreal.MaterialExpressionMultiply, op(unreal.MaterialExpressionMultiply, color, height_fade, x=-300, y=-150),
                     pulse, x=-150, y=-100), intensity, x=0, y=-100)
    g.output(emissive, "", MP.MP_EMISSIVE_COLOR)
    return _finish(material, g)


def build_spark(mpc):
    """Feuerwerksfunke: Farbe und Helligkeit pro Instanz (PerInstanceCustomData 0..3)."""
    material = _material(SPARK)
    _set(material, shading_model=unreal.MaterialShadingModel.MSM_UNLIT)
    for usage_name in ("MATL_INSTANCED_STATIC_MESHES",):
        usage = getattr(unreal.MaterialUsage, usage_name, None)
        if usage is not None:
            try:
                MEL.set_material_usage(material, usage)
            except Exception:  # noqa: BLE001
                pass
    g = vb.MaterialGraph(material)
    op = g.op
    channels = []
    for index in range(4):
        node = g.node(unreal.MaterialExpressionPerInstanceCustomData, -600, index * 120, data_index=index)
        channels.append(node)
    rgb = g.node(unreal.MaterialExpressionAppendVector, -400, 0)
    rg = g.node(unreal.MaterialExpressionAppendVector, -500, 0)
    g.link(channels[0], "", rg, "A")
    g.link(channels[1], "", rg, "B")
    g.link(rg, "", rgb, "A")
    g.link(channels[2], "", rgb, "B")
    g.output(op(unreal.MaterialExpressionMultiply, rgb, channels[3], x=-200, y=100), "", MP.MP_EMISSIVE_COLOR)
    return _finish(material, g)


def build_all(mpc):
    results = {}
    for name, builder in (("Clouds", build_clouds), ("Rain", build_rain), ("Stars", build_stars), ("Marker", build_marker),
                          ("Spark", build_spark)):
        try:
            results[name] = builder(mpc)
        except Exception as exc:  # noqa: BLE001
            vb.error("%s-Material: %s" % (name, exc))
            results[name] = None
    return results
