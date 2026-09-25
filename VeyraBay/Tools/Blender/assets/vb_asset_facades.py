"""Veyra Bay Fassaden-Kit (Phase 3): modulare Gebaeudeteile in drei Baustilen + Dach.

Aufruf:
    blender -b --factory-startup --python vb_asset_facades.py -- --out <SourceAssets/Export>
            [--blend <datei.blend>] [--preview <ordner>] [--textures <SourceAssets/Export>]

Raster (Unreal-Koordinaten, Meter):
    Modulbreite 3.0 entlang +X, Fassadenflaeche bei Y = 0, Aussenseite = -Y, Wand 0.30 nach +Y
    Erdgeschoss 4.5 hoch, Obergeschosse 3.0, Gesims oben drauf.
    Kachelgroessen der Oberflaechen (1.0 / 1.5 m) passen ins Raster -> keine Texturspruenge an Modulgrenzen.
Ecken: Pivot = Gebaeudeecke; Fassade A laeuft entlang +X, Fassade B entlang +Y (beide nach aussen).
UV-Kanal 0: Box-Projektion in Metern. UV-Kanal 1 (WindowUV): 0..1 ueber jede Glasflaeche (Interior Mapping).
Stile:
    A  Altbau     - Putz, Sandstein-Faschen, weisse Kreuzstockfenster, Balkone, Quaderecken
    B  Loft       - Klinker, Betonstuerze, Stahlsprossenfenster
    C  Modern     - Sichtbeton, Metallpaneele, grosse Verglasung
"""

import math
import os
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vb_blender_lib as lib  # noqa: E402

W = 3.0            # Modulbreite
T = 0.30           # Wandstaerke
GROUND_H = 4.5
FLOOR_H = 3.0
GLASS_Y = 0.14
FRAME_Y0, FRAME_Y1 = 0.10, 0.17


# ---------------------------------------------------------------------------
# Materialien
# ---------------------------------------------------------------------------
def materials():
    m = {}
    m["Plaster"] = lib.make_material("FacadePlaster", (0.8, 0.72, 0.6), 0.85, surface="Plaster")
    m["Sandstone"] = lib.make_material("FacadeSandstone", (0.55, 0.47, 0.36), 0.8, surface="Sandstone")
    m["Brick"] = lib.make_material("FacadeBrick", (0.36, 0.15, 0.09), 0.85, surface="Brick")
    m["Concrete"] = lib.make_material("FacadeConcrete", (0.36, 0.35, 0.33), 0.85, surface="Concrete")
    m["MetalPanel"] = lib.make_material("FacadeMetalPanel", (0.06, 0.062, 0.066), 0.3, 0.85, surface="MetalPanel")
    m["Wood"] = lib.make_material("DoorWood", (0.3, 0.18, 0.09), 0.6, surface="Wood")
    m["PaintWhite"] = lib.make_material("PaintWindowWhite", (0.78, 0.77, 0.73), 0.4, porosity=0.05)
    m["PaintBlack"] = lib.make_material("PaintIronBlack", (0.025, 0.025, 0.027), 0.45, 0.3, porosity=0.0)
    m["PaintSteel"] = lib.make_material("PaintSteelDark", (0.04, 0.045, 0.05), 0.4, 0.6, porosity=0.0)
    m["PaintFascia"] = lib.make_material("PaintFasciaGreen", (0.03, 0.09, 0.07), 0.35, porosity=0.0)
    m["Glass"] = lib.make_material("WindowGlass", (0.02, 0.025, 0.03), 0.04, shared_material="Window")
    m["ShopGlass"] = lib.make_material("ShopGlass", (0.02, 0.025, 0.03), 0.04, shared_material="WindowShop")
    m["Gravel"] = lib.make_material("RoofGravel", (0.2, 0.2, 0.19), 0.9, surface="RoofGravel")
    m["Steel"] = lib.make_material("GalvanizedSteel", (0.55, 0.56, 0.57), 0.45, 1.0, porosity=0.0)
    return m


