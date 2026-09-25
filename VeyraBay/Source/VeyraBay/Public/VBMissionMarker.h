#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VBMissionMarker.generated.h"

class UMaterialInstanceDynamic;
class UPointLightComponent;
class UStaticMeshComponent;

/** Leuchtende Lichtsaeule fuer Missionsziele (Material M_VB_MissionMarker, sonst Engine-Grundform). */
UCLASS(NotPlaceable, ClassGroup = (VeyraBay))
class VEYRABAY_API AVBMissionMarker : public AActor
{
	GENERATED_BODY()

public:
	AVBMissionMarker();

	virtual void BeginPlay() override;

	void SetRadius(float RadiusCm);
	void SetColor(const FLinearColor& Color);

	UPROPERTY(VisibleAnywhere, Category = "Components")
	TObjectPtr<UStaticMeshComponent> Beam;

	UPROPERTY(VisibleAnywhere, Category = "Components")
	TObjectPtr<UPointLightComponent> Glow;

private:
	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> Material;
};
