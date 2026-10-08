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
  worlds = map (n: p.${"world-${n}"}) names;
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
        --add-flags "--seed ${seed} --hyprland ${hyprland}/bin/Hyprland ${pkgs.lib.optionalString homeManager "--prefer-user-config"}"
      mkdir -p $out/share/wayland-sessions
      cat > $out/share/wayland-sessions/hyprune.desktop <<EOF
      [Desktop Entry]
      Name=Hyprune (${cfg.kit})
      Comment=An explorable Hyprland desktop
      Exec=$out/bin/Hyprland
      Type=Application
      DesktopNames=Hyprland
      EOF
    '';
    passthru = {
      providedSessions = [ "hyprune" ];
      unwrapped = hyprland;
    };
    meta.mainProgram = "Hyprland";
  }) {};
in {
  inherit seed session hyprland;
  packages = [ p.core p.shell p.sdk p.starter pkgs.kitty pkgs.btop ] ++ worlds;
}
