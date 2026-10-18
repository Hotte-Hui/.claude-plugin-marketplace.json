#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "VBWeatherTypes.h"
#include "VBWorldDeveloperSettings.generated.h"

class UMaterialParameterCollection;

/**
 * Projekteinstellungen der Welt-Simulation (Projekteinstellungen -> Game -> Veyra Bay World).
 * Werte stehen in Config/DefaultEngine.ini unter [/Script/VBWorld.VBWorldDeveloperSettings].
 */
UCLASS(Config = Engine, DefaultConfig, meta = (DisplayName = "Veyra Bay World"))
class VBWORLD_API UVBWorldDeveloperSettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	virtual FName GetCategoryName() const override { return TEXT("Game"); }

	/** Globale Material-Parameter (Naesse, Pfuetzen, Tageszeit ...), von allen Master-Materialien gelesen. */
	UPROPERTY(Config, EditAnywhere, Category = "Global")
	TSoftObjectPtr<UMaterialParameterCollection> WorldParameterCollection;

	/** Reale Minuten fuer einen kompletten 24h-Spieltag. */
	UPROPERTY(Config, EditAnywhere, Category = "Time", meta = (ClampMin = "1.0"))
	float RealMinutesPerGameDay = 48.f;

	UPROPERTY(Config, EditAnywhere, Category = "Time", meta = (ClampMin = "0.0", ClampMax = "24.0"))
	float StartTimeOfDay = 9.f;

	/** Tag im Jahr (1-365), beeinflusst Sonnenhoehe und Tageslaenge. */
	UPROPERTY(Config, EditAnywhere, Category = "Time", meta = (ClampMin = "1", ClampMax = "365"))
	int32 StartDayOfYear = 196;

	/** Geografische Breite der Stadt in Grad (Mittelmeer/Kalifornien ~ 34). */
	UPROPERTY(Config, EditAnywhere, Category = "Time", meta = (ClampMin = "-66.0", ClampMax = "66.0"))
	float Latitude = 34.f;

	/** Drehung von Norden relativ zur +X-Achse der Welt (Grad). */
	UPROPERTY(Config, EditAnywhere, Category = "Time")
	float NorthYawOffset = 0.f;

	UPROPERTY(Config, EditAnywhere, Category = "Weather")
	EVBWeatherType StartWeather = EVBWeatherType::Clear;

	UPROPERTY(Config, EditAnywhere, Category = "Weather", meta = (ClampMin = "0.0"))
	float DefaultWeatherTransitionSeconds = 45.f;

	/** Wetter wechselt automatisch (gewichtete Uebergaenge, tageszeitabhaengig). */
	UPROPERTY(Config, EditAnywhere, Category = "Weather")
	bool bDynamicWeather = true;

	/** Min/Max reale Minuten zwischen automatischen Wetterwechseln. */
	UPROPERTY(Config, EditAnywhere, Category = "Weather")
	FVector2D DynamicWeatherIntervalMinutes = FVector2D(6.0, 14.0);
};
