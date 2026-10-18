#include "VBMissionSubsystem.h"

#include "VBLog.h"
#include "VBMissionMarker.h"
#include "VBVehicle.h"
#include "VBWeatherSubsystem.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"

namespace VBMission
{
	static const TCHAR* SaveSlot = TEXT("VeyraBay");

	// Orte in Metern (vb_cityplan.py: Uferstrasse y = -74.34, Kaimauer y = -94.12)
	static FVector M(float X, float Y, float Z = 0.f)
	{
		return FVector(X, Y, Z) * 100.f;
	}

	static FVBDialogueLine Line(const TCHAR* Speaker, const TCHAR* Text, float Seconds = 4.f)
	{
		FVBDialogueLine Result;
		Result.Speaker = Speaker;
		Result.Text = Text;
		Result.Seconds = Seconds;
		return Result;
	}

	static FVBMissionStep Talk(std::initializer_list<FVBDialogueLine> Lines)
	{
		FVBMissionStep Step;
		Step.Type = EVBStepType::Dialogue;
		Step.Lines = Lines;
		return Step;
	}

	static FVBMissionStep Go(EVBStepType Type, const TCHAR* Objective, const FVector& Target, float RadiusM, float Seconds = 0.f)
	{
		FVBMissionStep Step;
		Step.Type = Type;
		Step.Objective = Objective;
		Step.Target = Target;
		Step.Radius = RadiusM * 100.f;
		Step.Seconds = Seconds;
		return Step;
	}

	static FVBMissionStep Simple(EVBStepType Type, float Seconds = 0.f, const TCHAR* Objective = TEXT(""))
	{
		FVBMissionStep Step;
		Step.Type = Type;
		Step.Seconds = Seconds;
		Step.Objective = Objective;
		return Step;
	}

	static FVBMissionStep Weather(EVBWeatherType Type)
	{
		FVBMissionStep Step;
		Step.Type = EVBStepType::SetWeather;
		Step.Weather = Type;
		return Step;
	}

	static FAutoConsoleCommandWithWorldAndArgs MissionCommand(TEXT("vb.Mission"), TEXT("vb.Mission <0..2> - Mission starten"),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			if (UVBMissionSubsystem* Missions = World ? World->GetSubsystem<UVBMissionSubsystem>() : nullptr)
			{
				Missions->StartMission(Args.Num() > 0 ? FCString::Atoi(*Args[0]) : 0);
			}
		}));

	static FAutoConsoleCommandWithWorldAndArgs ResetCommand(TEXT("vb.MissionReset"), TEXT("Spielstand der Missionen zuruecksetzen"),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			if (UVBMissionSubsystem* Missions = World ? World->GetSubsystem<UVBMissionSubsystem>() : nullptr)
			{
				Missions->ResetProgress();
			}
		}));
}

bool UVBMissionSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UVBMissionSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UVBMissionSubsystem, STATGROUP_Tickables);
}

