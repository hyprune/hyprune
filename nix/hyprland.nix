{ inputs, pkgs }:
let
  # v0.56.2's own nixpkgs lock carries Glaze 8, but its CMake asks for 7...<8.
  # Pin the exact fallback release, offline; don't let FetchContent use the network.
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
