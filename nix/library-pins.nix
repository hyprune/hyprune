# The published pins of libraries/releases.json (RFC-0011), by package name: `library-<name>`,
# where <name> is the release tag (from the pinned URL .../releases/download/<tag>/<asset>)
# without its `-v<version>` suffix, e.g. library-hyprune-starter.
{ lib }:
let
  releases = builtins.fromJSON (builtins.readFile ../libraries/releases.json);
  nameOf = r:
    let tag = builtins.elemAt (builtins.match ".*/releases/download/([^/]+)/[^/]+" r.url) 0;
    in "library-" + lib.removeSuffix "-v${r.version}" tag;
in lib.mapAttrs' (_: r: lib.nameValuePair (nameOf r) r) (lib.filterAttrs (_: r: r.published) releases)
