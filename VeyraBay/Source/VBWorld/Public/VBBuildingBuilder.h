#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "VBBuildingBuilder.generated.h"

class UInstancedStaticMeshComponent;
class UStaticMesh;

/** Modul-Komponenten des Gebaeude-Baukastens (Reihenfolge = ModuleInstances). */
enum class EVBBuildingModule : uint8
{
	Window, Variant, Plain, GroundShop, GroundDoor, GroundWindow, GroundPlain,
	Cornice, CornerGround, CornerUpper, CornerCornice, RoofTile, Count
};

/** Wie eine Gebaeudeseite ausgefuehrt wird. */
UENUM(BlueprintType)
enum class EVBFacadeMode : uint8
{
	/** Vollstaendige Fassade mit Fenstern (Strasse oder Hof). */
	Full,
	/** Geschlossene Brandwand (an Nachbargebaeude, oberhalb niedrigerer Nachbarn sichtbar). */
	Plain,
	/** Nichts bauen (vollstaendig verdeckt). */
	None
};

/** Modulsatz eines Baustils (Blender-Kit: Tools/Blender/assets/vb_asset_facades.py). */
USTRUCT(BlueprintType)
struct VBWORLD_API FVBFacadeStyle
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style") TObjectPtr<UStaticMesh> Window;
	/** Alternative fuer Obergeschosse (Balkon / Doppelfenster / Paneel), spaltenweise gewaehlt. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style") TObjectPtr<UStaticMesh> Variant;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style") TObjectPtr<UStaticMesh> Plain;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style") TObjectPtr<UStaticMesh> GroundShop;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style") TObjectPtr<UStaticMesh> GroundDoor;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style") TObjectPtr<UStaticMesh> GroundWindow;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style") TObjectPtr<UStaticMesh> GroundPlain;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style") TObjectPtr<UStaticMesh> Cornice;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style") TObjectPtr<UStaticMesh> CornerGround;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style") TObjectPtr<UStaticMesh> CornerUpper;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Style") TObjectPtr<UStaticMesh> CornerCornice;
};

/**
 * Baut ein Gebaeude aus modularen Fassadenteilen (3-m-Raster) als Instanced Static Meshes.
 * Lokales System (cm): Grundriss X 0..BaysX*300 (Strassenseite bei Y=0, aussen = -Y), Y 0..BaysY*300.
 * Jedes Gebaeude bekommt ueber Custom Primitive Data [1] einen eigenen Putzfarbton (TintBlend).
 */
UCLASS(ClassGroup = (VeyraBay), meta = (DisplayName = "VB Building Builder"))
class VBWORLD_API AVBBuildingBuilder : public AActor
{
	GENERATED_BODY()

public:
	static constexpr int32 MaxRoofProps = 4;

	AVBBuildingBuilder();

	virtual void OnConstruction(const FTransform& Transform) override;

	UFUNCTION(CallInEditor, BlueprintCallable, Category = "Building")
	void Rebuild();

	/** Traufhoehe (Oberkante oberstes Geschoss) in cm. */
	UFUNCTION(BlueprintPure, Category = "Building")
	float GetEavesHeight() const;

	// --- Form ------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Building", meta = (ClampMin = "1", ClampMax = "40"))
	int32 BaysX = 5;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Building", meta = (ClampMin = "1", ClampMax = "40"))
	int32 BaysY = 4;

	/** Geschosse inklusive Erdgeschoss. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Building", meta = (ClampMin = "1", ClampMax = "60"))
	int32 Floors = 5;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Building")
	EVBFacadeMode Front = EVBFacadeMode::Full;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Building")
	EVBFacadeMode Right = EVBFacadeMode::Full;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Building")
	EVBFacadeMode Back = EVBFacadeMode::Full;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Building")
	EVBFacadeMode Left = EVBFacadeMode::Full;

	/** Erdgeschoss der Strassenseite: Anteil Laeden (Rest Fenster, eine Tuer ist immer dabei). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Building", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float ShopRatio = 0.7f;

	/** Anteil der Fensterachsen mit Variante (Balkone usw.). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Building", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float VariantRatio = 0.35f;

	/** Farbton zwischen den zwei Putz-Grundtoenen (0..1); < 0 = zufaellig aus dem Seed. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Building")
	float TintBlend = -1.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Building")
	int32 Seed = 1;

	// --- Module ---------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Modules")
	FVBFacadeStyle Style;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Modules")
	TObjectPtr<UStaticMesh> RoofTile;

	/** Dachaufbauten (Klimageraete, Rohre, Antennen ...), zufaellig verteilt. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Modules")
	TArray<TObjectPtr<UStaticMesh>> RoofProps;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Modules", meta = (ClampMin = "0", ClampMax = "40"))
	int32 RoofPropCount = 6;

	// --- Raster (cm) -------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Grid")
	float BayWidth = 300.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Grid")
	float GroundHeight = 450.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Grid")
	float FloorHeight = 300.f;

	// --- Komponenten ----------------------------------------------------------------------------
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TArray<TObjectPtr<UInstancedStaticMeshComponent>> ModuleInstances;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TArray<TObjectPtr<UInstancedStaticMeshComponent>> RoofPropInstances;

private:
	UStaticMesh* MeshFor(EVBBuildingModule Module) const;
	void Add(EVBBuildingModule Module, const FVector& Location, float Yaw);
	void BuildFacade(int32 FacadeIndex, EVBFacadeMode Mode, FRandomStream& Stream);
	void BuildRoof(FRandomStream& Stream);
};
