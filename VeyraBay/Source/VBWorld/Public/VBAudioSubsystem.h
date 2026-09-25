#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "VBAudioSubsystem.generated.h"

class UAudioComponent;
class USoundBase;

/**
 * Klangkulisse (Phase 9): 2D-Schleifen fuer Regen (leicht/stark), Wind, Meer, Stadt, Voegel, Grillen - Lautstaerken folgen
 * Wetter, Tageszeit und Abstand des Zuhoerers zur Kueste. Donner folgt dem Blitz mit Laufzeitverzoegerung.
 * Klaenge: /Game/VeyraBay/Audio/SW_VB_* (synthetisiert von Tools/Audio/vb_audio.py).
 */
UCLASS()
class VBWORLD_API UVBAudioSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

	/** Gemeinsamer Loader fuer alle Klaenge (Name ohne Prefix, z. B. "Engine"). */
	static USoundBase* LoadSound(const TCHAR* Name);

	/** Schrittgeraeusch (zufaellige Variante, leicht variierte Tonhoehe) an einer Position. */
	static void PlayFootstep(const UObject* WorldContext, const FVector& Location, float Volume);

	/** Schritte aus der zurueckgelegten Strecke: liefert true, wenn ein Schritt faellig war. */
	static bool AdvanceStride(float& InOutDistance, float Speed, float DeltaSeconds);

	/** Gesamtlautstaerke der Umgebung (Einstellungsmenue). */
	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Audio")
	void SetAmbientVolume(float Volume) { AmbientVolume = FMath::Clamp(Volume, 0.f, 1.f); }

	UFUNCTION(BlueprintPure, Category = "VeyraBay|Audio")
	float GetAmbientVolume() const { return AmbientVolume; }

	/** Y-Koordinate der Kaimauer (cm) - Meeresrauschen wird zur Kueste hin lauter. */
	float CoastY = -9412.f;

private:
	enum ELoop : uint8 { RainLight, RainHeavy, Wind, Sea, City, Birds, Crickets, LoopCount };

	UPROPERTY(Transient)
	TArray<TObjectPtr<UAudioComponent>> Loops;

	UPROPERTY(Transient)
	TArray<TObjectPtr<USoundBase>> ThunderSounds;

	TArray<float> CurrentVolume;
	float AmbientVolume = 1.f;
	float LastFlash = 0.f;
	TArray<float> PendingThunder;      // Restzeit bis zum Donner (s)
	bool bStarted = false;
};
