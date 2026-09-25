# Veyra Bay – Open-World Vertical Slice (Unreal Engine 5.8)

Eine fiktive Küstenstadt als technisch hochwertiger Open-World-Prototyp.
**Aktueller Stand: Phasen 1–4 umgesetzt: Grundgerüst, hochwertige Straße, Stadtblock, Küstenbezirk mit Gelände, Meer, Promenade und Vegetation.**

| Dokument | Inhalt |
|---|---|
| [Docs/ARCHITECTURE.md](Docs/ARCHITECTURE.md) | Technische Architektur, Module, Datenfluss, Performance-Budgets |
| [Docs/ROADMAP.md](Docs/ROADMAP.md) | Die 9 Phasen mit Status und Abnahmekriterien |
| [Docs/CONVENTIONS.md](Docs/CONVENTIONS.md) | Namens- und Ordnerregeln, Blender-Konventionen |

---

## 1. Voraussetzungen (einmalig)

1. **Unreal Engine 5.8** (Epic Games Launcher) ✔ hast du
2. **Visual Studio 2022** (Community reicht, kostenlos) – beim Installieren diese Workloads anhaken:
   - *Spieleentwicklung mit C++* (dabei rechts **Unreal Engine-Installationsprogramm** anhaken)
   - *Desktopentwicklung mit C++*
   - Unter „Einzelne Komponenten“: das **Windows 11 SDK** (neueste Version) und **.NET 8 (oder neuer) Runtime**

   > Falls Epic für 5.8 eine neuere Visual-Studio-Version verlangt, zeigt Unreal beim Öffnen einen Hinweis – dann diese installieren.
3. ~50 GB freier Platz (Shader-Cache, Build-Dateien).

## 2. Projekt herunterladen

1. Auf GitHub das Repository öffnen → oben den Branch **`claude/awesome-dirac-a44iul`** wählen.
2. **Code → Download ZIP**.
3. ZIP entpacken und **nur den Ordner `VeyraBay`** an einen kurzen Pfad kopieren, z. B. `D:\UE\VeyraBay`
   (Unreal mag keine langen Pfade oder Umlaute im Pfad).

## 3. Projekt öffnen & kompilieren

1. Doppelklick auf **`VeyraBay.uproject`**.
2. Meldung *„The following modules are missing or built with a different engine version … Would you like to rebuild them now?“* → **Ja**.
   Das Kompilieren dauert beim ersten Mal 2–10 Minuten.
3. Falls das fehlschlägt: Rechtsklick auf `VeyraBay.uproject` → **Generate Visual Studio project files** →
   `VeyraBay.sln` öffnen → oben *Development Editor* / *Win64* wählen → **Erstellen → Projektmappe erstellen**.
   Die Fehlermeldungen aus dem Fenster *Ausgabe* bitte an mich schicken – ich behebe sie.

## 4. Spielfigur hinzufügen (1 Klick, einmalig)

Im Editor: **Content Browser → + Hinzufügen → Feature oder Content Pack hinzufügen → Third Person → Zum Projekt hinzufügen.**
Das liefert das Epic-Mannequin mit Animationen (in Phase 5 durch Motion Matching ersetzt).

## 5. Projekt einrichten (automatisch)

In der Menüleiste oben gibt es jetzt **„Veyra Bay“**:

| Menüpunkt | Was passiert |
|---|---|
| **1. Projekt einrichten** | Ordnerstruktur, Master-Material mit Nässe/Pfützen, globale Wetter-Parameter, Import der Blender-Assets, Spielfigur, Testkarte `L_VB_Dev` mit Straße, Gebäuden, Laternen, Kalibrierkugeln und Testtür |
| 2. Assets importieren | Importiert neue Blender-Exporte aus `SourceAssets/Export` (Nanite, Kollision, Materialien automatisch) |
| 3. Assets validieren | Prüft Namen, Ordner, Texturen, Nanite, LODs, Kollision → CSV-Bericht |
| Dev-Karte öffnen | Lädt `L_VB_Dev` |

Danach **Play** (Alt+P). Beim ersten Start werden Shader kompiliert – das kann mit Raytracing 10–30 Minuten dauern (einmalig).

## 6. Steuerung

