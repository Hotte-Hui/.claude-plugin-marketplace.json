#include "VBMissionMarker.h"

#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

AVBMissionMarker::AVBMissionMarker()
{
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));

	Beam = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Beam"));
	RootComponent = Beam;
	Beam->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Beam->SetCastShadow(false);
	Beam->SetMobility(EComponentMobility::Movable);
	if (Cylinder.Succeeded())
	{
		Beam->SetStaticMesh(Cylinder.Object);
	}

	Glow = CreateDefaultSubobject<UPointLightComponent>(TEXT("Glow"));
	Glow->SetupAttachment(Beam);
	Glow->SetUsingAbsoluteScale(true);
	Glow->SetIntensityUnits(ELightUnits::Candelas);
	Glow->SetIntensity(400.f);
	Glow->SetAttenuationRadius(1200.f);
	Glow->SetCastShadows(false);
	Glow->SetLightColor(FLinearColor(1.f, 0.75f, 0.2f));

	SetRadius(500.f);
}

void AVBMissionMarker::BeginPlay()
{
	Super::BeginPlay();
	if (UMaterialInterface* Base = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/VeyraBay/Materials/Gameplay/M_VB_MissionMarker.M_VB_MissionMarker"),
		nullptr, LOAD_NoWarn | LOAD_Quiet))
	{
		Material = UMaterialInstanceDynamic::Create(Base, this);
		Beam->SetMaterial(0, Material);
	}
}

void AVBMissionMarker::SetRadius(float RadiusCm)
{
	// Engine-Zylinder: 100 cm Durchmesser, 100 cm hoch, Pivot in der Mitte -> 30 m hohe Saeule.
	// Der Actor steht 15 m ueber dem Ziel (siehe UVBMissionSubsystem); das Licht sitzt 1.5 m ueber dem Boden.
	const float Height = 3000.f;
	Beam->SetRelativeScale3D(FVector(RadiusCm / 50.f, RadiusCm / 50.f, Height / 100.f));
	Glow->SetRelativeLocation(FVector(0.f, 0.f, -0.45f));
}

void AVBMissionMarker::SetColor(const FLinearColor& Color)
{
	if (Material)
	{
		Material->SetVectorParameterValue(TEXT("Color"), Color);
	}
	Glow->SetLightColor(Color);
}
