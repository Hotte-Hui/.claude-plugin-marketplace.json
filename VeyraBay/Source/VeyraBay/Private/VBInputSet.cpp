#include "VBInputSet.h"

#include "InputAction.h"
#include "InputCoreTypes.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"

namespace VBInput
{
	static UInputAction* MakeAction(UObject* Outer, const TCHAR* Name, EInputActionValueType ValueType, bool bWhenPaused = false)
	{
		UInputAction* Action = NewObject<UInputAction>(Outer, FName(Name));
		Action->ValueType = ValueType;
		Action->bTriggerWhenPaused = bWhenPaused;
		return Action;
	}

	static void AddNegate(UInputMappingContext* Context, FEnhancedActionKeyMapping& Mapping, bool bX, bool bY)
	{
		UInputModifierNegate* Negate = NewObject<UInputModifierNegate>(Context);
		Negate->bX = bX;
		Negate->bY = bY;
		Negate->bZ = false;
		Mapping.Modifiers.Add(Negate);
	}

	static void AddSwizzleYX(UInputMappingContext* Context, FEnhancedActionKeyMapping& Mapping)
	{
		UInputModifierSwizzleAxis* Swizzle = NewObject<UInputModifierSwizzleAxis>(Context);
		Swizzle->Order = EInputAxisSwizzle::YXZ;
		Mapping.Modifiers.Add(Swizzle);
	}

	static void AddDeadZone(UInputMappingContext* Context, FEnhancedActionKeyMapping& Mapping, float Lower)
	{
		UInputModifierDeadZone* DeadZone = NewObject<UInputModifierDeadZone>(Context);
		DeadZone->LowerThreshold = Lower;
		DeadZone->UpperThreshold = 1.f;
		DeadZone->Type = EDeadZoneType::Radial;
		Mapping.Modifiers.Add(DeadZone);
	}
}

void UVBInputSet::Build()
{
	using namespace VBInput;

	GameplayContext = NewObject<UInputMappingContext>(this, TEXT("IMC_VB_Gameplay"));
	DebugContext = NewObject<UInputMappingContext>(this, TEXT("IMC_VB_Debug"));

	Move        = MakeAction(this, TEXT("IA_Move"),        EInputActionValueType::Axis2D);
	Look        = MakeAction(this, TEXT("IA_Look"),        EInputActionValueType::Axis2D);
	LookGamepad = MakeAction(this, TEXT("IA_LookGamepad"), EInputActionValueType::Axis2D);
	Jump        = MakeAction(this, TEXT("IA_Jump"),        EInputActionValueType::Boolean);
	Sprint      = MakeAction(this, TEXT("IA_Sprint"),      EInputActionValueType::Boolean);
	WalkToggle  = MakeAction(this, TEXT("IA_WalkToggle"),  EInputActionValueType::Boolean);
	Interact    = MakeAction(this, TEXT("IA_Interact"),    EInputActionValueType::Boolean);
	Pause       = MakeAction(this, TEXT("IA_Pause"),       EInputActionValueType::Boolean, /*bWhenPaused*/ true);

	// --- Bewegung: WASD + linker Stick ---------------------------------------------
	{
		UInputMappingContext* C = GameplayContext;

		FEnhancedActionKeyMapping& W = C->MapKey(Move, EKeys::W);
		AddSwizzleYX(C, W);

		FEnhancedActionKeyMapping& S = C->MapKey(Move, EKeys::S);
		AddSwizzleYX(C, S);
		AddNegate(C, S, true, true);

		FEnhancedActionKeyMapping& A = C->MapKey(Move, EKeys::A);
		AddNegate(C, A, true, false);

		C->MapKey(Move, EKeys::D);

		FEnhancedActionKeyMapping& Stick = C->MapKey(Move, EKeys::Gamepad_Left2D);
		AddDeadZone(C, Stick, 0.15f);
	}

	// --- Kamera: Maus + rechter Stick ----------------------------------------------
	{
		UInputMappingContext* C = GameplayContext;

		// Wie in den Epic-Vorlagen: Y negieren, Pitch-Skalierung der Engine kehrt es wieder um.
		FEnhancedActionKeyMapping& Mouse = C->MapKey(Look, EKeys::Mouse2D);
		AddNegate(C, Mouse, false, true);

		FEnhancedActionKeyMapping& Stick = C->MapKey(LookGamepad, EKeys::Gamepad_Right2D);
		AddDeadZone(C, Stick, 0.12f);
	}

	// --- Aktionen ----------------------------------------------------------------
	GameplayContext->MapKey(Jump, EKeys::SpaceBar);
	GameplayContext->MapKey(Jump, EKeys::Gamepad_FaceButton_Bottom);

	GameplayContext->MapKey(Sprint, EKeys::LeftShift);
	GameplayContext->MapKey(Sprint, EKeys::Gamepad_LeftThumbstick);

	GameplayContext->MapKey(WalkToggle, EKeys::LeftControl);
	GameplayContext->MapKey(WalkToggle, EKeys::Gamepad_DPad_Down);

	GameplayContext->MapKey(Interact, EKeys::E);
	GameplayContext->MapKey(Interact, EKeys::Gamepad_FaceButton_Left);

	GameplayContext->MapKey(Pause, EKeys::P);
	GameplayContext->MapKey(Pause, EKeys::Escape);
	GameplayContext->MapKey(Pause, EKeys::Gamepad_Special_Right);

	// --- Entwickler-Tasten -----------------------------------------------------------
	DebugPerf         = MakeAction(this, TEXT("IA_Debug_Perf"),         EInputActionValueType::Boolean, true);
	DebugInfo         = MakeAction(this, TEXT("IA_Debug_Info"),         EInputActionValueType::Boolean, true);
	DebugNextWeather  = MakeAction(this, TEXT("IA_Debug_NextWeather"),  EInputActionValueType::Boolean);
	DebugTimeBack     = MakeAction(this, TEXT("IA_Debug_TimeBack"),     EInputActionValueType::Boolean);
	DebugTimeForward  = MakeAction(this, TEXT("IA_Debug_TimeForward"),  EInputActionValueType::Boolean);
	DebugTimePause    = MakeAction(this, TEXT("IA_Debug_TimePause"),    EInputActionValueType::Boolean);
	DebugGraphicsMode = MakeAction(this, TEXT("IA_Debug_GraphicsMode"), EInputActionValueType::Boolean, true);

	DebugContext->MapKey(DebugPerf, EKeys::F2);
	DebugContext->MapKey(DebugInfo, EKeys::F3);
	DebugContext->MapKey(DebugNextWeather, EKeys::F5);
	DebugContext->MapKey(DebugTimeBack, EKeys::F6);
	DebugContext->MapKey(DebugTimeForward, EKeys::F7);
	DebugContext->MapKey(DebugTimePause, EKeys::F8);
	DebugContext->MapKey(DebugGraphicsMode, EKeys::F9);
}
