"""Erzeugt ALLE Spielinhalte (Modelle, Texturen, Gelaende, Fahrzeuge, Klaenge) neu nach SourceAssets/Export.

Braucht nur Blender 4.5 LTS (kostenlos, z. B. `winget install BlenderFoundation.Blender.LTS.4.5`).

    python Tools/generate_all.py [--blender "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe"]

Ohne --blender wird Blender im PATH bzw. an den ueblichen Windows-Installationsorten gesucht.
Dauer: je nach PC etwa 20-60 Minuten (Oberflaechen werden mit Cycles gebacken).
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import time

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (Skript, zusaetzliche Argumente) - Reihenfolge wichtig: Oberflaechen vor den Modellen, Kueste/Vegetation vor Vorschauen
STEPS = [
    ("Tools/Blender/surfaces/vb_surfaces.py", []),
    ("Tools/Blender/surfaces/vb_rain_ripples.py", []),
    ("Tools/Blender/surfaces/vb_water_textures.py", []),
    ("Tools/Blender/surfaces/vb_sky_textures.py", []),
    ("Tools/Blender/assets/vb_asset_streetkit.py", ["--blend", "SourceAssets/Blender/VB_StreetKit.blend"]),
    ("Tools/Blender/assets/vb_asset_streetlight.py", ["--blend", "SourceAssets/Blender/SM_VB_StreetLight_A.blend"]),
    ("Tools/Blender/assets/vb_asset_facades.py", ["--blend", "SourceAssets/Blender/VB_Facades.blend"]),
    ("Tools/Blender/assets/vb_asset_coast.py", ["--blend", "SourceAssets/Blender/VB_Coast.blend"]),
    ("Tools/Blender/assets/vb_asset_vegetation.py", ["--blend", "SourceAssets/Blender/VB_Vegetation.blend"]),
    ("Tools/Blender/assets/vb_asset_vehicles.py", ["--blend", "SourceAssets/Blender/VB_Vehicles.blend"]),
    ("Tools/Blender/assets/vb_asset_weather.py", []),
    ("Tools/Blender/assets/vb_asset_cityterrain.py", []),
    ("Tools/Audio/vb_audio.py", []),
]


def find_blender(explicit):
    if explicit:
        return explicit
    found = shutil.which("blender")
    if found:
        return found
    candidates = sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender*\blender.exe"), reverse=True)
    if candidates:
        return candidates[0]
    sys.exit("Blender nicht gefunden. Installieren: winget install BlenderFoundation.Blender.LTS.4.5 (oder --blender angeben)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender")
    parser.add_argument("--out", default="SourceAssets/Export")
    args = parser.parse_args()
    blender = find_blender(args.blender)
    os.makedirs(os.path.join(PROJECT, "SourceAssets", "Blender"), exist_ok=True)
    os.makedirs(os.path.join(PROJECT, args.out), exist_ok=True)
    started = time.time()
    failed = []
    for index, (script, extra) in enumerate(STEPS, 1):
        print("[%d/%d] %s" % (index, len(STEPS), script), flush=True)
        cmd = [blender, "-b", "--factory-startup", "--python", os.path.join(PROJECT, script), "--", "--out",
               os.path.join(PROJECT, args.out)] + [os.path.join(PROJECT, a) if a.startswith("SourceAssets") else a for a in extra]
        result = subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True, errors="replace")
        log = result.stdout + result.stderr
        if result.returncode != 0 or "Traceback" in log:
            failed.append(script)
            print(log[-3000:])
            print("  -> FEHLER", flush=True)
        else:
            print("  -> ok (%.0f s gesamt)" % (time.time() - started), flush=True)
    print("Fertig in %.1f min. %s" % ((time.time() - started) / 60.0, "Fehler: " + ", ".join(failed) if failed else "Alles erzeugt."))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
