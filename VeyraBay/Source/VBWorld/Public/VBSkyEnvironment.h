#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VBWeatherTypes.h"
#include "VBSkyEnvironment.generated.h"

class UDirectionalLightComponent;
class USkyAtmosphereComponent;
class USkyLightComponent;
class UVolumetricCloudComponent;
class UExponentialHeightFogComponent;
class UPostProcessComponent;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;

/**
 * Komplette physikalisch basierte Himmels- und Lichtumgebung in einem Actor:
 * Sonne (Lux), Mond, Sky Atmosphere, Echtzeit-Skylight, volumetrische Wolken,
 * Hoehennebel mit volumetrischem Nebel und Post-Processing mit Auto-Belichtung.
 *
 * Im Spiel folgt er Tageszeit- und Wettersystem, im Editor zeigt er eine Vorschau
 * (PreviewTimeOfDay / PreviewWeather im Details-Panel).
 */
UCLASS(ClassGroup = (VeyraBay), meta = (DisplayName = "VB Sky Environment"))
class VBWORLD_API AVBSkyEnvironment : public AActor
{
	GENERATED_BODY()

public:
	AVBSkyEnvironment();

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	// --- Komponenten -------------------------------------------------------
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UDirectionalLightComponent> SunLight;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UDirectionalLightComponent> MoonLight;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USkyAtmosphereComponent> SkyAtmosphere;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USkyLightComponent> SkyLight;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UVolumetricCloudComponent> Clouds;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UExponentialHeightFogComponent> HeightFog;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UPostProcessComponent> PostProcess;

	// --- Editor-Vorschau ---------------------------------------------------
	UPROPERTY(EditAnywhere, Category = "Editor Preview", meta = (ClampMin = "0.0", ClampMax = "24.0", UIMin = "0.0", UIMax = "24.0"))
	float PreviewTimeOfDay = 10.f;

	UPROPERTY(EditAnywhere, Category = "Editor Preview")
	EVBWeatherType PreviewWeather = EVBWeatherType::Clear;

	// --- Licht (physikalische Einheiten) ------------------------------------
	/** Beleuchtungsstaerke der Sonne bei klarem Himmel in Lux (Atmosphaere daempft zusaetzlich). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Lighting", meta = (ClampMin = "0.0"))
	float SunIlluminanceLux = 110000.f;

	/** Vollmond ~0.3 lux; fuer Spielbarkeit leicht angehoben. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Lighting", meta = (ClampMin = "0.0"))
	float MoonIlluminanceLux = 0.6f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Lighting")
	FLinearColor MoonColor = FLinearColor(0.72f, 0.82f, 1.0f);

	/** Sonne wird erst nachgefuehrt, wenn sie sich um mehr als diesen Winkel bewegt hat (schont den VSM-Cache). */
	UPROPERTY(EditAnywhere, Category = "Lighting|Performance", meta = (ClampMin = "0.0"))
	float SunUpdateThresholdDegrees = 0.1f;

	// --- Belichtung --------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Exposure")
	float MinExposureEV100 = -3.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Exposure")
	float MaxExposureEV100 = 16.f;

	/** Belichtungskorrektur tagsueber / nachts (negativ = Nacht bleibt dunkel statt grau). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Exposure")
	float DayExposureBias = 0.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Exposure")
	float NightExposureBias = -1.f;

	// --- Wettereffekte (Phase 6) -------------------------------------------------
	/** Drei Regenschichten um die Kamera (nah / mittel / fern), Material M_VB_Rain. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TArray<TObjectPtr<UStaticMeshComponent>> RainLayers;

	/** Sternenhimmel (Kuppel um die Kamera, dreht mit der Erdrotation), Material M_VB_Stars. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> StarDome;

	/** Fallgeschwindigkeit der Tropfen fuer die Neigung im Wind (m/s). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Weather Effects")
	float RainFallSpeed = 7.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Weather Effects")
	float MaxRainTiltDegrees = 30.f;

	/** Wolkenschicht: Unterkante und Dicke (km). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Weather Effects")
	float CloudBottomKm = 1.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Weather Effects")
	float CloudLayerHeightKm = 6.f;

	// --- Nebel -------------------------------------------------------------
	/** Leichter Kuestendunst bei klarem Wetter. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fog", meta = (ClampMin = "0.0"))
	float BaseFogDensity = 0.006f;

private:
	struct FVBSkyInputs
	{
		FVector SunDirection = FVector::UpVector;
		FVector MoonDirection = -FVector::UpVector;
		float NightFactor = 0.f;
		FVBWeatherState Weather;
		float LightningFlash = 0.f;
	};

	FVBSkyInputs GatherRuntimeInputs() const;
	FVBSkyInputs GatherPreviewInputs() const;
	void ApplyInputs(const FVBSkyInputs& Inputs, bool bForce);
	void EnsureCloudMaterial();
	void SetupWeatherEffects();
	void UpdateWeatherEffects(const FVBSkyInputs& Inputs);

	static void SetLightDirection(UDirectionalLightComponent* Light, const FVector& TowardsLight, FVector& InOutLastApplied, float ThresholdDeg, bool bForce);

	FVector LastSunDirection = FVector::ZeroVector;
	FVector LastMoonDirection = FVector::ZeroVector;
	float LastSunIntensity = -1.f;
	float LastMoonIntensity = -1.f;
	float LastSkyIntensity = -1.f;
	float LastFogDensity = -1.f;
	bool bEffectsReady = false;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UMaterialInstanceDynamic>> RainMaterials;
};
