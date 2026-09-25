#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VBTrafficVehicle.generated.h"

class UStaticMesh;
class UStaticMeshComponent;

/** Ein Fahrzeugtyp fuer KI-Verkehr und geparkte Autos (Werte aus SourceAssets/Export/Vehicles/vehicles.json). */
USTRUCT(BlueprintType)
struct VBWORLD_API FVBTrafficVehicleType
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle")
	FName Name;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle")
	TObjectPtr<UStaticMesh> BodyMesh;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle")
	TObjectPtr<UStaticMesh> WheelMesh;

	/** Masse in cm. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle")
	float Length = 485.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle")
	float Width = 186.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle")
	float Wheelbase = 285.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle")
	float WheelRadius = 33.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle")
	float WheelWidth = 23.f;

	/** Relative Haeufigkeit im Verkehr (0 = nur geparkt / gar nicht). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle", meta = (ClampMin = "0.0"))
	float Weight = 1.f;

	/** Relative Haeufigkeit als geparktes Auto. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle", meta = (ClampMin = "0.0"))
	float ParkedWeight = 1.f;

	/** Feste Lackfarbe (Taxi, Bus) statt zufaelliger Farbe aus der Palette. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle")
	bool bFixedPaint = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle")
	FLinearColor Paint = FLinearColor(0.12f, 0.14f, 0.16f);

	/** Anfahr-/Bremsverhalten: schwere Fahrzeuge < 1. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Vehicle")
	float Agility = 1.f;
};

/**
 * Leichtgewichtiges Fahrzeug fuer KI-Verkehr und parkende Autos: Karosserie + 4 Raeder als Static Meshes,
 * kinematisch bewegt vom AVBTrafficManager (keine Physiksimulation -> hunderte Autos moeglich).
 * Lichter/Lack ueber Custom Primitive Data wie beim fahrbaren Auto.
 */
UCLASS(NotPlaceable, ClassGroup = (VeyraBay))
class VBWORLD_API AVBTrafficVehicle : public AActor
{
	GENERATED_BODY()

public:
	AVBTrafficVehicle();

	void Configure(const FVBTrafficVehicleType& InType, const FLinearColor& InPaint);

	/**
	 * Raeder drehen/lenken und Lichter setzen.
	 * Indicator: -1 links, 1 rechts, 0 aus. Lights: 0..1 (Scheinwerfer).
	 */
	void UpdateVisuals(float DeltaSeconds, float SpeedCm, float SteerDegrees, bool bBraking, bool bLights, int32 Indicator);

	const FVBTrafficVehicleType& GetType() const { return Type; }

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> Body;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TArray<TObjectPtr<UStaticMeshComponent>> Wheels;

private:
	void SetCPD(int32 Index, float Value);
	FVector WheelBase(int32 Index) const;

	FVBTrafficVehicleType Type;
	float WheelAngle = 0.f;
	float BlinkTime = 0.f;
};
