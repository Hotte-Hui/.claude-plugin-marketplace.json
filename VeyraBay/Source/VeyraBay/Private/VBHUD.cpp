#include "VBHUD.h"

#include "VBGraphicsSubsystem.h"
#include "VBInteractionComponent.h"
#include "VBPlayerCharacter.h"
#include "VBVehicle.h"
#include "VBTimeOfDaySubsystem.h"
#include "VBWeatherSubsystem.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"

namespace VBHUDStyle
{
	static const FLinearColor PanelColor(0.f, 0.f, 0.f, 0.45f);
	static const FLinearColor Accent(1.f, 0.78f, 0.35f, 1.f);
	static const FLinearColor Muted(0.8f, 0.8f, 0.8f, 1.f);
	static constexpr float PaddingX = 14.f;
	static constexpr float PaddingY = 8.f;
}

void AVBHUD::DrawHUD()
{
	Super::DrawHUD();

	if (!Canvas)
	{
		return;
	}

	const float UIScale = FMath::Max(Canvas->ClipY / 1080.f, 0.5f);

	DrawSetupHint(UIScale);
	DrawInteractionPrompt(UIScale);
	DrawVehicleHUD(UIScale);
	DrawToast(UIScale);

	if (bShowDebugInfo)
	{
		DrawDebugInfo(UIScale);
	}

	if (PlayerOwner && PlayerOwner->IsPaused())
	{
		DrawPauseOverlay(UIScale);
	}
}

void AVBHUD::CyclePerfOverlay()
{
	if (!PlayerOwner)
	{
		return;
	}

	PerfLevel = (PerfLevel + 1) % 3;
	switch (PerfLevel)
	{
	case 1:
		PlayerOwner->ConsoleCommand(TEXT("stat fps"));
		PlayerOwner->ConsoleCommand(TEXT("stat unit"));
		ShowToast(TEXT("Performance: Frame-Zeiten"));
		break;
	case 2:
		PlayerOwner->ConsoleCommand(TEXT("stat gpu"));
		ShowToast(TEXT("Performance: + GPU-Aufschluesselung (Lumen, Nanite, Schatten ...)"));
		break;
	default:
		PlayerOwner->ConsoleCommand(TEXT("stat none"));
		ShowToast(TEXT("Performance-Anzeige aus"));
		break;
	}
}

void AVBHUD::ToggleDebugInfo()
{
	bShowDebugInfo = !bShowDebugInfo;
}

void AVBHUD::ShowToast(const FString& Message, float Seconds)
{
	ToastText = Message;
	ToastEndTime = GetWorld() ? GetWorld()->GetRealTimeSeconds() + Seconds : 0.0;
}

void AVBHUD::DrawPanel(const FString& Text, float X, float Y, UFont* Font, float Scale, bool bCenterX, const FLinearColor& TextColor)
{
	float Width = 0.f;
	float Height = 0.f;
	GetTextSize(Text, Width, Height, Font, Scale);

	const float PadX = VBHUDStyle::PaddingX * Scale;
	const float PadY = VBHUDStyle::PaddingY * Scale;
	const float Left = bCenterX ? X - (Width * 0.5f) - PadX : X;

	DrawRect(VBHUDStyle::PanelColor, Left, Y, Width + PadX * 2.f, Height + PadY * 2.f);
	DrawText(Text, TextColor, Left + PadX, Y + PadY, Font, Scale);
}

void AVBHUD::DrawInteractionPrompt(float UIScale)
{
	const AVBPlayerCharacter* Player = PlayerOwner ? Cast<AVBPlayerCharacter>(PlayerOwner->GetPawn()) : nullptr;
	if (!Player || !Player->Interaction)
	{
		return;
	}

	const FText Prompt = Player->Interaction->GetFocusedPrompt();
	if (Prompt.IsEmpty())
	{
		return;
	}

	const FString Line = FString::Printf(TEXT("[E]  %s"), *Prompt.ToString());
	DrawPanel(Line, Canvas->ClipX * 0.5f, Canvas->ClipY * 0.72f, GEngine->GetMediumFont(), UIScale, true);
}

void AVBHUD::DrawVehicleHUD(float UIScale)
{
	const AVBVehicle* Vehicle = PlayerOwner ? Cast<AVBVehicle>(PlayerOwner->GetPawn()) : nullptr;
	if (!Vehicle)
	{
		return;
	}

	const float Speed = FMath::Abs(Vehicle->GetSpeedKmh());
	const int32 Gear = Vehicle->GetCurrentGear();
	const FString GearText = Gear < 0 ? TEXT("R") : (Gear == 0 ? TEXT("N") : FString::FromInt(Gear));
	const TCHAR* LightText = Vehicle->GetHeadlightMode() == EVBHeadlightMode::Auto ? TEXT("Licht Auto")
		: (Vehicle->GetHeadlightMode() == EVBHeadlightMode::On ? TEXT("Licht An") : TEXT("Licht Aus"));

	const FString SpeedText = FString::Printf(TEXT("%3.0f"), Speed);
	UFont* Large = GEngine->GetLargeFont();
	UFont* Small = GEngine->GetSmallFont();
	const float Scale = UIScale * 2.2f;
	float Width = 0.f;
	float Height = 0.f;
	GetTextSize(SpeedText, Width, Height, Large, Scale);

	const float Right = Canvas->ClipX - 40.f * UIScale;
	const float Bottom = Canvas->ClipY - 40.f * UIScale;
	const float BoxW = FMath::Max(Width + 40.f * UIScale, 470.f * UIScale);
	const float BoxH = Height + 60.f * UIScale;
	DrawRect(VBHUDStyle::PanelColor, Right - BoxW, Bottom - BoxH, BoxW, BoxH);
	DrawText(SpeedText, FLinearColor::White, Right - 20.f * UIScale - Width, Bottom - BoxH + 8.f * UIScale, Large, Scale);
	DrawText(FString::Printf(TEXT("km/h   Gang %s   %.0f U/min"), *GearText, Vehicle->GetEngineRPM()), VBHUDStyle::Muted,
		Right - BoxW + 16.f * UIScale, Bottom - 44.f * UIScale, Small, UIScale);
	DrawText(FString::Printf(TEXT("%s   [L] Licht  [C] Kamera  [R] Aufrichten  [E] Aussteigen"), LightText), VBHUDStyle::Muted,
		Right - BoxW + 16.f * UIScale, Bottom - 24.f * UIScale, Small, UIScale * 0.85f);
}

