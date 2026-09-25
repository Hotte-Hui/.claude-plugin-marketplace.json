#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "VBInputSet.generated.h"

class UInputAction;
class UInputMappingContext;

/**
 * Alle Eingabeaktionen des Spiels, zur Laufzeit in C++ erzeugt (Enhanced Input).
 * Dadurch funktioniert die Steuerung sofort ohne .uasset-Dateien; spaeter koennen
 * die Aktionen 1:1 durch Assets fuer frei belegbare Tasten ersetzt werden.
 */
UCLASS()
class VEYRABAY_API UVBInputSet : public UObject
{
	GENERATED_BODY()

public:
	void Build();

	UPROPERTY() TObjectPtr<UInputMappingContext> GameplayContext;
	UPROPERTY() TObjectPtr<UInputMappingContext> DebugContext;
	/** Ersetzt GameplayContext, solange der Spieler ein Fahrzeug steuert. */
	UPROPERTY() TObjectPtr<UInputMappingContext> VehicleContext;

	// --- Gameplay --------------------------------------------------------
	UPROPERTY() TObjectPtr<UInputAction> Move;
	UPROPERTY() TObjectPtr<UInputAction> Look;
	UPROPERTY() TObjectPtr<UInputAction> LookGamepad;
	UPROPERTY() TObjectPtr<UInputAction> Jump;
	UPROPERTY() TObjectPtr<UInputAction> Sprint;
	UPROPERTY() TObjectPtr<UInputAction> WalkToggle;
	UPROPERTY() TObjectPtr<UInputAction> Interact;
	UPROPERTY() TObjectPtr<UInputAction> Pause;

	// --- Fahrzeug -------------------------------------------------------------
	UPROPERTY() TObjectPtr<UInputAction> Throttle;
	UPROPERTY() TObjectPtr<UInputAction> Brake;
	UPROPERTY() TObjectPtr<UInputAction> Steer;
	UPROPERTY() TObjectPtr<UInputAction> Handbrake;
	UPROPERTY() TObjectPtr<UInputAction> ExitVehicle;
	UPROPERTY() TObjectPtr<UInputAction> VehicleLights;
	UPROPERTY() TObjectPtr<UInputAction> VehicleReset;
	UPROPERTY() TObjectPtr<UInputAction> VehicleCamera;

	// --- Entwickler-Tasten (nicht in Shipping-Builds) ------------------------
	UPROPERTY() TObjectPtr<UInputAction> DebugPerf;
	UPROPERTY() TObjectPtr<UInputAction> DebugInfo;
	UPROPERTY() TObjectPtr<UInputAction> DebugNextWeather;
	UPROPERTY() TObjectPtr<UInputAction> DebugTimeBack;
	UPROPERTY() TObjectPtr<UInputAction> DebugTimeForward;
	UPROPERTY() TObjectPtr<UInputAction> DebugTimePause;
	UPROPERTY() TObjectPtr<UInputAction> DebugGraphicsMode;
};
