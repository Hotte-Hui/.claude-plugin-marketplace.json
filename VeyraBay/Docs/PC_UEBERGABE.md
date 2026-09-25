# Übergabe an Claude auf dem Spiele-PC

Diese Datei ist für **Claude Code auf dem PC des Nutzers** (Windows, RTX 4090, Ryzen 9 7950X3D, Unreal Engine 5.8).
Der Nutzer ist kein Entwickler: Bitte selbstständig arbeiten, alles installieren/prüfen/beheben und ihm am Ende in
einfachem Deutsch sagen, was er anklicken soll. Alles Folgende ist bisher **nie auf echter Hardware kompiliert oder
getestet** worden – rechne mit Kompilierfehlern (Engine-API-Details von 5.8) und behebe sie.

## Ziel
1. Projekt `VeyraBay/VeyraBay.uproject` kompiliert fehlerfrei (Editor-Ziel `VeyraBayEditor`, Win64, Development).
2. Setup läuft unbeaufsichtigt durch (Materialien, Import aller Blender-Exporte, Dev-Karte `L_VB_Dev`).
3. Stadt `L_VB_City` ist gebaut (Menüpunkt „4. Stadt bauen“ bzw. Headless-Lauf) und HLODs sind gebaut.
4. Das Spiel startet im Editor (Play) ohne Absturz; Nutzer bekommt kurze Anleitung zum Spielen.
5. Alle Code-Korrekturen committen und auf den Branch `claude/awesome-dirac-a44iul` pushen (Remote: GitHub
   `Hotte-Hui/.claude-plugin-marketplace.json`), damit die Cloud-Sitzung weiterarbeiten kann.

## 1. Voraussetzungen prüfen / installieren
- Unreal Engine 5.8 (Epic Games Launcher). Üblicher Pfad: `C:\Program Files\Epic Games\UE_5.8`.
  Falls anders: in `HKLM\SOFTWARE\EpicGames\Unreal Engine\5.8` (Wert `InstalledDirectory`) nachsehen.
- **Visual Studio 2022** (Community reicht) mit Workload „Spieleentwicklung mit C++“ (`Microsoft.VisualStudio.Workload.NativeGame`),
  MSVC-Toolset und Windows-10/11-SDK. Installation z. B.:
  `winget install Microsoft.VisualStudio.2022.Community --override "--add Microsoft.VisualStudio.Workload.NativeGame --add Microsoft.VisualStudio.Workload.NativeDesktop --includeRecommended --passive --norestart"`
  (Welche Toolset-Version UE 5.8 verlangt, steht bei Fehlern im UBT-Log – dann gezielt nachinstallieren.)
- Git (`winget install Git.Git`), falls nicht vorhanden.
- **Spielfigur**: Das Projekt nutzt das Epic-Mannequin. Falls `Content/Characters/Mannequins` fehlt, aus der Engine-Vorlage
  kopieren: `<UE>\Templates\TP_ThirdPerson\Content\Characters` → `VeyraBay\Content\Characters`
  (und falls vorhanden `...\Content\LevelPrototyping`). Das Setup trägt Mesh + AnimBlueprint dann automatisch ein.

## 2. Kompilieren
```
"<UE>\Engine\Build\BatchFiles\Build.bat" VeyraBayEditor Win64 Development -Project="<Pfad>\VeyraBay\VeyraBay.uproject" -WaitMutex -NoHotReload
```
Fehler beheben, erneut bauen, bis es durchläuft. Hinweise:
- Module: `VBCore`, `VBWorld`, `VeyraBay` (Quellcode unter `Source/`), Plugins in `VeyraBay.uproject` (u. a. ChaosVehiclesPlugin).
- Schattenvariablen, geänderte Engine-Signaturen (Chaos Vehicles, UMG `UTextBlock::GetFont`, `RHIGetGPUFrameCycles`,
  `AActor::SetIsSpatiallyLoaded`, Landschafts-/World-Partition-APIs) sind die wahrscheinlichsten Stellen.
- Verhalten nicht umbauen – nur so ändern, dass es mit 5.8 kompiliert.

## 3. Unbeaufsichtigtes Setup + Stadt
```
set VB_HEADLESS=1
set VB_STEPS=setup,city
"<UE>\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "<Pfad>\VeyraBay\VeyraBay.uproject" -ExecutePythonScript="<Pfad>\VeyraBay\Content\Python\vb_headless.py" -unattended -nosplash -stdout -FullStdOutLogOutput
```
- Ergebnis: `VeyraBay\Saved\VeyraBay_Headless.txt` („OK“ oder Traceback) und `Saved\Logs\VeyraBay.log`.
- Python-Fehler in `Content/Python/*.py` beheben (Unreal-Python-API 5.8), erneut starten. Einzelschritte mit
  `VB_STEPS=setup` bzw. `VB_STEPS=city`.
- Der Stadtbau dauert (ca. 10 900 Gebäude). Danach HLODs bauen:
  `UnrealEditor-Cmd.exe "<uproject>" /Game/VeyraBay/World/Maps/L_VB_City -run=WorldPartitionBuilderCommandlet -Builder=WorldPartitionHLODsBuilder -AllowCommandletRendering`

## 4. Test
- Editor normal öffnen (`UnrealEditor.exe "<uproject>"`), Karte `L_VB_City` laden, Play. Konsole `^`:
  `vb.Benchmark 60 all` → Ergebnis in `Saved/Benchmarks/*.txt`.
- Output Log auf `Error`/`Warning` mit `[VeyraBay]` bzw. `LogVB` prüfen und beheben.
- Checklisten: README Abschnitte 7–7i.

## 5. Zurückmelden
- Änderungen committen (Deutsch, kurz) und auf `claude/awesome-dirac-a44iul` pushen.
- Kurzbericht für den Nutzer (einfaches Deutsch): läuft es, fps aus dem Benchmark, was er selbst tun muss.
- Offene Probleme als Liste in diese Datei unter „Stand“ eintragen.

## Stand
- (noch nicht auf dem PC ausgeführt)
