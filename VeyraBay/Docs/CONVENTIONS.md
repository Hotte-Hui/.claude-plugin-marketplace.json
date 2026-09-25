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

## Actor-Tags

- `VB_Prototype` – Platzhalter, muss vor der Abnahme der Phase ersetzt werden.
- `VB_Generated` – vom Setup-Skript erzeugt, wird beim erneuten Setup neu aufgebaut.
