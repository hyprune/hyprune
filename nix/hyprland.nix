{ inputs, pkgs }:
let
  # Hyprland's CMake falls back to Glaze 7.2.0 through FetchContent (v0.56 asked for 7...<8,
  # its nixpkgs carried 8). Pin that release, offline; don't let FetchContent use the network.
  glaze = (pkgs.glaze.override { enableSSL = false; enableInterop = false; }).overrideAttrs {
    version = "7.2.0";
    src = pkgs.fetchFromGitHub {
      owner = "stephenberry";
      repo = "glaze";
      tag = "v7.2.0";
      hash = "sha256-f3NVRi3SXKo42hn0WCw7JsOK3EkdOVJIcuzhPorKjFY=";
    };
  };
in inputs.hyprland.packages.${pkgs.stdenv.hostPlatform.system}.hyprland.override {
  glaze-hyprland = glaze;
}
