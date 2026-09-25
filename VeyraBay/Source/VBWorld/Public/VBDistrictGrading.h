#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VBDistrictGrading.generated.h"

class UPostProcessComponent;

/** Farbstimmung eines Bezirks (Rechteck in cm). */
USTRUCT(BlueprintType)
struct VBWORLD_API FVBDistrictGrade
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Grading")
	FName Name;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Grading")
	FVector2D Min = FVector2D::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Grading")
	FVector2D Max = FVector2D::ZeroVector;

	/** Farbverstaerkung (1 = neutral). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Grading")
	FLinearColor Gain = FLinearColor::White;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Grading")
	float Saturation = 1.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Grading")
	float Contrast = 1.f;
};

/**
 * Bezirks-Farbstimmung (Phase 9): ein unbegrenztes Post-Process, dessen Farbwerte je nach Spielerposition weich
 * zwischen den Bezirken ueberblendet werden (BlendDistance an den Grenzen). Wird vom Stadt-Setup (vb_city.py) gefuellt.
 */
UCLASS(ClassGroup = (VeyraBay), meta = (DisplayName = "VB District Grading"))
class VBWORLD_API AVBDistrictGrading : public AActor
{
	GENERATED_BODY()

public:
	AVBDistrictGrading();

	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Grading")
	TArray<FVBDistrictGrade> Districts;

	/** Uebergangsbreite an den Bezirksgrenzen (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Grading")
	float BlendDistance = 8000.f;

	/** Gesamtstaerke der Bezirksstimmung (0 = aus). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Grading", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float Strength = 1.f;

	UPROPERTY(VisibleAnywhere, Category = "Components")
	TObjectPtr<UPostProcessComponent> PostProcess;

private:
	FLinearColor CurrentGain = FLinearColor::White;
	float CurrentSaturation = 1.f;
	float CurrentContrast = 1.f;
};
