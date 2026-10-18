#include "VBSkyEnvironment.h"

#include "VBSolarMath.h"
#include "VBStats.h"
#include "VBTimeOfDaySubsystem.h"
#include "VBWeatherSubsystem.h"
#include "VBWorldDeveloperSettings.h"
#include "VBWorldParams.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/PostProcessComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/VolumetricCloudComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"

namespace VBSky
{
	static const TCHAR* DefaultCloudMaterial = TEXT("/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst.m_SimpleVolumetricCloud_Inst");
	// Eigene Assets (vom Setup-Skript erzeugt / importiert); fehlen sie, bleibt der Engine-Standard
	static const TCHAR* CloudMaterial = TEXT("/Game/VeyraBay/Materials/Sky/M_VB_Clouds.M_VB_Clouds");
	static const TCHAR* RainMaterial = TEXT("/Game/VeyraBay/Materials/Sky/M_VB_Rain.M_VB_Rain");
	static const TCHAR* StarMaterial = TEXT("/Game/VeyraBay/Materials/Sky/M_VB_Stars.M_VB_Stars");
	static const TCHAR* RainMesh = TEXT("/Game/VeyraBay/Environment/Sky/SM_VB_RainCylinder/SM_VB_RainCylinder.SM_VB_RainCylinder");
	static const TCHAR* DomeMesh = TEXT("/Game/VeyraBay/Environment/Sky/SM_VB_SkyDome/SM_VB_SkyDome.SM_VB_SkyDome");

	// Regenschichten: Radius, Hoehe (m), Kachelung U/V, Fallgeschwindigkeit (UV/s), Deckkraft
	struct FRainLayer { float Radius; float Height; float TilingU; float TilingV; float Speed; float Opacity; };
	static const FRainLayer RainLayerSetup[3] = {
		{ 3.5f, 10.f, 6.f, 2.f, 1.6f, 0.55f },
		{ 9.f, 22.f, 14.f, 3.5f, 1.1f, 0.45f },
		{ 22.f, 40.f, 30.f, 5.f, 0.7f, 0.35f },
	};

	static UStaticMeshComponent* MakeEffectMesh(AActor* Owner, USceneComponent* Parent, const TCHAR* Name)
	{
		UStaticMeshComponent* Mesh = Owner->CreateDefaultSubobject<UStaticMeshComponent>(Name);
		Mesh->SetupAttachment(Parent);
		Mesh->SetUsingAbsoluteLocation(true);
		Mesh->SetUsingAbsoluteRotation(true);
		Mesh->SetUsingAbsoluteScale(true);
		Mesh->SetMobility(EComponentMobility::Movable);
		Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Mesh->SetGenerateOverlapEvents(false);
		Mesh->SetCastShadow(false);
		Mesh->bAffectDistanceFieldLighting = false;
		Mesh->bAffectDynamicIndirectLighting = false;
		Mesh->SetVisibility(false);
		Mesh->SetHiddenInGame(false);
		return Mesh;
	}

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

	// --- Regen und Sterne ---------------------------------------------------------
	static const TCHAR* RainNames[3] = { TEXT("RainNear"), TEXT("RainMid"), TEXT("RainFar") };
	for (const TCHAR* Name : RainNames)
	{
		RainLayers.Add(VBSky::MakeEffectMesh(this, Root, Name));
	}
	StarDome = VBSky::MakeEffectMesh(this, Root, TEXT("StarDome"));
	StarDome->SetBoundsScale(1.f);
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
	SetupWeatherEffects();
	ApplyInputs(GatherRuntimeInputs(), /*bForce*/ true);
}

DECLARE_CYCLE_STAT(TEXT("Himmel/Wetter (Tick)"), STAT_VBSky, STATGROUP_VeyraBay);

void AVBSkyEnvironment::Tick(float DeltaSeconds)
{
	SCOPE_CYCLE_COUNTER(STAT_VBSky);
	Super::Tick(DeltaSeconds);
	const FVBSkyInputs Inputs = GatherRuntimeInputs();
	ApplyInputs(Inputs, /*bForce*/ false);
	UpdateWeatherEffects(Inputs);
}

