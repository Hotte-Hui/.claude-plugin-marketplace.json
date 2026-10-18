#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VBTrafficLight.generated.h"

class AVBTrafficLight;
class UMaterialInstanceDynamic;
class UPointLightComponent;
class UStaticMesh;
class UStaticMeshComponent;

/** Signalzustaende (deutsche Folge inkl. Rot-Gelb). */
UENUM(BlueprintType)
enum class EVBSignalState : uint8
{
	Red,
	RedAmber,
	Green,
	Amber
};

/**
 * Phasenplan einer Ampel. Der Zustand haengt nur von der Weltzeit ab - dadurch zeigen Ampel-Actor,
 * Verkehr und Fussgaenger immer dasselbe, auch wenn der Actor (World Partition) gerade nicht geladen ist.
 */
USTRUCT(BlueprintType)
struct VBWORLD_API FVBSignalTiming
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Timing") float Green = 14.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Timing") float Amber = 3.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Timing") float Red = 18.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Timing") float RedAmber = 1.5f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Timing") float Offset = 0.f;

	float CycleLength() const { return FMath::Max(Green + Amber + Red + RedAmber, 1.f); }

	/** Zustand zur Weltzeit; optional Sekunden bis zum naechsten Wechsel. */
	EVBSignalState StateAt(double WorldSeconds, float* OutTimeUntilChange = nullptr) const;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FVBOnSignalChanged, AVBTrafficLight*, Light, EVBSignalState, NewState);

/**
 * Verkehrsampel mit echtem Phasenzyklus. Linsen leuchten ueber Custom Primitive Data (keine
 * Lichtberechnung pro Linse), ein schwaches Punktlicht faerbt nachts die Umgebung.
 * Der Verkehr (Phase 5) liest GetState() / OnSignalChanged; Ampeln einer Kreuzung werden
 * ueber CycleOffset gegeneinander versetzt.
 */
UCLASS(ClassGroup = (VeyraBay), meta = (DisplayName = "VB Traffic Light"))
class VBWORLD_API AVBTrafficLight : public AActor
{
	GENERATED_BODY()

public:
	AVBTrafficLight();

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintPure, Category = "Traffic Light")
	EVBSignalState GetState() const { return State; }

	/** Sekunden bis zum naechsten Zustandswechsel. */
	UFUNCTION(BlueprintPure, Category = "Traffic Light")
	float GetTimeUntilChange() const;

	/** Darf ein Fahrzeug, das jetzt die Haltelinie erreicht, noch fahren? */
	UFUNCTION(BlueprintPure, Category = "Traffic Light")
	bool AllowsPassage() const { return State == EVBSignalState::Green; }

	UPROPERTY(BlueprintAssignable, Category = "Traffic Light")
	FVBOnSignalChanged OnSignalChanged;

	/** Phasenplan dieser Ampel (fuer Verkehr/Fussgaenger, die den Zustand ohne geladenen Actor berechnen). */
	FVBSignalTiming GetTiming() const;

	// --- Modelle ----------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Traffic Light")
	TObjectPtr<UStaticMesh> Model;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Traffic Light")
	TObjectPtr<UStaticMesh> LensModel;

	// --- Phasen (Sekunden) ----------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Timing", meta = (ClampMin = "1.0"))
	float GreenSeconds = 14.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Timing", meta = (ClampMin = "1.0"))
	float AmberSeconds = 3.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Timing", meta = (ClampMin = "1.0"))
	float RedSeconds = 18.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Timing", meta = (ClampMin = "0.0"))
	float RedAmberSeconds = 1.5f;

	/** Versatz im Zyklus (Sekunden) - fuer gegenlaeufige Ampeln einer Kreuzung. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Timing")
	float CycleOffset = 0.f;

	/** Zustand im Editor (Vorschau). */
	UPROPERTY(EditAnywhere, Category = "Timing")
	EVBSignalState PreviewState = EVBSignalState::Green;

	// --- Komponenten -----------------------------------------------------------------------
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> Body;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> LensRed;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> LensAmber;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> LensGreen;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UPointLightComponent> SignalLight;

private:
	float GetCycleLength() const;
	EVBSignalState StateAtCycleTime(float CycleTime) const;
	void ApplyState(EVBSignalState NewState, bool bBroadcast);
	void SetupLensMaterial(UStaticMeshComponent* Lens, const FLinearColor& Color);

	EVBSignalState State = EVBSignalState::Red;
	float CycleTime = 0.f;
	bool bHasState = false;
};
