#include "VBVehicle.h"

#include "VBInputSet.h"
#include "VBPlayerController.h"
#include "VBAudioSubsystem.h"
#include "VBTimeOfDaySubsystem.h"
#include "VBWeatherSubsystem.h"
#include "Camera/CameraComponent.h"
#include "Components/AudioComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"
#include "ChaosWheeledVehicleMovementComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EnhancedInputComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputActionValue.h"

#define LOCTEXT_NAMESPACE "VBVehicle"

namespace VBVehicleCPD
{
	static constexpr int32 Brake = 2;
	static constexpr int32 Headlight = 3;
	static constexpr int32 IndicatorLeft = 4;
	static constexpr int32 IndicatorRight = 5;
	static constexpr int32 Paint = 6;   // 6, 7, 8
}

static const FName WheelBones[4] = { TEXT("wheel_fl"), TEXT("wheel_fr"), TEXT("wheel_rl"), TEXT("wheel_rr") };

// ---------------------------------------------------------------------------------------------
// Raeder
// ---------------------------------------------------------------------------------------------
UVBWheelFront::UVBWheelFront()
{
	AxleType = EAxleType::Front;
	bAffectedBySteering = true;
	bAffectedByBrake = true;
	bAffectedByHandbrake = false;
	bAffectedByEngine = false;
	MaxSteerAngle = 38.f;
	MaxBrakeTorque = 2200.f;
	FrictionForceMultiplier = 2.5f;
	CorneringStiffness = 1000.f;
	SuspensionMaxRaise = 9.f;
	SuspensionMaxDrop = 11.f;
	SpringRate = 250.f;
	SpringPreload = 50.f;
	SuspensionDampingRatio = 0.55f;
	bABSEnabled = true;
	bTractionControlEnabled = true;
}

UVBWheelRear::UVBWheelRear()
{
	AxleType = EAxleType::Rear;
	bAffectedBySteering = false;
	bAffectedByBrake = true;
	bAffectedByHandbrake = true;
	bAffectedByEngine = true;
	MaxSteerAngle = 0.f;
	MaxBrakeTorque = 1600.f;
	MaxHandBrakeTorque = 3500.f;
	FrictionForceMultiplier = 2.5f;
	CorneringStiffness = 1000.f;
	SuspensionMaxRaise = 9.f;
	SuspensionMaxDrop = 11.f;
	SpringRate = 250.f;
	SpringPreload = 50.f;
	SuspensionDampingRatio = 0.55f;
	bABSEnabled = true;
	bTractionControlEnabled = true;
}

