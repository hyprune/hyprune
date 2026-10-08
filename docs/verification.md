# Front-door verification

Validation date: 2026-10-08. Local only; no push, deployment, live plugin load,
owner-session compositor command, or component checkout edit.

## Repo layout and build ownership

```text
flake.nix, flake.lock        compatibility inputs, packages, checks, contributor shells
component-pins.json         matching non-Nix commit snapshot
nix/                       component derivations and pinned compositor packaging
modules/                   NixOS / Home Manager options and session integration
kits/{lumen-reach,minimal,dev}/kit.toml
runtime/                   kit compiler, trusted session launcher, installer
install.sh                 Arch-first entry point
worlds/releases.json        explicit TODO release URLs/hashes
worlds/minimal/             tiny original, data-only CC0 world
scripts/                   Docker Nix testing, deterministic Minimal generation
tests/                     starter/config/archive/credential tests
.github/workflows/ci.yml    flake checks/builds and Arch container dry runs
docs/zero-to-the-trailer.md illustrated site-ready first-launch guide
docs/images/               resized original gallery stills + provenance
proposals/                 hyprpm manifest prerequisite, no component mutation
```

Core is compiled here from its source input, with the pinned Hyprland headers,
stdenv and matching dependency graph. It installs `lib/hyprune-core.so`,
`bin/hypruned` and `bin/hyprune-world-check`, plus the canonical keymap.
Shell installs QML, vendored protocol files and the Python bridge with a
Quickshell/Python wrapper. SDK uses its npm lock and a verified npm-dependency
hash, builds the CLI, and wraps its tar/zstd tools. Starter supplies config
generation and the inherited-FD session launcher. NixOS and Home Manager both
evaluate full configurations using the Minimal kit.

Release worlds use fixed-output fetches with TODO hashes; Minimal is included
directly. `default`/`kit-minimal` join the working components and Minimal.
`kit-lumen-reach` and `kit-dev` add their release worlds. The Arch installer
builds core/SDK in private copied/cloned sources and uses a Python venv for shell.

## Results

The completed Nix build/check results are recorded below. Validation
uses clean `git archive` snapshots at `component-pins.json` through local path
overrides, so it tests the same bytes hashed in the committed GitHub lock without
requiring access to private GitHub repos. Component working-tree changes are
outside this snapshot and remain untouched.

| Check | Result |
| --- | --- |
| Starter tests on host | Passed: 17 tests |
| Arch container dry runs | Passed: Minimal, showcase, dev and uninstall; temporary user directory stayed empty |
| Arch process/config/archive tests | Passed: 17 tests |
| Docker `nix flake check` | Passed: all eight x86_64-linux checks, using clean pinned component sources |
| Docker package builds | Passed: core, shell, SDK, starter, world-minimal and default on x86_64-linux |
| Core CTest | Passed: 8/8, including render tests with software EGL |
| Shell Python tests | Passed: 42/42 |
| SDK Node tests | Passed: 53; two optional integration tests skipped; no failures |
| Packaged entry points | Passed: config installation twice, session/shell/SDK help, offline world checker; isolated Docker home |
| Hyprland 0.56.2 Lua verification | Passed: generated configs for all three kits; config verification only |
| Both supported architectures | Passed: x86_64-linux and aarch64-linux flake evaluation; ARM builds not run |
| Minimal core offline validation | Passed: one area, three anchors, 12 collision triangles |
| Release-world fetches | Expected failure: both TODO GitHub Release URLs returned HTTP 404 |
| NixOS / Home Manager | Full configurations evaluated in module checks; no system activation |
| Live DRM or real session | Not run; core's supervised hardware-cursor acceptance remains pending |

An upstream Nix packaging issue was reproduced and corrected here: Hyprland
0.56.2 requests Glaze 7, while its own locked nixpkgs supplies Glaze 8. The
`nix/hyprland.nix` dependency override pins the tag's exact fallback Glaze 7.2.0
with its measured hash. Plugin and session use the same corrected derivation.
Neither the Hyprland tag nor its nixpkgs lock is changed.

The script's full Arch compilation/session install is not claimed: the dry-run
container has no pinned Hyprland or GPU. Fedora/Debian script installation is
unimplemented. Container software EGL tests do not establish live hardware-cursor
behavior, arbitrary app compatibility or iGPU performance.

See [contributor commands](contributing.md) to reproduce. Raw logs are kept
locally in `.test-results/` (ignored by Git). See [release decisions](releases.md)
for world hosting, public access, CI credentials, UWSM/token renewal and the
supervised first-session steps.
