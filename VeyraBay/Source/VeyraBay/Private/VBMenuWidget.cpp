#include "VBMenuWidget.h"

#include "VBAudioSubsystem.h"
#include "VBGraphicsSubsystem.h"
#include "VBMissionSubsystem.h"
#include "VBPlayerController.h"
#include "VBWeatherSubsystem.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/Button.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "Kismet/KismetSystemLibrary.h"

namespace VBMenu
{
	static const FLinearColor Accent(1.f, 0.78f, 0.35f, 1.f);
	static const FLinearColor Muted(0.75f, 0.75f, 0.75f, 1.f);
}

TSharedRef<SWidget> UVBMenuWidget::RebuildWidget()
{
	if (WidgetTree && !WidgetTree->RootWidget)
	{
		UBorder* Background = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("Background"));
		Background->SetBrushColor(FLinearColor(0.f, 0.f, 0.f, 0.55f));
		Background->SetHorizontalAlignment(HAlign_Center);
		Background->SetVerticalAlignment(VAlign_Center);
		WidgetTree->RootWidget = Background;

		USizeBox* Size = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass(), TEXT("Size"));
		Size->SetWidthOverride(560.f);
		Background->SetContent(Size);

		UVerticalBox* Box = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("Box"));
		Size->SetContent(Box);

		AddText(Box, TEXT("VEYRA BAY"), 52, VBMenu::Accent);
		SubtitleText = AddText(Box, TEXT("Eine Stadt am Meer"), 18, VBMenu::Muted);

		UTextBlock* Text = nullptr;
		AddButton(Box, TEXT("Spielen"), Text)->OnClicked.AddDynamic(this, &UVBMenuWidget::OnResume);
		ResumeText = Text;
		AddButton(Box, TEXT(""), Text)->OnClicked.AddDynamic(this, &UVBMenuWidget::OnGraphics);
		GraphicsText = Text;
		AddButton(Box, TEXT(""), Text)->OnClicked.AddDynamic(this, &UVBMenuWidget::OnWeather);
		WeatherText = Text;
		AddButton(Box, TEXT(""), Text)->OnClicked.AddDynamic(this, &UVBMenuWidget::OnVolume);
		VolumeText = Text;
		AddButton(Box, TEXT("Mission neu starten"), Text)->OnClicked.AddDynamic(this, &UVBMenuWidget::OnRestartMission);
		RestartText = Text;
		AddButton(Box, TEXT("Neues Spiel (Missionen zuruecksetzen)"), Text)->OnClicked.AddDynamic(this, &UVBMenuWidget::OnNewGame);
		NewGameText = Text;
		AddButton(Box, TEXT("Beenden"), Text)->OnClicked.AddDynamic(this, &UVBMenuWidget::OnQuit);
		QuitText = Text;

		AddText(Box, TEXT("WASD bewegen  -  Maus schauen  -  E Einsteigen/Interagieren  -  P Pause"), 13, VBMenu::Muted);
		RefreshLabels();
	}
	return Super::RebuildWidget();
}

UTextBlock* UVBMenuWidget::AddText(UVerticalBox* Box, const FString& Text, int32 Size, const FLinearColor& Color)
{
	UTextBlock* Block = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
	Block->SetText(FText::FromString(Text));
	FSlateFontInfo Font = Block->GetFont();
	Font.Size = Size;
	Block->SetFont(Font);
	Block->SetColorAndOpacity(FSlateColor(Color));
	Block->SetJustification(ETextJustify::Center);
	if (UVerticalBoxSlot* BoxSlot = Box->AddChildToVerticalBox(Block))
	{
		BoxSlot->SetPadding(FMargin(0.f, 6.f));
		BoxSlot->SetHorizontalAlignment(HAlign_Center);
	}
	return Block;
}

UButton* UVBMenuWidget::AddButton(UVerticalBox* Box, const FString& Label, UTextBlock*& OutText)
{
	UButton* Button = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass());
	Button->SetBackgroundColor(FLinearColor(0.08f, 0.09f, 0.1f, 0.9f));
	UTextBlock* Text = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
	Text->SetText(FText::FromString(Label));
	FSlateFontInfo Font = Text->GetFont();
	Font.Size = 20;
	Text->SetFont(Font);
	Text->SetColorAndOpacity(FSlateColor(FLinearColor::White));
	Button->SetContent(Text);
	if (UVerticalBoxSlot* BoxSlot = Box->AddChildToVerticalBox(Button))
	{
		BoxSlot->SetPadding(FMargin(0.f, 5.f));
		BoxSlot->SetHorizontalAlignment(HAlign_Fill);
	}
	OutText = Text;
	return Button;
}