// ---------------------------------------------------------------------------------------------
// Fahrzeug
// ---------------------------------------------------------------------------------------------
AVBVehicle::AVBVehicle(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryActorTick.bCanEverTick = true;

	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(GetMesh());
	CameraBoom->bUsePawnControlRotation = false;
	CameraBoom->bInheritPitch = false;
	CameraBoom->bInheritRoll = false;
	CameraBoom->bInheritYaw = true;
	CameraBoom->bEnableCameraLag = true;
	CameraBoom->bEnableCameraRotationLag = true;
	CameraBoom->CameraLagSpeed = 12.f;
	CameraBoom->CameraRotationLagSpeed = 7.f;
	CameraBoom->ProbeSize = 16.f;

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
	Camera->FieldOfView = CameraFOV;

	static const TCHAR* WheelNames[4] = { TEXT("WheelFL"), TEXT("WheelFR"), TEXT("WheelRL"), TEXT("WheelRR") };
	for (int32 Index = 0; Index < 4; ++Index)
	{
		UStaticMeshComponent* Wheel = CreateDefaultSubobject<UStaticMeshComponent>(WheelNames[Index]);
		Wheel->SetupAttachment(GetMesh());
		Wheel->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Wheel->SetGenerateOverlapEvents(false);
		WheelMeshes.Add(Wheel);
	}

	auto MakeHeadlight = [this](const TCHAR* Name)
	{
		USpotLightComponent* Light = CreateDefaultSubobject<USpotLightComponent>(Name);
		Light->SetupAttachment(GetMesh());
		Light->SetIntensityUnits(ELightUnits::Candelas);
		Light->SetIntensity(0.f);
		Light->SetLightColor(FLinearColor(1.f, 0.94f, 0.86f));
		Light->SetAttenuationRadius(6000.f);
		Light->SetInnerConeAngle(14.f);
		Light->SetOuterConeAngle(34.f);
		Light->SetSourceRadius(6.f);
		Light->SetVisibility(false);
		return Light;
	};
	HeadlightLeft = MakeHeadlight(TEXT("HeadlightLeft"));
	HeadlightRight = MakeHeadlight(TEXT("HeadlightRight"));
	HeadlightRight->SetCastShadows(false);      // ein Schatten reicht optisch, spart GPU-Zeit

	// Klang: Motor (Tonhoehe nach Drehzahl), Reifen (nach Tempo), Blinker, Hupe - raeumlich, 40 m Reichweite
	auto MakeAudio = [this](const TCHAR* Name)
	{
		UAudioComponent* Audio = CreateDefaultSubobject<UAudioComponent>(Name);
		Audio->SetupAttachment(GetMesh());
		Audio->bAutoActivate = false;
		Audio->bOverrideAttenuation = true;
		Audio->AttenuationOverrides.bAttenuate = true;
		Audio->AttenuationOverrides.bSpatialize = true;
		Audio->AttenuationOverrides.AttenuationShapeExtents = FVector(600.f, 0.f, 0.f);
		Audio->AttenuationOverrides.FalloffDistance = 4000.f;
		return Audio;
	};
	EngineAudio = MakeAudio(TEXT("EngineAudio"));
	TireAudio = MakeAudio(TEXT("TireAudio"));
	IndicatorAudio = MakeAudio(TEXT("IndicatorAudio"));
	HornAudio = MakeAudio(TEXT("HornAudio"));

	UChaosWheeledVehicleMovementComponent* Movement = GetWheeledMovement();
	Movement->WheelSetups.SetNum(4);
	for (int32 Index = 0; Index < 4; ++Index)
	{
		Movement->WheelSetups[Index].WheelClass = Index < 2 ? UVBWheelFront::StaticClass() : UVBWheelRear::StaticClass();
		Movement->WheelSetups[Index].BoneName = WheelBones[Index];
	}

	// Motor: Drehmomentkurve (wird von Chaos auf das Maximum normiert und mit MaxTorque skaliert)
	FRichCurve* Torque = Movement->EngineSetup.TorqueCurve.GetRichCurve();
	Torque->Reset();
	Torque->AddKey(0.f, 0.55f);
	Torque->AddKey(1500.f, 0.85f);
	Torque->AddKey(3500.f, 1.f);
	Torque->AddKey(5500.f, 0.95f);
	Torque->AddKey(7000.f, 0.7f);
	Movement->EngineSetup.EngineIdleRPM = 850.f;
	Movement->EngineSetup.EngineBrakeEffect = 0.12f;
	Movement->EngineSetup.EngineRevUpMOI = 5.f;
	Movement->EngineSetup.EngineRevDownRate = 600.f;

	Movement->TransmissionSetup.bUseAutomaticGears = true;
	Movement->TransmissionSetup.bUseAutoReverse = true;
	Movement->TransmissionSetup.FinalRatio = 3.6f;
	Movement->TransmissionSetup.ForwardGearRatios = { 3.6f, 2.2f, 1.5f, 1.15f, 0.92f, 0.76f };
	Movement->TransmissionSetup.ReverseGearRatios = { 3.4f };
	Movement->TransmissionSetup.ChangeUpRPM = 5200.f;
	Movement->TransmissionSetup.ChangeDownRPM = 2000.f;
	Movement->TransmissionSetup.GearChangeTime = 0.3f;

	Movement->SteeringSetup.SteeringType = ESteeringType::AngleRatio;
	Movement->SteeringSetup.AngleRatio = 0.75f;
	// Weniger Lenkeinschlag bei hohem Tempo (x = km/h, y = Anteil)
	FRichCurve* SteeringCurve = Movement->SteeringSetup.SteeringCurve.GetRichCurve();
	SteeringCurve->Reset();
	SteeringCurve->AddKey(0.f, 1.f);
	SteeringCurve->AddKey(60.f, 0.7f);
	SteeringCurve->AddKey(140.f, 0.4f);

	Movement->DragCoefficient = 0.32f;
	Movement->DownforceCoefficient = 0.1f;
	Movement->bEnableCenterOfMassOverride = true;
	Movement->bReverseAsBrake = true;

	Tags.Add(TEXT("VB_Vehicle"));
}

