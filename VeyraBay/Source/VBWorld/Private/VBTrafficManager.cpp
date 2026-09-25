#include "VBTrafficManager.h"

#include "VBLog.h"
#include "VBStats.h"
#include "VBStreetBuilder.h"
#include "VBTimeOfDaySubsystem.h"
#include "VBTrafficLight.h"
#include "VBWeatherSubsystem.h"
#include "DrawDebugHelpers.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"

DECLARE_CYCLE_STAT(TEXT("Verkehr (Tick)"), STAT_VBTraffic, STATGROUP_VeyraBay);
DECLARE_DWORD_COUNTER_STAT(TEXT("Verkehr: Fahrzeuge"), STAT_VBTrafficVehicles, STATGROUP_VeyraBay);
DECLARE_DWORD_COUNTER_STAT(TEXT("Verkehr: geparkt"), STAT_VBTrafficParked, STATGROUP_VeyraBay);

namespace VBTraffic
{
	// Intelligent Driver Model (cm, s)
	static constexpr float MaxAccel = 160.f;        // 1.6 m/s^2
	static constexpr float ComfortDecel = 220.f;    // 2.2 m/s^2
	static constexpr float MaxDecel = 900.f;        // Notbremsung
	static constexpr float MinGap = 250.f;          // Abstand im Stand
	static constexpr float TimeHeadway = 1.4f;
	static constexpr float LookAhead = 6000.f;
	static constexpr float JunctionCluster = 2300.f;
	static constexpr int32 ArcSamples = 32;

	static FVector RightOf(const FVector& Dir)
	{
		return FVector(-Dir.Y, Dir.X, 0.f);
	}

	static FIntPoint CellOf(const FVector& Point, float CellSize)
	{
		return FIntPoint(FMath::FloorToInt(Point.X / CellSize), FMath::FloorToInt(Point.Y / CellSize));
	}
}

// ---------------------------------------------------------------------------------------------
// FVBLane
// ---------------------------------------------------------------------------------------------
FVector FVBLane::Eval(float T) const
{
	const float U = 1.f - T;
	return P0 * (U * U * U) + P1 * (3.f * U * U * T) + P2 * (3.f * U * T * T) + P3 * (T * T * T);
}

FVector FVBLane::Tangent(float T) const
{
	const float U = 1.f - T;
	const FVector D = (P1 - P0) * (3.f * U * U) + (P2 - P1) * (6.f * U * T) + (P3 - P2) * (3.f * T * T);
	return D.GetSafeNormal2D();
}

void FVBLane::Build()
{
	ArcTable.SetNum(VBTraffic::ArcSamples + 1);
	ArcTable[0] = 0.f;
	FVector Previous = P0;
	for (int32 Index = 1; Index <= VBTraffic::ArcSamples; ++Index)
	{
		const FVector Point = Eval(static_cast<float>(Index) / VBTraffic::ArcSamples);
		ArcTable[Index] = ArcTable[Index - 1] + FVector::Dist2D(Previous, Point);
		Previous = Point;
	}
	Length = FMath::Max(ArcTable.Last(), 1.f);
}

float FVBLane::ParamAtDistance(float S) const
{
	if (S <= 0.f || ArcTable.Num() < 2)
	{
		return 0.f;
	}
	if (S >= Length)
	{
		return 1.f;
	}
	int32 Low = 0;
	int32 High = ArcTable.Num() - 1;
	while (High - Low > 1)
	{
		const int32 Mid = (Low + High) / 2;
		(ArcTable[Mid] < S ? Low : High) = Mid;
	}
	const float Span = FMath::Max(ArcTable[High] - ArcTable[Low], 1e-3f);
	return (Low + (S - ArcTable[Low]) / Span) / VBTraffic::ArcSamples;
}

// ---------------------------------------------------------------------------------------------
// Aufbau
// ---------------------------------------------------------------------------------------------
AVBTrafficManager::AVBTrafficManager()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;

#if WITH_EDITORONLY_DATA
	bIsSpatiallyLoaded = false;     // verwaltet die ganze Stadt
#endif

	USceneComponent* SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = SceneRoot;

	// Typische Verteilung: Grau/Silber, Schwarz, Weiss dominieren, wenige Farben
	PaintPalette = {
		FLinearColor(0.02f, 0.02f, 0.022f), FLinearColor(0.03f, 0.03f, 0.035f), FLinearColor(0.75f, 0.75f, 0.74f),
		FLinearColor(0.8f, 0.8f, 0.78f), FLinearColor(0.32f, 0.33f, 0.34f), FLinearColor(0.12f, 0.13f, 0.14f),
		FLinearColor(0.45f, 0.46f, 0.47f), FLinearColor(0.02f, 0.05f, 0.14f), FLinearColor(0.35f, 0.02f, 0.02f),
		FLinearColor(0.05f, 0.1f, 0.06f), FLinearColor(0.3f, 0.24f, 0.16f), FLinearColor(0.06f, 0.16f, 0.3f)
	};

	FRichCurve* Curve = DensityByHour.GetRichCurve();
	const float Keys[][2] = { {0.f, 0.15f}, {4.f, 0.08f}, {6.f, 0.45f}, {7.5f, 1.f}, {9.f, 0.75f}, {12.f, 0.7f},
		{16.5f, 0.85f}, {17.5f, 1.f}, {19.f, 0.7f}, {21.f, 0.45f}, {23.f, 0.25f}, {24.f, 0.15f} };
	for (const auto& Key : Keys)
	{
		Curve->AddKey(Key[0], Key[1]);
	}
}

void AVBTrafficManager::BakeNetwork()
{
	TArray<FVBLane> NewLanes;
	TArray<FVBParkingSlot> NewSlots;
	float NewLength = 0.f;
	BuildGraph(NewLanes, NewSlots, NewLength);
	Modify();
	Lanes = MoveTemp(NewLanes);
	ParkingSlots = MoveTemp(NewSlots);
	TotalLaneLength = NewLength;
}

