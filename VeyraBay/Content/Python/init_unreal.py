"""Wird beim Editor-Start automatisch ausgefuehrt: registriert das Menue "Veyra Bay"."""

import unreal

MENU_OWNER = "VeyraBayTools"

ENTRIES = [
    ("VB_Setup", "1. Projekt einrichten",
     "Ordner, Master-Material, globale Parameter, Spielfigur und Dev-Karte automatisch anlegen.",
     "import importlib, vb_common, vb_import, vb_materials_nature, vb_district, vb_setup; [importlib.reload(m) for m in (vb_common, vb_import, vb_materials_nature, vb_district, vb_setup)]; vb_setup.run()"),
    ("VB_Import", "2. Assets importieren (Blender-Export)",
     "Alle Exporte aus SourceAssets/Export importieren (Nanite, Kollision, Materialien).",
     "import importlib, vb_common, vb_import; importlib.reload(vb_common); importlib.reload(vb_import); vb_import.run()"),
    ("VB_Validate", "3. Assets validieren",
     "Namen, Ordner, Texturen, Nanite, LODs und Kollision pruefen.",
     "import importlib, vb_common, vb_validate; importlib.reload(vb_common); importlib.reload(vb_validate); vb_validate.run()"),
    ("VB_OpenDevMap", "Dev-Karte oeffnen",
     "L_VB_Dev laden.",
     "import unreal; unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/VeyraBay/World/Maps/L_VB_Dev')"),
]


def register_menu():
    menus = unreal.ToolMenus.get()
    main_menu = menus.find_menu("LevelEditor.MainMenu")
    if main_menu is None:
        unreal.log_warning("[VeyraBay] Hauptmenue nicht gefunden - Menue nicht registriert.")
        return

    vb_menu = main_menu.add_sub_menu(MENU_OWNER, "", "VeyraBay", "Veyra Bay", "Veyra Bay Werkzeuge")
    for name, label, tooltip, command in ENTRIES:
        entry = unreal.ToolMenuEntry(name=name, type=unreal.MultiBlockType.MENU_ENTRY)
        entry.set_label(label)
        entry.set_tool_tip(tooltip)
        entry.set_string_command(unreal.ToolMenuStringCommandType.PYTHON, "", command)
        vb_menu.add_menu_entry("VeyraBay", entry)

    menus.refresh_all_widgets()
    unreal.log("[VeyraBay] Menue 'Veyra Bay' registriert.")


try:
    register_menu()
except Exception as exc:  # noqa: BLE001
    unreal.log_error("[VeyraBay] Menue-Registrierung fehlgeschlagen: %s" % exc)
