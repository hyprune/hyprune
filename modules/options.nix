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
    content = {
      lock = lib.mkOption {
        type = lib.types.nullOr lib.types.path;
        default = null;
        example = lib.literalExpression "./hyprune-content.lock.json";
        description = ''
          A content lock written by `hyprune content lock` (RFC-0015): every world and library
          in it becomes a fixed-output fetch of its locked archive, unpacked with the
          installer's rules and installed read-only (system-managed in the Director: no update,
          rollback or remove there). Update by writing a new lock.
        '';
      };
      sources = lib.mkOption {
        type = lib.types.listOf lib.types.attrs;
        default = [];
        example = [ { id = "franks-stuff"; label = "Frank's stuff"; kind = "index"; url = "https://example.org/hyprune/v0.1/index.json"; enabled = true; } ];
        description = ''
          Custom content sources (entries of registry/v0.1/sources.schema.json `custom`),
          written to a read-only file listed in HYPRUNE_SOURCES_FILES.
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
