"""Prozedurale PBR-Oberflaechen fuer Veyra Bay -> gebackene, nahtlos kachelnde Texturen.

Aufruf:
    blender -b --factory-startup --python vb_surfaces.py -- --out <SourceAssets/Export> [--only Asphalt] [--size 2048]

Ergebnis je Oberflaeche: SourceAssets/Export/Surfaces/<Name>/T_VB_<Name>_D.png, _N.png, _ORM.png, surface.json
Albedo-Werte orientieren sich an gemessenen Referenzen (Asphalt 0.04-0.08, Beton 0.25-0.40, Granit 0.1-0.5).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vb_blender_lib as lib  # noqa: E402


def asphalt(s):
    """Gebrauchter Stadtasphalt: Gesteinskoernung, Bitumen-Flicken, feine Risse."""
    tone = s.noise(24, 6, 0.55).outputs["Fac"]
    fine = s.noise(220, 3, 0.6).outputs["Fac"]
    stones = s.voronoi(260, "F1")
    stone_shape = s.math("SUBTRACT", 1.0, s.smoothstep(0.12, 0.42, stones.outputs["Distance"]))
    bright = s.math("MULTIPLY", s.smoothstep(0.6, 0.72, stones.outputs["Color"]), stone_shape)
    # Kleine Bitumen-Flecken (grossflaechige Variation kommt weltbasiert aus dem Master-Material)
    patches = s.smoothstep(0.62, 0.7, s.noise(9.0, 3, 0.5).outputs["Fac"])
    crack_edge = s.voronoi(3.0, "DISTANCE_TO_EDGE").outputs["Distance"]
    crack_region = s.smoothstep(0.6, 0.68, s.noise(4.0, 4, 0.6).outputs["Fac"])
    cracks = s.math("MULTIPLY", s.math("SUBTRACT", 1.0, s.smoothstep(0.003, 0.011, crack_edge)), crack_region)

    color = s.mix((0.030, 0.030, 0.032), (0.062, 0.060, 0.058), tone)
    color = s.mix(color, (0.17, 0.165, 0.155), s.math("MULTIPLY", bright, 0.85))
    color = s.mix(color, (0.020, 0.020, 0.022), s.math("MULTIPLY", patches, 0.85))
    color = s.mix(color, (0.010, 0.010, 0.010), cracks)

    roughness = s.lerp(0.9, 0.74, bright)
    roughness = s.lerp(roughness, 0.62, patches)
    roughness = s.lerp(roughness, 0.96, cracks)

    height = s.value(stone_shape, 0.35, 0.4)
    height = s.math("ADD", height, s.math("MULTIPLY", fine, 0.15))
    height = s.math("SUBTRACT", height, s.math("MULTIPLY", cracks, 0.45))
    height = s.math("SUBTRACT", height, s.math("MULTIPLY", patches, 0.05))

    ao = s.math("MULTIPLY", s.lerp(1.0, 0.45, cracks), s.lerp(0.82, 1.0, stone_shape))
    return {"color": color, "roughness": roughness, "height": height, "ao": ao, "metallic": 0.0}


def concrete(s):
    """Betonsteinpflaster / Rinnstein: feine Koernung, Poren, Verfaerbungen."""
    tone = s.noise(14, 8, 0.6).outputs["Fac"]
    fine = s.noise(90, 5, 0.6).outputs["Fac"]
    pores_v = s.voronoi(420, "F1")
    pores = s.math("MULTIPLY", s.math("SUBTRACT", 1.0, s.smoothstep(0.04, 0.2, pores_v.outputs["Distance"])),
                   s.smoothstep(0.86, 0.94, pores_v.outputs["Color"]))
    stains = s.smoothstep(0.6, 0.78, s.noise(5.0, 4, 0.5).outputs["Fac"])

    color = s.mix((0.285, 0.28, 0.265), (0.37, 0.36, 0.34), tone)
    color = s.mix(color, (0.21, 0.205, 0.19), s.math("MULTIPLY", stains, 0.6))
    color = s.mix(color, (0.12, 0.12, 0.11), pores)

    roughness = s.lerp(s.value(fine, 0.08, 0.84), 0.8, stains)
    height = s.math("SUBTRACT", s.value(fine, 0.3, 0.45), s.math("MULTIPLY", pores, 0.45))
    ao = s.lerp(1.0, 0.55, pores)
    return {"color": color, "roughness": roughness, "height": height, "ao": ao, "metallic": 0.0}


def granite(s):
    """Grauer Granit fuer Bordsteine: Kristallkoernung, leicht polierte Oberseite."""
    grains = s.voronoi(170, "F1")
    grain_color = s.ramp(grains.outputs["Color"], [
        (0.0, (0.07, 0.07, 0.075)),
        (0.28, (0.24, 0.24, 0.25)),
        (0.62, (0.40, 0.40, 0.41)),
        (0.9, (0.47, 0.42, 0.40)),
        (0.97, (0.55, 0.55, 0.56)),
    ], interpolation="CONSTANT")
    tone = s.noise(3, 5, 0.5).outputs["Fac"]
    color = s.mix(grain_color, (0.2, 0.2, 0.2), s.math("MULTIPLY", tone, 0.25))
    edges = s.voronoi(170, "DISTANCE_TO_EDGE").outputs["Distance"]
    roughness = s.value(s.noise(30, 4, 0.5).outputs["Fac"], 0.2, 0.52)
    height = s.value(s.smoothstep(0.0, 0.08, edges), 0.2, 0.5)
    return {"color": color, "roughness": roughness, "height": height, "ao": 1.0, "metallic": 0.0}


def cast_iron(s):
    """Gusseisen (Kanaldeckel): blank gefahrene Kanten, Rostnester."""
    tone = s.noise(8, 6, 0.6).outputs["Fac"]
    rust = s.smoothstep(0.55, 0.7, s.noise(3.5, 6, 0.62).outputs["Fac"])
    color = s.mix((0.22, 0.22, 0.23), (0.34, 0.34, 0.35), tone)
    color = s.mix(color, (0.21, 0.10, 0.045), rust)
    metallic = s.lerp(0.85, 0.0, rust)
    roughness = s.lerp(s.value(tone, 0.15, 0.48), 0.88, rust)
    height = s.math("ADD", s.value(s.noise(60, 5, 0.6).outputs["Fac"], 0.3, 0.35), s.math("MULTIPLY", rust, 0.2))
    ao = s.lerp(1.0, 0.8, rust)
    return {"color": color, "roughness": roughness, "height": height, "ao": ao, "metallic": metallic}


def weathered_wood(s):
    """Verwittertes Hartholz fuer Baenke: Maserung entlang U, vergraute Oberflaeche."""
    warp = s.noise(3.0, 4, 0.55).outputs["Fac"]
    phase = s.math("ADD", s.math("MULTIPLY", s.uv(1), 38.0), s.math("MULTIPLY", warp, 0.9))
    grain = s.value(s.math("SINE", s.math("MULTIPLY", phase, 6.283185)), 0.5, 0.5)
    pores = s.noise(160, 3, 0.6).outputs["Fac"]
    weather = s.smoothstep(0.4, 0.7, s.noise(2.0, 5, 0.55).outputs["Fac"])
    color = s.ramp(grain, [(0.0, (0.20, 0.11, 0.055)), (1.0, (0.34, 0.20, 0.10))])
    color = s.mix(color, (0.30, 0.28, 0.25), s.math("MULTIPLY", weather, 0.55))
    roughness = s.lerp(s.value(grain, 0.1, 0.6), 0.82, weather)
    height = s.math("ADD", s.value(grain, 0.3, 0.3), s.math("MULTIPLY", pores, 0.2))
    return {"color": color, "roughness": roughness, "height": height, "ao": s.value(grain, 0.15, 0.85), "metallic": 0.0}


def brick(s):
    """Klinker im Laeuferverband: 24 x 7.1 cm, 1-cm-Fugen -> 4 Steine x 12 Schichten pro Meter (kachelbar)."""
    u, v = s.uv(0), s.uv(1)
    rows = s.math("MULTIPLY", v, 12.0)
    row = s.math("FLOOR", rows)
    offset = s.math("MULTIPLY", s.math("MODULO", row, 2.0), 0.5)
    bricks_u = s.math("ADD", s.math("MULTIPLY", u, 4.0), offset)
    column = s.math("MODULO", s.math("FLOOR", bricks_u), 4.0)
    fu, fv = s.math("FRACT", bricks_u), s.math("FRACT", rows)
    # Fugenmaske (1 cm), leicht weich
    joint_u = s.math("MAXIMUM", s.math("SUBTRACT", 1.0, s.smoothstep(0.0, 0.045, fu)), s.smoothstep(0.955, 1.0, fu))
    joint_v = s.math("MAXIMUM", s.math("SUBTRACT", 1.0, s.smoothstep(0.0, 0.14, fv)), s.smoothstep(0.93, 1.0, fv))
    mortar = s.math("MAXIMUM", joint_u, joint_v)
    rnd = s.white_noise(s.combine(column, s.math("MODULO", row, 12.0), 3.0))
    rnd2 = s.white_noise(s.combine(column, s.math("MODULO", row, 12.0), 7.0))
    brick_color = s.ramp(rnd, [(0.0, (0.20, 0.07, 0.04)), (0.25, (0.33, 0.12, 0.07)), (0.7, (0.42, 0.18, 0.10)),
                               (0.92, (0.46, 0.27, 0.16)), (1.0, (0.24, 0.16, 0.13))])
    surface = s.noise(60, 5, 0.6).outputs["Fac"]
    brick_color = s.mix(brick_color, (0.15, 0.07, 0.05), s.math("MULTIPLY", s.smoothstep(0.55, 0.8, surface), 0.4))
    color = s.mix(brick_color, (0.40, 0.38, 0.34), mortar)
    roughness = s.lerp(s.value(rnd2, 0.12, 0.78), 0.93, mortar)
    height = s.math("SUBTRACT", s.value(surface, 0.2, 0.7), s.math("MULTIPLY", mortar, 0.6))
    ao = s.lerp(1.0, 0.55, mortar)
    return {"color": color, "roughness": roughness, "height": height, "ao": ao, "metallic": 0.0}


def plaster(s):
    """Heller Kratzputz (wird in Unreal per BaseColorTint eingefaerbt), mit feinen Laufspuren."""
    grain = s.noise(140, 6, 0.65).outputs["Fac"]
    trowel = s.noise(6, 4, 0.5).outputs["Fac"]
    streaks = s.smoothstep(0.58, 0.75, s.noise_aniso(34.0, 2.0, 6, 0.55).outputs["Fac"])
    color = s.mix((0.70, 0.69, 0.66), (0.80, 0.79, 0.76), trowel)
    color = s.mix(color, (0.50, 0.49, 0.46), s.math("MULTIPLY", streaks, 0.35))
    roughness = s.value(grain, 0.1, 0.84)
    height = s.math("ADD", s.value(grain, 0.5, 0.3), s.math("MULTIPLY", trowel, 0.15))
    return {"color": color, "roughness": roughness, "height": height, "ao": s.value(grain, 0.2, 0.8), "metallic": 0.0}


def sandstone(s):
    """Sandstein fuer Gesimse, Fensterfaschen, Eckquader."""
    grains = s.noise(220, 4, 0.6).outputs["Fac"]
    layers = s.noise_aniso(3.0, 18.0, 4, 0.5).outputs["Fac"]
    weather = s.smoothstep(0.55, 0.75, s.noise(4, 5, 0.6).outputs["Fac"])
    color = s.mix((0.50, 0.42, 0.31), (0.60, 0.52, 0.40), layers)
    color = s.mix(color, (0.32, 0.29, 0.25), s.math("MULTIPLY", weather, 0.5))
    roughness = s.value(grains, 0.12, 0.8)
    height = s.math("ADD", s.value(grains, 0.35, 0.3), s.math("MULTIPLY", layers, 0.2))
    return {"color": color, "roughness": roughness, "height": height, "ao": 1.0, "metallic": 0.0}


def metal_panel(s):
    """Dunkel eloxierte Metallpaneele (moderne Fassaden), leicht gebuerstet mit Schlieren."""
    brushed = s.noise_aniso(400.0, 4.0, 3, 0.5).outputs["Fac"]
    smudge = s.smoothstep(0.5, 0.75, s.noise(3, 5, 0.55).outputs["Fac"])
    color = s.mix((0.055, 0.058, 0.062), (0.075, 0.078, 0.082), brushed)
    roughness = s.lerp(s.value(brushed, 0.1, 0.3), 0.5, s.math("MULTIPLY", smudge, 0.6))
    height = s.value(brushed, 0.1, 0.5)
    return {"color": color, "roughness": roughness, "height": height, "ao": 1.0, "metallic": 0.85}


def roof_gravel(s):
    """Flachdach mit Kiesschuettung und Bitumenflecken."""
    stones = s.voronoi(180, "F1")
    stone_shape = s.math("SUBTRACT", 1.0, s.smoothstep(0.15, 0.5, stones.outputs["Distance"]))
    stone_color = s.ramp(stones.outputs["Color"], [(0.0, (0.18, 0.17, 0.16)), (0.5, (0.32, 0.31, 0.29)), (1.0, (0.45, 0.43, 0.40))])
    tar = s.smoothstep(0.6, 0.7, s.noise(5, 4, 0.5).outputs["Fac"])
    color = s.mix((0.05, 0.05, 0.05), stone_color, stone_shape)
    color = s.mix(color, (0.03, 0.03, 0.032), s.math("MULTIPLY", tar, 0.8))
    roughness = s.lerp(0.9, 0.7, tar)
    height = s.math("SUBTRACT", s.value(stone_shape, 0.6, 0.2), s.math("MULTIPLY", tar, 0.2))
    return {"color": color, "roughness": roughness, "height": height, "ao": s.lerp(0.6, 1.0, stone_shape), "metallic": 0.0}


SURFACES = {
    # Name: (Funktion, Kachelgroesse m, Aufloesung, Normal-Staerke, Unreal-Parameter)
    "Asphalt": (asphalt, 2.0, 2048, 1.0, {"porosity": 0.85, "wetness_response": 1.0, "puddle_response": 1.0}),
    "Concrete": (concrete, 1.5, 1024, 0.8, {"porosity": 0.6, "wetness_response": 1.0, "puddle_response": 1.0}),
    "Granite": (granite, 1.0, 1024, 0.5, {"porosity": 0.35, "wetness_response": 1.0, "puddle_response": 0.0}),
    "CastIron": (cast_iron, 1.0, 1024, 0.8, {"porosity": 0.1, "wetness_response": 1.0, "puddle_response": 0.0}),
    "Wood": (weathered_wood, 1.0, 1024, 0.6, {"porosity": 0.7, "wetness_response": 1.0, "puddle_response": 0.0}),
    "Brick": (brick, 1.0, 1024, 0.9, {"porosity": 0.7, "wetness_response": 1.0, "puddle_response": 0.0}),
    # Putz: zwei Grundtoene; jedes Gebaeude mischt per Custom Primitive Data [1] ("TintBlend") dazwischen
    "Plaster": (plaster, 1.5, 1024, 0.6, {"porosity": 0.55, "wetness_response": 0.8, "puddle_response": 0.0,
                                          "tint": [1.0, 0.86, 0.66], "tint2": [0.82, 0.88, 0.9]}),
    "Sandstone": (sandstone, 1.0, 1024, 0.6, {"porosity": 0.6, "wetness_response": 0.9, "puddle_response": 0.0}),
    "MetalPanel": (metal_panel, 1.0, 1024, 0.3, {"porosity": 0.0, "wetness_response": 0.7, "puddle_response": 0.0}),
    "RoofGravel": (roof_gravel, 1.5, 1024, 1.0, {"porosity": 0.8, "wetness_response": 1.0, "puddle_response": 1.0}),
}


def main():
    args = lib.cli_args()
    out_root = args.get("out")
    if not out_root:
        print("Aufruf: ... -- --out <SourceAssets/Export> [--only Name] [--size N]")
        return 2
    only = args.get("only")
    for name, (build, tile, size, strength, params) in SURFACES.items():
        if only and name not in only.split(","):
            continue
        lib.bake_surface(name, build, out_root, size=int(args.get("size", size)), tile_meters=tile,
                         normal_strength=strength, bump_distance=0.02, params=params)
    return 0


if __name__ == "__main__":
    sys.exit(main())
