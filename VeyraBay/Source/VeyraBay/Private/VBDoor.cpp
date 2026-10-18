#include "VBDoor.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

#define LOCTEXT_NAMESPACE "VBDoor"

AVBDoor::AVBDoor()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;

	Hinge = CreateDefaultSubobject<USceneComponent>(TEXT("Hinge"));
	Hinge->SetupAttachment(Root);

	// Tuerblatt 95 x 210 x 5 cm, erstreckt sich vom Scharnier entlang +Y
	Panel = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Panel"));
	Panel->SetupAttachment(Hinge);
	Panel->SetRelativeLocation(FVector(0.f, 47.5f, 105.f));
	Panel->SetRelativeScale3D(FVector(0.05f, 0.95f, 2.1f));
	if (CubeMesh.Succeeded())
	{
		Panel->SetStaticMesh(CubeMesh.Object);
	}

	Tags.Add(TEXT("VB_Prototype"));
}

FText AVBDoor::GetInteractionPrompt_Implementation(AActor* Interactor) const
{
	if (bLocked)
	{
		return LOCTEXT("Locked", "Abgeschlossen");
	}
	return bOpen ? LOCTEXT("Close", "Tuer schliessen") : LOCTEXT("Open", "Tuer oeffnen");
}

void AVBDoor::Interact_Implementation(AActor* Interactor)
{
	if (bLocked)
	{
		return;
	}

	bOpen = !bOpen;
	if (bOpen)
	{
		// Vom Spieler weg oeffnen: steht er auf der +X-Seite, schwingt die Tuer nach -X.
		float Side = 1.f;
		if (Interactor)
		{
			const FVector ToInteractor = Interactor->GetActorLocation() - GetActorLocation();
			Side = FVector::DotProduct(ToInteractor, GetActorForwardVector()) >= 0.0 ? 1.f : -1.f;
		}
		TargetAngle = OpenAngle * Side;
	}
	else
	{
		TargetAngle = 0.f;
	}

	SetActorTickEnabled(true);
}

void AVBDoor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	CurrentAngle = FMath::FInterpTo(CurrentAngle, TargetAngle, DeltaSeconds, SwingSpeed);
	if (FMath::IsNearlyEqual(CurrentAngle, TargetAngle, 0.05f))
	{
		CurrentAngle = TargetAngle;
		SetActorTickEnabled(false);
	}

	Hinge->SetRelativeRotation(FRotator(0.f, CurrentAngle, 0.f));
}

#undef LOCTEXT_NAMESPACE