void AVBTrafficManager::BeginPlay()
{
	Super::BeginPlay();
	Random.Initialize(Seed);

	if (Lanes.Num() == 0)
	{
		// Nicht gebacken (kleine Testkarte): aus den geladenen Strassen erzeugen
		BuildGraph(Lanes, ParkingSlots, TotalLaneLength);
	}
	for (FVBLane& Lane : Lanes)
	{
		if (Lane.ArcTable.Num() < 2)
		{
			Lane.Build();
		}
	}
	AgentsOnLane.SetNum(Lanes.Num());
	JunctionIncoming.Reset();
	for (int32 Index = 0; Index < Lanes.Num(); ++Index)
	{
		const FVBLane& Lane = Lanes[Index];
		if (!Lane.bConnector && Lane.Junction != INDEX_NONE)
		{
			if (JunctionIncoming.Num() <= Lane.Junction)
			{
				JunctionIncoming.SetNum(Lane.Junction + 1);
			}
			JunctionIncoming[Lane.Junction].Add(Index);
		}
	}

	RefreshObstacleActors();
	FVector Direction;
	GetPlayerView(PlayerLocation, Direction);
	UpdateNearLanes();
	if (bSpawnParkedCars)
	{
		UpdateParkedCars();
	}
	if (bEnableTraffic && VehicleTypes.Num() > 0)
	{
		UpdateDensity(0.f);
	}
}

