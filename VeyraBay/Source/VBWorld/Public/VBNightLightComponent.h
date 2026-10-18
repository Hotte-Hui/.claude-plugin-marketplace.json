#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "VBNightLightComponent.generated.h"

/**
 * Schaltet alle Lichtquellen des Besitzers abhaengig von Tageszeit und Wetter
 * (wie ein Daemmerungsschalter). Jede Instanz hat eine leicht andere Schwelle,
 * damit Strassenlaternen nicht alle im selben Frame angehen.
 *
 * Zusaetzlich wird Custom Primitive Data [0] aller Meshes auf 1/0 gesetzt, damit
 * Emissive-Materialien (Lampenschirm, Fenster, Neon) ohne dynamische Materialinstanzen mitschalten.
 */
UCLASS(ClassGroup = (VeyraBay), meta = (BlueprintSpawnableComponent, DisplayName = "VB Night Light Switch"))
class VBWORLD_API UVBNightLightComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UVBNightLightComponent();

	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	/** Einschalten ab diesem Dunkelheitsgrad (0 = Tag, 1 = Nacht). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Night Light", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float SwitchOnThreshold = 0.35f;

	/** Zufaellige Streuung der Schwelle pro Instanz. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Night Light", meta = (ClampMin = "0.0", ClampMax = "0.5"))
	float ThresholdJitter = 0.08f;

	/** Bei Starkregen, Sturm oder dichtem Nebel auch tagsueber einschalten. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Night Light")
	bool bReactToWeather = true;

	UFUNCTION(BlueprintCallable, Category = "Night Light")
	void SetLightsOn(bool bOn);

	UFUNCTION(BlueprintPure, Category = "Night Light")
	bool AreLightsOn() const { return bLightsOn; }

private:
	float ComputeDarkness() const;

	float EffectiveThreshold = 0.35f;
	bool bLightsOn = true;
	bool bHasApplied = false;
};
