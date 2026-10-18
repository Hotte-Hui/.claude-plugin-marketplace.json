#include "VBWeatherTypes.h"

FVBWeatherState FVBWeatherState::Lerp(const FVBWeatherState& A, const FVBWeatherState& B, float Alpha)
{
	FVBWeatherState Out;
	Out.CloudCoverage = FMath::Lerp(A.CloudCoverage, B.CloudCoverage, Alpha);
	Out.RainIntensity = FMath::Lerp(A.RainIntensity, B.RainIntensity, Alpha);
	Out.FogDensityScale = FMath::Lerp(A.FogDensityScale, B.FogDensityScale, Alpha);
	Out.WindStrength = FMath::Lerp(A.WindStrength, B.WindStrength, Alpha);
	Out.SunTransmission = FMath::Lerp(A.SunTransmission, B.SunTransmission, Alpha);
	Out.LightningPerMinute = FMath::Lerp(A.LightningPerMinute, B.LightningPerMinute, Alpha);
	return Out;
}

FVBWeatherState FVBWeatherState::GetPreset(EVBWeatherType Type)
{
	FVBWeatherState S;
	switch (Type)
	{
	case EVBWeatherType::Clear:
		S.CloudCoverage = 0.15f; S.RainIntensity = 0.f;  S.FogDensityScale = 1.0f; S.WindStrength = 0.2f;  S.SunTransmission = 1.0f;  S.LightningPerMinute = 0.f;
		break;
	case EVBWeatherType::Overcast:
		S.CloudCoverage = 0.85f; S.RainIntensity = 0.f;  S.FogDensityScale = 1.8f; S.WindStrength = 0.35f; S.SunTransmission = 0.18f; S.LightningPerMinute = 0.f;
		break;
	case EVBWeatherType::LightRain:
		S.CloudCoverage = 0.92f; S.RainIntensity = 0.3f; S.FogDensityScale = 2.5f; S.WindStrength = 0.4f;  S.SunTransmission = 0.1f;  S.LightningPerMinute = 0.f;
		break;
	case EVBWeatherType::HeavyRain:
		S.CloudCoverage = 1.0f;  S.RainIntensity = 0.85f; S.FogDensityScale = 4.0f; S.WindStrength = 0.6f; S.SunTransmission = 0.04f; S.LightningPerMinute = 0.f;
		break;
	case EVBWeatherType::Fog:
		S.CloudCoverage = 0.6f;  S.RainIntensity = 0.f;  S.FogDensityScale = 12.f; S.WindStrength = 0.05f; S.SunTransmission = 0.3f;  S.LightningPerMinute = 0.f;
		break;
	case EVBWeatherType::Storm:
		S.CloudCoverage = 1.0f;  S.RainIntensity = 1.0f; S.FogDensityScale = 5.0f; S.WindStrength = 1.0f;  S.SunTransmission = 0.02f; S.LightningPerMinute = 4.f;
		break;
	default:
		break;
	}
	return S;
}

namespace VBWeather
{
	FString ToString(EVBWeatherType Type)
	{
		if (const UEnum* Enum = StaticEnum<EVBWeatherType>())
		{
			return Enum->GetNameStringByValue(static_cast<int64>(Type));
		}
		return TEXT("Unknown");
	}

	bool FromString(const FString& Text, EVBWeatherType& OutType)
	{
		for (int32 Index = 0; Index < static_cast<int32>(EVBWeatherType::Count); ++Index)
		{
			const EVBWeatherType Candidate = static_cast<EVBWeatherType>(Index);
			if (ToString(Candidate).Equals(Text, ESearchCase::IgnoreCase) || Text == FString::FromInt(Index))
			{
				OutType = Candidate;
				return true;
			}
		}
		return false;
	}
}