void AVBSkyEnvironment::EnsureCloudMaterial()
{
	if (!Clouds)
	{
		return;
	}
	// Eigenes Wolkenmaterial (Bedeckung, Wind und Gewitter aus der MPC) bevorzugen
	UMaterialInterface* Wanted = LoadObject<UMaterialInterface>(nullptr, VBSky::CloudMaterial, nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (!Wanted && !Clouds->Material)
	{
		Wanted = LoadObject<UMaterialInterface>(nullptr, VBSky::DefaultCloudMaterial, nullptr, LOAD_NoWarn | LOAD_Quiet);
	}
	if (Wanted && Clouds->Material != Wanted)
	{
		Clouds->SetMaterial(Wanted);
	}
	if (Wanted && Wanted->GetPathName().StartsWith(TEXT("/Game/")))
	{
		Clouds->SetLayerBottomAltitude(CloudBottomKm);
		Clouds->SetLayerHeight(CloudLayerHeightKm);
	}
}

void AVBSkyEnvironment::SetupWeatherEffects()
{
	UStaticMesh* Cylinder = LoadObject<UStaticMesh>(nullptr, VBSky::RainMesh, nullptr, LOAD_NoWarn | LOAD_Quiet);
	UStaticMesh* Dome = LoadObject<UStaticMesh>(nullptr, VBSky::DomeMesh, nullptr, LOAD_NoWarn | LOAD_Quiet);
	UMaterialInterface* Rain = LoadObject<UMaterialInterface>(nullptr, VBSky::RainMaterial, nullptr, LOAD_NoWarn | LOAD_Quiet);
	UMaterialInterface* Stars = LoadObject<UMaterialInterface>(nullptr, VBSky::StarMaterial, nullptr, LOAD_NoWarn | LOAD_Quiet);

	RainMaterials.Reset();
	if (Cylinder && Rain)
	{
		for (int32 Index = 0; Index < RainLayers.Num(); ++Index)
		{
			const VBSky::FRainLayer& Layer = VBSky::RainLayerSetup[Index];
			UStaticMeshComponent* Mesh = RainLayers[Index];
			Mesh->SetStaticMesh(Cylinder);
			UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(Rain, this);
			MID->SetScalarParameterValue(TEXT("TilingU"), Layer.TilingU);
			MID->SetScalarParameterValue(TEXT("TilingV"), Layer.TilingV);
			MID->SetScalarParameterValue(TEXT("FallSpeed"), Layer.Speed);
			MID->SetScalarParameterValue(TEXT("OpacityScale"), Layer.Opacity);
			Mesh->SetMaterial(0, MID);
			Mesh->SetWorldScale3D(FVector(Layer.Radius, Layer.Radius, Layer.Height));
			Mesh->SetTranslucentSortPriority(10 - Index);
			RainMaterials.Add(MID);
		}
	}
	if (Dome && Stars)
	{
		StarDome->SetStaticMesh(Dome);
		StarDome->SetMaterial(0, Stars);
		StarDome->SetWorldScale3D(FVector(10000.f));     // 1 m Radius -> 10 km
		StarDome->SetTranslucentSortPriority(-100);      // hinter allem anderen Durchscheinenden
	}
	bEffectsReady = RainMaterials.Num() > 0 || StarDome->GetStaticMesh() != nullptr;
}

void AVBSkyEnvironment::UpdateWeatherEffects(const FVBSkyInputs& Inputs)
{
	UWorld* World = GetWorld();
	if (!bEffectsReady || !World)
	{
		return;
	}
	const APlayerController* PC = World->GetFirstPlayerController();
	if (!PC || !PC->PlayerCameraManager)
	{
		return;
	}
	const FVector Camera = PC->PlayerCameraManager->GetCameraLocation();

	// Regen: Achse gegen die Fallrichtung (Tropfen fallen mit dem Wind schraeg)
	const bool bRain = Inputs.Weather.RainIntensity > 0.01f && RainMaterials.Num() > 0;
	FVector WindDirection = FVector::ForwardVector;
	if (const UVBWeatherSubsystem* Weather = World->GetSubsystem<UVBWeatherSubsystem>())
	{
		WindDirection = Weather->GetWindDirection();
	}
	const float WindSpeed = 2.f + Inputs.Weather.WindStrength * 16.f;
	const float Tilt = FMath::Min(FMath::RadiansToDegrees(FMath::Atan2(WindSpeed, RainFallSpeed)), MaxRainTiltDegrees);
	const FVector Axis = (FVector::UpVector * FMath::Cos(FMath::DegreesToRadians(Tilt)) - WindDirection.GetSafeNormal2D() * FMath::Sin(FMath::DegreesToRadians(Tilt))).GetSafeNormal();
	const FQuat Rotation = FQuat::FindBetweenNormals(FVector::UpVector, Axis);
	for (int32 Index = 0; Index < RainLayers.Num(); ++Index)
	{
		UStaticMeshComponent* Mesh = RainLayers[Index];
		if (Mesh->IsVisible() != bRain)
		{
			Mesh->SetVisibility(bRain);
		}
		if (bRain)
		{
			// Zylinder-Pivot unten: so verschieben, dass die Kamera etwa auf halber Hoehe sitzt
			const float Height = VBSky::RainLayerSetup[Index].Height * 100.f;
			Mesh->SetWorldLocationAndRotation(Camera - Axis * (Height * 0.4f), Rotation);
		}
	}

	// Sterne: nachts sichtbar, drehen einmal pro Tag um den Himmelspol
	const bool bStars = Inputs.NightFactor > 0.05f && StarDome->GetStaticMesh() != nullptr;
	if (StarDome->IsVisible() != bStars)
	{
		StarDome->SetVisibility(bStars);
	}
	if (bStars)
	{
		const UVBWorldDeveloperSettings* Settings = GetDefault<UVBWorldDeveloperSettings>();
		const UVBTimeOfDaySubsystem* Time = World->GetSubsystem<UVBTimeOfDaySubsystem>();
		const float Hours = Time ? Time->GetTimeOfDay() : PreviewTimeOfDay;
		const float Latitude = FMath::DegreesToRadians(Settings->Latitude);
		const FVector Pole = FVector(FMath::Cos(Latitude), 0.f, FMath::Sin(Latitude)).RotateAngleAxis(Settings->NorthYawOffset, FVector::UpVector);
		const FQuat Spin(FVector::UpVector, -FMath::DegreesToRadians(Hours * 15.f));
		StarDome->SetWorldLocationAndRotation(Camera, FQuat::FindBetweenNormals(FVector::UpVector, Pole) * Spin);
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
