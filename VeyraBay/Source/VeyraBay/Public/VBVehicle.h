#pragma once

#include "CoreMinimal.h"
#include "ChaosVehicleWheel.h"
#include "WheeledVehiclePawn.h"
#include "VBInteractable.h"
#include "VBVehicle.generated.h"

class UCameraComponent;
class USpotLightComponent;
class USpringArmComponent;
class UStaticMesh;
class UStaticMeshComponent;
class UChaosWheeledVehicleMovementComponent;
struct FInputActionValue;

/** Vorderrad: gelenkt, gebremst, ohne Handbremse. */
UCLASS()
class VEYRABAY_API UVBWheelFront : public UChaosVehicleWheel
{
	GENERATED_BODY()

public:
	UVBWheelFront();
};

/** Hinterrad: Handbremse, nicht gelenkt. */
UCLASS()
class VEYRABAY_API UVBWheelRear : public UChaosVehicleWheel
{
	GENERATED_BODY()

public:
	UVBWheelRear();
};

UENUM(BlueprintType)
enum class EVBHeadlightMode : uint8
{
	Auto,
	On,
	Off
};

/**
 * Fahrbares Auto (Chaos Vehicle). Karosserie = SK_VB_Car_<Typ> (Radknochen wheel_fl/fr/rl/rr),
 * Raeder = SM_VB_Wheel_<Typ> als eigene Komponenten, die dem Radzustand der Simulation folgen.
 *
 * Lichter und Lack laufen ueber Custom Primitive Data der Karosserie (siehe Docs/CONVENTIONS.md):
 * 2 Rueck-/Bremslicht, 3 Scheinwerfer, 4/5 Blinker links/rechts, 6..8 Lackfarbe.
 * Nasse Strasse: Reibung der Raeder folgt UVBWeatherSubsystem::GetRoadGripMultiplier().
 */
UCLASS(ClassGroup = (VeyraBay), meta = (DisplayName = "VB Vehicle"))
class VEYRABAY_API AVBVehicle : public AWheeledVehiclePawn, public IVBInteractable
{
	GENERATED_BODY()

public:
	AVBVehicle(const FObjectInitializer& ObjectInitializer);

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

	// IVBInteractable: Einsteigen
	virtual FText GetInteractionPrompt_Implementation(AActor* Interactor) const override;
	virtual bool CanInteract_Implementation(AActor* Interactor) const override;
	virtual void Interact_Implementation(AActor* Interactor) override;

	/** Setzt den Fahrer (zu Fuss) ab und gibt ihm die Steuerung zurueck. */
	UFUNCTION(BlueprintCallable, Category = "Vehicle")
	bool ExitVehicle();

	UFUNCTION(BlueprintPure, Category = "Vehicle")
	float GetSpeedKmh() const;

	UFUNCTION(BlueprintPure, Category = "Vehicle")
	int32 GetCurrentGear() const;

	UFUNCTION(BlueprintPure, Category = "Vehicle")
	float GetEngineRPM() const;

	UFUNCTION(BlueprintPure, Category = "Vehicle")
	bool AreHeadlightsOn() const { return bHeadlightsOn; }

	UFUNCTION(BlueprintPure, Category = "Vehicle")
	EVBHeadlightMode GetHeadlightMode() const { return HeadlightMode; }

	UChaosWheeledVehicleMovementComponent* GetWheeledMovement() const;

	// --- Komponenten -------------------------------------------------------------
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USpringArmComponent> CameraBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UCameraComponent> Camera;

	/** Reihenfolge wie WheelSetups: vorne links, vorne rechts, hinten links, hinten rechts. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TArray<TObjectPtr<UStaticMeshComponent>> WheelMeshes;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USpotLightComponent> HeadlightLeft;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USpotLightComponent> HeadlightRight;

	// --- Fahrzeugdaten (vom Setup-Skript aus vehicles.json gesetzt) --------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Spec")
	FName VehicleType = TEXT("Sedan");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Spec")
	TObjectPtr<UStaticMesh> WheelMesh;

	/** Laenge/Breite/Radstand/Radradius/Radbreite in cm. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Spec")
	float Length = 485.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Spec")
	float Width = 186.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Spec")
	float Wheelbase = 285.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Spec")
	float WheelRadius = 33.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Spec")
	float WheelWidth = 23.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Spec", meta = (ClampMin = "300.0"))
	float MassKg = 1550.f;

	/** Motor: maximales Drehmoment [Nm] und Drehzahl. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Spec")
	float MaxTorque = 350.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Spec")
	float MaxRPM = 6500.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Spec")
	bool bAllWheelDrive = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Spec")
	FLinearColor PaintColor = FLinearColor(0.12f, 0.14f, 0.16f);

	// --- Verhalten --------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Lights")
	EVBHeadlightMode HeadlightMode = EVBHeadlightMode::Auto;

	/** Lichtstaerke eines Abblendlichts [cd]. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Lights")
	float HeadlightCandela = 18000.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Camera")
	float CameraFOV = 72.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Camera")
	float CameraFOVAtSpeed = 84.f;

	/** Sekunden ohne Kamera-Eingabe, bis die Kamera wieder hinter das Auto schwenkt. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle|Camera")
	float CameraRecenterDelay = 1.5f;

protected:
	void ApplySpec();
	void UpdateWheelVisuals();
	void UpdateLights(float DeltaSeconds);
	void UpdateGrip();
	void UpdateCamera(float DeltaSeconds);
	void SetCPD(int32 Index, float Value);

private:
	void Input_Throttle(const FInputActionValue& Value);
	void Input_ThrottleReleased(const FInputActionValue& Value);
	void Input_Brake(const FInputActionValue& Value);
	void Input_BrakeReleased(const FInputActionValue& Value);
	void Input_Steer(const FInputActionValue& Value);
	void Input_SteerReleased(const FInputActionValue& Value);
	void Input_HandbrakePressed(const FInputActionValue& Value);
	void Input_HandbrakeReleased(const FInputActionValue& Value);
	void Input_Look(const FInputActionValue& Value);
	void Input_LookGamepad(const FInputActionValue& Value);
	void Input_Exit(const FInputActionValue& Value);
	void Input_Lights(const FInputActionValue& Value);
	void Input_Reset(const FInputActionValue& Value);
	void Input_Camera(const FInputActionValue& Value);

	FVector WheelBaseLocation(int32 Index) const;

	UPROPERTY(Transient)
	TObjectPtr<APawn> Driver;

	TArray<float> BaseFriction;
	float GripTimer = 0.f;
	float BrakeInput = 0.f;
	float ThrottleInput = 0.f;
	float SteerInput = 0.f;
	bool bHeadlightsOn = false;
	float IndicatorTime = 0.f;
	int32 IndicatorSide = 0;     // -1 links, 1 rechts, 0 aus (Blinker setzt sich beim Abbiegen selbst)
	FRotator LookOffset = FRotator::ZeroRotator;
	float TimeSinceLook = 100.f;
	int32 CameraPreset = 0;
};
