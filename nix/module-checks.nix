{ self, inputs, pkgs }:
let
  inherit (pkgs) lib;
  hm = inputs.home-manager.lib.homeManagerConfiguration {
    inherit pkgs;
    modules = [ self.homeManagerModules.default {
      home = { username = "starter-test"; homeDirectory = "/home/starter-test"; stateVersion = "26.05"; };
      programs.hyprune = { enable = true; kit = "minimal"; settings.graphics.quality = "intel"; };
    } ];
  };
  nixos = hyprune: inputs.nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [ self.nixosModules.default {
      system.stateVersion = "26.05";
      programs.hyprune = { enable = true; kit = "minimal"; } // hyprune;
      fileSystems."/" = { device = "/dev/test"; fsType = "ext4"; };
      boot.loader.grub.devices = [ "/dev/test" ];
    } ];
  };
  os = nixos {};
  osOwnLibraries = nixos { libraries = { pinned = false; extra = [ "/srv/hyprune/libraries" ]; }; };
  # A content lock (hyprune content lock): its library joins the system library roots, its world
  # the packaged world directories; content.sources become a read-only sources file.
  osLocked = nixos { libraries.pinned = false; content = { lock = ../tests/fixtures/content.lock.json;
    sources = [ { id = "franks-stuff"; label = "Frank's stuff"; kind = "index"; url = "https://example.org/hyprune/v0.1/index.json"; enabled = true; } ]; }; };
  lockedPackage = osLocked.config.programs.hyprland.package;
  pins = import ./library-pins.nix { inherit lib; };
  # The session wrapper's library roots (the package passes them through for this check).
  osLibraries = os.config.programs.hyprland.package.libraryDirs;
  hmLibraries = hm.config.wayland.windowManager.hyprland.package.libraryDirs;
  hmEvaluation = builtins.unsafeDiscardStringContext hm.activationPackage.drvPath;
  osEvaluation = builtins.unsafeDiscardStringContext os.config.system.build.toplevel.drvPath;
in assert hm.config.wayland.windowManager.hyprland.configType == "lua";
   assert os.config.programs.hyprland.enable;
   assert hm.config.programs.hyprune.settings.graphics.quality == "intel";
   # Every published library pin is a system library root by default, in both modules.
   assert pins != {} && builtins.length osLibraries == builtins.length (builtins.attrNames pins);
   assert lib.all (d: lib.hasSuffix "/share/hyprune/libraries" d) osLibraries;
   assert hmLibraries == osLibraries;
   assert osOwnLibraries.config.programs.hyprland.package.libraryDirs == [ "/srv/hyprune/libraries" ];
   assert builtins.length lockedPackage.libraryDirs == 1 && lib.hasInfix "hyprune-content-library-com.hyprune.starter-" (builtins.head lockedPackage.libraryDirs);
   assert lib.any (d: lib.hasInfix "hyprune-content-world-com.hyprune.lumen-reach-" d) lockedPackage.worldDirs;
   assert builtins.length lockedPackage.sourcesFiles == 1;
pkgs.runCommand "hyprune-module-evaluation" {} ''
  echo ${hm.config.wayland.windowManager.hyprland.package} > $out
  echo ${os.config.programs.hyprland.package} >> $out
  echo ${hmEvaluation} >> $out
  echo ${osEvaluation} >> $out
  echo ${builtins.unsafeDiscardStringContext osLocked.config.system.build.toplevel.drvPath} >> $out
  # The session exports the library roots, and each holds its pinned <id>@<version>/ directory.
  for session in ${hm.config.wayland.windowManager.hyprland.package} ${os.config.programs.hyprland.package}; do
    grep -q HYPRUNE_LIBRARY_DIR $session/bin/Hyprland
    ${lib.concatMapStrings (d: "grep -qF ${lib.escapeShellArg d} $session/bin/Hyprland\n") osLibraries}
  done
  grep -qF /srv/hyprune/libraries ${osOwnLibraries.config.programs.hyprland.package}/bin/Hyprland
  ${lib.concatMapStrings (name: let r = pins.${name}; in ''
    test -f ${self.packages.${pkgs.stdenv.hostPlatform.system}.${name}}/share/hyprune/libraries/${r.id}@${r.version}/library.json
  '') (builtins.attrNames pins)}
  echo ${lib.concatStringsSep ":" osLibraries} >> $out
''
