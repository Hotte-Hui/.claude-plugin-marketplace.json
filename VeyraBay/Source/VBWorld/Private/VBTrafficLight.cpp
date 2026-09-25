#include "VBTrafficLight.h"

#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"

namespace VBSignal
{
	// Muss zu Tools/Blender/assets/vb_asset_streetkit.py passen (SIGNAL_LENS_X / SIGNAL_LENS_Z)
	static constexpr float LensX = 32.5f;
	static constexpr float LensZRed = 320.f;
	static constexpr float LensZAmber = 290.f;
	static constexpr float LensZGreen = 260.f;

	// LED-Signalfarben (linear)
	static const FLinearColor Red(1.f, 0.06f, 0.02f);
	static const FLinearColor Amber(1.f, 0.42f, 0.02f);
	static const FLinearColor Green(0.05f, 1.f, 0.55f);

	static UStaticMeshComponent* CreateLens(AActor* Owner, USceneComponent* Parent, const TCHAR* Name, float Z)
	{
		UStaticMeshComponent* Lens = Owner->CreateDefaultSubobject<UStaticMeshComponent>(Name);
		Lens->SetupAttachment(Parent);
		Lens->SetRelativeLocation(FVector(LensX, 0.f, Z));
		Lens->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Lens->SetCastShadow(false);
		return Lens;
	}
}

AVBTrafficLight::AVBTrafficLight()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = 0.1f;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	Body->SetupAttachment(Root);

	LensRed = VBSignal::CreateLens(this, Root, TEXT("LensRed"), VBSignal::LensZRed);
	LensAmber = VBSignal::CreateLens(this, Root, TEXT("LensAmber"), VBSignal::LensZAmber);
	LensGreen = VBSignal::CreateLens(this, Root, TEXT("LensGreen"), VBSignal::LensZGreen);

	SignalLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("SignalLight"));
	SignalLight->SetupAttachment(Root);
	SignalLight->SetRelativeLocation(FVector(VBSignal::LensX + 25.f, 0.f, VBSignal::LensZAmber));
	SignalLight->IntensityUnits = ELightUnits::Candelas;
	SignalLight->Intensity = 40.f;
	SignalLight->AttenuationRadius = 600.f;
	SignalLight->SourceRadius = 10.f;
	SignalLight->CastShadows = false;
	SignalLight->VolumetricScatteringIntensity = 2.f;
}

void AVBTrafficLight::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

	Body->SetStaticMesh(Model);
	for (UStaticMeshComponent* Lens : { LensRed.Get(), LensAmber.Get(), LensGreen.Get() })
	{
		Lens->SetStaticMesh(LensModel);
	}

	const UWorld* World = GetWorld();
	if (!World || !World->IsGameWorld())
	{
		// Editor-Vorschau: Farben und Zustand ohne Tick setzen
		SetupLensMaterial(LensRed, VBSignal::Red);
		SetupLensMaterial(LensAmber, VBSignal::Amber);
		SetupLensMaterial(LensGreen, VBSignal::Green);
		ApplyState(PreviewState, /*bBroadcast*/ false);
	}
}

void AVBTrafficLight::BeginPlay()
{
	Super::BeginPlay();

	SetupLensMaterial(LensRed, VBSignal::Red);
	SetupLensMaterial(LensAmber, VBSignal::Amber);
	SetupLensMaterial(LensGreen, VBSignal::Green);

	CycleTime = static_cast<float>(FMath::Fmod(GetWorld()->GetTimeSeconds() + static_cast<double>(FMath::Max(CycleOffset, 0.f)), static_cast<double>(GetCycleLength())));
	bHasState = false;
	ApplyState(StateAtCycleTime(CycleTime), /*bBroadcast*/ true);
}

void AVBTrafficLight::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Aus der Weltzeit statt aufsummiert: nachgeladene Ampeln bleiben synchron mit Verkehr und Nachbarn
	CycleTime = static_cast<float>(FMath::Fmod(GetWorld()->GetTimeSeconds() + static_cast<double>(FMath::Max(CycleOffset, 0.f)), static_cast<double>(GetCycleLength())));
	const EVBSignalState NewState = StateAtCycleTime(CycleTime);
	if (NewState != State)
	{
		ApplyState(NewState, /*bBroadcast*/ true);
	}
}

