#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "VBEventSubsystem.generated.h"

class AActor;
class UAudioComponent;
class AVBTrafficVehicle;

/**
 * Dynamische Stadt-Ereignisse (Phase 9), zufaellig alle paar Minuten in der Naehe des Spielers:
 *   - Panne: liegengebliebenes Auto mit Warnblinker blockiert eine Spur, der Verkehr staut sich dahinter
 *   - Strassenmusik: Musiker mit Zuhoerern auf dem Gehweg (eigene Gitarrenmusik, raeumlich)
 *   - Hafenfest-Feuerwerk: nachts ueber dem Meer, wenn der Spieler in Kuestennaehe ist
 * Konsole: vb.Event panne|musik|feuerwerk
 */
UCLASS()
class VEYRABAY_API UVBEventSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

	bool StartBreakdown();
	bool StartMusician();
	bool StartFireworks();

	/** Letzte Meldung fuer das HUD ("In der Naehe: ..."). */
	FString ConsumeNotice();

private:
	struct FActiveEvent
	{
		FString Name;
		float TimeLeft = 0.f;
		FVector Location = FVector::ZeroVector;
		TArray<TWeakObjectPtr<AActor>> Actors;
		TWeakObjectPtr<UAudioComponent> Audio;
		TWeakObjectPtr<AVBTrafficVehicle> Car;
		float Blink = 0.f;
	};

	FVector PlayerLocation() const;
	void EndEvent(FActiveEvent& Event);

	TArray<FActiveEvent> Active;
	float NextEvent = 75.f;
	FString Notice;
};
