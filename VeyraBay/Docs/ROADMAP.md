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
| Offen: Schmutz-/Öl-/Laub-Decals, Niagara-Regen, Megascans als optionale Qualitätsstufe | ⏳ |

**Abnahme Phase 2:** siehe README, Abschnitt 7b.

## Phase 3 – Ein kompletter Stadtblock 🟡

| Baustein | Status |
|---|---|
| Neue Oberflächen: Klinker (Läuferverband), Putz (2 Grundtöne je Gebäude), Sandstein, Metallpaneel, Dachkies | ✅ gebacken |
| Fassaden-Kit, 3 Stile × 11 Module (Fenster, Variante, Brandwand, Laden, Tür, EG-Fenster, EG-Brandwand, Gesims, 3 Ecken) | ✅ 38 Module inkl. Dach |
| Dach: Kiesdach-Kachel, Klimageräte, Lüftungsrohre, Antennen, Treppenhausaufbau | ✅ |
| Kreuzung mit Bordsteinradius 3 m, Zebrastreifen, Haltelinien, Plattenecken | ✅ |
| `AVBBuildingBuilder`: Gebäude aus Modulen (Läden/Tür zur Straße, Balkonachsen, Brandwände, Dachaufbauten, Putzfarbe je Gebäude) | 🟡 |
| Fenster-Material `M_VB_Window`: Interior Mapping (Räume, Möbel, Jalousien), nachts uhrzeitabhängig beleuchtete Fenster, Läden tagsüber hell | 🟡 |
| Testkarte: 3 × 3 Blöcke, Mittelblock mit Innenhof, 12 Straßenabschnitte, 4 Kreuzungen, 16 Ampeln (Querrichtung gegenphasig) | 🟡 |
| Fix: FBX-Import spiegelt Y → Kit-Teile werden in Unreal-Koordinaten modelliert (`mirror_to_unreal`) | ✅ |
| Offen: echte begehbare Innenräume (1 Laden, 1 Treppenhaus), Markisen, Werbeschilder mit fiktiven Marken, Graffiti-Decals | ⏳ |

**Abnahme Phase 3:** README, Abschnitt 7c.

## Phase 4 – Ein kleiner Stadtbezirk (Küste) 🟡

| Baustein | Status |
|---|---|
| Gelände 1,6 × 1,6 km als 16 Nanite-Kacheln: Stadtplateau, Hügel, Hafenkai, Sandstrand, Felsküste, Meeresboden | ✅ erzeugt |
| Oberflächen Sand, Gras, Fels (organisch), Rinde; Ozean-Normals + Schaum; Höhenkarte (16 bit) | ✅ gebacken |
| `M_VB_Terrain`: Sand/Gras/Fels nach Höhe und Neigung, Fels seitlich projiziert, Nässe | 🟡 |
| `M_VB_Ocean`: Single Layer Water, zwei Wellenlagen nach Wind, Küstenschaum aus der Höhenkarte | 🟡 |
| `M_VB_Foliage`: maskiert, zweiseitig, Wind aus der MPC (Stärke + Richtung) | 🟡 |
| Straßen-Kit: T-Kreuzung und Ecke (gleicher Generator wie die 4er-Kreuzung) | ✅ |
| Kaimauer (Steinblöcke), Hafenpoller, Promenadengeländer, Promenadenplatten | ✅ |
| Palme und Platane (prozedural, Blatt-/Wedeltexturen mit Alpha) | ✅ |
| `AVBInstancedArray` (generische Instanzen), `vb_district.py`: Ringstraße, 8 T-Kreuzungen, 4 Ecken, Promenade, Bäume | 🟡 |
| Offen: HLOD-Ebenen (Phase 7), Strandzugänge/Treppen, Boote im Hafen, Gras/Büsche (Foliage-Tool) | ⏳ |

**Abnahme Phase 4:** README, Abschnitt 7d.

