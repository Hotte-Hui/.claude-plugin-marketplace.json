#include "VBGameMode.h"

#include "VBHUD.h"
#include "VBLog.h"
#include "VBPlayerCharacter.h"
#include "VBPlayerController.h"
#include "VBSkyEnvironment.h"
#include "Engine/DirectionalLight.h"
#include "Engine/World.h"
#include "EngineUtils.h"

AVBGameMode::AVBGameMode()
{
	DefaultPawnClass = AVBPlayerCharacter::StaticClass();
	PlayerControllerClass = AVBPlayerController::StaticClass();
	HUDClass = AVBHUD::StaticClass();
}

void AVBGameMode::StartPlay()
{
	EnsureSkyEnvironment();
	Super::StartPlay();
}

void AVBGameMode::EnsureSkyEnvironment()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	// Karte hat bereits einen Himmel bzw. eine eigene Beleuchtung - nicht doppelt beleuchten.
	const bool bHasSky = static_cast<bool>(TActorIterator<AVBSkyEnvironment>(World));
	const bool bHasSun = static_cast<bool>(TActorIterator<ADirectionalLight>(World));
	if (bHasSky || bHasSun)
	{
		return;
	}

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	World->SpawnActor<AVBSkyEnvironment>(FVector::ZeroVector, FRotator::ZeroRotator, Params);
	UE_LOG(LogVB, Log, TEXT("Kein Himmel in der Karte gefunden - VB Sky Environment wurde automatisch erzeugt."));
}
