{ self, inputs, pkgs, cfg, homeManager ? false }:
let
  system = pkgs.stdenv.hostPlatform.system;
  p = self.packages.${system};
  hyprland = p.hyprland;
  names = pkgs.lib.unique (({
    minimal = [ "minimal" ];
    lumen-reach = [ "lumen-reach" ];
    dev = [ "switchyard" "minimal" ];
  }.${cfg.kit}) ++ cfg.worlds);
  # RFC-0015 content lock: read-only system worlds and libraries (nix/content-lock.nix).
  locked = if cfg.content.lock == null then { worlds = []; libraries = []; }
    else import ../nix/content-lock.nix { inherit (pkgs) lib; inherit pkgs; } cfg.content.lock;
  worlds = map (n: p.${"world-${n}"}) names ++ locked.worlds;
  sourcesFile = pkgs.writeText "hyprune-content-sources.json" (builtins.toJSON { version = 1; custom = cfg.content.sources; });
  # Read-only system libraries (RFC-0011): each entry is a library root holding <id>@<version>/.
  libraryDirs = pkgs.lib.optionals cfg.libraries.pinned
    (map (n: "${p.${n}}/share/hyprune/libraries") (builtins.attrNames (import ../nix/library-pins.nix { inherit (pkgs) lib; })))
    ++ map (l: "${l}/share/hyprune/libraries") locked.libraries
    ++ map toString cfg.libraries.extra;
  settings = pkgs.writeText "hyprune-settings.json" (builtins.toJSON cfg.settings);
  seed = pkgs.runCommand "hyprune-${cfg.kit}-seed" { nativeBuildInputs = [ pkgs.python3 ]; } ''
    python3 ${self}/runtime/setup.py render --kit ${self}/kits/${cfg.kit}/kit.toml \
      --output $out --plugin ${p.core}/lib/hyprune-core.so \
      --input-default ${p.core}/share/hyprune/input.default.json --settings ${settings} \
      ${pkgs.lib.optionalString homeManager "--external-plugin"} \
      ${pkgs.lib.concatMapStringsSep " " (w: "--world-dir ${w}/share/hyprune/worlds") worlds}
  '';
  session = pkgs.lib.makeOverridable ({ enableXWayland ? true }:
    assert pkgs.lib.assertMsg enableXWayland "Hyprune's pinned plugin uses the XWayland-enabled Hyprland ABI";
    pkgs.symlinkJoin {
    name = "hyprune-session-${cfg.kit}";
    version = hyprland.version;
    paths = [ p.starter hyprland ];
    nativeBuildInputs = [ pkgs.makeWrapper ];
    postBuild = ''
      rm $out/bin/Hyprland
      makeWrapper ${p.starter}/bin/hyprune-session $out/bin/Hyprland \
        --set HYPRUNE_PACKAGED_WORLD_DIRS '${builtins.toJSON (map (w: "${w}/share/hyprune/worlds") worlds)}' \
        ${pkgs.lib.optionalString (libraryDirs != []) "--prefix HYPRUNE_LIBRARY_DIR : ${pkgs.lib.escapeShellArg (pkgs.lib.concatStringsSep ":" libraryDirs)}"} \
        ${pkgs.lib.optionalString (cfg.content.sources != []) "--prefix HYPRUNE_SOURCES_FILES : ${sourcesFile}"} \
        --add-flags "--seed ${seed} --hyprland ${hyprland}/bin/Hyprland ${pkgs.lib.optionalString homeManager "--prefer-user-config"}"
      mkdir -p $out/share/wayland-sessions
      cat > $out/share/wayland-sessions/hyprune.desktop <<EOF
      [Desktop Entry]
      Name=Hyprune (${cfg.kit})
      Comment=An explorable Hyprland desktop
      Exec=$out/bin/Hyprland
      Icon=hyprune
      Type=Application
      DesktopNames=Hyprland
      EOF
    '';
    passthru = {
      providedSessions = [ "hyprune" ];
      inherit libraryDirs;
      worldDirs = map (w: "${w}/share/hyprune/worlds") worlds;
      sourcesFiles = pkgs.lib.optional (cfg.content.sources != []) "${sourcesFile}";
      unwrapped = hyprland;
    };
    meta.mainProgram = "Hyprland";
  }) {};
in {
  inherit seed session hyprland libraryDirs;
  packages = [ p.core p.shell p.sdk p.starter pkgs.kitty pkgs.btop ] ++ worlds;
}
