using UnrealBuildTool;

public class VeyraBay : ModuleRules
{
	public VeyraBay(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"DeveloperSettings",
			"PhysicsCore",
			"RenderCore",
			"UMG",
			"Slate",
			"SlateCore",
			"RHI",
			"ChaosVehicles",
			"VBCore",
			"VBWorld"
		});
	}
}
