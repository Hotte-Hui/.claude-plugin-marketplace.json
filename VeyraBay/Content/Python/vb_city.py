"""Phase 7: die ganze Stadt Veyra Bay als World-Partition-Karte L_VB_City.

Menue "Veyra Bay -> 4. Stadt bauen". Grundlage ist vb_cityplan.py (12 Bezirke, Strassenraster, Kueste) und das
Stadtgelaende aus Tools/Blender/assets/vb_asset_cityterrain.py. Alle Inhalte werden raeumlich gestreamt
(World Partition); Verkehr und Passanten backen ihre Netze und simulieren nur um den Spieler.

Einheiten: vb_cityplan liefert Meter, Unreal braucht Zentimeter (M = 100).
"""

import json
import math
import os
import random
import time

import unreal

import vb_cityplan as P
import vb_common as vb
import vb_vehicles

M = 100.0
MAP_CITY = vb.ROOT + "/World/Maps/L_VB_City"
ENV = vb.ROOT + "/Environment"
TILE_PATH = ENV + "/Terrain/SM_VB_CityTerrain_%d_%d/SM_VB_CityTerrain_%d_%d"
OCEAN_MI = vb.shared_material_path("OceanCity")
CITY_HEIGHT_TEX = vb.ROOT + "/Textures/Surfaces/CityTerrain/T_VB_CityTerrain_H"
EXTRA = {
    "t": ENV + "/Roads/SM_VB_Intersection_T/SM_VB_Intersection_T",
    "corner": ENV + "/Roads/SM_VB_Intersection_Corner/SM_VB_Intersection_Corner",
    "promenade": ENV + "/Roads/SM_VB_Promenade_5m/SM_VB_Promenade_5m",
    "quay": ENV + "/Landmarks/SM_VB_QuayWall_10m/SM_VB_QuayWall_10m",
    "bollard": ENV + "/Props/SM_VB_MooringBollard/SM_VB_MooringBollard",
    "railing": ENV + "/Props/SM_VB_Railing_2m/SM_VB_Railing_2m",
    "palm": ENV + "/Vegetation/SM_VB_PalmTree_A/SM_VB_PalmTree_A",
    "plane_tree": ENV + "/Vegetation/SM_VB_PlaneTree_A/SM_VB_PlaneTree_A",
    "ocean": ENV + "/Terrain/SM_VB_OceanPlane/SM_VB_OceanPlane",
    "bench": ENV + "/Props/SM_VB_Bench_A/SM_VB_Bench_A",
}
CHUNK = 250.0     # Meter je Instanz-Gruppe (World-Partition-Zellen)

# Farbstimmung je Bezirk (Farbverstaerkung RGB, Saettigung, Kontrast) - dezent
GRADING = {
    "Altstadt": ((1.04, 1.0, 0.94), 1.06, 1.0),
    "Hafen": ((0.96, 0.99, 1.04), 0.88, 1.04),
    "Industrie": ((0.98, 0.99, 1.0), 0.8, 1.05),
    "Strandviertel": ((1.03, 1.01, 0.96), 1.1, 0.98),
    "Marina": ((0.97, 1.0, 1.04), 1.05, 1.0),
    "Bayfront": ((0.97, 0.99, 1.03), 0.94, 1.06),
    "Mercato": ((1.05, 1.0, 0.93), 1.14, 1.02),
    "Bahnhof": ((0.99, 0.99, 1.0), 0.92, 1.03),
    "Universitaet": ((1.0, 1.02, 0.97), 1.08, 0.98),
    "Nordstadt": ((1.02, 1.0, 0.97), 1.0, 1.0),
    "Weststadt": ((1.01, 1.02, 0.96), 1.04, 0.98),
    "Monte Veyra": ((1.03, 1.02, 0.95), 1.08, 0.97),
}


def _load(path):
    return unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None


def available():
    return _load(TILE_PATH % (5, 2, 5, 2)) is not None


def _world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def _v(x_m, y_m, z_m=0.0):
    return unreal.Vector(x_m * M, y_m * M, z_m * M)


def _transform(x_m, y_m, z_m=0.0, yaw=0.0, scale=1.0):
    return unreal.Transform(location=_v(x_m, y_m, z_m), rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw),
                            scale=unreal.Vector(scale, scale, scale))


