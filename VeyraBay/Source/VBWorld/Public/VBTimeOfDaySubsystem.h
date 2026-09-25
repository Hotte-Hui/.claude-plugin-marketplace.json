#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "VBTimeOfDaySubsystem.generated.h"

/** Tagesabschnitte - steuern NPC-Routinen, Verkehrsdichte, Licht und Audio. */
UENUM(BlueprintType)
enum class EVBDayPhase : uint8
{
	Night,		// 22 - 5 Uhr
	Dawn,		// 5 - 7 Uhr
	Morning,	// 7 - 11 Uhr (Pendler, Geschaefte oeffnen)
	Midday,		// 11 - 15 Uhr (hohe Aktivitaet)
	Afternoon,	// 15 - 18 Uhr (Feierabendverkehr)
	Evening		// 18 - 22 Uhr (Restaurants, Nachtleben beginnt)
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FVBOnDayPhaseChanged, EVBDayPhase, NewPhase);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FVBOnHourChanged, int32, NewHour);

/**
 * Zentrale Uhr der Welt: 24h-Zyklus, Sonnen-/Mondstand, Tag-Nacht-Faktor.
 * Einzige "Quelle der Wahrheit" fuer die Zeit - Himmel, KI, Verkehr und Audio lesen hier.
 */
UCLASS()
class VBWORLD_API UVBTimeOfDaySubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

	/** Aktuelle Uhrzeit in Stunden [0, 24). */
	UFUNCTION(BlueprintPure, Category = "VeyraBay|Time")
	float GetTimeOfDay() const { return Hours; }

	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Time")
	void SetTimeOfDay(float NewHours);

	/** Zusaetzlicher Zeitraffer-Faktor (1 = Standard-Tageslaenge aus den Projekteinstellungen). */
	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Time")
	void SetTimeScale(float NewScale);

	UFUNCTION(BlueprintPure, Category = "VeyraBay|Time")
	float GetTimeScale() const { return TimeScale; }

	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Time")
	void SetTimePaused(bool bPaused);

	UFUNCTION(BlueprintPure, Category = "VeyraBay|Time")
	bool IsTimePaused() const { return bTimePaused; }

	UFUNCTION(BlueprintPure, Category = "VeyraBay|Time")
	EVBDayPhase GetDayPhase() const { return Phase; }

	UFUNCTION(BlueprintPure, Category = "VeyraBay|Time")
	int32 GetDayOfYear() const { return DayOfYear; }

	/** Einheitsvektor zur Sonne. */
	UFUNCTION(BlueprintPure, Category = "VeyraBay|Time")
	FVector GetSunDirection() const { return SunDirection; }

	/** Einheitsvektor zum Mond. */
	UFUNCTION(BlueprintPure, Category = "VeyraBay|Time")
	FVector GetMoonDirection() const { return MoonDirection; }

	UFUNCTION(BlueprintPure, Category = "VeyraBay|Time")
	float GetSunElevationDegrees() const { return SunElevation; }

	/** 0 = Tag, 1 = Nacht (weicher Uebergang in der Daemmerung). */
	UFUNCTION(BlueprintPure, Category = "VeyraBay|Time")
	float GetNightFactor() const { return NightFactor; }

	/** Formatierte Uhrzeit, z. B. "18:45". */
	UFUNCTION(BlueprintPure, Category = "VeyraBay|Time")
	FString GetClockString() const;

	static EVBDayPhase PhaseForHour(float InHours);
	static FString PhaseToString(EVBDayPhase InPhase);

	UPROPERTY(BlueprintAssignable, Category = "VeyraBay|Time")
	FVBOnDayPhaseChanged OnDayPhaseChanged;

	UPROPERTY(BlueprintAssignable, Category = "VeyraBay|Time")
	FVBOnHourChanged OnHourChanged;

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	void UpdateDerivedState(bool bBroadcast);

	float Hours = 9.f;
	int32 DayOfYear = 196;
	float Latitude = 34.f;
	float NorthYaw = 0.f;
	float GameHoursPerRealSecond = 24.f / (48.f * 60.f);
	float TimeScale = 1.f;
	bool bTimePaused = false;

	FVector SunDirection = FVector::UpVector;
	FVector MoonDirection = -FVector::UpVector;
	float SunElevation = 45.f;
	float NightFactor = 0.f;
	EVBDayPhase Phase = EVBDayPhase::Morning;
	int32 LastWholeHour = -1;
};
