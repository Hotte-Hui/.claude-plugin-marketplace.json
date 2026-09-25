"""Stadtplan von Veyra Bay (Phase 7) - gemeinsame Datenquelle fuer Blender (Gelaende) und Unreal (Aufbau).

Kein `import unreal` hier: das Modul wird auch vom Blender-Gelaendegenerator geladen.
Alle Masse in METERN, Unreal-Achsen: +X Osten, +Y Norden (Hinterland), das Meer liegt im Sueden.

Strassenraster: globale Gitterlinien (wie im Phase-3-Stadtblock)
    Nord-Sued-Strassen  x_k = 39.78 + 79.56 * k
    Ost-West-Strassen   y_j = 24.78 + 49.56 * j      (j = -2: Uferstrasse bei y = -74.34)
Jeder Bezirk behaelt jede n-te Linie (Blockgroesse), Hauptachsen (jede 4. Linie) laufen durch.
Zwischen Strassenmitte und Bauflucht liegen 9.78 m (Fahrbahn + Gehweg), Blockgroessen sind Vielfache von 3 m.
"""

import math

PITCH_X, PITCH_Y = 79.56, 49.56
ORIGIN_X, ORIGIN_Y = 39.78, 24.78
BUILDING_LINE = 9.78
WATERFRONT_J = -2                       # Uferstrasse
QUAY_Y = -94.12                         # Kaimauer / Uferlinie (wie Phase 4)
SEA_LEVEL = -2.5

K_RANGE = (-40, 39)                     # x von -3142.7 bis 3142.8
J_RANGE = (-2, 38)                      # y von -74.3 bis 1908.1

# Gelaende (Blender): Ausdehnung und Kacheln
TERRAIN_X = (-3600.0, 3600.0)
TERRAIN_Y = (-1600.0, 2600.0)
TERRAIN_TILE = 600.0
TERRAIN_CELL = 4.0

# Kuestenabschnitte entlang X: Hafenkai, Strand, Marina-Kai; ausserhalb Felskueste
HARBOR = (-3150.0, 400.0)
BEACH = (400.0, 2300.0)
MARINA = (2300.0, 3150.0)


def line_x(k):
    return ORIGIN_X + PITCH_X * k


def line_y(j):
    return ORIGIN_Y + PITCH_Y * j