FVBSignalTiming AVBTrafficLight::GetTiming() const
{
	FVBSignalTiming Timing;
	Timing.Green = GreenSeconds;
	Timing.Amber = AmberSeconds;
	Timing.Red = RedSeconds;
	Timing.RedAmber = RedAmberSeconds;
	Timing.Offset = FMath::Max(CycleOffset, 0.f);
	return Timing;
}

EVBSignalState FVBSignalTiming::StateAt(double WorldSeconds, float* OutTimeUntilChange) const
{
	const float Length = CycleLength();
	const float Time = static_cast<float>(FMath::Fmod(WorldSeconds + static_cast<double>(Offset), static_cast<double>(Length)));
	const float Boundaries[4] = { Green, Green + Amber, Green + Amber + Red, Length };
	static const EVBSignalState States[4] = { EVBSignalState::Green, EVBSignalState::Amber, EVBSignalState::Red, EVBSignalState::RedAmber };
	for (int32 Index = 0; Index < 4; ++Index)
	{
		if (Time < Boundaries[Index])
		{
			if (OutTimeUntilChange)
			{
				*OutTimeUntilChange = Boundaries[Index] - Time;
			}
			return States[Index];
		}
	}
	if (OutTimeUntilChange)
	{
		*OutTimeUntilChange = 0.f;
	}
	return EVBSignalState::RedAmber;
}

float AVBTrafficLight::GetCycleLength() const
{
	return FMath::Max(GreenSeconds + AmberSeconds + RedSeconds + RedAmberSeconds, 1.f);
}

EVBSignalState AVBTrafficLight::StateAtCycleTime(float InCycleTime) const
{
	// Reihenfolge: Gruen -> Gelb -> Rot -> Rot-Gelb -> Gruen
	float Time = InCycleTime;
	if (Time < GreenSeconds) { return EVBSignalState::Green; }
	Time -= GreenSeconds;
	if (Time < AmberSeconds) { return EVBSignalState::Amber; }
	Time -= AmberSeconds;
	if (Time < RedSeconds) { return EVBSignalState::Red; }
	return EVBSignalState::RedAmber;
}

float AVBTrafficLight::GetTimeUntilChange() const
{
	const float Boundaries[] = { GreenSeconds, GreenSeconds + AmberSeconds, GreenSeconds + AmberSeconds + RedSeconds, GetCycleLength() };
	for (const float Boundary : Boundaries)
	{
		if (CycleTime < Boundary)
		{
			return Boundary - CycleTime;
		}
	}
	return 0.f;
}

void AVBTrafficLight::SetupLensMaterial(UStaticMeshComponent* Lens, const FLinearColor& Color)
{
	if (!Lens || !Lens->GetStaticMesh())
	{
		return;
	}
	if (UMaterialInstanceDynamic* Material = Lens->CreateDynamicMaterialInstance(0))
	{
		Material->SetVectorParameterValue(TEXT("EmissiveColor"), Color);
		Material->SetVectorParameterValue(TEXT("BaseColorTint"), Color * 0.2f);
	}
}

void AVBTrafficLight::ApplyState(EVBSignalState NewState, bool bBroadcast)
{
	const bool bChanged = !bHasState || NewState != State;
	State = NewState;
	bHasState = true;

	const bool bRed = (State == EVBSignalState::Red || State == EVBSignalState::RedAmber);
	const bool bAmber = (State == EVBSignalState::Amber || State == EVBSignalState::RedAmber);
	const bool bGreen = (State == EVBSignalState::Green);

	// Custom Primitive Data [0] = "LightOn" im Master-Material (UseNightSwitch = 1 in der Linsen-Instanz)
	LensRed->SetCustomPrimitiveDataFloat(0, bRed ? 1.f : 0.f);
	LensAmber->SetCustomPrimitiveDataFloat(0, bAmber ? 1.f : 0.f);
	LensGreen->SetCustomPrimitiveDataFloat(0, bGreen ? 1.f : 0.f);

	const FLinearColor LightColor = bGreen ? VBSignal::Green : (bAmber && !bRed ? VBSignal::Amber : VBSignal::Red);
	const float LightZ = bGreen ? VBSignal::LensZGreen : (bAmber && !bRed ? VBSignal::LensZAmber : VBSignal::LensZRed);
	SignalLight->SetLightColor(LightColor);
	SignalLight->SetRelativeLocation(FVector(VBSignal::LensX + 25.f, 0.f, LightZ));

	if (bBroadcast && bChanged)
	{
		OnSignalChanged.Broadcast(this, State);
	}
}
