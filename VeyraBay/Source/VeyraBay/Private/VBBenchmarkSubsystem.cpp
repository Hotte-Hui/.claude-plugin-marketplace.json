#include "VBBenchmarkSubsystem.h"

#include "VBGraphicsSubsystem.h"
#include "VBHUD.h"
#include "VBLog.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerStart.h"
#include "HAL/IConsoleManager.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "RenderCore.h"
#include "RHI.h"

namespace VBBench
{
	// Stadtrundflug (Meter, Unreal-Koordinaten; passt zu vb_cityplan.py): Promenade -> Strassenschlucht
	// in der Altstadt -> ueber die Bayfront-Hochhaeuser -> Strandviertel -> Marina
	static const FVector CityTour[] = {
		FVector(-600.f, -110.f, 6.f), FVector(-250.f, -108.f, 6.f), FVector(20.f, -60.f, 5.f), FVector(39.78f, 60.f, 4.f),
		FVector(39.78f, 320.f, 4.f), FVector(60.f, 560.f, 25.f), FVector(400.f, 820.f, 140.f), FVector(1000.f, 700.f, 110.f),
		FVector(1500.f, 250.f, 60.f), FVector(2100.f, -40.f, 25.f), FVector(2700.f, -130.f, 10.f),
	};

	static float Percentile(TArray<float> Values, float P)
	{
		if (Values.Num() == 0)
		{
			return 0.f;
		}
		Values.Sort();
		const int32 Index = FMath::Clamp(FMath::FloorToInt(P * (Values.Num() - 1)), 0, Values.Num() - 1);
		return Values[Index];
	}

	static FAutoConsoleCommandWithWorldAndArgs BenchmarkCommand(
		TEXT("vb.Benchmark"),
		TEXT("Kameraflug-Benchmark. vb.Benchmark [Sekunden] [all] - 'all' misst QUALITY und PERFORMANCE nacheinander."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			UVBBenchmarkSubsystem* Bench = World ? World->GetSubsystem<UVBBenchmarkSubsystem>() : nullptr;
			if (!Bench)
			{
				return;
			}
			if (Bench->IsRunning())
			{
				Bench->StopBenchmark();
				return;
			}
			const float Seconds = Args.Num() > 0 ? FMath::Max(FCString::Atof(*Args[0]), 10.f) : 90.f;
			const bool bAll = Args.ContainsByPredicate([](const FString& Arg) { return Arg.Equals(TEXT("all"), ESearchCase::IgnoreCase); });
			Bench->StartBenchmark(Seconds, bAll);
		}));
}

bool UVBBenchmarkSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UVBBenchmarkSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UVBBenchmarkSubsystem, STATGROUP_Tickables);
}

void UVBBenchmarkSubsystem::BuildPath()
{
	Waypoints.Reset();
	UWorld* World = GetWorld();
	const bool bCity = World && World->GetMapName().Contains(TEXT("L_VB_City"));
	if (bCity)
	{
		for (const FVector& Point : VBBench::CityTour)
		{
			Waypoints.Add(Point * 100.f);
		}
		return;
	}
	// Andere Karten: Kreis um den Spielerstart (100 m Radius, 25 m hoch)
	FVector Center = FVector::ZeroVector;
	for (TActorIterator<APlayerStart> It(World); It; ++It)
	{
		Center = It->GetActorLocation();
		break;
	}
	for (int32 Step = 0; Step <= 12; ++Step)
	{
		const float Angle = 2.f * PI * Step / 12.f;
		Waypoints.Add(Center + FVector(FMath::Cos(Angle) * 10000.f, FMath::Sin(Angle) * 10000.f, 2500.f + 1500.f * FMath::Sin(Angle * 2.f)));
	}
}