// ---------------------------------------------------------------------------------------------
// Story: Mara Castell kehrt nach Veyra Bay zurueck. Ihr Grossvater Tomas fuehrt das kleine
// Hafen-Fuhrunternehmen "Castell Transporte", das ums Ueberleben kaempft. (Eigene, fiktive Handlung.)
// ---------------------------------------------------------------------------------------------
void UVBMissionSubsystem::BuildMissions()
{
	using namespace VBMission;
	Missions.Reset();
	const FVector Office = M(-1150.f, -72.f);

	// --- 1. Heimkehr ---------------------------------------------------------------------------
	{
		FVBMission Mission;
		Mission.Title = TEXT("Heimkehr");
		Mission.StartLocation = M(-300.f, -87.f);
		Mission.Steps.Add(Talk({
			Line(TEXT("Mara"), TEXT("Veyra Bay. Sieben Jahre... und die Promenade riecht immer noch nach Salz und Kaffee.")),
			Line(TEXT("Tomas (Telefon)"), TEXT("Mara? Bist du wirklich da? Ich stehe im Kontor, der Laster springt wieder nicht an.")),
			Line(TEXT("Tomas (Telefon)"), TEXT("Nimm eins der Autos an der Uferstrasse. Die Schluessel stecken, das ist hier noch so.")),
		}));
		Mission.Steps.Add(Go(EVBStepType::GoTo, TEXT("Geh zu den geparkten Autos an der Uferstrasse"), M(-322.f, -80.f), 7.f));
		Mission.Steps.Add(Simple(EVBStepType::EnterVehicle, 0.f, TEXT("Steig in ein Auto  [E]")));
		Mission.Steps.Add(Go(EVBStepType::DriveTo, TEXT("Fahr zum Kontor von Castell Transporte im Hafen"), Office, 9.f));
		Mission.Steps.Add(Talk({
			Line(TEXT("Tomas"), TEXT("Da bist du ja! Lass dich ansehen. Erwachsen geworden, und immer noch zu schnell unterwegs.")),
			Line(TEXT("Tomas"), TEXT("Das Tor haengt schief, das Dach tropft - aber Castell Transporte faehrt noch.")),
			Line(TEXT("Mara"), TEXT("Deshalb bin ich hier, Opa. Zeig mir, was zu tun ist.")),
		}));
		Missions.Add(MoveTemp(Mission));
	}

	// --- 2. Lieferrunde (Mercato, Zeitlimit) ------------------------------------------------------
	{
		FVBMission Mission;
		Mission.Title = TEXT("Lieferrunde");
		Mission.StartLocation = Office;
		Mission.Steps.Add(Talk({
			Line(TEXT("Tomas"), TEXT("Drei Laeden im Mercato warten auf ihre Ware. Wenn wir heute puenktlich sind, bleiben sie Kunden.")),
			Line(TEXT("Tomas"), TEXT("Sechs Minuten. Der Mercato ist eng - halt an den Laeden kurz an, die holen sich die Kisten.")),
		}));
		Mission.Steps.Add(Simple(EVBStepType::EnterVehicle, 0.f, TEXT("Steig in ein Auto  [E]")));
		Mission.Steps.Add(Simple(EVBStepType::StartTimer, 360.f));
		Mission.Steps.Add(Go(EVBStepType::DriveTo, TEXT("Lieferung 1/3: Baeckerei Ostrova (Mercato)"), M(-1195.f, 519.f), 8.f));
		Mission.Steps.Add(Go(EVBStepType::Hold, TEXT("Ware wird uebergeben ..."), M(-1195.f, 519.f), 10.f, 3.f));
		Mission.Steps.Add(Go(EVBStepType::DriveTo, TEXT("Lieferung 2/3: Gewuerzladen Hadad (Mercato)"), M(-875.f, 618.f), 8.f));
		Mission.Steps.Add(Go(EVBStepType::Hold, TEXT("Ware wird uebergeben ..."), M(-875.f, 618.f), 10.f, 3.f));
		Mission.Steps.Add(Go(EVBStepType::DriveTo, TEXT("Lieferung 3/3: Cafe Lanterna (Mercato)"), M(-636.f, 717.f), 8.f));
		Mission.Steps.Add(Go(EVBStepType::Hold, TEXT("Ware wird uebergeben ..."), M(-636.f, 717.f), 10.f, 3.f));
		Mission.Steps.Add(Simple(EVBStepType::StopTimer));
		Mission.Steps.Add(Talk({
			Line(TEXT("Tomas (Telefon)"), TEXT("Alle drei zufrieden! Frau Ostrova hat sogar nach naechster Woche gefragt.")),
			Line(TEXT("Tomas (Telefon)"), TEXT("Komm zurueck zum Kontor. Und Mara - die Leute von Aurelion waren wieder hier.")),
		}));
		Missions.Add(MoveTemp(Mission));
	}

	// --- 3. Sturmflut (Marina, Unwetter) -------------------------------------------------------------
	{
		FVBMission Mission;
		Mission.Title = TEXT("Sturmflut");
		Mission.StartLocation = Office;
		Mission.Steps.Add(Weather(EVBWeatherType::Storm));
		Mission.Steps.Add(Talk({
			Line(TEXT("Tomas"), TEXT("Hoerst du das? Sturmwarnung. In der Marina liegen noch drei Boote von Kunden an losen Leinen.")),
			Line(TEXT("Tomas"), TEXT("Wenn die heute Nacht gegen die Mauer schlagen, sind wir erledigt. Fahr hin, schnell!")),
		}));
		Mission.Steps.Add(Simple(EVBStepType::EnterVehicle, 0.f, TEXT("Steig in ein Auto  [E]")));
		Mission.Steps.Add(Simple(EVBStepType::StartTimer, 300.f));
		Mission.Steps.Add(Go(EVBStepType::DriveTo, TEXT("Fahr zur Marina im Osten"), M(2530.f, -72.f), 12.f));
		Mission.Steps.Add(Go(EVBStepType::GoTo, TEXT("Leine 1/3 sichern (Kaimauer)"), M(2500.f, -92.f), 3.f));
		Mission.Steps.Add(Go(EVBStepType::Hold, TEXT("Knoten wird festgezogen ..."), M(2500.f, -92.f), 4.f, 2.5f));
		Mission.Steps.Add(Go(EVBStepType::GoTo, TEXT("Leine 2/3 sichern"), M(2560.f, -92.f), 3.f));
		Mission.Steps.Add(Go(EVBStepType::Hold, TEXT("Knoten wird festgezogen ..."), M(2560.f, -92.f), 4.f, 2.5f));
		Mission.Steps.Add(Go(EVBStepType::GoTo, TEXT("Leine 3/3 sichern"), M(2620.f, -92.f), 3.f));
		Mission.Steps.Add(Go(EVBStepType::Hold, TEXT("Knoten wird festgezogen ..."), M(2620.f, -92.f), 4.f, 2.5f));
		Mission.Steps.Add(Simple(EVBStepType::StopTimer));
		Mission.Steps.Add(Talk({
			Line(TEXT("Mara (Telefon)"), TEXT("Alle drei sind fest, Opa. Ich bin klatschnass, aber die Boote bleiben, wo sie sind.")),
			Line(TEXT("Tomas (Telefon)"), TEXT("Deine Grossmutter waere stolz. Morgen reden wir ueber Aurelion - und ueber deine Zukunft hier.")),
			Line(TEXT(""), TEXT("Fortsetzung folgt."), 5.f),
		}));
		Mission.Steps.Add(Weather(EVBWeatherType::LightRain));
		Missions.Add(MoveTemp(Mission));
	}
}

void UVBMissionSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	bCityMap = InWorld.GetMapName().Contains(TEXT("L_VB_City"));
	BuildMissions();
	if (const UVBSaveGame* Save = Cast<UVBSaveGame>(UGameplayStatics::LoadGameFromSlot(VBMission::SaveSlot, 0)))
	{
		Completed = FMath::Clamp(Save->CompletedMissions, 0, Missions.Num());
	}
}

APawn* UVBMissionSubsystem::GetPlayerPawn() const
{
	const APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
	return PC ? PC->GetPawn() : nullptr;
}

void UVBMissionSubsystem::SaveProgress()
{
	UVBSaveGame* Save = Cast<UVBSaveGame>(UGameplayStatics::CreateSaveGameObject(UVBSaveGame::StaticClass()));
	Save->CompletedMissions = Completed;
	UGameplayStatics::SaveGameToSlot(Save, VBMission::SaveSlot, 0);
}

void UVBMissionSubsystem::ResetProgress()
{
	Completed = 0;
	Current = INDEX_NONE;
	HideMarker();
	SaveProgress();
	AutoStartDelay = 2.f;
}

// ---------------------------------------------------------------------------------------------
// Ablauf
// ---------------------------------------------------------------------------------------------
void UVBMissionSubsystem::StartMission(int32 Index)
{
	if (!Missions.IsValidIndex(Index))
	{
		return;
	}
	Current = Index;
	bTimerRunning = false;
	ShowBanner(FString::Printf(TEXT("MISSION %d: %s"), Index + 1, *Missions[Index].Title.ToUpper()), 4.f);
	EnterStep(0);
	UE_LOG(LogVB, Log, TEXT("Mission gestartet: %s"), *Missions[Index].Title);
}

void UVBMissionSubsystem::RestartMission()
{
	if (Current != INDEX_NONE)
	{
		StartMission(Current);
	}
}