void AVBTrafficManager::BuildGraph(TArray<FVBLane>& OutLanes, TArray<FVBParkingSlot>& OutSlots, float& OutLength)
{
	OutLanes.Reset();
	OutSlots.Reset();
	OutLength = 0.f;
	FRandomStream Stream(Seed);

	TArray<AVBStreetBuilder*> Streets;
	for (TActorIterator<AVBStreetBuilder> It(GetWorld()); It; ++It)
	{
		Streets.Add(*It);
	}

	// --- Strassenspuren: vorwaerts (+X) rechts, rueckwaerts links; Parkplaetze --------------------
	for (int32 StreetIndex = 0; StreetIndex < Streets.Num(); ++StreetIndex)
	{
		const AVBStreetBuilder* Street = Streets[StreetIndex];
		const FTransform Transform = Street->GetActorTransform();
		const float Length = Street->Length;
		for (int32 Direction = 0; Direction < 2; ++Direction)
		{
			const float Y = Direction == 0 ? LaneOffset : -LaneOffset;
			const float X0 = Direction == 0 ? 0.f : Length;
			const float X1 = Direction == 0 ? Length : 0.f;
			FVBLane Lane;
			Lane.P0 = Transform.TransformPosition(FVector(X0, Y, RoadHeight));
			Lane.P3 = Transform.TransformPosition(FVector(X1, Y, RoadHeight));
			Lane.P1 = FMath::Lerp(Lane.P0, Lane.P3, 1.f / 3.f);
			Lane.P2 = FMath::Lerp(Lane.P0, Lane.P3, 2.f / 3.f);
			Lane.Street = StreetIndex;
			Lane.SpeedLimit = SpeedLimitKmh / 3.6f * 100.f;
			Lane.Build();
			OutLength += Lane.Length;
			OutLanes.Add(MoveTemp(Lane));
		}

		// Parkplaetze beidseitig, 15 m Abstand zu den Strassenenden
		for (int32 Side = -1; Side <= 1; Side += 2)
		{
			float X = 1500.f + Stream.FRandRange(0.f, 300.f);
			while (X < Length - 1500.f)
			{
				const int32 TypeIndex = PickType(true, Stream);
				const float Slot = VehicleTypes.IsValidIndex(TypeIndex) ? VehicleTypes[TypeIndex].Length + 120.f : 600.f;
				if (TypeIndex != INDEX_NONE && Stream.FRand() < ParkingOccupancy)
				{
					const float Y = Side * ParkingOffset + Stream.FRandRange(-10.f, 10.f);
					FVBParkingSlot Parking;
					Parking.Location = Transform.TransformPosition(FVector(X + Slot * 0.5f, Y, Street->GetRoadSurfaceHeight(Y)));
					// In Fahrtrichtung der jeweiligen Seite (Rechtsverkehr)
					Parking.Yaw = Transform.Rotator().Yaw + (Side > 0 ? 0.f : 180.f) + Stream.FRandRange(-1.5f, 1.5f);
					Parking.Type = TypeIndex;
					Parking.Paint = (VehicleTypes[TypeIndex].bFixedPaint || PaintPalette.Num() == 0) ? INDEX_NONE
						: Stream.RandRange(0, PaintPalette.Num() - 1);
					OutSlots.Add(Parking);
				}
				X += Slot + Stream.FRandRange(20.f, 180.f);
			}
		}
	}
	const int32 StreetLaneCount = OutLanes.Num();

	// --- Kreuzungen: Spurenden/-anfaenge, die nah beieinander liegen (Raster fuer schnelle Suche) -----
	const float CellSize = VBTraffic::JunctionCluster;
	TArray<FVector> JunctionCenters;
	TMap<FIntPoint, TArray<int32>> JunctionGrid;
	auto FindOrAddJunction = [&](const FVector& Center)
	{
		const FIntPoint Cell = VBTraffic::CellOf(Center, CellSize);
		for (int32 DX = -1; DX <= 1; ++DX)
		{
			for (int32 DY = -1; DY <= 1; ++DY)
			{
				if (const TArray<int32>* Bucket = JunctionGrid.Find(Cell + FIntPoint(DX, DY)))
				{
					for (int32 Index : *Bucket)
					{
						if (FVector::Dist2D(JunctionCenters[Index], Center) < CellSize * 0.5f)
						{
							return Index;
						}
					}
				}
			}
		}
		const int32 NewIndex = JunctionCenters.Add(Center);
		JunctionGrid.FindOrAdd(Cell).Add(NewIndex);
		return NewIndex;
	};

	TArray<int32> StartJunction;
	StartJunction.Init(INDEX_NONE, StreetLaneCount);
	for (int32 Index = 0; Index < StreetLaneCount; ++Index)
	{
		FVBLane& Lane = OutLanes[Index];
		const FVector Dir = (Lane.P3 - Lane.P0).GetSafeNormal2D();
		Lane.Junction = FindOrAddJunction(Lane.P3 + Dir * StopLineOffset - VBTraffic::RightOf(Dir) * LaneOffset);
		StartJunction[Index] = FindOrAddJunction(Lane.P0 - Dir * StopLineOffset - VBTraffic::RightOf(Dir) * LaneOffset);
	}

	TArray<TArray<int32>> Incoming, Outgoing;
	Incoming.SetNum(JunctionCenters.Num());
	Outgoing.SetNum(JunctionCenters.Num());
	for (int32 Index = 0; Index < StreetLaneCount; ++Index)
	{
		Incoming[OutLanes[Index].Junction].Add(Index);
		Outgoing[StartJunction[Index]].Add(Index);
	}

	// --- Abbiegekurven je Kreuzung -----------------------------------------------------------------
	TArray<TArray<int32>> JunctionCurves;
	JunctionCurves.SetNum(JunctionCenters.Num());
	for (int32 Junction = 0; Junction < JunctionCenters.Num(); ++Junction)
	{
		for (int32 From : Incoming[Junction])
		{
			for (int32 To : Outgoing[Junction])
			{
				const FVBLane& A = OutLanes[From];
				const FVBLane& B = OutLanes[To];
				if (A.Street == B.Street || FVector::Dist2D(A.P3, B.P0) > VBTraffic::JunctionCluster)
				{
					continue;
				}
				const FVector DA = (A.P3 - A.P0).GetSafeNormal2D();
				const FVector DB = (B.P3 - B.P0).GetSafeNormal2D();
				const float Dot = FVector::DotProduct(DA, DB);
				if (Dot < -0.7f)
				{
					continue;   // keine Wendemanoever
				}
				const float Cross = DA.X * DB.Y - DA.Y * DB.X;

				FVBLane Curve;
				Curve.bConnector = true;
				Curve.Source = From;
				Curve.Junction = Junction;
				Curve.P0 = A.P3;
				Curve.P3 = B.P0;
				if (Dot > 0.7f)
				{
					Curve.Turn = 0;
					Curve.P1 = FMath::Lerp(Curve.P0, Curve.P3, 1.f / 3.f);
					Curve.P2 = FMath::Lerp(Curve.P0, Curve.P3, 2.f / 3.f);
					Curve.SpeedLimit = 1100.f;
				}
				else
				{
					Curve.Turn = Cross > 0.f ? 1 : -1;
					const FVector Delta = Curve.P3 - Curve.P0;
					const float Along = FMath::Max(static_cast<float>(FVector::DotProduct(Delta, DA)), 100.f);
					const float Across = FMath::Max(static_cast<float>(FVector::DotProduct(Delta, DB)), 100.f);
					Curve.P1 = Curve.P0 + DA * Along * 0.55f;
					Curve.P2 = Curve.P3 - DB * Across * 0.55f;
					Curve.SpeedLimit = Curve.Turn > 0 ? 560.f : 720.f;
				}
				Curve.Next.Add(To);
				Curve.Build();
				const int32 CurveIndex = OutLanes.Add(MoveTemp(Curve));
				OutLanes[From].Next.Add(CurveIndex);
				JunctionCurves[Junction].Add(CurveIndex);
			}
		}
	}

	// --- Konflikte und Gegenverkehr (nur innerhalb einer Kreuzung) ---------------------------------------
	for (int32 Junction = 0; Junction < JunctionCenters.Num(); ++Junction)
	{
		const TArray<int32>& Curves = JunctionCurves[Junction];
		TArray<TArray<FVector>> Samples;
		Samples.SetNum(Curves.Num());
		for (int32 C = 0; C < Curves.Num(); ++C)
		{
			for (int32 Step = 0; Step <= 16; ++Step)
			{
				Samples[C].Add(OutLanes[Curves[C]].Eval(Step / 16.f));
			}
		}
		for (int32 C = 0; C < Curves.Num(); ++C)
		{
			FVBLane& Curve = OutLanes[Curves[C]];
			for (int32 D = 0; D < Curves.Num(); ++D)
			{
				if (C == D || OutLanes[Curves[D]].Source == Curve.Source)
				{
					continue;
				}
				bool bConflict = false;
				for (int32 SA = 0; SA < Samples[C].Num() && !bConflict; ++SA)
				{
					for (int32 SB = 0; SB < Samples[D].Num(); ++SB)
					{
						if (FVector::DistSquared2D(Samples[C][SA], Samples[D][SB]) < FMath::Square(220.f))
						{
							bConflict = true;
							break;
						}
					}
				}
				if (bConflict)
				{
					Curve.Conflicts.Add(Curves[D]);
				}
			}
			if (Curve.Turn < 0)
			{
				const FVector DA = (OutLanes[Curve.Source].P3 - OutLanes[Curve.Source].P0).GetSafeNormal2D();
				for (int32 Candidate : Incoming[Junction])
				{
					const FVBLane& Other = OutLanes[Candidate];
					if (FVector::DotProduct((Other.P3 - Other.P0).GetSafeNormal2D(), DA) < -0.9f)
					{
						Curve.Opposing = Candidate;
						break;
					}
				}
			}
		}
	}

	// --- Ampeln: Phasenplan der Ampel, die der Zufahrt gegenuebersteht ---------------------------------
	TMap<FIntPoint, TArray<AVBTrafficLight*>> SignalGrid;
	for (TActorIterator<AVBTrafficLight> It(GetWorld()); It; ++It)
	{
		SignalGrid.FindOrAdd(VBTraffic::CellOf(It->GetActorLocation(), CellSize)).Add(*It);
	}
	int32 SignalCount = 0;
	for (int32 Index = 0; Index < StreetLaneCount; ++Index)
	{
		FVBLane& Lane = OutLanes[Index];
		if (Lane.Next.Num() == 0)
		{
			continue;
		}
		const FVector Dir = (Lane.P3 - Lane.P0).GetSafeNormal2D();
		const FIntPoint Cell = VBTraffic::CellOf(Lane.P3, CellSize);
		float Best = 1500.f;
		const AVBTrafficLight* BestSignal = nullptr;
		for (int32 DX = -1; DX <= 1; ++DX)
		{
			for (int32 DY = -1; DY <= 1; ++DY)
			{
				if (const TArray<AVBTrafficLight*>* Bucket = SignalGrid.Find(Cell + FIntPoint(DX, DY)))
				{
					for (const AVBTrafficLight* Signal : *Bucket)
					{
						const float Facing = FVector::DotProduct(Signal->GetActorForwardVector().GetSafeNormal2D(), Dir);
						const float Distance = FVector::Dist2D(Signal->GetActorLocation(), Lane.P3);
						if (Facing < -0.8f && Distance < Best)
						{
							Best = Distance;
							BestSignal = Signal;
						}
					}
				}
			}
		}
		if (BestSignal)
		{
			Lane.bHasSignal = true;
			Lane.Signal = BestSignal->GetTiming();
			++SignalCount;
		}
	}

	UE_LOG(LogVB, Log, TEXT("Verkehr: %d Strassen, %d Spuren, %d Abbiegekurven, %d Kreuzungen, %d Ampel-Zufahrten, %d Parkplaetze, %.1f km Spur"),
		Streets.Num(), StreetLaneCount, OutLanes.Num() - StreetLaneCount, JunctionCenters.Num(), SignalCount, OutSlots.Num(),
		OutLength / 100000.f);
}

