#pragma once

#include "CoreMinimal.h"
#include "Curves/CurveFloat.h"
#include "GameFramework/Actor.h"
#include "VBTrafficVehicle.h"
#include "VBTrafficManager.generated.h"

class AVBStreetBuilder;
class AVBTrafficLight;

/** Ein Fahrweg: gerade Spur einer Strasse oder Abbiegekurve in einer Kreuzung (kubische Bezierkurve). */
struct FVBLane
{
	FVector P0, P1, P2, P3;
	float Length = 0.f;
	TArray<float> ArcTable;              // kumulierte Laenge an gleichmaessigen t-Schritten
	TArray<int32> Next;                  // folgende Fahrwege
	TArray<int32> Conflicts;             // Kurven derselben Kreuzung, die sich mit dieser schneiden
	TWeakObjectPtr<AVBTrafficLight> Signal;
	int32 Junction = INDEX_NONE;         // Kreuzung am Ende (Strassenspur) bzw. in der die Kurve liegt
	int32 Street = INDEX_NONE;           // Index des Street Builders (nur Strassenspuren)
	int32 Source = INDEX_NONE;           // Kurven: kommende Strassenspur
	int32 Opposing = INDEX_NONE;         // Linksabbieger: Gegenverkehrsspur
	int32 Turn = 0;                      // -1 links, 0 geradeaus, 1 rechts
	float SpeedLimit = 1389.f;           // cm/s
	bool bConnector = false;

	FVector Eval(float T) const;
	FVector Tangent(float T) const;
	float ParamAtDistance(float S) const;
	void Build();
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
 * KI-Verkehr (Phase 5): baut beim Spielstart aus allen AVBStreetBuilder-Strassen einen Spurgraphen
 * (Rechtsverkehr, eine Spur je Richtung), verbindet die Spuren in den Kreuzungen mit Abbiegekurven,
 * ordnet die Ampeln zu und simuliert die Autos kinematisch:
 *   - Intelligent Driver Model (Abstand, sanftes Bremsen/Anfahren)
 *   - Ampeln (Rot/Gelb-Entscheidung), Linksabbieger warten auf Gegenverkehr,
 *     Kreuzungen ohne Ampel: wer zuerst da ist, faehrt; Konfliktkurven werden freigehalten
 *   - Spieler (zu Fuss oder im Auto) und fahrbare Autos sind Hindernisse
 *   - Dichte nach Tageszeit und Wetter, Blinker, Bremslichter, Scheinwerfer
 * Zusaetzlich parkende Autos am Fahrbahnrand.
 */
UCLASS(ClassGroup = (VeyraBay), meta = (DisplayName = "VB Traffic Manager"))
class VBWORLD_API AVBTrafficManager : public AActor
{
	GENERATED_BODY()

public:
	AVBTrafficManager();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintPure, Category = "Traffic")
	int32 GetVehicleCount() const { return Agents.Num(); }

	UFUNCTION(BlueprintPure, Category = "Traffic")
	int32 GetLaneCount() const { return Lanes.Num(); }

	/** Fussgaenger auf der Fahrbahn melden (Autos halten davor). Wird jeden Frame geleert. */
	void AddTransientObstacle(const FVector& Location, float Radius);

	/** Fahrwege (fuer Debug-Anzeige und Fussgaengersystem). */
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
	int32 MaxVehicles = 60;

	/** Dichte ueber den Tag (x = Stunde 0..24, y = Anteil 0..1). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Traffic")
	FRuntimeFloatCurve DensityByHour;

	/** Anteil der Parkplaetze am Strassenrand, die belegt sind. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parking", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float ParkingOccupancy = 0.55f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Parking")
	bool bSpawnParkedCars = true;

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

private:
	void BuildGraph();
	void SpawnParkedCars();
	void UpdateDensity(float DeltaSeconds);
	bool TrySpawnAgent(bool bAvoidPlayer);
	void RemoveAgent(int32 Index);
	void UpdateObstacles();
	void StepAgent(FVBTrafficAgent& Agent, int32 AgentIndex, float DeltaSeconds);
	void PlaceAgent(FVBTrafficAgent& Agent, float DeltaSeconds, bool bBraking);
	void EnsureRoute(FVBTrafficAgent& Agent);
	int32 PickNext(int32 Lane);
	bool MayEnterJunction(const FVBTrafficAgent& Agent, int32 AgentIndex, float DistanceToStop) const;
	float LeaderGap(const FVBTrafficAgent& Agent, int32 AgentIndex, float& OutLeaderSpeed) const;
	float ObstacleGap(const FVBTrafficAgent& Agent) const;
	float DesiredSpeed(const FVBTrafficAgent& Agent) const;
	float WeatherFactor() const;
	int32 PickType(bool bParked);
	FLinearColor PickPaint(const FVBTrafficVehicleType& Type);
	float DistanceToPlayer(const FVector& Location) const;
	void DrawDebug() const;

	TArray<FVBLane> Lanes;
	TArray<FVBTrafficAgent> Agents;
	TArray<TWeakObjectPtr<AActor>> ObstacleActors;
	TArray<FVector4> TransientObstacles;       // xyz + Radius
	TArray<FVector4> FrameObstacles;
	TArray<TObjectPtr<AVBTrafficVehicle>> ParkedCars;
	TArray<TArray<int32>> AgentsOnLane;
	float TotalLaneLength = 0.f;
	float SpawnTimer = 0.f;
	float ObstacleTimer = 0.f;
	FRandomStream Random;

	UPROPERTY(Transient)
	TArray<TObjectPtr<AVBTrafficVehicle>> SpawnedActors;
};
