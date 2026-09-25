#include "VBCrowdManager.h"

#include "VBGameSettings.h"
#include "VBLog.h"
#include "VBPedestrian.h"
#include "VBStreetBuilder.h"
#include "VBTimeOfDaySubsystem.h"
#include "VBTrafficLight.h"
#include "VBTrafficManager.h"
#include "VBWeatherSubsystem.h"
#include "Animation/AnimInstance.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "DrawDebugHelpers.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"

namespace VBCrowd
{
	static const TCHAR* FallbackMeshes[] =
	{
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny.SKM_Manny"),
		TEXT("/Game/Characters/Mannequins/Meshes/SKM_Quinn.SKM_Quinn"),
	};
	static const TCHAR* FallbackAnimClasses[] =
	{
		TEXT("/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed.ABP_Unarmed_C"),
		TEXT("/Game/Characters/Mannequins/Animations/ABP_Manny.ABP_Manny_C"),
	};

	static FVector RightOf(const FVector& Dir)
	{
		return FVector(-Dir.Y, Dir.X, 0.f);
	}

	static float WeatherDensity(EVBWeatherType Type)
	{
		switch (Type)
		{
		case EVBWeatherType::Overcast:  return 0.9f;
		case EVBWeatherType::LightRain: return 0.55f;
		case EVBWeatherType::HeavyRain: return 0.25f;
		case EVBWeatherType::Fog:       return 0.7f;
		case EVBWeatherType::Storm:     return 0.1f;
		default:                        return 1.f;
		}
	}
}

AVBCrowdManager::AVBCrowdManager()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

	FRichCurve* Curve = DensityByHour.GetRichCurve();
	const float Keys[][2] = { {0.f, 0.1f}, {5.f, 0.05f}, {7.f, 0.5f}, {9.f, 0.8f}, {12.f, 1.f}, {18.f, 1.f},
		{21.f, 0.6f}, {23.f, 0.25f}, {24.f, 0.1f} };
	for (const auto& Key : Keys)
	{
		Curve->AddKey(Key[0], Key[1]);
	}
}

void AVBCrowdManager::BeginPlay()
{
	Super::BeginPlay();
	Random.Initialize(Seed);
	for (TActorIterator<AVBTrafficManager> It(GetWorld()); It; ++It)
	{
		Traffic = *It;
		break;
	}
	LoadAssets();
	BuildGraph();
	if (bEnableCrowd && LoadedMeshes.Num() > 0)
	{
		UpdateDensity(0.f);
	}
}

void AVBCrowdManager::LoadAssets()
{
	for (const TSoftObjectPtr<USkeletalMesh>& Mesh : Meshes)
	{
		if (USkeletalMesh* Loaded = Mesh.LoadSynchronous())
		{
			LoadedMeshes.Add(Loaded);
		}
	}
	for (const TCHAR* Path : VBCrowd::FallbackMeshes)
	{
		if (LoadedMeshes.Num() >= 2)
		{
			break;
		}
		if (USkeletalMesh* Loaded = LoadObject<USkeletalMesh>(nullptr, Path, nullptr, LOAD_NoWarn | LOAD_Quiet))
		{
			LoadedMeshes.AddUnique(Loaded);
		}
	}
	if (LoadedMeshes.Num() == 0)
	{
		const UVBGameSettings* Settings = GetDefault<UVBGameSettings>();
		if (USkeletalMesh* Loaded = Settings->PlayerMesh.IsNull() ? nullptr : Settings->PlayerMesh.LoadSynchronous())
		{
			LoadedMeshes.Add(Loaded);
		}
	}

	LoadedAnimClass = AnimClass.IsNull() ? nullptr : AnimClass.LoadSynchronous();
	if (!LoadedAnimClass)
	{
		const UVBGameSettings* Settings = GetDefault<UVBGameSettings>();
		LoadedAnimClass = Settings->PlayerAnimClass.IsNull() ? nullptr : Settings->PlayerAnimClass.LoadSynchronous();
	}
	for (int32 Index = 0; !LoadedAnimClass && Index < UE_ARRAY_COUNT(VBCrowd::FallbackAnimClasses); ++Index)
	{
		LoadedAnimClass = LoadClass<UAnimInstance>(nullptr, VBCrowd::FallbackAnimClasses[Index], nullptr, LOAD_NoWarn | LOAD_Quiet);
	}
	if (LoadedMeshes.Num() == 0)
	{
		UE_LOG(LogVB, Warning, TEXT("Passanten: kein Mannequin gefunden (Third Person Pack hinzufuegen)."));
	}
}

