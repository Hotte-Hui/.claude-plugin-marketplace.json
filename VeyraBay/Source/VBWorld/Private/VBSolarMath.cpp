#include "VBSolarMath.h"

namespace VBSolar
{
	FVector ComputeSunDirection(float Hours, int32 DayOfYear, float LatitudeDeg, float NorthYawDeg)
	{
		// Sonnendeklination (Cooper-Naeherung)
		const float Declination = FMath::DegreesToRadians(23.44f) * FMath::Sin(2.f * UE_PI * (284.f + static_cast<float>(DayOfYear)) / 365.f);
		// Stundenwinkel: 15 Grad pro Stunde, 0 um 12 Uhr Sonnenzeit
		const float HourAngle = FMath::DegreesToRadians(15.f * (Hours - 12.f));
		const float Latitude = FMath::DegreesToRadians(LatitudeDeg);

		const float SinDec = FMath::Sin(Declination);
		const float CosDec = FMath::Cos(Declination);
		const float SinLat = FMath::Sin(Latitude);
		const float CosLat = FMath::Cos(Latitude);
		const float CosH = FMath::Cos(HourAngle);
		const float SinH = FMath::Sin(HourAngle);

		// Lokales Horizontsystem (Ost / Nord / Oben)
		const float East = -CosDec * SinH;
		const float North = SinDec * CosLat - CosDec * CosH * SinLat;
		const float Up = SinDec * SinLat + CosDec * CosH * CosLat;

		const FVector Direction = FVector(North, East, Up).RotateAngleAxis(NorthYawDeg, FVector::UpVector);
		return Direction.GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
	}

	FVector ComputeMoonDirection(const FVector& SunDirection)
	{
		// Gegenueber der Sonne, um 18 Grad versetzt, damit Mondschatten nicht exakt mit der Sonnenachse fluchten.
		return (-SunDirection).RotateAngleAxis(18.f, FVector::UpVector).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
	}

	float ElevationDegrees(const FVector& Direction)
	{
		return FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(static_cast<float>(Direction.Z), -1.f, 1.f)));
	}

	float NightFactorFromElevation(float SunElevationDeg)
	{
		return 1.f - FMath::SmoothStep(-8.f, 6.f, SunElevationDeg);
	}
}
