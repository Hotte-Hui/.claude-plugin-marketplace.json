#include "VBTrafficVehicle.h"

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
	Tags.Add(TEXT("VB_TrafficVehicle"));
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
	SetCPD(4, Indicator < 0 ? Blink : 0.f);
	SetCPD(5, Indicator > 0 ? Blink : 0.f);
}
