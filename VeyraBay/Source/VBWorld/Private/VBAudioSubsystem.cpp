#include "VBAudioSubsystem.h"

#include "VBTimeOfDaySubsystem.h"
#include "VBWeatherSubsystem.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/AudioComponent.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"

namespace VBAudio
{
	static const TCHAR* LoopNames[] = { TEXT("RainLight"), TEXT("RainHeavy"), TEXT("Wind"), TEXT("Sea"), TEXT("City"), TEXT("Birds"), TEXT("Crickets") };
	static constexpr float BaseVolume[] = { 0.7f, 0.9f, 0.6f, 0.8f, 0.45f, 0.35f, 0.3f };
}

USoundBase* UVBAudioSubsystem::LoadSound(const TCHAR* Name)
{
	const FString Path = FString::Printf(TEXT("/Game/VeyraBay/Audio/SW_VB_%s.SW_VB_%s"), Name, Name);
	return LoadObject<USoundBase>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
}

void UVBAudioSubsystem::PlayFootstep(const UObject* WorldContext, const FVector& Location, float Volume)
{
	static const TCHAR* Names[] = { TEXT("Footstep_1"), TEXT("Footstep_2"), TEXT("Footstep_3"), TEXT("Footstep_4") };
	if (USoundBase* Sound = LoadSound(Names[FMath::RandRange(0, 3)]))
	{
		UGameplayStatics::PlaySoundAtLocation(WorldContext, Sound, Location, Volume, FMath::FRandRange(0.9f, 1.1f));
	}
}

bool UVBAudioSubsystem::AdvanceStride(float& InOutDistance, float Speed, float DeltaSeconds)
{
	// Schrittlaenge waechst mit dem Tempo (Gehen ~0.75 m, Laufen ~1.2 m, Sprinten ~1.5 m)
	const float Stride = Speed > 500.f ? 150.f : (Speed > 250.f ? 120.f : 75.f);
	InOutDistance += Speed * DeltaSeconds;
	if (Speed < 20.f)
	{
		InOutDistance = Stride * 0.5f;
		return false;
	}
	if (InOutDistance >= Stride)
	{
		InOutDistance -= Stride;
		return true;
	}
	return false;
}

bool UVBAudioSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UVBAudioSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UVBAudioSubsystem, STATGROUP_Tickables);
}

void UVBAudioSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	Loops.Reset();
	CurrentVolume.Init(0.f, LoopCount);
	for (int32 Index = 0; Index < LoopCount; ++Index)
	{
		UAudioComponent* Component = nullptr;
		if (USoundBase* Sound = LoadSound(VBAudio::LoopNames[Index]))
		{
			Component = UGameplayStatics::CreateSound2D(&InWorld, Sound, 0.f, 1.f, 0.f, nullptr, false, false);
			if (Component)
			{
				Component->bIsUISound = false;
				Component->Play(FMath::FRandRange(0.f, 5.f));   // versetzt starten, damit Schleifen nicht gleichzeitig beginnen
			}
		}
		Loops.Add(Component);
	}
	ThunderSounds.Reset();
	for (const TCHAR* Name : { TEXT("Thunder_1"), TEXT("Thunder_2"), TEXT("Thunder_3") })
	{
		if (USoundBase* Sound = LoadSound(Name))
		{
			ThunderSounds.Add(Sound);
		}
	}
	bStarted = true;
}

void UVBAudioSubsystem::Deinitialize()
{
	for (UAudioComponent* Component : Loops)
	{
		if (Component)
		{
			Component->Stop();
		}
	}
	Loops.Reset();
	Super::Deinitialize();
}

