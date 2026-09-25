"""Unbeaufsichtigter Komplettlauf ohne Dialoge: Projekt einrichten (inkl. Import) und optional die Stadt bauen.

Aufruf (Windows, Pfade anpassen):
    set VB_HEADLESS=1
    "C:\\Program Files\\Epic Games\\UE_5.8\\Engine\\Binaries\\Win64\\UnrealEditor-Cmd.exe" ^
        "C:\\VeyraBay\\VeyraBay.uproject" -ExecutePythonScript="C:\\VeyraBay\\Content\\Python\\vb_headless.py" ^
        -unattended -nosplash -stdout -FullStdOutLogOutput

Umgebungsvariable VB_STEPS (Standard "setup,city"): welche Schritte laufen.
Ergebnis steht im Log und in Saved/VeyraBay_Headless.txt ("OK" oder die Fehlermeldung).
"""

import os
import traceback

os.environ["VB_HEADLESS"] = "1"

import unreal  # noqa: E402

import vb_common as vb  # noqa: E402

vb.HEADLESS = True


def main():
    steps = [s.strip() for s in os.environ.get("VB_STEPS", "setup,city").split(",") if s.strip()]
    report = []
    try:
        if "setup" in steps:
            import vb_setup
            vb_setup.run()
            report.append("setup: OK")
        if "import" in steps and "setup" not in steps:
            import vb_import
            vb_import.run(show_dialog=False)
            report.append("import: OK")
        if "city" in steps:
            import vb_city
            stats = vb_city.build(show_dialog=False)
            report.append("city: %s" % ("OK %s" % stats if stats else "uebersprungen (Gelaende fehlt?)"))
        status = "OK"
    except Exception:  # noqa: BLE001
        status = "FEHLER\n" + traceback.format_exc()
        unreal.log_error(status)
    path = os.path.join(unreal.Paths.project_saved_dir(), "VeyraBay_Headless.txt")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(status + "\n" + "\n".join(report) + "\n")
    unreal.log("[VeyraBay] Headless-Lauf: %s -> %s" % (status.splitlines()[0], path))


main()
