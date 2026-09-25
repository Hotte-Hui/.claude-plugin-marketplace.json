# Veyra Bay – Technische Architektur

## 1. Leitprinzipien

1. **Engine-native vor Eigenbau** – Lumen, Nanite, VSM, World Partition, Mass, StateTree, Smart Objects, Chaos, MetaHuman, Motion Matching.
2. **Eine Quelle der Wahrheit pro Systemzustand** – Uhrzeit nur im `UVBTimeOfDaySubsystem`, Wetter nur im `UVBWeatherSubsystem`. Alle anderen lesen.
3. **Daten statt Sonderfälle** – Wetterlagen, Fahrzeuge, NPC-Tagesabläufe, Bezirke als Daten.
4. **Materialien reagieren global** – eine Material Parameter Collection (`MPC_VB_World`) verteilt Nässe, Pfützen, Wind, Tageszeit an jedes Material, ohne Blueprints und ohne dynamische Materialinstanzen.
5. **Budgets zuerst** – jede Funktion hat ein Frame-Budget; Prototypen werden markiert (`VB_Prototype`) und ersetzt.
6. **Automatisierung** – Import, Materialerzeugung, Kollision, Nanite/LOD und Validierung laufen über Skripte.

## 2. Code-Module

```
VBCore        Log, Grafikmodi (Quality/Performance), später: Performance-Statistiken, Gameplay Tags
  ▲
VBWorld       Tageszeit, Sonnenstand, Wetter, globale Material-Parameter, Himmel, Straßenlaternen
  ▲
VeyraBay      Spielmodus, Spielfigur, Eingabe, Interaktion, HUD, Türen
  ▲
(geplant)     VBVehicles · VBTraffic · VBCrowd · VBNarrative · VBUI · VBAudio · VBEditor
```

Abhängigkeiten zeigen nur nach unten. Neue Systeme bekommen ein eigenes Modul, sobald sie mehr als eine Handvoll Klassen haben.

| Klasse | Modul | Aufgabe |
|---|---|---|
| `UVBGraphicsSubsystem` | VBCore | QUALITY/PERFORMANCE-Umschaltung (Skalierbarkeit + Renderer-CVars, DLSS falls vorhanden), gespeichert in GameUserSettings |
| `UVBTimeOfDaySubsystem` | VBWorld | 24-h-Uhr, astronomischer Sonnen-/Mondstand (Breitengrad, Tag im Jahr), Tagesabschnitte + Events |
| `UVBWeatherSubsystem` | VBWorld | 6 Wetterlagen, weiche Übergänge, akkumulierte Nässe/Pfützen, Blitze, automatischer Wetterwechsel (Markov-Kette, tageszeitabhängig), Fahrbahn-Grip |
| `AVBSkyEnvironment` | VBWorld | Sonne (Lux), Mond, Sky Atmosphere, Echtzeit-Skylight, Volumetric Clouds, Höhennebel + volumetrischer Nebel, Post-Processing mit physikalischer Belichtung, Editor-Vorschau |
| `UVBNightLightComponent` | VBWorld | Dämmerungsschalter für alle Lichter eines Actors + Custom Primitive Data für Emissive-Materialien |
| `AVBStreetLight` | VBWorld | Straßenlaterne (3000 cd, 3800 K, volumetrisch), nutzt das Blender-Modell, falls gesetzt |
| `AVBStreetBuilder` | VBWorld | Gerade Straße aus dem Kit per Instanced Static Meshes, Regeln für Stadtmöbel, Fahrbahnhöhe `GetRoadSurfaceHeight()` |
| `AVBTrafficLight` | VBWorld | Ampelzyklus, Linsen über Custom Primitive Data, `OnSignalChanged` / `AllowsPassage()` für den Verkehr |
| `AVBPlayerCharacter` | VeyraBay | Third-Person-Figur mit realistischen Geschwindigkeiten, Sprint-FOV, Interaktion |
| `UVBInputSet` | VeyraBay | Enhanced-Input-Aktionen zur Laufzeit (Tastatur/Maus + Gamepad, Entwickler-Tasten) |
| `IVBInteractable` / `UVBInteractionComponent` | VeyraBay | Einheitliches Interaktionssystem für Türen, Schalter, Automaten, NPCs, Fahrzeuge |
| `AVBHUD` | VeyraBay | Prototyp-HUD (wird durch Common UI ersetzt) |

## 3. Datenfluss Welt-Simulation

```
                ┌──────────────────────────┐
 Projekt-       │ UVBWorldDeveloperSettings │  Tageslänge, Breitengrad, Startwetter ...
 einstellungen  └────────────┬─────────────┘
                             ▼
┌───────────────────────┐        ┌────────────────────────┐
│ UVBTimeOfDaySubsystem │───────▶│ UVBWeatherSubsystem    │ (Nebel morgens wahrscheinlicher)
│ Uhrzeit, Sonne, Mond, │        │ Zustand, Nässe,        │
│ NightFactor, Phase    │        │ Pfützen, Wind, Blitze  │
└──────────┬────────────┘        └───────────┬────────────┘
           │   schreiben                     │
           ▼                                 ▼
     ┌────────────────────── MPC_VB_World ──────────────────────┐
     │ TimeOfDay01 NightFactor SunElevation Wetness Puddles ...  │──▶ alle Materialien (M_VB_Surface)
     └───────────────────────────────────────────────────────────┘
           │ lesen                           │ lesen
           ▼                                 ▼
   AVBSkyEnvironment               UVBNightLightComponent, HUD,
   (Licht, Nebel, Belichtung)      später: Verkehr, NPCs, Audio, Fahrphysik
```

