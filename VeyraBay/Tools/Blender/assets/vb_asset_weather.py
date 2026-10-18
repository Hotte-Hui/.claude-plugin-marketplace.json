"""Hilfsmeshes fuer Himmel und Wetter (Phase 6).

    blender -b --factory-startup --python vb_asset_weather.py -- --out <SourceAssets/Export>

SM_VB_RainCylinder  offener Zylinder, Radius 1 m, Hoehe 1 m (Pivot unten Mitte), U = Umfang (0..1), V = Hoehe.
                    AVBWeatherEffects skaliert drei davon um die Kamera (nah / mittel / fern) mit M_VB_Rain.
SM_VB_SkyDome       Kugel, Radius 1 m, Normalen nach innen, equirektangulare UVs (Sternenhimmel M_VB_Stars).
"""

import math
import os
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vb_blender_lib as lib  # noqa: E402


def rain_cylinder(material):
    bm = bmesh.new()
    segments, rows = 32, 4
    uv_layer = bm.loops.layers.uv.new("UVMap")
    grid = []
    for row in range(rows + 1):
        z = row / rows
        grid.append([bm.verts.new((math.cos(2 * math.pi * k / segments), math.sin(2 * math.pi * k / segments), z))
                     for k in range(segments)])
    for row in range(rows):
        for k in range(segments):
            nxt = (k + 1) % segments
            face = bm.faces.new((grid[row][k], grid[row][nxt], grid[row + 1][nxt], grid[row + 1][k]))
            u0, u1 = k / segments, (k + 1) / segments
            v0, v1 = row / rows, (row + 1) / rows
            for loop, uv in zip(face.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
                loop[uv_layer].uv = uv
    obj = lib.bm_to_object(bm, "SM_VB_RainCylinder")
    obj.data.materials.append(material)
    return lib.finalize(obj, "Sky", nanite=False, collision="none")


def sky_dome(material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1.0, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = obj.data.name = "SM_VB_SkyDome"
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.materials.append(material)
    lib.shade_smooth(obj, 180.0)
    # Pivot in der Mitte ist gewollt (Kamera sitzt im Zentrum)
    return lib.finalize(obj, "Sky", nanite=False, collision="none", allow_floating_pivot=True)


def main():
    args = lib.cli_args()
    lib.reset_scene()
    rain = lib.make_material("RainStreaks", (0.8, 0.85, 0.9), 0.1)
    stars = lib.make_material("Stars", (0.0, 0.0, 0.0), 1.0)
    assets = [rain_cylinder(rain), sky_dome(stars)]
    if args.get("out"):
        exported, _ = lib.export(os.path.abspath(args["out"]), only=[a.name for a in assets])
        return 0 if exported == len(assets) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
