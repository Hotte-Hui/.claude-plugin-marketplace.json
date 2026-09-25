#include "VBSkyEnvironment.h"

#include "VBSolarMath.h"
#include "VBTimeOfDaySubsystem.h"
#include "VBWeatherSubsystem.h"
#include "VBWorldDeveloperSettings.h"
#include "VBWorldParams.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/PostProcessComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/VolumetricCloudComponent.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"

namespace VBSky
{
	static const TCHAR* DefaultCloudMaterial = TEXT("/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst.m_SimpleVolumetricCloud_Inst");

	static bool ChangedEnough(float NewValue, float OldValue)
	{
		return OldValue < 0.f || !FMath::IsNearlyEqual(NewValue, OldValue, FMath::Max(FMath::Abs(NewValue) * 0.002f, 0.0005f));
	}
}

AVBSkyEnvironment::AVBSkyEnvironment()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

#if WITH_EDITORONLY_DATA
	// Himmel ist global und darf von World Partition nie entladen werden.
	bIsSpatiallyLoaded = false;
#endif

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;

	// --- Sonne ---------------------------------------------------------------
	SunLight = CreateDefaultSubobject<UDirectionalLightComponent>(TEXT("SunLight"));
	SunLight->SetupAttachment(Root);
	SunLight->SetMobility(EComponentMobility::Movable);
	SunLight->bAtmosphereSunLight = true;
	SunLight->AtmosphereSunLightIndex = 0;
	SunLight->bCastCloudShadows = true;
	SunLight->Intensity = SunIlluminanceLux;
	SunLight->LightSourceAngle = 0.5357f;
	SunLight->SetRelativeRotation(FRotator(-45.f, 30.f, 0.f));

	// --- Mond ----------------------------------------------------------------
	MoonLight = CreateDefaultSubobject<UDirectionalLightComponent>(TEXT("MoonLight"));
	MoonLight->SetupAttachment(Root);
	MoonLight->SetMobility(EComponentMobility::Movable);
	MoonLight->bAtmosphereSunLight = true;
	MoonLight->AtmosphereSunLightIndex = 1;
	MoonLight->Intensity = MoonIlluminanceLux;
	MoonLight->LightColor = MoonColor.ToFColor(true);
	MoonLight->LightSourceAngle = 0.52f;
	MoonLight->SetRelativeRotation(FRotator(-45.f, 210.f, 0.f));

	// --- Atmosphaere, Himmelslicht, Wolken ------------------------------------
	SkyAtmosphere = CreateDefaultSubobject<USkyAtmosphereComponent>(TEXT("SkyAtmosphere"));
	SkyAtmosphere->SetupAttachment(Root);

	SkyLight = CreateDefaultSubobject<USkyLightComponent>(TEXT("SkyLight"));
	SkyLight->SetupAttachment(Root);
	SkyLight->SetMobility(EComponentMobility::Movable);
	SkyLight->bRealTimeCapture = true;
	SkyLight->SourceType = SLS_CapturedScene;
	SkyLight->Intensity = 1.f;

	Clouds = CreateDefaultSubobject<UVolumetricCloudComponent>(TEXT("VolumetricClouds"));
	Clouds->SetupAttachment(Root);

	// --- Nebel -----------------------------------------------------------------
	HeightFog = CreateDefaultSubobject<UExponentialHeightFogComponent>(TEXT("HeightFog"));
	HeightFog->SetupAttachment(Root);
	HeightFog->FogDensity = BaseFogDensity;
	HeightFog->FogHeightFalloff = 0.2f;
	HeightFog->bEnableVolumetricFog = true;
	HeightFog->VolumetricFogDistance = 12000.f;

	// --- Post-Processing (unbegrenzt, physikalische Belichtung) -----------------
	PostProcess = CreateDefaultSubobject<UPostProcessComponent>(TEXT("PostProcess"));
	PostProcess->SetupAttachment(Root);
	PostProcess->bUnbound = true;
	PostProcess->Priority = 0.f;

	FPostProcessSettings& PP = PostProcess->Settings;
	PP.bOverride_AutoExposureMethod = true;
	PP.AutoExposureMethod = AEM_Histogram;
	PP.bOverride_AutoExposureMinBrightness = true;
	PP.AutoExposureMinBrightness = MinExposureEV100;
	PP.bOverride_AutoExposureMaxBrightness = true;
	PP.AutoExposureMaxBrightness = MaxExposureEV100;
	PP.bOverride_AutoExposureSpeedUp = true;
	PP.AutoExposureSpeedUp = 2.5f;
	PP.bOverride_AutoExposureSpeedDown = true;
	PP.AutoExposureSpeedDown = 1.2f;
	PP.bOverride_AutoExposureBias = true;
	PP.AutoExposureBias = DayExposureBias;
	PP.bOverride_BloomIntensity = true;
	PP.BloomIntensity = 0.4f;
	PP.bOverride_VignetteIntensity = true;
	PP.VignetteIntensity = 0.3f;
	PP.bOverride_SceneFringeIntensity = true;
	PP.SceneFringeIntensity = 0.15f;
	PP.bOverride_FilmGrainIntensity = true;
	PP.FilmGrainIntensity = 0.03f;
	PP.bOverride_MotionBlurAmount = true;
	PP.MotionBlurAmount = 0.3f;
	PP.bOverride_MotionBlurMax = true;
	PP.MotionBlurMax = 3.f;
	PP.bOverride_LensFlareIntensity = true;
	PP.LensFlareIntensity = 0.f;
}

