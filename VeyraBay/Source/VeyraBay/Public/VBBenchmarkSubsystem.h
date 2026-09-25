#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "VBBenchmarkSubsystem.generated.h"

class ACameraActor;

/**
 * Automatischer Benchmark (Phase 8): Kameraflug durch die Stadt (Promenade, Strassenschlucht, Hochhaeuser, Marina),
 * misst Frame-, Game-, Render- und GPU-Zeiten und schreibt Saved/Benchmarks/<Karte>_<Modus>_<Datum>.csv + Zusammenfassung.
 *
 * Konsole:  vb.Benchmark            90 s im aktuellen Grafikmodus
 *           vb.Benchmark 60 all     je 60 s in QUALITY und PERFORMANCE nacheinander
 */
UCLASS()
class VEYRABAY_API UVBBenchmarkSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Benchmark")
	void StartBenchmark(float Seconds = 90.f, bool bInBothModes = false);

	UFUNCTION(BlueprintCallable, Category = "VeyraBay|Benchmark")
	void StopBenchmark();

	UFUNCTION(BlueprintPure, Category = "VeyraBay|Benchmark")
	bool IsRunning() const { return bRunning; }

	/** Letzte Zusammenfassung (fuer das HUD). */
	UFUNCTION(BlueprintPure, Category = "VeyraBay|Benchmark")
	FString GetLastSummary() const { return LastSummary; }

private:
	struct FSample
	{
		float Time;
		float FrameMs;
		float GameMs;
		float RenderMs;
		float GpuMs;
	};

	void BuildPath();
	FVector PathPoint(float Alpha) const;
	void Finish();
	void WriteResults();

	TArray<FVector> Waypoints;
	TArray<FSample> Samples;
	TWeakObjectPtr<ACameraActor> Camera;
	TWeakObjectPtr<AActor> PreviousViewTarget;
	float Duration = 90.f;
	float Elapsed = 0.f;
	float WarmUp = 3.f;
	bool bRunning = false;
	bool bSecondPass = false;
	bool bBothModes = false;
	FString LastSummary;
};
