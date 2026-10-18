#include "VBBuildingBuilder.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"

namespace VBBuilding
{
	static const TCHAR* ModuleNames[] = {
		TEXT("Window"), TEXT("Variant"), TEXT("Plain"), TEXT("GroundShop"), TEXT("GroundDoor"), TEXT("GroundWindow"),
		TEXT("GroundPlain"), TEXT("Cornice"), TEXT("CornerGround"), TEXT("CornerUpper"), TEXT("CornerCornice"), TEXT("RoofTile")
	};
	static_assert(UE_ARRAY_COUNT(ModuleNames) == static_cast<int32>(EVBBuildingModule::Count), "Modulnamen passen nicht");
}

AVBBuildingBuilder::AVBBuildingBuilder()
{
	PrimaryActorTick.bCanEverTick = false;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Static);
	RootComponent = Root;

	for (const TCHAR* Name : VBBuilding::ModuleNames)
	{
		UInstancedStaticMeshComponent* Instances = CreateDefaultSubobject<UInstancedStaticMeshComponent>(*FString::Printf(TEXT("Module_%s"), Name));
		Instances->SetupAttachment(Root);
		Instances->SetMobility(EComponentMobility::Static);
		ModuleInstances.Add(Instances);
	}
	for (int32 Index = 0; Index < MaxRoofProps; ++Index)
	{
		UInstancedStaticMeshComponent* Instances = CreateDefaultSubobject<UInstancedStaticMeshComponent>(*FString::Printf(TEXT("RoofProp_%d"), Index));
		Instances->SetupAttachment(Root);
		Instances->SetMobility(EComponentMobility::Static);
		Instances->SetCullDistances(30000, 40000);    // Dachaufbauten ab 300-400 m ausblenden
		RoofPropInstances.Add(Instances);
	}
}

void AVBBuildingBuilder::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	Rebuild();
}

float AVBBuildingBuilder::GetEavesHeight() const
{
	return GroundHeight + FMath::Max(Floors - 1, 0) * FloorHeight;
}

UStaticMesh* AVBBuildingBuilder::MeshFor(EVBBuildingModule Module) const
{
	switch (Module)
	{
	case EVBBuildingModule::Window:        return Style.Window;
	case EVBBuildingModule::Variant:       return Style.Variant ? Style.Variant.Get() : Style.Window.Get();
	case EVBBuildingModule::Plain:         return Style.Plain;
	case EVBBuildingModule::GroundShop:    return Style.GroundShop;
	case EVBBuildingModule::GroundDoor:    return Style.GroundDoor;
	case EVBBuildingModule::GroundWindow:  return Style.GroundWindow;
	case EVBBuildingModule::GroundPlain:   return Style.GroundPlain;
	case EVBBuildingModule::Cornice:       return Style.Cornice;
	case EVBBuildingModule::CornerGround:  return Style.CornerGround;
	case EVBBuildingModule::CornerUpper:   return Style.CornerUpper;
	case EVBBuildingModule::CornerCornice: return Style.CornerCornice;
	case EVBBuildingModule::RoofTile:      return RoofTile;
	default:                     return nullptr;
	}
}

void AVBBuildingBuilder::Add(EVBBuildingModule Module, const FVector& Location, float Yaw)
{
	UInstancedStaticMeshComponent* Instances = ModuleInstances[static_cast<int32>(Module)];
	if (Instances && Instances->GetStaticMesh())
	{
		Instances->AddInstance(FTransform(FRotator(0.f, Yaw, 0.f), Location));
	}
}

void AVBBuildingBuilder::Rebuild()
{
	FRandomStream Stream(Seed);
	const float Blend = TintBlend >= 0.f ? FMath::Clamp(TintBlend, 0.f, 1.f) : Stream.FRand();

	for (int32 Index = 0; Index < ModuleInstances.Num(); ++Index)
	{
		UInstancedStaticMeshComponent* Instances = ModuleInstances[Index];
		UStaticMesh* Mesh = MeshFor(static_cast<EVBBuildingModule>(Index));
		Instances->ClearInstances();
		Instances->SetStaticMesh(Mesh);
		Instances->SetVisibility(Mesh != nullptr);
		// Custom Primitive Data [1] = TintBlend (Putzfarbton je Gebaeude, siehe M_VB_Surface)
		Instances->SetCustomPrimitiveDataFloat(1, Blend);
	}

	const EVBFacadeMode Modes[] = { Front, Right, Back, Left };
	for (int32 Facade = 0; Facade < 4; ++Facade)
	{
		BuildFacade(Facade, Modes[Facade], Stream);
	}
	BuildRoof(Stream);
}

