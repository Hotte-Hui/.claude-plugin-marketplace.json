#include "VBWorldParams.h"

#include "VBWorldDeveloperSettings.h"
#include "Engine/World.h"
#include "Materials/MaterialParameterCollection.h"
#include "Materials/MaterialParameterCollectionInstance.h"

namespace VBWorldParams
{
	const FName TimeOfDay01(TEXT("TimeOfDay01"));
	const FName NightFactor(TEXT("NightFactor"));
	const FName SunElevation(TEXT("SunElevation"));
	const FName Wetness(TEXT("Wetness"));
	const FName Puddles(TEXT("Puddles"));
	const FName RainIntensity(TEXT("RainIntensity"));
	const FName WindStrength(TEXT("WindStrength"));
	const FName CloudCoverage(TEXT("CloudCoverage"));
	const FName FogAmount(TEXT("FogAmount"));
	const FName LightningFlash(TEXT("LightningFlash"));
	const FName WindDirection(TEXT("WindDirection"));

	static UMaterialParameterCollectionInstance* GetInstance(UWorld* World)
	{
		if (!World)
		{
			return nullptr;
		}

		const UVBWorldDeveloperSettings* Settings = GetDefault<UVBWorldDeveloperSettings>();
		if (Settings->WorldParameterCollection.IsNull())
		{
			return nullptr;
		}

		UMaterialParameterCollection* Collection = Settings->WorldParameterCollection.Get();
		if (!Collection)
		{
			Collection = Settings->WorldParameterCollection.LoadSynchronous();
		}

		return Collection ? World->GetParameterCollectionInstance(Collection) : nullptr;
	}

	void SetScalar(UWorld* World, FName Name, float Value)
	{
		if (UMaterialParameterCollectionInstance* Instance = GetInstance(World))
		{
			Instance->SetScalarParameterValue(Name, Value);
		}
	}

	void SetVector(UWorld* World, FName Name, const FLinearColor& Value)
	{
		if (UMaterialParameterCollectionInstance* Instance = GetInstance(World))
		{
			Instance->SetVectorParameterValue(Name, Value);
		}
	}
}
