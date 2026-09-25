#include "VBGraphicsSubsystem.h"

#include "VBLog.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/GameUserSettings.h"
#include "HAL/IConsoleManager.h"
#include "Misc/ConfigCacheIni.h"

namespace VBGraphics
{
	static const TCHAR* ConfigSection = TEXT("/Script/VBCore.VBGraphics");
	static const TCHAR* ConfigKey = TEXT("GraphicsMode");

	struct FCVarSetting
	{
		const TCHAR* Name;
		const TCHAR* Quality;
		const TCHAR* Performance;
	};

	/**
	 * Modusspezifische Renderer-Einstellungen.
	 * Nicht vorhandene CVars (z. B. DLSS ohne Plugin) werden stillschweigend uebersprungen.
	 */
	static const FCVarSetting ModeCVars[] =
	{
		// Temporal Super Resolution: nativ vs. ~67 % Renderaufloesung (entspricht "Quality"-Upscaling)
		{ TEXT("r.AntiAliasingMethod"),                          TEXT("4"),    TEXT("4") },
		{ TEXT("r.ScreenPercentage"),                            TEXT("100"),  TEXT("67") },
		{ TEXT("r.TSR.History.ScreenPercentage"),                TEXT("200"),  TEXT("100") },
		// Lumen: Hardware-RT + Hit-Lighting fuer Reflexionen nur im Quality-Modus
		{ TEXT("r.Lumen.HardwareRayTracing"),                    TEXT("1"),    TEXT("0") },
		{ TEXT("r.Lumen.HardwareRayTracing.LightingMode"),       TEXT("1"),    TEXT("0") },
		// Nanite: Performance-Modus erlaubt etwas groebere Dreiecke
		{ TEXT("r.Nanite.MaxPixelsPerEdge"),                     TEXT("1"),    TEXT("2") },
		// Virtual Shadow Maps: Aufloesungs-Bias (hoeher = guenstiger)
		{ TEXT("r.Shadow.Virtual.ResolutionLodBiasDirectional"), TEXT("-1.5"), TEXT("-0.5") },
		{ TEXT("r.Shadow.Virtual.ResolutionLodBiasLocal"),       TEXT("0"),    TEXT("1") },
		// Volumetrischer Nebel
		{ TEXT("r.VolumetricFog.GridPixelSize"),                 TEXT("8"),    TEXT("16") },
		// Optional: NVIDIA DLSS-Plugin (nur aktiv, wenn installiert)
		{ TEXT("r.NGX.DLSS.Enable"),                             TEXT("1"),    TEXT("1") },
		{ TEXT("r.NGX.DLAA.Enable"),                             TEXT("1"),    TEXT("0") },
	};
}

void UVBGraphicsSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	FString Stored;
	EVBGraphicsMode Mode = EVBGraphicsMode::Quality;
	if (GConfig && GConfig->GetString(VBGraphics::ConfigSection, VBGraphics::ConfigKey, Stored, GGameUserSettingsIni))
	{
		ModeFromString(Stored, Mode);
	}

	SetGraphicsMode(Mode, /*bSave*/ false);
}

void UVBGraphicsSubsystem::SetGraphicsMode(EVBGraphicsMode NewMode, bool bSave)
{
	CurrentMode = NewMode;
	ApplyMode(NewMode);

	if (bSave && GConfig)
	{
		GConfig->SetString(VBGraphics::ConfigSection, VBGraphics::ConfigKey, *ModeToString(NewMode), GGameUserSettingsIni);
		GConfig->Flush(false, GGameUserSettingsIni);
	}

	UE_LOG(LogVB, Log, TEXT("Grafikmodus: %s"), *ModeToString(NewMode));
}

void UVBGraphicsSubsystem::ToggleGraphicsMode()
{
	SetGraphicsMode(CurrentMode == EVBGraphicsMode::Quality ? EVBGraphicsMode::Performance : EVBGraphicsMode::Quality);
}

