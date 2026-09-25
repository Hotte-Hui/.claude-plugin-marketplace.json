#pragma once

#include "CoreMinimal.h"
#include "Curves/CurveFloat.h"
#include "GameFramework/Actor.h"
#include "VBTrafficLight.h"
#include "VBCrowdManager.generated.h"

class AVBPedestrian;
class AVBTrafficLight;
class AVBTrafficManager;
class UAnimInstance;
class USkeletalMesh;

/** Knoten des Gehweg-Graphen (Kreuzungsecken, Strassenenden). */
USTRUCT()
struct FVBWalkNode
{
	GENERATED_BODY()

	UPROPERTY() FVector Location = FVector::ZeroVector;
	UPROPERTY() TArray<int32> Edges;
};

/** Gehweg-Abschnitt oder Zebrastreifen. */
USTRUCT()
struct FVBWalkEdge
{
	GENERATED_BODY()

	UPROPERTY() int32 A = INDEX_NONE;
	UPROPERTY() int32 B = INDEX_NONE;
	UPROPERTY() bool bCrossing = false;
	/** Ampel fuer den Autoverkehr, der diesen Uebergang kreuzt (Fussgaenger gehen bei deren Rot). */
	UPROPERTY() bool bHasSignal = false;
	UPROPERTY() FVBSignalTiming Signal;
	UPROPERTY() float Length = 0.f;

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

	/** Stehenden Passanten erzeugen (fuer Ereignisse: Zuhoerer, Musiker). Wird nicht vom Manager bewegt. */
	AVBPedestrian* SpawnStandingPedestrian(const FVector& Location, const FVector& FaceTowards);

	/** Zufaelliger Punkt auf einem Gehweg im Ring [MinDistance, MaxDistance] um Center (cm); false wenn keiner. */
	bool FindSidewalkPoint(const FVector& Center, float MinDistance, float MaxDistance, FVector& OutPoint, FVector& OutStreetDirection);

	/** Gehweg-Graph aus den Strassen der Karte berechnen und speichern (unabhaengig vom Streaming). */
	UFUNCTION(CallInEditor, BlueprintCallable, Category = "Crowd")
	void BakeNetwork();

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

	/** Passanten nur in diesem Umkreis um den Spieler (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Crowd", meta = (ClampMin = "3000.0"))
	float SimulationRadius = 16000.f;

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

	// --- Gebackene Daten ------------------------------------------------------------------
	UPROPERTY(VisibleAnywhere, Category = "Baked")
	TArray<FVBWalkNode> Nodes;

	UPROPERTY(VisibleAnywhere, Category = "Baked")
	TArray<FVBWalkEdge> Edges;

	UPROPERTY(VisibleAnywhere, Category = "Baked")
	float TotalSidewalk = 0.f;

private:
	void BuildGraph();
	void UpdateNearEdges();
	int32 AddNode(const FVector& Location, float MergeDistance);
	void AddEdge(int32 A, int32 B, bool bCrossing, const AVBTrafficLight* Signal);
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

	TArray<FVBWalker> Walkers;
	TArray<int32> NearEdges;
	float NearSidewalk = 0.f;
	float NearTimer = 0.f;
	FVector PlayerLocation = FVector::ZeroVector;
	TMap<FIntPoint, TArray<int32>> NodeGrid;    // nur waehrend des Aufbaus
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