void UVBAudioSubsystem::Tick(float DeltaTime)
{
	UWorld* World = GetWorld();
	if (!bStarted || !World)
	{
		return;
	}
	const UVBWeatherSubsystem* Weather = World->GetSubsystem<UVBWeatherSubsystem>();
	const UVBTimeOfDaySubsystem* Time = World->GetSubsystem<UVBTimeOfDaySubsystem>();
	const FVBWeatherState State = Weather ? Weather->GetCurrentState() : FVBWeatherState();
	const float Night = Time ? Time->GetNightFactor() : 0.f;
	const float Hour = Time ? Time->GetTimeOfDay() : 12.f;
	const float Rain = State.RainIntensity;

	FVector Listener = FVector::ZeroVector;
	if (const APlayerController* PC = World->GetFirstPlayerController())
	{
		if (PC->PlayerCameraManager)
		{
			Listener = PC->PlayerCameraManager->GetCameraLocation();
		}
	}
	const float CoastDistance = FMath::Max(0.f, static_cast<float>(Listener.Y) - CoastY);
	const float Altitude = FMath::Clamp(static_cast<float>(Listener.Z) / 8000.f, 0.f, 1.f);

	float Target[LoopCount];
	Target[RainLight] = FMath::Clamp(Rain * 2.5f, 0.f, 1.f) * (1.f - FMath::Clamp((Rain - 0.45f) * 2.5f, 0.f, 1.f));
	Target[RainHeavy] = FMath::Clamp((Rain - 0.35f) * 2.f, 0.f, 1.f);
	Target[Wind] = FMath::Clamp(0.12f + FMath::Pow(State.WindStrength, 1.5f) * 0.9f + Altitude * 0.4f, 0.f, 1.f);
	Target[Sea] = FMath::Clamp(1.f - CoastDistance / 20000.f, 0.f, 1.f) * (0.6f + 0.4f * State.WindStrength);
	Target[City] = (1.f - 0.6f * Night) * (1.f - 0.4f * Rain) * (1.f - Altitude * 0.5f) * FMath::Clamp(CoastDistance / 6000.f + 0.4f, 0.f, 1.f);
	const float Morning = FMath::Clamp((Hour - 5.f) / 1.5f, 0.f, 1.f) * FMath::Clamp((20.5f - Hour) / 1.5f, 0.f, 1.f);
	Target[Birds] = Morning * (1.f - Night) * (1.f - FMath::Clamp(Rain * 3.f, 0.f, 1.f));
	Target[Crickets] = Night * (1.f - FMath::Clamp(Rain * 3.f, 0.f, 1.f)) * (1.f - FMath::Clamp(State.WindStrength * 1.5f - 0.3f, 0.f, 1.f));

	for (int32 Index = 0; Index < LoopCount; ++Index)
	{
		UAudioComponent* Component = Loops.IsValidIndex(Index) ? Loops[Index].Get() : nullptr;
		if (!Component)
		{
			continue;
		}
		CurrentVolume[Index] = FMath::FInterpTo(CurrentVolume[Index], Target[Index], DeltaTime, 0.6f);
		Component->SetVolumeMultiplier(FMath::Max(CurrentVolume[Index] * VBAudio::BaseVolume[Index] * AmbientVolume, 0.001f));
	}

	// Donner: Blitz erkannt -> Donner nach 0.5..6 s (Entfernung), lauter bei kurzer Verzoegerung
	const float Flash = Weather ? Weather->GetLightningFlash() : 0.f;
	if (Flash > 0.5f && LastFlash <= 0.5f && ThunderSounds.Num() > 0)
	{
		PendingThunder.Add(FMath::FRandRange(0.5f, 6.f));
	}
	LastFlash = Flash;
	for (int32 Index = PendingThunder.Num() - 1; Index >= 0; --Index)
	{
		PendingThunder[Index] -= DeltaTime;
		if (PendingThunder[Index] <= 0.f)
		{
			USoundBase* Sound = ThunderSounds[FMath::RandRange(0, ThunderSounds.Num() - 1)];
			const float Volume = FMath::FRandRange(0.6f, 1.f) * AmbientVolume;
			UGameplayStatics::PlaySound2D(World, Sound, Volume, FMath::FRandRange(0.85f, 1.1f));
			PendingThunder.RemoveAtSwap(Index);
		}
	}
}
