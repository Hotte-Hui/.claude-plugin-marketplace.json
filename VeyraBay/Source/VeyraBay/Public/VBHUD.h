#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "VBHUD.generated.h"

class UFont;

/**
 * [PROTOTYP-UI] Minimalistisches Canvas-HUD fuer Phase 1:
 * Interaktionshinweis, Pause, Debug-Infos, Performance-Overlay.
 * Wird in der UI-Phase durch Common-UI-Widgets (animiert) ersetzt.
 */
UCLASS()
class VEYRABAY_API AVBHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

	/** Aus -> Frame-Zeiten (stat unit) -> + GPU-Aufschluesselung (stat gpu) -> Aus */
	void CyclePerfOverlay();
	void ToggleDebugInfo();
	void ShowToast(const FString& Message, float Seconds = 2.5f);

private:
	void DrawPanel(const FString& Text, float X, float Y, UFont* Font, float Scale, bool bCenterX, const FLinearColor& TextColor = FLinearColor::White);
	void DrawInteractionPrompt(float UIScale);
	void DrawDebugInfo(float UIScale);
	void DrawToast(float UIScale);
	void DrawPauseOverlay(float UIScale);
	void DrawSetupHint(float UIScale);
	void DrawVehicleHUD(float UIScale);

	int32 PerfLevel = 0;
	bool bShowDebugInfo = false;
	FString ToastText;
	double ToastEndTime = 0.0;
};