void AVBSkyEnvironment::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

	EnsureCloudMaterial();

	FPostProcessSettings& PP = PostProcess->Settings;
	PP.AutoExposureMinBrightness = MinExposureEV100;
	PP.AutoExposureMaxBrightness = MaxExposureEV100;

	const UWorld* World = GetWorld();
	if (!World || !World->IsGameWorld())
	{
		ApplyInputs(GatherPreviewInputs(), /*bForce*/ true);
	}
}

void AVBSkyEnvironment::BeginPlay()
{
	Super::BeginPlay();

	EnsureCloudMaterial();
	ApplyInputs(GatherRuntimeInputs(), /*bForce*/ true);
}

void AVBSkyEnvironment::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	ApplyInputs(GatherRuntimeInputs(), /*bForce*/ false);
}

void AVBSkyEnvironment::EnsureCloudMaterial()
{
	if (Clouds && !Clouds->Material)
	{
		if (UMaterialInterface* CloudMaterial = LoadObject<UMaterialInterface>(nullptr, VBSky::DefaultCloudMaterial, nullptr, LOAD_NoWarn | LOAD_Quiet))
		{
			Clouds->Material = CloudMaterial;
			Clouds->MarkRenderStateDirty();
		}
	}
}

AVBSkyEnvironment::FVBSkyInputs AVBSkyEnvironment::GatherPreviewInputs() const
{
	const UVBWorldDeveloperSettings* Settings = GetDefault<UVBWorldDeveloperSettings>();

	FVBSkyInputs Inputs;
	Inputs.SunDirection = VBSolar::ComputeSunDirection(PreviewTimeOfDay, Settings->StartDayOfYear, Settings->Latitude, Settings->NorthYawOffset);
	Inputs.MoonDirection = VBSolar::ComputeMoonDirection(Inputs.SunDirection);
	Inputs.NightFactor = VBSolar::NightFactorFromElevation(VBSolar::ElevationDegrees(Inputs.SunDirection));
	Inputs.Weather = FVBWeatherState::GetPreset(PreviewWeather);
	return Inputs;
}

AVBSkyEnvironment::FVBSkyInputs AVBSkyEnvironment::GatherRuntimeInputs() const
{
	UWorld* World = GetWorld();
	const UVBTimeOfDaySubsystem* Time = World ? World->GetSubsystem<UVBTimeOfDaySubsystem>() : nullptr;
	const UVBWeatherSubsystem* Weather = World ? World->GetSubsystem<UVBWeatherSubsystem>() : nullptr;

	FVBSkyInputs Inputs = GatherPreviewInputs();
	if (Time)
	{
		Inputs.SunDirection = Time->GetSunDirection();
		Inputs.MoonDirection = Time->GetMoonDirection();
		Inputs.NightFactor = Time->GetNightFactor();
	}
	if (Weather)
	{
		Inputs.Weather = Weather->GetCurrentState();
		Inputs.LightningFlash = Weather->GetLightningFlash();
	}
	return Inputs;
}

void AVBSkyEnvironment::SetLightDirection(UDirectionalLightComponent* Light, const FVector& TowardsLight, FVector& InOutLastApplied, float ThresholdDeg, bool bForce)
{
	if (!bForce && !InOutLastApplied.IsNearlyZero())
	{
		const double CosAngle = FVector::DotProduct(InOutLastApplied, TowardsLight);
		if (CosAngle > FMath::Cos(FMath::DegreesToRadians(ThresholdDeg)))
		{
			return;
		}
	}

	// Licht faellt von der Sonne zur Erde: Blickrichtung des Lichts ist -TowardsLight.
	Light->SetWorldRotation((-TowardsLight).Rotation());
	InOutLastApplied = TowardsLight;
}