// ---------------------------------------------------------------------------------------------
// Auswahl
// ---------------------------------------------------------------------------------------------
int32 AVBTrafficManager::PickType(bool bParked, FRandomStream& Stream) const
{
	float Total = 0.f;
	for (const FVBTrafficVehicleType& Type : VehicleTypes)
	{
		Total += (bParked ? Type.ParkedWeight : Type.Weight) * (Type.BodyMesh ? 1.f : 0.f);
	}
	if (Total <= 0.f)
	{
		return INDEX_NONE;
	}
	float Pick = Stream.FRand() * Total;
	for (int32 Index = 0; Index < VehicleTypes.Num(); ++Index)
	{
		const FVBTrafficVehicleType& Type = VehicleTypes[Index];
		Pick -= (bParked ? Type.ParkedWeight : Type.Weight) * (Type.BodyMesh ? 1.f : 0.f);
		if (Pick <= 0.f)
		{
			return Index;
		}
	}
	return VehicleTypes.Num() - 1;
}

FLinearColor AVBTrafficManager::PaintFor(const FVBTrafficVehicleType& Type, int32 PaintIndex) const
{
	if (Type.bFixedPaint || !PaintPalette.IsValidIndex(PaintIndex))
	{
		return Type.Paint;
	}
	return PaintPalette[PaintIndex];
}

int32 AVBTrafficManager::PickNext(int32 LaneIndex)
{
	const FVBLane& Lane = Lanes[LaneIndex];
	if (Lane.Next.Num() == 0)
	{
		return INDEX_NONE;
	}
	float Total = 0.f;
	for (int32 Next : Lane.Next)
	{
		Total += Lanes[Next].Turn == 0 ? 2.f : 1.f;
	}
	float Pick = Random.FRand() * Total;
	for (int32 Next : Lane.Next)
	{
		Pick -= Lanes[Next].Turn == 0 ? 2.f : 1.f;
		if (Pick <= 0.f)
		{
			return Next;
		}
	}
	return Lane.Next.Last();
}

void AVBTrafficManager::EnsureRoute(FVBTrafficAgent& Agent)
{
	while (Agent.Route.Num() < 3)
	{
		const int32 From = Agent.Route.Num() > 0 ? Agent.Route.Last() : Agent.Lane;
		const int32 Next = PickNext(From);
		if (Next == INDEX_NONE)
		{
			break;
		}
		Agent.Route.Add(Next);
	}
}

// ---------------------------------------------------------------------------------------------
// Spieler, Blase, parkende Autos
// ---------------------------------------------------------------------------------------------
bool AVBTrafficManager::GetPlayerView(FVector& OutLocation, FVector& OutDirection) const
{
	const APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (!PC)
	{
		return false;
	}
	FRotator Rotation;
	PC->GetPlayerViewPoint(OutLocation, Rotation);
	OutDirection = Rotation.Vector();
	return true;
}

float AVBTrafficManager::DistanceToPlayer(const FVector& Location, bool* bOutInView) const
{
	FVector ViewLocation, ViewDirection;
	if (!GetPlayerView(ViewLocation, ViewDirection))
	{
		if (bOutInView)
		{
			*bOutInView = false;
		}
		return TNumericLimits<float>::Max();
	}
	const FVector Delta = Location - ViewLocation;
	if (bOutInView)
	{
		*bOutInView = FVector::DotProduct(Delta.GetSafeNormal(), ViewDirection) > 0.35f;
	}
	return Delta.Size();
}

void AVBTrafficManager::UpdateNearLanes()
{
	NearLanes.Reset();
	NearLaneLength = 0.f;
	const float RadiusSq = FMath::Square(SimulationRadius);
	for (int32 Index = 0; Index < Lanes.Num(); ++Index)
	{
		const FVBLane& Lane = Lanes[Index];
		if (Lane.bConnector)
		{
			continue;
		}
		const FVector Mid = (Lane.P0 + Lane.P3) * 0.5f;
		if (FVector::DistSquared2D(Mid, PlayerLocation) < RadiusSq)
		{
			NearLanes.Add(Index);
			NearLaneLength += Lane.Length;
		}
	}
}

void AVBTrafficManager::UpdateParkedCars()
{
	if (!bSpawnParkedCars || VehicleTypes.Num() == 0)
	{
		return;
	}
	const float SpawnSq = FMath::Square(ParkedRadius);
	const float KeepSq = FMath::Square(ParkedRadius + 5000.f);

	// Entfernen, was aus dem Radius gefallen ist
	for (auto It = ParkedActors.CreateIterator(); It; ++It)
	{
		AVBTrafficVehicle* Car = It->Value;
		if (!IsValid(Car) || FVector::DistSquared2D(Car->GetActorLocation(), PlayerLocation) > KeepSq)
		{
			if (IsValid(Car))
			{
				Car->Destroy();
			}
			It.RemoveCurrent();
		}
	}

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Params.Owner = this;
	for (int32 Index = 0; Index < ParkingSlots.Num(); ++Index)
	{
		const FVBParkingSlot& Slot = ParkingSlots[Index];
		if (!VehicleTypes.IsValidIndex(Slot.Type) || ParkedActors.Contains(Index)
			|| FVector::DistSquared2D(Slot.Location, PlayerLocation) > SpawnSq)
		{
			continue;
		}
		// Platz neben fahrbaren Autos (vom Setup-Skript geparkt) freilassen
		const bool bBlocked = ObstacleActors.ContainsByPredicate([&Slot](const TWeakObjectPtr<AActor>& Actor)
		{
			return Actor.IsValid() && FVector::Dist2D(Actor->GetActorLocation(), Slot.Location) < 700.f;
		});
		if (bBlocked)
		{
			continue;
		}
		const FVBTrafficVehicleType& Type = VehicleTypes[Slot.Type];
		if (AVBTrafficVehicle* Car = GetWorld()->SpawnActor<AVBTrafficVehicle>(Slot.Location, FRotator(0.f, Slot.Yaw, 0.f), Params))
		{
			Car->Configure(Type, PaintFor(Type, Slot.Paint));
			Car->UpdateVisuals(0.f, 0.f, 0.f, false, false, 0);
			ParkedActors.Add(Index, Car);
		}
	}
}