void UVBMissionSubsystem::EnterStep(int32 StepIndex)
{
	Step = StepIndex;
	StepTime = 0.f;
	HoldTime = 0.f;
	LineIndex = 0;
	LineTime = 0.f;
	const FVBMission& Mission = Missions[Current];
	if (!Mission.Steps.IsValidIndex(Step))
	{
		CompleteMission();
		return;
	}
	const FVBMissionStep& Data = Mission.Steps[Step];
	switch (Data.Type)
	{
	case EVBStepType::GoTo:
	case EVBStepType::DriveTo:
	case EVBStepType::Hold:
		ShowMarker(Data.Target, Data.Radius, Data.Type == EVBStepType::Hold ? FLinearColor(0.2f, 0.9f, 0.4f) : FLinearColor(1.f, 0.75f, 0.2f));
		break;
	case EVBStepType::SetWeather:
		if (UVBWeatherSubsystem* Weather = GetWorld()->GetSubsystem<UVBWeatherSubsystem>())
		{
			Weather->SetWeather(Data.Weather, 25.f);
		}
		AdvanceStep();
		break;
	case EVBStepType::StartTimer:
		bTimerRunning = true;
		TimerLeft = Data.Seconds;
		AdvanceStep();
		break;
	case EVBStepType::StopTimer:
		bTimerRunning = false;
		AdvanceStep();
		break;
	default:
		HideMarker();
		break;
	}
}

void UVBMissionSubsystem::AdvanceStep()
{
	if (Current != INDEX_NONE)
	{
		EnterStep(Step + 1);
	}
}

void UVBMissionSubsystem::CompleteMission()
{
	HideMarker();
	ShowBanner(FString::Printf(TEXT("MISSION ERFUELLT: %s"), *Missions[Current].Title), 5.f);
	Completed = FMath::Max(Completed, Current + 1);
	Current = INDEX_NONE;
	bTimerRunning = false;
	SaveProgress();
}

void UVBMissionSubsystem::FailMission(const FString& Reason)
{
	HideMarker();
	Current = INDEX_NONE;
	bTimerRunning = false;
	ShowBanner(FString::Printf(TEXT("MISSION GESCHEITERT - %s  (Startpunkt erneut betreten)"), *Reason), 6.f);
}

void UVBMissionSubsystem::ShowBanner(const FString& Text, float Seconds)
{
	BannerText = Text;
	BannerTime = Seconds;
}

void UVBMissionSubsystem::ShowMarker(const FVector& Location, float Radius, const FLinearColor& Color)
{
	UWorld* World = GetWorld();
	if (!Marker)
	{
		FActorSpawnParameters Params;
		Params.ObjectFlags |= RF_Transient;
		Marker = World->SpawnActor<AVBMissionMarker>(Location, FRotator::ZeroRotator, Params);
	}
	if (Marker)
	{
		Marker->SetActorHiddenInGame(false);
		Marker->SetActorLocation(Location + FVector(0.f, 0.f, 1500.f));
		Marker->SetRadius(Radius);
		Marker->SetColor(Color);
	}
}

void UVBMissionSubsystem::HideMarker()
{
	if (Marker)
	{
		Marker->SetActorHiddenInGame(true);
	}
}