UChaosWheeledVehicleMovementComponent* AVBVehicle::GetWheeledMovement() const
{
	return CastChecked<UChaosWheeledVehicleMovementComponent>(GetVehicleMovementComponent());
}

FVector AVBVehicle::WheelBaseLocation(int32 Index) const
{
	const float X = (Index < 2 ? 0.5f : -0.5f) * Wheelbase;
	const float Y = (Index % 2 == 0 ? -1.f : 1.f) * (Width * 0.5f - WheelWidth * 0.55f);
	return FVector(X, Y, WheelRadius);
}

void AVBVehicle::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	ApplySpec();
}

void AVBVehicle::ApplySpec()
{
	UChaosWheeledVehicleMovementComponent* Movement = GetWheeledMovement();
	Movement->Mass = MassKg;
	Movement->ChassisWidth = Width;
	Movement->ChassisHeight = 140.f;
	Movement->CenterOfMassOverride = FVector(0.f, 0.f, WheelRadius + 15.f);
	Movement->EngineSetup.MaxTorque = MaxTorque;
	Movement->EngineSetup.MaxRPM = MaxRPM;
	Movement->TransmissionSetup.ChangeUpRPM = MaxRPM * 0.82f;
	Movement->DifferentialSetup.DifferentialType = bAllWheelDrive ? EVehicleDifferential::AllWheelDrive : EVehicleDifferential::RearWheelDrive;
	Movement->DifferentialSetup.FrontRearSplit = 0.4f;

	for (int32 Index = 0; Index < WheelMeshes.Num(); ++Index)
	{
		UStaticMeshComponent* Wheel = WheelMeshes[Index];
		Wheel->SetStaticMesh(WheelMesh);
		Wheel->SetRelativeLocation(WheelBaseLocation(Index));
		// Felge des Rad-Meshes zeigt nach +Y (rechts) -> linke Raeder um 180 Grad drehen
		Wheel->SetRelativeRotation(FRotator(0.f, Index % 2 == 0 ? 180.f : 0.f, 0.f));
	}

	const float FrontX = Length * 0.5f - 10.f;
	const float LampY = Width * 0.5f - 30.f;
	const float LampZ = WheelRadius + 38.f;
	HeadlightLeft->SetRelativeLocationAndRotation(FVector(FrontX, -LampY, LampZ), FRotator(-3.f, -1.5f, 0.f));
	HeadlightRight->SetRelativeLocationAndRotation(FVector(FrontX, LampY, LampZ), FRotator(-3.f, 1.5f, 0.f));

	CameraBoom->TargetArmLength = Length * 0.9f + 220.f;
	CameraBoom->SocketOffset = FVector(0.f, 0.f, 90.f);
	CameraBoom->SetRelativeLocation(FVector(0.f, 0.f, 120.f));
	CameraBoom->SetRelativeRotation(FRotator(-10.f, 0.f, 0.f));

	SetCPD(VBVehicleCPD::Paint + 0, PaintColor.R);
	SetCPD(VBVehicleCPD::Paint + 1, PaintColor.G);
	SetCPD(VBVehicleCPD::Paint + 2, PaintColor.B);
}

