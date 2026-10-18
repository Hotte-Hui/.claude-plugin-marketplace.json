#include "VBEventSubsystem.h"

#include "VBAudioSubsystem.h"
#include "VBCrowdManager.h"
#include "VBFireworks.h"
#include "VBLog.h"
#include "VBPedestrian.h"
#include "VBTimeOfDaySubsystem.h"
#include "VBTrafficManager.h"
#include "VBTrafficVehicle.h"
#include "Components/AudioComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"

namespace VBEvents
{
	static AVBTrafficManager* Traffic(UWorld* World)
	{
		TActorIterator<AVBTrafficManager> It(World);
		return It ? *It : nullptr;
	}

	static AVBCrowdManager* Crowd(UWorld* World)
	{
		TActorIterator<AVBCrowdManager> It(World);
		return It ? *It : nullptr;
	}

	static FAutoConsoleCommandWithWorldAndArgs EventCommand(TEXT("vb.Event"), TEXT("vb.Event panne|musik|feuerwerk - Ereignis ausloesen"),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			UVBEventSubsystem* Events = World ? World->GetSubsystem<UVBEventSubsystem>() : nullptr;
			if (!Events || Args.Num() == 0)
			{
				return;
			}
			const FString Kind = Args[0].ToLower();
			const bool bOk = Kind.StartsWith(TEXT("pan")) ? Events->StartBreakdown()
				: Kind.StartsWith(TEXT("mus")) ? Events->StartMusician()
				: Kind.StartsWith(TEXT("feu")) ? Events->StartFireworks() : false;
			UE_LOG(LogVB, Log, TEXT("Ereignis %s: %s"), *Kind, bOk ? TEXT("gestartet") : TEXT("kein passender Ort"));
		}));
}

bool UVBEventSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UVBEventSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UVBEventSubsystem, STATGROUP_Tickables);
}

FVector UVBEventSubsystem::PlayerLocation() const
{
	const APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
	const APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	return Pawn ? Pawn->GetActorLocation() : FVector::ZeroVector;
}

FString UVBEventSubsystem::ConsumeNotice()
{
	FString Result = Notice;
	Notice.Reset();
	return Result;
}

// ---------------------------------------------------------------------------------------------
// Panne: Auto mit Warnblinker blockiert eine Fahrspur
// ---------------------------------------------------------------------------------------------
bool UVBEventSubsystem::StartBreakdown()
{
	UWorld* World = GetWorld();
	AVBTrafficManager* Manager = VBEvents::Traffic(World);
	if (!Manager || Manager->VehicleTypes.Num() == 0)
	{
		return false;
	}
	const FVector Player = PlayerLocation();
	const TArray<FVBLane>& Lanes = Manager->GetLanes();
	for (int32 Attempt = 0; Attempt < 80; ++Attempt)
	{
		const int32 Index = FMath::RandRange(0, Lanes.Num() - 1);
		const FVBLane& Lane = Lanes[Index];
		if (Lane.bConnector || Lane.Length < 4000.f)
		{
			continue;
		}
		const float T = Lane.ParamAtDistance(Lane.Length * 0.45f);
		const FVector Point = Lane.Eval(T);
		const float Distance = FVector::Dist2D(Point, Player);
		if (Distance < 8000.f || Distance > 25000.f)
		{
			continue;
		}
		const FVector Direction = Lane.Tangent(T);
		const FVector Location = Point + FVector(-Direction.Y, Direction.X, 0.f) * 60.f;   // etwas nach rechts
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		AVBTrafficVehicle* Car = World->SpawnActor<AVBTrafficVehicle>(Location, Direction.Rotation(), Params);
		if (!Car)
		{
			return false;
		}
		const FVBTrafficVehicleType& Type = Manager->VehicleTypes[FMath::RandRange(0, Manager->VehicleTypes.Num() - 1)];
		Car->Configure(Type, Manager->PaintPalette.Num() ? Manager->PaintPalette[FMath::RandRange(0, Manager->PaintPalette.Num() - 1)] : Type.Paint);

		FActiveEvent Event;
		Event.Name = TEXT("Panne");
		Event.TimeLeft = 180.f;
		Event.Location = Location;
		Event.Car = Car;
		Event.Actors.Add(Car);
		Active.Add(Event);
		Notice = TEXT("Verkehrsmeldung: Pannenfahrzeug in der Naehe");
		return true;
	}
	return false;
}

