#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "VBGameSettings.generated.h"

class USkeletalMesh;
class UAnimInstance;

/**
 * Spieler-Einstellungen (Projekteinstellungen -> Game -> Veyra Bay Game).
 * Das Setup-Skript traegt hier automatisch das gefundene Mannequin + AnimBlueprint ein.
 */
UCLASS(Config = Game, DefaultConfig, meta = (DisplayName = "Veyra Bay Game"))
class VEYRABAY_API UVBGameSettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	virtual FName GetCategoryName() const override { return TEXT("Game"); }

	/** Skeletal Mesh der Spielfigur (z. B. SKM_Manny aus dem Third Person Pack / Game Animation Sample). */
	UPROPERTY(Config, EditAnywhere, BlueprintReadOnly, Category = "Player")
	TSoftObjectPtr<USkeletalMesh> PlayerMesh;

	/** Animation Blueprint der Spielfigur. */
	UPROPERTY(Config, EditAnywhere, BlueprintReadOnly, Category = "Player")
	TSoftClassPtr<UAnimInstance> PlayerAnimClass;

	/** Maus-Empfindlichkeit (1 = Standard). */
	UPROPERTY(Config, EditAnywhere, BlueprintReadOnly, Category = "Input", meta = (ClampMin = "0.05", ClampMax = "5.0"))
	float MouseSensitivity = 1.f;

	UPROPERTY(Config, EditAnywhere, BlueprintReadOnly, Category = "Input")
	bool bInvertMouseY = false;

	/** Gamepad-Drehgeschwindigkeit in Grad pro Sekunde. */
	UPROPERTY(Config, EditAnywhere, BlueprintReadOnly, Category = "Input", meta = (ClampMin = "30.0", ClampMax = "400.0"))
	float GamepadLookRate = 160.f;

	/** Schreibt die aktuellen Werte nach Config/DefaultGame.ini (vom Python-Setup genutzt). */
	UFUNCTION(BlueprintCallable, Category = "VeyraBay")
	void SaveToDefaultConfig();
};