void AVBSkyEnvironment::ApplyInputs(const FVBSkyInputs& Inputs, bool bForce)
{
	if (!SunLight || !MoonLight || !SkyLight || !HeightFog || !PostProcess)
	{
		return;
	}

	const FVBWeatherState& Weather = Inputs.Weather;
	const float SunElevation = VBSolar::ElevationDegrees(Inputs.SunDirection);
	const float MoonElevation = VBSolar::ElevationDegrees(Inputs.MoonDirection);

	// --- Sonne: bleibt bis -10 Grad aktiv, damit die Atmosphaere die Daemmerung streut ---
	const bool bSunActive = SunElevation > -10.f;
	if (SunLight->IsVisible() != bSunActive)
	{
		SunLight->SetVisibility(bSunActive);
	}
	if (bSunActive)
	{
		SetLightDirection(SunLight, Inputs.SunDirection, LastSunDirection, SunUpdateThresholdDegrees, bForce);

		const float SunIntensity = SunIlluminanceLux * Weather.SunTransmission;
		if (bForce || VBSky::ChangedEnough(SunIntensity, LastSunIntensity))
		{
			SunLight->SetIntensity(SunIntensity);
			LastSunIntensity = SunIntensity;
		}
	}

	// --- Mond: nur nachts und ueber dem Horizont -----------------------------------
	const float MoonVisibility = Inputs.NightFactor * FMath::SmoothStep(-2.f, 8.f, MoonElevation);
	const bool bMoonActive = MoonVisibility > 0.01f;
	if (MoonLight->IsVisible() != bMoonActive)
	{
		MoonLight->SetVisibility(bMoonActive);
	}
	if (bMoonActive)
	{
		SetLightDirection(MoonLight, Inputs.MoonDirection, LastMoonDirection, SunUpdateThresholdDegrees, bForce);

		const float MoonIntensity = MoonIlluminanceLux * MoonVisibility * FMath::Lerp(1.f, 0.2f, Weather.CloudCoverage);
		if (bForce || VBSky::ChangedEnough(MoonIntensity, LastMoonIntensity))
		{
			MoonLight->SetIntensity(MoonIntensity);
			MoonLight->SetLightColor(MoonColor);
			LastMoonIntensity = MoonIntensity;
		}
	}

	// --- Himmelslicht: bei geschlossener Decke gedaempft, Blitze hellen kurz auf ------
	const float SkyIntensity = FMath::Lerp(1.f, 0.7f, Weather.CloudCoverage) * (1.f + Inputs.LightningFlash * 6.f);
	if (bForce || VBSky::ChangedEnough(SkyIntensity, LastSkyIntensity))
	{
		SkyLight->SetIntensity(SkyIntensity);
		LastSkyIntensity = SkyIntensity;
	}

	// --- Nebel ---------------------------------------------------------------------
	const float FogDensity = BaseFogDensity * Weather.FogDensityScale;
	if (bForce || VBSky::ChangedEnough(FogDensity, LastFogDensity))
	{
		HeightFog->SetFogDensity(FogDensity);
		LastFogDensity = FogDensity;
	}

	// --- Belichtung: Nacht bleibt dunkel, statt von der Auto-Belichtung grau hochgezogen zu werden
	PostProcess->Settings.AutoExposureBias = FMath::Lerp(DayExposureBias, NightExposureBias, Inputs.NightFactor);

	// --- Editor-Vorschau: globale Material-Parameter auch ohne laufendes Spiel setzen ---
	UWorld* World = GetWorld();
	if (World && !World->IsGameWorld())
	{
		const float PreviewWet = Weather.RainIntensity > 0.02f ? 1.f : 0.f;
		VBWorldParams::SetScalar(World, VBWorldParams::Wetness, PreviewWet);
		VBWorldParams::SetScalar(World, VBWorldParams::Puddles, Weather.RainIntensity > 0.5f ? 1.f : 0.f);
		VBWorldParams::SetScalar(World, VBWorldParams::RainIntensity, Weather.RainIntensity);
		VBWorldParams::SetScalar(World, VBWorldParams::NightFactor, Inputs.NightFactor);
		VBWorldParams::SetScalar(World, VBWorldParams::TimeOfDay01, PreviewTimeOfDay / 24.f);
	}
}
