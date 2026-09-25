#pragma once

#include "CoreMinimal.h"
#include "Curves/CurveFloat.h"
#include "GameFramework/Actor.h"
#include "VBTrafficLight.h"
#include "VBTrafficVehicle.h"
#include "VBTrafficManager.generated.h"

class AVBStreetBuilder;

/** Ein Fahrweg: gerade Spur einer Strasse oder Abbiegekurve in einer Kreuzung (kubische Bezierkurve). */
USTRUCT()
struct VBWORLD_API FVBLane
{
	GENERATED_BODY()

	UPROPERTY() FVector P0 = FVector::ZeroVector;
	UPROPERTY() FVector P1 = FVector::ZeroVector;
	UPROPERTY() FVector P2 = FVector::ZeroVector;
	UPROPERTY() FVector P3 = FVector::ZeroVector;
	UPROPERTY() float Length = 0.f;
	UPROPERTY() TArray<float> ArcTable;              // kumulierte Laenge an gleichmaessigen t-Schritten
	UPROPERTY() TArray<int32> Next;                  // folgende Fahrwege
	UPROPERTY() TArray<int32> Conflicts;             // Kurven derselben Kreuzung, die sich mit dieser schneiden
	UPROPERTY() int32 Junction = INDEX_NONE;         // Kreuzung am Ende (Strassenspur) bzw. in der die Kurve liegt
	UPROPERTY() int32 Street = INDEX_NONE;           // Strasse (nur Strassenspuren)
	UPROPERTY() int32 Source = INDEX_NONE;           // Kurven: kommende Strassenspur
	UPROPERTY() int32 Opposing = INDEX_NONE;         // Linksabbieger: Gegenverkehrsspur
	UPROPERTY() int32 Turn = 0;                      // -1 links, 0 geradeaus, 1 rechts
	UPROPERTY() float SpeedLimit = 1389.f;           // cm/s
	UPROPERTY() bool bConnector = false;
	UPROPERTY() bool bHasSignal = false;
	UPROPERTY() FVBSignalTiming Signal;              // Ampel am Ende der Strassenspur (Zustand aus der Weltzeit)

	FVector Eval(float T) const;
	FVector Tangent(float T) const;
	float ParamAtDistance(float S) const;
	void Build();
};

/** Parkplatz am Fahrbahnrand (beim Backen belegt oder nicht, Fahrzeugtyp und Lack fest). */
USTRUCT()
struct VBWORLD_API FVBParkingSlot
{
	GENERATED_BODY()

	UPROPERTY() FVector Location = FVector::ZeroVector;
	UPROPERTY() float Yaw = 0.f;
	UPROPERTY() int32 Type = 0;
	UPROPERTY() int32 Paint = INDEX_NONE;            // Index in PaintPalette, INDEX_NONE = Typfarbe
};

/** Ein KI-Fahrzeug im Verkehr. */
struct FVBTrafficAgent
{
	TObjectPtr<AVBTrafficVehicle> Actor;
	int32 Type = 0;
	int32 Lane = INDEX_NONE;
	float S = 0.f;                       // Position der Fahrzeugmitte auf dem Fahrweg (cm)
	float V = 0.f;                       // cm/s
	float DesiredFactor = 1.f;           // individuelles Temperament
	float Accel = 0.f;
	float WaitTime = 0.f;
	float Yaw = 0.f;
	TArray<int32, TInlineAllocator<4>> Route;   // geplante naechste Fahrwege
	bool bCommitted = false;             // darf in die Kreuzung einfahren
};

/**
 * KI-Verkehr: Spurgraph aus allen AVBStreetBuilder-Strassen (Rechtsverkehr, eine Spur je Richtung), Abbiegekurven in
 * den Kreuzungen, Ampelphasen, Parkplaetze. Der Graph wird im Editor gebacken ("Bake Network", vom Setup-Skript
 * aufgerufen) und ist dadurch unabhaengig vom World-Partition-Streaming; ohne gebackene Daten wird er beim Start aus
 * den geladenen Strassen erzeugt (kleine Testkarten).
 *
 * Simuliert werden nur Autos in einer Blase um den Spieler (SimulationRadius): Intelligent Driver Model, Ampeln mit
 * Gelb-Entscheidung, Linksabbieger warten, Kreuzungen ohne Ampel nach Ankunft, Spieler/fahrbare Autos/Fussgaenger als
 * Hindernisse, Dichte nach Uhrzeit und Wetter. Parkende Autos erscheinen ebenfalls nur in der Naehe.
 */
UCLASS(ClassGroup = (VeyraBay), meta = (DisplayName = "VB Traffic Manager"))
class VBWORLD_API AVBTrafficManager : public AActor
{
	GENERATED_BODY()

public:
	AVBTrafficManager();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Spurgraph und Parkplaetze aus den Strassen der Karte berechnen und speichern. */
	UFUNCTION(CallInEditor, BlueprintCallable, Category = "Traffic")
	void BakeNetwork();

	UFUNCTION(BlueprintPure, Category = "Traffic")
	int32 GetVehicleCount() const { return Agents.Num(); }

	UFUNCTION(BlueprintPure, Category = "Traffic")
	int32 GetLaneCount() const { return Lanes.Num(); }

	/** Fussgaenger auf der Fahrbahn melden (Autos halten davor). Gilt fuer den naechsten Frame. */
	void AddTransientObstacle(const FVector& Location, float Radius);