// ---------------------------------------------------------------------------------------------
// Dichte, Spawnen
// ---------------------------------------------------------------------------------------------
float AVBTrafficManager::WeatherFactor() const
{
	const UVBWeatherSubsystem* Weather = GetWorld()->GetSubsystem<UVBWeatherSubsystem>();
	return Weather ? Weather->GetRoadGripMultiplier() : 1.f;
}

void AVBTrafficManager::UpdateDensity(float DeltaSeconds)
{
	const UVBTimeOfDaySubsystem* Time = GetWorld()->GetSubsystem<UVBTimeOfDaySubsystem>();
	const float Hour = Time ? Time->GetTimeOfDay() : 12.f;
	const float Density = FMath::Clamp(DensityByHour.GetRichCurveConst()->Eval(Hour), 0.f, 1.f);
	const float Weather = FMath::Lerp(0.8f, 1.f, WeatherFactor());
	const int32 Target = FMath::Min(MaxVehicles, FMath::RoundToInt(NearLaneLength / 100000.f * VehiclesPerKm * Density * Weather));

	if (DeltaSeconds <= 0.f)
	{
		// Start: direkt auffuellen (Spieler sieht noch nichts)
		for (int32 Attempt = 0; Attempt < Target * 4 && Agents.Num() < Target; ++Attempt)
		{
			TrySpawnAgent(false);
		}
		return;
	}

	SpawnTimer -= DeltaSeconds;
	if (SpawnTimer > 0.f)
	{
		return;
	}
	SpawnTimer = 0.25f;
	if (Agents.Num() < Target)
	{
		TrySpawnAgent(true);
	}
	else if (Agents.Num() > Target + 2)
	{
		// Ueberzaehlige ausserhalb der Sicht entfernen
		for (int32 Index = 0; Index < Agents.Num(); ++Index)
		{
			bool bInView = false;
			const float Distance = DistanceToPlayer(Agents[Index].Actor->GetActorLocation(), &bInView);
			if (Distance > MinSpawnDistance && !bInView)
			{
				RemoveAgent(Index);
				break;
			}
		}
	}
}

bool AVBTrafficManager::TrySpawnAgent(bool bAvoidPlayer)
{
	if (NearLaneLength <= 0.f || NearLanes.Num() == 0)
	{
		return false;
	}
	const int32 TypeIndex = PickType(false, Random);
	if (TypeIndex == INDEX_NONE)
	{
		return false;
	}
	const FVBTrafficVehicleType& Type = VehicleTypes[TypeIndex];

	// Spur in der Blase nach Laenge gewichtet waehlen
	float Pick = Random.FRand() * NearLaneLength;
	int32 LaneIndex = NearLanes.Last();
	for (int32 Candidate : NearLanes)
	{
		Pick -= Lanes[Candidate].Length;
		if (Pick <= 0.f)
		{
			LaneIndex = Candidate;
			break;
		}
	}
	const FVBLane& Lane = Lanes[LaneIndex];
	if (Lane.Length < Type.Length + 1500.f)
	{
		return false;
	}
	const float S = Random.FRandRange(Type.Length, Lane.Length - 1200.f);
	for (const FVBTrafficAgent& Other : Agents)
	{
		if (Other.Lane == LaneIndex && FMath::Abs(Other.S - S) < 1500.f)
		{
			return false;
		}
	}
	const FVector Location = Lane.Eval(Lane.ParamAtDistance(S));
	bool bInView = false;
	const float PlayerDistance = DistanceToPlayer(Location, &bInView);
	if (PlayerDistance > SimulationRadius || PlayerDistance < (bAvoidPlayer ? MinSpawnDistance : 2500.f)
		|| (bAvoidPlayer && bInView && PlayerDistance < SimulationRadius * 0.7f))
	{
		return false;
	}

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Params.Owner = this;
	const FRotator Rotation = Lane.Tangent(Lane.ParamAtDistance(S)).Rotation();
	AVBTrafficVehicle* Car = GetWorld()->SpawnActor<AVBTrafficVehicle>(Location, Rotation, Params);
	if (!Car)
	{
		return false;
	}
	const int32 PaintIndex = PaintPalette.Num() > 0 ? Random.RandRange(0, PaintPalette.Num() - 1) : INDEX_NONE;
	Car->Configure(Type, PaintFor(Type, PaintIndex));
	SpawnedActors.Add(Car);

	FVBTrafficAgent Agent;
	Agent.Actor = Car;
	Agent.Type = TypeIndex;
	Agent.Lane = LaneIndex;
	Agent.S = S;
	Agent.DesiredFactor = Random.FRandRange(0.88f, 1.08f);
	Agent.V = Lane.SpeedLimit * 0.6f;
	Agent.Yaw = Rotation.Yaw;
	EnsureRoute(Agent);
	Agents.Add(MoveTemp(Agent));
	return true;
}

void AVBTrafficManager::RemoveAgent(int32 Index)
{
	if (AVBTrafficVehicle* Car = Agents[Index].Actor)
	{
		SpawnedActors.Remove(Car);
		Car->Destroy();
	}
	Agents.RemoveAtSwap(Index);
}

void AVBTrafficManager::AddTransientObstacle(const FVector& Location, float Radius)
{
	TransientObstacles.Add(FVector4(Location.X, Location.Y, Location.Z, Radius));
}

void AVBTrafficManager::RefreshObstacleActors()
{
	// Fahrbare Autos (World Partition laedt sie nach) - Pawns sind wenige, daher billig
	ObstacleActors.Reset();
	for (TActorIterator<APawn> It(GetWorld()); It; ++It)
	{
		if (It->ActorHasTag(TEXT("VB_Vehicle")))
		{
			ObstacleActors.Add(*It);
		}
	}
}

void AVBTrafficManager::UpdateObstacles()
{
	// Spieler zu Fuss (kleiner Radius), fahrbare Autos (negativer Radius = Fahrzeug, laengs 2.5-fach), Fussgaenger
	FrameObstacles = MoveTemp(TransientObstacles);
	TransientObstacles.Reset();
	const APlayerController* PC = GetWorld()->GetFirstPlayerController();
	const APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	if (Pawn && !Pawn->ActorHasTag(TEXT("VB_Vehicle")))
	{
		const FVector Location = Pawn->GetActorLocation();
		FrameObstacles.Add(FVector4(Location.X, Location.Y, Location.Z, 45.f));
	}
	for (const TWeakObjectPtr<AActor>& Actor : ObstacleActors)
	{
		if (const AActor* Vehicle = Actor.Get())
		{
			const FVector Location = Vehicle->GetActorLocation();
			FrameObstacles.Add(FVector4(Location.X, Location.Y, Location.Z, -95.f));
		}
	}
}