void AVBVehicle::SetCPD(int32 Index, float Value)
{
	USkeletalMeshComponent* Body = GetMesh();
	const TArray<float>& Current = Body->GetCustomPrimitiveData().Data;
	if (!Current.IsValidIndex(Index) || !FMath::IsNearlyEqual(Current[Index], Value, 1e-3f))
	{
		Body->SetCustomPrimitiveDataFloat(Index, Value);
	}
}

void AVBVehicle::BeginPlay()
{
	Super::BeginPlay();

	UChaosWheeledVehicleMovementComponent* Movement = GetWheeledMovement();
	BaseFriction.Reset();
	for (int32 Index = 0; Index < Movement->Wheels.Num(); ++Index)
	{
		Movement->SetWheelRadius(Index, WheelRadius);
		BaseFriction.Add(Movement->Wheels[Index] ? Movement->Wheels[Index]->FrictionForceMultiplier : 2.5f);
	}
	// Ohne Fahrer: Handbremse angezogen
	Movement->SetHandbrakeInput(true);
	UpdateGrip();

	EngineAudio->SetSound(UVBAudioSubsystem::LoadSound(TEXT("Engine")));
	TireAudio->SetSound(UVBAudioSubsystem::LoadSound(TEXT("Tires")));
	IndicatorAudio->SetSound(UVBAudioSubsystem::LoadSound(TEXT("Indicator")));
	HornAudio->SetSound(UVBAudioSubsystem::LoadSound(TEXT("Horn")));
	DoorSound = UVBAudioSubsystem::LoadSound(TEXT("CarDoor"));
}

// ---------------------------------------------------------------------------------------------
// Ein- und Aussteigen
// ---------------------------------------------------------------------------------------------
FText AVBVehicle::GetInteractionPrompt_Implementation(AActor* Interactor) const
{
	return LOCTEXT("Enter", "Einsteigen");
}

bool AVBVehicle::CanInteract_Implementation(AActor* Interactor) const
{
	return Driver == nullptr && Cast<APawn>(Interactor) != nullptr;
}

void AVBVehicle::Interact_Implementation(AActor* Interactor)
{
	APawn* Pawn = Cast<APawn>(Interactor);
	AController* DriverController = Pawn ? Pawn->GetController() : nullptr;
	if (!Pawn || !DriverController || Driver)
	{
		return;
	}

	Driver = Pawn;
	if (ACharacter* Character = Cast<ACharacter>(Pawn))
	{
		Character->GetCharacterMovement()->StopMovementImmediately();
		Character->GetCharacterMovement()->DisableMovement();
	}
	Pawn->SetActorEnableCollision(false);
	Pawn->SetActorHiddenInGame(true);
	Pawn->AttachToActor(this, FAttachmentTransformRules::KeepWorldTransform);

	LookOffset = FRotator::ZeroRotator;
	DriverController->Possess(this);
	GetWheeledMovement()->SetHandbrakeInput(false);
	if (DoorSound)
	{
		UGameplayStatics::PlaySoundAtLocation(this, DoorSound, GetActorLocation());
	}
	EngineAudio->Play();
	TireAudio->Play();
}

