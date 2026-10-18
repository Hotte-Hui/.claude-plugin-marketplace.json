#include "VBDistrictGrading.h"

#include "Components/PostProcessComponent.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"

AVBDistrictGrading::AVBDistrictGrading()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = 0.1f;
#if WITH_EDITORONLY_DATA
	bIsSpatiallyLoaded = false;
#endif

	PostProcess = CreateDefaultSubobject<UPostProcessComponent>(TEXT("PostProcess"));
	RootComponent = PostProcess;
	PostProcess->bUnbound = true;
	PostProcess->Priority = 1.f;       // ueber dem Himmels-Post-Process (Belichtung bleibt dort)
	FPostProcessSettings& PP = PostProcess->Settings;
	PP.bOverride_ColorGain = true;
	PP.bOverride_ColorSaturation = true;
	PP.bOverride_ColorContrast = true;
}

void AVBDistrictGrading::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (!PC || Districts.Num() == 0)
	{
		return;
	}
	FVector View;
	FRotator Rotation;
	PC->GetPlayerViewPoint(View, Rotation);
	const FVector2D Point(View.X, View.Y);

	// Gewicht je Bezirk: 1 innen, weich auslaufend ueber BlendDistance ausserhalb
	FLinearColor Gain(0.f, 0.f, 0.f, 0.f);
	float Saturation = 0.f;
	float Contrast = 0.f;
	float Total = 0.f;
	for (const FVBDistrictGrade& District : Districts)
	{
		const float DX = FMath::Max3(District.Min.X - Point.X, 0.0, Point.X - District.Max.X);
		const float DY = FMath::Max3(District.Min.Y - Point.Y, 0.0, Point.Y - District.Max.Y);
		const float Outside = FMath::Sqrt(DX * DX + DY * DY);
		const float Weight = FMath::Clamp(1.f - Outside / FMath::Max(BlendDistance, 1.f), 0.f, 1.f);
		if (Weight <= 0.f)
		{
			continue;
		}
		Gain += District.Gain * Weight;
		Saturation += District.Saturation * Weight;
		Contrast += District.Contrast * Weight;
		Total += Weight;
	}
	FLinearColor TargetGain = FLinearColor::White;
	float TargetSaturation = 1.f;
	float TargetContrast = 1.f;
	if (Total > 0.f)
	{
		TargetGain = Gain / Total;
		TargetSaturation = Saturation / Total;
		TargetContrast = Contrast / Total;
	}
	TargetGain = FMath::Lerp(FLinearColor::White, TargetGain, Strength);
	TargetSaturation = FMath::Lerp(1.f, TargetSaturation, Strength);
	TargetContrast = FMath::Lerp(1.f, TargetContrast, Strength);

	const float Alpha = FMath::Clamp(DeltaSeconds * 1.5f, 0.f, 1.f);
	CurrentGain = FMath::Lerp(CurrentGain, TargetGain, Alpha);
	CurrentSaturation = FMath::Lerp(CurrentSaturation, TargetSaturation, Alpha);
	CurrentContrast = FMath::Lerp(CurrentContrast, TargetContrast, Alpha);

	FPostProcessSettings& PP = PostProcess->Settings;
	PP.ColorGain = FVector4(CurrentGain.R, CurrentGain.G, CurrentGain.B, 1.f);
	PP.ColorSaturation = FVector4(1.f, 1.f, 1.f, CurrentSaturation);
	PP.ColorContrast = FVector4(1.f, 1.f, 1.f, CurrentContrast);
}
