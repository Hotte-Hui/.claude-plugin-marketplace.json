"""Phase 4: kleiner Kuestenbezirk.

Baut auf dem Stadtblock aus Phase 3 auf (vb_setup.build_city_block) und ergaenzt:
  - Ringstrasse (Nord/Ost/West) + Uferstrasse (Sued) mit T-Kreuzungen und Ecken
  - Gelaende-Kacheln (Nanite) und Meer (Single Layer Water)
  - Uferpromenade mit Kaimauer, Hafenpollern (West) und Gelaender am Strand (Ost)
  - Palmenallee auf der Promenade, Platanen im Innenhof und am Stadtrand

Koordinaten in cm (Unreal). Muss zu Tools/Blender/assets/vb_asset_coast.py passen.
"""

import random

import unreal

import vb_common as vb

ENV = vb.ROOT + "/Environment"
TERRAIN_TILE = ENV + "/Terrain/SM_VB_Terrain_%d_%d/SM_VB_Terrain_%d_%d"
OCEAN = ENV + "/Terrain/SM_VB_OceanPlane/SM_VB_OceanPlane"
ASSETS = {
    "t_junction": ENV + "/Roads/SM_VB_Intersection_T/SM_VB_Intersection_T",
    "corner": ENV + "/Roads/SM_VB_Intersection_Corner/SM_VB_Intersection_Corner",
    "promenade": ENV + "/Roads/SM_VB_Promenade_5m/SM_VB_Promenade_5m",
    "quay": ENV + "/Landmarks/SM_VB_QuayWall_10m/SM_VB_QuayWall_10m",
    "bollard": ENV + "/Props/SM_VB_MooringBollard/SM_VB_MooringBollard",
    "railing": ENV + "/Props/SM_VB_Railing_2m/SM_VB_Railing_2m",
    "palm": ENV + "/Vegetation/SM_VB_PalmTree_A/SM_VB_PalmTree_A",
    "plane_tree": ENV + "/Vegetation/SM_VB_PlaneTree_A/SM_VB_PlaneTree_A",
}
SEA_LEVEL = -250.0
QUAY_Y = -9412.0
BEACH_FROM_X = 4000.0
HARBOR_TO_X = 3500.0


def _load(path):
    return unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None


def available():
    return _load(TERRAIN_TILE % (0, 0, 0, 0)) is not None and _load(ASSETS["quay"]) is not None


def _transform(x, y, z=0.0, yaw=0.0, scale=1.0):
    return unreal.Transform(location=unreal.Vector(x, y, z), rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw),
                            scale=unreal.Vector(scale, scale, scale))


def _array(actors, label, folder, mesh, transforms, cast_shadow=True):
    if mesh is None or not transforms:
        return None
    array = actors.spawn_actor_from_class(unreal.VBInstancedArray, unreal.Vector(0, 0, 0))
    array.set_editor_property("mesh", mesh)
    array.set_editor_property("cast_shadow", cast_shadow)
    array.set_editor_property("transforms", transforms)
    vb.tag_actor(array, label, folder, prototype=False)
    return array