bool AVBVehicle::ExitVehicle()
{
	if (!Driver)
	{
		return false;
	}
	UWorld* World = GetWorld();
	AController* PlayerController = GetController();

	// Fahrerseite ist links (Rechtsverkehr); sonst rechts, sonst oben
	const FVector Right = GetActorRightVector();
	const FVector Candidates[3] = {
		GetActorLocation() - Right * (Width * 0.5f + 70.f) + FVector(0.f, 0.f, 100.f),
		GetActorLocation() + Right * (Width * 0.5f + 70.f) + FVector(0.f, 0.f, 100.f),
		GetActorLocation() + FVector(0.f, 0.f, 260.f),
	};

	Driver->DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
	Driver->SetActorEnableCollision(true);
	bool bPlaced = false;
	for (const FVector& Candidate : Candidates)
	{
		FVector Location = Candidate;
		if (World->FindTeleportSpot(Driver, Location, GetActorRotation()))
		{
			Driver->SetActorLocationAndRotation(Location, FRotator(0.f, GetActorRotation().Yaw, 0.f), false, nullptr, ETeleportType::TeleportPhysics);
			bPlaced = true;
			break;
		}
	}
	if (!bPlaced)
	{
		Driver->SetActorLocation(Candidates[2], false, nullptr, ETeleportType::TeleportPhysics);
	}
	Driver->SetActorHiddenInGame(false);
	if (ACharacter* Character = Cast<ACharacter>(Driver))
	{
		Character->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
	}

	UChaosWheeledVehicleMovementComponent* Movement = GetWheeledMovement();
	Movement->SetThrottleInput(0.f);
	Movement->SetSteeringInput(0.f);
	Movement->SetBrakeInput(0.f);
	Movement->SetHandbrakeInput(true);
	ThrottleInput = BrakeInput = SteerInput = 0.f;

	APawn* OldDriver = Driver;
	Driver = nullptr;
	EngineAudio->FadeOut(0.6f, 0.f);
	TireAudio->Stop();
	HornAudio->Stop();
	if (DoorSound)
	{
		UGameplayStatics::PlaySoundAtLocation(this, DoorSound, GetActorLocation(), 1.f, 0.95f);
	}
	if (PlayerController)
	{
		PlayerController->Possess(OldDriver);
		PlayerController->SetControlRotation(FRotator(0.f, GetActorRotation().Yaw, 0.f));
	}
	return true;
}

// ---------------------------------------------------------------------------------------------
// Eingabe
// ---------------------------------------------------------------------------------------------
void AVBVehicle::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	AVBPlayerController* PC = Cast<AVBPlayerController>(GetController());
	UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent);
	if (!PC || !Input)
	{
		return;
	}
	UVBInputSet* Set = PC->GetInputSet();

	Input->BindAction(Set->Throttle, ETriggerEvent::Triggered, this, &AVBVehicle::Input_Throttle);
	Input->BindAction(Set->Throttle, ETriggerEvent::Completed, this, &AVBVehicle::Input_ThrottleReleased);
	Input->BindAction(Set->Brake, ETriggerEvent::Triggered, this, &AVBVehicle::Input_Brake);
	Input->BindAction(Set->Brake, ETriggerEvent::Completed, this, &AVBVehicle::Input_BrakeReleased);
	Input->BindAction(Set->Steer, ETriggerEvent::Triggered, this, &AVBVehicle::Input_Steer);
	Input->BindAction(Set->Steer, ETriggerEvent::Completed, this, &AVBVehicle::Input_SteerReleased);
	Input->BindAction(Set->Handbrake, ETriggerEvent::Started, this, &AVBVehicle::Input_HandbrakePressed);
	Input->BindAction(Set->Handbrake, ETriggerEvent::Completed, this, &AVBVehicle::Input_HandbrakeReleased);
	Input->BindAction(Set->Look, ETriggerEvent::Triggered, this, &AVBVehicle::Input_Look);
	Input->BindAction(Set->LookGamepad, ETriggerEvent::Triggered, this, &AVBVehicle::Input_LookGamepad);
	Input->BindAction(Set->ExitVehicle, ETriggerEvent::Started, this, &AVBVehicle::Input_Exit);
	Input->BindAction(Set->VehicleLights, ETriggerEvent::Started, this, &AVBVehicle::Input_Lights);
	Input->BindAction(Set->VehicleReset, ETriggerEvent::Started, this, &AVBVehicle::Input_Reset);
	Input->BindAction(Set->VehicleCamera, ETriggerEvent::Started, this, &AVBVehicle::Input_Camera);
	Input->BindAction(Set->Horn, ETriggerEvent::Started, this, &AVBVehicle::Input_HornPressed);
	Input->BindAction(Set->Horn, ETriggerEvent::Completed, this, &AVBVehicle::Input_HornReleased);
}

