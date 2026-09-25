#include "VBNightLightComponent.h"

#include "VBTimeOfDaySubsystem.h"
#include "VBWeatherSubsystem.h"
#include "Components/LightComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

UVBNightLightComponent::UVBNightLightComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = true;
	PrimaryComponentTick.TickInterval = 0.5f;
}

void UVBNightLightComponent::BeginPlay()
{
	Super::BeginPlay();

	EffectiveThreshold = FMath::Clamp(SwitchOnThreshold + FMath::FRandRange(-ThresholdJitter, ThresholdJitter), 0.02f, 0.98f);
	// Tick-Zeitpunkte verteilen, damit nicht hunderte Lampen im selben Frame pruefen
	SetComponentTickInterval(FMath::FRandRange(0.4f, 0.8f));

	SetLightsOn(ComputeDarkness() >= EffectiveThreshold);
}

void UVBNightLightComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	// Hysterese verhindert Flackern an der Schwelle
	const float Darkness = ComputeDarkness();
	if (!bLightsOn && Darkness >= EffectiveThreshold)
	{
		SetLightsOn(true);
	}
	else if (bLightsOn && Darkness < EffectiveThreshold - 0.05f)
	{
		SetLightsOn(false);
	}
}

float UVBNightLightComponent::ComputeDarkness() const
{
	const UWorld* World = GetWorld();
	const UVBTimeOfDaySubsystem* Time = World ? World->GetSubsystem<UVBTimeOfDaySubsystem>() : nullptr;
	float Darkness = Time ? Time->GetNightFactor() : 0.f;

	if (bReactToWeather)
	{
		if (const UVBWeatherSubsystem* Weather = World ? World->GetSubsystem<UVBWeatherSubsystem>() : nullptr)
		{
			const float WeatherDarkness = (1.f - Weather->GetCurrentState().SunTransmission) * 0.6f;
			Darkness = FMath::Max(Darkness, WeatherDarkness);
		}
	}
	return Darkness;
}

void UVBNightLightComponent::SetLightsOn(bool bOn)
{
	if (bHasApplied && bOn == bLightsOn)
	{
		return;
	}
	bLightsOn = bOn;
	bHasApplied = true;

	AActor* Owner = GetOwner();
	if (!Owner)
	{
		return;
	}

	TArray<ULightComponent*> Lights;
	Owner->GetComponents<ULightComponent>(Lights);
	for (ULightComponent* Light : Lights)
	{
		Light->SetVisibility(bOn);
	}

	TArray<UPrimitiveComponent*> Primitives;
	Owner->GetComponents<UPrimitiveComponent>(Primitives);
	for (UPrimitiveComponent* Primitive : Primitives)
	{
		Primitive->SetCustomPrimitiveDataFloat(0, bOn ? 1.f : 0.f);
	}
}