FVector UVBBenchmarkSubsystem::PathPoint(float Alpha) const
{
	// Catmull-Rom durch alle Wegpunkte
	const int32 Segments = Waypoints.Num() - 1;
	if (Segments < 1)
	{
		return Waypoints.Num() ? Waypoints[0] : FVector::ZeroVector;
	}
	const float Scaled = FMath::Clamp(Alpha, 0.f, 1.f) * Segments;
	const int32 Index = FMath::Min(FMath::FloorToInt(Scaled), Segments - 1);
	const float T = Scaled - Index;
	const FVector& P0 = Waypoints[FMath::Max(Index - 1, 0)];
	const FVector& P1 = Waypoints[Index];
	const FVector& P2 = Waypoints[Index + 1];
	const FVector& P3 = Waypoints[FMath::Min(Index + 2, Segments)];
	const float T2 = T * T;
	const float T3 = T2 * T;
	return 0.5f * ((2.f * P1) + (-P0 + P2) * T + (2.f * P0 - 5.f * P1 + 4.f * P2 - P3) * T2 + (-P0 + 3.f * P1 - 3.f * P2 + P3) * T3);
}

void UVBBenchmarkSubsystem::StartBenchmark(float Seconds, bool bInBothModes)
{
	UWorld* World = GetWorld();
	APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
	if (!PC || bRunning)
	{
		return;
	}
	BuildPath();
	Duration = Seconds;
	Elapsed = 0.f;
	Samples.Reset();
	bBothModes = bInBothModes;
	bRunning = true;

	if (!Camera.IsValid())
	{
		FActorSpawnParameters Params;
		Params.ObjectFlags |= RF_Transient;
		ACameraActor* NewCamera = World->SpawnActor<ACameraActor>(PathPoint(0.f), FRotator::ZeroRotator, Params);
		NewCamera->GetCameraComponent()->SetFieldOfView(80.f);
		NewCamera->GetCameraComponent()->bConstrainAspectRatio = false;
		Camera = NewCamera;
	}
	if (PC->GetViewTarget() != Camera.Get())
	{
		PreviousViewTarget = PC->GetViewTarget();
	}
	PC->SetViewTarget(Camera.Get());
	PC->SetIgnoreMoveInput(true);
	PC->SetIgnoreLookInput(true);
	if (AVBHUD* HUD = Cast<AVBHUD>(PC->GetHUD()))
	{
		HUD->ShowToast(FString::Printf(TEXT("Benchmark laeuft (%.0f s) - vb.Benchmark bricht ab"), Duration), 4.f);
	}
	UE_LOG(LogVB, Log, TEXT("Benchmark gestartet: %.0f s, %d Wegpunkte"), Duration, Waypoints.Num());
}

void UVBBenchmarkSubsystem::StopBenchmark()
{
	if (bRunning)
	{
		bBothModes = false;
		Finish();
	}
}

void UVBBenchmarkSubsystem::Tick(float DeltaTime)
{
	if (!bRunning)
	{
		return;
	}
	Elapsed += DeltaTime;
	const float Alpha = Elapsed / Duration;
	if (ACameraActor* Cam = Camera.Get())
	{
		const FVector Position = PathPoint(Alpha);
		const FVector Ahead = PathPoint(FMath::Min(Alpha + 0.02f, 1.f));
		FRotator Rotation = (Ahead - Position).Rotation();
		Rotation.Pitch = FMath::Clamp(Rotation.Pitch - 8.f, -45.f, 20.f);
		Cam->SetActorLocationAndRotation(Position, Rotation);
	}

	if (Elapsed > WarmUp)
	{
		FSample Sample;
		Sample.Time = Elapsed;
		Sample.FrameMs = DeltaTime * 1000.f;
		Sample.GameMs = FPlatformTime::ToMilliseconds(GGameThreadTime);
		Sample.RenderMs = FPlatformTime::ToMilliseconds(GRenderThreadTime);
		Sample.GpuMs = FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles(0));
		Samples.Add(Sample);
	}
	if (Elapsed >= Duration)
	{
		Finish();
	}
}

