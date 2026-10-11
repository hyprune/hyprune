# Front-door verification

Validation date: 2026-10-08. Local only; no push, deployment, live plugin load,
owner-session compositor command, or component checkout edit.

## 2026-10-10: core 9587032, shell 78e6749, sdk be7a020, schema f76922b (IPC 0.19)

IPC 0.18 (offload device selection, automatic power cap and its source) and
0.19 (player settings, view bob, reticle and reach limits) across schema, SDK,
shell and core. Core `9587032` also includes:
- the NVIDIA consumer offload fix;
- carry sweeps that query the world BVH (a back-face grab in Lumen Reach blocked
  the press handler for 234–239 ms on the laptop and 561 ms on 10.2.2.2; it now
  takes 0.15–0.17 ms);
- live titles for room windows;
- the room-20 smoke run;
- the remote nightly.

Core `9587032` was locked by hand before it was pushed: rev, commit time, and
`nix hash path` of its `git archive` tree on 10.2.2.2. On 10.2.2.2
(`scripts/nix-remote.sh`): `nix flake check` passed, with core CTest 27/27.

## 2026-10-10: sdk e2b458e, schema bf8d401 (derived version lists)

Schema `bf8d401` derives IPC protocol and contract versions (after `f9f357d`
derived world formats) from its versioned directories. SDK `e2b458e` vendors
it and generates `PROTOCOLS`/`ProtocolMethods` from the vendored pins
(generation fails if a pin lacks a method map). Locked by hand before those
commits were pushed: narHash from `git archive` bytes, method checked against
sdk `0cf79a4`'s existing entry, and equal to the path-override hashes on
10.2.2.2. On 10.2.2.2: `nix flake check` passed (sdk 66 pass, 2 skipped).
`release-worlds` re-ran with the new SDK. Kits were built.

## 2026-10-10: core a804191, shell 6d293bb; shell catalog in drift checks

A live session with Lumen Reach 0.9.0 died in the shell launcher ("Unsupported
world format"): shell 21c90fd's catalog stopped at 0.5, and the meta checks only
looked at core. Pins: core `a804191` (single ready notice), shell `6d293bb`
(catalog 0.1–0.7, derived from vendored schema pins). `world-formats` now also
imports the pinned shell catalog (fails on 21c90fd: "format 0.7 not accepted by
pinned shell (0.1, 0.2, 0.3, 0.4, 0.5)"). `release-worlds` validates each real
package with that catalog and with `hyprune world validate`. On the build host:
`nix flake check` passed (core CTest 23/23, shell 120 OK, 1 skipped). Kits were
built.

## 2026-10-10: core 9e50dfb, Lumen Reach 0.9.0

Core `9e50dfb` (autodrive on stairs, idle wall recomposition fix, walls in
native stacking order); shell, sdk and schema unchanged. No packaging change.
On the build host: `nix flake check` passed (core CTest 23/23 including the new
autodrive test). `release-worlds` loads Lumen Reach 0.9.0 (format 0.7, four
canonical areas, slots 01–04, no warnings) and Switchyard 0.1.1.
`world-formats` passed. kit-lumen-reach, kit-dev and default were built.

## 2026-10-10: pin bump (IPC 0.16, Lumen Reach 0.8.0)

Pins: core `35ace21` (IPC 0.16 upscaler, shader specialisation, parallel
compile, capture watermark, world 0.7), shell `21c90fd` (IPC 0.16 upscaler UI,
brand mark), sdk `0cf79a4`, schema `1ae2ed1`. The only packaging change: the
shell launches on IPC 0.16. Brand masks are compiled into core. New core and
shell files need no extra inputs.

Built on the build host (`scripts/nix-remote.sh`, x86_64-linux), not locally:

| Build / check | Result |
| --- | --- |
| `nix flake check` (all x86_64 checks) | Passed |
| core | CTest 22/22, including capture-watermark and render (software EGL) |
| shell | 118 tests OK, 1 skipped (brand sync needs a sibling meta checkout) |
| sdk | 66 pass, 0 fail |
| `world-formats` | lumen-reach 0.7, switchyard 0.2, minimal 0.3 within core 0.1–0.7 |
| `release-worlds` | Lumen Reach 0.8.0 (format 0.7): 4 areas, slots 01–04, no warnings; Switchyard 0.1.1: no warnings |
| kit-lumen-reach, kit-dev, kit-minimal/default | Built (Lumen Reach 0.8.0 package, app icon installed) |
| aarch64-linux | Evaluation only |

## 2026-10-09: pins to current main

Pins: core `49c8408` (world formats 0.1–0.7, render-on-demand, FSR 1 default),
shell `043e115` (IPC 0.15), sdk `2a0742d`, schema `6250450`. The previous core
pin (`5761416`) predated world format registries and could not load Lumen Reach
0.7.1 (format 0.5). `world-formats` now fails on such a pin.

Packaging changes: core needs lua, libpng, freetype, fontconfig, Vulkan loader
and headers, and libgbm. meshoptimizer, basisu/zstd and FSR 1 are vendored.
The offload renderer path is embedded like the daemon's and is installed. CTest
generates the climbing fixture and uses jsonschema + referencing. The shell
launches on IPC 0.15, and its tests need node, numpy and Pillow.

Built on the build host (`scripts/nix-remote.sh`, x86_64-linux, clean pinned
sources), not locally:

| Build / check | Result |
| --- | --- |
| core | Built; CTest 21/21 including render tests with software EGL |
| shell | Built; 103 Python tests OK |
| sdk | Built; 65 Node tests pass, 0 fail |
| starter, default, kit-lumen-reach, kit-dev | Built |
| `nix flake check` (all x86_64 checks) | Passed, including `world-formats`, `release-worlds`, `lua-configs`, `modules`, `contracts` |
| `release-worlds` | Lumen Reach 0.7.1 (format 0.5): 4 areas, slots 01–04, no warnings; Switchyard 0.1.1 (format 0.2): no warnings |
| aarch64-linux | Evaluation only (`flake check --no-build --all-systems`); not built |
| Live session | Not run |

## Repo layout and build ownership

```text
flake.nix, flake.lock        compatibility inputs, packages, checks, contributor shells
component-pins.json         matching non-Nix commit snapshot
nix/                       component derivations and pinned compositor packaging
modules/                   NixOS / Home Manager options and session integration
kits/{lumen-reach,minimal,dev}/kit.toml
runtime/                   kit compiler, trusted session launcher, installer
install.sh                 Arch-first entry point
worlds/releases.json        release URLs, hashes and formatVersion
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