void UVBMenuWidget::SetStartScreen(bool bInStartScreen)
{
	bStartScreen = bInStartScreen;
	RefreshLabels();
}

void UVBMenuWidget::RefreshLabels()
{
	UWorld* World = GetWorld();
	if (!World || !GraphicsText)
	{
		return;
	}
	const UGameInstance* GameInstance = World->GetGameInstance();
	const UVBGraphicsSubsystem* Graphics = GameInstance ? GameInstance->GetSubsystem<UVBGraphicsSubsystem>() : nullptr;
	const UVBWeatherSubsystem* Weather = World->GetSubsystem<UVBWeatherSubsystem>();
	const UVBAudioSubsystem* Audio = World->GetSubsystem<UVBAudioSubsystem>();
	const UVBMissionSubsystem* Missions = World->GetSubsystem<UVBMissionSubsystem>();

	if (SubtitleText)
	{
		const FString Progress = Missions ? FString::Printf(TEXT("  -  Missionen %d/%d"), Missions->GetCompletedMissions(), Missions->GetMissionCount()) : FString();
		SubtitleText->SetText(FText::FromString((bStartScreen ? FString(TEXT("Eine Stadt am Meer")) : FString(TEXT("PAUSE"))) + Progress));
	}
	if (ResumeText)
	{
		ResumeText->SetText(FText::FromString(bStartScreen ? TEXT("Spielen") : TEXT("Weiter")));
	}
	GraphicsText->SetText(FText::FromString(FString::Printf(TEXT("Grafik: %s"),
		Graphics ? *UVBGraphicsSubsystem::ModeToString(Graphics->GetGraphicsMode()) : TEXT("-"))));
	WeatherText->SetText(FText::FromString(FString::Printf(TEXT("Dynamisches Wetter: %s"),
		(Weather && Weather->IsDynamicWeatherEnabled()) ? TEXT("An") : TEXT("Aus"))));
	VolumeText->SetText(FText::FromString(FString::Printf(TEXT("Umgebungsklang: %d %%"),
		Audio ? FMath::RoundToInt(Audio->GetAmbientVolume() * 100.f) : 100)));
}

void UVBMenuWidget::OnResume()
{
	if (AVBPlayerController* PC = Cast<AVBPlayerController>(GetOwningPlayer()))
	{
		PC->CloseMenu();
	}
}

void UVBMenuWidget::OnGraphics()
{
	if (UGameInstance* GameInstance = GetWorld() ? GetWorld()->GetGameInstance() : nullptr)
	{
		if (UVBGraphicsSubsystem* Graphics = GameInstance->GetSubsystem<UVBGraphicsSubsystem>())
		{
			Graphics->ToggleGraphicsMode();
		}
	}
	RefreshLabels();
}

void UVBMenuWidget::OnWeather()
{
	if (UVBWeatherSubsystem* Weather = GetWorld() ? GetWorld()->GetSubsystem<UVBWeatherSubsystem>() : nullptr)
	{
		Weather->SetDynamicWeatherEnabled(!Weather->IsDynamicWeatherEnabled());
	}
	RefreshLabels();
}

void UVBMenuWidget::OnVolume()
{
	if (UVBAudioSubsystem* Audio = GetWorld() ? GetWorld()->GetSubsystem<UVBAudioSubsystem>() : nullptr)
	{
		const float Current = Audio->GetAmbientVolume();
		Audio->SetAmbientVolume(Current <= 0.01f ? 1.f : Current - 0.25f);
	}
	RefreshLabels();
}

void UVBMenuWidget::OnRestartMission()
{
	if (UVBMissionSubsystem* Missions = GetWorld() ? GetWorld()->GetSubsystem<UVBMissionSubsystem>() : nullptr)
	{
		Missions->RestartMission();
	}
	OnResume();
}

void UVBMenuWidget::OnNewGame()
{
	if (UVBMissionSubsystem* Missions = GetWorld() ? GetWorld()->GetSubsystem<UVBMissionSubsystem>() : nullptr)
	{
		Missions->ResetProgress();
	}
	OnResume();
}

void UVBMenuWidget::OnQuit()
{
	UKismetSystemLibrary::QuitGame(this, GetOwningPlayer(), EQuitPreference::Quit, false);
}
