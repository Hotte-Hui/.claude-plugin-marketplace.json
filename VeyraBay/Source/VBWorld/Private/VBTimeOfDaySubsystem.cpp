#include "VBTimeOfDaySubsystem.h"

#include "VBLog.h"
#include "VBSolarMath.h"
#include "VBWorldDeveloperSettings.h"
#include "VBWorldParams.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Stats/Stats.h"

void UVBTimeOfDaySubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	const UVBWorldDeveloperSettings* Settings = GetDefault<UVBWorldDeveloperSettings>();
	Hours = FMath::Fmod(FMath::Max(Settings->StartTimeOfDay, 0.f), 24.f);
	DayOfYear = FMath::Clamp(Settings->StartDayOfYear, 1, 365);
	Latitude = Settings->Latitude;
	NorthYaw = Settings->NorthYawOffset;
	GameHoursPerRealSecond = 24.f / (FMath::Max(Settings->RealMinutesPerGameDay, 1.f) * 60.f);

	UpdateDerivedState(/*bBroadcast*/ false);
}

void UVBTimeOfDaySubsystem::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	if (!bTimePaused)
	{
		Hours += DeltaTime * GameHoursPerRealSecond * TimeScale;
		while (Hours >= 24.f)
		{
			Hours -= 24.f;
			DayOfYear = (DayOfYear % 365) + 1;
		}
	}

	UpdateDerivedState(/*bBroadcast*/ true);
}

TStatId UVBTimeOfDaySubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UVBTimeOfDaySubsystem, STATGROUP_Tickables);
}

bool UVBTimeOfDaySubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UVBTimeOfDaySubsystem::SetTimeOfDay(float NewHours)
{
	Hours = FMath::Fmod(NewHours, 24.f);
	if (Hours < 0.f)
	{
		Hours += 24.f;
	}
	UpdateDerivedState(/*bBroadcast*/ true);
}

void UVBTimeOfDaySubsystem::SetTimeScale(float NewScale)
{
	TimeScale = FMath::Max(NewScale, 0.f);
}

void UVBTimeOfDaySubsystem::SetTimePaused(bool bPaused)
{
	bTimePaused = bPaused;
}

FString UVBTimeOfDaySubsystem::GetClockString() const
{
	const int32 TotalMinutes = FMath::FloorToInt(Hours * 60.f);
	return FString::Printf(TEXT("%02d:%02d"), (TotalMinutes / 60) % 24, TotalMinutes % 60);
}

EVBDayPhase UVBTimeOfDaySubsystem::PhaseForHour(float InHours)
{
	if (InHours < 5.f)  { return EVBDayPhase::Night; }
	if (InHours < 7.f)  { return EVBDayPhase::Dawn; }
	if (InHours < 11.f) { return EVBDayPhase::Morning; }
	if (InHours < 15.f) { return EVBDayPhase::Midday; }
	if (InHours < 18.f) { return EVBDayPhase::Afternoon; }
	if (InHours < 22.f) { return EVBDayPhase::Evening; }
	return EVBDayPhase::Night;
}

FString UVBTimeOfDaySubsystem::PhaseToString(EVBDayPhase InPhase)
{
	switch (InPhase)
	{
	case EVBDayPhase::Night:     return TEXT("Nacht");
	case EVBDayPhase::Dawn:      return TEXT("Morgendaemmerung");
	case EVBDayPhase::Morning:   return TEXT("Morgen");
	case EVBDayPhase::Midday:    return TEXT("Mittag");
	case EVBDayPhase::Afternoon: return TEXT("Nachmittag");
	case EVBDayPhase::Evening:   return TEXT("Abend");
	default:                     return TEXT("?");
	}
}

