#include "VBInstancedArray.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"

AVBInstancedArray::AVBInstancedArray()
{
	PrimaryActorTick.bCanEverTick = false;

	Instances = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Instances"));
	Instances->SetMobility(EComponentMobility::Static);
	RootComponent = Instances;
}

void AVBInstancedArray::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

	Instances->ClearInstances();
	Instances->SetStaticMesh(Mesh);
	Instances->SetCastShadow(bCastShadow);
	if (!Mesh)
	{
		return;
	}
	for (const FTransform& InstanceTransform : Transforms)
	{
		Instances->AddInstance(InstanceTransform);
	}
}
