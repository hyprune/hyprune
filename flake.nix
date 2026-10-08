{
  description = "Hyprune — an explorable desktop, with a place to start";
  inputs = {
    hyprland.url = "github:hyprwm/Hyprland/v0.56.2";
    nixpkgs.follows = "hyprland/nixpkgs";
    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    # Source flake inputs: component repositories need no Nix files.
    core = { url = "github:hyprune/core"; flake = false; };
    shell = { url = "github:hyprune/shell"; flake = false; };
    sdk = { url = "github:hyprune/sdk"; flake = false; };
    worlds = { url = "github:hyprune/worlds"; flake = false; };
    schema = { url = "github:hyprune/schema"; flake = false; };
    docs = { url = "github:hyprune/docs"; flake = false; };
  };
  outputs = inputs@{ self, nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      each = nixpkgs.lib.genAttrs systems;
      pkgsFor = system: import nixpkgs {
        inherit system;
        overlays = [ inputs.hyprland.overlays.hyprland-packages ];
      };
    in {
      packages = each (system: import ./nix/packages.nix {
        inherit inputs self;
        pkgs = pkgsFor system;
      });
      nixosModules.default = import ./modules/nixos.nix self inputs;
      homeManagerModules.default = import ./modules/home-manager.nix self inputs;
      devShells = each (system: let pkgs = pkgsFor system; p = self.packages.${system}; in {
        default = pkgs.mkShell.override { stdenv = p.core.stdenv; } {
          inputsFrom = [ p.core p.sdk ];
          packages = with pkgs; [ python3 nodejs ninja cmake pkg-config shellcheck git zstd ];
          shellHook = ''echo "Hyprune: build against Hyprland 0.56.2; never test on your running desktop."'';
        };
        worlds = pkgs.mkShell { packages = with pkgs; [ nodejs python3 zstd ]; };
      });
      checks = each (system: let pkgs = pkgsFor system; p = self.packages.${system}; in {
        inherit (p) core shell sdk starter;
        contracts = pkgs.runCommand "hyprune-starter-checks" {
          nativeBuildInputs = [ pkgs.python3 pkgs.shellcheck pkgs.zstd pkgs.git ];
        } ''
          cp -r ${self} source; chmod -R u+w source; cd source
          export PYTHONDONTWRITEBYTECODE=1
          python3 -m unittest discover -s tests -v
          shellcheck install.sh scripts/*.sh
          touch $out
        '';
        modules = import ./nix/module-checks.nix { inherit self inputs pkgs; };
        minimal-world = pkgs.runCommand "hyprune-minimal-world-check" {} ''
          ${p.core}/bin/hyprune-world-check ${p.world-minimal}/share/hyprune/worlds/com.hyprune.minimal > $out
        '';
        lua-configs = pkgs.runCommand "hyprune-kit-lua-checks" { nativeBuildInputs = [ pkgs.python3 ]; } ''
          export HOME=$TMPDIR/home XDG_CONFIG_HOME=$TMPDIR/config XDG_RUNTIME_DIR=$TMPDIR/runtime
          mkdir -p "$HOME" "$XDG_CONFIG_HOME/hyprune" "$XDG_RUNTIME_DIR" $out
          chmod 700 "$XDG_RUNTIME_DIR"
          for kit in minimal lumen-reach dev; do
            python3 ${self}/runtime/setup.py render --kit ${self}/kits/$kit/kit.toml \
              --output "$XDG_CONFIG_HOME/hyprune" --plugin /tmp/verification-only.so \
              --input-default ${inputs.core}/config/input.default.json
            # Config verification returns before compositor/display initialization.
            ${p.hyprland}/bin/Hyprland --verify-config --i-am-really-stupid \
              -c "$XDG_CONFIG_HOME/hyprune/session.lua" > $out/$kit.log 2>&1
          done
        '';
      });
    };
}
