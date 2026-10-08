self: inputs: { config, lib, pkgs, ... }:
let
  cfg = config.programs.hyprune;
  s = import ./session.nix { inherit self inputs pkgs cfg; };
in {
  imports = [ ./options.nix ];
  config = lib.mkIf cfg.enable {
    programs.hyprland = {
      enable = true;
      package = lib.mkForce s.session;
      portalPackage = inputs.hyprland.packages.${pkgs.stdenv.hostPlatform.system}.xdg-desktop-portal-hyprland;
    };
    environment.systemPackages = s.packages ++ [ s.session ];
    programs.hyprland.withUWSM = lib.mkForce false;
  };
}
