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
    libraries = {
      pinned = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = ''
          Preinstall the published official object libraries pinned in libraries/releases.json
          (fixed-output fetches, unpacked with the installer's archive rules) as read-only system
          libraries: the session's HYPRUNE_LIBRARY_DIR lists them, so the Director shows them as
          system-managed.
        '';
      };
      extra = lib.mkOption {
        type = lib.types.listOf lib.types.path;
        default = [];
        example = lib.literalExpression ''[ "''${myLibraries}/share/hyprune/libraries" ]'';
        description = ''
          More read-only library roots for HYPRUNE_LIBRARY_DIR: directories holding
          <id>@<version>/ library directories (real directories, not symlinks).
        '';
      };
    };
    settings = lib.mkOption {
      type = lib.types.attrs;
      default = {};
      example = { graphics = { quality = "intel"; reduced_motion = true; }; };
      description = "Initial partial patch for hl.plugin.hyprune.config; user edits win after generation.";
    };
  };
}
