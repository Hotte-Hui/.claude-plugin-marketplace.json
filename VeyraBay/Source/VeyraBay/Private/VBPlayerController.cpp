#include "VBPlayerController.h"

#include "VBGraphicsSubsystem.h"
#include "VBHUD.h"
#include "VBInputSet.h"
#include "VBTimeOfDaySubsystem.h"
#include "VBVehicle.h"
#include "VBWeatherSubsystem.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/GameInstance.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "InputActionValue.h"
#include "Kismet/GameplayStatics.h"

UVBInputSet* AVBPlayerController::GetInputSet()
{
	if (!InputSet)
	{
		InputSet = NewObject<UVBInputSet>(this, TEXT("VBInputSet"));
		InputSet->Build();
	}
	return InputSet;
}

void AVBPlayerController::BeginPlay()
{
	Super::BeginPlay();

	if (IsLocalController())
	{
		SetInputMode(FInputModeGameOnly());
		SetShowMouseCursor(false);
	}
}

void AVBPlayerController::SetupInputComponent()
{
	Super::SetupInputComponent();

	UVBInputSet* Set = GetInputSet();

	if (ULocalPlayer* LocalPlayer = GetLocalPlayer())
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>())
		{
			Subsystem->AddMappingContext(Cast<AVBVehicle>(GetPawn()) ? Set->VehicleContext : Set->GameplayContext, 0);
#if !UE_BUILD_SHIPPING
			Subsystem->AddMappingContext(Set->DebugContext, 1);
#endif
		}
	}

	UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(InputComponent);
	if (!Input)
	{
		return;
	}

	Input->BindAction(Set->Pause, ETriggerEvent::Started, this, &AVBPlayerController::Input_Pause);

#if !UE_BUILD_SHIPPING
	Input->BindAction(Set->DebugPerf, ETriggerEvent::Started, this, &AVBPlayerController::Debug_CyclePerf);
	Input->BindAction(Set->DebugInfo, ETriggerEvent::Started, this, &AVBPlayerController::Debug_ToggleInfo);
	Input->BindAction(Set->DebugNextWeather, ETriggerEvent::Started, this, &AVBPlayerController::Debug_NextWeather);
	Input->BindAction(Set->DebugTimeBack, ETriggerEvent::Started, this, &AVBPlayerController::Debug_TimeBack);
	Input->BindAction(Set->DebugTimeForward, ETriggerEvent::Started, this, &AVBPlayerController::Debug_TimeForward);
	Input->BindAction(Set->DebugTimePause, ETriggerEvent::Started, this, &AVBPlayerController::Debug_TimePause);
	Input->BindAction(Set->DebugGraphicsMode, ETriggerEvent::Started, this, &AVBPlayerController::Debug_GraphicsMode);
#endif
}

void AVBPlayerController::OnPossess(APawn* InPawn)
{
	Super::OnPossess(InPawn);
	UpdateMappingContexts(InPawn);
}

void AVBPlayerController::UpdateMappingContexts(APawn* ForPawn)
{
	ULocalPlayer* LocalPlayer = GetLocalPlayer();
	UEnhancedInputLocalPlayerSubsystem* Subsystem = LocalPlayer ? LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
	if (!Subsystem)
	{
		return;
	}
	UVBInputSet* Set = GetInputSet();
	const bool bInVehicle = Cast<AVBVehicle>(ForPawn) != nullptr;
	Subsystem->RemoveMappingContext(bInVehicle ? Set->GameplayContext : Set->VehicleContext);
	if (!Subsystem->HasMappingContext(bInVehicle ? Set->VehicleContext : Set->GameplayContext))
	{
		Subsystem->AddMappingContext(bInVehicle ? Set->VehicleContext : Set->GameplayContext, 0);
	}
}

AVBHUD* AVBPlayerController::GetVBHUD() const
{
	return Cast<AVBHUD>(GetHUD());
}

void AVBPlayerController::Input_Pause(const FInputActionValue& Value)
{
	const bool bPause = !IsPaused();
	UGameplayStatics::SetGamePaused(this, bPause);
}

void AVBPlayerController::Debug_CyclePerf(const FInputActionValue& Value)
{
	if (AVBHUD* HUD = GetVBHUD())
	{
		HUD->CyclePerfOverlay();
	}
}

void AVBPlayerController::Debug_ToggleInfo(const FInputActionValue& Value)
{
	if (AVBHUD* HUD = GetVBHUD())
	{
		HUD->ToggleDebugInfo();
	}
}

void AVBPlayerController::Debug_NextWeather(const FInputActionValue& Value)
{
	if (UVBWeatherSubsystem* Weather = GetWorld()->GetSubsystem<UVBWeatherSubsystem>())
	{
		Weather->CycleWeather();
		if (AVBHUD* HUD = GetVBHUD())
		{
			HUD->ShowToast(FString::Printf(TEXT("Wetter: %s"), *VBWeather::ToString(Weather->GetWeather())));
		}
	}
}

void AVBPlayerController::ShiftTime(float DeltaHours)
{
	if (UVBTimeOfDaySubsystem* Time = GetWorld()->GetSubsystem<UVBTimeOfDaySubsystem>())
	{
		Time->SetTimeOfDay(Time->GetTimeOfDay() + DeltaHours);
		if (AVBHUD* HUD = GetVBHUD())
		{
			HUD->ShowToast(FString::Printf(TEXT("Uhrzeit: %s"), *Time->GetClockString()));
		}
	}
}

void AVBPlayerController::Debug_TimeBack(const FInputActionValue& Value)
{
	ShiftTime(-1.f);
}

void AVBPlayerController::Debug_TimeForward(const FInputActionValue& Value)
{
	ShiftTime(1.f);
}

void AVBPlayerController::Debug_TimePause(const FInputActionValue& Value)
{
	if (UVBTimeOfDaySubsystem* Time = GetWorld()->GetSubsystem<UVBTimeOfDaySubsystem>())
	{
		Time->SetTimePaused(!Time->IsTimePaused());
		if (AVBHUD* HUD = GetVBHUD())
		{
			HUD->ShowToast(Time->IsTimePaused() ? TEXT("Tageszeit angehalten") : TEXT("Tageszeit laeuft"));
		}
	}
}

void AVBPlayerController::Debug_GraphicsMode(const FInputActionValue& Value)
{
	UGameInstance* GameInstance = GetGameInstance();
	if (UVBGraphicsSubsystem* Graphics = GameInstance ? GameInstance->GetSubsystem<UVBGraphicsSubsystem>() : nullptr)
	{
		Graphics->ToggleGraphicsMode();
		if (AVBHUD* HUD = GetVBHUD())
		{
			HUD->ShowToast(FString::Printf(TEXT("Grafikmodus: %s"), *UVBGraphicsSubsystem::ModeToString(Graphics->GetGraphicsMode())));
		}
	}
}