STYLES = {
    "A": {"wall": "Plaster", "ground_wall": "Sandstone", "trim": "Sandstone", "frame": "PaintWhite", "shop_frame": "PaintFascia",
          "metal": "PaintBlack", "fascia": "PaintFascia", "plinth": "Sandstone"},
    "B": {"wall": "Brick", "ground_wall": "Brick", "trim": "Concrete", "frame": "PaintSteel", "shop_frame": "PaintSteel",
          "metal": "PaintSteel", "fascia": "PaintSteel", "plinth": "Concrete"},
    "C": {"wall": "Concrete", "ground_wall": "Concrete", "trim": "MetalPanel", "frame": "MetalPanel", "shop_frame": "MetalPanel",
          "metal": "MetalPanel", "fascia": "MetalPanel", "plinth": "MetalPanel"},
}


# ---------------------------------------------------------------------------
# Modul-Bauer
# ---------------------------------------------------------------------------
class Module:
    """Sammelt Quader und Glasflaechen, erzeugt UVs (Meter + WindowUV) und das Objekt."""

    def __init__(self, name, mats):
        self.name = name
        self.mats = mats
        self.bm = bmesh.new()
        self.slots = []
        self.glass = []  # (face, x0, x1, z0, z1)

    def slot(self, key):
        material = self.mats[key]
        if material not in self.slots:
            self.slots.append(material)
        return self.slots.index(material)

    def box(self, x0, x1, y0, y1, z0, z1, key):
        if x1 - x0 < 1e-4 or y1 - y0 < 1e-4 or z1 - z0 < 1e-4:
            return
        lib.box(self.bm, ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0, y1 - y0, z1 - z0), self.slot(key))

    def wall(self, openings, key, x0=0.0, x1=W, z0=0.0, z1=FLOOR_H, y0=0.0, y1=T):
        """Wandscheibe mit rechteckigen Oeffnungen (Rasterzerlegung - Leibungen entstehen automatisch)."""
        xs = sorted({x0, x1, *[c for o in openings for c in (o[0], o[1]) if x0 < c < x1]})
        zs = sorted({z0, z1, *[c for o in openings for c in (o[2], o[3]) if z0 < c < z1]})
        for i in range(len(xs) - 1):
            for j in range(len(zs) - 1):
                cx, cz = (xs[i] + xs[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
                if any(o[0] < cx < o[1] and o[2] < cz < o[3] for o in openings):
                    continue
                self.box(xs[i], xs[i + 1], y0, y1, zs[j], zs[j + 1], key)

    def glass_pane(self, x0, x1, z0, z1, key="Glass", y=GLASS_Y):
        verts = [self.bm.verts.new((x0, y, z0)), self.bm.verts.new((x1, y, z0)),
                 self.bm.verts.new((x1, y, z1)), self.bm.verts.new((x0, y, z1))]
        face = self.bm.faces.new(verts)  # Normale zeigt nach -Y (aussen)
        face.material_index = self.slot(key)
        self.glass.append((face, x0, x1, z0, z1))

    def window(self, ox0, ox1, oz0, oz1, frame_key, verticals=(), horizontals=(), frame=0.06, bar=0.045,
               glass_key="Glass", sill_key=None, sill_depth=0.06):
        """Fenster in einer Oeffnung: Blendrahmen, Sprossen, Glas, optional Fensterbank."""
        y0, y1 = FRAME_Y0, FRAME_Y1
        self.box(ox0, ox0 + frame, y0, y1, oz0, oz1, frame_key)
        self.box(ox1 - frame, ox1, y0, y1, oz0, oz1, frame_key)
        self.box(ox0 + frame, ox1 - frame, y0, y1, oz0, oz0 + frame, frame_key)
        self.box(ox0 + frame, ox1 - frame, y0, y1, oz1 - frame, oz1, frame_key)
        for x in verticals:
            self.box(x - bar / 2, x + bar / 2, y0 + 0.01, y1 - 0.01, oz0 + frame, oz1 - frame, frame_key)
        for z in horizontals:
            self.box(ox0 + frame, ox1 - frame, y0 + 0.01, y1 - 0.01, z - bar / 2, z + bar / 2, frame_key)
        self.glass_pane(ox0 + frame, ox1 - frame, oz0 + frame, oz1 - frame, glass_key)
        if sill_key:
            self.box(ox0 - 0.04, ox1 + 0.04, -sill_depth, y0, oz0 - 0.06, oz0, sill_key)

    def build(self, category="Buildings", bevel=0.006, collision="auto"):
        bm = self.bm
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bm.normal_update()
        uv0 = bm.loops.layers.uv.new("UVMap")
        uv1 = bm.loops.layers.uv.new("WindowUV")
        glass = {face: rect for face, *rect in self.glass}
        for face in bm.faces:
            n = face.normal
            ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
            rect = glass.get(face)
            for loop in face.loops:
                co = loop.vert.co
                if ay >= ax and ay >= az:
                    u, v = co.x, co.z
                elif ax >= az:
                    u, v = co.y, co.z
                else:
                    u, v = co.x, co.y
                loop[uv0].uv = (u, v)
                if rect:
                    x0, x1, z0, z1 = rect
                    loop[uv1].uv = ((co.x - x0) / (x1 - x0), (co.z - z0) / (z1 - z0))
                else:
                    loop[uv1].uv = (0.0, 0.0)
        obj = lib.bm_to_object(bm, self.name)
        lib.assign_materials(obj, self.slots)
        if bevel > 0:
            lib.add_bevel(obj, bevel, segments=1, limit_angle=60.0)
            lib.apply_modifiers(obj)
        lib.mirror_to_unreal(obj)
        return lib.finalize(obj, category, nanite=True, collision=collision, puddle_response=0.0)


def sandstone_surround(mod, ox0, ox1, oz0, oz1, key, width=0.14, depth=0.03, hood=True):
    """Fensterfaschen (Stil A): Rahmen aus Sandstein um die Oeffnung, optional Verdachung."""
    mod.box(ox0 - width, ox0, -depth, 0.0, oz0, oz1, key)
    mod.box(ox1, ox1 + width, -depth, 0.0, oz0, oz1, key)
    mod.box(ox0 - width, ox1 + width, -depth, 0.0, oz1, oz1 + width, key)
    if hood:
        mod.box(ox0 - width - 0.08, ox1 + width + 0.08, -depth - 0.06, 0.0, oz1 + width, oz1 + width + 0.09, key)
        mod.box(ox0 - width - 0.04, ox1 + width + 0.04, -depth - 0.03, 0.0, oz1 + width + 0.09, oz1 + width + 0.13, key)


# ---------------------------------------------------------------------------
# Module je Stil
# ---------------------------------------------------------------------------
def upper_window(style, m):
    s = STYLES[style]
    mod = Module("SM_VB_Fac%s_Window" % style, m)
    if style == "A":
        o = (0.85, 2.15, 0.9, 2.65)
        mod.wall([o], s["wall"])
        mod.window(*o, s["frame"], verticals=(1.5,), horizontals=(2.1,), sill_key=s["trim"])
        sandstone_surround(mod, *o, s["trim"])
        # Bruestungsfeld unter dem Fenster
        mod.box(0.9, 2.1, -0.015, 0.0, 0.2, 0.75, s["trim"])
    elif style == "B":
        o = (0.6, 2.4, 0.75, 2.6)
        mod.wall([o], s["wall"])
        mod.window(*o, s["frame"], verticals=(1.05, 1.5, 1.95), horizontals=(1.2, 1.65, 2.1), bar=0.035,
                   frame=0.05, sill_key=s["trim"])
        mod.box(o[0] - 0.12, o[1] + 0.12, -0.01, 0.0, o[3], o[3] + 0.24, s["trim"])  # Betonsturz
    else:
        o = (0.1, 2.9, 0.75, 2.85)
        mod.wall([o], s["wall"])
        mod.window(*o, s["frame"], verticals=(1.5,), frame=0.05, sill_key=None)
        mod.box(0.0, W, -0.04, 0.0, 0.0, 0.75, s["trim"])          # Bruestungspaneel
        mod.box(0.0, W, -0.04, 0.0, 2.85, FLOOR_H, s["trim"])      # Sturzpaneel
    return mod.build()


def upper_variant(style, m):
    """A: Balkon, B: Doppelfenster, C: geschlossene Paneelfassade."""
    s = STYLES[style]
    if style == "A":
        mod = Module("SM_VB_FacA_Balcony", m)
        o = (0.9, 2.1, 0.0, 2.55)
        mod.wall([o], s["wall"])
        mod.window(*o, s["frame"], verticals=(1.5,), horizontals=(2.0,))
        sandstone_surround(mod, *o, s["trim"], hood=True)
        mod.box(0.3, 2.7, -0.95, 0.0, -0.16, 0.02, s["trim"])                 # Balkonplatte
        for x in (0.45, 2.55):                                                 # Konsolen
            mod.box(x - 0.08, x + 0.08, -0.8, 0.0, -0.45, -0.16, s["trim"])
        metal = s["metal"]
        mod.box(0.3, 2.7, -0.95, -0.9, 0.98, 1.03, metal)                     # Handlauf vorne
        for y0, y1 in ((-0.95, 0.0),):
            mod.box(0.3, 0.35, y0, y1, 0.98, 1.03, metal)
            mod.box(2.65, 2.7, y0, y1, 0.98, 1.03, metal)
        x = 0.36
        while x < 2.66:                                                        # Staebe vorne
            mod.box(x - 0.008, x + 0.008, -0.935, -0.92, 0.02, 0.98, metal)
            x += 0.12
        for xs in (0.32, 2.68):                                               # Staebe seitlich
            y = -0.8
            while y < -0.05:
                mod.box(xs - 0.008, xs + 0.008, y - 0.008, y + 0.008, 0.02, 0.98, metal)
                y += 0.12
        return mod.build()
    if style == "B":
        mod = Module("SM_VB_FacB_WindowPair", m)
        openings = [(0.45, 1.35, 0.75, 2.6), (1.65, 2.55, 0.75, 2.6)]
        mod.wall(openings, s["wall"])
        for o in openings:
            mid = (o[0] + o[1]) / 2
            mod.window(*o, s["frame"], verticals=(mid,), horizontals=(1.35, 1.95), bar=0.035, frame=0.05, sill_key=s["trim"])
            mod.box(o[0] - 0.1, o[1] + 0.1, -0.01, 0.0, o[3], o[3] + 0.24, s["trim"])
        return mod.build()
    mod = Module("SM_VB_FacC_Panel", m)
    mod.wall([], s["wall"])
    for i in range(3):                                                         # 3 Paneele mit Fugen
        mod.box(i * 1.0 + 0.006, (i + 1) * 1.0 - 0.006, -0.04, 0.0, 0.006, FLOOR_H - 0.006, s["trim"])
    return mod.build()


def upper_plain(style, m):
    """Geschlossene Wand (Brandwand / Giebel) fuer Obergeschosse."""
    s = STYLES[style]
    mod = Module("SM_VB_Fac%s_Plain" % style, m)
    mod.wall([], s["wall"])
    if style == "C":
        mod.box(0.0, W, -0.02, 0.0, FLOOR_H - 0.03, FLOOR_H, s["trim"])   # Deckenstirn-Fuge
    return mod.build()


def ground_plain(style, m):
    s = STYLES[style]
    mod = Module("SM_VB_Fac%s_GroundPlain" % style, m)
    mod.wall([], s["ground_wall"], z1=GROUND_H)
    mod.box(0.0, W, -0.04, 0.0, 0.0, 0.6, s["plinth"])
    if style == "A":
        rustication(mod, [], s["ground_wall"])
    if style != "C":
        mod.box(0.0, W, -0.06, 0.0, 4.25, GROUND_H, s["trim"])
    return mod.build()


def ground_shop(style, m):
    s = STYLES[style]
    mod = Module("SM_VB_Fac%s_GroundShop" % style, m)
    if style == "C":
        o = (0.1, 2.9, 0.0, 3.9)
        mod.wall([o], s["ground_wall"], z1=GROUND_H)
        mod.window(*o, s["shop_frame"], verticals=(1.5,), horizontals=(3.2,), frame=0.05, glass_key="ShopGlass")
        mod.box(0.0, W, -0.08, 0.0, 3.9, GROUND_H, s["fascia"])
        return mod.build()
    o = (0.3, 2.7, 0.6, 3.6)
    walls = s["ground_wall"]
    mod.wall([o], walls, z1=GROUND_H)
    mod.window(*o, s["shop_frame"], verticals=(1.5,), horizontals=(3.05,), frame=0.07, glass_key="ShopGlass")
    mod.box(0.0, W, -0.04, 0.0, 0.0, 0.6, s["plinth"])                            # Sockel
    mod.box(0.25, 2.75, -0.08, 0.0, 3.72, 4.15, s["fascia"])                     # Schildband
    mod.box(0.0, W, -0.06, 0.0, 4.25, GROUND_H, s["trim"])                       # Gurtgesims
    if style == "A":
        rustication(mod, [o], s["ground_wall"])
    return mod.build()


def ground_door(style, m):
    s = STYLES[style]
    mod = Module("SM_VB_Fac%s_GroundDoor" % style, m)
    o = (0.9, 2.1, 0.0, 3.3) if style != "C" else (0.6, 2.4, 0.0, 3.9)
    mod.wall([o], s["ground_wall"], z1=GROUND_H)
    frame = s["frame"] if style != "A" else "PaintFascia"
    # Tuerfluegel: unten Holz/Metallfeld, oben Glas, darueber Oberlicht
    leaf_top = 2.6
    panel_key = "Wood" if style == "A" else s["frame"]
    mod.box(o[0] + 0.06, o[1] - 0.06, FRAME_Y0 + 0.01, FRAME_Y1 - 0.01, 0.0, 1.0, panel_key)
    mod.window(o[0], o[1], 1.0, leaf_top, frame, verticals=((o[0] + o[1]) / 2,), frame=0.06)
    mod.window(o[0], o[1], leaf_top, o[3], frame, frame=0.06)
    mod.box(o[0], o[0] + 0.06, FRAME_Y0, FRAME_Y1, 0.0, 1.0, frame)
    mod.box(o[1] - 0.06, o[1], FRAME_Y0, FRAME_Y1, 0.0, 1.0, frame)
    mod.box(o[0] - 0.05, o[1] + 0.05, -0.02, FRAME_Y0, -0.02, 0.02, s["plinth"])  # Schwelle
    if style != "C":
        mod.box(0.0, o[0], -0.04, 0.0, 0.0, 0.6, s["plinth"])
        mod.box(o[1], W, -0.04, 0.0, 0.0, 0.6, s["plinth"])
        mod.box(0.0, W, -0.06, 0.0, 4.25, GROUND_H, s["trim"])
    else:
        mod.box(0.0, W, -0.08, 0.0, 3.9, GROUND_H, s["fascia"])
    if style == "A":
        rustication(mod, [o], s["ground_wall"])
        mod.box(1.35, 1.65, -0.07, 0.0, 3.3, 3.62, s["trim"])                   # Schlussstein
    return mod.build()


def ground_window(style, m):
    s = STYLES[style]
    mod = Module("SM_VB_Fac%s_GroundWindow" % style, m)
    if style == "C":
        o = (0.1, 2.9, 0.6, 3.9)
        mod.wall([o], s["ground_wall"], z1=GROUND_H)
        mod.window(*o, s["frame"], verticals=(1.5,), frame=0.05)
        mod.box(0.0, W, -0.08, 0.0, 3.9, GROUND_H, s["fascia"])
        mod.box(0.0, W, -0.04, 0.0, 0.0, 0.6, s["plinth"])
        return mod.build()
    o = (0.85, 2.15, 1.3, 3.4) if style == "A" else (0.6, 2.4, 1.1, 3.6)
    mod.wall([o], s["ground_wall"], z1=GROUND_H)
    if style == "A":
        mod.window(*o, s["frame"], verticals=(1.5,), horizontals=(2.8,), sill_key=s["trim"])
        rustication(mod, [o], s["ground_wall"])
        x = o[0] + 0.15                                                            # Fenstergitter
        while x < o[1] - 0.1:
            mod.box(x - 0.01, x + 0.01, -0.02, 0.0, o[2] + 0.02, o[2] + 1.1, s["metal"])
            x += 0.16
    else:
        mod.window(*o, s["frame"], verticals=(1.05, 1.5, 1.95), horizontals=(1.7, 2.3, 2.9), bar=0.035, frame=0.05,
                   sill_key=s["trim"])
        mod.box(o[0] - 0.12, o[1] + 0.12, -0.01, 0.0, o[3], o[3] + 0.24, s["trim"])
    mod.box(0.0, W, -0.04, 0.0, 0.0, 0.6, s["plinth"])
    mod.box(0.0, W, -0.06, 0.0, 4.25, GROUND_H, s["trim"])
    return mod.build()


def rustication(mod, openings, key):
    """Stil A: Baenderung im Erdgeschoss (Steinlagen mit Fugen, 2 cm vor der Wand)."""
    z = 0.6
    while z < 4.2:
        top = min(z + 0.4, 4.25)
        mod.wall([(o[0] - 0.001, o[1] + 0.001, o[2], o[3]) for o in openings], key, z0=z + 0.025, z1=top - 0.025,
                 y0=-0.02, y1=0.0)
        z += 0.45


def cornice(style, m):
    """Gesims + Attika ueber dem obersten Geschoss (Modul liegt auf der Traufhoehe)."""
    s = STYLES[style]
    mod = Module("SM_VB_Fac%s_Cornice" % style, m)
    if style == "A":
        for z0, z1, p in ((0.0, 0.15, 0.06), (0.15, 0.3, 0.14), (0.3, 0.38, 0.2), (0.38, 0.52, 0.28)):
            mod.box(0.0, W, -p, T, z0, z1, s["trim"])
        mod.box(0.0, W, 0.0, T, 0.52, 1.1, s["wall"])
        mod.box(0.0, W, -0.04, T + 0.04, 1.1, 1.17, s["trim"])
    elif style == "B":
        mod.box(0.0, W, -0.05, T, 0.0, 0.15, s["wall"])
        mod.box(0.0, W, -0.1, T, 0.15, 0.27, s["wall"])
        mod.box(0.0, W, 0.0, T, 0.27, 1.0, s["wall"])
        mod.box(0.0, W, -0.05, T + 0.05, 1.0, 1.05, "PaintSteel")
    else:
        mod.box(0.0, W, -0.04, T, 0.0, 1.2, s["trim"])
        mod.box(0.0, W, -0.06, T + 0.04, 1.2, 1.25, s["trim"])
    return mod.build()


def corner(style, m, height, suffix):
    """Eckstueck (Pivot = Gebaeudeecke). Verdeckt die Stossfuge zweier Fassaden."""
    s = STYLES[style]
    mod = Module("SM_VB_Fac%s_Corner%s" % (style, suffix), m)
    if suffix == "Cornice":
        steps = {"A": ((0.0, 0.15, 0.06), (0.15, 0.3, 0.14), (0.3, 0.38, 0.2), (0.38, 0.52, 0.28), (0.52, 1.1, 0.0), (1.1, 1.17, 0.04)),
                 "B": ((0.0, 0.15, 0.05), (0.15, 0.27, 0.1), (0.27, 1.0, 0.0), (1.0, 1.05, 0.05)),
                 "C": ((0.0, 1.2, 0.04), (1.2, 1.25, 0.06))}[style]
        for z0, z1, p in steps:
            key = s["wall"] if (style == "A" and z0 == 0.52) or style == "B" and z1 <= 1.0 else s["trim"]
            if style == "B" and z0 >= 1.0:
                key = "PaintSteel"
            mod.box(-p, T, -p, T, z0, z1, key)
        return mod.build(bevel=0.004)
    key = s["ground_wall"] if suffix == "Ground" else s["wall"]
    if style == "A":
        z, k = 0.0, 0
        while z < height - 0.01:
            top = min(z + 0.5, height)
            lx, ly = (0.55, 0.33) if k % 2 == 0 else (0.33, 0.55)
            mod.box(-0.03, lx, -0.03, ly, z + 0.012, top - 0.012, s["trim"])
            z, k = top, k + 1
        mod.box(0.0, T, 0.0, T, 0.0, height, key)
    elif style == "B":
        mod.box(-0.05, 0.45, -0.05, 0.45, 0.0, height, key)
    else:
        mod.box(-0.04, T, -0.04, T, 0.0, height, s["trim"])
    return mod.build(bevel=0.004)


# ---------------------------------------------------------------------------
# Dach
# ---------------------------------------------------------------------------
def roof_tile(m):
    mod = Module("SM_VB_Roof_Tile_3m", m)
    mod.box(0.0, W, 0.0, W, -0.3, 0.05, "Gravel")
    obj = mod.build(category="Buildings", bevel=0.0)
    obj["vb_puddle_response"] = 1.0
    return obj


def roof_props(m):
    objects = []
    # Klimageraet
    mod = Module("SM_VB_Roof_AC", m)
    for x in (0.05, 0.95):
        for y in (0.05, 0.65):
            mod.box(x - 0.03, x + 0.03, y - 0.03, y + 0.03, 0.0, 0.12, "PaintSteel")
    mod.box(0.0, 1.0, 0.0, 0.7, 0.12, 0.92, "Steel")
    z = 0.2
    while z < 0.85:                                                             # Lamellen
        mod.box(0.05, 0.95, -0.015, 0.0, z, z + 0.03, "Steel")
        z += 0.07
    lib.cylinder(mod.bm, (0.5, 0.35, 0.94), 0.28, 0.04, segments=32, material_index=mod.slot("PaintSteel"))
    for i in range(6):
        lib.box(mod.bm, (0.5, 0.35, 0.965), (0.52, 0.012, 0.01), mod.slot("PaintSteel"))
        bmesh.ops.rotate(mod.bm, verts=[v for v in mod.bm.verts if abs(v.co.z - 0.965) < 0.006 and abs(v.co.y - 0.35) < 0.27][-8:],
                         cent=(0.5, 0.35, 0.965), matrix=__import__("mathutils").Matrix.Rotation(math.radians(30 * i), 3, "Z"))
    objects.append(mod.build(category="Props", bevel=0.004))
    # Entlueftungsrohr
    mod = Module("SM_VB_Roof_Vent", m)
    lib.tapered_cylinder(mod.bm, 0.09, 0.09, 0.0, 0.9, segments=24, material_index=mod.slot("Steel"))
    lib.tapered_cylinder(mod.bm, 0.16, 0.05, 0.95, 1.08, segments=24, material_index=mod.slot("Steel"))
    lib.tapered_cylinder(mod.bm, 0.03, 0.03, 0.9, 0.96, segments=12, material_index=mod.slot("Steel"))
    objects.append(mod.build(category="Props", bevel=0.0))
    # Treppenhausaufbau
    mod = Module("SM_VB_Roof_StairHouse", m)
    door = (0.8, 1.7, 0.0, 2.1)
    mod.wall([door], "Plaster", x0=0.0, x1=2.4, z1=2.6, y0=0.0, y1=0.2)
    mod.box(0.0, 0.2, 0.2, 2.4, 0.0, 2.6, "Plaster")
    mod.box(2.2, 2.4, 0.2, 2.4, 0.0, 2.6, "Plaster")
    mod.box(0.0, 2.4, 2.2, 2.4, 0.0, 2.6, "Plaster")
    mod.box(-0.05, 2.45, -0.05, 2.45, 2.6, 2.7, "Concrete")
    mod.box(door[0], door[1], 0.08, 0.12, 0.0, 2.1, "PaintSteel")
    objects.append(mod.build(category="Props", bevel=0.004))
    # Antenne
    mod = Module("SM_VB_Roof_Antenna", m)
    lib.tapered_cylinder(mod.bm, 0.025, 0.02, 0.0, 3.2, segments=12, material_index=mod.slot("Steel"))
    lib.tapered_cylinder(mod.bm, 0.12, 0.12, 0.0, 0.03, segments=12, material_index=mod.slot("Steel"))
    for z, length in ((2.4, 1.2), (2.7, 1.0), (3.0, 0.8)):
        lib.box(mod.bm, (0.0, 0.0, z), (length, 0.012, 0.012), mod.slot("Steel"))
    objects.append(mod.build(category="Props", bevel=0.0))
    return objects


def build_all(m):
    assets = []
    for style in ("A", "B", "C"):
        assets.append(upper_window(style, m))
        assets.append(upper_variant(style, m))
        assets.append(upper_plain(style, m))
        assets.append(ground_plain(style, m))
        assets.append(ground_shop(style, m))
        assets.append(ground_door(style, m))
        assets.append(ground_window(style, m))
        assets.append(cornice(style, m))
        assets.append(corner(style, m, GROUND_H, "Ground"))
        assets.append(corner(style, m, FLOOR_H, "Upper"))
        assets.append(corner(style, m, 0.0, "Cornice"))
    assets.append(roof_tile(m))
    assets.extend(roof_props(m))
    return assets


# ---------------------------------------------------------------------------
# Vorschau: kleines Eckhaus je Stil
# ---------------------------------------------------------------------------
def preview_building(assets, style, origin, bays_x=4, bays_y=3, floors=4):
    """Setzt ein Eckgebaeude in UNREAL-Koordinaten zusammen (wie AVBBuildingBuilder) und rechnet nach Blender um."""
    lookup = {a.name: a for a in assets}

    def place(name, x, y, z, yaw):
        obj = bpy.data.objects.new(name + "_p", lookup[name].data)
        obj.location = (origin[0] + x, -(origin[1] + y), z)
        obj.rotation_euler = (0, 0, math.radians(-yaw))
        bpy.context.collection.objects.link(obj)

    top = GROUND_H + (floors - 1) * FLOOR_H
    faces = [((0, 0), 0, bays_x), ((bays_x * W, 0), 90, bays_y), ((bays_x * W, bays_y * W), 180, bays_x), ((0, bays_y * W), 270, bays_y)]
    for (fx, fy), yaw, bays in faces:
        dx, dy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        for i in range(bays):
            x, y = fx + dx * i * W, fy + dy * i * W
            ground = "GroundShop" if (yaw == 0 and i % 2 == 0) else ("GroundDoor" if yaw == 0 else "GroundWindow")
            place("SM_VB_Fac%s_%s" % (style, ground), x, y, 0, yaw)
            for f in range(1, floors):
                variant = {"A": "Balcony", "B": "WindowPair", "C": "Panel"}[style]
                kind = variant if (i + f) % 3 == 0 else "Window"
                place("SM_VB_Fac%s_%s" % (style, kind), x, y, GROUND_H + (f - 1) * FLOOR_H, yaw)
            place("SM_VB_Fac%s_Cornice" % style, x, y, top, yaw)
        place("SM_VB_Fac%s_CornerGround" % style, fx, fy, 0, yaw)
        for f in range(1, floors):
            place("SM_VB_Fac%s_CornerUpper" % style, fx, fy, GROUND_H + (f - 1) * FLOOR_H, yaw)
        place("SM_VB_Fac%s_CornerCornice" % style, fx, fy, top, yaw)


def main():
    args = lib.cli_args()
    lib.reset_scene()
    m = materials()
    assets = build_all(m)
    for asset in assets:
        print("%-30s %6d Dreiecke" % (asset.name, lib.vb_blender_export.triangle_count(asset)))
    if args.get("blend"):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args["blend"]))
    status = 0
    if args.get("out"):
        exported, _ = lib.export(args["out"])
        status = 0 if exported == len(assets) else 1
    if args.get("preview"):
        for asset in assets:
            asset.hide_render = True
        for index, style in enumerate(("A", "B", "C")):
            preview_building(assets, style, (index * 16.0, 0.0), floors=4 + index)
        os.makedirs(args["preview"], exist_ok=True)
        lib.render_preview(os.path.join(args["preview"], "facades.png"), (22.0, -6.0, 7.0), (-6.0, 16.0, 3.0),
                           resolution=(1280, 720), lens=24.0, samples=40, sun_angle=(50.0, 0.0, -30.0),
                           preview_textures_root=args.get("textures"))
    return status


if __name__ == "__main__":
    sys.exit(main())
