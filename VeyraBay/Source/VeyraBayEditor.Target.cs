using UnrealBuildTool;

public class VeyraBayEditorTarget : TargetRules
{
	public VeyraBayEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.AddRange(new string[] { "VBCore", "VBWorld", "VeyraBay" });
	}
}
