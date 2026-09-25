#pragma once

#include "CoreMinimal.h"
#include "Stats/Stats.h"

/**
 * Eigene Profiling-Gruppe: in der Konsole "stat VeyraBay" (Zeiten der Systeme pro Frame).
 * Budgets (Ziel 60 fps, Quality-Modus, RTX 4090): Verkehr < 0.6 ms, Passanten < 0.5 ms, Himmel/Wetter < 0.1 ms.
 */
DECLARE_STATS_GROUP(TEXT("VeyraBay"), STATGROUP_VeyraBay, STATCAT_Advanced);