// ---------------------------------------------------------------------------------------------
// Gehweg-Graph
// ---------------------------------------------------------------------------------------------
int32 AVBCrowdManager::AddNode(const FVector& Location, float MergeDistance)
{
	for (int32 Index = 0; Index < Nodes.Num(); ++Index)
	{
		if (FVector::Dist2D(Nodes[Index].Location, Location) < MergeDistance)
		{
			return Index;
		}
	}
	FVBWalkNode Node;
	Node.Location = Location;
	return Nodes.Add(MoveTemp(Node));
}

void AVBCrowdManager::AddEdge(int32 A, int32 B, bool bCrossing, AVBTrafficLight* Signal)
{
	if (A == B)
	{
		return;
	}
	for (int32 EdgeIndex : Nodes[A].Edges)
	{
		if (Edges[EdgeIndex].Other(A) == B)
		{
			return;
		}
	}
	FVBWalkEdge Edge;
	Edge.A = A;
	Edge.B = B;
	Edge.bCrossing = bCrossing;
	Edge.Signal = Signal;
	Edge.Length = FVector::Dist2D(Nodes[A].Location, Nodes[B].Location);
	const int32 Index = Edges.Add(Edge);
	Nodes[A].Edges.Add(Index);
	Nodes[B].Edges.Add(Index);
	if (!bCrossing)
	{
		TotalSidewalk += Edge.Length;
	}
}

void AVBCrowdManager::BuildGraph()
{
	struct FJunction
	{
		FVector Center;
		FVector AxisX;
		TArray<FVector> Arms;
	};
	TArray<FJunction> Junctions;
	TArray<AVBStreetBuilder*> Streets;
	for (TActorIterator<AVBStreetBuilder> It(GetWorld()); It; ++It)
	{
		Streets.Add(*It);
	}

	for (const AVBStreetBuilder* Street : Streets)
	{
		const FTransform Transform = Street->GetActorTransform();
		const FVector Forward = Transform.GetUnitAxis(EAxis::X).GetSafeNormal2D();
		for (int32 End = 0; End < 2; ++End)
		{
			const FVector Point = Transform.TransformPosition(FVector(End == 0 ? 0.f : Street->Length, 0.f, 0.f));
			const FVector Out = End == 0 ? -Forward : Forward;
			const FVector Center = Point + Out * JunctionHalfSize;
			FJunction* Found = Junctions.FindByPredicate([&Center](const FJunction& J) { return FVector::Dist2D(J.Center, Center) < 300.f; });
			if (!Found)
			{
				FJunction& New = Junctions.AddDefaulted_GetRef();
				New.Center = Center;
				New.AxisX = Out;
				Found = &New;
			}
			Found->Arms.Add(-Out);
		}
	}

	TArray<AVBTrafficLight*> Signals;
	for (TActorIterator<AVBTrafficLight> It(GetWorld()); It; ++It)
	{
		Signals.Add(*It);
	}

	// Ecken und Uebergaenge je Kreuzung
	int32 Crossings = 0;
	for (const FJunction& Junction : Junctions)
	{
		if (Junction.Arms.Num() < 2)
		{
			continue;   // Strassenende ohne Kreuzung
		}
		const FVector AX = Junction.AxisX;
		const FVector AY = VBCrowd::RightOf(AX);
		const FVector Up(0.f, 0.f, SidewalkHeight);
		int32 Corner[2][2];
		for (int32 SX = 0; SX < 2; ++SX)
		{
			for (int32 SY = 0; SY < 2; ++SY)
			{
				const float X = SX == 0 ? -SidewalkOffset : SidewalkOffset;
				const float Y = SY == 0 ? -SidewalkOffset : SidewalkOffset;
				Corner[SX][SY] = AddNode(Junction.Center + AX * X + AY * Y + Up, 60.f);
			}
		}
		struct FSide { FVector Dir; int32 A; int32 B; };
		const FSide Sides[4] = {
			{ AX,  Corner[1][0], Corner[1][1] },
			{ -AX, Corner[0][0], Corner[0][1] },
			{ AY,  Corner[0][1], Corner[1][1] },
			{ -AY, Corner[0][0], Corner[1][0] },
		};
		for (const FSide& Side : Sides)
		{
			const bool bArm = Junction.Arms.ContainsByPredicate([&Side](const FVector& Arm) { return FVector::DotProduct(Arm, Side.Dir) > 0.9f; });
			AVBTrafficLight* Signal = nullptr;
			if (bArm)
			{
				float Best = 1600.f;
				const FVector CrossingCenter = Junction.Center + Side.Dir * SidewalkOffset;
				for (AVBTrafficLight* Light : Signals)
				{
					const float Facing = FMath::Abs(FVector::DotProduct(Light->GetActorForwardVector().GetSafeNormal2D(), Side.Dir));
					const float Distance = FVector::Dist2D(Light->GetActorLocation(), CrossingCenter);
					if (Facing > 0.8f && Distance < Best)
					{
						Best = Distance;
						Signal = Light;
					}
				}
				++Crossings;
			}
			AddEdge(Side.A, Side.B, bArm, Signal);
		}
	}

	// Gehwege entlang der Strassen (Enden verschmelzen mit den Kreuzungsecken)
	for (const AVBStreetBuilder* Street : Streets)
	{
		const FTransform Transform = Street->GetActorTransform();
		for (int32 Side = -1; Side <= 1; Side += 2)
		{
			const FVector A = Transform.TransformPosition(FVector(0.f, Side * SidewalkOffset, SidewalkHeight));
			const FVector B = Transform.TransformPosition(FVector(Street->Length, Side * SidewalkOffset, SidewalkHeight));
			AddEdge(AddNode(A, 400.f), AddNode(B, 400.f), false, nullptr);
		}
	}

	UE_LOG(LogVB, Log, TEXT("Passanten: %d Knoten, %d Wege, %d Uebergaenge, %.0f m Gehweg"), Nodes.Num(), Edges.Num(), Crossings, TotalSidewalk / 100.f);
}

