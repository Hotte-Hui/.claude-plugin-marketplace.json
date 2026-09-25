#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "Subsystems/WorldSubsystem.h"
#include "VBWeatherTypes.h"
#include "VBMissionSubsystem.generated.h"

class AVBMissionMarker;

/** Spielstand: abgeschlossene Missionen. */
UCLASS()
class VEYRABAY_API UVBSaveGame : public USaveGame
{
	GENERATED_BODY()

public:
	UPROPERTY() int32 CompletedMissions = 0;
};

enum class EVBStepType : uint8
{
	Dialogue,       // Zeilen abspielen
	GoTo,           // zu Fuss (oder egal wie) zum Ziel
	EnterVehicle,   // in ein fahrbares Auto steigen
	DriveTo,        // mit dem Auto zum Ziel und anhalten
	Hold,           // im Ziel stehen bleiben (Aktion dauert Seconds)
	SetWeather,     // Wetter wechseln
	StartTimer,     // Zeitlimit fuer die folgenden Schritte
	StopTimer,
};

struct FVBDialogueLine
{
	FString Speaker;
	FString Text;
	float Seconds = 3.5f;
};

struct FVBMissionStep
{
	EVBStepType Type = EVBStepType::Dialogue;
	FString Objective;
	FVector Target = FVector::ZeroVector;    // cm
	float Radius = 600.f;                    // cm
	float Seconds = 0.f;                     // Hold / Timer
	EVBWeatherType Weather = EVBWeatherType::Clear;
	TArray<FVBDialogueLine> Lines;
};

struct FVBMission
{
	FString Title;
	FVector StartLocation = FVector::ZeroVector;   // Startmarker (cm); erste Mission startet automatisch
	TArray<FVBMissionStep> Steps;
};

/**
 * Missionen der Story (Phase 9): "Heimkehr", "Lieferrunde", "Sturmflut" in der Stadtkarte L_VB_City.
 * Ziele als Lichtsaeulen, Hinweise/Dialoge/Timer im HUD, Fortschritt im Spielstand (Slot "VeyraBay").
 *
 * Konsole: vb.Mission <0..2> startet eine Mission, vb.MissionReset setzt den Spielstand zurueck.
 */
UCLASS()
class VEYRABAY_API UVBMissionSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

	void StartMission(int32 Index);
	void RestartMission();
	void ResetProgress();

	bool IsActive() const { return Current != INDEX_NONE; }
	FString GetMissionTitle() const;
	FString GetObjective() const;
	bool GetDialogue(FString& OutSpeaker, FString& OutText) const;
	bool GetTimer(float& OutSeconds) const;
	bool GetTarget(FVector& OutLocation) const;
	bool GetBanner(FString& OutText) const;
	int32 GetCompletedMissions() const { return Completed; }
	int32 GetMissionCount() const { return Missions.Num(); }

private:
	void BuildMissions();
	void EnterStep(int32 StepIndex);
	void AdvanceStep();
	void CompleteMission();
	void FailMission(const FString& Reason);
	void ShowMarker(const FVector& Location, float Radius, const FLinearColor& Color);
	void HideMarker();
	void ShowBanner(const FString& Text, float Seconds);
	void SaveProgress();
	APawn* GetPlayerPawn() const;

	TArray<FVBMission> Missions;
	int32 Completed = 0;
	int32 Current = INDEX_NONE;
	int32 Step = 0;
	float StepTime = 0.f;
	float HoldTime = 0.f;
	int32 LineIndex = 0;
	float LineTime = 0.f;
	bool bTimerRunning = false;
	float TimerLeft = 0.f;
	float AutoStartDelay = 4.f;
	bool bCityMap = false;
	FString BannerText;
	float BannerTime = 0.f;

	UPROPERTY(Transient)
	TObjectPtr<AVBMissionMarker> Marker;
};
