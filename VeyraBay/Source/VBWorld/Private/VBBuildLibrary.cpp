#include "VBBuildLibrary.h"

#include "VBInstancedArray.h"
#include "VBStreetLight.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"

namespace VBBuild
{
	static UWorld* WorldOf(UObject* WorldContextObject)
	{
		return WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	}

	static FTransform MakeTransform(const FVector& Location, float Yaw)
	{
		return FTransform(FRotator(0.f, Yaw, 0.f), Location);
	}

	template <typename T>
	static T* Begin(UWorld* World, const FTransform& Transform)
	{
		if (!World)
		{
			return nullptr;
		}
		T* Actor = World->SpawnActorDeferred<T>(T::StaticClass(), Transform, nullptr, nullptr,
			ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
		if (Actor)
		{
			Actor->SetFlags(RF_Transactional);
		}
		return Actor;
	}
}

void UVBBuildLibrary::MarkGenerated(AActor* Actor, const FString& Label, const FString& Folder, bool bSpatiallyLoaded)
{
	if (!Actor)
	{
		return;
	}
	Actor->Tags.AddUnique(TEXT("VB_Generated"));
#if WITH_EDITOR
	if (!Label.IsEmpty())
	{
		Actor->SetActorLabel(Label);
	}
	if (!Folder.IsEmpty())
	{
		Actor->SetFolderPath(FName(*Folder));
	}
	Actor->SetIsSpatiallyLoaded(bSpatiallyLoaded);
#endif
}

AVBBuildingBuilder* UVBBuildLibrary::SpawnBuilding(UObject* WorldContextObject, const FVector& Location, float Yaw, const FVBFacadeStyle& Style,
	int32 BaysX, int32 BaysY, int32 Floors, EVBFacadeMode Front, EVBFacadeMode Right, EVBFacadeMode Back, EVBFacadeMode Left,
	int32 Seed, float ShopRatio, UStaticMesh* RoofTile, const TArray<UStaticMesh*>& RoofProps, const FString& Label, const FString& Folder)
{
	const FTransform Transform = VBBuild::MakeTransform(Location, Yaw);
	AVBBuildingBuilder* Building = VBBuild::Begin<AVBBuildingBuilder>(VBBuild::WorldOf(WorldContextObject), Transform);
	if (!Building)
	{
		return nullptr;
	}
	Building->Style = Style;
	Building->BaysX = FMath::Max(BaysX, 1);
	Building->BaysY = FMath::Max(BaysY, 1);
	Building->Floors = FMath::Max(Floors, 1);
	Building->Front = Front;
	Building->Right = Right;
	Building->Back = Back;
	Building->Left = Left;
	Building->Seed = Seed;
	Building->ShopRatio = ShopRatio;
	Building->RoofTile = RoofTile;
	Building->RoofProps.Reset();
	for (UStaticMesh* Prop : RoofProps)
	{
		Building->RoofProps.Add(Prop);
	}
	MarkGenerated(Building, Label, Folder, true);
	Building->FinishSpawning(Transform);
	return Building;
}

AVBStreetBuilder* UVBBuildLibrary::SpawnStreet(UObject* WorldContextObject, const FVector& Location, float Yaw, float Length,
	UStaticMesh* RoadMesh, UStaticMesh* CurbMesh, UStaticMesh* SidewalkMesh, const TArray<FVBStreetPropRule>& Props, int32 Seed,
	const FString& Label, const FString& Folder)
{
	const FTransform Transform = VBBuild::MakeTransform(Location, Yaw);
	AVBStreetBuilder* Street = VBBuild::Begin<AVBStreetBuilder>(VBBuild::WorldOf(WorldContextObject), Transform);
	if (!Street)
	{
		return nullptr;
	}
	Street->Length = Length;
	Street->RoadMesh = RoadMesh;
	Street->CurbMesh = CurbMesh;
	Street->SidewalkMesh = SidewalkMesh;
	Street->CrosswalkPieceIndex = INDEX_NONE;
	Street->Seed = Seed;
	Street->Props = Props;
	MarkGenerated(Street, Label, Folder, true);
	Street->FinishSpawning(Transform);
	return Street;
}

AVBInstancedArray* UVBBuildLibrary::SpawnInstances(UObject* WorldContextObject, UStaticMesh* Mesh, const TArray<FTransform>& Transforms,
	bool bCastShadow, const FString& Label, const FString& Folder, bool bSpatiallyLoaded)
{
	if (!Mesh || Transforms.Num() == 0)
	{
		return nullptr;
	}
	// Instanzen relativ zum ersten Punkt -> Actor-Position liegt im Gebiet (wichtig fuer World-Partition-Zellen)
	const FVector Origin = Transforms[0].GetLocation();
	const FTransform Transform(FRotator::ZeroRotator, Origin);
	AVBInstancedArray* Array = VBBuild::Begin<AVBInstancedArray>(VBBuild::WorldOf(WorldContextObject), Transform);
	if (!Array)
	{
		return nullptr;
	}
	Array->Mesh = Mesh;
	Array->bCastShadow = bCastShadow;
	Array->Transforms.Reset(Transforms.Num());
	for (const FTransform& Instance : Transforms)
	{
		FTransform Local = Instance;
		Local.SetLocation(Instance.GetLocation() - Origin);
		Array->Transforms.Add(Local);
	}
	MarkGenerated(Array, Label, Folder, bSpatiallyLoaded);
	Array->FinishSpawning(Transform);
	return Array;
}

AActor* UVBBuildLibrary::SpawnMesh(UObject* WorldContextObject, UStaticMesh* Mesh, const FVector& Location, float Yaw, const FString& Label,
	const FString& Folder, bool bSpatiallyLoaded)
{
	if (!Mesh)
	{
		return nullptr;
	}
	const FTransform Transform = VBBuild::MakeTransform(Location, Yaw);
	AStaticMeshActor* Actor = VBBuild::Begin<AStaticMeshActor>(VBBuild::WorldOf(WorldContextObject), Transform);
	if (!Actor)
	{
		return nullptr;
	}
	Actor->GetStaticMeshComponent()->SetMobility(EComponentMobility::Static);
	Actor->GetStaticMeshComponent()->SetStaticMesh(Mesh);
	MarkGenerated(Actor, Label, Folder, bSpatiallyLoaded);
	Actor->FinishSpawning(Transform);
	return Actor;
}

AVBStreetLight* UVBBuildLibrary::SpawnStreetLight(UObject* WorldContextObject, const FVector& Location, float Yaw, UStaticMesh* Model,
	const FString& Label, const FString& Folder)
{
	const FTransform Transform = VBBuild::MakeTransform(Location, Yaw);
	AVBStreetLight* Light = VBBuild::Begin<AVBStreetLight>(VBBuild::WorldOf(WorldContextObject), Transform);
	if (!Light)
	{
		return nullptr;
	}
	Light->Model = Model;
	MarkGenerated(Light, Label, Folder, true);
	Light->FinishSpawning(Transform);
	return Light;
}