# ---------------------------------------------------------------------------
# Bezirke
# ---------------------------------------------------------------------------
# rect: (x0, x1, y0, y1) in Metern (werden auf Gitterlinien gerundet)
# every: (n_x, n_y) jede n-te Gitterlinie wird Strasse
# kind: perimeter | towers | warehouses | industry | villas | houses | park | campus | plaza
# styles: Gewichte der Fassadenstile A (Altbau), B (Klinker-Loft), C (Modern)
DISTRICTS = [
    dict(id=1, name="Altstadt", rect=(-900, 700, -80, 600), every=(1, 1), kind="perimeter", floors=(4, 6),
         styles={"A": 8, "B": 2}, shop_ratio=0.85, lamp_spacing=25.0, signals=True, trees=0.3),
    dict(id=2, name="Hafen", rect=(-2300, -900, -80, 450), every=(2, 2), kind="warehouses", floors=(2, 4),
         styles={"B": 8, "C": 1}, shop_ratio=0.15, lamp_spacing=35.0, signals=False, trees=0.05),
    dict(id=3, name="Industrie", rect=(-3150, -2300, -80, 1150), every=(3, 3), kind="industry", floors=(2, 3),
         styles={"B": 5, "C": 5}, shop_ratio=0.0, lamp_spacing=40.0, signals=False, trees=0.1),
    dict(id=4, name="Strandviertel", rect=(700, 2300, -80, 450), every=(1, 2), kind="perimeter", floors=(5, 10),
         styles={"C": 5, "A": 4}, shop_ratio=0.8, lamp_spacing=25.0, signals=True, trees=0.5, waterfront_floors=(8, 14)),
    # Zwickel zwischen Strandviertel, Bayfront und Universitaet
    dict(id=4, name="Strandviertel", rect=(700, 1100, 450, 600), every=(1, 2), kind="perimeter", floors=(5, 9),
         styles={"C": 5, "A": 4}, shop_ratio=0.8, lamp_spacing=25.0, signals=True, trees=0.5),
    dict(id=5, name="Marina", rect=(2300, 3150, -80, 600), every=(2, 1), kind="perimeter", floors=(3, 6),
         styles={"C": 8, "A": 1}, shop_ratio=0.6, lamp_spacing=30.0, signals=False, trees=0.6),
    dict(id=6, name="Bayfront", rect=(-500, 1100, 600, 1150), every=(1, 1), kind="towers", floors=(14, 42),
         styles={"C": 9, "B": 1}, shop_ratio=0.9, lamp_spacing=25.0, signals=True, trees=0.3),
    dict(id=7, name="Mercato", rect=(-1500, -500, 450, 1150), every=(1, 1), kind="perimeter", floors=(3, 5),
         styles={"A": 6, "B": 4}, shop_ratio=0.98, lamp_spacing=25.0, signals=True, trees=0.2),
    dict(id=8, name="Bahnhof", rect=(-2300, -1500, 450, 1150), every=(2, 1), kind="perimeter", floors=(5, 9),
         styles={"B": 5, "C": 4, "A": 2}, shop_ratio=0.7, lamp_spacing=30.0, signals=True, trees=0.3, plaza=True),
    dict(id=9, name="Universitaet", rect=(1100, 2300, 450, 1150), every=(2, 2), kind="campus", floors=(3, 6),
         styles={"C": 5, "A": 5}, shop_ratio=0.2, lamp_spacing=30.0, signals=False, trees=1.0),
    dict(id=10, name="Nordstadt", rect=(-1500, 1100, 1150, 1910), every=(2, 2), kind="perimeter", floors=(3, 5),
         styles={"A": 5, "B": 5}, shop_ratio=0.4, lamp_spacing=30.0, signals=False, trees=0.7),
    dict(id=11, name="Weststadt", rect=(-3150, -1500, 1150, 1910), every=(2, 2), kind="houses", floors=(2, 3),
         styles={"A": 6, "C": 4}, shop_ratio=0.0, lamp_spacing=40.0, signals=False, trees=1.0),
    dict(id=12, name="Monte Veyra", rect=(1100, 3150, 1150, 2400), every=(0, 0), kind="villas", floors=(2, 3),
         styles={"A": 6, "C": 4}, shop_ratio=0.0, lamp_spacing=0.0, signals=False, trees=1.0, hills=True),
    # Zusatzflaeche Monte Veyra: Suedhang zwischen Marina und Universitaet
    dict(id=12, name="Monte Veyra", rect=(2300, 3150, 600, 1150), every=(0, 0), kind="villas", floors=(2, 3),
         styles={"A": 6, "C": 4}, shop_ratio=0.0, lamp_spacing=0.0, signals=False, trees=1.0, hills=True),
]

ARTERIAL_EVERY = 4


def district_at(x, y):
    for district in DISTRICTS:
        x0, x1, y0, y1 = district["rect"]
        if x0 <= x < x1 and y0 <= y < y1:
            return district
    return None


def is_plateau(x, y, margin=0.0):
    """Liegt der Punkt auf der flachen Stadtebene (Strassen, Bebauung auf z = 0)?"""
    for district in DISTRICTS:
        if district.get("hills"):
            continue
        x0, x1, y0, y1 = district["rect"]
        if x0 - margin <= x < x1 + margin and y0 - margin <= y < y1 + margin:
            return True
    return False


def _keeps(district, axis, index):
    if district is None or district.get("hills"):
        return False
    every = district["every"][0 if axis == "x" else 1]
    if every <= 0:
        return False
    if index % ARTERIAL_EVERY == 0:
        return True
    return index % every == 0


def keeps_x_line(k, y):
    """Gibt es die Nord-Sued-Strasse k auf Hoehe y?"""
    x = line_x(k)
    # Die Linie liegt auf der Grenze zweier Bezirke -> beide Seiten fragen
    return _keeps(district_at(x - 1.0, y), "x", k) or _keeps(district_at(x + 1.0, y), "x", k)


