#include "VBWeatherSubsystem.h"

#include "VBLog.h"
#include "VBTimeOfDaySubsystem.h"
#include "VBWorldDeveloperSettings.h"
#include "VBWorldParams.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Stats/Stats.h"

namespace VBWeatherTuning
{
	// Sekunden bis Oberflaechen bei Starkregen voll nass sind
	static constexpr float WetUpSeconds = 40.f;
	// Sekunden bis Oberflaechen nach Regenende wieder trocken sind
	static constexpr float DrySeconds = 420.f;
	// Pfuetzen bilden sich ab dieser Regenintensitaet
	static constexpr float PuddleRainThreshold = 0.2f;
	static constexpr float PuddleFillSeconds = 150.f;
	static constexpr float PuddleDrySeconds = 900.f;
	// Dauer eines Blitzes
	static constexpr float LightningDecayPerSecond = 7.f;
}

void UVBWeatherSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	const UVBWorldDeveloperSettings* Settings = GetDefault<UVBWorldDeveloperSettings>();
	DefaultTransitionSeconds = Settings->DefaultWeatherTransitionSeconds;
	bDynamicWeather = Settings->bDynamicWeather;

	TargetWeather = Settings->StartWeather;
	TargetState = FVBWeatherState::GetPreset(TargetWeather);
	FromState = TargetState;
	CurrentState = TargetState;

	// Bei Start mit Regen sind die Strassen bereits nass.
	Wetness = CurrentState.RainIntensity > 0.05f ? 1.f : 0.f;
	Puddles = CurrentState.RainIntensity > 0.5f ? 0.8f : 0.f;

	const float WindYaw = FMath::FRandRange(0.f, 360.f);
	WindDirection = FVector::ForwardVector.RotateAngleAxis(WindYaw, FVector::UpVector);

	ScheduleNextDynamicChange();
}

TStatId UVBWeatherSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UVBWeatherSubsystem, STATGROUP_Tickables);
}

bool UVBWeatherSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UVBWeatherSubsystem::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	// Uebergang zwischen Wetterlagen (Smoothstep fuer natuerlichen Verlauf)
	if (TransitionElapsed < TransitionDuration)
	{
		TransitionElapsed = FMath::Min(TransitionElapsed + DeltaTime, TransitionDuration);
		const float Alpha = FMath::SmoothStep(0.f, 1.f, TransitionElapsed / FMath::Max(TransitionDuration, UE_KINDA_SMALL_NUMBER));
		CurrentState = FVBWeatherState::Lerp(FromState, TargetState, Alpha);
	}
	else
	{
		CurrentState = TargetState;
	}

	// Wind dreht langsam
	WindPhase += DeltaTime * 0.01f;
	WindDirection = WindDirection.RotateAngleAxis(FMath::Sin(WindPhase) * DeltaTime * 0.5f, FVector::UpVector).GetSafeNormal2D();

	UpdateSurfaceWater(DeltaTime);
	UpdateLightning(DeltaTime);
	UpdateDynamicWeather(DeltaTime);
	PushToMaterialParameters();
}

void UVBWeatherSubsystem::SetWeather(EVBWeatherType NewWeather, float TransitionSeconds)
{
	if (NewWeather == EVBWeatherType::Count)
	{
		return;
	}

	FromState = CurrentState;
	TargetWeather = NewWeather;
	TargetState = FVBWeatherState::GetPreset(NewWeather);
	TransitionDuration = TransitionSeconds < 0.f ? DefaultTransitionSeconds : TransitionSeconds;
	TransitionElapsed = 0.f;

	if (TransitionDuration <= 0.f)
	{
		CurrentState = TargetState;
	}

	ScheduleNextDynamicChange();

	UE_LOG(LogVB, Log, TEXT("Wetter -> %s (Uebergang %.0f s)"), *VBWeather::ToString(NewWeather), TransitionDuration);
	OnWeatherChanged.Broadcast(NewWeather);
}

void UVBWeatherSubsystem::CycleWeather()
{
	const int32 Next = (static_cast<int32>(TargetWeather) + 1) % static_cast<int32>(EVBWeatherType::Count);
	SetWeather(static_cast<EVBWeatherType>(Next), 8.f);
}

float UVBWeatherSubsystem::GetRoadGripMultiplier() const
{
	// Nasser Asphalt ~ 70 % Haftung, Pfuetzen (Aquaplaning-Gefahr) bis ~ 55 %.
	return FMath::Clamp(1.f - Wetness * 0.3f - Puddles * 0.15f, 0.5f, 1.f);
}

void UVBWeatherSubsystem::SetDynamicWeatherEnabled(bool bEnabled)
{
	bDynamicWeather = bEnabled;
	ScheduleNextDynamicChange();
}