void AVBVehicle::Input_Throttle(const FInputActionValue& Value)
{
	ThrottleInput = FMath::Clamp(Value.Get<float>(), 0.f, 1.f);
	GetWheeledMovement()->SetThrottleInput(ThrottleInput);
}

void AVBVehicle::Input_ThrottleReleased(const FInputActionValue& Value)
{
	ThrottleInput = 0.f;
	GetWheeledMovement()->SetThrottleInput(0.f);
}

void AVBVehicle::Input_Brake(const FInputActionValue& Value)
{
	BrakeInput = FMath::Clamp(Value.Get<float>(), 0.f, 1.f);
	GetWheeledMovement()->SetBrakeInput(BrakeInput);
}

void AVBVehicle::Input_BrakeReleased(const FInputActionValue& Value)
{
	BrakeInput = 0.f;
	GetWheeledMovement()->SetBrakeInput(0.f);
}

void AVBVehicle::Input_Steer(const FInputActionValue& Value)
{
	SteerInput = FMath::Clamp(Value.Get<float>(), -1.f, 1.f);
	GetWheeledMovement()->SetSteeringInput(SteerInput);
}

void AVBVehicle::Input_SteerReleased(const FInputActionValue& Value)
{
	SteerInput = 0.f;
	GetWheeledMovement()->SetSteeringInput(0.f);
}

void AVBVehicle::Input_HandbrakePressed(const FInputActionValue& Value)
{
	GetWheeledMovement()->SetHandbrakeInput(true);
}

void AVBVehicle::Input_HandbrakeReleased(const FInputActionValue& Value)
{
	GetWheeledMovement()->SetHandbrakeInput(false);
}

void AVBVehicle::Input_Look(const FInputActionValue& Value)
{
	const FVector2D Axis = Value.Get<FVector2D>();
	LookOffset.Yaw = FMath::Clamp(LookOffset.Yaw + Axis.X, -170.f, 170.f);
	LookOffset.Pitch = FMath::Clamp(LookOffset.Pitch - Axis.Y, -35.f, 25.f);
	TimeSinceLook = 0.f;
}

void AVBVehicle::Input_LookGamepad(const FInputActionValue& Value)
{
	const FVector2D Axis = Value.Get<FVector2D>();
	const float Rate = 150.f * GetWorld()->GetDeltaSeconds();
	LookOffset.Yaw = FMath::Clamp(LookOffset.Yaw + Axis.X * Rate, -170.f, 170.f);
	LookOffset.Pitch = FMath::Clamp(LookOffset.Pitch + Axis.Y * Rate, -35.f, 25.f);
	TimeSinceLook = 0.f;
}

void AVBVehicle::Input_Exit(const FInputActionValue& Value)
{
	// Erst bei (fast) stehendem Auto aussteigen
	if (FMath::Abs(GetSpeedKmh()) < 12.f)
	{
		ExitVehicle();
	}
}

void AVBVehicle::Input_Lights(const FInputActionValue& Value)
{
	HeadlightMode = static_cast<EVBHeadlightMode>((static_cast<uint8>(HeadlightMode) + 1) % 3);
}

void AVBVehicle::Input_Reset(const FInputActionValue& Value)
{
	// Auf die Raeder stellen (nach Unfall / Ueberschlag)
	const FVector Location = GetActorLocation() + FVector(0.f, 0.f, 150.f);
	const FRotator Rotation(0.f, GetActorRotation().Yaw, 0.f);
	GetMesh()->SetPhysicsLinearVelocity(FVector::ZeroVector);
	GetMesh()->SetPhysicsAngularVelocityInDegrees(FVector::ZeroVector);
	SetActorLocationAndRotation(Location, Rotation, false, nullptr, ETeleportType::TeleportPhysics);
}

void AVBVehicle::Input_Camera(const FInputActionValue& Value)
{
	CameraPreset = (CameraPreset + 1) % 2;
	CameraBoom->TargetArmLength = CameraPreset == 0 ? Length * 0.9f + 220.f : Length * 1.4f + 420.f;
}

