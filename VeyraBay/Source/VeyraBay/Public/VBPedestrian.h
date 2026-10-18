#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "VBPedestrian.generated.h"

/**
 * Passant: normaler Character (gleiches Mannequin + AnimBlueprint wie die Spielfigur, dadurch sofort
 * animiert), aber ohne Controller - der AVBCrowdManager gibt Ziel und Tempo vor.
 * Animation wird nur berechnet, wenn der Passant sichtbar ist (VisibilityBasedAnimTickOption).
 */
UCLASS(NotPlaceable, ClassGroup = (VeyraBay))
class VEYRABAY_API AVBPedestrian : public ACharacter
{
	GENERATED_BODY()

public:
	AVBPedestrian();

	/** Richtung zum Ziel laufen (Tempo = Anteil von MaxWalkSpeed). */
	void MoveTowards(const FVector& Target, float SpeedScale);

	/** Stehen bleiben und in eine Richtung schauen. */
	void StandFacing(const FVector& Direction);

	void SetWalkSpeed(float Speed);

	/** Schrittgeraeusche (nur fuer Passanten nahe am Spieler aufrufen). */
	void UpdateFootsteps(float DeltaSeconds);

private:
	float StrideDistance = 0.f;
};
