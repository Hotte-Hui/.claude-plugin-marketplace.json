#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "VBPlayerController.generated.h"

class UVBInputSet;
class UVBMenuWidget;
class AVBHUD;
struct FInputActionValue;

UCLASS()
class VEYRABAY_API AVBPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	/** Liefert die (bei Bedarf erzeugten) Eingabeaktionen. */
	UVBInputSet* GetInputSet();

	/** Start-/Pausenmenue (pausiert das Spiel, Maus sichtbar). */
	void OpenMenu(bool bStartScreen);
	void CloseMenu();
	bool IsMenuOpen() const;

protected:
	virtual void BeginPlay() override;
	virtual void SetupInputComponent() override;
	virtual void OnPossess(APawn* InPawn) override;

	/** Zu Fuss: GameplayContext, im Fahrzeug: VehicleContext. */
	void UpdateMappingContexts(APawn* ForPawn);

private:
	void Input_Pause(const FInputActionValue& Value);

	void Debug_CyclePerf(const FInputActionValue& Value);
	void Debug_ToggleInfo(const FInputActionValue& Value);
	void Debug_NextWeather(const FInputActionValue& Value);
	void Debug_TimeBack(const FInputActionValue& Value);
	void Debug_TimeForward(const FInputActionValue& Value);
	void Debug_TimePause(const FInputActionValue& Value);
	void Debug_GraphicsMode(const FInputActionValue& Value);

	void ShiftTime(float DeltaHours);
	AVBHUD* GetVBHUD() const;

	UPROPERTY(Transient)
	TObjectPtr<UVBInputSet> InputSet;

	UPROPERTY(Transient)
	TObjectPtr<UVBMenuWidget> Menu;
};
