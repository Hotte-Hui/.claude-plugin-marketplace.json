#include "VBTrafficVehicle.h"

#include "VBAudioSubsystem.h"
#include "Components/AudioComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"

AVBTrafficVehicle::AVBTrafficVehicle()
{
	PrimaryActorTick.bCanEverTick = false;     // Bewegung kommt vom Traffic Manager

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	Body->SetMobility(EComponentMobility::Movable);
	Body->SetCollisionProfileName(TEXT("BlockAllDynamic"));
	Body->SetGenerateOverlapEvents(false);
	RootComponent = Body;

	static const TCHAR* Names[4] = { TEXT("WheelFL"), TEXT("WheelFR"), TEXT("WheelRL"), TEXT("WheelRR") };
	for (int32 Index = 0; Index < 4; ++Index)
	{
		UStaticMeshComponent* Wheel = CreateDefaultSubobject<UStaticMeshComponent>(Names[Index]);
		Wheel->SetupAttachment(Body);
		Wheel->SetMobility(EComponentMobility::Movable);
		Wheel->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Wheel->SetGenerateOverlapEvents(false);
		Wheels.Add(Wheel);
	}
	EngineAudio = CreateDefaultSubobject<UAudioComponent>(TEXT("EngineAudio"));
	EngineAudio->SetupAttachment(Body);
	EngineAudio->bAutoActivate = false;
	EngineAudio->bOverrideAttenuation = true;
	EngineAudio->AttenuationOverrides.bAttenuate = true;
	EngineAudio->AttenuationOverrides.bSpatialize = true;
	EngineAudio->AttenuationOverrides.AttenuationShapeExtents = FVector(300.f, 0.f, 0.f);
	EngineAudio->AttenuationOverrides.FalloffDistance = 3000.f;

	Tags.Add(TEXT("VB_TrafficVehicle"));
}

void AVBTrafficVehicle::UpdateAudio(float SpeedCm, bool bNear)
{
	if (!bNear)
	{
		if (EngineAudio->IsPlaying())
		{
			EngineAudio->Stop();
		}
		return;
	}
	if (!EngineAudio->GetSound())
	{
		EngineAudio->SetSound(UVBAudioSubsystem::LoadSound(TEXT("Engine")));
	}
	if (!EngineAudio->IsPlaying())
	{
		EngineAudio->Play(FMath::FRandRange(0.f, 2.f));
	}
	// Grobe Drehzahl aus dem Tempo (Automatik): 900..3500 U/min
	const float Kmh = SpeedCm * 0.036f;
	const float Rpm = 900.f + FMath::Fmod(Kmh, 25.f) / 25.f * 1800.f + Kmh * 12.f;
	EngineAudio->SetPitchMultiplier(FMath::Clamp(Rpm / 2000.f, 0.4f, 2.f) * (Type.Agility < 0.7f ? 0.7f : 1.f));
	EngineAudio->SetVolumeMultiplier(Type.Agility < 0.7f ? 0.7f : 0.45f);
}

FVector AVBTrafficVehicle::WheelBase(int32 Index) const
{
	const float X = (Index < 2 ? 0.5f : -0.5f) * Type.Wheelbase;
	const float Y = (Index % 2 == 0 ? -1.f : 1.f) * (Type.Width * 0.5f - Type.WheelWidth * 0.55f);
	return FVector(X, Y, Type.WheelRadius);
}

void AVBTrafficVehicle::Configure(const FVBTrafficVehicleType& InType, const FLinearColor& InPaint)
{
	Type = InType;
	Body->SetStaticMesh(Type.BodyMesh);
	for (int32 Index = 0; Index < Wheels.Num(); ++Index)
	{
		Wheels[Index]->SetStaticMesh(Type.WheelMesh);
		Wheels[Index]->SetRelativeLocationAndRotation(WheelBase(Index), FRotator(0.f, Index % 2 == 0 ? 180.f : 0.f, 0.f));
	}
	SetCPD(6, InPaint.R);
	SetCPD(7, InPaint.G);
	SetCPD(8, InPaint.B);
}

void AVBTrafficVehicle::SetCPD(int32 Index, float Value)
{
	const TArray<float>& Current = Body->GetCustomPrimitiveData().Data;
	if (!Current.IsValidIndex(Index) || !FMath::IsNearlyEqual(Current[Index], Value, 1e-3f))
	{
		Body->SetCustomPrimitiveDataFloat(Index, Value);
	}
}

void AVBTrafficVehicle::UpdateVisuals(float DeltaSeconds, float SpeedCm, float SteerDegrees, bool bBraking, bool bLights, int32 Indicator)
{
	if (Type.WheelRadius > 1.f)
	{
		WheelAngle = FMath::Fmod(WheelAngle + FMath::RadiansToDegrees(SpeedCm * DeltaSeconds / Type.WheelRadius), 360.f);
	}
	for (int32 Index = 0; Index < Wheels.Num(); ++Index)
	{
		const float Steer = Index < 2 ? SteerDegrees : 0.f;
		const FQuat Rotation = FRotator(0.f, Steer, 0.f).Quaternion() * FRotator(-WheelAngle, 0.f, 0.f).Quaternion()
			* FRotator(0.f, Index % 2 == 0 ? 180.f : 0.f, 0.f).Quaternion();
		Wheels[Index]->SetRelativeRotation(Rotation);
	}

	BlinkTime = Indicator != 0 ? BlinkTime + DeltaSeconds : 0.f;
	const float Blink = (Indicator != 0 && FMath::Fmod(BlinkTime, 0.667f) < 0.36f) ? 1.f : 0.f;
	SetCPD(2, bBraking ? 1.f : (bLights ? 0.3f : 0.f));
	SetCPD(3, bLights ? 1.f : 0.f);
	SetCPD(4, (Indicator < 0 || Indicator == 2) ? Blink : 0.f);
	SetCPD(5, Indicator > 0 ? Blink : 0.f);
}