	const TArray<FVBLane>& GetLanes() const { return Lanes; }

	// --- Einstellungen ---------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic")
	bool bEnableTraffic = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic")
	TArray<FVBTrafficVehicleType> VehicleTypes;

	/** Lackfarben fuer Autos ohne feste Farbe (realistische Verteilung: viel Grau/Schwarz/Weiss). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic")
	TArray<FLinearColor> PaintPalette;

	/** Fahrzeuge bei voller Dichte (Hauptverkehrszeit) pro Kilometer Spur. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic", meta = (ClampMin = "0.0"))
	float VehiclesPerKm = 22.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic", meta = (ClampMin = "0"))
	int32 MaxVehicles = 80;

	/** Autos fahren nur in diesem Umkreis um den Spieler (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic", meta = (ClampMin = "5000.0"))
	float SimulationRadius = 35000.f;

	/** Neue Autos erscheinen nicht naeher als hier (und moeglichst ausserhalb der Sicht). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic", meta = (ClampMin = "0.0"))
	float MinSpawnDistance = 8000.f;

	/** Dichte ueber den Tag (x = Stunde 0..24, y = Anteil 0..1). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic")
	FRuntimeFloatCurve DensityByHour;

	/** Anteil der Parkplaetze am Strassenrand, die belegt sind (beim Backen). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parking", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float ParkingOccupancy = 0.55f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parking")
	bool bSpawnParkedCars = true;

	/** Geparkte Autos erscheinen in diesem Umkreis (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parking")
	float ParkedRadius = 22000.f;

	/** Seitlicher Abstand Fahrspur- bzw. Parkstreifenmitte zur Strassenmitte (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Lanes")
	float LaneOffset = 240.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Lanes")
	float ParkingOffset = 455.f;

	/** Abstand Kreuzungsmitte -> Haltelinie (cm), passend zum Kreuzungs-Mesh. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Lanes")
	float StopLineOffset = 935.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Lanes")
	float RoadHeight = 3.f;

	/** Innerorts 50 km/h. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Lanes")
	float SpeedLimitKmh = 50.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Debug")
	bool bDrawDebug = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic")
	int32 Seed = 1234;

	// --- Gebackene Daten ---------------------------------------------------------------------
	UPROPERTY(VisibleAnywhere, Category = "Baked")
	TArray<FVBLane> Lanes;

	UPROPERTY(VisibleAnywhere, Category = "Baked")
	TArray<FVBParkingSlot> ParkingSlots;

	UPROPERTY(VisibleAnywhere, Category = "Baked")
	float TotalLaneLength = 0.f;

private:
	void BuildGraph(TArray<FVBLane>& OutLanes, TArray<FVBParkingSlot>& OutSlots, float& OutLength);
	void UpdateNearLanes();
	void UpdateParkedCars();
	void UpdateDensity(float DeltaSeconds);
	bool TrySpawnAgent(bool bAvoidPlayer);
	void RemoveAgent(int32 Index);
	void UpdateObstacles();
	void RefreshObstacleActors();
	void StepAgent(FVBTrafficAgent& Agent, int32 AgentIndex, float DeltaSeconds);
	void PlaceAgent(FVBTrafficAgent& Agent, float DeltaSeconds, bool bBraking);
	void EnsureRoute(FVBTrafficAgent& Agent);
	int32 PickNext(int32 Lane);
	bool MayEnterJunction(const FVBTrafficAgent& Agent, int32 AgentIndex, float DistanceToStop) const;
	float LeaderGap(const FVBTrafficAgent& Agent, int32 AgentIndex, float& OutLeaderSpeed) const;
	float ObstacleGap(const FVBTrafficAgent& Agent) const;
	float DesiredSpeed(const FVBTrafficAgent& Agent) const;
	float WeatherFactor() const;
	int32 PickType(bool bParked, FRandomStream& Stream) const;
	FLinearColor PaintFor(const FVBTrafficVehicleType& Type, int32 PaintIndex) const;
	bool GetPlayerView(FVector& OutLocation, FVector& OutDirection) const;
	float DistanceToPlayer(const FVector& Location, bool* bOutInView = nullptr) const;
	void DrawDebug() const;

	TArray<FVBTrafficAgent> Agents;
	TArray<TWeakObjectPtr<AActor>> ObstacleActors;
	TArray<FVector4> TransientObstacles;       // xyz + Radius
	TArray<FVector4> FrameObstacles;
	TArray<TArray<int32>> AgentsOnLane;
	TArray<int32> NearLanes;                    // Strassenspuren in der Simulationsblase
	TArray<TArray<int32>> JunctionIncoming;     // Kreuzung -> ankommende Strassenspuren
	float NearLaneLength = 0.f;
	float SpawnTimer = 0.f;
	float NearTimer = 0.f;
	float ParkedTimer = 0.f;
	float ObstacleRefreshTimer = 0.f;
	FVector PlayerLocation = FVector::ZeroVector;
	FRandomStream Random;

	UPROPERTY(Transient)
	TArray<TObjectPtr<AVBTrafficVehicle>> SpawnedActors;

	UPROPERTY(Transient)
	TMap<int32, TObjectPtr<AVBTrafficVehicle>> ParkedActors;
};
