#include "VBStreetBuilder.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"

namespace VBStreet
{
	static UInstancedStaticMeshComponent* CreateInstances(AActor* Owner, USceneComponent* Parent, const TCHAR* Name)
	{
		UInstancedStaticMeshComponent* Instances = Owner->CreateDefaultSubobject<UInstancedStaticMeshComponent>(Name);
		Instances->SetupAttachment(Parent);
		Instances->SetMobility(EComponentMobility::Static);
		return Instances;
	}

	static void Reset(UInstancedStaticMeshComponent* Instances, UStaticMesh* Mesh)
	{
		Instances->ClearInstances();
		Instances->SetStaticMesh(Mesh);
		Instances->SetVisibility(Mesh != nullptr);
	}
}

AVBStreetBuilder::AVBStreetBuilder()
{
	PrimaryActorTick.bCanEverTick = false;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Static);
	RootComponent = Root;

	RoadInstances = VBStreet::CreateInstances(this, Root, TEXT("RoadInstances"));
	CrosswalkInstances = VBStreet::CreateInstances(this, Root, TEXT("CrosswalkInstances"));
	CurbInstances = VBStreet::CreateInstances(this, Root, TEXT("CurbInstances"));
	SidewalkInstances = VBStreet::CreateInstances(this, Root, TEXT("SidewalkInstances"));

	for (int32 Index = 0; Index < MaxPropRules; ++Index)
	{
		const FString Name = FString::Printf(TEXT("PropInstances_%d"), Index);
		UInstancedStaticMeshComponent* Props = VBStreet::CreateInstances(this, Root, *Name);
		Props->SetCullDistances(12000, 15000);        // Stadtmoebel ab 120-150 m ausblenden
		PropInstances.Add(Props);
	}
}

void AVBStreetBuilder::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	Rebuild();
}

float AVBStreetBuilder::GetRoadSurfaceHeight(float LocalY) const
{
	const float Distance = FMath::Abs(LocalY);
	if (Distance <= AsphaltHalfWidth)
	{
		return CrownHeight * (1.f - Distance / FMath::Max(AsphaltHalfWidth, 1.f));
	}
	const float GutterWidth = FMath::Max(CurbOffset - AsphaltHalfWidth, 1.f);
	return -1.f * FMath::Min(1.f, (Distance - AsphaltHalfWidth) / GutterWidth);
}

void AVBStreetBuilder::Rebuild()
{
	VBStreet::Reset(RoadInstances, RoadMesh);
	VBStreet::Reset(CrosswalkInstances, CrosswalkMesh);
	VBStreet::Reset(CurbInstances, CurbMesh);
	VBStreet::Reset(SidewalkInstances, SidewalkMesh);

	// --- Fahrbahn ---------------------------------------------------------------------
	const int32 RoadPieces = FMath::Max(1, FMath::CeilToInt(Length / FMath::Max(RoadPieceLength, 1.f)));
	for (int32 Piece = 0; Piece < RoadPieces; ++Piece)
	{
		const FTransform PieceTransform(FVector(Piece * RoadPieceLength, 0.f, 0.f));
		const bool bCrosswalk = (Piece == CrosswalkPieceIndex) && CrosswalkMesh;
		UInstancedStaticMeshComponent* Target = bCrosswalk ? CrosswalkInstances.Get() : RoadInstances.Get();
		if (Target->GetStaticMesh())
		{
			Target->AddInstance(PieceTransform);
		}
	}

	// --- Bordsteine & Gehwege auf beiden Seiten ---------------------------------------------
	BuildEdges(CurbInstances, CurbMesh, CurbPieceLength);
	BuildEdges(SidewalkInstances, SidewalkMesh, SidewalkPieceLength);

	// --- Stadtmoebel -----------------------------------------------------------------------
	FRandomStream Stream(Seed);
	for (int32 Index = 0; Index < PropInstances.Num(); ++Index)
	{
		UInstancedStaticMeshComponent* Instances = PropInstances[Index];
		const FVBStreetPropRule* Rule = Props.IsValidIndex(Index) ? &Props[Index] : nullptr;
		VBStreet::Reset(Instances, Rule ? Rule->Mesh.Get() : nullptr);
		if (Rule && Rule->Mesh)
		{
			BuildProps(*Rule, Instances, Stream);
		}
	}
}

void AVBStreetBuilder::BuildEdges(UInstancedStaticMeshComponent* Instances, UStaticMesh* Mesh, float PieceLength) const
{
	if (!Mesh || PieceLength <= 1.f)
	{
		return;
	}

	const int32 Pieces = FMath::Max(1, FMath::CeilToInt(Length / PieceLength));
	for (int32 Piece = 0; Piece < Pieces; ++Piece)
	{
		const float X = Piece * PieceLength;
		// Rechte Seite (+Y): Profil zeigt nach +Y
		Instances->AddInstance(FTransform(FRotator::ZeroRotator, FVector(X, CurbOffset, 0.f)));
		// Linke Seite (-Y): um 180 Grad gedreht, Stueck laeuft von X+Laenge zurueck nach X
		Instances->AddInstance(FTransform(FRotator(0.f, 180.f, 0.f), FVector(X + PieceLength, -CurbOffset, 0.f)));
	}
}

void AVBStreetBuilder::BuildProps(const FVBStreetPropRule& Rule, UInstancedStaticMeshComponent* Instances, FRandomStream& Stream) const
{
	const float Step = FMath::Max(Rule.Spacing, 50.f);
	for (float X = Rule.StartOffset; X <= Length; X += Step)
	{
		for (const float Side : { 1.f, -1.f })
		{
			if ((Side > 0.f && !Rule.bRightSide) || (Side < 0.f && !Rule.bLeftSide))
			{
				continue;
			}
			if (Stream.FRand() > Rule.Probability)
			{
				continue;
			}

			const float Jitter = Rule.PositionJitter > 0.f ? Stream.FRandRange(-Rule.PositionJitter, Rule.PositionJitter) : 0.f;
			const float PosX = FMath::Clamp(X + Jitter, 0.f, Length);
			const float PosY = Side * Rule.LateralOffset;

			FTransform Transform;
			if (Rule.bOnRoadSurface)
			{
				// Neigung der gewoelbten Fahrbahn uebernehmen: Normale = (0, -dz/dy, 1)
				const float Slope = (FMath::Abs(PosY) <= AsphaltHalfWidth) ? -Side * CrownHeight / FMath::Max(AsphaltHalfWidth, 1.f) : 0.f;
				const FVector Normal = FVector(0.f, -Slope, 1.f).GetSafeNormal();
				const FRotator Yaw(0.f, Rule.YawOffset + Stream.FRandRange(0.f, 360.f), 0.f);
				const FRotator Rotation = FRotationMatrix::MakeFromZX(Normal, Yaw.Vector()).Rotator();
				Transform = FTransform(Rotation, FVector(PosX, PosY, GetRoadSurfaceHeight(PosY)));
			}
			else
			{
				// Vorderseite (+X des Meshes) zur Fahrbahn drehen
				const float Yaw = (Side > 0.f ? -90.f : 90.f) + Rule.YawOffset;
				Transform = FTransform(FRotator(0.f, Yaw, 0.f), FVector(PosX, PosY, Rule.Height));
			}
			Instances->AddInstance(Transform);
		}
	}
}
