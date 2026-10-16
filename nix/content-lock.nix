# A content lock (`hyprune content lock`, registry/v0.1/content-lock.schema.json) as packages:
# each world and library a fixed-output fetch of its locked archive (nixHash is the SRI form of
# its sha256), unpacked with the installer's archive and data-only rules. The session lists
# them as read-only system content (packaged world directories, HYPRUNE_LIBRARY_DIR).
{ pkgs, lib }:
lockFile:
let
  lock = builtins.fromJSON (builtins.readFile lockFile);
  # meta.license from a plain SPDX id; an expression or an unknown id leaves it unset.
  license = p: let id = p.license or null; in
    if id != null && builtins.match "[A-Za-z0-9.+-]+" id != null
    then (lib.getLicenseFromSpdxIdOr or (i: d: d)) id null else null;
  unpack = p: kind: pkgs.runCommand "hyprune-content-${kind}-${p.id}-${p.version}" ({
    src = pkgs.fetchurl { inherit (p) url; hash = p.nixHash; };
    nativeBuildInputs = [ pkgs.python3 pkgs.zstd ];
    passthru = { inherit (p) id version sourceLabel; };
  } // lib.optionalAttrs (license p != null) { meta.license = license p; }) ''
    python3 -I ${../runtime/content.py} unpack-${kind} --archive "$src" --id ${p.id} --version ${p.version} \
      --out "$out/share/hyprune/${if kind == "world" then "worlds" else "libraries"}"
  '';
  of = type: builtins.filter (p: p.type == type) lock.packages;
in
  assert lib.assertMsg (lock.lockVersion or null == "0.1") "content lock ${toString lockFile}: lockVersion 0.1 expected";
  { worlds = map (p: unpack p "world") (of "world"); libraries = map (p: unpack p "library") (of "library"); }
