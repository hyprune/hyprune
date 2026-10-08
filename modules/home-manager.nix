self: inputs: { config, lib, pkgs, ... }:
let
  cfg = config.programs.hyprune;
  p = self.packages.${pkgs.stdenv.hostPlatform.system};
  s = import ./session.nix { inherit self inputs pkgs cfg; homeManager = true; };
in {
  imports = [ ./options.nix ];
  config = lib.mkIf cfg.enable {
    home.packages = s.packages;
    home.activation.hypruneStarter = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      run ${p.starter}/bin/hyprune-setup init --seed ${s.seed}
    '';
    wayland.windowManager.hyprland = {
      enable = true;
      package = lib.mkForce s.session;
      portalPackage = inputs.hyprland.packages.${pkgs.stdenv.hostPlatform.system}.xdg-desktop-portal-hyprland;
      configType = "lua";
      plugins = [ "${p.core}/lib/hyprune-core.so" ];
      extraConfig = ''
        dofile((os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")) .. "/hyprune/hyprune.lua")
      '';
      # Inherited launch pipes require a direct compositor child, not UWSM's broker.
      systemd.enable = false;
    };
  };
}