void AVBBuildingBuilder::BuildFacade(int32 FacadeIndex, EVBFacadeMode Mode, FRandomStream& Stream)
{
	if (Mode == EVBFacadeMode::None)
	{
		return;
	}

	// Startecke und Laufrichtung: vorne (+X), rechts (+Y), hinten (-X), links (-Y); aussen liegt jeweils links der Laufrichtung
	const float Width = BaysX * BayWidth;
	const float Depth = BaysY * BayWidth;
	const FVector Starts[] = { FVector(0.f, 0.f, 0.f), FVector(Width, 0.f, 0.f), FVector(Width, Depth, 0.f), FVector(0.f, Depth, 0.f) };
	const float Yaws[] = { 0.f, 90.f, 180.f, 270.f };
	const int32 Bays = (FacadeIndex % 2 == 0) ? BaysX : BaysY;

	const FVector Start = Starts[FacadeIndex];
	const float Yaw = Yaws[FacadeIndex];
	const FVector Direction = FRotator(0.f, Yaw, 0.f).Vector();
	const bool bPlain = (Mode == EVBFacadeMode::Plain);
	const float Eaves = GetEavesHeight();

	// Strassenseite: eine Tuer, sonst Laeden/Fenster; Hof/Seiten: Fenster (hinten ebenfalls eine Tuer)
	const int32 DoorBay = Stream.RandRange(0, Bays - 1);
	const bool bHasDoor = !bPlain && (FacadeIndex == 0 || FacadeIndex == 2);

	for (int32 Bay = 0; Bay < Bays; ++Bay)
	{
		const FVector Base = Start + Direction * (Bay * BayWidth);

		EVBBuildingModule Ground = EVBBuildingModule::GroundWindow;
		if (bPlain)
		{
			Ground = EVBBuildingModule::GroundPlain;
		}
		else if (bHasDoor && Bay == DoorBay)
		{
			Ground = EVBBuildingModule::GroundDoor;
		}
		else if (FacadeIndex == 0 && Stream.FRand() < ShopRatio)
		{
			Ground = EVBBuildingModule::GroundShop;
		}
		Add(Ground, Base, Yaw);

		// Varianten spaltenweise (Balkone uebereinander wirken architektonisch richtig), nie im 1. OG ueber Laeden
		const bool bVariantColumn = !bPlain && Stream.FRand() < VariantRatio;
		for (int32 Floor = 1; Floor < Floors; ++Floor)
		{
			const EVBBuildingModule Upper = bPlain ? EVBBuildingModule::Plain : ((bVariantColumn && Floor >= 1) ? EVBBuildingModule::Variant : EVBBuildingModule::Window);
			Add(Upper, Base + FVector(0.f, 0.f, GroundHeight + (Floor - 1) * FloorHeight), Yaw);
		}
		Add(EVBBuildingModule::Cornice, Base + FVector(0.f, 0.f, Eaves), Yaw);
	}

	// Ecke am Anfang dieser Fassade (jede Ecke genau einmal)
	Add(EVBBuildingModule::CornerGround, Start, Yaw);
	for (int32 Floor = 1; Floor < Floors; ++Floor)
	{
		Add(EVBBuildingModule::CornerUpper, Start + FVector(0.f, 0.f, GroundHeight + (Floor - 1) * FloorHeight), Yaw);
	}
	Add(EVBBuildingModule::CornerCornice, Start + FVector(0.f, 0.f, Eaves), Yaw);
}

void AVBBuildingBuilder::BuildRoof(FRandomStream& Stream)
{
	const float Eaves = GetEavesHeight();
	for (int32 X = 0; X < BaysX; ++X)
	{
		for (int32 Y = 0; Y < BaysY; ++Y)
		{
			Add(EVBBuildingModule::RoofTile, FVector(X * BayWidth, Y * BayWidth, Eaves), 0.f);
		}
	}

	for (UInstancedStaticMeshComponent* Instances : RoofPropInstances)
	{
		Instances->ClearInstances();
		Instances->SetStaticMesh(nullptr);
	}
	const int32 PropTypes = FMath::Min(RoofProps.Num(), RoofPropInstances.Num());
	for (int32 Type = 0; Type < PropTypes; ++Type)
	{
		RoofPropInstances[Type]->SetStaticMesh(RoofProps[Type]);
	}
	if (PropTypes == 0)
	{
		return;
	}

	// Aufbauten mit Abstand zur Attika verteilen (1.5 m Rand)
	const float Margin = 150.f;
	const float MaxX = BaysX * BayWidth - Margin;
	const float MaxY = BaysY * BayWidth - Margin;
	if (MaxX <= Margin || MaxY <= Margin)
	{
		return;
	}
	for (int32 Index = 0; Index < RoofPropCount; ++Index)
	{
		const int32 Type = Stream.RandRange(0, PropTypes - 1);
		const FVector Location(Stream.FRandRange(Margin, MaxX), Stream.FRandRange(Margin, MaxY), Eaves + 5.f);
		const float Yaw = 90.f * Stream.RandRange(0, 3);
		RoofPropInstances[Type]->AddInstance(FTransform(FRotator(0.f, Yaw, 0.f), Location));
	}
}
