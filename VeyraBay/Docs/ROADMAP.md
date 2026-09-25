# Veyra Bay – Roadmap

Jede Phase muss auf dem Zielrechner funktionieren (Abnahme), bevor die nächste beginnt.
Legende: ✅ fertig · 🟡 umgesetzt, wartet auf Test am PC · ⏳ offen

## Phase 1 – Technisches Grundgerüst 🟡

| Baustein | Status |
|---|---|
| Projektdatei, Module (VBCore, VBWorld, VeyraBay), Renderer-Konfiguration (Lumen, Nanite, VSM, HW-RT, TSR, DX12/SM6) | 🟡 |
| Grafikmodi QUALITY/PERFORMANCE (+ automatische DLSS-Erkennung) | 🟡 |
| 24-h-Zyklus mit astronomischem Sonnen-/Mondstand | 🟡 |
| Wettersystem (6 Lagen, Übergänge, Nässe/Pfützen, Blitze, automatischer Wechsel) | 🟡 |
| Himmel/Licht/Nebel/Belichtung (physikalische Einheiten) | 🟡 |
| Master-Material mit globaler Nässe, Pfützen, Emissive + Dämmerungsschalter | 🟡 |
| Spielfigur, Enhanced Input, Interaktionssystem, Testtür, Prototyp-HUD | 🟡 |
| Editor-Tools: Setup, Import-Automatisierung, Validierung (Python) | 🟡 |
| Blender-Pipeline: Export-Add-on mit Validierung + Metadaten | ✅ (in Blender 4.5 getestet) |

**Abnahme:** siehe README, Abschnitt 7.

## Phase 2 – Eine extrem hochwertige Straße 🟡

| Baustein | Status |
|---|---|
| Gebackene, nahtlos kachelnde PBR-Oberflächen: Asphalt (2K), Beton, Granit, Gusseisen, Holz | ✅ in Blender gebacken und geprüft |
| Straßen-Kit: Fahrbahn 10 m (Wölbung, Rinnen, Markierungen), Zebrastreifen-Variante, Granit-Bordstein, Gehweg aus 45 Einzelplatten | ✅ |
| Stadtmöbel: Kanaldeckel, Poller, Bank, Mülleimer, Hydrant, Halteverbotsschild, Ampel + Signallinse, LED-Laterne | ✅ |
| `AVBStreetBuilder`: Straße prozedural per Instanced Static Meshes, Stadtmöbel-Regeln, Kanaldeckel folgen der Fahrbahnwölbung | 🟡 |
| `AVBTrafficLight`: Ampelphasen Grün/Gelb/Rot/Rot-Gelb, Linsen per Custom Primitive Data, Event für den Verkehr | 🟡 |
| Master-Material: Anti-Tiling-Makrovariation, animierte Regenkräuseln in Pfützen | 🟡 |
| Import: gemeinsame Oberflächen-Materialien `MI_VB_Surface_<Name>` statt Texturduplikaten | 🟡 |
| Testkarte: 120 m Straße mit Zebrastreifen, 2 Ampeln, 9 Laternen, Stadtmöbeln | 🟡 |
| Offen: Schmutz-/Öl-/Laub-Decals, Niagara-Regen, Megascans als optionale Qualitätsstufe, Fassaden (→ Phase 3) | ⏳ |

**Abnahme Phase 2:** siehe README, Abschnitt 7b.

## Phase 3 – Ein kompletter Stadtblock ⏳
Modulare Fassaden-Kits (3 Baustile), Dächer mit Klimaanlagen/Antennen, Hinterhof, Gasse, Innenräume (1 Laden, 1 Treppenhaus), Fensterlicht nachts.

## Phase 4 – Ein kleiner Stadtbezirk ⏳
Straßennetz per Splines + PCG, 6–10 Blöcke, Küstenabschnitt mit Wasser (Water-Plugin), Landschaft/Heightmap, erste HLODs.

## Phase 5 – Fahrzeuge + NPCs ⏳
Chaos Vehicles (8 fiktive Modelle), Mass-Verkehr mit Ampeln, MetaHuman-NPCs mit Tagesabläufen, Motion Matching, Ein-/Aussteigen.

## Phase 6 – Wetter + Tag/Nacht (Ausbau) ⏳
Eigenes Wolkenmaterial (Bedeckung aus MPC), Niagara-Regen/Nebel/Sturm, Blitze mit Licht und Donner, Scheibenwischer, Sterne, Mondphasen, MegaLights für viele Stadtlichter.

## Phase 7 – Streaming + Open World ⏳
Alle 12 Bezirke als Blockout, World-Partition-Zellen, Data Layers für Events, HLOD für die Fernsicht, Autobahnnetz.

## Phase 8 – Optimierung ⏳
Automatischer Benchmark-Kameraflug, Insights-Profile, Budgets je System, Shader-Vorkompilierung (PSO-Cache).

## Phase 9 – Polishing ⏳
Common-UI-Menüs, Audio-Mix, Story-Vertical-Slice (3 Missionen), dynamische Stadt-Events, Color Grading pro Bezirk.