// ---------------------------------------------------------------------------------------------
// Simulation
// ---------------------------------------------------------------------------------------------
void AVBTrafficManager::Tick(float DeltaSeconds)
{
	SCOPE_CYCLE_COUNTER(STAT_VBTraffic);
	Super::Tick(DeltaSeconds);
	SET_DWORD_STAT(STAT_VBTrafficVehicles, Agents.Num());
	SET_DWORD_STAT(STAT_VBTrafficParked, ParkedActors.Num());
	if (Lanes.Num() == 0)
	{
		return;
	}
	FVector ViewDirection;
	if (!GetPlayerView(PlayerLocation, ViewDirection))
	{
		return;
	}

	NearTimer -= DeltaSeconds;
	if (NearTimer <= 0.f)
	{
		NearTimer = 1.f;
		UpdateNearLanes();
	}
	ParkedTimer -= DeltaSeconds;
	if (ParkedTimer <= 0.f)
	{
		ParkedTimer = 1.f;
		UpdateParkedCars();
	}
	ObstacleRefreshTimer -= DeltaSeconds;
	if (ObstacleRefreshTimer <= 0.f)
	{
		ObstacleRefreshTimer = 2.f;
		RefreshObstacleActors();
	}
	if (!bEnableTraffic || VehicleTypes.Num() == 0)
	{
		return;
	}
	const float Step = FMath::Min(DeltaSeconds, 0.1f);

	UpdateObstacles();
	for (TArray<int32>& Bucket : AgentsOnLane)
	{
		Bucket.Reset();
	}
	for (int32 Index = 0; Index < Agents.Num(); ++Index)
	{
		AgentsOnLane[Agents[Index].Lane].Add(Index);
	}

	// Entfernen erst nach dem Durchlauf (AgentsOnLane haelt Indizes)
	TArray<int32> ToRemove;
	const float DespawnDistance = SimulationRadius + 5000.f;
	for (int32 Index = 0; Index < Agents.Num(); ++Index)
	{
		FVBTrafficAgent& Agent = Agents[Index];
		if (!IsValid(Agent.Actor))
		{
			ToRemove.Add(Index);
			continue;
		}
		StepAgent(Agent, Index, Step);
		// Sackgasse, ausserhalb der Blase oder lange festgefahren (ausser Sicht)
		bool bInView = false;
		const float Distance = DistanceToPlayer(Agent.Actor->GetActorLocation(), &bInView);
		const bool bDeadEnd = Agent.Route.Num() == 0 && Agent.S > Lanes[Agent.Lane].Length - VehicleTypes[Agent.Type].Length;
		if (bDeadEnd || Distance > DespawnDistance || (Agent.WaitTime > 60.f && !bInView && Distance > 4000.f))
		{
			ToRemove.Add(Index);
		}
	}
	for (int32 Position = ToRemove.Num() - 1; Position >= 0; --Position)
	{
		const int32 Index = ToRemove[Position];
		if (IsValid(Agents[Index].Actor))
		{
			RemoveAgent(Index);
		}
		else
		{
			Agents.RemoveAtSwap(Index);
		}
	}

	UpdateDensity(DeltaSeconds);
	if (bDrawDebug)
	{
		DrawDebug();
	}
}

float AVBTrafficManager::DesiredSpeed(const FVBTrafficAgent& Agent) const
{
	const FVBLane& Lane = Lanes[Agent.Lane];
	float Speed = Lane.SpeedLimit * Agent.DesiredFactor * FMath::Lerp(0.75f, 1.f, WeatherFactor());
	// Vor einer langsameren Kurve rechtzeitig verzoegern
	float Distance = Lane.Length - Agent.S;
	for (int32 RouteIndex = 0; RouteIndex < Agent.Route.Num() && Distance < VBTraffic::LookAhead; ++RouteIndex)
	{
		const FVBLane& Next = Lanes[Agent.Route[RouteIndex]];
		const float Allowed = FMath::Sqrt(FMath::Square(Next.SpeedLimit * Agent.DesiredFactor) + 2.f * VBTraffic::ComfortDecel * FMath::Max(Distance, 0.f));
		Speed = FMath::Min(Speed, Allowed);
		Distance += Next.Length;
	}
	return FMath::Max(Speed, 100.f);
}

float AVBTrafficManager::LeaderGap(const FVBTrafficAgent& Agent, int32 AgentIndex, float& OutLeaderSpeed) const
{
	const float HalfLength = VehicleTypes[Agent.Type].Length * 0.5f;
	OutLeaderSpeed = 0.f;

	// Gleicher Fahrweg
	float Best = TNumericLimits<float>::Max();
	for (int32 OtherIndex : AgentsOnLane[Agent.Lane])
	{
		const FVBTrafficAgent& Other = Agents[OtherIndex];
		if (OtherIndex == AgentIndex || Other.S <= Agent.S)
		{
			continue;
		}
		const float Gap = Other.S - Agent.S - HalfLength - VehicleTypes[Other.Type].Length * 0.5f;
		if (Gap < Best)
		{
			Best = Gap;
			OutLeaderSpeed = Other.V;
		}
	}
	if (Best < TNumericLimits<float>::Max())
	{
		return Best;
	}

	// Geplante naechste Fahrwege
	float Distance = Lanes[Agent.Lane].Length - Agent.S;
	for (int32 RouteIndex = 0; RouteIndex < Agent.Route.Num() && Distance < VBTraffic::LookAhead; ++RouteIndex)
	{
		const int32 LaneIndex = Agent.Route[RouteIndex];
		for (int32 OtherIndex : AgentsOnLane[LaneIndex])
		{
			const FVBTrafficAgent& Other = Agents[OtherIndex];
			if (OtherIndex == AgentIndex)
			{
				continue;
			}
			const float Gap = Distance + Other.S - HalfLength - VehicleTypes[Other.Type].Length * 0.5f;
			if (Gap < Best)
			{
				Best = Gap;
				OutLeaderSpeed = Other.V;
			}
		}
		if (Best < TNumericLimits<float>::Max())
		{
			return Best;
		}
		Distance += Lanes[LaneIndex].Length;
	}
	return Best;
}

