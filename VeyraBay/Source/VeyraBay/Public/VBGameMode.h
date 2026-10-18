#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "VBGameMode.generated.h"

UCLASS()
class VEYRABAY_API AVBGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AVBGameMode();

	virtual void StartPlay() override;

private:
	/** Falls die Karte keinen Himmel hat, wird automatisch ein AVBSkyEnvironment erzeugt. */
	void EnsureSkyEnvironment();
};
