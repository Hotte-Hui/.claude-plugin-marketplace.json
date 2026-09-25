#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "VBInteractable.generated.h"

UINTERFACE(MinimalAPI, Blueprintable)
class UVBInteractable : public UInterface
{
	GENERATED_BODY()
};

/**
 * Alles, womit der Spieler interagieren kann: Tueren, Lichtschalter, Aufzuege, Geldautomaten,
 * Parkuhren, Sitzplaetze, Fahrzeuge, NPCs ... In C++ oder Blueprint implementierbar.
 */
class VEYRABAY_API IVBInteractable
{
	GENERATED_BODY()

public:
	/** Text fuer die Interaktionsanzeige, z. B. "Tuer oeffnen". */
	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Interaction")
	FText GetInteractionPrompt(AActor* Interactor) const;
	virtual FText GetInteractionPrompt_Implementation(AActor* Interactor) const { return FText::GetEmpty(); }

	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Interaction")
	bool CanInteract(AActor* Interactor) const;
	virtual bool CanInteract_Implementation(AActor* Interactor) const { return true; }

	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Interaction")
	void Interact(AActor* Interactor);
	virtual void Interact_Implementation(AActor* Interactor) {}
};
