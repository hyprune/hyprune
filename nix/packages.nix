{ inputs, self, pkgs }:
let
  inherit (pkgs) lib;
  hyprland = import ./hyprland.nix { inherit inputs pkgs; };
  python = pkgs.python3.withPackages (p: [ p.jsonschema ]);
  # Core's wire/schema tests validate with jsonschema + referencing.
  testPython = pkgs.python3.withPackages (p: [ p.jsonschema p.referencing ]);
  # Shell's own tests also compute HUD contrast (numpy, Pillow) and run QML JS with node.
  shellTestPython = pkgs.python3.withPackages (p: [ p.jsonschema p.referencing p.numpy p.pillow ]);
  core = hyprland.stdenv.mkDerivation {
    pname = "hyprune-core";
    version = "0.3.0";
    src = inputs.core;
    nativeBuildInputs = (with pkgs; [ cmake ninja pkg-config wayland-scanner ]) ++ [ testPython ];
    # meshoptimizer, basisu/zstd (KTX2) and FidelityFX FSR 1 are vendored in
    # third_party; overlay text, the optional Vulkan offload renderer and the
    # Lua config need system libraries.
    buildInputs = hyprland.buildInputs ++ (with pkgs; [
      libGL libxml2 openssl lua libpng freetype fontconfig vulkan-loader vulkan-headers libgbm
    ]);
    propagatedBuildInputs = [ hyprland.dev ];
    # Upstream embeds build-tree helper paths (daemon, offload renderer) and has no
    # install rule. Keep that packaging adjustment here rather than changing core.
    postPatch = ''
      substituteInPlace CMakeLists.txt \
        --replace-fail ${lib.escapeShellArg ("$" + "{CMAKE_CURRENT_BINARY_DIR}/hypruned")} "$out/bin/hypruned" \
        --replace-fail ${lib.escapeShellArg ("$" + "{CMAKE_CURRENT_BINARY_DIR}/hyprune-renderer")} "$out/bin/hyprune-renderer"
    '';
    # Generated (gitignored) CTest fixtures: m2.py also writes atrium and materials.
    preConfigure = ''
      python3 tests/fixtures/m2.py
      python3 tests/fixtures/climbing.py
    '';
    cmakeFlags = [ "-DBUILD_TESTING=ON" ];
    nativeCheckInputs = [ pkgs.mesa ];
    doCheck = true;
    checkPhase = ''
      runHook preCheck
      export EGL_PLATFORM=surfaceless LIBGL_ALWAYS_SOFTWARE=1
      export __EGL_VENDOR_LIBRARY_FILENAMES=${pkgs.mesa}/share/glvnd/egl_vendor.d/50_mesa.json
      export XDG_RUNTIME_DIR=$TMPDIR/runtime
      mkdir -m 700 "$XDG_RUNTIME_DIR"
      ctest --output-on-failure
      runHook postCheck
    '';
    installPhase = ''
      mkdir -p $out/lib $out/bin $out/share/hyprune
      cp hyprune-core.so $out/lib/hyprune-core.so
      cp hypruned hyprune-renderer hyprune-world-check $out/bin/
      cp ../config/input.default.json $out/share/hyprune/input.default.json
      mkdir -p $out/share/licenses/hyprune-core
      cp ../LICENSE $out/share/licenses/hyprune-core/
      cp -r ../third_party $out/share/licenses/hyprune-core/
    '';
    passthru = { inherit hyprland; };
    meta = { license = lib.licenses.mit; platforms = lib.platforms.linux; };
  };
  shell = pkgs.stdenvNoCC.mkDerivation {
    pname = "hyprune-shell"; version = "0.2.0"; src = inputs.shell;
    nativeBuildInputs = [ pkgs.makeWrapper ];
    dontBuild = true;
    installPhase = ''
      mkdir -p $out/share/hyprune-shell $out/bin
      cp -r qml bridge protocol $out/share/hyprune-shell/
      cp LICENSE README.md $out/share/hyprune-shell/
      makeWrapper ${python}/bin/python3 $out/bin/hyprune-shell \
        --add-flags "$out/share/hyprune-shell/bridge/launch.py" \
        --prefix PATH : ${lib.makeBinPath [ pkgs.quickshell ]} \
        --prefix QML_IMPORT_PATH : ${pkgs.qt6.qt5compat}/lib/qt-6/qml
    '';
    doInstallCheck = true;
    installCheckPhase = ''
      PATH=${pkgs.nodejs}/bin:$PATH ${shellTestPython}/bin/python3 -m unittest discover -s tests -v
    '';
    meta.license = lib.licenses.mit;
  };
  sdk = pkgs.buildNpmPackage {
    pname = "hyprune-sdk"; version = "0.4.0"; src = inputs.sdk;
    npmDepsHash = "sha256-GfNhuMZBf6WmgtvSXUzYPqpMwpkTsJTfPFpsXuHVC2k=";
    nodejs = pkgs.nodejs_24;
    npmFlags = [ "--ignore-scripts" ];
    npmBuildScript = "build";
    doCheck = true;
    checkPhase = ''npm test'';
    nativeBuildInputs = [ pkgs.makeWrapper pkgs.gnutar pkgs.zstd ];
    postInstall = ''
      wrapProgram $out/bin/hyprune --prefix PATH : ${lib.makeBinPath [ pkgs.gnutar pkgs.zstd ]}
    '';
    meta = { license = lib.licenses.mit; mainProgram = "hyprune"; };
  };
  releases = builtins.fromJSON (builtins.readFile ../worlds/releases.json);
  releaseWorld = name: let r = releases.${name}; in pkgs.stdenvNoCC.mkDerivation {
    pname = "hyprune-world-${name}"; inherit (r) version;
    src = pkgs.fetchurl { inherit (r) url; hash = r.nixHash; };
    nativeBuildInputs = [ pkgs.zstd ];
    dontBuild = true;
    unpackPhase = ''mkdir package; tar --zstd -xf $src -C package'';
    installPhase = ''
      mkdir -p $out/share/hyprune/worlds
      cp -r package/${r.id} $out/share/hyprune/worlds/
      test -f $out/share/hyprune/worlds/${r.id}/world.json
    '';
    meta = { license = lib.licenses.cc-by-40; platforms = lib.platforms.linux; };
  };
  world-minimal = pkgs.runCommand "hyprune-world-minimal-0.1.0" {} ''
    mkdir -p $out/share/hyprune/worlds/com.hyprune.minimal
    cp ${../worlds/minimal}/* $out/share/hyprune/worlds/com.hyprune.minimal/
  '';
  starter = pkgs.stdenvNoCC.mkDerivation {
    pname = "hyprune-starter"; version = "0.1.0"; src = self;
    nativeBuildInputs = [ pkgs.makeWrapper ]; dontBuild = true;
    installPhase = ''
      mkdir -p $out/share/hyprune $out/bin
      cp -r runtime kits worlds $out/share/hyprune/
      cp LICENSE $out/share/hyprune/
      # App icons (H / optical / full room by size) and the brand licence note.
      ${python}/bin/python3 runtime/icons.py $out/share/icons
      install -Dm644 brand/README.md $out/share/licenses/hyprune-brand/README.md
      makeWrapper ${python}/bin/python3 $out/bin/hyprune-setup \
        --add-flags "$out/share/hyprune/runtime/setup.py" \
        --set HYPRUNE_INPUT_DEFAULT ${core}/share/hyprune/input.default.json \
        --set HYPRUNE_PLUGIN ${core}/lib/hyprune-core.so \
        --set HYPRUNE_DEFAULT_WORLD_DIR ${world-minimal}/share/hyprune/worlds
      makeWrapper ${python}/bin/python3 $out/bin/hyprune-session \
        --add-flags "$out/share/hyprune/runtime/session.py" \
        --set HYPRUNE_PLUGIN ${core}/lib/hyprune-core.so \
        --prefix PATH : ${lib.makeBinPath [ hyprland shell pkgs.kitty pkgs.btop sdk ]}
    '';
    meta = { license = lib.licenses.mit; mainProgram = "hyprune-session"; };
  };
in lib.mapAttrs' (name: _: lib.nameValuePair "world-${name}" (releaseWorld name)) releases // {
  inherit core shell sdk starter world-minimal hyprland;
  default = pkgs.symlinkJoin {
    name = "hyprune-minimal";
    paths = [ core shell sdk starter world-minimal pkgs.kitty pkgs.btop ];
  };
  kit-minimal = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
  kit-lumen-reach = pkgs.symlinkJoin {
    name = "hyprune-lumen-reach";
    paths = [ core shell sdk starter (releaseWorld "lumen-reach") pkgs.kitty pkgs.btop ];
  };
  kit-dev = pkgs.symlinkJoin {
    name = "hyprune-dev";
    paths = [ core shell sdk starter world-minimal (releaseWorld "switchyard") pkgs.kitty pkgs.btop ];
  };
}
