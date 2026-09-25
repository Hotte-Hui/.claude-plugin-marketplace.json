#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VBInstancedArray.generated.h"

class UInstancedStaticMeshComponent;
class UStaticMesh;

/**
 * Viele Kopien eines Meshes als ein Instanced Static Mesh (Kaimauern, Promenadenplatten, Baumreihen, Poller ...).
 * Die Transformationen werden vom Setup-Skript geschrieben und koennen im Editor bearbeitet werden.
 */
UCLASS(ClassGroup = (VeyraBay), meta = (DisplayName = "VB Instanced Array"))
class VBWORLD_API AVBInstancedArray : public AActor
{
	GENERATED_BODY()

public:
	AVBInstancedArray();

	virtual void OnConstruction(const FTransform& Transform) override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Instances")
	TObjectPtr<UStaticMesh> Mesh;

	/** Transformationen relativ zum Actor. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Instances")
	TArray<FTransform> Transforms;

	/** Schatten werfen (bei sehr vielen kleinen Objekten ggf. aus). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Instances")
	bool bCastShadow = true;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UInstancedStaticMeshComponent> Instances;
};