void UVBTimeOfDaySubsystem::UpdateDerivedState(bool bBroadcast)
{
	SunDirection = VBSolar::ComputeSunDirection(Hours, DayOfYear, Latitude, NorthYaw);
	MoonDirection = VBSolar::ComputeMoonDirection(SunDirection);
	SunElevation = VBSolar::ElevationDegrees(SunDirection);
	NightFactor = VBSolar::NightFactorFromElevation(SunElevation);

	UWorld* World = GetWorld();
	VBWorldParams::SetScalar(World, VBWorldParams::TimeOfDay01, Hours / 24.f);
	VBWorldParams::SetScalar(World, VBWorldParams::NightFactor, NightFactor);
	VBWorldParams::SetScalar(World, VBWorldParams::SunElevation, SunElevation / 90.f);

	const EVBDayPhase NewPhase = PhaseForHour(Hours);
	const int32 WholeHour = FMath::FloorToInt(Hours);

	if (bBroadcast && NewPhase != Phase)
	{
		Phase = NewPhase;
		UE_LOG(LogVB, Log, TEXT("Tagesabschnitt: %s (%s)"), *PhaseToString(Phase), *GetClockString());
		OnDayPhaseChanged.Broadcast(Phase);
	}
	else
	{
		Phase = NewPhase;
	}

	if (bBroadcast && WholeHour != LastWholeHour)
	{
		OnHourChanged.Broadcast(WholeHour);
	}
	LastWholeHour = WholeHour;
}

// ---------------------------------------------------------------------------
// Konsolenbefehle
// ---------------------------------------------------------------------------
static UVBTimeOfDaySubsystem* VBGetTimeSubsystem(UWorld* World)
{
	UVBTimeOfDaySubsystem* Time = World ? World->GetSubsystem<UVBTimeOfDaySubsystem>() : nullptr;
	if (!Time)
	{
		UE_LOG(LogVB, Warning, TEXT("Tageszeit-System nur waehrend des Spiels (PIE/Standalone) verfuegbar."));
	}
	return Time;
}

static FAutoConsoleCommandWithWorldAndArgs GVBTimeCommand(
	TEXT("vb.Time"),
	TEXT("Uhrzeit setzen: vb.Time 18.5  (ohne Argument: aktuelle Zeit ausgeben)"),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (UVBTimeOfDaySubsystem* Time = VBGetTimeSubsystem(World))
		{
			if (Args.Num() > 0)
			{
				Time->SetTimeOfDay(FCString::Atof(*Args[0]));
			}
			UE_LOG(LogVB, Display, TEXT("Uhrzeit %s | %s | Sonne %.1f Grad | Nacht %.2f"),
				*Time->GetClockString(), *UVBTimeOfDaySubsystem::PhaseToString(Time->GetDayPhase()),
				Time->GetSunElevationDegrees(), Time->GetNightFactor());
		}
	}));

static FAutoConsoleCommandWithWorldAndArgs GVBTimeScaleCommand(
	TEXT("vb.TimeScale"),
	TEXT("Zeitraffer: vb.TimeScale 30  (1 = normal)"),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (UVBTimeOfDaySubsystem* Time = VBGetTimeSubsystem(World))
		{
			if (Args.Num() > 0)
			{
				Time->SetTimeScale(FCString::Atof(*Args[0]));
			}
			UE_LOG(LogVB, Display, TEXT("Zeitraffer: x%.2f"), Time->GetTimeScale());
		}
	}));

static FAutoConsoleCommandWithWorldAndArgs GVBTimePauseCommand(
	TEXT("vb.TimePause"),
	TEXT("Tageszeit anhalten/fortsetzen: vb.TimePause [0|1]"),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (UVBTimeOfDaySubsystem* Time = VBGetTimeSubsystem(World))
		{
			const bool bPause = Args.Num() > 0 ? FCString::Atoi(*Args[0]) != 0 : !Time->IsTimePaused();
			Time->SetTimePaused(bPause);
			UE_LOG(LogVB, Display, TEXT("Tageszeit %s"), bPause ? TEXT("angehalten") : TEXT("laeuft"));
		}
	}));