void UVBWeatherSubsystem::UpdateSurfaceWater(float DeltaTime)
{
	using namespace VBWeatherTuning;

	const float Rain = CurrentState.RainIntensity;
	if (Rain > 0.02f)
	{
		Wetness = FMath::Min(1.f, Wetness + DeltaTime * (0.3f + Rain) / WetUpSeconds);
	}
	else
	{
		// Bei Wind und Sonne trocknet es schneller, bei Nebel kaum.
		const float DryBoost = 0.5f + CurrentState.WindStrength + CurrentState.SunTransmission;
		const float FogSlowdown = CurrentState.FogDensityScale > 6.f ? 0.25f : 1.f;
		Wetness = FMath::Max(0.f, Wetness - DeltaTime * DryBoost * FogSlowdown / DrySeconds);
	}

	if (Rain > PuddleRainThreshold)
	{
		Puddles = FMath::Min(1.f, Puddles + DeltaTime * (Rain - PuddleRainThreshold) / PuddleFillSeconds);
	}
	else
	{
		Puddles = FMath::Max(0.f, Puddles - DeltaTime / PuddleDrySeconds);
	}
}

void UVBWeatherSubsystem::UpdateLightning(float DeltaTime)
{
	LightningFlash = FMath::Max(0.f, LightningFlash - DeltaTime * VBWeatherTuning::LightningDecayPerSecond);
	LightningCooldown -= DeltaTime;

	const float PerMinute = CurrentState.LightningPerMinute;
	if (PerMinute <= 0.01f || LightningCooldown > 0.f)
	{
		return;
	}

	// Poisson-Prozess: Wahrscheinlichkeit pro Frame
	const float Chance = PerMinute / 60.f * DeltaTime;
	if (FMath::FRand() < Chance)
	{
		LightningFlash = FMath::FRandRange(0.6f, 1.f);
		LightningCooldown = 1.5f;
		OnLightningStrike.Broadcast();
	}
}

void UVBWeatherSubsystem::UpdateDynamicWeather(float DeltaTime)
{
	if (!bDynamicWeather)
	{
		return;
	}

	SecondsUntilDynamicChange -= DeltaTime;
	if (SecondsUntilDynamicChange <= 0.f)
	{
		const EVBWeatherType Next = PickNextWeather();
		// Grosse Wetterwechsel dauern laenger
		SetWeather(Next, DefaultTransitionSeconds * FMath::FRandRange(1.5f, 3.f));
	}
}

void UVBWeatherSubsystem::ScheduleNextDynamicChange()
{
	const FVector2D Interval = GetDefault<UVBWorldDeveloperSettings>()->DynamicWeatherIntervalMinutes;
	const float MinMinutes = FMath::Max(0.5f, static_cast<float>(FMath::Min(Interval.X, Interval.Y)));
	const float MaxMinutes = FMath::Max(MinMinutes, static_cast<float>(FMath::Max(Interval.X, Interval.Y)));
	SecondsUntilDynamicChange = FMath::FRandRange(MinMinutes, MaxMinutes) * 60.f;
}

EVBWeatherType UVBWeatherSubsystem::PickNextWeather() const
{
	// Gewichtete Markov-Uebergaenge (Kuestenklima: meist klar, Nebel morgens, Regen selten)
	float Weights[static_cast<int32>(EVBWeatherType::Count)] = { 0.f };
	auto W = [&Weights](EVBWeatherType Type) -> float& { return Weights[static_cast<int32>(Type)]; };

	switch (TargetWeather)
	{
	case EVBWeatherType::Clear:
		W(EVBWeatherType::Clear) = 3.f; W(EVBWeatherType::Overcast) = 2.f; W(EVBWeatherType::Fog) = 0.6f;
		break;
	case EVBWeatherType::Overcast:
		W(EVBWeatherType::Clear) = 2.f; W(EVBWeatherType::Overcast) = 1.f; W(EVBWeatherType::LightRain) = 1.5f; W(EVBWeatherType::Fog) = 0.5f;
		break;
	case EVBWeatherType::LightRain:
		W(EVBWeatherType::Overcast) = 2.f; W(EVBWeatherType::LightRain) = 1.f; W(EVBWeatherType::HeavyRain) = 1.f;
		break;
	case EVBWeatherType::HeavyRain:
		W(EVBWeatherType::LightRain) = 2.f; W(EVBWeatherType::HeavyRain) = 0.5f; W(EVBWeatherType::Storm) = 0.7f;
		break;
	case EVBWeatherType::Storm:
		W(EVBWeatherType::HeavyRain) = 2.f; W(EVBWeatherType::LightRain) = 1.f;
		break;
	case EVBWeatherType::Fog:
		W(EVBWeatherType::Clear) = 2.f; W(EVBWeatherType::Overcast) = 1.f; W(EVBWeatherType::Fog) = 0.5f;
		break;
	default:
		W(EVBWeatherType::Clear) = 1.f;
		break;
	}

	// Nebel ist morgens deutlich wahrscheinlicher, mittags fast ausgeschlossen
	if (const UVBTimeOfDaySubsystem* Time = GetWorld() ? GetWorld()->GetSubsystem<UVBTimeOfDaySubsystem>() : nullptr)
	{
		const EVBDayPhase Phase = Time->GetDayPhase();
		if (Phase == EVBDayPhase::Dawn || Phase == EVBDayPhase::Morning || Phase == EVBDayPhase::Night)
		{
			W(EVBWeatherType::Fog) *= 3.f;
		}
		else if (Phase == EVBDayPhase::Midday)
		{
			W(EVBWeatherType::Fog) *= 0.1f;
		}
	}

	float Total = 0.f;
	for (const float Weight : Weights)
	{
		Total += Weight;
	}

	float Roll = FMath::FRandRange(0.f, Total);
	for (int32 Index = 0; Index < static_cast<int32>(EVBWeatherType::Count); ++Index)
	{
		Roll -= Weights[Index];
		if (Roll <= 0.f && Weights[Index] > 0.f)
		{
			return static_cast<EVBWeatherType>(Index);
		}
	}
	return EVBWeatherType::Clear;
}

