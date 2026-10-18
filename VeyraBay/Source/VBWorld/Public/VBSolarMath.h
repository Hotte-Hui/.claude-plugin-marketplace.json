#pragma once

#include "CoreMinimal.h"

/**
 * Vereinfachtes astronomisches Sonnenmodell (Deklination + Stundenwinkel).
 * Weltkoordinaten: +X = Norden, +Y = Osten, +Z = oben (optional gedreht per NorthYawOffset).
 * Genau genug fuer glaubwuerdige Sonnenstaende, Tageslaengen und Jahreszeiten.
 */
namespace VBSolar
{
	/** Einheitsvektor von der Welt zur Sonne. */
	VBWORLD_API FVector ComputeSunDirection(float Hours, int32 DayOfYear, float LatitudeDeg, float NorthYawDeg);

	/** Einheitsvektor zum Mond (vereinfachte Bahn: grob gegenueber der Sonne, leicht versetzt). */
	VBWORLD_API FVector ComputeMoonDirection(const FVector& SunDirection);

	/** Hoehenwinkel eines Richtungsvektors ueber dem Horizont in Grad. */
	VBWORLD_API float ElevationDegrees(const FVector& Direction);

	/** 0 = voller Tag, 1 = volle Nacht. Weicher Uebergang in der Daemmerung (+6 Grad bis -8 Grad). */
	VBWORLD_API float NightFactorFromElevation(float SunElevationDeg);
}
