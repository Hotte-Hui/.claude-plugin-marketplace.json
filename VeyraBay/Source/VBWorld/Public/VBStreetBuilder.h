#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VBStreetBuilder.generated.h"

class UInstancedStaticMeshComponent;
class UStaticMesh;

/** Regel fuer wiederkehrende Stadtmoebel entlang der Strasse (Baenke, Poller, Kanaldeckel ...). */
USTRUCT(BlueprintType)
struct VBWORLD_API FVBStreetPropRule
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prop")
	TObjectPtr<UStaticMesh> Mesh;

	/** Abstand zwischen zwei Objekten entlang der Strasse (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prop", meta = (ClampMin = "50.0"))
	float Spacing = 2000.f;

	/** Position des ersten Objekts ab Strassenanfang (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prop")
	float StartOffset = 500.f;

	/** Seitlicher Abstand zur Strassenmitte (cm), wird je Seite gespiegelt. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prop")
	float LateralOffset = 700.f;

	/** Hoehe ueber dem Strassen-Nullpunkt (cm). Gehweg = 15. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prop")
	float Height = 15.f;

	/** Zusaetzliche Drehung. 0 = Vorderseite (+X des Meshes) zeigt zur Fahrbahn. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prop")
	float YawOffset = 0.f;

	/** Zufaellige Verschiebung entlang der Strasse (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prop", meta = (ClampMin = "0.0"))
	float PositionJitter = 0.f;

	/** Wahrscheinlichkeit, dass ein Platz besetzt wird. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prop", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float Probability = 1.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prop")
	bool bLeftSide = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prop")
	bool bRightSide = true;

	/** Auf der gewoelbten Fahrbahn platzieren und an deren Neigung ausrichten (Kanaldeckel). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prop")
	bool bOnRoadSurface = false;
};

/**
 * Baut eine gerade Strasse aus dem modularen Kit (Fahrbahn, Bordstein, Gehweg) plus Stadtmoebel.
 * Alles als Instanced Static Meshes (Nanite) -> sehr wenige Draw Calls, im Editor live einstellbar.
 *
 * Lokales Koordinatensystem: Strasse verlaeuft von X=0 bis X=Length, Mitte bei Y=0.
 * Masse passen zum Blender-Kit (Tools/Blender/assets/vb_asset_streetkit.py).
 */
UCLASS(ClassGroup = (VeyraBay), meta = (DisplayName = "VB Street Builder"))
class VBWORLD_API AVBStreetBuilder : public AActor
{
	GENERATED_BODY()

public:
	static constexpr int32 MaxPropRules = 8;

	AVBStreetBuilder();

	virtual void OnConstruction(const FTransform& Transform) override;

	UFUNCTION(CallInEditor, BlueprintCallable, Category = "Street")
	void Rebuild();

	/** Hoehe der Fahrbahnoberflaeche an lokaler Y-Position (Woelbung + Rinne), in cm. */
	UFUNCTION(BlueprintPure, Category = "Street")
	float GetRoadSurfaceHeight(float LocalY) const;

	// --- Aufbau -------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Street", meta = (ClampMin = "1000.0"))
	float Length = 12000.f;

	/** Index des Fahrbahnstuecks mit Zebrastreifen (-1 = keiner). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Street")
	int32 CrosswalkPieceIndex = -1;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Street")
	int32 Seed = 7;

	// --- Kit-Meshes -----------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Kit")
	TObjectPtr<UStaticMesh> RoadMesh;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Kit")
	TObjectPtr<UStaticMesh> CrosswalkMesh;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Kit")
	TObjectPtr<UStaticMesh> CurbMesh;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Kit")
	TObjectPtr<UStaticMesh> SidewalkMesh;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Kit")
	float RoadPieceLength = 1000.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Kit")
	float CurbPieceLength = 200.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Kit")
	float SidewalkPieceLength = 200.f;

	// --- Querschnitt (cm) -------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Profile")
	float AsphaltHalfWidth = 560.f;

	/** Abstand Strassenmitte -> Bordstein (Pivot von Bordstein und Gehweg). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Profile")
	float CurbOffset = 600.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Profile")
	float CrownHeight = 6.f;

	// --- Stadtmoebel --------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Props")
	TArray<FVBStreetPropRule> Props;

	// --- Komponenten --------------------------------------------------------------------
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UInstancedStaticMeshComponent> RoadInstances;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UInstancedStaticMeshComponent> CrosswalkInstances;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UInstancedStaticMeshComponent> CurbInstances;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UInstancedStaticMeshComponent> SidewalkInstances;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TArray<TObjectPtr<UInstancedStaticMeshComponent>> PropInstances;

private:
	void BuildEdges(UInstancedStaticMeshComponent* Instances, UStaticMesh* Mesh, float PieceLength) const;
	void BuildProps(const FVBStreetPropRule& Rule, UInstancedStaticMeshComponent* Instances, FRandomStream& Stream) const;
};
