#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "VBMenuWidget.generated.h"

class UButton;
class UTextBlock;
class UVerticalBox;

/**
 * Start- und Pausenmenue (Phase 9), komplett in C++ aufgebaut (keine Widget-Assets noetig):
 * Spielen/Weiter, Grafikmodus, dynamisches Wetter, Umgebungslautstaerke, Mission neu starten, Neues Spiel, Beenden.
 */
UCLASS()
class VEYRABAY_API UVBMenuWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	void SetStartScreen(bool bInStartScreen);
	void RefreshLabels();

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;

private:
	UButton* AddButton(UVerticalBox* Box, const FString& Label, UTextBlock*& OutText);
	UTextBlock* AddText(UVerticalBox* Box, const FString& Text, int32 Size, const FLinearColor& Color);

	UFUNCTION() void OnResume();
	UFUNCTION() void OnGraphics();
	UFUNCTION() void OnWeather();
	UFUNCTION() void OnVolume();
	UFUNCTION() void OnRestartMission();
	UFUNCTION() void OnNewGame();
	UFUNCTION() void OnQuit();

	UPROPERTY(Transient) TObjectPtr<UTextBlock> SubtitleText;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> ResumeText;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> GraphicsText;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> WeatherText;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> VolumeText;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> RestartText;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> NewGameText;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> QuitText;

	bool bStartScreen = false;
};