## Phase 5 – Fahrzeuge + NPCs 🟡

| Baustein | Status |
|---|---|
| Fahrzeug-Generator (Blender): Sportwagen, Limousine, Taxi, SUV, Pickup, Transporter, Bus, Motorrad – fiktive Formen, Radhäuser, Innenraum, Lichtzonen | ✅ erzeugt |
| Je Auto: `SM_` (Verkehr/geparkt), `SK_` mit Radknochen (Chaos), eigenes Rad-Mesh; `vehicles.json` mit Maßen/Masse | ✅ |
| Import: Skeletal Meshes + Physics Asset, `M_VB_Surface` für Skeletal Meshes freigegeben | 🟡 |
| `AVBVehicle` (Chaos): Einsteigen per E, Automatik, Handbremse, Verfolgerkamera (2 Stufen, Rückwärtsblick), Lichtautomatik, Blinker beim Abbiegen, Aufrichten, Nässe senkt den Grip, Tacho | 🟡 |
| `AVBTrafficManager`: Spurgraph aus den Straßen, Abbiegekurven, Ampeln (Gelb-Entscheidung), Linksabbieger warten, Kreuzungen ohne Ampel, IDM-Folgemodell, Dichte nach Uhrzeit/Wetter, Blinker/Bremslicht/Scheinwerfer, parkende Autos | 🟡 |
| `AVBCrowdManager` + `AVBPedestrian`: Gehweg-Graph mit Ecken und Zebrastreifen, Warten bei Rot, Autos halten für Fußgänger, Dichte nach Uhrzeit/Wetter | 🟡 |
| Offen: MetaHuman-Passanten mit Tagesabläufen, Motion Matching, Motorsound, Fahrzeugschäden, Einsteige-Animation | ⏳ |

**Abnahme Phase 5:** README, Abschnitt 7e.

## Phase 6 – Wetter + Tag/Nacht (Ausbau) 🟡

| Baustein | Status |
|---|---|
| `M_VB_Clouds` (Volume): Bedeckung aus der MPC, Wolken ziehen mit dem Wind, flache Haufenwolken bei Schönwetter, hohe geschlossene Decke bei Sturm, Gewitter leuchten von innen | 🟡 |
| Regen: drei Schichten um die Kamera (`M_VB_Rain`, beleuchtet von Sonne, Himmel und Laternen), Neigung im Wind, Deckkraft = Regenstärke | 🟡 |
| Sternenhimmel: 9 000 Sterne mit Farbtemperatur + Milchstraße (`T_VB_Sky_D`), dreht um den Himmelspol, von Wolken/Nebel verdeckt | 🟡 |
| Blitze: Himmelslicht-Blitz (Phase 1) + Wolkenleuchten | 🟡 |
| Offen: Donner (Phase 9 Audio), Scheibenwischer + Tropfen auf der Scheibe, Mondphasen, Niagara-Spritzer, MegaLights-Test | ⏳ |

**Abnahme Phase 6:** README, Abschnitt 7f.

## Phase 7 – Streaming + Open World 🟡

| Baustein | Status |
|---|---|
| `vb_cityplan.py`: Stadtplan als Daten (12 Bezirke, Straßenraster mit Hauptachsen, Küste, Bebauungstypen) – gemeinsame Quelle für Blender und Unreal | ✅ |
| Stadtgelände 7,2 × 4,2 km (84 Nanite-Kacheln, flache Stadtebene zusammengefasst), Hügel, Monte Veyra, Hafenkai/Strand/Marina, Höhenkarte für Meer und Hangbebauung | ✅ erzeugt |
| Bebauung je Typ: Blockrand (Altstadt, Mercato, Nordstadt …), Hochhäuser (Bayfront), Lagerhallen (Hafen), Industrie, Einfamilienhäuser (Weststadt), Campus/Parks, Villen am Hang | ✅ (Blender-Vorschau) |
| `vb_city.py` + `UVBBuildLibrary`: ~1 350 Kreuzungen, ~2 650 Straßen, ~10 900 Gebäude, Ampeln an Hauptachsen, Laternen, Alleen, 5,7 km Uferpromenade in `L_VB_City` (World Partition) | 🟡 |
| Verkehr/Passanten für die offene Welt: Netze werden gebacken, Simulation nur um den Spieler, Ampelphasen aus der Weltzeit | 🟡 |
| Ozean-Material mit austauschbarer Höhenkarte (`MI_VB_OceanCity`) | 🟡 |
| Offen: HLOD-Layer-Feinschliff, Data Layers für Events, Autobahn/Brücken, Kurven- und Hangstraßen, Wahrzeichen je Bezirk | ⏳ |