// ---------------------------------------------------------------------------------------------
// Strassenmusik
// ---------------------------------------------------------------------------------------------
bool UVBEventSubsystem::StartMusician()
{
	UWorld* World = GetWorld();
	AVBCrowdManager* Crowd = VBEvents::Crowd(World);
	FVector Point, StreetDirection;
	if (!Crowd || !Crowd->FindSidewalkPoint(PlayerLocation(), 4000.f, 15000.f, Point, StreetDirection))
	{
		return false;
	}
	FActiveEvent Event;
	Event.Name = TEXT("Strassenmusik");
	Event.TimeLeft = 240.f;
	Event.Location = Point;
	const FVector Across(-StreetDirection.Y, StreetDirection.X, 0.f);
	if (AVBPedestrian* Musician = Crowd->SpawnStandingPedestrian(Point, Point + Across * 1000.f))
	{
		Event.Actors.Add(Musician);
	}
	for (int32 Index = 0; Index < 5; ++Index)
	{
		// Halbkreis zur Strassenseite hin, 2-3 m entfernt
		const float Angle = FMath::DegreesToRadians(-70.f + Index * 35.f + FMath::FRandRange(-8.f, 8.f));
		const FVector Offset = (Across * FMath::Cos(Angle) + StreetDirection * FMath::Sin(Angle)) * FMath::FRandRange(200.f, 300.f);
		if (AVBPedestrian* Listener = Crowd->SpawnStandingPedestrian(Point + Offset, Point))
		{
			Event.Actors.Add(Listener);
		}
	}
	if (USoundBase* Music = UVBAudioSubsystem::LoadSound(TEXT("StreetMusic")))
	{
		if (UAudioComponent* Audio = UGameplayStatics::SpawnSoundAtLocation(World, Music, Point + FVector(0.f, 0.f, 120.f), FRotator::ZeroRotator,
			0.8f, 1.f, 0.f, nullptr, nullptr, false))
		{
			Audio->bOverrideAttenuation = true;
			Audio->AttenuationOverrides.bAttenuate = true;
			Audio->AttenuationOverrides.bSpatialize = true;
			Audio->AttenuationOverrides.AttenuationShapeExtents = FVector(300.f, 0.f, 0.f);
			Audio->AttenuationOverrides.FalloffDistance = 3500.f;
			Audio->Stop();
			Audio->Play();
			Event.Audio = Audio;
		}
	}
	Active.Add(Event);
	Notice = TEXT("In der Naehe: Strassenmusik");
	return true;
}

// ---------------------------------------------------------------------------------------------
// Feuerwerk (nachts, ueber dem Meer)
// ---------------------------------------------------------------------------------------------
bool UVBEventSubsystem::StartFireworks()
{
	UWorld* World = GetWorld();
	const FVector Player = PlayerLocation();
	const float CoastY = -9412.f;
	if (Player.Y - CoastY > 90000.f)
	{
		return false;
	}
	FActorSpawnParameters Params;
	const FVector Location(Player.X + FMath::FRandRange(-10000.f, 10000.f), CoastY - 18000.f, 0.f);
	AVBFireworks* Show = World->SpawnActor<AVBFireworks>(Location, FRotator::ZeroRotator, Params);
	if (!Show)
	{
		return false;
	}
	FActiveEvent Event;
	Event.Name = TEXT("Feuerwerk");
	Event.TimeLeft = 80.f;
	Event.Location = Location;
	Active.Add(Event);    // das Feuerwerk raeumt sich selbst auf
	Notice = TEXT("Hafenfest: Feuerwerk ueber der Bucht!");
	return true;
}

void UVBEventSubsystem::EndEvent(FActiveEvent& Event)
{
	for (const TWeakObjectPtr<AActor>& Actor : Event.Actors)
	{
		if (AActor* Resolved = Actor.Get())
		{
			Resolved->Destroy();
		}
	}
	if (UAudioComponent* Audio = Event.Audio.Get())
	{
		Audio->FadeOut(2.f, 0.f);
	}
}

void UVBEventSubsystem::Tick(float DeltaTime)
{
	UWorld* World = GetWorld();
	if (!World || !World->GetMapName().Contains(TEXT("L_VB_City")))
	{
		return;
	}
	const FVector Player = PlayerLocation();
	AVBTrafficManager* Manager = VBEvents::Traffic(World);

	for (int32 Index = Active.Num() - 1; Index >= 0; --Index)
	{
		FActiveEvent& Event = Active[Index];
		Event.TimeLeft -= DeltaTime;
		// Pannenauto: Warnblinker + Hindernis fuer den Verkehr
		if (AVBTrafficVehicle* Car = Event.Car.Get())
		{
			Car->UpdateVisuals(DeltaTime, 0.f, 0.f, false, false, 2);
			if (Manager)
			{
				Manager->AddTransientObstacle(Car->GetActorLocation(), -95.f);
			}
		}
		if (Event.TimeLeft <= 0.f || FVector::Dist2D(Event.Location, Player) > 40000.f)
		{
			EndEvent(Event);
			Active.RemoveAtSwap(Index);
		}
	}

	NextEvent -= DeltaTime;
	if (NextEvent > 0.f || Active.Num() >= 2)
	{
		return;
	}
	NextEvent = FMath::FRandRange(120.f, 260.f);
	const UVBTimeOfDaySubsystem* Time = World->GetSubsystem<UVBTimeOfDaySubsystem>();
	const bool bNight = Time && Time->GetNightFactor() > 0.7f;
	const float Roll = FMath::FRand();
	if (bNight && Roll < 0.3f && StartFireworks())
	{
		return;
	}
	if (Roll < 0.6f)
	{
		StartBreakdown();
	}
	else if (!bNight)
	{
		StartMusician();
	}
}
