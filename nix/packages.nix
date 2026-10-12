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
    version = "0.6.0";
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
    nativeCheckInputs = [ pkgs.mesa pkgs.zstd ]; # zstd: the catalog test packs .tar.zst fixtures
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
      cp hypruned hyprune-renderer hyprune-world-check hyprune-object-check $out/bin/
      cp ../config/input.default.json $out/share/hyprune/input.default.json
      # Machines: the data.publish source helper (hyprune-session starts it for
      # sources.json from <prefix>/libexec, beside lib/) and the system gauge script.
      install -Dm755 ../dev/machines/source-helper.py $out/libexec/hyprune/source-helper
      install -Dm755 ../dev/machines/scripts/system-gauges.py $out/share/hyprune/machines/system-gauges.py
      ln -s ../share/hyprune/machines/system-gauges.py $out/bin/hyprune-system-gauges
      for script in $out/libexec/hyprune/source-helper $out/share/hyprune/machines/system-gauges.py; do
        substituteInPlace $script --replace-fail '#!/usr/bin/env python3' '#!${pkgs.python3.interpreter}'
      done
      mkdir -p $out/share/licenses/hyprune-core
      cp ../LICENSE $out/share/licenses/hyprune-core/
      cp -r ../third_party $out/share/licenses/hyprune-core/
    '';
    doInstallCheck = true;
    installCheckPhase = ''
      runHook preInstallCheck
      # Both run from the installed paths alone (standard-library Python, no checkout).
      $out/libexec/hyprune/source-helper --help > /dev/null
      $out/bin/hyprune-system-gauges ram | ${pkgs.python3.interpreter} -c 'import json, sys; assert json.load(sys.stdin)["label"] == "RAM"'
      runHook postInstallCheck
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
    pname = "hyprune-sdk"; version = "0.7.0"; src = inputs.sdk;
    npmDepsHash = "sha256-vb3T6xbrQpyOcYxPBv22fMdK5fjCUAmzc1lP56VHd3Q=";
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
  # Official object libraries as read-only system libraries (RFC-0011, RFC-0015): each output
  # is a library root, $out/share/hyprune/libraries/<id>@<version>/, for HYPRUNE_LIBRARY_DIR.
  # Core skips symlinked entries, so point at these outputs, never at a symlinked profile.
  # Same extractor, limits and data-only rules as the installer.
  libraryPins = import ./library-pins.nix { inherit lib; };
  releaseLibrary = r: pkgs.runCommand "hyprune-library-${r.id}-${r.version}" {
    src = pkgs.fetchurl { inherit (r) url; hash = r.nixHash; };
    nativeBuildInputs = [ pkgs.python3 pkgs.zstd ];
    passthru = { inherit (r) id version formatVersion; };
    meta = { license = lib.licenses.cc-by-40; platforms = lib.platforms.all; };
  } ''
    python3 -I ${../runtime/content.py} unpack-library --archive "$src" --id ${r.id} --version ${r.version} \
      --out "$out/share/hyprune/libraries"
  '';
  libraries = lib.mapAttrs (_: releaseLibrary) libraryPins;
  world-minimal = pkgs.runCommand "hyprune-world-minimal-0.1.0" {} ''
    mkdir -p $out/share/hyprune/worlds/com.hyprune.minimal
    cp ${../worlds/minimal}/* $out/share/hyprune/worlds/com.hyprune.minimal/
  '';
  starter = pkgs.stdenvNoCC.mkDerivation {
    pname = "hyprune-starter"; version = "0.1.0"; src = self;
    nativeBuildInputs = [ pkgs.makeWrapper ]; dontBuild = true;
    installPhase = ''
      mkdir -p $out/share/hyprune $out/bin
      cp -r runtime kits worlds try $out/share/hyprune/
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
  # `nix run github:hyprune/hyprune#try`: the try folder's nested window, with the
  # pinned Hyprland that core was built against, so the plugin ABI always matches.
  # Config, state and caches live in one folder (default ~/hyprune-try-nix).
  try = pkgs.writeShellApplication {
    name = "hyprune-try";
    runtimeInputs = [ python hyprland shell sdk pkgs.kitty pkgs.btop pkgs.coreutils ];
    text = ''
      dir=''${HYPRUNE_TRY_DIR:-$HOME/hyprune-try-nix}
      while (($#)); do
        case $1 in
          --dir) dir=$2; shift ;;
          --size) export HYPRUNE_TRY_SIZE=$2; shift ;;
          *) echo "usage: hyprune-try [--dir DIR] [--size WxH]   (uninstall: rm -rf DIR)"; exit 0 ;;
        esac
        shift
      done
      [[ -n ''${WAYLAND_DISPLAY:-} ]] || { echo "hyprune-try: needs a Wayland session" >&2; exit 1; }
      mkdir -p "$dir"/{config,state,cache,data/hyprune/worlds}
      world=${releaseWorld "lumen-reach"}/share/hyprune/worlds/${releases.lumen-reach.id}
      # Core refuses symlinked world packages: copy it out of the store once.
      [[ -d $dir/data/hyprune/worlds/${releases.lumen-reach.id} ]] ||
        cp -r --no-preserve=mode "$world" "$dir/data/hyprune/worlds/"
      export XDG_CONFIG_HOME=$dir/config XDG_STATE_HOME=$dir/state XDG_DATA_HOME=$dir/data XDG_CACHE_HOME=$dir/cache
      export HYPRUNE_LIBRARY_DIR=${lib.concatMapStringsSep ":" (l: "${l}/share/hyprune/libraries") (lib.attrValues libraries)}
      python3 ${starter}/share/hyprune/try/prepare.py --folder "$dir" --kit ${starter}/share/hyprune/kits/lumen-reach/kit.toml \
        --plugin ${core}/lib/hyprune-core.so --input-default ${core}/share/hyprune/input.default.json
      # Outside NixOS there is no /run/opengl-driver: use this Mesa (Intel, AMD, nouveau).
      if [[ ! -e /run/opengl-driver ]]; then
        export __EGL_VENDOR_LIBRARY_FILENAMES=${pkgs.mesa}/share/glvnd/egl_vendor.d/50_mesa.json \
          LIBGL_DRIVERS_PATH=${pkgs.mesa}/lib/dri GBM_BACKENDS_PATH=${pkgs.mesa}/lib/gbm
      fi
      [[ $WAYLAND_DISPLAY == /* ]] || export WAYLAND_DISPLAY=$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY
      base=$XDG_RUNTIME_DIR
      ((''${#base} <= 20)) || base=/tmp
      runtime=$(mktemp -d "$base/ht.XXXX")
      trap 'rm -rf "$runtime"' EXIT
      echo "Hyprune (Nix): a nested window; your session is untouched. Quit: Alt+Shift+Q or Ctrl+C."
      # sources.json in the folder's config feeds gauges through core's source helper.
      export HYPRUNE_SOURCE_HELPER=${core}/libexec/hyprune/source-helper
      XDG_RUNTIME_DIR=$runtime python3 ${starter}/share/hyprune/runtime/session.py --window --enter \
        --hyprland ${hyprland}/bin/Hyprland
    '';
  };
in lib.mapAttrs' (name: _: lib.nameValuePair "world-${name}" (releaseWorld name)) releases // libraries // {
  inherit core shell sdk starter world-minimal hyprland try;
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
