#pragma once

#include "CoreMinimal.h"

class UWorld;

/**
 * Zugriff auf die globale Material Parameter Collection (MPC_VB_World).
 * Alle Master-Materialien lesen daraus Naesse, Pfuetzen, Wind, Tageszeit usw.
 * Fehlt die MPC oder ein Parameter, passiert nichts (kein Log-Spam).
 */
namespace VBWorldParams
{
	// Skalare Parameternamen (muessen mit dem Setup-Skript uebereinstimmen)
	extern VBWORLD_API const FName TimeOfDay01;
	extern VBWORLD_API const FName NightFactor;
	extern VBWORLD_API const FName SunElevation;
	extern VBWORLD_API const FName Wetness;
	extern VBWORLD_API const FName Puddles;
	extern VBWORLD_API const FName RainIntensity;
	extern VBWORLD_API const FName WindStrength;
	extern VBWORLD_API const FName CloudCoverage;
	extern VBWORLD_API const FName FogAmount;
	extern VBWORLD_API const FName LightningFlash;
	// Vektor-Parameter
	extern VBWORLD_API const FName WindDirection;

	VBWORLD_API void SetScalar(UWorld* World, FName Name, float Value);
	VBWORLD_API void SetVector(UWorld* World, FName Name, const FLinearColor& Value);
}