class Heights:
    """Gelaendehoehe aus SourceAssets/Export/Terrain/city_heights.json (16-m-Raster, bilinear)."""

    def __init__(self):
        path = os.path.join(vb.project_dir(), "SourceAssets", "Export", "Terrain", "city_heights.json")
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        self.x0, self.y0, self.step = data["x0"], data["y0"], data["step"]
        self.nx, self.ny = data["nx"], data["ny"]
        self.h = data["heights"]

    def at(self, x, y):
        fx = min(max((x - self.x0) / self.step, 0.0), self.nx - 1.001)
        fy = min(max((y - self.y0) / self.step, 0.0), self.ny - 1.001)
        ix, iy = int(fx), int(fy)
        tx, ty = fx - ix, fy - iy

        def g(i, j):
            return self.h[j * self.nx + i]

        top = g(ix, iy) + (g(ix + 1, iy) - g(ix, iy)) * tx
        bottom = g(ix, iy + 1) + (g(ix + 1, iy + 1) - g(ix, iy + 1)) * tx
        return top + (bottom - top) * ty


class Chunks:
    """Sammelt Instanzen je Mesh und 250-m-Zelle und legt am Ende je Zelle ein AVBInstancedArray an."""

    def __init__(self, world):
        self.world = world
        self.data = {}

    def add(self, key, mesh, transform_m, cast_shadow=True):
        if mesh is None:
            return
        x, y = transform_m[0], transform_m[1]
        cell = (key, int(math.floor(x / CHUNK)), int(math.floor(y / CHUNK)))
        entry = self.data.setdefault(cell, {"mesh": mesh, "shadow": cast_shadow, "transforms": []})
        entry["transforms"].append(_transform(*transform_m))

    def flush(self, folder):
        count = 0
        for (key, cx, cy), entry in self.data.items():
            unreal.VBBuildLibrary.spawn_instances(self.world, entry["mesh"], entry["transforms"], entry["shadow"],
                                                  "%s_%d_%d" % (key, cx, cy), folder, True)
            count += len(entry["transforms"])
        self.data = {}
        return count


# ---------------------------------------------------------------------------
# Aufbau
# ---------------------------------------------------------------------------
def open_city_map():
    level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if unreal.EditorAssetLibrary.does_asset_exist(MAP_CITY):
        level_editor.load_level(MAP_CITY)
        return False
    created = False
    try:
        created = level_editor.new_level(MAP_CITY, True)
    except TypeError:
        created = False
    if not created:
        created = level_editor.new_level_from_template(MAP_CITY, "/Engine/Maps/Templates/OpenWorld")
    if not created:
        raise RuntimeError("Karte %s konnte nicht erstellt werden." % MAP_CITY)
    return True


def ocean_material():
    parent = _load(vb.shared_material_path("Ocean"))
    height = _load(CITY_HEIGHT_TEX)
    if parent is None or height is None:
        return parent
    mel = unreal.MaterialEditingLibrary
    mi, _ = vb.load_or_create(OCEAN_MI, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, parent.get_editor_property("parent") or parent)
    mel.set_material_instance_texture_parameter_value(mi, "TerrainHeightMap", height)
    mel.set_material_instance_scalar_parameter_value(mi, "TerrainExtentCm", 3600.0 * M)
    mel.set_material_instance_scalar_parameter_value(mi, "HeightMinCm", -30.0 * M)
    mel.set_material_instance_scalar_parameter_value(mi, "HeightRangeCm", 180.0 * M)
    mel.update_material_instance(mi)
    vb.save_asset(mi)
    return mi


