#include "VBFireworks.h"

#include "VBAudioSubsystem.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace VBFireworksConst
{
	static constexpr int32 Pool = 1400;
	static constexpr int32 SparksPerBurst = 46;
	static const FLinearColor Colors[] = {
		FLinearColor(1.f, 0.35f, 0.15f), FLinearColor(1.f, 0.85f, 0.3f), FLinearColor(0.3f, 0.6f, 1.f),
		FLinearColor(0.4f, 1.f, 0.45f), FLinearColor(1.f, 0.3f, 0.8f), FLinearColor(1.f, 1.f, 1.f),
	};
}

AVBFireworks::AVBFireworks()
{
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	Sparks = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Sparks"));
	RootComponent = Sparks;
	Sparks->SetMobility(EComponentMobility::Movable);
	Sparks->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Sparks->SetCastShadow(false);
	Sparks->NumCustomDataFloats = 4;
	if (Sphere.Succeeded())
	{
		Sparks->SetStaticMesh(Sphere.Object);
	}

	Flash = CreateDefaultSubobject<UPointLightComponent>(TEXT("Flash"));
	Flash->SetupAttachment(Sparks);
	Flash->SetUsingAbsoluteLocation(true);
	Flash->SetIntensityUnits(ELightUnits::Candelas);
	Flash->SetIntensity(0.f);
	Flash->SetAttenuationRadius(45000.f);
	Flash->SetCastShadows(false);
}

void AVBFireworks::BeginPlay()
{
	Super::BeginPlay();
	if (UMaterialInterface* SparkMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/VeyraBay/Materials/Gameplay/M_VB_Spark.M_VB_Spark"),
		nullptr, LOAD_NoWarn | LOAD_Quiet))
	{
		Sparks->SetMaterial(0, SparkMaterial);
	}
	// Instanz-Pool (unsichtbar, Skalierung 0)
	TArray<FTransform> Hidden;
	Hidden.Init(FTransform(FQuat::Identity, GetActorLocation(), FVector::ZeroVector), VBFireworksConst::Pool);
	Sparks->AddInstances(Hidden, false, true);

	for (int32 Index = 0; Index < Rockets; ++Index)
	{
		LaunchTimes.Add(FMath::FRandRange(1.f, ShowSeconds - 4.f));
	}
	LaunchTimes.Sort();
	BangSound = UVBAudioSubsystem::LoadSound(TEXT("Thunder_2"));
}

void AVBFireworks::Burst(const FVector& Center)
{
	const FLinearColor Color = VBFireworksConst::Colors[FMath::RandRange(0, UE_ARRAY_COUNT(VBFireworksConst::Colors) - 1)];
	const float Speed = FMath::FRandRange(1600.f, 2600.f);
	for (int32 Index = 0; Index < VBFireworksConst::SparksPerBurst && Live.Num() < VBFireworksConst::Pool; ++Index)
	{
		FSpark Spark;
		Spark.Position = Center;
		Spark.Velocity = FMath::VRand() * Speed * FMath::FRandRange(0.85f, 1.f);
		Spark.Color = Color;
		Spark.Life = FMath::FRandRange(1.8f, 2.8f);
		Live.Add(Spark);
	}
	Flash->SetWorldLocation(Center);
	Flash->SetLightColor(Color);
	FlashLevel = 1.f;

	// Knall mit Schallverzoegerung (343 m/s)
	if (const APlayerController* PC = GetWorld()->GetFirstPlayerController())
	{
		FVector View;
		FRotator Rotation;
		PC->GetPlayerViewPoint(View, Rotation);
		const float Distance = FVector::Dist(View, Center);
		PendingBangs.Add(TPair<float, float>(Distance / 34300.f, FMath::Clamp(40000.f / FMath::Max(Distance, 1.f), 0.15f, 0.9f)));
	}
}

void AVBFireworks::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	Elapsed += DeltaSeconds;

	while (NextRocket < LaunchTimes.Num() && LaunchTimes[NextRocket] <= Elapsed)
	{
		const FVector Center = GetActorLocation() + FVector(FMath::FRandRange(-8000.f, 8000.f), FMath::FRandRange(-4000.f, 4000.f),
			FMath::FRandRange(9000.f, 15000.f));
		Burst(Center);
		++NextRocket;
	}

	// Funken: Schwerkraft, Luftwiderstand, verglimmen
	TArray<FTransform> Transforms;
	Transforms.Reserve(VBFireworksConst::Pool);
	for (int32 Index = Live.Num() - 1; Index >= 0; --Index)
	{
		FSpark& Spark = Live[Index];
		Spark.Age += DeltaSeconds;
		if (Spark.Age >= Spark.Life)
		{
			Live.RemoveAtSwap(Index);
			continue;
		}
		Spark.Velocity *= FMath::Exp(-1.6f * DeltaSeconds);
		Spark.Velocity.Z -= 450.f * DeltaSeconds;
		Spark.Position += Spark.Velocity * DeltaSeconds;
	}
	for (int32 Index = 0; Index < VBFireworksConst::Pool; ++Index)
	{
		if (Live.IsValidIndex(Index))
		{
			const FSpark& Spark = Live[Index];
			const float Fade = 1.f - Spark.Age / Spark.Life;
			Transforms.Add(FTransform(FQuat::Identity, Spark.Position, FVector(0.5f * (0.4f + 0.6f * Fade))));
			const float Brightness = 60.f * Fade * Fade * (0.7f + 0.3f * FMath::Sin(Spark.Age * 40.f + Index));
			Sparks->SetCustomDataValue(Index, 0, Spark.Color.R, false);
			Sparks->SetCustomDataValue(Index, 1, Spark.Color.G, false);
			Sparks->SetCustomDataValue(Index, 2, Spark.Color.B, false);
			Sparks->SetCustomDataValue(Index, 3, Brightness, false);
		}
		else
		{
			Transforms.Add(FTransform(FQuat::Identity, GetActorLocation(), FVector::ZeroVector));
		}
	}
	Sparks->BatchUpdateInstancesTransforms(0, Transforms, true, true, true);

	FlashLevel = FMath::Max(FlashLevel - DeltaSeconds * 2.2f, 0.f);
	Flash->SetIntensity(FlashLevel * FlashLevel * 60000.f);

	for (int32 Index = PendingBangs.Num() - 1; Index >= 0; --Index)
	{
		PendingBangs[Index].Key -= DeltaSeconds;
		if (PendingBangs[Index].Key <= 0.f)
		{
			if (BangSound)
			{
				UGameplayStatics::PlaySound2D(this, BangSound, PendingBangs[Index].Value, FMath::FRandRange(1.8f, 2.4f));
			}
			PendingBangs.RemoveAtSwap(Index);
		}
	}

	if (Elapsed > ShowSeconds && Live.Num() == 0 && PendingBangs.Num() == 0)
	{
		Destroy();
	}
}