void UVBMissionSubsystem::Tick(float DeltaTime)
{
	BannerTime = FMath::Max(BannerTime - DeltaTime, 0.f);
	if (!bCityMap)
	{
		return;
	}
	APawn* Pawn = GetPlayerPawn();
	if (!Pawn)
	{
		return;
	}

	// Keine Mission aktiv: erste automatisch, weitere ueber den Startmarker
	if (Current == INDEX_NONE)
	{
		if (!Missions.IsValidIndex(Completed))
		{
			HideMarker();
			return;
		}
		if (Completed == 0 && AutoStartDelay > 0.f)
		{
			AutoStartDelay -= DeltaTime;
			if (AutoStartDelay <= 0.f)
			{
				StartMission(0);
			}
			return;
		}
		const FVector Start = Missions[Completed].StartLocation;
		ShowMarker(Start, 400.f, FLinearColor(0.3f, 0.6f, 1.f));
		if (FVector::Dist2D(Pawn->GetActorLocation(), Start) < 450.f)
		{
			StartMission(Completed);
		}
		return;
	}

	StepTime += DeltaTime;
	if (bTimerRunning)
	{
		TimerLeft -= DeltaTime;
		if (TimerLeft <= 0.f)
		{
			FailMission(TEXT("Zeit abgelaufen"));
			return;
		}
	}

	const FVBMissionStep& Data = Missions[Current].Steps[Step];
	const AVBVehicle* Vehicle = Cast<AVBVehicle>(Pawn);
	const float Distance = FVector::Dist2D(Pawn->GetActorLocation(), Data.Target);
	switch (Data.Type)
	{
	case EVBStepType::Dialogue:
		LineTime += DeltaTime;
		if (Data.Lines.IsValidIndex(LineIndex) && LineTime >= Data.Lines[LineIndex].Seconds)
		{
			LineTime = 0.f;
			++LineIndex;
		}
		if (!Data.Lines.IsValidIndex(LineIndex))
		{
			AdvanceStep();
		}
		break;
	case EVBStepType::GoTo:
		if (Distance < Data.Radius)
		{
			AdvanceStep();
		}
		break;
	case EVBStepType::EnterVehicle:
		if (Vehicle)
		{
			AdvanceStep();
		}
		break;
	case EVBStepType::DriveTo:
		if (Vehicle && Distance < Data.Radius && FMath::Abs(Vehicle->GetSpeedKmh()) < 8.f)
		{
			AdvanceStep();
		}
		break;
	case EVBStepType::Hold:
		if (Distance < Data.Radius && Pawn->GetVelocity().Size() < 250.f)
		{
			HoldTime += DeltaTime;
			if (HoldTime >= Data.Seconds)
			{
				AdvanceStep();
			}
		}
		else
		{
			HoldTime = 0.f;
		}
		break;
	default:
		break;
	}
}

// ---------------------------------------------------------------------------------------------
// HUD-Abfragen
// ---------------------------------------------------------------------------------------------
FString UVBMissionSubsystem::GetMissionTitle() const
{
	return Missions.IsValidIndex(Current) ? Missions[Current].Title : FString();
}

FString UVBMissionSubsystem::GetObjective() const
{
	if (Missions.IsValidIndex(Current) && Missions[Current].Steps.IsValidIndex(Step))
	{
		const FVBMissionStep& Data = Missions[Current].Steps[Step];
		if (Data.Type == EVBStepType::Hold && Data.Seconds > 0.f)
		{
			return FString::Printf(TEXT("%s  %d %%"), *Data.Objective, FMath::RoundToInt(100.f * HoldTime / Data.Seconds));
		}
		return Data.Objective;
	}
	if (bCityMap && Current == INDEX_NONE && Missions.IsValidIndex(Completed) && Completed > 0)
	{
		return FString::Printf(TEXT("Naechste Mission: %s - zum blauen Marker"), *Missions[Completed].Title);
	}
	return FString();
}

bool UVBMissionSubsystem::GetDialogue(FString& OutSpeaker, FString& OutText) const
{
	if (!Missions.IsValidIndex(Current) || !Missions[Current].Steps.IsValidIndex(Step))
	{
		return false;
	}
	const FVBMissionStep& Data = Missions[Current].Steps[Step];
	if (Data.Type != EVBStepType::Dialogue || !Data.Lines.IsValidIndex(LineIndex))
	{
		return false;
	}
	OutSpeaker = Data.Lines[LineIndex].Speaker;
	OutText = Data.Lines[LineIndex].Text;
	return true;
}

bool UVBMissionSubsystem::GetTimer(float& OutSeconds) const
{
	OutSeconds = TimerLeft;
	return bTimerRunning;
}

bool UVBMissionSubsystem::GetTarget(FVector& OutLocation) const
{
	if (Missions.IsValidIndex(Current) && Missions[Current].Steps.IsValidIndex(Step))
	{
		const FVBMissionStep& Data = Missions[Current].Steps[Step];
		if (Data.Type == EVBStepType::GoTo || Data.Type == EVBStepType::DriveTo || Data.Type == EVBStepType::Hold)
		{
			OutLocation = Data.Target;
			return true;
		}
		return false;
	}
	if (bCityMap && Current == INDEX_NONE && Missions.IsValidIndex(Completed) && Completed > 0)
	{
		OutLocation = Missions[Completed].StartLocation;
		return true;
	}
	return false;
}

bool UVBMissionSubsystem::GetBanner(FString& OutText) const
{
	OutText = BannerText;
	return BannerTime > 0.f;
}