void AVBHUD::DrawToast(float UIScale)
{
	const UWorld* World = GetWorld();
	if (ToastText.IsEmpty() || !World || World->GetRealTimeSeconds() > ToastEndTime)
	{
		return;
	}
	DrawPanel(ToastText, Canvas->ClipX * 0.5f, Canvas->ClipY * 0.08f, GEngine->GetMediumFont(), UIScale, true, VBHUDStyle::Accent);
}

void AVBHUD::DrawPauseOverlay(float UIScale)
{
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.35f), 0.f, 0.f, Canvas->ClipX, Canvas->ClipY);
	DrawPanel(TEXT("PAUSIERT  -  [P] / [Esc] fortsetzen"), Canvas->ClipX * 0.5f, Canvas->ClipY * 0.45f, GEngine->GetLargeFont(), UIScale, true);
}

void AVBHUD::DrawSetupHint(float UIScale)
{
	const AVBPlayerCharacter* Player = PlayerOwner ? Cast<AVBPlayerCharacter>(PlayerOwner->GetPawn()) : nullptr;
	if (!Player || Player->HasCharacterMesh())
	{
		return;
	}
	DrawPanel(TEXT("Kein Spieler-Mesh: Third Person Pack hinzufuegen, dann Menue 'Veyra Bay -> 1. Projekt einrichten'"),
		Canvas->ClipX * 0.5f, Canvas->ClipY * 0.9f, GEngine->GetSmallFont(), UIScale, true, VBHUDStyle::Accent);
}

void AVBHUD::DrawDebugInfo(float UIScale)
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	TArray<FString> Lines;

	if (const UVBTimeOfDaySubsystem* Time = World->GetSubsystem<UVBTimeOfDaySubsystem>())
	{
		Lines.Add(FString::Printf(TEXT("Zeit       %s  (%s)%s"), *Time->GetClockString(),
			*UVBTimeOfDaySubsystem::PhaseToString(Time->GetDayPhase()), Time->IsTimePaused() ? TEXT("  [angehalten]") : TEXT("")));
		Lines.Add(FString::Printf(TEXT("Sonne      %.1f Grad   Nacht %.2f"), Time->GetSunElevationDegrees(), Time->GetNightFactor()));
	}

	if (const UVBWeatherSubsystem* Weather = World->GetSubsystem<UVBWeatherSubsystem>())
	{
		const FVBWeatherState State = Weather->GetCurrentState();
		Lines.Add(FString::Printf(TEXT("Wetter     %s%s"), *VBWeather::ToString(Weather->GetWeather()),
			Weather->IsDynamicWeatherEnabled() ? TEXT("  (dynamisch)") : TEXT("")));
		Lines.Add(FString::Printf(TEXT("Regen %.2f  Naesse %.2f  Pfuetzen %.2f  Wind %.2f"),
			State.RainIntensity, Weather->GetWetness(), Weather->GetPuddles(), State.WindStrength));
		Lines.Add(FString::Printf(TEXT("Fahrbahn-Grip  %.0f %%"), Weather->GetRoadGripMultiplier() * 100.f));
	}

	if (const UGameInstance* GameInstance = World->GetGameInstance())
	{
		if (const UVBGraphicsSubsystem* Graphics = GameInstance->GetSubsystem<UVBGraphicsSubsystem>())
		{
			Lines.Add(FString::Printf(TEXT("Grafik     %s"), *UVBGraphicsSubsystem::ModeToString(Graphics->GetGraphicsMode())));
		}
	}

	Lines.Add(TEXT(""));
	Lines.Add(TEXT("F2 Performance  F3 Info  F5 Wetter  F6/F7 Zeit -/+  F8 Zeit Stop  F9 Grafikmodus"));

	UFont* Font = GEngine->GetSmallFont();
	float Y = 24.f * UIScale;
	for (const FString& Line : Lines)
	{
		if (Line.IsEmpty())
		{
			Y += 8.f * UIScale;
			continue;
		}
		float Width = 0.f;
		float Height = 0.f;
		GetTextSize(Line, Width, Height, Font, UIScale);
		DrawRect(VBHUDStyle::PanelColor, 20.f * UIScale, Y, Width + 20.f * UIScale, Height + 6.f * UIScale);
		DrawText(Line, VBHUDStyle::Muted, 30.f * UIScale, Y + 3.f * UIScale, Font, UIScale);
		Y += Height + 8.f * UIScale;
	}
}
