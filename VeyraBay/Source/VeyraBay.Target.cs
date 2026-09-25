using UnrealBuildTool;

public class VeyraBayTarget : TargetRules
{
	public VeyraBayTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.AddRange(new string[] { "VBCore", "VBWorld", "VeyraBay" });
	}
}