void UVBWeatherSubsystem::PushToMaterialParameters()
{
	UWorld* World = GetWorld();
	VBWorldParams::SetScalar(World, VBWorldParams::Wetness, Wetness);
	VBWorldParams::SetScalar(World, VBWorldParams::Puddles, Puddles);
	VBWorldParams::SetScalar(World, VBWorldParams::RainIntensity, CurrentState.RainIntensity);
	VBWorldParams::SetScalar(World, VBWorldParams::WindStrength, CurrentState.WindStrength);
	VBWorldParams::SetScalar(World, VBWorldParams::CloudCoverage, CurrentState.CloudCoverage);
	VBWorldParams::SetScalar(World, VBWorldParams::FogAmount, FMath::Clamp(CurrentState.FogDensityScale / 12.f, 0.f, 1.f));
	VBWorldParams::SetScalar(World, VBWorldParams::LightningFlash, LightningFlash);
	VBWorldParams::SetVector(World, VBWorldParams::WindDirection,
		FLinearColor(static_cast<float>(WindDirection.X), static_cast<float>(WindDirection.Y), 0.f, CurrentState.WindStrength));
}

// ---------------------------------------------------------------------------
// Konsolenbefehle
// ---------------------------------------------------------------------------
static UVBWeatherSubsystem* VBGetWeatherSubsystem(UWorld* World)
{
	UVBWeatherSubsystem* Weather = World ? World->GetSubsystem<UVBWeatherSubsystem>() : nullptr;
	if (!Weather)
	{
		UE_LOG(LogVB, Warning, TEXT("Wettersystem nur waehrend des Spiels (PIE/Standalone) verfuegbar."));
	}
	return Weather;
}

static FAutoConsoleCommandWithWorldAndArgs GVBWeatherCommand(
	TEXT("vb.Weather"),
	TEXT("Wetter setzen: vb.Weather Clear|Overcast|LightRain|HeavyRain|Fog|Storm [Uebergang in Sekunden]"),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		UVBWeatherSubsystem* Weather = VBGetWeatherSubsystem(World);
		if (!Weather)
		{
			return;
		}

		if (Args.Num() == 0)
		{
			UE_LOG(LogVB, Display, TEXT("Wetter: %s | Naesse %.2f | Pfuetzen %.2f | Regen %.2f"),
				*VBWeather::ToString(Weather->GetWeather()), Weather->GetWetness(), Weather->GetPuddles(),
				Weather->GetCurrentState().RainIntensity);
			return;
		}

		EVBWeatherType Type;
		if (!VBWeather::FromString(Args[0], Type))
		{
			UE_LOG(LogVB, Warning, TEXT("Unbekanntes Wetter '%s'. Erlaubt: Clear, Overcast, LightRain, HeavyRain, Fog, Storm"), *Args[0]);
			return;
		}

		const float Seconds = Args.Num() > 1 ? FCString::Atof(*Args[1]) : -1.f;
		Weather->SetWeather(Type, Seconds);
	}));

static FAutoConsoleCommandWithWorldAndArgs GVBDynamicWeatherCommand(
	TEXT("vb.DynamicWeather"),
	TEXT("Automatischen Wetterwechsel ein-/ausschalten: vb.DynamicWeather 0|1"),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (UVBWeatherSubsystem* Weather = VBGetWeatherSubsystem(World))
		{
			const bool bEnable = Args.Num() > 0 ? FCString::Atoi(*Args[0]) != 0 : !Weather->IsDynamicWeatherEnabled();
			Weather->SetDynamicWeatherEnabled(bEnable);
			UE_LOG(LogVB, Display, TEXT("Dynamisches Wetter: %s"), bEnable ? TEXT("an") : TEXT("aus"));
		}
	}));