float AVBTrafficManager::ObstacleGap(const FVBTrafficAgent& Agent) const
{
	const FVBTrafficVehicleType& Type = VehicleTypes[Agent.Type];
	const FVector Location = Agent.Actor->GetActorLocation();
	const FVector Forward = FRotator(0.f, Agent.Yaw, 0.f).Vector();
	const FVector Right = VBTraffic::RightOf(Forward);
	float Best = TNumericLimits<float>::Max();
	for (const FVector4& Obstacle : FrameObstacles)
	{
		const FVector Delta = FVector(Obstacle.X, Obstacle.Y, Obstacle.Z) - Location;
		const float Lateral = FMath::Abs(Obstacle.W);
		const float Longitudinal = Obstacle.W < 0.f ? Lateral * 2.5f : Lateral;
		const float X = FVector::DotProduct(Delta, Forward);
		const float Y = FVector::DotProduct(Delta, Right);
		if (X > 0.f && X < VBTraffic::LookAhead && FMath::Abs(Y) < Type.Width * 0.5f + Lateral + 10.f && FMath::Abs(Delta.Z) < 400.f)
		{
			Best = FMath::Min(Best, X - Type.Length * 0.5f - Longitudinal);
		}
	}
	return Best;
}

bool AVBTrafficManager::MayEnterJunction(const FVBTrafficAgent& Agent, int32 AgentIndex, float DistanceToStop) const
{
	if (DistanceToStop <= 0.f || Agent.Route.Num() == 0)
	{
		return true;
	}
	const FVBLane& Lane = Lanes[Agent.Lane];
	const FVBLane& Curve = Lanes[Agent.Route[0]];

	if (Lane.bHasSignal)
	{
		switch (Lane.Signal.StateAt(GetWorld()->GetTimeSeconds()))
		{
		case EVBSignalState::Green:
			break;
		case EVBSignalState::Amber:
			// Nur weiterfahren, wenn ein angenehmes Anhalten nicht mehr moeglich ist
			if (DistanceToStop > Agent.V * Agent.V / (2.f * 350.f))
			{
				return false;
			}
			break;
		default:
			return false;
		}
	}

	// Platz hinter der Kreuzung?
	if (Agent.Route.Num() > 1)
	{
		for (int32 OtherIndex : AgentsOnLane[Agent.Route[1]])
		{
			const FVBTrafficAgent& Other = Agents[OtherIndex];
			if (Other.S < VehicleTypes[Agent.Type].Length + VehicleTypes[Other.Type].Length * 0.5f + 300.f && Other.V < 300.f)
			{
				return false;
			}
		}
	}

	// Konfliktkurven belegt?
	for (int32 Conflict : Curve.Conflicts)
	{
		if (AgentsOnLane[Conflict].Num() > 0)
		{
			return false;
		}
	}

	// Linksabbieger: Gegenverkehr abwarten
	if (Curve.Turn < 0 && Curve.Opposing != INDEX_NONE)
	{
		const FVBLane& Opposing = Lanes[Curve.Opposing];
		for (int32 OtherIndex : AgentsOnLane[Curve.Opposing])
		{
			const FVBTrafficAgent& Other = Agents[OtherIndex];
			const float Remaining = Opposing.Length - Other.S;
			const bool bOtherTurnsLeft = Other.Route.Num() > 0 && Lanes[Other.Route[0]].Turn < 0;
			if (!bOtherTurnsLeft && (Remaining < 1500.f || (Remaining < 4500.f && Other.V > 250.f)))
			{
				return false;
			}
		}
	}

	// Kreuzung ohne Ampel: wer der Haltelinie naeher ist, faehrt zuerst
	if (!Lane.bHasSignal && JunctionIncoming.IsValidIndex(Lane.Junction))
	{
		for (int32 Index : JunctionIncoming[Lane.Junction])
		{
			if (Index == Agent.Lane)
			{
				continue;
			}
			const FVBLane& Other = Lanes[Index];
			for (int32 OtherIndex : AgentsOnLane[Index])
			{
				const FVBTrafficAgent& OtherAgent = Agents[OtherIndex];
				const float OtherDistance = Other.Length - OtherAgent.S - VehicleTypes[OtherAgent.Type].Length * 0.5f - 60.f;
				if (OtherDistance > 0.f && OtherDistance < 1200.f
					&& (OtherDistance < DistanceToStop - 50.f || (FMath::Abs(OtherDistance - DistanceToStop) <= 50.f && OtherIndex < AgentIndex)))
				{
					return false;
				}
			}
		}
	}
	return true;
}

void AVBTrafficManager::StepAgent(FVBTrafficAgent& Agent, int32 AgentIndex, float DeltaSeconds)
{
	EnsureRoute(Agent);
	const FVBTrafficVehicleType& Type = VehicleTypes[Agent.Type];
	const FVBLane& Lane = Lanes[Agent.Lane];

	float LeaderSpeed = 0.f;
	float Gap = LeaderGap(Agent, AgentIndex, LeaderSpeed);
	const float Obstacle = ObstacleGap(Agent);
	if (Obstacle < Gap)
	{
		Gap = Obstacle;
		LeaderSpeed = 0.f;
	}

	// Haltelinie vor der Kreuzung
	if (!Lane.bConnector && Agent.Route.Num() > 0 && Lanes[Agent.Route[0]].bConnector)
	{
		const float DistanceToStop = Lane.Length - Agent.S - Type.Length * 0.5f - 60.f;
		if (DistanceToStop > -Type.Length * 0.5f)
		{
			if (DistanceToStop > 0.f || !Agent.bCommitted)
			{
				Agent.bCommitted = DistanceToStop < 5000.f && MayEnterJunction(Agent, AgentIndex, DistanceToStop);
			}
			if (!Agent.bCommitted && DistanceToStop < Gap)
			{
				Gap = FMath::Max(DistanceToStop, 0.f);
				LeaderSpeed = 0.f;
			}
		}
	}

	// Intelligent Driver Model
	const float Agility = FMath::Max(Type.Agility, 0.2f);
	const float A = VBTraffic::MaxAccel * Agility;
	const float B = VBTraffic::ComfortDecel;
	const float V0 = DesiredSpeed(Agent);
	const float V = Agent.V;
	float Acceleration = A * (1.f - FMath::Pow(V / V0, 4.f));
	if (Gap < TNumericLimits<float>::Max())
	{
		const float DesiredGap = VBTraffic::MinGap + FMath::Max(0.f, V * VBTraffic::TimeHeadway + V * (V - LeaderSpeed) / (2.f * FMath::Sqrt(A * B)));
		Acceleration -= A * FMath::Square(DesiredGap / FMath::Max(Gap, 1.f));
	}
	Acceleration = FMath::Clamp(Acceleration, -VBTraffic::MaxDecel, A);
	Agent.Accel = Acceleration;
	Agent.V = FMath::Max(0.f, V + Acceleration * DeltaSeconds);
	Agent.S += Agent.V * DeltaSeconds;
	Agent.WaitTime = Agent.V < 20.f ? Agent.WaitTime + DeltaSeconds : 0.f;

	while (Agent.S > Lanes[Agent.Lane].Length && Agent.Route.Num() > 0)
	{
		Agent.S -= Lanes[Agent.Lane].Length;
		Agent.Lane = Agent.Route[0];
		Agent.Route.RemoveAt(0);
		Agent.bCommitted = false;
		EnsureRoute(Agent);
	}
	Agent.S = FMath::Min(Agent.S, Lanes[Agent.Lane].Length);

	const bool bBraking = Acceleration < -80.f || Agent.V < 30.f;
	PlaceAgent(Agent, DeltaSeconds, bBraking);
}

