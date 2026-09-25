"""Phase 5: Verkehr, Passanten und fahrbare Autos in die Karte setzen.

Liest SourceAssets/Export/Vehicles/vehicles.json (vom Blender-Generator vb_asset_vehicles.py) und die
importierten Meshes unter /Game/VeyraBay/Vehicles. Koordinaten in cm.
"""

import json
import os

import unreal

import vb_common as vb

VEHICLES = vb.ROOT + "/Vehicles"

# Haeufigkeit im fliessenden Verkehr / als geparktes Auto, Beweglichkeit (Anfahren)
TRAFFIC = {
    "Sedan": (30, 30, 1.0),
    "SUV": (18, 18, 0.9),
    "Taxi": (12, 3, 1.0),
    "Van": (10, 8, 0.75),
    "Pickup": (9, 8, 0.85),
    "Sport": (5, 4, 1.3),
    "Bus": (3, 0, 0.5),
}
FIXED_PAINT = {"Taxi", "Bus"}

# Fahrbare Autos (Chaos): Motor und Antrieb
DRIVABLE = {
    "Sport": dict(max_torque=520.0, max_rpm=7600.0, all_wheel_drive=False),
    "Sedan": dict(max_torque=340.0, max_rpm=6400.0, all_wheel_drive=False),
    "Taxi": dict(max_torque=300.0, max_rpm=6000.0, all_wheel_drive=False),
    "SUV": dict(max_torque=480.0, max_rpm=6000.0, all_wheel_drive=True),
    "Pickup": dict(max_torque=560.0, max_rpm=5600.0, all_wheel_drive=True),
    "Van": dict(max_torque=380.0, max_rpm=5200.0, all_wheel_drive=False),
}


def _asset(name):
    path = "%s/%s/%s" % (VEHICLES, name, name)
    return unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None


def catalog():
    path = os.path.join(vb.project_dir(), "SourceAssets", "Export", "Vehicles", "vehicles.json")
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def available():
    return _asset("SM_VB_Car_Sedan") is not None and _asset("SM_VB_Wheel_Sedan") is not None


def traffic_types():
    types = []
    for name, data in catalog().items():
        body = _asset("SM_VB_Car_%s" % name)
        wheel = _asset(data.get("wheel", "SM_VB_Wheel_%s" % name))
        if body is None or wheel is None:
            continue
        spec = data["spec"]
        weight, parked, agility = TRAFFIC.get(name, (1, 1, 1.0))
        t = unreal.VBTrafficVehicleType()
        t.set_editor_property("name", name)
        t.set_editor_property("body_mesh", body)
        t.set_editor_property("wheel_mesh", wheel)
        t.set_editor_property("length", spec["length"] * 100.0)
        t.set_editor_property("width", spec["width"] * 100.0)
        t.set_editor_property("wheelbase", spec["wheelbase"] * 100.0)
        t.set_editor_property("wheel_radius", spec["radius"] * 100.0)
        t.set_editor_property("wheel_width", spec["wheel_width"] * 100.0)
        t.set_editor_property("weight", float(weight))
        t.set_editor_property("parked_weight", float(parked))
        t.set_editor_property("agility", agility)
        t.set_editor_property("fixed_paint", name in FIXED_PAINT)
        paint = data.get("paint", [0.12, 0.14, 0.16])
        t.set_editor_property("paint", unreal.LinearColor(paint[0], paint[1], paint[2], 1.0))
        types.append(t)
    return types


def spawn_drivable(actors, name, location, yaw, paint=None):
    mesh = _asset("SK_VB_Car_%s" % name)
    data = catalog().get(name)
    if mesh is None or data is None:
        return None
    spec = data["spec"]
    vehicle = actors.spawn_actor_from_class(unreal.VBVehicle, location, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    component = vehicle.get_component_by_class(unreal.SkeletalMeshComponent)
    component.set_skeletal_mesh_asset(mesh)
    vehicle.set_editor_property("vehicle_type", name)
    vehicle.set_editor_property("wheel_mesh", _asset(data.get("wheel", "SM_VB_Wheel_%s" % name)))
    vehicle.set_editor_property("length", spec["length"] * 100.0)
    vehicle.set_editor_property("width", spec["width"] * 100.0)
    vehicle.set_editor_property("wheelbase", spec["wheelbase"] * 100.0)
    vehicle.set_editor_property("wheel_radius", spec["radius"] * 100.0)
    vehicle.set_editor_property("wheel_width", spec["wheel_width"] * 100.0)
    vehicle.set_editor_property("mass_kg", float(spec["mass"]))
    for key, value in DRIVABLE.get(name, {}).items():
        vehicle.set_editor_property(key, value)
    color = paint or data.get("paint", [0.12, 0.14, 0.16])
    vehicle.set_editor_property("paint_color", unreal.LinearColor(color[0], color[1], color[2], 1.0))
    vehicle.rerun_construction_scripts()
    vb.tag_actor(vehicle, "Drivable_%s" % name, "Gameplay/Vehicles", prototype=False)
    return vehicle


def populate(actors, parking_spots):
    """parking_spots: Liste (x, y, yaw) am Fahrbahnrand fuer die fahrbaren Autos."""
    counts = {"drivable": 0, "traffic_types": 0}
    if not available():
        vb.warn("Fahrzeuge nicht importiert - Verkehr wird uebersprungen (Blender: vb_asset_vehicles.py, dann Import).")
        return counts

    for (x, y, yaw), name in zip(parking_spots, ("Sport", "Sedan", "SUV", "Pickup", "Taxi", "Van")):
        if spawn_drivable(actors, name, unreal.Vector(x, y, 30.0), yaw) is not None:
            counts["drivable"] += 1

    types = traffic_types()
    counts["traffic_types"] = len(types)
    traffic = actors.spawn_actor_from_class(unreal.VBTrafficManager, unreal.Vector(0, 0, 0))
    traffic.set_editor_property("vehicle_types", types)
    vb.tag_actor(traffic, "TrafficManager", "Gameplay/Simulation", prototype=False)

    crowd = actors.spawn_actor_from_class(unreal.VBCrowdManager, unreal.Vector(0, 0, 0))
    vb.tag_actor(crowd, "CrowdManager", "Gameplay/Simulation", prototype=False)
    vb.log("Verkehr: %(traffic_types)d Fahrzeugtypen, %(drivable)d fahrbare Autos" % counts)
    return counts
