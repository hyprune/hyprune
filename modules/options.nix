{ lib, ... }:
{
  options.programs.hyprune = {
    enable = lib.mkEnableOption "Hyprune's starter session";
    kit = lib.mkOption {
      type = lib.types.enum [ "lumen-reach" "minimal" "dev" ];
      default = "minimal";
      description = "Initial kit; existing user-owned starter files are preserved.";
    };
    worlds = lib.mkOption {
      type = lib.types.listOf (lib.types.enum [ "lumen-reach" "switchyard" "minimal" ]);
      default = [];
      description = "Additional official worlds to install alongside the kit.";
    };
    settings = lib.mkOption {
      type = lib.types.attrs;
      default = {};
      example = { graphics = { quality = "intel"; reduced_motion = true; }; };
      description = "Initial partial patch for hl.plugin.hyprune.config; user edits win after generation.";
    };
  };
}
