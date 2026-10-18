# Veyra Bay – Konventionen

Das Tool **Veyra Bay → 3. Assets validieren** prüft diese Regeln automatisch.

## Ordner (`/Game/VeyraBay/...`)

```
Core/        Blueprints, Data, Input
Characters/  Player, MetaHumans, NPC_Wardrobe, Animations
Vehicles/    <Fahrzeug>/ (Mesh, Materialien, Audio, Daten)
Environment/ Buildings, Roads, Props, Vegetation, Landmarks, Terrain  → je Asset ein Unterordner
Materials/   Global (MPC), Master, Functions, Instances, Decals
Textures/    Default, Surfaces
FX/ Weather/ AI/ UI/ Audio/ Systems/
World/       Maps, DataLayers, HLOD, Districts
Dev/         Test-Inhalte, werden nicht ausgeliefert
```

## Namens-Präfixe

| Typ | Präfix | Typ | Präfix |
|---|---|---|---|
| Static Mesh | `SM_` | Material | `M_` |
| Skeletal Mesh | `SK_` / `SKM_` | Material-Instanz | `MI_` |
| Blueprint | `BP_` | Material-Funktion | `MF_` |
| Widget | `WBP_` | Parameter-Collection | `MPC_` |
| Anim Blueprint | `ABP_` | Textur | `T_` |
| Niagara | `NS_` | Karte | `L_` |
| MetaSound | `MS_` | Data Table | `DT_` |

**Textur-Suffixe:** `_D` BaseColor (sRGB) · `_N` Normal (Normalmap-Kompression) · `_ORM` AO/Rauheit/Metallic (linear, Masks) · `_E` Emissive · `_M` Maske · `_H` Höhe

## Master-Material `M_VB_Surface` – Parameter

| Parameter | Bedeutung |
|---|---|
| `BaseColorMap`, `NormalMap`, `ORMMap` | Texturen (Standardtexturen, falls leer) |
| `BaseColorTint`, `Roughness`, `Metallic`, `UVTiling` | Grundwerte (Roughness/Metallic skalieren den ORM-Kanal) |
| `Porosity` | Wie stark die Oberfläche bei Nässe dunkler wird (Asphalt 0,85, Beton 0,55, Metall 0) |
| `WetnessResponse` | 0 = bleibt trocken (Innenräume, überdacht), 1 = voll nass |
| `PuddleResponse` | 1 = Pfützen möglich (Straßen, Plätze), 0 = nie (Fassaden, Möbel) |
| `EmissiveColor`, `EmissiveIntensity` | Leuchten in cd/m² (LED-Linse ~8.000, Fenster ~50–300, Neon ~1.000–3.000) |
| `UseNightSwitch` | 1 = Leuchten nur, wenn `UVBNightLightComponent` des Actors eingeschaltet ist |

## Blender

- Szene metrisch, Unit Scale 1.0 (1 BU = 1 m). Skalierung/Rotation anwenden.
- Asset = Mesh auf oberster Ebene, Name `SM_<Name>`. Kollision: Kinder `UCX_SM_<Name>_00 …`.
- Pivot unten mittig (bei Türen: Scharnierkante). Vorderseite/Ausleger zeigt nach **+X**.
- Custom Properties am Objekt: `vb_category`, `vb_nanite`, `vb_collision`, `vb_porosity`, `vb_wetness_response`, `vb_puddle_response`, `vb_uv_tiling`.
- Custom Properties am Material: `vb_base_color`, `vb_roughness`, `vb_metallic`, `vb_emissive_color`, `vb_emissive_intensity`, `vb_use_night_switch`.
- Texturen neben die FBX legen: `T_<Name>_D.png`, `T_<Name>_N.png`, `T_<Name>_ORM.png` (bei mehreren Slots `T_<Name>_<Slot>_D.png`).
- Normal Maps im Blender-/OpenGL-Format backen – der Import spiegelt den Grünkanal automatisch.

## Gebackene Oberflächen & Kit-Teile

- Oberflächen liegen unter `SourceAssets/Export/Surfaces/<Name>/` (`T_VB_<Name>_D/_N/_ORM.png` + `surface.json` mit Kachelgröße und Wetterparametern) und werden zu `MI_VB_Surface_<Name>` in `/Game/VeyraBay/Materials/Surfaces`.
- UVs aller Kit-Teile sind **in Metern** (Würfelprojektion, 1 UV = 1 m). `UVTiling` der Oberfläche = 1 / Kachelgröße.
- Materialslot mit Custom Property `vb_surface = "Asphalt"` → Unreal nutzt die gemeinsame Oberflächen-Instanz.
- Kit-Teile: Pivot am Anfang (X = 0), kacheln entlang +X; Straßenquerschnitt siehe `Tools/Blender/assets/vb_asset_streetkit.py`.
- Wegen `materials.clear()` in Blender immer `vb_blender_lib.assign_materials()` benutzen (erhält die Flächen-Materialindizes).

## Koordinaten Blender → Unreal

Der FBX-Import von Unreal negiert Y (Blender +Y → Unreal −Y; darum schaut das Mannequin nach +Y).
Kit-Teile, bei denen die Seite zählt (Bordsteine, Fahrspuren, Fassaden, Kreuzungen), werden in **Unreal-Koordinaten**
modelliert und vor dem Export mit `vb_blender_lib.mirror_to_unreal()` gespiegelt. Rechtsverkehr: Fahrtrichtung +X
fährt auf der +Y-Seite. Fassadenmodule: Außenseite = −Y, Wand nach +Y, Modulbreite 3 m, EG 4,5 m, OG 3 m.

## Custom Primitive Data

| Index | Name im Material | Gesetzt von |
|---|---|---|
| 0 | `LightOn` | `UVBNightLightComponent`, `AVBTrafficLight` |
| 1 | `TintBlend` | `AVBBuildingBuilder` (Putzfarbton je Gebäude) |
| 2 | Rück-/Bremslicht (0,3 = Standlicht, 1 = Bremsen) | `AVBVehicle`, `AVBTrafficVehicle` (Materialparameter `LightChannel` = 2) |
| 3 | Scheinwerfer | dito (`LightChannel` = 3) |
| 4 / 5 | Blinker links / rechts (blinkt 1,5 Hz) | dito (`LightChannel` = 4 / 5) |
| 6–8 | Lackfarbe R, G, B (linear) | dito, nur bei `UsePaintData` = 1 (Material `CarPaint`) |

Fahrzeuge: Pivot = Mitte des Radstands am Boden, X vorne. Räder sind eigene Meshes (`SM_VB_Wheel_<Typ>`,
Achse Y, Felge zeigt nach +Y); linke Räder werden um 180° gedreht. Radreihenfolge überall: VL, VR, HL, HR.
Skelett der fahrbaren Autos: `root` + `wheel_fl`, `wheel_fr`, `wheel_rl`, `wheel_rr` (Karosserie zu 100 % an `root`).

Verkehr (Rechtsverkehr): Fahrspur-Mitte 2,40 m, Parkstreifen 4,55 m, Gehweg-Laufmitte 8,00 m von der
Straßenmitte; Haltelinie 9,35 m, Kreuzungs-Mesh ±9,78 m ab Kreuzungsmitte.

## Actor-Tags

- `VB_Prototype` – Platzhalter, muss vor der Abnahme der Phase ersetzt werden.
- `VB_Generated` – vom Setup-Skript erzeugt, wird beim erneuten Setup neu aufgebaut.
