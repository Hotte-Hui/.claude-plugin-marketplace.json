#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VBFireworks.generated.h"

class UInstancedStaticMeshComponent;
class UPointLightComponent;
class USoundBase;

/**
 * Hafenfest-Feuerwerk (Ereignis bei Nacht): Raketen steigen ueber dem Meer auf und zerplatzen in leuchtende Funken
 * (Instanzen mit eigener Farbe/Helligkeit, Material M_VB_Spark), ein Lichtblitz faerbt Wasser und Fassaden,
 * der Knall kommt mit Schallverzoegerung beim Zuhoerer an.
 */
UCLASS(NotPlaceable, ClassGroup = (VeyraBay))
class VEYRABAY_API AVBFireworks : public AActor
{
	GENERATED_BODY()

public:
	AVBFireworks();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Anzahl der Raketen und Dauer der Show. */
	int32 Rockets = 28;
	float ShowSeconds = 70.f;

	UPROPERTY(VisibleAnywhere, Category = "Components")
	TObjectPtr<UInstancedStaticMeshComponent> Sparks;

	UPROPERTY(VisibleAnywhere, Category = "Components")
	TObjectPtr<UPointLightComponent> Flash;

private:
	struct FSpark
	{
		FVector Position;
		FVector Velocity;
		FLinearColor Color;
		float Age = 0.f;
		float Life = 2.5f;
	};

	void Burst(const FVector& Center);

	TArray<FSpark> Live;
	TArray<float> LaunchTimes;
	TArray<TPair<float, float>> PendingBangs;     // (Restzeit, Lautstaerke)
	float Elapsed = 0.f;
	float FlashLevel = 0.f;
	int32 NextRocket = 0;

	UPROPERTY(Transient)
	TObjectPtr<USoundBase> BangSound;
};
