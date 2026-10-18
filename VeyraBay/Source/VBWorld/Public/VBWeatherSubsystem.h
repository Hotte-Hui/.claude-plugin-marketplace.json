#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "VBWeatherTypes.h"
#include "VBWeatherSubsystem.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FVBOnWeatherChanged, EVBWeatherType, NewWeather);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FVBOnLightningStrike);

/**
 * Dynamisches Wettersystem.
 * - Weiche Uebergaenge zwischen Wetterlagen
 * - Oberflaechennaesse & Pfuetzen werden aus dem Regen akkumuliert und trocknen langsam ab
 * - Schreibt alles in die globale MPC, damit Materialien, Himmel, Fahrzeuge und Audio reagieren
 * - Optional automatischer Wetterwechsel (tageszeitabhaengige Wahrscheinlichkeiten)
 */
UCLASS()
class VBWORLD_API UVBWeatherSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

	/** Wetter wechseln. TransitionSeconds < 0 = Standarddauer aus den Projekteinstellungen. */
	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Weather")
	void SetWeather(EVBWeatherType NewWeather, float TransitionSeconds = -1.f);

	/** Zur naechsten Wetterlage schalten (Debug). */
	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Weather")
	void CycleWeather();

	UFUNCTION(BlueprintPure, Category = "VeyraBay|Weather")
	EVBWeatherType GetWeather() const { return TargetWeather; }

	UFUNCTION(BlueprintPure, Category = "VeyraBay|Weather")
	FVBWeatherState GetCurrentState() const { return CurrentState; }

	/** Oberflaechennaesse 0..1 (Strassen, Fassaden, Fahrbahn-Grip). */
	UFUNCTION(BlueprintPure, Category = "VeyraBay|Weather")
	float GetWetness() const { return Wetness; }

	/** Pfuetzenmenge 0..1 (sammelt sich langsamer als Naesse, trocknet langsamer ab). */
	UFUNCTION(BlueprintPure, Category = "VeyraBay|Weather")
	float GetPuddles() const { return Puddles; }

	/** Aktuelle Blitzhelligkeit 0..1 (fuer Himmel, Licht, Audio). */
	UFUNCTION(BlueprintPure, Category = "VeyraBay|Weather")
	float GetLightningFlash() const { return LightningFlash; }

	/** Windrichtung (normiert, XY). */
	UFUNCTION(BlueprintPure, Category = "VeyraBay|Weather")
	FVector GetWindDirection() const { return WindDirection; }

	/** Faktor fuer Reifenhaftung (1 = trocken). Wird in Phase 5 vom Fahrzeugsystem genutzt. */
	UFUNCTION(BlueprintPure, Category = "VeyraBay|Weather")
	float GetRoadGripMultiplier() const;

	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Weather")
	void SetDynamicWeatherEnabled(bool bEnabled);

	UFUNCTION(BlueprintPure, Category = "VeyraBay|Weather")
	bool IsDynamicWeatherEnabled() const { return bDynamicWeather; }

	UPROPERTY(BlueprintAssignable, Category = "VeyraBay|Weather")
	FVBOnWeatherChanged OnWeatherChanged;

	UPROPERTY(BlueprintAssignable, Category = "VeyraBay|Weather")
	FVBOnLightningStrike OnLightningStrike;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	void UpdateSurfaceWater(float DeltaTime);
	void UpdateLightning(float DeltaTime);
	void UpdateDynamicWeather(float DeltaTime);
	void ScheduleNextDynamicChange();
	EVBWeatherType PickNextWeather() const;
	void PushToMaterialParameters();

	EVBWeatherType TargetWeather = EVBWeatherType::Clear;
	FVBWeatherState FromState;
	FVBWeatherState TargetState;
	FVBWeatherState CurrentState;
	float TransitionDuration = 0.f;
	float TransitionElapsed = 0.f;

	float Wetness = 0.f;
	float Puddles = 0.f;
	float LightningFlash = 0.f;
	float LightningCooldown = 0.f;
	FVector WindDirection = FVector(0.7, 0.7, 0.0);
	float WindPhase = 0.f;

	bool bDynamicWeather = true;
	float SecondsUntilDynamicChange = 600.f;
	float DefaultTransitionSeconds = 45.f;
};