## 4. Rendering

| Bereich | Entscheidung | Begründung |
|---|---|---|
| Globale Beleuchtung | Lumen, voll dynamisch, keine statische Beleuchtung | 24-h-Zyklus und Wetter schließen Lightmaps aus |
| Reflexionen | Lumen, im Quality-Modus Hardware-RT mit Hit-Lighting | Nasse Straßen und Glas brauchen genaue Reflexionen |
| Schatten | Virtual Shadow Maps; Sonne wird erst ab 0,1° Bewegung nachgeführt | Schont den VSM-Cache bei langsamer Sonnenbewegung |
| Geometrie | Nanite für alle statischen Meshes über ~500 Dreiecke | Echte geometrische Details, keine LOD-Pop-ins |
| Belichtung | Physikalische Einheiten: Sonne ~110.000 lux, Mond ~0,6 lux, Laternen in Candela; Auto-Belichtung EV100 −3…16 | Richtige Verhältnisse zwischen Tag, Nacht und Kunstlicht |
| AA / Upscaling | TSR (Quality nativ, Performance ~67 %); DLSS/DLAA automatisch, wenn das Plugin installiert ist | Beste Qualität je Hardware |
| Wetter auf Oberflächen | Master-Material: Porositäts-Abdunklung, Rauheit → 0,12, Pfützen weltbasiert nur auf flachen Flächen, glatte Normalen mit animierten Regenkräuseln (4×4-Flipbook) | Straßen reagieren glaubwürdig und ohne Zusatzkosten pro Objekt |
| Anti-Tiling | Weltbasierte Makrovariation (23-m-Rauschen) auf jeder Oberfläche | Kachelnde Texturen wiederholen sich nicht sichtbar |
| Straßen & Möbel | Eigene Blender-Kits mit echter Geometrie (Fasen, Einzelplatten, Relief), Instanced Static Meshes + Nanite | Nahbereich-Detail bei minimalen Draw Calls |

## 5. Welt & Streaming (ab Phase 3/7)

- **World Partition**: Zellen ~128 m (nah), HLOD-Ebenen: Instancing → zusammengeführte Meshes → vereinfachte Silhouetten für die Fernsicht.
- **Data Layers**: Events (Baustelle, Unfall, Stadtfest), Innenräume, wetterabhängige Details.
- **Bezirke**: `World/Districts/<Bezirk>`, jeweils mit eigenen Daten zu Dichte (Verkehr/NPC), Soundscape, Fassaden-Kits, Materialvarianten.
- **Straßennetz**: Spline-basiert; dieselben Daten erzeugen Geometrie (PCG), ZoneGraph-Spuren für Verkehr und Fußgänger.

## 6. Geplante Systeme (Phasen 5–9)

| System | Technik |
|---|---|
| Fahrzeuge | Chaos Vehicles, Datenprofile pro Fahrzeug (Masse, Drehmomentkurve, Federung, Bremsen); Grip aus `GetRoadGripMultiplier()` |
| Verkehr | Mass Entity + ZoneGraph; nah: vollwertige Chaos-Fahrzeuge, fern: leichte Mass-Einträge; Ampel-Prozessoren |
| NPCs | Mass Crowd (fern) → Skeletal Mesh (mittel) → MetaHuman + StateTree + Smart Objects (nah); Tagesabläufe über `OnDayPhaseChanged` |
| Animation | Motion Matching (PoseSearch), Motion Warping (Ein-/Aussteigen), IK Rig, Control Rig |
| Audio | MetaSounds, Soundscape pro Bezirk × Wetter × Tageszeit, Convolution Reverb in Innenräumen |
| UI | Common UI (animiert): Hauptmenü, Pause, Einstellungen, Karte, Missionen, Fahrzeug-HUD, Speichern/Laden |
| Story | Eigene Figuren/Fraktionen, Dialog- und Missionssystem als Daten; dynamische Stadt-Events |

## 7. Performance-Budgets (Referenz RTX 4090, 1440p)

| | QUALITY | PERFORMANCE |
|---|---|---|
| Ziel-FPS | 60 | 100+ |
| GPU | ≤ 16 ms | ≤ 9 ms |
| Game Thread | ≤ 8 ms | ≤ 8 ms |
| KI (Verkehr + NPCs) | ≤ 2 ms | ≤ 2 ms |
| VRAM | ≤ 14 GB | ≤ 10 GB |

Gemessen wird mit `stat unit`, `stat gpu` (F2), Unreal Insights und ab Phase 8 mit einem automatischen Kameraflug-Benchmark.