// ---------------------------------------------------------------------------------------------
// Dichte
// ---------------------------------------------------------------------------------------------
float AVBCrowdManager::DistanceToPlayer(const FVector& Location, bool* bOutInView) const
{
	float Best = TNumericLimits<float>::Max();
	bool bInView = false;
	for (FConstPlayerControllerIterator It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
	{
		if (const APlayerController* PC = It->Get())
		{
			FVector ViewLocation;
			FRotator ViewRotation;
			PC->GetPlayerViewPoint(ViewLocation, ViewRotation);
			const FVector Delta = Location - ViewLocation;
			Best = FMath::Min(Best, static_cast<float>(Delta.Size()));
			bInView |= FVector::DotProduct(Delta.GetSafeNormal(), ViewRotation.Vector()) > 0.45f;
		}
	}
	if (bOutInView)
	{
		*bOutInView = bInView;
	}
	return Best;
}

void AVBCrowdManager::UpdateDensity(float DeltaSeconds)
{
	const UVBTimeOfDaySubsystem* Time = GetWorld()->GetSubsystem<UVBTimeOfDaySubsystem>();
	const UVBWeatherSubsystem* Weather = GetWorld()->GetSubsystem<UVBWeatherSubsystem>();
	const float Hour = Time ? Time->GetTimeOfDay() : 12.f;
	const float Density = FMath::Clamp(DensityByHour.GetRichCurveConst()->Eval(Hour), 0.f, 1.f)
		* VBCrowd::WeatherDensity(Weather ? Weather->GetWeather() : EVBWeatherType::Clear);
	const int32 Target = FMath::Min(MaxPedestrians, FMath::RoundToInt(TotalSidewalk / 10000.f * PedestriansPer100m * Density));

	if (DeltaSeconds <= 0.f)
	{
		for (int32 Attempt = 0; Attempt < Target * 4 && Walkers.Num() < Target; ++Attempt)
		{
			TrySpawn(false);
		}
		return;
	}

	SpawnTimer -= DeltaSeconds;
	if (SpawnTimer > 0.f)
	{
		return;
	}
	SpawnTimer = 0.4f;
	if (Walkers.Num() < Target)
	{
		TrySpawn(true);
	}
	else if (Walkers.Num() > Target + 2)
	{
		// Bei Regen/Nacht verschwinden Passanten ausserhalb der Sicht ("gehen nach Hause")
		for (int32 Index = 0; Index < Walkers.Num(); ++Index)
		{
			bool bInView = false;
			const float Distance = DistanceToPlayer(Walkers[Index].Actor->GetActorLocation(), &bInView);
			if (Distance > 6000.f || (!bInView && Distance > 2500.f))
			{
				RemoveWalker(Index);
				break;
			}
		}
	}
}

bool AVBCrowdManager::TrySpawn(bool bAvoidPlayer)
{
	if (TotalSidewalk <= 0.f || LoadedMeshes.Num() == 0)
	{
		return false;
	}
	float Pick = Random.FRand() * TotalSidewalk;
	int32 EdgeIndex = INDEX_NONE;
	for (int32 Index = 0; Index < Edges.Num(); ++Index)
	{
		if (Edges[Index].bCrossing)
		{
			continue;
		}
		Pick -= Edges[Index].Length;
		if (Pick <= 0.f)
		{
			EdgeIndex = Index;
			break;
		}
	}
	if (EdgeIndex == INDEX_NONE)
	{
		return false;
	}
	const FVBWalkEdge& Edge = Edges[EdgeIndex];
	const FVector A = Nodes[Edge.A].Location;
	const FVector B = Nodes[Edge.B].Location;
	const FVector Dir = (B - A).GetSafeNormal2D();
	const float Lateral = Random.FRandRange(-85.f, 85.f);
	const FVector Location = FMath::Lerp(A, B, Random.FRandRange(0.05f, 0.95f)) + VBCrowd::RightOf(Dir) * Lateral + FVector(0.f, 0.f, 97.f);

	bool bInView = false;
	const float Distance = DistanceToPlayer(Location, &bInView);
	if (Distance < 600.f || (bAvoidPlayer && bInView && Distance < 7000.f))
	{
		return false;
	}

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButDontSpawnIfColliding;
	Params.Owner = this;
	const int32 TargetNode = Random.FRand() < 0.5f ? Edge.A : Edge.B;
	const FRotator Rotation = (Nodes[TargetNode].Location - Location).GetSafeNormal2D().Rotation();
	AVBPedestrian* Ped = GetWorld()->SpawnActor<AVBPedestrian>(Location, FRotator(0.f, Rotation.Yaw, 0.f), Params);
	if (!Ped)
	{
		return false;
	}
	USkeletalMeshComponent* Body = Ped->GetMesh();
	Body->SetSkeletalMeshAsset(LoadedMeshes[Random.RandRange(0, LoadedMeshes.Num() - 1)]);
	if (LoadedAnimClass)
	{
		Body->SetAnimInstanceClass(LoadedAnimClass);
	}
	const float Scale = Random.FRandRange(0.94f, 1.06f);
	Ped->SetActorScale3D(FVector(Scale));

	FVBWalker Walker;
	Walker.Actor = Ped;
	Walker.Edge = EdgeIndex;
	Walker.TargetNode = TargetNode;
	Walker.Lateral = Lateral;
	Walker.Speed = Random.FRandRange(115.f, 160.f);
	Ped->SetWalkSpeed(Walker.Speed);
	SpawnedActors.Add(Ped);
	Walkers.Add(Walker);
	return true;
}

void AVBCrowdManager::RemoveWalker(int32 Index)
{
	if (AVBPedestrian* Ped = Walkers[Index].Actor)
	{
		SpawnedActors.Remove(Ped);
		Ped->Destroy();
	}
	Walkers.RemoveAtSwap(Index);
}

// ---------------------------------------------------------------------------------------------
// Laufen
// ---------------------------------------------------------------------------------------------
bool AVBCrowdManager::MayCross(const FVBWalkEdge& Edge, float Speed) const
{
	const AVBTrafficLight* Signal = Edge.Signal.Get();
	if (!Signal)
	{
		return true;   // Zebrastreifen ohne Ampel: Fussgaenger haben Vorrang, Autos halten
	}
	return Signal->GetState() == EVBSignalState::Red && Signal->GetTimeUntilChange() > Edge.Length / FMath::Max(Speed, 50.f) + 1.5f;
}

int32 AVBCrowdManager::PickNextEdge(int32 Node, int32 FromEdge)
{
	const TArray<int32>& Options = Nodes[Node].Edges;
	if (Options.Num() == 0)
	{
		return INDEX_NONE;
	}
	if (Options.Num() == 1)
	{
		return Options[0];   // Sackgasse: umkehren
	}
	for (int32 Attempt = 0; Attempt < 8; ++Attempt)
	{
		const int32 Candidate = Options[Random.RandRange(0, Options.Num() - 1)];
		if (Candidate != FromEdge)
		{
			return Candidate;
		}
	}
	return Options[0];
}

FVector AVBCrowdManager::EdgePoint(const FVBWalker& Walker, int32 Node) const
{
	const FVBWalkEdge& Edge = Edges[Walker.Edge];
	const FVector From = Nodes[Edge.Other(Node)].Location;
	const FVector To = Nodes[Node].Location;
	const FVector Dir = (To - From).GetSafeNormal2D();
	return To + VBCrowd::RightOf(Dir) * Walker.Lateral;
}

void AVBCrowdManager::StepWalker(FVBWalker& Walker, float DeltaSeconds)
{
	AVBPedestrian* Ped = Walker.Actor;
	const FVBWalkEdge& Edge = Edges[Walker.Edge];

	if (Walker.IdleTime > 0.f)
	{
		Walker.IdleTime -= DeltaSeconds;
		return;
	}

	const FVector Target = EdgePoint(Walker, Walker.TargetNode);
	const FVector Location = Ped->GetActorLocation();

	// Auf dem Zebrastreifen: den Autos als Hindernis melden
	if (Edge.bCrossing && Traffic)
	{
		Traffic->AddTransientObstacle(Location - FVector(0.f, 0.f, 90.f), 60.f);
	}

	if (FVector::Dist2D(Location, Target) > 70.f)
	{
		Ped->MoveTowards(Target, 1.f);
		Walker.StuckTime = Ped->GetVelocity().Size2D() < 15.f ? Walker.StuckTime + DeltaSeconds : 0.f;
		return;
	}

	// Knoten erreicht: naechsten Weg waehlen
	const int32 Node = Walker.TargetNode;
	const int32 NextEdge = PickNextEdge(Node, Walker.Edge);
	if (NextEdge == INDEX_NONE)
	{
		return;
	}
	const FVBWalkEdge& Next = Edges[NextEdge];
	if (Next.bCrossing && !MayCross(Next, Walker.Speed))
	{
		// An der Ampel warten (Richtung Uebergang schauen); neue Wahl erst nach Gruen
		Walker.bWaiting = true;
		Ped->StandFacing(Nodes[Next.Other(Node)].Location - Nodes[Node].Location);
		if (Random.FRand() < 0.004f)
		{
			// Manche gehen doch lieber auf dieser Seite weiter
			Walker.Edge = PickNextEdge(Node, NextEdge);
			Walker.TargetNode = Edges[Walker.Edge].Other(Node);
			Walker.bWaiting = false;
		}
		return;
	}
	Walker.bWaiting = false;
	Walker.Edge = NextEdge;
	Walker.TargetNode = Next.Other(Node);
	Walker.Lateral = FMath::Clamp(Walker.Lateral + Random.FRandRange(-30.f, 30.f), -85.f, 85.f);
	if (!Next.bCrossing && Random.FRand() < 0.08f)
	{
		Walker.IdleTime = Random.FRandRange(2.f, 7.f);
	}
}

void AVBCrowdManager::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bEnableCrowd || Edges.Num() == 0)
	{
		return;
	}
	for (int32 Index = Walkers.Num() - 1; Index >= 0; --Index)
	{
		FVBWalker& Walker = Walkers[Index];
		if (!IsValid(Walker.Actor))
		{
			Walkers.RemoveAtSwap(Index);
			continue;
		}
		StepWalker(Walker, DeltaSeconds);
		if (Walker.StuckTime > 6.f)
		{
			bool bInView = false;
			const float Distance = DistanceToPlayer(Walker.Actor->GetActorLocation(), &bInView);
			if (!bInView || Distance > 3000.f)
			{
				RemoveWalker(Index);
			}
			else
			{
				Walker.StuckTime = 0.f;
				Walker.TargetNode = Edges[Walker.Edge].Other(Walker.TargetNode);   // umdrehen
			}
		}
	}
	UpdateDensity(DeltaSeconds);
	if (bDrawDebug)
	{
		DrawDebug();
	}
}

void AVBCrowdManager::DrawDebug() const
{
	for (const FVBWalkEdge& Edge : Edges)
	{
		FColor Color = FColor::Blue;
		if (Edge.bCrossing)
		{
			Color = MayCross(Edge, 130.f) ? FColor::Green : FColor::Red;
		}
		DrawDebugLine(GetWorld(), Nodes[Edge.A].Location + FVector(0, 0, 10), Nodes[Edge.B].Location + FVector(0, 0, 10), Color, false, -1.f, 0, 5.f);
	}
}