void UVBBenchmarkSubsystem::Finish()
{
	WriteResults();
	bRunning = false;

	UWorld* World = GetWorld();
	APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
	UGameInstance* GameInstance = World ? World->GetGameInstance() : nullptr;
	UVBGraphicsSubsystem* Graphics = GameInstance ? GameInstance->GetSubsystem<UVBGraphicsSubsystem>() : nullptr;

	// Zweiter Durchlauf im anderen Grafikmodus
	if (bBothModes && !bSecondPass && Graphics)
	{
		bSecondPass = true;
		Graphics->ToggleGraphicsMode();
		StartBenchmark(Duration, true);
		return;
	}
	if (bSecondPass && Graphics)
	{
		Graphics->ToggleGraphicsMode();   // urspruenglichen Modus wiederherstellen
	}
	bSecondPass = false;
	bBothModes = false;

	if (PC)
	{
		PC->SetViewTarget(PreviousViewTarget.IsValid() ? PreviousViewTarget.Get() : PC->GetPawn());
		PC->SetIgnoreMoveInput(false);
		PC->SetIgnoreLookInput(false);
		if (AVBHUD* HUD = Cast<AVBHUD>(PC->GetHUD()))
		{
			HUD->ShowToast(LastSummary, 12.f);
		}
	}
	if (ACameraActor* Cam = Camera.Get())
	{
		Cam->Destroy();
	}
	Camera.Reset();
}

void UVBBenchmarkSubsystem::WriteResults()
{
	if (Samples.Num() == 0)
	{
		LastSummary = TEXT("Benchmark: keine Messwerte");
		return;
	}
	TArray<float> Frames, Game, Render, Gpu;
	FString Csv = TEXT("time_s,frame_ms,game_ms,render_ms,gpu_ms\n");
	for (const FSample& Sample : Samples)
	{
		Frames.Add(Sample.FrameMs);
		Game.Add(Sample.GameMs);
		Render.Add(Sample.RenderMs);
		Gpu.Add(Sample.GpuMs);
		Csv += FString::Printf(TEXT("%.3f,%.3f,%.3f,%.3f,%.3f\n"), Sample.Time, Sample.FrameMs, Sample.GameMs, Sample.RenderMs, Sample.GpuMs);
	}
	auto Average = [](const TArray<float>& Values)
	{
		double Sum = 0.0;
		for (float Value : Values)
		{
			Sum += Value;
		}
		return Values.Num() ? static_cast<float>(Sum / Values.Num()) : 0.f;
	};
	const float AvgFrame = Average(Frames);
	const float P99Frame = VBBench::Percentile(Frames, 0.99f);

	UGameInstance* GameInstance = GetWorld() ? GetWorld()->GetGameInstance() : nullptr;
	const UVBGraphicsSubsystem* Graphics = GameInstance ? GameInstance->GetSubsystem<UVBGraphicsSubsystem>() : nullptr;
	const FString Mode = Graphics ? UVBGraphicsSubsystem::ModeToString(Graphics->GetGraphicsMode()) : TEXT("Unbekannt");

	LastSummary = FString::Printf(TEXT("Benchmark %s: %.1f fps (%.2f ms), 1%% low %.1f fps | Game %.2f  Render %.2f  GPU %.2f ms"),
		*Mode, 1000.f / FMath::Max(AvgFrame, 0.01f), AvgFrame, 1000.f / FMath::Max(P99Frame, 0.01f), Average(Game), Average(Render),
		Average(Gpu));

	const FString Folder = FPaths::ProjectSavedDir() / TEXT("Benchmarks");
	const FString Base = FString::Printf(TEXT("%s_%s_%s"), *GetWorld()->GetMapName(), *Mode, *FDateTime::Now().ToString(TEXT("%Y%m%d_%H%M%S")));
	FFileHelper::SaveStringToFile(Csv, *(Folder / (Base + TEXT(".csv"))));
	FFileHelper::SaveStringToFile(LastSummary + LINE_TERMINATOR, *(Folder / (Base + TEXT(".txt"))));
	UE_LOG(LogVB, Log, TEXT("%s  -> %s"), *LastSummary, *(Folder / Base));
}
