#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VBInteractable.h"
#include "VBDoor.generated.h"

class UStaticMeshComponent;

/**
 * Drehtuer mit Scharnier. Oeffnet sich immer vom Spieler weg, mit weicher Bewegung.
 * [PROTOTYP-GEOMETRIE] Tuerblatt ist eine Engine-Grundform; Phase 3 tauscht das Mesh
 * gegen die Blender-Tueren der Fassaden-Kits (Pivot = Scharnierkante).
 */
UCLASS(ClassGroup = (VeyraBay), meta = (DisplayName = "VB Door"))
class VEYRABAY_API AVBDoor : public AActor, public IVBInteractable
{
	GENERATED_BODY()

public:
	AVBDoor();

	virtual void Tick(float DeltaSeconds) override;

	virtual FText GetInteractionPrompt_Implementation(AActor* Interactor) const override;
	virtual void Interact_Implementation(AActor* Interactor) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USceneComponent> Root;

	/** Drehpunkt an der Scharnierkante. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USceneComponent> Hinge;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> Panel;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door", meta = (ClampMin = "10.0", ClampMax = "180.0"))
	float OpenAngle = 95.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door", meta = (ClampMin = "0.5"))
	float SwingSpeed = 4.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door")
	bool bLocked = false;

	UFUNCTION(BlueprintPure, Category = "Door")
	bool IsOpen() const { return bOpen; }

private:
	bool bOpen = false;
	float CurrentAngle = 0.f;
	float TargetAngle = 0.f;
};
