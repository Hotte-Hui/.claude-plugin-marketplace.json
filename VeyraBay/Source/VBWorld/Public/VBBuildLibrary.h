#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "VBBuildingBuilder.h"
#include "VBStreetBuilder.h"
#include "VBBuildLibrary.generated.h"

class AVBInstancedArray;
class AVBStreetLight;
class UStaticMesh;

/**
 * Schnelles Platzieren fuer die Aufbau-Skripte (Python): Actors werden "deferred" gespawnt, alle Eigenschaften
 * gesetzt und das Construction Script genau einmal ausgefuehrt. (set_editor_property aus Python loest pro
 * Eigenschaft einen Neuaufbau aus - bei tausenden Gebaeuden viel zu langsam.)
 * Alle Actors bekommen das Tag VB_Generated, Label und Ordner; bSpatiallyLoaded steuert World Partition.
 */
UCLASS()
class VBWORLD_API UVBBuildLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Build", meta = (WorldContext = "WorldContextObject"))
	static AVBBuildingBuilder* SpawnBuilding(UObject* WorldContextObject, const FVector& Location, float Yaw, const FVBFacadeStyle& Style,
		int32 BaysX, int32 BaysY, int32 Floors, EVBFacadeMode Front, EVBFacadeMode Right, EVBFacadeMode Back, EVBFacadeMode Left,
		int32 Seed, float ShopRatio, UStaticMesh* RoofTile, const TArray<UStaticMesh*>& RoofProps, const FString& Label,
		const FString& Folder);

	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Build", meta = (WorldContext = "WorldContextObject"))
	static AVBStreetBuilder* SpawnStreet(UObject* WorldContextObject, const FVector& Location, float Yaw, float Length,
		UStaticMesh* RoadMesh, UStaticMesh* CurbMesh, UStaticMesh* SidewalkMesh, const TArray<FVBStreetPropRule>& Props, int32 Seed,
		const FString& Label, const FString& Folder);

	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Build", meta = (WorldContext = "WorldContextObject"))
	static AVBInstancedArray* SpawnInstances(UObject* WorldContextObject, UStaticMesh* Mesh, const TArray<FTransform>& Transforms,
		bool bCastShadow, const FString& Label, const FString& Folder, bool bSpatiallyLoaded = true);

	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Build", meta = (WorldContext = "WorldContextObject"))
	static AActor* SpawnMesh(UObject* WorldContextObject, UStaticMesh* Mesh, const FVector& Location, float Yaw, const FString& Label,
		const FString& Folder, bool bSpatiallyLoaded = true);

	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Build", meta = (WorldContext = "WorldContextObject"))
	static AVBStreetLight* SpawnStreetLight(UObject* WorldContextObject, const FVector& Location, float Yaw, UStaticMesh* Model,
		const FString& Label, const FString& Folder);

	/** Tag VB_Generated, Label, Ordner, World-Partition-Streaming. */
	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Build")
	static void MarkGenerated(AActor* Actor, const FString& Label, const FString& Folder, bool bSpatiallyLoaded = true);
};
