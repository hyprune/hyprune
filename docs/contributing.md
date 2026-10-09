# Build and test the front door

This repo packages component source through non-flake source inputs. Component
repositories require no Nix files. `flake.nix` pins Hyprland to **v0.56.2** and
follows **that flake's nixpkgs**. Both the plugin and compositor use Hyprland's
stdenv and dependency graph. Nix modules choose that same compositor and portal;
an unrelated system Hyprland build is not ABI-compatible just because its
displayed version matches. Core retains its exact runtime ABI gate.

`nix/hyprland.nix` pins Glaze 7.2.0 because the tag's own nixpkgs lock provides
Glaze 8 while 0.56.2's CMake accepts only 7. Both plugin and session use that same
corrected derivation; nothing in the Hyprland source/tag or its nixpkgs is changed.

`component-pins.json` records the non-Nix source commits. `flake.lock` locks the
same GitHub commits plus public build dependencies. All six components remain
source inputs for the compatibility snapshot, even when docs/schema/worlds
authoring source is not a build dependency. Generated world art is distributed
through hashed release archives, never a Blender build on the user's machine.

## Docker when Nix isn't installed

From this repo, with sibling checkouts present:

```sh
./scripts/nix-docker.sh flake check --print-build-logs
./scripts/nix-docker.sh build .#core .#shell .#sdk .#starter .#world-minimal .#default --print-build-logs
```

Heavy builds (core, Hyprland, Glaze, every check) belong on the bake host, not
a laptop. `scripts/nix-remote.sh` stages clean `git archive` snapshots of each
component at its `flake.lock` revision plus this working tree, then runs the same
`nixos/nix` container over SSH on `HYPRUNE_BUILD_HOST` (default `10.2.2.2`). No
GitHub token leaves your machine. The release archives are private, so download
them first (`gh release download`) and point `HYPRUNE_RELEASE_DIR` at them; they
are seeded as fixed outputs:

```sh
HYPRUNE_RELEASE_DIR=/tmp/releases ./scripts/nix-remote.sh flake check --keep-going --print-build-logs
HYPRUNE_RELEASE_DIR=/tmp/releases ./scripts/nix-remote.sh build --no-link .#core .#kit-lumen-reach
```

`world-formats` fails when the pinned core's own format registry
(`src/world/Format.hpp`) can't load a release's recorded `formatVersion`, or
the bundled Minimal world. `release-worlds` runs the pinned `hyprune-world-check`
on the real release packages and checks the recorded `formatVersion`. Update
`worlds/releases.json` (`formatVersion` included), the core pin and
`component-pins.json` together.

Set `HYPRUNE_COMPONENT_ROOT=/absolute/path/to/hyprune` for another sibling root.
The script runs `docker run --rm -v "$PWD:/src" -w /src nixos/nix`, mounts the
component root read-only at `/components`, enables `nix-command flakes`, and adds
`--override-input core path:/components/core` (and shell/sdk/worlds/schema/docs).
It uses a named `hyprune-nix-store` volume for downloaded/build dependencies and
the official [Hyprland cache](https://github.com/hyprwm/hyprland-wiki/blob/main/content/nix/cachix.md).
No GPU, compositor socket or home directory is mounted. Git's explicit `/src`
safe-directory entry accommodates the container's root UID.

Overrides include local uncommitted files and generated data in those paths;
they do not update the committed GitHub lock (`--no-write-lock-file`). A clean
snapshot can instead be mounted from `git archive` for each recorded commit.
Do not commit a lockfile containing `/components` paths. World `dist/` is not
used for release fetches, even when present in the local input.

Normal `flake check` evaluates every package and module but **does not fetch the
TODO release-world derivations**. Its checks build core, shell, SDK and starter,
run core CTest using software EGL, shell unit tests, starter tests, ShellCheck,
SDK tests (two real-core interoperability tests can skip), validate the Minimal
package with core's offline checker, and evaluate both NixOS and Home Manager
with a Minimal kit. `nix build .#default`
also builds the original Minimal world. Release packages can be tested only
after replacing their URLs/hashes, or by overriding their hashed archive source
in an explicitly temporary test expression; don't publish placeholder success.

Nix contributor shells:

```sh
nix develop        # core compiler/dependencies, Node, Python, formatting tools
nix develop .#worlds  # package validation/tools; no local Blender
```

## Arch without a GPU

```sh
docker run --rm -v "$PWD:/src:ro" -w /src archlinux:latest bash -lc '
  set -e
  pacman -Sy --noconfirm python zstd git
  export HOME=/tmp/hyprune-test XDG_CONFIG_HOME=/tmp/hyprune-test/config XDG_DATA_HOME=/tmp/hyprune-test/data PYTHONDONTWRITEBYTECODE=1
  mkdir -p "$HOME"
  ./install.sh --dry-run --kit minimal
  ./install.sh --dry-run --kit lumen-reach
  ./install.sh --dry-run --uninstall
  python -m unittest discover -s tests -v
  test -z "$(ls -A "$HOME")"
'
```

These validate installer planning, preservation/backup prompts, safe archive
extraction and credential/session lifecycle through fixtures. They do not prove
that today's rolling Arch packages match the pinned compositor. Full script
build/run acceptance needs an isolated Arch environment with 0.56.2 plus matching
generated headers and a GPU/display. Never test by loading into an owner's
desktop. For real component acceptance use core's verified nested harness under
`flock /tmp/worldshell-nested.lock`; don't bypass it with bare `hyprctl`.

## CI and changes

GitHub Actions uses `cachix/install-nix-action`, runs flake check and the explicit
builds, and tests Arch dry runs. While components are private, set
`HYPRUNE_READ_TOKEN` to a read-only fine-grained token authorized for their repos.
The standard `GITHUB_TOKEN` alone cannot read sibling private repos. Fork PRs
cannot use the secret; their private-input jobs will fail until public access or
a reviewed private-checkout workflow is arranged. No `pull_request_target` code
execution or deployment is configured. The optional manual release-world job
checks `published` before fetching showcase archives.

Update component commit pins and SDK's `npmDepsHash` together with relevant
contract checks. Keep build-path adjustments in `nix/packages.nix` and the
script's private source copy until core gains an install target. Commit messages
must end with:

```text
Co-Authored-By: Krombopulos Michael <Krombopulos.Michael@mail99.me>
```
