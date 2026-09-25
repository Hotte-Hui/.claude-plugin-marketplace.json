#pragma once

#include "CoreMinimal.h"
#include "Curves/CurveFloat.h"
#include "GameFramework/Actor.h"
#include "VBCrowdManager.generated.h"

class AVBPedestrian;
class AVBTrafficLight;
class AVBTrafficManager;
class UAnimInstance;
class USkeletalMesh;

/** Knoten des Gehweg-Graphen (Kreuzungsecken, Strassenenden). */
struct FVBWalkNode
{
	FVector Location;
	TArray<int32> Edges;
};

/** Gehweg-Abschnitt oder Zebrastreifen. */
struct FVBWalkEdge
{
	int32 A = INDEX_NONE;
	int32 B = INDEX_NONE;
	bool bCrossing = false;
	/** Ampel fuer den Autoverkehr, der diesen Uebergang kreuzt (Fussgaenger gehen bei deren Rot). */
	TWeakObjectPtr<AVBTrafficLight> Signal;
	float Length = 0.f;

	int32 Other(int32 Node) const { return Node == A ? B : A; }
};

struct FVBWalker
{
	TObjectPtr<AVBPedestrian> Actor;
	int32 Edge = INDEX_NONE;
	int32 TargetNode = INDEX_NONE;
	float Lateral = 0.f;          // seitlicher Versatz auf dem Gehweg
	float Speed = 135.f;
	float IdleTime = 0.f;         // > 0: bleibt stehen (Schaufenster, Telefon ...)
	float StuckTime = 0.f;
	bool bWaiting = false;        // wartet an der Ampel
};

/**
 * Passanten (Phase 5): Gehweg-Graph aus den Strassen und Kreuzungen (Ecken, Zebrastreifen),
 * Passanten laufen zufaellige Wege, warten an roten Ampeln, gehen bei Rot fuer die Autos ueber
 * den Zebrastreifen und melden sich dabei beim Verkehr als Hindernis. Dichte nach Tageszeit und Wetter.
 */
UCLASS(ClassGroup = (VeyraBay), meta = (DisplayName = "VB Crowd Manager"))
class VEYRABAY_API AVBCrowdManager : public AActor
{
	GENERATED_BODY()

public:
	AVBCrowdManager();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Crowd")
	bool bEnableCrowd = true;

	/** Leer = Mannequins aus dem Third Person Pack (Manny/Quinn). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Crowd")
	TArray<TSoftObjectPtr<USkeletalMesh>> Meshes;

	/** Leer = AnimBlueprint der Spielfigur. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Crowd")
	TSoftClassPtr<UAnimInstance> AnimClass;

	/** Passanten pro 100 m Gehweg bei voller Dichte. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Crowd", meta = (ClampMin = "0.0"))
	float PedestriansPer100m = 5.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Crowd", meta = (ClampMin = "0"))
	int32 MaxPedestrians = 70;

	/** Dichte ueber den Tag (x = Stunde, y = 0..1). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Crowd")
	FRuntimeFloatCurve DensityByHour;

	/** Abstand Strassenmitte -> Gehweg-Laufmitte (cm); Gehweg reicht von 618 bis 978. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Layout")
	float SidewalkOffset = 800.f;

	/** Kreuzungsmitte -> Rand des Kreuzungs-Meshes (cm), passend zu vb_asset_streetkit.py. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Layout")
	float JunctionHalfSize = 978.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Layout")
	float SidewalkHeight = 15.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Debug")
	bool bDrawDebug = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Crowd")
	int32 Seed = 99;

private:
	void BuildGraph();
	int32 AddNode(const FVector& Location, float MergeDistance);
	void AddEdge(int32 A, int32 B, bool bCrossing, AVBTrafficLight* Signal);
	void LoadAssets();
	void UpdateDensity(float DeltaSeconds);
	bool TrySpawn(bool bAvoidPlayer);
	void RemoveWalker(int32 Index);
	void StepWalker(FVBWalker& Walker, float DeltaSeconds);
	bool MayCross(const FVBWalkEdge& Edge, float Speed) const;
	int32 PickNextEdge(int32 Node, int32 FromEdge);
	FVector EdgePoint(const FVBWalker& Walker, int32 Node) const;
	float DistanceToPlayer(const FVector& Location, bool* bOutInView = nullptr) const;
	void DrawDebug() const;

	TArray<FVBWalkNode> Nodes;
	TArray<FVBWalkEdge> Edges;
	TArray<FVBWalker> Walkers;
	float TotalSidewalk = 0.f;
	float SpawnTimer = 0.f;
	FRandomStream Random;

	UPROPERTY(Transient)
	TArray<TObjectPtr<USkeletalMesh>> LoadedMeshes;

	UPROPERTY(Transient)
	TObjectPtr<UClass> LoadedAnimClass;

	UPROPERTY(Transient)
	TArray<TObjectPtr<AVBPedestrian>> SpawnedActors;

	UPROPERTY(Transient)
	TObjectPtr<AVBTrafficManager> Traffic;
};