void AVBTrafficManager::PlaceAgent(FVBTrafficAgent& Agent, float DeltaSeconds, bool bBraking)
{
	const FVBTrafficVehicleType& Type = VehicleTypes[Agent.Type];
	const FVBLane& Lane = Lanes[Agent.Lane];
	const float T = Lane.ParamAtDistance(Agent.S);
	const FVector Location = Lane.Eval(T);
	const float NewYaw = Lane.Tangent(T).Rotation().Yaw;
	const float YawDelta = FMath::FindDeltaAngleDegrees(Agent.Yaw, NewYaw);
	Agent.Yaw = NewYaw;

	// Lenkwinkel aus der Kruemmung: tan(delta) = Radstand * Kruemmung
	const float Distance = FMath::Max(Agent.V * DeltaSeconds, 1.f);
	const float Curvature = FMath::DegreesToRadians(YawDelta) / Distance;

	// Karosseriebewegung: Nicken beim Bremsen/Anfahren, Neigen in Kurven (Querbeschleunigung v^2 * Kruemmung)
	const float TargetPitch = FMath::Clamp(-Agent.Accel / 900.f * 1.6f, -1.8f, 1.2f);
	const float TargetRoll = FMath::Clamp(Agent.V * Agent.V * Curvature / 900.f * 1.4f, -2.5f, 2.5f);
	Agent.BodyPitch = FMath::FInterpTo(Agent.BodyPitch, TargetPitch, DeltaSeconds, 4.f);
	Agent.BodyRoll = FMath::FInterpTo(Agent.BodyRoll, TargetRoll, DeltaSeconds, 4.f);
	Agent.Actor->SetActorLocationAndRotation(Location, FRotator(Agent.BodyPitch, Agent.Yaw, Agent.BodyRoll));
	const float Steer = Agent.V > 10.f ? FMath::Clamp(FMath::RadiansToDegrees(FMath::Atan(Type.Wheelbase * Curvature)), -35.f, 35.f) : 0.f;

	// Blinker: auf der Abbiegekurve oder bis 35 m davor
	int32 Indicator = Lane.bConnector ? Lane.Turn : 0;
	if (!Lane.bConnector && Agent.Route.Num() > 0 && Lane.Length - Agent.S < 3500.f)
	{
		Indicator = Lanes[Agent.Route[0]].Turn;
	}

	const UVBTimeOfDaySubsystem* Time = GetWorld()->GetSubsystem<UVBTimeOfDaySubsystem>();
	const UVBWeatherSubsystem* Weather = GetWorld()->GetSubsystem<UVBWeatherSubsystem>();
	const EVBWeatherType WeatherType = Weather ? Weather->GetWeather() : EVBWeatherType::Clear;
	const bool bLights = (Time && Time->GetNightFactor() > 0.3f) || WeatherType == EVBWeatherType::HeavyRain
		|| WeatherType == EVBWeatherType::Fog || WeatherType == EVBWeatherType::Storm;

	Agent.Actor->UpdateVisuals(DeltaSeconds, Agent.V, Steer, bBraking, bLights, Indicator);
	Agent.Actor->UpdateAudio(Agent.V, FVector::DistSquared(Location, PlayerLocation) < FMath::Square(4000.f));
}

void AVBTrafficManager::DrawDebug() const
{
	UWorld* World = GetWorld();
	const float RadiusSq = FMath::Square(SimulationRadius);
	const double Now = World->GetTimeSeconds();
	for (const FVBLane& Lane : Lanes)
	{
		if (FVector::DistSquared2D(Lane.P0, PlayerLocation) > RadiusSq)
		{
			continue;
		}
		FColor Color = Lane.bConnector ? (Lane.Turn < 0 ? FColor::Orange : (Lane.Turn > 0 ? FColor::Cyan : FColor::White)) : FColor::Green;
		if (!Lane.bConnector && Lane.bHasSignal)
		{
			const EVBSignalState State = Lane.Signal.StateAt(Now);
			Color = State == EVBSignalState::Green ? FColor::Green : (State == EVBSignalState::Red ? FColor::Red : FColor::Yellow);
		}
		FVector Previous = Lane.P0;
		for (int32 Step = 1; Step <= 12; ++Step)
		{
			const FVector Point = Lane.Eval(Step / 12.f);
			DrawDebugLine(World, Previous + FVector(0, 0, 20), Point + FVector(0, 0, 20), Color, false, -1.f, 0, Lane.bConnector ? 4.f : 8.f);
			Previous = Point;
		}
	}
	for (const FVBTrafficAgent& Agent : Agents)
	{
		if (Agent.Actor)
		{
			DrawDebugString(World, Agent.Actor->GetActorLocation() + FVector(0, 0, 260), FString::Printf(TEXT("%.0f km/h%s"),
				Agent.V * 0.036f, Agent.bCommitted ? TEXT(" >") : TEXT("")), nullptr, FColor::White, 0.f, true);
		}
	}
}