def build(actors, instances, sphere):
    import vb_setup as S  # spaeter Import: vb_setup importiert dieses Modul

    kit = {key: S.load_kit(path) for key, path in S.KIT.items()}
    styles = {letter: S.facade_style(letter) for letter in ("A", "B", "C")}
    styles = {k: v for k, v in styles.items() if v is not None}
    roof = S.load_kit(S.ROOF_TILE)
    roof_props = [p for p in (S.load_kit(path) for path in S.ROOF_PROPS) if p is not None]
    extra = {key: _load(path) for key, path in ASSETS.items()}
    lamp_model = S.load_kit(S.STREETLIGHT_MODEL)

    # --- Stadtkern (Phase 3) -------------------------------------------------------
    counts = S.build_city_block(actors, kit, styles, roof, roof_props)
    counts.setdefault("trees", 0)

    ring_x = S.STREET_X + S.PITCH_X
    ring_y = S.STREET_Y + S.PITCH_Y

    # --- Ringstrasse + Uferstrasse -----------------------------------------------------
    for sy in (-1, 1):
        for i in (-1, 0, 1):
            origin = unreal.Vector(i * S.PITCH_X - S.BLOCK_W / 2, sy * ring_y, 0)
            label = "Ring_%s_%d" % ("N" if sy > 0 else "S", i + 1)
            S.spawn_street(actors, kit, label, origin, 0.0, S.BLOCK_W)
            counts["lamps"] += S.street_lamps(actors, lamp_model, origin, 0.0, S.BLOCK_W, label)
            counts["streets"] += 1
    for sx in (-1, 1):
        for j in (-1, 0, 1):
            origin = unreal.Vector(sx * ring_x, j * S.PITCH_Y - S.BLOCK_D / 2, 0)
            label = "Ring_%s_%d" % ("E" if sx > 0 else "W", j + 1)
            S.spawn_street(actors, kit, label, origin, 90.0, S.BLOCK_D)
            counts["lamps"] += S.street_lamps(actors, lamp_model, origin, 90.0, S.BLOCK_D, label)
            counts["streets"] += 1

    # T-Kreuzungen (Modell: Arm -Y fehlt) und Ecken (Modell: Arme +X und +Y)
    joints = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            joints.append(("t_junction", sx * S.STREET_X, sy * ring_y, 180.0 if sy > 0 else 0.0))
            joints.append(("t_junction", sx * ring_x, sy * S.STREET_Y, 90.0 if sx > 0 else 270.0))
            corner_yaw = {(1, 1): 180.0, (-1, 1): 270.0, (1, -1): 90.0, (-1, -1): 0.0}[(sx, sy)]
            joints.append(("corner", sx * ring_x, sy * ring_y, corner_yaw))
    for index, (kind, x, y, yaw) in enumerate(joints):
        mesh = extra.get(kind)
        if mesh is None:
            continue
        joint = actors.spawn_actor_from_object(mesh, unreal.Vector(x, y, 0), unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        vb.tag_actor(joint, "Junction_%02d" % index, "Street/Intersections", prototype=False)

    # --- Gelaende + Meer ---------------------------------------------------------------
    for i in range(4):
        for j in range(4):
            tile = _load(TERRAIN_TILE % (i, j, i, j))
            if tile is not None:
                actor = actors.spawn_actor_from_object(tile, unreal.Vector(0, 0, 0))
                vb.tag_actor(actor, "Terrain_%d_%d" % (i, j), "Landscape/Terrain", prototype=False)
    ocean = _load(OCEAN)
    if ocean is not None:
        actor = actors.spawn_actor_from_object(ocean, unreal.Vector(0, 0, SEA_LEVEL))
        vb.tag_actor(actor, "Ocean", "Landscape", prototype=False)

    # --- Uferpromenade ------------------------------------------------------------------------
    edge = ring_x + S.BUILDING_LINE
    x_values = []
    x = -edge
    while x < edge:
        x_values.append(x)
        x += 500.0
    _array(actors, "Promenade", "Coast", extra["promenade"],
           [_transform(px, QUAY_Y + row * 500.0) for px in x_values for row in (0, 1)])
    quay = []
    x = -edge
    while x < edge:
        quay.append(_transform(x, QUAY_Y))
        x += 1000.0
    _array(actors, "QuayWall", "Coast", extra["quay"], quay)
    _array(actors, "MooringBollards", "Coast", extra["bollard"],
           [_transform(px, QUAY_Y + 55.0, 15.0, yaw=random.Random(int(px)).uniform(0, 360))
            for px in range(int(-edge + 400), int(HARBOR_TO_X), 1200)])
    railing = []
    x = BEACH_FROM_X
    while x < edge:
        railing.append(_transform(x, QUAY_Y + 20.0, 15.0))
        x += 200.0
    _array(actors, "BeachRailing", "Coast", extra["railing"], railing)

    # --- Baeume -------------------------------------------------------------------------------
    rng = random.Random(17)
    palms = [_transform(px + rng.uniform(-80, 80), QUAY_Y + 480.0 + rng.uniform(-40, 40), 15.0, rng.uniform(0, 360),
                        rng.uniform(0.9, 1.15)) for px in range(int(-edge + 600), int(edge), 1500)]
    _array(actors, "Palms_Promenade", "Vegetation", extra["palm"], palms)
    counts["trees"] += len(palms)

    trees = []
    for px in range(int(-edge + 800), int(edge), 1800):
        trees.append(_transform(px + rng.uniform(-150, 150), ring_y + S.BUILDING_LINE + 350.0, 0.0, rng.uniform(0, 360),
                                rng.uniform(0.85, 1.2)))
    for sx in (-1, 1):
        for py in range(int(-ring_y + 600), int(ring_y), 1800):
            trees.append(_transform(sx * (ring_x + S.BUILDING_LINE + 350.0), py + rng.uniform(-150, 150), 0.0,
                                    rng.uniform(0, 360), rng.uniform(0.85, 1.2)))
    for px in (-1500.0, 0.0, 1500.0):                               # Innenhof des Mittelblocks
        trees.append(_transform(px, rng.uniform(-150, 150), 0.0, rng.uniform(0, 360), rng.uniform(0.9, 1.1)))
    _array(actors, "PlaneTrees", "Vegetation", extra["plane_tree"], trees)
    counts["trees"] += len(trees)

    # --- Kalibrierung, Spielerstart -------------------------------------------------------------
    for index, name in enumerate(["MI_VB_Calib_Grey18", "MI_VB_Calib_White80", "MI_VB_Calib_Black04", "MI_VB_Calib_Chrome"]):
        ball = actors.spawn_actor_from_object(sphere, unreal.Vector(-600 + index * 120, 300, 50))
        ball.get_component_by_class(unreal.StaticMeshComponent).set_material(0, instances[name])
        vb.tag_actor(ball, "Calibration_" + name.replace("MI_VB_Calib_", ""), "Dev/Calibration")
    start = actors.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(-2000, QUAY_Y + 700.0, 120),
                                          unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    vb.tag_actor(start, "PlayerStart", "Gameplay", prototype=False)

    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    vb.log("Bezirk: %(buildings)d Gebaeude, %(streets)d Strassen, %(lamps)d Laternen, %(signals)d Ampeln, %(trees)d Baeume" % counts)
    return counts
