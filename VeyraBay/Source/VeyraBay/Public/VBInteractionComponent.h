#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "VBInteractionComponent.generated.h"

/**
 * Sucht vor dem Spieler (Kamera-Blickrichtung) nach IVBInteractable-Objekten
 * und fuehrt die Interaktion aus. Prueft nur 10x pro Sekunde (guenstig).
 */
UCLASS(ClassGroup = (VeyraBay), meta = (BlueprintSpawnableComponent))
class VEYRABAY_API UVBInteractionComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UVBInteractionComponent();

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	/** Maximale Entfernung vom Charakter zum Interaktionspunkt (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Interaction")
	float InteractionRange = 220.f;

	UFUNCTION(BlueprintCallable, Category = "Interaction")
	bool TryInteract();

	UFUNCTION(BlueprintPure, Category = "Interaction")
	AActor* GetFocusedActor() const { return FocusedActor.Get(); }

	UFUNCTION(BlueprintPure, Category = "Interaction")
	FText GetFocusedPrompt() const { return FocusedPrompt; }

private:
	void UpdateFocus();

	TWeakObjectPtr<AActor> FocusedActor;
	FText FocusedPrompt;
};