void AVBVehicle::Input_HornPressed(const FInputActionValue& Value)
{
	HornAudio->Play();
}

void AVBVehicle::Input_HornReleased(const FInputActionValue& Value)
{
	HornAudio->Stop();
}

// ---------------------------------------------------------------------------------------------
// Tick: Raeder, Lichter, Grip, Kamera
// ---------------------------------------------------------------------------------------------
float AVBVehicle::GetSpeedKmh() const
{
	return GetWheeledMovement()->GetForwardSpeed() * 0.036f;
}

int32 AVBVehicle::GetCurrentGear() const
{
	return GetWheeledMovement()->GetCurrentGear();
}

float AVBVehicle::GetEngineRPM() const
{
	return GetWheeledMovement()->GetEngineRotationSpeed();
}

void AVBVehicle::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UpdateWheelVisuals();
	UpdateLights(DeltaSeconds);
	UpdateCamera(DeltaSeconds);
	UpdateAudio(DeltaSeconds);

	GripTimer -= DeltaSeconds;
	if (GripTimer <= 0.f)
	{
		GripTimer = 0.25f;
		UpdateGrip();
	}
}

void AVBVehicle::UpdateWheelVisuals()
{
	const UChaosWheeledVehicleMovementComponent* Movement = GetWheeledMovement();
	for (int32 Index = 0; Index < WheelMeshes.Num() && Index < Movement->Wheels.Num(); ++Index)
	{
		const UChaosVehicleWheel* Wheel = Movement->Wheels[Index];
		if (!Wheel)
		{
			continue;
		}
		// Wie UVehicleAnimationInstance: Pitch = Drehung, Yaw = Lenkung, Z = Federweg
		const FQuat Steer = FRotator(0.f, Wheel->GetSteerAngle(), 0.f).Quaternion();
		const FQuat Spin = FRotator(Wheel->GetRotationAngle(), 0.f, 0.f).Quaternion();
		const FQuat Side = FRotator(0.f, Index % 2 == 0 ? 180.f : 0.f, 0.f).Quaternion();
		const FVector Location = WheelBaseLocation(Index) + FVector(0.f, 0.f, Wheel->GetSuspensionOffset());
		WheelMeshes[Index]->SetRelativeLocationAndRotation(Location, Steer * Spin * Side);
	}
}

void AVBVehicle::UpdateLights(float DeltaSeconds)
{
	bool bWantLights = false;
	if (HeadlightMode == EVBHeadlightMode::On)
	{
		bWantLights = true;
	}
	else if (HeadlightMode == EVBHeadlightMode::Auto && Driver)
	{
		const UVBTimeOfDaySubsystem* Time = GetWorld()->GetSubsystem<UVBTimeOfDaySubsystem>();
		const UVBWeatherSubsystem* Weather = GetWorld()->GetSubsystem<UVBWeatherSubsystem>();
		const EVBWeatherType Type = Weather ? Weather->GetWeather() : EVBWeatherType::Clear;
		bWantLights = (Time && Time->GetNightFactor() > 0.3f)
			|| Type == EVBWeatherType::HeavyRain || Type == EVBWeatherType::Fog || Type == EVBWeatherType::Storm;
	}

	if (bWantLights != bHeadlightsOn)
	{
		bHeadlightsOn = bWantLights;
		for (USpotLightComponent* Light : { HeadlightLeft.Get(), HeadlightRight.Get() })
		{
			Light->SetVisibility(bHeadlightsOn);
			Light->SetIntensity(bHeadlightsOn ? HeadlightCandela : 0.f);
		}
	}

	const float Speed = GetSpeedKmh();
	const bool bBraking = Driver && BrakeInput > 0.05f && Speed > 1.f;
	SetCPD(VBVehicleCPD::Headlight, bHeadlightsOn ? 1.f : 0.f);
	SetCPD(VBVehicleCPD::Brake, bBraking ? 1.f : (bHeadlightsOn ? 0.3f : 0.f));

	// Blinker: beim langsamen Abbiegen automatisch, 1.5 Hz
	int32 WantedSide = 0;
	if (Driver && FMath::Abs(SteerInput) > 0.45f && FMath::Abs(Speed) < 35.f)
	{
		WantedSide = SteerInput < 0.f ? -1 : 1;
	}
	if (WantedSide != IndicatorSide)
	{
		IndicatorSide = WantedSide;
		IndicatorTime = 0.f;
	}
	IndicatorTime += DeltaSeconds;
	const float Blink = (IndicatorSide != 0 && FMath::Fmod(IndicatorTime, 0.667f) < 0.36f) ? 1.f : 0.f;
	SetCPD(VBVehicleCPD::IndicatorLeft, IndicatorSide < 0 ? Blink : 0.f);
	SetCPD(VBVehicleCPD::IndicatorRight, IndicatorSide > 0 ? Blink : 0.f);
}