def build(show_dialog=True):
    import vb_setup as S   # spaeter Import (vb_setup importiert viele Module)

    if not available():
        vb.show_message("Veyra Bay - Stadt",
                        "Stadtgelaende fehlt. Zuerst 'Veyra Bay -> 2. Assets importieren' ausfuehren\n"
                        "(SourceAssets/Export/Terrain/SM_VB_CityTerrain_*).")
        return None
    started = time.time()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    is_new = open_city_map()
    S.clear_generated_actors(actors, remove_template_lighting=is_new)
    world = _world()
    rng = random.Random(2024)
    stats = {"buildings": 0, "streets": 0, "junctions": 0, "signals": 0, "lamps": 0, "instances": 0, "villas": 0}

    kit = {key: S.load_kit(path) for key, path in S.KIT.items()}
    styles = {letter: S.facade_style(letter) for letter in ("A", "B", "C")}
    styles = {k: v for k, v in styles.items() if v is not None}
    roof = S.load_kit(S.ROOF_TILE)
    roof_props = [p for p in (S.load_kit(path) for path in S.ROOF_PROPS) if p is not None]
    lamp_model = S.load_kit(S.STREETLIGHT_MODEL)
    extra = {key: _load(path) for key, path in EXTRA.items()}
    extra["4way"] = kit["intersection"]
    heights = Heights()
    prop_rules = S.street_prop_rules(kit)
    trees = Chunks(world)
    trees.meshes = extra
    coast = Chunks(world)

    junctions, streets, blocks = P.network()
    total_steps = 6
    with unreal.ScopedSlowTask(total_steps, "Veyra Bay: Stadt wird gebaut ...") as task:
        task.make_dialog(True)

        # --- 1. Himmel, Gelaende, Meer --------------------------------------------------------
        task.enter_progress_frame(1, "Himmel, Gelaende, Meer")
        sky = actors.spawn_actor_from_class(unreal.VBSkyEnvironment, unreal.Vector(0, 0, 0))
        vb.tag_actor(sky, "VB_SkyEnvironment", "Lighting", prototype=False)
        x_tiles = int((P.TERRAIN_X[1] - P.TERRAIN_X[0]) / P.TERRAIN_TILE)
        y_tiles = int((P.TERRAIN_Y[1] - P.TERRAIN_Y[0]) / P.TERRAIN_TILE)
        for i in range(x_tiles):
            for j in range(y_tiles):
                tile = _load(TILE_PATH % (i, j, i, j))
                if tile is not None:
                    # Geometrie liegt in Weltkoordinaten; World Partition nutzt die Bounds fuer die Zellzuordnung
                    unreal.VBBuildLibrary.spawn_mesh(world, tile, unreal.Vector(0, 0, 0), 0.0, "Terrain_%d_%d" % (i, j),
                                                     "Landscape/Terrain", True)
        ocean_mesh = extra.get("ocean")
        if ocean_mesh is not None:
            ocean = unreal.VBBuildLibrary.spawn_mesh(world, ocean_mesh, _v(0, 0, P.SEA_LEVEL), 0.0, "Ocean", "Landscape", False)
            material = ocean_material()
            if ocean is not None and material is not None:
                ocean.get_component_by_class(unreal.StaticMeshComponent).set_material(0, material)

        # --- 2. Strassen, Laternen, Alleebaeume ----------------------------------------------------
        task.enter_progress_frame(1, "Strassen (%d)" % len(streets))
        for index, (x0, y0, yaw, length, district_name, arterial) in enumerate(streets):
            label = "Street_%s_%04d" % (district_name.replace(" ", ""), index)
            unreal.VBBuildLibrary.spawn_street(world, _v(x0, y0), yaw, length * M, kit["road"], kit["curb"], kit["sidewalk"],
                                               prop_rules, abs(hash(label)) % 100000, label, "City/%s/Streets" % district_name)
            stats["streets"] += 1
            district = next((d for d in P.DISTRICTS if d["name"] == district_name), None)
            spacing = 25.0 if arterial else (district["lamp_spacing"] if district else 35.0)
            rad = math.radians(yaw)
            fx, fy = math.cos(rad), math.sin(rad)
            if lamp_model is not None and spacing > 0:
                along = spacing * 0.4
                side = 1
                while along < length - 3.0:
                    lx, ly = along, side * 7.0
                    wx, wy = x0 + fx * lx - fy * ly, y0 + fy * lx + fx * ly
                    unreal.VBBuildLibrary.spawn_street_light(world, _v(wx, wy, 0.15), yaw + (-90.0 if side > 0 else 90.0),
                                                             lamp_model, "%s_L%02d" % (label, stats["lamps"] % 100),
                                                             "City/%s/Lights" % district_name)
                    stats["lamps"] += 1
                    along += spacing / 2.0 if arterial else spacing
                    side = -side
            if arterial or (district and rng.random() < district.get("trees", 0.0) * 0.4):
                along = 7.5
                while along < length - 5.0:
                    for side in (-1, 1):
                        lx, ly = along, side * 8.6
                        trees.add("alley", extra["plane_tree"], (x0 + fx * lx - fy * ly, y0 + fy * lx + fx * ly, 0.15,
                                                                 rng.uniform(0, 360), rng.uniform(0.85, 1.15)))
                    along += 15.0

        # --- 3. Kreuzungen und Ampeln -------------------------------------------------------------------
        task.enter_progress_frame(1, "Kreuzungen (%d)" % len(junctions))
        for (k, j), arms in junctions.items():
            kind, yaw = P.junction_kind(arms)
            mesh = extra.get(kind)
            if mesh is None:
                continue
            x, y = P.line_x(k), P.line_y(j)
            district = P.district_at(x + 1, y + 1) or P.district_at(x - 1, y - 1)
            name = district["name"] if district else "Rand"
            unreal.VBBuildLibrary.spawn_mesh(world, mesh, _v(x, y), yaw, "Junction_%d_%d" % (k, j),
                                             "City/%s/Junctions" % name, True)
            stats["junctions"] += 1
            major = (k % P.ARTERIAL_EVERY == 0) or (j % P.ARTERIAL_EVERY == 0)
            if kind == "4way" and district and district.get("signals") and major and kit["signal"] and kit["signal_lens"]:
                for arm in range(4):
                    angle = math.radians(90.0 * arm)
                    lx, ly = 9.2, -7.0      # Zufahrt aus +X, rechte Seite = -Y
                    wx = x + math.cos(angle) * lx - math.sin(angle) * ly
                    wy = y + math.sin(angle) * lx + math.cos(angle) * ly
                    offset = 0.0 if arm % 2 == 0 else S.SIGNAL_CYCLE_OFFSET_CROSS
                    signal = S.spawn_signal(actors, kit, "Signal_%d_%d_%d" % (k, j, arm), _v(wx, wy, 0.15), 90.0 * arm, offset)
                    signal.set_folder_path("City/%s/TrafficLights" % name)
                    try:
                        signal.set_editor_property("is_spatially_loaded", True)
                    except Exception:  # noqa: BLE001
                        pass
                    stats["signals"] += 1

        # --- 4. Bebauung (Layout aus vb_cityplan: gleich wie in der Blender-Vorschau) -------------------------
        layout = P.Layout(rng).city(blocks, heights.at)
        task.enter_progress_frame(1, "Gebaeude (%d)" % len(layout.buildings))
        mode = unreal.VBFacadeMode
        for index, b in enumerate(layout.buildings):
            style = styles.get(b["style"]) or next(iter(styles.values()))
            unreal.VBBuildLibrary.spawn_building(
                world, _v(b["x"], b["y"], b["z"]), b["yaw"], style, b["bays_x"], b["bays_y"], b["floors"],
                *[getattr(mode, m.upper()) for m in b["modes"]], b["seed"], b["shop"], roof, roof_props,
                "%s_B%05d" % (b["district"].replace(" ", ""), index), "City/%s/Buildings" % b["district"])
            stats["buildings"] += 1
            stats["villas"] += 1 if b["district"] == "Monte Veyra" else 0
        for art, x, y, z, yaw, scale in layout.trees:
            trees.add("tree", extra[art], (x, y, z, yaw, scale))

        # --- 5. Uferpromenade -------------------------------------------------------------------------------
        task.enter_progress_frame(1, "Uferpromenade")
        for art, x, y, z, yaw in P.waterfront():
            target = trees if art == "palm" else coast
            target.add(art, extra[art], (x, y, z, yaw, 1.0 if art != "palm" else 0.9 + P.hash01(x, 3) * 0.25))
        stats["instances"] += coast.flush("City/Coast")
        stats["instances"] += trees.flush("City/Vegetation")

        # --- 6. Spielerstart, Autos, Verkehr, Passanten ------------------------------------------------------
        task.enter_progress_frame(1, "Verkehr und Passanten")
        grading = actors.spawn_actor_from_class(unreal.VBDistrictGrading, unreal.Vector(0, 0, 0))
        grades = []
        for d in P.DISTRICTS:
            if d["name"] not in GRADING:
                continue
            gain, saturation, contrast = GRADING[d["name"]]
            grade = unreal.VBDistrictGrade()
            grade.set_editor_property("name", d["name"])
            grade.set_editor_property("min", unreal.Vector2D(d["rect"][0] * M, d["rect"][2] * M))
            grade.set_editor_property("max", unreal.Vector2D(d["rect"][1] * M, d["rect"][3] * M))
            grade.set_editor_property("gain", unreal.LinearColor(gain[0], gain[1], gain[2], 1.0))
            grade.set_editor_property("saturation", saturation)
            grade.set_editor_property("contrast", contrast)
            grades.append(grade)
        grading.set_editor_property("districts", grades)
        vb.tag_actor(grading, "DistrictGrading", "Lighting", prototype=False)

        start = actors.spawn_actor_from_class(unreal.PlayerStart, _v(-300.0, P.QUAY_Y + 7.0, 1.2),
                                              unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        vb.tag_actor(start, "PlayerStart", "Gameplay", prototype=False)
        waterfront_y = P.line_y(P.WATERFRONT_J)
        vb_vehicles.populate(actors, [((-340.0 + k * 7.2) * M, (waterfront_y - 4.55) * M, 180.0) for k in range(6)])
        for actor in actors.get_all_level_actors():
            if isinstance(actor, unreal.VBTrafficManager) or isinstance(actor, unreal.VBCrowdManager):
                actor.bake_network()

    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    minutes = (time.time() - started) / 60.0
    summary = ("Stadt gebaut in %.1f min: %d Gebaeude (davon %d Villen), %d Strassen, %d Kreuzungen, %d Ampeln, "
               "%d Laternen, %d Baeume/Kuestenteile" % (minutes, stats["buildings"], stats["villas"], stats["streets"],
                                                     stats["junctions"], stats["signals"], stats["lamps"], stats["instances"]))
    vb.log(summary)
    if show_dialog:
        vb.show_message("Veyra Bay - Stadt", summary + "\n\nKarte: L_VB_City. Fuer die Fernsicht einmal 'Build -> Build HLODs'"
                        " ausfuehren, dann Play.")
    return stats


def run():
    return build(show_dialog=True)
