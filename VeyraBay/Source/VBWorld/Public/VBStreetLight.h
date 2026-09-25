#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VBStreetLight.generated.h"

class USpotLightComponent;
class UStaticMesh;
class UStaticMeshComponent;
class UVBNightLightComponent;

/**
 * Strassenlaterne mit physikalisch plausibler Lichtstaerke (Candela), Daemmerungsschalter
 * und volumetrischer Streuung (Lichtkegel bei Regen/Nebel).
 *
 * Ist "Model" gesetzt (z. B. SM_VB_StreetLight_A aus der Blender-Pipeline), wird dieses
 * Nanite-Mesh angezeigt und die Prototyp-Grundformen werden ausgeblendet.
 */
UCLASS(ClassGroup = (VeyraBay), meta = (DisplayName = "VB Street Light"))
class VBWORLD_API AVBStreetLight : public AActor
{
	GENERATED_BODY()

public:
	AVBStreetLight();

	virtual void OnConstruction(const FTransform& Transform) override;

	/** Finales Modell. Leer = Prototyp-Geometrie aus Engine-Grundformen. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Street Light")
	TObjectPtr<UStaticMesh> Model;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> Body;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> Pole;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> Arm;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> Head;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USpotLightComponent> Lamp;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UVBNightLightComponent> NightSwitch;
};