def keeps_y_line(j, x):
    y = line_y(j)
    if j == WATERFRONT_J:
        return is_plateau(x, y + 30.0)
    return _keeps(district_at(x, y - 1.0), "y", j) or _keeps(district_at(x, y + 1.0), "y", j)


# ---------------------------------------------------------------------------
# Strassennetz aus dem Gitter
# ---------------------------------------------------------------------------
def network():
    """Liefert (junctions, streets, blocks).

    junctions: dict (k, j) -> set der Arme {"+X", "-X", "+Y", "-Y"}
    streets:   Liste (x0, y0, yaw, length, district_name) - Strasse zwischen zwei Knoten (Bauflucht-bereinigt)
    blocks:    Liste (x0, y0, x1, y1, district) - Bauflaeche zwischen den Baufluchten
    """
    k0, k1 = K_RANGE
    j0, j1 = J_RANGE
    # Kanten im Gitter
    edges_x = {}   # (k, j) -> Kante von (k, j) nach (k, j+1) entlang X-Linie k
    edges_y = {}   # (k, j) -> Kante von (k, j) nach (k+1, j) entlang Y-Linie j
    for k in range(k0, k1 + 1):
        for j in range(j0, j1):
            ym = (line_y(j) + line_y(j + 1)) / 2
            if keeps_x_line(k, ym):
                edges_x[(k, j)] = True
    for j in range(j0, j1 + 1):
        for k in range(k0, k1):
            xm = (line_x(k) + line_x(k + 1)) / 2
            if keeps_y_line(j, xm):
                edges_y[(k, j)] = True

    arms = {}
    for (k, j) in edges_x:
        arms.setdefault((k, j), set()).add("+Y")
        arms.setdefault((k, j + 1), set()).add("-Y")
    for (k, j) in edges_y:
        arms.setdefault((k, j), set()).add("+X")
        arms.setdefault((k + 1, j), set()).add("-X")

    def is_junction(node):
        a = arms.get(node, set())
        if len(a) >= 3:
            return True
        if len(a) == 2 and a not in ({"+X", "-X"}, {"+Y", "-Y"}):
            return True    # Ecke
        return False

    junctions = {node: a for node, a in arms.items() if is_junction(node)}

    # Strassen: zusammenhaengende Kantenfolgen zwischen Kreuzungen/Enden
    streets = []
    half = BUILDING_LINE
    for (k, j) in sorted(edges_y):
        # Nur am Anfang einer Folge starten
        if (k - 1, j) in edges_y and (k, j) not in junctions:
            continue
        start = (k, j)
        end_k = k
        while (end_k, j) in edges_y and ((end_k + 1, j) not in junctions) and (end_k + 1, j) in edges_y:
            end_k += 1
        end = (end_k + 1, j)
        x0 = line_x(start[0]) + (half if start in junctions else 0.0)
        x1 = line_x(end[0]) - (half if end in junctions else 0.0)
        if x1 - x0 > 5.0:
            d = district_at((x0 + x1) / 2, line_y(j) + 1.0) or district_at((x0 + x1) / 2, line_y(j) - 1.0)
            streets.append((x0, line_y(j), 0.0, x1 - x0, d["name"] if d else "Rand", j % ARTERIAL_EVERY == 0))
    for (k, j) in sorted(edges_x):
        if (k, j - 1) in edges_x and (k, j) not in junctions:
            continue
        end_j = j
        while (k, end_j) in edges_x and ((k, end_j + 1) not in junctions) and (k, end_j + 1) in edges_x:
            end_j += 1
        start, end = (k, j), (k, end_j + 1)
        y0 = line_y(start[1]) + (half if start in junctions else 0.0)
        y1 = line_y(end[1]) - (half if end in junctions else 0.0)
        if y1 - y0 > 5.0:
            d = district_at(line_x(k) + 1.0, (y0 + y1) / 2) or district_at(line_x(k) - 1.0, (y0 + y1) / 2)
            streets.append((line_x(k), y0, 90.0, y1 - y0, d["name"] if d else "Rand", k % ARTERIAL_EVERY == 0))

    # Bloecke: Gitterzellen, die nicht durch eine Strasse getrennt sind, werden (je Bezirk) zusammengefasst
    owner = {}
    for k in range(k0, k1):
        for j in range(j0, j1):
            d = district_at((line_x(k) + line_x(k + 1)) / 2, (line_y(j) + line_y(j + 1)) / 2)
            if d is not None and not d.get("hills"):
                owner[(k, j)] = d
    parent = {cell: cell for cell in owner}

    def find(cell):
        while parent[cell] != cell:
            parent[cell] = parent[parent[cell]]
            cell = parent[cell]
        return cell

    for (k, j), d in owner.items():
        right, up = (k + 1, j), (k, j + 1)
        if right in owner and owner[right] is d and (k + 1, j) not in edges_x:
            parent[find(right)] = find((k, j))
        if up in owner and owner[up] is d and (k, j + 1) not in edges_y:
            parent[find(up)] = find((k, j))
    groups = {}
    for cell in owner:
        groups.setdefault(find(cell), []).append(cell)

    blocks = []
    for cells in groups.values():
        ks = [c[0] for c in cells]
        js = [c[1] for c in cells]
        kmin, kmax, jmin, jmax = min(ks), max(ks), min(js), max(js)
        rectangular = len(cells) == (kmax - kmin + 1) * (jmax - jmin + 1)
        rects = [(kmin, kmax, jmin, jmax)] if rectangular else [(c[0], c[0], c[1], c[1]) for c in cells]
        for ka, kb, ja, jb in rects:
            d = owner[(ka, ja)]
            # Einruecken: an Strassen bis zur Bauflucht, sonst schmaler Abstand
            west = half if (ka, ja) in edges_x else 2.0
            east = half if (kb + 1, ja) in edges_x else 2.0
            south = half if (ka, ja) in edges_y else 2.0
            north = half if (ka, jb + 1) in edges_y else 2.0
            bx0, bx1 = line_x(ka) + west, line_x(kb + 1) - east
            by0, by1 = line_y(ja) + south, line_y(jb + 1) - north
            if bx1 - bx0 >= 20.0 and by1 - by0 >= 20.0:
                blocks.append((bx0, by0, bx1, by1, d))
    return junctions, streets, blocks


