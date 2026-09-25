#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "VBGraphicsSubsystem.generated.h"

/** Die beiden Grafikmodi des Projekts. */
UENUM(BlueprintType)
enum class EVBGraphicsMode : uint8
{
	/** Maximale Bildqualitaet: HW-Raytracing fuer Lumen, native Aufloesung (TSR/DLAA). */
	Quality,
	/** Hohe Framerate: Software-Lumen, TSR-Upscaling, leicht reduzierte Schatten/Effekte. */
	Performance
};

/**
 * Schaltet zwischen QUALITY und PERFORMANCE um und speichert die Wahl in GameUserSettings.ini.
 * Im Editor (PIE) werden nur die modusspezifischen CVars gesetzt, nicht die globale Skalierbarkeit,
 * damit die Editor-Einstellungen unangetastet bleiben.
 */
UCLASS()
class VBCORE_API UVBGraphicsSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;

	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Graphics")
	void SetGraphicsMode(EVBGraphicsMode NewMode, bool bSave = true);

	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Graphics")
	void ToggleGraphicsMode();

	UFUNCTION(BlueprintPure, Category = "VeyraBay|Graphics")
	EVBGraphicsMode GetGraphicsMode() const { return CurrentMode; }

	static FString ModeToString(EVBGraphicsMode Mode);
	static bool ModeFromString(const FString& Text, EVBGraphicsMode& OutMode);

private:
	void ApplyMode(EVBGraphicsMode Mode) const;

	EVBGraphicsMode CurrentMode = EVBGraphicsMode::Quality;
};
