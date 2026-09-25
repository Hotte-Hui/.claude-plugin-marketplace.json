#include "VBStreetLight.h"

#include "VBNightLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

AVBStreetLight::AVBStreetLight()
{
	PrimaryActorTick.bCanEverTick = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;

	// Finales Modell (Blender-Asset), wird in OnConstruction befuellt
	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	Body->SetupAttachment(Root);

	// Mast: 8 m hoch, 18 cm Durchmesser (Engine-Zylinder = 100 x 100 cm, Pivot in der Mitte)
	Pole = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Pole"));
	Pole->SetupAttachment(Root);
	Pole->SetRelativeLocation(FVector(0.f, 0.f, 400.f));
	Pole->SetRelativeScale3D(FVector(0.18f, 0.18f, 8.f));

	// Ausleger: 1.6 m zur Strasse hin (+X)
	Arm = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Arm"));
	Arm->SetupAttachment(Root);
	Arm->SetRelativeLocation(FVector(80.f, 0.f, 790.f));
	Arm->SetRelativeScale3D(FVector(1.6f, 0.1f, 0.1f));

	// Leuchtenkopf
	Head = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Head"));
	Head->SetupAttachment(Root);
	Head->SetRelativeLocation(FVector(150.f, 0.f, 780.f));
	Head->SetRelativeScale3D(FVector(0.6f, 0.28f, 0.08f));
	Head->SetCastShadow(false);

	if (CylinderMesh.Succeeded())
	{
		Pole->SetStaticMesh(CylinderMesh.Object);
	}
	if (CubeMesh.Succeeded())
	{
		Arm->SetStaticMesh(CubeMesh.Object);
		Head->SetStaticMesh(CubeMesh.Object);
	}

	// LED-Strassenleuchte: ~3000 cd, 3800 K, breiter Kegel. Ergibt ~15-45 lux am Boden (realistisch).
	Lamp = CreateDefaultSubobject<USpotLightComponent>(TEXT("Lamp"));
	Lamp->SetupAttachment(Root);
	Lamp->SetMobility(EComponentMobility::Movable);
	Lamp->SetRelativeLocation(FVector(150.f, 0.f, 770.f));
	Lamp->SetRelativeRotation(FRotator(-90.f, 0.f, 0.f));
	Lamp->IntensityUnits = ELightUnits::Candelas;
	Lamp->Intensity = 3000.f;
	Lamp->AttenuationRadius = 2800.f;
	Lamp->InnerConeAngle = 25.f;
	Lamp->OuterConeAngle = 62.f;
	Lamp->SourceRadius = 15.f;
	Lamp->bUseTemperature = true;
	Lamp->Temperature = 3800.f;
	Lamp->VolumetricScatteringIntensity = 1.5f;
	Lamp->CastShadows = true;

	NightSwitch = CreateDefaultSubobject<UVBNightLightComponent>(TEXT("NightSwitch"));
}

void AVBStreetLight::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

	const bool bHasModel = (Model != nullptr);
	Body->SetStaticMesh(Model);
	Body->SetVisibility(bHasModel);
	Body->SetCollisionEnabled(bHasModel ? ECollisionEnabled::QueryAndPhysics : ECollisionEnabled::NoCollision);

	for (UStaticMeshComponent* Prototype : { Pole.Get(), Arm.Get(), Head.Get() })
	{
		Prototype->SetVisibility(!bHasModel);
		Prototype->SetCollisionEnabled(bHasModel ? ECollisionEnabled::NoCollision : ECollisionEnabled::QueryAndPhysics);
	}

	if (bHasModel)
	{
		Tags.Remove(TEXT("VB_Prototype"));
	}
	else
	{
		Tags.AddUnique(TEXT("VB_Prototype"));
	}
}