void UVBGraphicsSubsystem::ApplyMode(EVBGraphicsMode Mode) const
{
	const bool bQuality = (Mode == EVBGraphicsMode::Quality);

	// Globale Skalierbarkeit nur im echten Spiel, nicht im Editor (dort hat der Editor eigene Einstellungen).
	if (!GIsEditor && GEngine)
	{
		if (UGameUserSettings* Settings = GEngine->GetGameUserSettings())
		{
			// 3 = Episch. Sichtweite & Texturen bleiben in beiden Modi maximal (kein Pop-in, 24 GB VRAM).
			const int32 Level = bQuality ? 3 : 2;
			Settings->SetOverallScalabilityLevel(Level);
			Settings->SetViewDistanceQuality(3);
			Settings->SetTextureQuality(3);
			Settings->SetGlobalIlluminationQuality(bQuality ? 3 : 2);
			Settings->SetReflectionQuality(bQuality ? 3 : 2);
			Settings->ApplyNonResolutionSettings();
			Settings->SaveSettings();
		}
	}

	IConsoleManager& ConsoleManager = IConsoleManager::Get();
	for (const VBGraphics::FCVarSetting& Setting : VBGraphics::ModeCVars)
	{
		if (IConsoleVariable* CVar = ConsoleManager.FindConsoleVariable(Setting.Name))
		{
			CVar->Set(bQuality ? Setting.Quality : Setting.Performance, ECVF_SetByGameOverride);
		}
	}
}

FString UVBGraphicsSubsystem::ModeToString(EVBGraphicsMode Mode)
{
	return Mode == EVBGraphicsMode::Quality ? TEXT("Quality") : TEXT("Performance");
}

bool UVBGraphicsSubsystem::ModeFromString(const FString& Text, EVBGraphicsMode& OutMode)
{
	if (Text.Equals(TEXT("Quality"), ESearchCase::IgnoreCase) || Text == TEXT("0"))
	{
		OutMode = EVBGraphicsMode::Quality;
		return true;
	}
	if (Text.Equals(TEXT("Performance"), ESearchCase::IgnoreCase) || Text == TEXT("1"))
	{
		OutMode = EVBGraphicsMode::Performance;
		return true;
	}
	return false;
}

// ---------------------------------------------------------------------------
// Konsolenbefehl: vb.GraphicsMode [Quality|Performance|Toggle]
// ---------------------------------------------------------------------------
static void VBHandleGraphicsModeCommand(const TArray<FString>& Args, UWorld* World)
{
	UGameInstance* GameInstance = World ? World->GetGameInstance() : nullptr;
	UVBGraphicsSubsystem* Graphics = GameInstance ? GameInstance->GetSubsystem<UVBGraphicsSubsystem>() : nullptr;
	if (!Graphics)
	{
		UE_LOG(LogVB, Warning, TEXT("vb.GraphicsMode: nur waehrend des Spiels (PIE/Standalone) verfuegbar."));
		return;
	}

	if (Args.Num() == 0)
	{
		UE_LOG(LogVB, Display, TEXT("Aktueller Grafikmodus: %s  (vb.GraphicsMode Quality|Performance|Toggle)"),
			*UVBGraphicsSubsystem::ModeToString(Graphics->GetGraphicsMode()));
		return;
	}

	if (Args[0].Equals(TEXT("Toggle"), ESearchCase::IgnoreCase))
	{
		Graphics->ToggleGraphicsMode();
		return;
	}

	EVBGraphicsMode Mode;
	if (UVBGraphicsSubsystem::ModeFromString(Args[0], Mode))
	{
		Graphics->SetGraphicsMode(Mode);
	}
	else
	{
		UE_LOG(LogVB, Warning, TEXT("Unbekannter Modus '%s'. Erlaubt: Quality, Performance, Toggle"), *Args[0]);
	}
}

static FAutoConsoleCommandWithWorldAndArgs GVBGraphicsModeCommand(
	TEXT("vb.GraphicsMode"),
	TEXT("Grafikmodus setzen: vb.GraphicsMode Quality|Performance|Toggle"),
	FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&VBHandleGraphicsModeCommand));