| Taste | Aktion |
|---|---|
| WASD / linker Stick | Bewegen |
| Maus / rechter Stick | Kamera |
| Shift / L3 | Sprinten |
| Strg / Steuerkreuz ↓ | Gehen an/aus |
| Leertaste / A | Springen |
| E / X | Interagieren (z. B. Testtür) |
| P / Esc | Pause (im Editor beendet Esc die Vorschau – dort P nutzen) |

**Entwickler-Tasten** (nicht im fertigen Spiel):

| Taste | Aktion |
|---|---|
| F2 | Performance-Anzeige durchschalten (Frame-Zeiten → GPU-Aufschlüsselung → aus) |
| F3 | Infos: Uhrzeit, Sonne, Wetter, Nässe, Pfützen, Fahrbahn-Grip, Grafikmodus |
| F5 | Nächste Wetterlage |
| F6 / F7 | Uhrzeit −1 h / +1 h |
| F8 | Tageszeit anhalten |
| F9 | Grafikmodus QUALITY ↔ PERFORMANCE |

**Konsole** (Taste `^`):
`vb.Time 21.5` · `vb.TimeScale 60` · `vb.TimePause` · `vb.Weather HeavyRain 10` · `vb.DynamicWeather 0` · `vb.GraphicsMode Performance`

## 7. Was du jetzt sehen solltest (Phase-1-Abnahme)

- [ ] Projekt kompiliert ohne Fehler
- [ ] Menü „Veyra Bay“ ist da, Setup läuft durch
- [ ] Spielfigur läuft/sprintet die Teststraße entlang
- [ ] F7 mehrfach: Sonne wandert, Abenddämmerung, Nacht → Laternen schalten nacheinander ein
- [ ] F5 bis „HeavyRain“: Straßen werden über ~40 s dunkler und glänzend, Pfützen bilden sich auf flachen Flächen
- [ ] E an der Testtür: Tür schwingt vom Spieler weg auf
- [ ] F9: sichtbarer Wechsel QUALITY/PERFORMANCE, F2 zeigt die Frame-Zeiten

### 7b. Phase-2-Abnahme (Straße)

- [ ] „Veyra Bay → 1. Projekt einrichten“ erneut ausführen – die Karte nutzt dann automatisch das Straßen-Kit
- [ ] 120 m Straße: Fahrbahn mit Wölbung, Markierungen, Zebrastreifen, Bordsteine, Plattengehweg, Kanaldeckel
- [ ] Die zwei Ampeln am Zebrastreifen schalten Grün → Gelb → Rot → Rot-Gelb
- [ ] Nahansicht (0–10 m): Gesteinskörnung im Asphalt, Fugen zwischen Gehwegplatten, Relief auf den Kanaldeckeln
- [ ] F5 bis „HeavyRain“: in den Pfützen erscheinen animierte Tropfenringe
- [ ] Die Fahrbahn wiederholt sich nicht sichtbar (großflächige Helligkeitsvariation)

### 7c. Phase-3-Abnahme (Stadtblock)

- [ ] Nach „1. Projekt einrichten“ steht ein 3 × 3-Stadtraster; Start auf dem Gehweg der südlichen Straße
- [ ] Drei Baustile (Altbau mit Balkonen, Klinker-Loft, Modern), jedes Putzgebäude hat einen eigenen Farbton
- [ ] Hinter den Fenstern sind Räume mit Tiefe, Jalousien und Möbeln zu sehen (Parallaxe beim Vorbeigehen)
- [ ] F7 bis zum Abend: nach und nach gehen Fensterlichter an, Läden sind beleuchtet; spät nachts nur noch wenige Fenster
- [ ] Ampeln an den 4 Kreuzungen: Längs- und Querrichtung schalten gegenläufig
- [ ] Brandwände über niedrigeren Nachbarn, Dachaufbauten sichtbar

### 7d. Phase-4-Abnahme (Küstenbezirk)

- [ ] Start auf der Uferpromenade: Palmenallee, Kaimauer mit Pollern (Hafen, Westen), Geländer am Strand (Osten)
- [ ] Meer: Wellen bewegen sich, Stärke folgt dem Wind (F5 → Sturm), Schaum an Strand und Felsen
- [ ] Gelände: Sand am Wasser, Gras im Hinterland, Fels an Steilhängen; Hügel im Norden
- [ ] Ringstraße mit T-Kreuzungen und Ecken schließt den Bezirk; Platanen am Stadtrand und im Innenhof
- [ ] Palmen und Bäume bewegen sich im Wind

