#include "VBPedestrian.h"

#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/CharacterMovementComponent.h"

AVBPedestrian::AVBPedestrian()
{
	PrimaryActorTick.bCanEverTick = false;
	AutoPossessAI = EAutoPossessAI::Disabled;

	GetCapsuleComponent()->InitCapsuleSize(36.f, 92.f);

	UCharacterMovementComponent* Movement = GetCharacterMovement();
	Movement->bRunPhysicsWithNoController = true;
	Movement->bOrientRotationToMovement = true;
	Movement->RotationRate = FRotator(0.f, 280.f, 0.f);
	Movement->MaxWalkSpeed = 135.f;
	Movement->MaxAcceleration = 500.f;
	Movement->BrakingDecelerationWalking = 700.f;
	Movement->bUseRVOAvoidance = true;           // Passanten weichen einander aus
	Movement->AvoidanceConsiderationRadius = 250.f;

	bUseControllerRotationYaw = false;

	USkeletalMeshComponent* Body = GetMesh();
	Body->SetRelativeLocationAndRotation(FVector(0.f, 0.f, -92.f), FRotator(0.f, -90.f, 0.f));
	Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
	Body->bEnableUpdateRateOptimizations = true;
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	Tags.Add(TEXT("VB_Pedestrian"));
}

void AVBPedestrian::SetWalkSpeed(float Speed)
{
	GetCharacterMovement()->MaxWalkSpeed = Speed;
}

void AVBPedestrian::MoveTowards(const FVector& Target, float SpeedScale)
{
	const FVector Direction = (Target - GetActorLocation()).GetSafeNormal2D();
	if (!Direction.IsNearlyZero())
	{
		AddMovementInput(Direction, SpeedScale, /*bForce*/ true);
	}
}

void AVBPedestrian::StandFacing(const FVector& Direction)
{
	const FVector Flat = Direction.GetSafeNormal2D();
	if (Flat.IsNearlyZero() || GetVelocity().Size2D() > 20.f)
	{
		return;
	}
	const FRotator Current = GetActorRotation();
	const FRotator Wanted(0.f, Flat.Rotation().Yaw, 0.f);
	SetActorRotation(FMath::RInterpTo(Current, Wanted, GetWorld()->GetDeltaSeconds(), 3.f));
}
