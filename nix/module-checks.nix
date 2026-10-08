{ self, inputs, pkgs }:
let
  hm = inputs.home-manager.lib.homeManagerConfiguration {
    inherit pkgs;
    modules = [ self.homeManagerModules.default {
      home = { username = "starter-test"; homeDirectory = "/home/starter-test"; stateVersion = "26.05"; };
      programs.hyprune = { enable = true; kit = "minimal"; settings.graphics.quality = "intel"; };
    } ];
  };
  os = inputs.nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [ self.nixosModules.default {
      system.stateVersion = "26.05";
      programs.hyprune = { enable = true; kit = "minimal"; };
      fileSystems."/" = { device = "/dev/test"; fsType = "ext4"; };
      boot.loader.grub.devices = [ "/dev/test" ];
    } ];
  };
  hmEvaluation = builtins.unsafeDiscardStringContext hm.activationPackage.drvPath;
  osEvaluation = builtins.unsafeDiscardStringContext os.config.system.build.toplevel.drvPath;
in assert hm.config.wayland.windowManager.hyprland.configType == "lua";
   assert os.config.programs.hyprland.enable;
   assert hm.config.programs.hyprune.settings.graphics.quality == "intel";
pkgs.runCommand "hyprune-module-evaluation" {} ''
  echo ${hm.config.wayland.windowManager.hyprland.package} > $out
  echo ${os.config.programs.hyprland.package} >> $out
  echo ${hmEvaluation} >> $out
  echo ${osEvaluation} >> $out
''