Bitte schick mir **Screenshots** (Tag, Nacht, Regen) und bei Problemen den **Output Log** (Fenster → Output Log).

> **Ehrlicher Hinweis:** Alle Inhalte sind selbst erzeugt (Blender, prozedural) und in Blender gerendert geprüft. In Unreal wurde bisher nichts kompiliert oder getestet – das kann nur auf deinem PC passieren. Rechne beim ersten Kompilieren mit einzelnen Fehlern, die ich dann behebe.

## 8. Blender-Pipeline

- Add-on: `Tools/Blender/vb_blender_export.py` in Blender installieren → Seitenleiste (N) → Reiter **Veyra Bay** → Exportordner auf `<Projekt>/SourceAssets/Export` setzen → **Nach Unreal exportieren**.
- Prozedurale Assets (Beispiel Straßenlaterne):
  `blender -b --factory-startup --python Tools/Blender/assets/vb_asset_streetlight.py -- --out SourceAssets/Export --blend SourceAssets/Blender/SM_VB_StreetLight_A.blend`
- Danach im Editor: **Veyra Bay → 2. Assets importieren**.

Alle Phase-2-Inhalte sind bereits erzeugt und im Repository. Neu erzeugen (Blender 4.2+):

```
blender -b --factory-startup --python Tools/Blender/surfaces/vb_surfaces.py -- --out SourceAssets/Export
blender -b --factory-startup --python Tools/Blender/surfaces/vb_rain_ripples.py -- --out SourceAssets/Export
blender -b --factory-startup --python Tools/Blender/assets/vb_asset_streetkit.py -- --out SourceAssets/Export --blend SourceAssets/Blender/VB_StreetKit.blend
blender -b --factory-startup --python Tools/Blender/assets/vb_asset_streetlight.py -- --out SourceAssets/Export --blend SourceAssets/Blender/SM_VB_StreetLight_A.blend
blender -b --factory-startup --python Tools/Blender/assets/vb_asset_facades.py -- --out SourceAssets/Export --blend SourceAssets/Blender/VB_Facades.blend
blender -b --factory-startup --python Tools/Blender/surfaces/vb_water_textures.py -- --out SourceAssets/Export
blender -b --factory-startup --python Tools/Blender/assets/vb_asset_coast.py -- --out SourceAssets/Export
blender -b --factory-startup --python Tools/Blender/assets/vb_asset_vegetation.py -- --out SourceAssets/Export --blend SourceAssets/Blender/VB_Vegetation.blend
# Vorschau des Stadtblocks (gleiche Logik wie in Unreal):
blender -b --factory-startup --python Tools/Blender/assets/vb_preview_block.py -- --out block.png --view street --textures SourceAssets/Export
blender -b --factory-startup --python Tools/Blender/assets/vb_preview_district.py -- --out promenade.png --textures SourceAssets/Export
```
Hinweis: `vb_preview_district.py` braucht `SourceAssets/Blender/VB_Coast.blend` – dazu `vb_asset_coast.py` einmal mit `--blend SourceAssets/Blender/VB_Coast.blend` ausführen (die Datei ist wegen ihrer Größe nicht im Repository).

Details: [Docs/CONVENTIONS.md](Docs/CONVENTIONS.md).

## 9. Empfohlene kostenlose Inhalte (klare Lizenz)

| Inhalt | Wofür | Lizenz |
|---|---|---|
| **Quixel Megascans** (über Fab, im Editor) | Fotogrammetrie-Oberflächen: Asphalt, Beton, Putz, Decals | Kostenlos für Unreal-Projekte |
| **Game Animation Sample** (Fab) | Motion Matching, 500+ Animationen (Phase 5) | Epic Content License |
| **MetaHuman Creator** | Realistische NPCs (Phase 5) | Kostenlos für Unreal-Projekte |
| **City Sample** (Fab) | Referenz für Mass-Verkehr & Menschenmengen | Epic Content License |
| **NVIDIA DLSS-Plugin** | DLSS / Frame Generation für die RTX 4090 – wird automatisch erkannt | NVIDIA-Lizenz |