def junction_kind(arms):
    """Kreuzungs-Mesh und Drehung (Grad) fuer eine Arm-Menge.
    Modelle: 4Way; T = Arm -Y fehlt; Corner = Arme +X und +Y."""
    if len(arms) == 4:
        return "4way", 0.0
    if len(arms) == 3:
        missing = ({"+X", "-X", "+Y", "-Y"} - arms).pop()
        # T-Modell fehlt -Y; Drehung so, dass der fehlende Arm an die richtige Stelle kommt
        return "t", {"-Y": 0.0, "+X": 90.0, "+Y": 180.0, "-X": 270.0}[missing]
    if len(arms) == 2:
        key = frozenset(arms)
        yaw = {frozenset({"+X", "+Y"}): 0.0, frozenset({"+Y", "-X"}): 90.0, frozenset({"-X", "-Y"}): 180.0,
               frozenset({"-Y", "+X"}): 270.0}.get(key)
        if yaw is not None:
            return "corner", yaw
    return None, 0.0


def hash01(*values):
    """Deterministische Pseudo-Zufallszahl 0..1 (gleich in Blender und Unreal)."""
    h = 2166136261
    for value in values:
        for ch in repr(round(value, 3) if isinstance(value, float) else value):
            h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return (h % 100000) / 100000.0