void AVBVehicle::UpdateGrip()
{
	const UVBWeatherSubsystem* Weather = GetWorld()->GetSubsystem<UVBWeatherSubsystem>();
	const float Grip = Weather ? Weather->GetRoadGripMultiplier() : 1.f;
	UChaosWheeledVehicleMovementComponent* Movement = GetWheeledMovement();
	for (int32 Index = 0; Index < BaseFriction.Num() && Index < Movement->Wheels.Num(); ++Index)
	{
		Movement->SetWheelFrictionMultiplier(Index, BaseFriction[Index] * Grip);
	}
}

void AVBVehicle::UpdateCamera(float DeltaSeconds)
{
	if (!Driver)
	{
		return;
	}
	TimeSinceLook += DeltaSeconds;
	if (TimeSinceLook > CameraRecenterDelay)
	{
		LookOffset = FMath::RInterpTo(LookOffset, FRotator::ZeroRotator, DeltaSeconds, 2.5f);
	}
	// Beim Rueckwaertsfahren nach hinten schauen
	const float Speed = GetSpeedKmh();
	const float ReverseYaw = (Speed < -8.f && TimeSinceLook > CameraRecenterDelay) ? 180.f : 0.f;
	CameraBoom->SetRelativeRotation(FRotator(-10.f + LookOffset.Pitch, LookOffset.Yaw + ReverseYaw, 0.f));

	const float SpeedAlpha = FMath::Clamp(FMath::Abs(Speed) / 160.f, 0.f, 1.f);
	Camera->SetFieldOfView(FMath::FInterpTo(Camera->FieldOfView, FMath::Lerp(CameraFOV, CameraFOVAtSpeed, SpeedAlpha), DeltaSeconds, 3.f));
}

#undef LOCTEXT_NAMESPACE

void AVBVehicle::UpdateAudio(float DeltaSeconds)
{
	if (!Driver)
	{
		if (IndicatorAudio->IsPlaying())
		{
			IndicatorAudio->Stop();
		}
		return;
	}
	// Motor: Schleife bei 2000 U/min aufgenommen -> Tonhoehe = Drehzahl / 2000
	const float Rpm = FMath::Max(GetEngineRPM(), 800.f);
	EngineAudio->SetPitchMultiplier(FMath::Clamp(Rpm / 2000.f, 0.4f, 3.8f));
	EngineAudio->SetVolumeMultiplier(0.35f + 0.65f * ThrottleInput);

	const float Speed = FMath::Abs(GetSpeedKmh());
	TireAudio->SetVolumeMultiplier(FMath::Clamp(Speed / 100.f, 0.f, 1.f) * 0.8f + 0.001f);
	TireAudio->SetPitchMultiplier(0.8f + FMath::Clamp(Speed / 150.f, 0.f, 1.f) * 0.6f);

	const bool bBlinking = IndicatorSide != 0;
	if (bBlinking && !IndicatorAudio->IsPlaying())
	{
		IndicatorAudio->Play();
	}
	else if (!bBlinking && IndicatorAudio->IsPlaying())
	{
		IndicatorAudio->Stop();
	}
}
