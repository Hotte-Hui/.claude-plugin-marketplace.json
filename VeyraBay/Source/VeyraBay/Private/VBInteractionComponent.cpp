#include "VBInteractionComponent.h"

#include "VBInteractable.h"
#include "CollisionQueryParams.h"
#include "WorldCollision.h"
#include "Engine/World.h"
#include "GameFramework/Controller.h"
#include "GameFramework/Pawn.h"

UVBInteractionComponent::UVBInteractionComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickInterval = 0.1f;
}

void UVBInteractionComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	UpdateFocus();
}

void UVBInteractionComponent::UpdateFocus()
{
	FocusedActor.Reset();
	FocusedPrompt = FText::GetEmpty();

	const APawn* Pawn = Cast<APawn>(GetOwner());
	const AController* Controller = Pawn ? Pawn->GetController() : nullptr;
	UWorld* World = GetWorld();
	if (!Controller || !World)
	{
		return;
	}

	FVector ViewLocation;
	FRotator ViewRotation;
	Controller->GetPlayerViewPoint(ViewLocation, ViewRotation);

	// Von der Kamera aus bis knapp hinter den Charakter + Reichweite
	const float CameraToPawn = FVector::Dist(ViewLocation, Pawn->GetActorLocation());
	const FVector End = ViewLocation + ViewRotation.Vector() * (CameraToPawn + InteractionRange);

	FCollisionQueryParams Params(SCENE_QUERY_STAT(VBInteraction), /*bTraceComplex*/ false, Pawn);
	FHitResult Hit;
	if (!World->SweepSingleByChannel(Hit, ViewLocation, End, FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(12.f), Params))
	{
		return;
	}

	AActor* HitActor = Hit.GetActor();
	if (!HitActor || !HitActor->Implements<UVBInteractable>())
	{
		return;
	}

	if (FVector::Dist(Hit.ImpactPoint, Pawn->GetActorLocation()) > InteractionRange)
	{
		return;
	}

	AActor* Interactor = GetOwner();
	if (!IVBInteractable::Execute_CanInteract(HitActor, Interactor))
	{
		return;
	}

	FocusedActor = HitActor;
	FocusedPrompt = IVBInteractable::Execute_GetInteractionPrompt(HitActor, Interactor);
}

bool UVBInteractionComponent::TryInteract()
{
	UpdateFocus();

	AActor* Target = FocusedActor.Get();
	if (!Target)
	{
		return false;
	}

	IVBInteractable::Execute_Interact(Target, GetOwner());
	UpdateFocus();
	return true;
}
