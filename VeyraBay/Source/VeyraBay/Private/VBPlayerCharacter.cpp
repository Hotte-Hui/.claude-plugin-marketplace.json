#include "VBPlayerCharacter.h"

#include "VBAudioSubsystem.h"
#include "VBGameSettings.h"
#include "VBInputSet.h"
#include "VBInteractionComponent.h"
#include "VBLog.h"
#include "VBPlayerController.h"
#include "Animation/AnimInstance.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "EnhancedInputComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputActionValue.h"

namespace VBPlayer
{
	// Fallback-Pfade, falls die Projekteinstellungen noch leer sind (Third Person Pack / Game Animation Sample)
	static const TCHAR* FallbackMeshes[] =
	{
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny.SKM_Manny"),
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Quinn.SKM_Quinn"),
		TEXT("/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"),
	};

	static const TCHAR* FallbackAnimClasses[] =
	{
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed.ABP_Unarmed_C"),
		TEXT("/Game/Characters/Mannequins/Animations/ABP_Manny.ABP_Manny_C"),
		TEXT("/Game/Characters/Mannequins/Animations/ABP_Quinn.ABP_Quinn_C"),
	};
}

AVBPlayerCharacter::AVBPlayerCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	GetCapsuleComponent()->InitCapsuleSize(42.f, 96.f);

	bUseControllerRotationPitch = false;
	bUseControllerRotationYaw = false;
	bUseControllerRotationRoll = false;

	UCharacterMovementComponent* Movement = GetCharacterMovement();
	Movement->bOrientRotationToMovement = true;
	Movement->RotationRate = FRotator(0.f, 540.f, 0.f);
	Movement->MaxWalkSpeed = RunSpeed;
	Movement->MinAnalogWalkSpeed = 20.f;
	Movement->MaxAcceleration = 1400.f;
	Movement->BrakingDecelerationWalking = 1600.f;
	Movement->GroundFriction = 7.f;
	Movement->JumpZVelocity = 450.f;
	Movement->AirControl = 0.3f;

	// Mannequin: Fuesse an der Kapselunterseite, Blick entlang +X
	GetMesh()->SetRelativeLocationAndRotation(FVector(0.f, 0.f, -96.f), FRotator(0.f, -90.f, 0.f));

	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(RootComponent);
	CameraBoom->TargetArmLength = 320.f;
	CameraBoom->SocketOffset = FVector(0.f, 45.f, 55.f);
	CameraBoom->bUsePawnControlRotation = true;
	CameraBoom->bEnableCameraLag = true;
	CameraBoom->CameraLagSpeed = 14.f;
	CameraBoom->CameraLagMaxDistance = 60.f;
	CameraBoom->ProbeSize = 14.f;

	FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
	FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
	FollowCamera->bUsePawnControlRotation = false;
	FollowCamera->SetFieldOfView(DefaultFOV);

	Interaction = CreateDefaultSubobject<UVBInteractionComponent>(TEXT("Interaction"));
}

void AVBPlayerCharacter::BeginPlay()
{
	Super::BeginPlay();
	ApplyCharacterAssets();
}

void AVBPlayerCharacter::ApplyCharacterAssets()
{
	const UVBGameSettings* Settings = GetDefault<UVBGameSettings>();

	USkeletalMesh* Mesh = Settings->PlayerMesh.IsNull() ? nullptr : Settings->PlayerMesh.LoadSynchronous();
	for (int32 Index = 0; !Mesh && Index < UE_ARRAY_COUNT(VBPlayer::FallbackMeshes); ++Index)
	{
		Mesh = LoadObject<USkeletalMesh>(nullptr, VBPlayer::FallbackMeshes[Index], nullptr, LOAD_NoWarn | LOAD_Quiet);
	}

	UClass* AnimClass = Settings->PlayerAnimClass.IsNull() ? nullptr : Settings->PlayerAnimClass.LoadSynchronous();
	for (int32 Index = 0; !AnimClass && Index < UE_ARRAY_COUNT(VBPlayer::FallbackAnimClasses); ++Index)
	{
		AnimClass = LoadClass<UAnimInstance>(nullptr, VBPlayer::FallbackAnimClasses[Index], nullptr, LOAD_NoWarn | LOAD_Quiet);
	}

	bHasCharacterMesh = (Mesh != nullptr);
	if (!Mesh)
	{
		UE_LOG(LogVB, Warning, TEXT("Kein Spieler-Mesh gefunden. Third Person Pack hinzufuegen und 'Veyra Bay -> Projekt einrichten' ausfuehren."));
		return;
	}

	GetMesh()->SetSkeletalMeshAsset(Mesh);
	if (AnimClass)
	{
		GetMesh()->SetAnimInstanceClass(AnimClass);
	}
	else
	{
		UE_LOG(LogVB, Warning, TEXT("Kein Animation Blueprint gefunden - Spielfigur ist nicht animiert."));
	}
}

void AVBPlayerCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent);
	AVBPlayerController* PC = Cast<AVBPlayerController>(GetController());
	UVBInputSet* Set = PC ? PC->GetInputSet() : nullptr;
	if (!Input || !Set)
	{
		UE_LOG(LogVB, Error, TEXT("Enhanced Input nicht verfuegbar - pruefe Config/DefaultInput.ini."));
		return;
	}

	Input->BindAction(Set->Move, ETriggerEvent::Triggered, this, &AVBPlayerCharacter::Input_Move);
	Input->BindAction(Set->Look, ETriggerEvent::Triggered, this, &AVBPlayerCharacter::Input_Look);
	Input->BindAction(Set->LookGamepad, ETriggerEvent::Triggered, this, &AVBPlayerCharacter::Input_LookGamepad);
	Input->BindAction(Set->Jump, ETriggerEvent::Started, this, &ACharacter::Jump);
	Input->BindAction(Set->Jump, ETriggerEvent::Completed, this, &ACharacter::StopJumping);
	Input->BindAction(Set->Sprint, ETriggerEvent::Started, this, &AVBPlayerCharacter::Input_SprintStarted);
	Input->BindAction(Set->Sprint, ETriggerEvent::Completed, this, &AVBPlayerCharacter::Input_SprintCompleted);
	Input->BindAction(Set->WalkToggle, ETriggerEvent::Started, this, &AVBPlayerCharacter::Input_WalkToggle);
	Input->BindAction(Set->Interact, ETriggerEvent::Started, this, &AVBPlayerCharacter::Input_Interact);
}

void AVBPlayerCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Weiche Geschwindigkeitswechsel statt harter Spruenge
	UCharacterMovementComponent* Movement = GetCharacterMovement();
	Movement->MaxWalkSpeed = FMath::FInterpTo(Movement->MaxWalkSpeed, GetTargetSpeed(), DeltaSeconds, SpeedInterpRate);

	// Leichte FOV-Erweiterung beim Sprinten (Geschwindigkeitsgefuehl)
	const float TargetFOV = IsSprinting() ? SprintFOV : DefaultFOV;
	FollowCamera->SetFieldOfView(FMath::FInterpTo(FollowCamera->FieldOfView, TargetFOV, DeltaSeconds, 4.f));

	// Schritte
	if (Movement->IsMovingOnGround())
	{
		const float Speed = GetVelocity().Size2D();
		if (UVBAudioSubsystem::AdvanceStride(StrideDistance, Speed, DeltaSeconds))
		{
			UVBAudioSubsystem::PlayFootstep(this, GetActorLocation() - FVector(0.f, 0.f, 90.f), FMath::Clamp(Speed / 450.f, 0.35f, 1.f));
		}
	}
}

float AVBPlayerCharacter::GetTargetSpeed() const
{
	if (bSprintHeld)
	{
		return SprintSpeed;
	}
	return bWalkMode ? WalkSpeed : RunSpeed;
}

bool AVBPlayerCharacter::IsSprinting() const
{
	return bSprintHeld && GetVelocity().Size2D() > RunSpeed * 0.9f;
}

void AVBPlayerCharacter::Input_Move(const FInputActionValue& Value)
{
	const FVector2D Axis = Value.Get<FVector2D>();
	if (!Controller)
	{
		return;
	}

	const FRotator YawRotation(0.f, Controller->GetControlRotation().Yaw, 0.f);
	const FRotationMatrix YawMatrix(YawRotation);
	AddMovementInput(YawMatrix.GetUnitAxis(EAxis::X), Axis.Y);
	AddMovementInput(YawMatrix.GetUnitAxis(EAxis::Y), Axis.X);
}

void AVBPlayerCharacter::Input_Look(const FInputActionValue& Value)
{
	const FVector2D Axis = Value.Get<FVector2D>();
	const UVBGameSettings* Settings = GetDefault<UVBGameSettings>();
	const float Invert = Settings->bInvertMouseY ? -1.f : 1.f;

	AddControllerYawInput(Axis.X * Settings->MouseSensitivity);
	AddControllerPitchInput(Axis.Y * Settings->MouseSensitivity * Invert);
}

void AVBPlayerCharacter::Input_LookGamepad(const FInputActionValue& Value)
{
	AController* OwningController = GetController();
	const UWorld* World = GetWorld();
	if (!OwningController || !World)
	{
		return;
	}

	// Stick ist eine Drehrate (Grad/s) - unabhaengig von der Framerate
	const FVector2D Axis = Value.Get<FVector2D>();
	const float Rate = GetDefault<UVBGameSettings>()->GamepadLookRate;
	const float DeltaSeconds = World->GetDeltaSeconds();

	FRotator Rotation = OwningController->GetControlRotation();
	Rotation.Yaw += Axis.X * Rate * DeltaSeconds;
	Rotation.Pitch = FMath::ClampAngle(Rotation.Pitch + Axis.Y * Rate * 0.7f * DeltaSeconds, -75.f, 70.f);
	OwningController->SetControlRotation(Rotation);
}

void AVBPlayerCharacter::Input_SprintStarted(const FInputActionValue& Value)
{
	bSprintHeld = true;
}

void AVBPlayerCharacter::Input_SprintCompleted(const FInputActionValue& Value)
{
	bSprintHeld = false;
}

void AVBPlayerCharacter::Input_WalkToggle(const FInputActionValue& Value)
{
	bWalkMode = !bWalkMode;
}

void AVBPlayerCharacter::Input_Interact(const FInputActionValue& Value)
{
	Interaction->TryInteract();
}
