#pragma once

#include "CoreMinimal.h"
#include "VBWeatherTypes.generated.h"

/** Wetterlagen der Stadt. */
UENUM(BlueprintType)
enum class EVBWeatherType : uint8
{
	Clear,
	Overcast,
	LightRain,
	HeavyRain,
	Fog,
	Storm,

	Count UMETA(Hidden)
};

/**
 * Parametersatz einer Wetterlage. Zwischen zwei Zustaenden wird linear interpoliert.
 * Nasse Strassen / Pfuetzen werden NICHT direkt gesetzt, sondern vom Wettersystem
 * aus der Regenintensitaet ueber die Zeit akkumuliert (Straessen trocknen realistisch ab).
 */
USTRUCT(BlueprintType)
struct VBWORLD_API FVBWeatherState
{
	GENERATED_BODY()

	/** 0 = wolkenlos, 1 = geschlossene Wolkendecke. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Weather", meta = (ClampMin = "0", ClampMax = "1"))
	float CloudCoverage = 0.15f;

	/** 0 = trocken, 1 = Starkregen. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Weather", meta = (ClampMin = "0", ClampMax = "1"))
	float RainIntensity = 0.f;

	/** Multiplikator auf die Basis-Nebeldichte. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Weather", meta = (ClampMin = "0"))
	float FogDensityScale = 1.f;

	/** 0 = windstill, 1 = Sturm. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Weather", meta = (ClampMin = "0", ClampMax = "1"))
	float WindStrength = 0.2f;

	/** Anteil des direkten Sonnenlichts, das durch die Wolken kommt. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Weather", meta = (ClampMin = "0", ClampMax = "1"))
	float SunTransmission = 1.f;

	/** Blitze pro Minute (nur Sturm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Weather", meta = (ClampMin = "0"))
	float LightningPerMinute = 0.f;

	static FVBWeatherState Lerp(const FVBWeatherState& A, const FVBWeatherState& B, float Alpha);
	static FVBWeatherState GetPreset(EVBWeatherType Type);
};

namespace VBWeather
{
	VBWORLD_API FString ToString(EVBWeatherType Type);
	VBWORLD_API bool FromString(const FString& Text, EVBWeatherType& OutType);
}