def villa_sites():
    """Grundstuecke am Monte Veyra (x, y, yaw) - Hoehe kommt aus dem Gelaende."""
    sites = []
    for district in DISTRICTS:
        if district["kind"] != "villas":
            continue
        x0, x1, y0, y1 = district["rect"]
        y = y0 + 40.0
        row = 0
        while y < y1 - 30.0:
            x = x0 + 30.0 + (25.0 if row % 2 else 0.0)
            while x < x1 - 30.0:
                if hash01(x, y, 7) < 0.55:
                    jitter_x = (hash01(x, y, 1) - 0.5) * 16.0
                    jitter_y = (hash01(x, y, 2) - 0.5) * 12.0
                    sites.append((x + jitter_x, y + jitter_y, 180.0 if hash01(x, y, 3) < 0.8 else 90.0))
                x += 55.0
            y += 45.0
            row += 1
    return sites


# ---------------------------------------------------------------------------
# Bebauung je Bezirkstyp (reine Daten: gleich in Unreal und in der Blender-Vorschau)
# ---------------------------------------------------------------------------
class Layout:
    """Erzeugt Gebaeude- und Baum-Beschreibungen fuer Bloecke (Meter).

    buildings: dict(x, y, yaw, bays_x, bays_y, floors, modes=(front, right, back, left), style, shop, z, district)
               Ursprung = vordere linke Ecke; Yaw 0: Front nach Sueden (-Y), Gebaeude erstreckt sich nach +X/+Y.
    trees:     (art, x, y, z, yaw, scale) mit art in {"plane_tree", "palm"}
    """

    def __init__(self, rng):
        self.rng = rng
        self.buildings = []
        self.trees = []

    def style(self, district):
        pool = [letter for letter, weight in district["styles"].items() for _ in range(weight)]
        return self.rng.choice(pool)

    def building(self, district, x, y, yaw, bays_x, bays_y, floors, modes=("Full", "Full", "Full", "Full"), shop=None, z=0.0):
        if bays_x < 2 or bays_y < 2:
            return
        self.buildings.append(dict(x=x, y=y, yaw=yaw, bays_x=int(bays_x), bays_y=int(bays_y), floors=int(floors), modes=modes,
                                   style=self.style(district), shop=district["shop_ratio"] if shop is None else shop, z=z,
                                   district=district["name"], seed=self.rng.randint(1, 999999)))

    def tree(self, x, y, z=0.0, palm=False, scale=(0.8, 1.15)):
        self.trees.append(("palm" if palm else "plane_tree", x, y, z, self.rng.uniform(0, 360), self.rng.uniform(*scale)))

    def floors(self, district, waterfront=False):
        low, high = district.get("waterfront_floors", district["floors"]) if waterfront else district["floors"]
        return self.rng.randint(low, high)

    def splits(self, bays, low=4, high=8):
        parts = []
        while bays > 0:
            size = min(bays, self.rng.randint(low, high))
            if 0 < bays - size < low:
                size = bays
            parts.append(size)
            bays -= size
        return parts

    def block(self, block):
        kind = block[4]["kind"]
        {"perimeter": self.perimeter, "towers": self.towers, "warehouses": self.warehouses,
         "industry": lambda b: self.warehouses(b, industry=True), "houses": self.houses,
         "campus": self.campus}.get(kind, lambda b: None)(block)

    # --- Blockrandbebauung -----------------------------------------------------------------
    def perimeter(self, block):
        x0, y0, x1, y1, d = block
        bays_w, bays_h = int((x1 - x0) // 3), int((y1 - y0) // 3)
        waterfront = y0 < -60.0
        if bays_h < 7:
            # Schmaler Block: durchgehende Zeile, Vorder- und Rueckseite zur Strasse
            x = x0
            for bays in self.splits(bays_w):
                self.building(d, x, y0, 0.0, bays, bays_h, self.floors(d, waterfront))
                x += bays * 3
            return
        depth = min(4, bays_h // 2 - 1) if bays_h < 12 else self.rng.choice([3, 4])
        parts = self.splits(bays_w)
        x = x0
        for index, bays in enumerate(parts):       # Suedzeile, Front nach Sueden
            first, last = index == 0, index == len(parts) - 1
            self.building(d, x, y0, 0.0, bays, depth, self.floors(d, waterfront),
                          ("Full", "Full" if last else "Plain", "Plain", "Full" if first else "Plain"))
            x += bays * 3
        parts = self.splits(bays_w)
        x = x0
        for index, bays in enumerate(parts):       # Nordzeile, Front nach Norden (Ursprung am Ostende)
            first, last = index == 0, index == len(parts) - 1
            self.building(d, x + bays * 3, y1, 180.0, bays, depth, self.floors(d),
                          ("Full", "Full" if first else "Plain", "Plain", "Full" if last else "Plain"))
            x += bays * 3
        inner = bays_h - 2 * depth
        if inner >= 3:
            y_start = y0 + depth * 3
            self.building(d, x1, y_start, 90.0, inner, depth, self.floors(d), ("Full", "Plain", "Plain", "Plain"))
            self.building(d, x0, y_start + inner * 3, 270.0, inner, depth, self.floors(d), ("Full", "Plain", "Plain", "Plain"))
        if self.rng.random() < d.get("trees", 0.0) and bays_w > 2 * depth + 4 and inner >= 4:
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            for _ in range(self.rng.randint(1, 3)):
                self.tree(cx + self.rng.uniform(-(x1 - x0) / 4, (x1 - x0) / 4), cy + self.rng.uniform(-3, 3))

    # --- Hochhaeuser -----------------------------------------------------------------------
    def towers(self, block):
        x0, y0, x1, y1, d = block
        bays_w, bays_h = int((x1 - x0) // 3), int((y1 - y0) // 3)
        count = 2 if bays_w >= 22 else 1
        tw = min((bays_w - 2 * count) // count, 12)
        th = min(bays_h - 2, 9)
        if tw < 4 or th < 4:
            return self.perimeter(block)
        slot = (x1 - x0) / count
        for index in range(count):
            x = x0 + index * slot + (slot - tw * 3) / 2
            y = y0 + ((y1 - y0) - th * 3) / 2
            self.building(d, x, y, 0.0, tw, th, self.floors(d))
        for _ in range(self.rng.randint(2, 5)):
            self.tree(self.rng.uniform(x0 + 3, x1 - 3), y0 + 2.5, scale=(0.8, 1.1))

    # --- Lagerhallen / Industrie -----------------------------------------------------------
    def warehouses(self, block, industry=False):
        x0, y0, x1, y1, d = block
        bays_w, bays_h = int((x1 - x0) // 3), int((y1 - y0) // 3)
        if industry:
            w = max(4, int(bays_w * self.rng.uniform(0.55, 0.85)))
            h = max(4, int(bays_h * self.rng.uniform(0.5, 0.75)))
            self.building(d, x0 + ((x1 - x0) - w * 3) / 2, y0 + 3.0, 0.0, w, h, self.floors(d), shop=0.0)
            return
        rows = 2 if bays_h >= 18 else 1
        depth = min((bays_h - 2 * rows) // rows, 10)
        for row in range(rows):
            y = y0 + 2 + row * (depth * 3 + 4)
            x = x0
            for bays in self.splits(bays_w - 1, 8, 16):
                self.building(d, x, y, 0.0, bays - 1, depth, self.floors(d))
                x += bays * 3

    # --- Einfamilienhaeuser ----------------------------------------------------------------
    def houses(self, block):
        x0, y0, x1, y1, d = block
        for y, yaw in ((y0 + 4.0, 0.0), (y1 - 4.0, 180.0)):
            x = x0 + 4.0
            while x < x1 - 16.0:
                bays = self.rng.choice([3, 4])
                self.building(d, x if yaw == 0.0 else x + bays * 3, y, yaw, bays, 3, self.floors(d), shop=0.0)
                self.tree(x + bays * 1.5, (y0 + y1) / 2 + self.rng.uniform(-4, 4), scale=(0.7, 1.0))
                x += bays * 3 + self.rng.uniform(6.0, 10.0)

    # --- Campus / Park ---------------------------------------------------------------------
    def campus(self, block):
        x0, y0, x1, y1, d = block
        if self.rng.random() < 0.4:
            self.park(block)
            return
        bays_w, bays_h = int((x1 - x0) // 3), int((y1 - y0) // 3)
        self.building(d, x0 + 6, y0 + 6, 0.0, min(bays_w - 4, 14), min(bays_h - 4, 7), self.floors(d), shop=0.1)
        self.park(block, density=0.3)

    def park(self, block, density=1.0):
        x0, y0, x1, y1, _d = block
        y = y0 + 6.0
        while y < y1 - 4.0:
            x = x0 + 6.0 + self.rng.uniform(0, 4)
            while x < x1 - 4.0:
                if self.rng.random() < 0.7 * density:
                    self.tree(x + self.rng.uniform(-2, 2), y + self.rng.uniform(-2, 2), palm=self.rng.random() < 0.15,
                              scale=(0.8, 1.2))
                x += self.rng.uniform(10.0, 16.0)
            y += self.rng.uniform(10.0, 16.0)

    # --- Villen am Hang --------------------------------------------------------------------
    def villas(self, height_at):
        district = next(d for d in DISTRICTS if d["kind"] == "villas")
        for (x, y, _yaw) in villa_sites():
            bays_x, bays_y = self.rng.choice([3, 4]), 3
            corners = [height_at(x + dx, y + dy) for dx in (0, bays_x * 3) for dy in (0, bays_y * 3)]
            base = min(corners)
            if base < 1.0:
                continue
            # Front nach Sueden (Meerblick); tiefste Ecke, damit nichts schwebt
            self.building(district, x, y, 0.0, bays_x, bays_y, self.floors(district), shop=0.0, z=base - 0.3)
            for _ in range(self.rng.randint(1, 3)):
                tx, ty = x + self.rng.uniform(-8, bays_x * 3 + 8), y + self.rng.uniform(-10, 2)
                self.tree(tx, ty, height_at(tx, ty) - 0.2, palm=self.rng.random() < 0.4)

    def city(self, blocks, height_at=None):
        """Alle Bloecke (+ Bahnhofsvorplatz, Villen)."""
        plaza_done = set()
        for block in blocks:
            district = block[4]
            if district.get("plaza") and district["name"] not in plaza_done:
                cx = (district["rect"][0] + district["rect"][1]) / 2
                cy = (district["rect"][2] + district["rect"][3]) / 2
                if block[0] - 40 <= cx <= block[2] + 40 and block[1] - 30 <= cy <= block[3] + 30:
                    self.park(block, density=0.5)       # Bahnhofsvorplatz
                    plaza_done.add(district["name"])
                    continue
            self.block(block)
        if height_at is not None:
            self.villas(height_at)
        return self


def waterfront():
    """Uferpromenade: (art, x, y, z, yaw) - Promenadenplatten, Kaimauer, Poller, Gelaender, Palmen."""
    items = []
    x = HARBOR[0]
    while x < MARINA[1]:
        items.append(("promenade", x, QUAY_Y, 0.0, 0.0))
        items.append(("promenade", x, QUAY_Y + 5.0, 0.0, 0.0))
        x += 5.0
    x = HARBOR[0]
    while x < MARINA[1]:
        items.append(("quay", x, QUAY_Y, 0.0, 0.0))
        x += 10.0
    x = HARBOR[0] + 4.0
    while x < MARINA[1]:
        if HARBOR[0] <= x < HARBOR[1] or MARINA[0] <= x < MARINA[1]:
            items.append(("bollard", x, QUAY_Y + 0.55, 0.15, hash01(x, 5) * 360.0))
        x += 12.0
    x = BEACH[0]
    while x < BEACH[1]:
        items.append(("railing", x, QUAY_Y + 0.2, 0.15, 0.0))
        x += 2.0
    x = HARBOR[0] + 6.0
    while x < MARINA[1]:
        items.append(("palm", x + (hash01(x, 1) - 0.5) * 1.6, QUAY_Y + 4.8, 0.15, hash01(x, 2) * 360.0))
        x += 15.0
    return items


def describe():
    junctions, streets, blocks = network()
    length = sum(s[3] for s in streets)
    return "%d Kreuzungen, %d Strassen (%.1f km), %d Bloecke, %d Villen" % (
        len(junctions), len(streets), length / 1000.0, len(blocks), len(villa_sites()))


if __name__ == "__main__":
    print(describe())