**Abnahme Phase 7:** README, Abschnitt 7g.

## Phase 8 – Optimierung 🟡

| Baustein | Status |
|---|---|
| `vb.Benchmark [Sekunden] [all]`: Kameraflug (Promenade → Straßenschlucht → Hochhäuser → Marina), CSV + Zusammenfassung in `Saved/Benchmarks`, optional beide Grafikmodi | 🟡 |
| `stat VeyraBay`: Zeiten für Verkehr, Passanten, Himmel/Wetter + Anzahl Fahrzeuge/Passanten; Budgets im Code dokumentiert (`VBStats.h`) | 🟡 |
| Laternen-Licht nur bis 150 m (weich ausgeblendet), Stadtmöbel-Instanzen ab 150 m, Dachaufbauten ab 400 m ausgeblendet | 🟡 |
| Simulation nur um den Spieler (Verkehr 350 m, parkende Autos 220 m, Passanten 160 m), Kreuzungs-/Knotensuche über Raster | 🟡 |
| PSO-Precaching, Textur-Pool 8 GB, World-Partition-Ladebudget | 🟡 |
| Offen: Messwerte vom Ziel-PC (4090 / 7950X3D) auswerten, HLOD-Layer abstimmen, Insights-Profile je Bezirk | ⏳ |

**Abnahme Phase 8:** README, Abschnitt 7h.

## Phase 9 – Polishing 🟡

| Baustein | Status |
|---|---|
| Klänge komplett selbst synthetisiert (`Tools/Audio/vb_audio.py`): Regen leicht/stark, Wind, Meer, Stadt, Vögel, Grillen, 3× Donner, Motor, Reifen, Hupe, Blinker, Schritte, Autotür, UI, Straßenmusik (eigene Gitarrenmusik) | ✅ erzeugt |
| `UVBAudioSubsystem`: Klangkulisse nach Wetter/Tageszeit/Küstenabstand, Donner mit Laufzeit; Motor nach Drehzahl, Reifen nach Tempo, Blinker, Hupe (H), Türen; Schritte für Spieler und nahe Passanten; Motoren im KI-Verkehr | 🟡 |
| Story „Castell Transporte“ (eigene Handlung): Missionen Heimkehr, Lieferrunde (Zeitlimit), Sturmflut (Unwetter); Lichtsäulen-Marker, Dialoge, Timer, Spielstand | 🟡 |
| Dynamische Ereignisse: Panne mit Stau, Straßenmusik, Hafenfest-Feuerwerk (Funken-Instanzen, Lichtblitz, Knall mit Schallverzögerung) | 🟡 |
| Start- und Pausenmenü (UMG in C++): Grafikmodus, dynamisches Wetter, Lautstärke, Mission neu starten, Neues Spiel, Beenden | 🟡 |
| Bezirks-Farbstimmung (`AVBDistrictGrading`), weich überblendet | 🟡 |
| Offen: MetaHuman-Charaktere und Sprachaufnahmen, Common-UI-Styling, Musik-Soundtrack, Niagara-Effekte, weitere Missionen | ⏳ |

**Abnahme Phase 9:** README, Abschnitt 7i.
