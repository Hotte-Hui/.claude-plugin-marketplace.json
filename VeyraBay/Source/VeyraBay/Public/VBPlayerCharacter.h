#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "VBPlayerCharacter.generated.h"

class UCameraComponent;
class USpringArmComponent;
class UVBInteractionComponent;
struct FInputActionValue;

/**
 * Spielfigur: Third-Person-Kamera ueber der Schulter, Gehen / Laufen / Sprinten,
 * Interaktion. Mesh + AnimBlueprint kommen aus UVBGameSettings (Setup-Skript traegt sie ein).
 *
 * Phase 5 ersetzt die Animation durch Motion Matching (Game Animation Sample) - die
 * Bewegungswerte hier sind bereits auf realistische Geschwindigkeiten abgestimmt.
 */
UCLASS()
class VEYRABAY_API AVBPlayerCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	AVBPlayerCharacter();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera")
	TObjectPtr<USpringArmComponent> CameraBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera")
	TObjectPtr<UCameraComponent> FollowCamera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Interaction")
	TObjectPtr<UVBInteractionComponent> Interaction;

	// --- Bewegung (cm/s, realistische Werte) ---------------------------------
	/** Gehen ~1.7 m/s */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Movement")
	float WalkSpeed = 170.f;

	/** Joggen ~4 m/s (Standard) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Movement")
	float RunSpeed = 400.f;

	/** Sprinten ~6.5 m/s */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Movement")
	float SprintSpeed = 650.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Movement")
	float SpeedInterpRate = 5.f;

	// --- Kamera --------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera")
	float DefaultFOV = 75.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera")
	float SprintFOV = 81.f;

	UFUNCTION(BlueprintPure, Category = "Movement")
	bool IsSprinting() const;

	UFUNCTION(BlueprintPure, Category = "Movement")
	bool IsWalkMode() const { return bWalkMode; }

	/** false, wenn kein Charakter-Mesh gefunden wurde (HUD zeigt dann einen Hinweis). */
	UFUNCTION(BlueprintPure, Category = "Player")
	bool HasCharacterMesh() const { return bHasCharacterMesh; }

private:
	void Input_Move(const FInputActionValue& Value);
	void Input_Look(const FInputActionValue& Value);
	void Input_LookGamepad(const FInputActionValue& Value);
	void Input_SprintStarted(const FInputActionValue& Value);
	void Input_SprintCompleted(const FInputActionValue& Value);
	void Input_WalkToggle(const FInputActionValue& Value);
	void Input_Interact(const FInputActionValue& Value);

	void ApplyCharacterAssets();
	float GetTargetSpeed() const;

	bool bSprintHeld = false;
	bool bWalkMode = false;
	bool bHasCharacterMesh = false;
};
