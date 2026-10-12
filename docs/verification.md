# Front-door verification

Validation date: 2026-10-08. Local only; no push, deployment, live plugin load,
owner-session compositor command, or component checkout edit.

## 2026-10-12: core b55058b, docs 906a19d

Core b55058b (IPC 0.22, no wire change): paths draw only in the path tool, whose points
can be aimed, dragged, inserted and removed with undo. Docs 906a19d documents it in
RFC-0006 and the keymap. `try/manifest.json` names core b55058b with its source archive
hash recomputed. `nix flake check` passed on clean `git archive` snapshots (core CTest
40/40).

## 2026-10-12: core d68ac86, docs f00dde6

Core d68ac86 (still IPC 0.22): home windows stay tiled on their wall (only the room
floats), catalog rescans, object commits and aiming no longer hitch, and the offload
worker draws world objects. `try/manifest.json` names core d68ac86
with its source archive hash recomputed. `nix flake check` passed on clean
`git archive` snapshots (core CTest 40/40).

## 2026-10-12: core 1c2cb93

Core 1c2cb93 applies deferred input at the start of the world tick, so recorded input
takes effect in its recorded frame and replays stay exact under load.
`try/manifest.json` names core 1c2cb93 with its source archive hash recomputed. `nix
flake check` passed on clean `git archive` snapshots (core CTest 40/40).

## 2026-10-12: core 027b20e, sdk d7fffb9

The sdk check's mock demo test waits for the first stats line (it ran a fixed
2.5 s window, which a slow runner missed). SDK 0.4.0, npm lock unchanged. `nix flake
check` passed on clean `git archive` snapshots; the sdk check also passes in the
sandbox limited to one CPU (110 pass / 2 skipped).
Core 027b20e gives each nested harness script its own state directory; core
CTest 40/40 in the check. `try/manifest.json` names core 027b20e with its source
archive hash recomputed.

## 2026-10-12: core 6dd4661, shell d1dd22d, sdk 3a65a64, schema ce517ea, docs b94f159 (IPC 0.22)

IPC 0.22 (the objects runtime: catalog, pocket, place, transform) across schema,
SDK, shell and core. Core 6dd4661 also composes an attached child (an X11 menu) with
its parent and pulls the natively topmost client off a wall. The launcher grants the shell `objects.control`, which it
requests only at 0.22, as `quest.control` at 0.21. `try/manifest.json` follows the
core and shell pins with recomputed source archive hashes. Core's catalog test packs
`.tar.zst` fixtures with the zstd CLI, so the core check now has zstd (the runtime
decodes archives with its vendored decoder). `nix flake check` passed on clean
`git archive` snapshots: core CTest 40/40, shell 243 tests, sdk 110 pass / 2 skipped
(SDK 0.4.0, npm lock unchanged), starter 46 tests (1 skipped).

## 2026-10-12: core eb562cd, shell c547ef8, sdk cfd7f4d, schema 9c5570d, worlds 596d0f9, docs 9769946 (IPC 0.21)

IPC 0.21 (quests and focus sessions) across schema, SDK, shell and core.
`try/manifest.json` follows the core and shell pins, with the source archive
hashes recomputed from GitHub. Lumen Reach stays at 0.10.2 (world format 0.8);
README and the zero-to-the-trailer guide describe IPC 0.21 and that release.
`nix flake check` passed on clean `git archive` snapshots of the pinned
revisions: core CTest 37/37, shell 210 tests (1 skipped), sdk 96 pass /
2 skipped (SDK 0.4.0, npm lock unchanged), starter 46 tests (1 skipped).

## 2026-10-11: worlds 3037c91; Lumen Reach 0.9.2

Lumen Reach 0.9.2 has 0.9.1's content, rebuilt so no shipped PNG carries
build-machine path metadata. Its budgets delta against 0.9.1 is 0; perf gate,
screens and routes pass (worlds `lumen-reach/reports/release.json`).
`worlds/releases.json` and the docs point to it; the worlds pin moves to the
release commit. On the build host (release archives seeded): `nix flake check`
passed, including the world-format check.

## 2026-10-11: core 86a71db, shell 163d6cf, worlds e5ca754; Switchyard 0.1.2

Go-public pins: core and shell docs without owner/agent journals, core
`dev/live` with a configurable plugin/HUD swap, the shell's HUD concept with a
neutral name (a legacy alias keeps saved preferences working), and worlds after
its history rewrite (the previous pin `be1be28` no longer exists). Switchyard
0.1.2 replaces 0.1.1 in `worlds/releases.json`. On the build host
(`scripts/nix-remote.sh`, release archives seeded with `HYPRUNE_RELEASE_DIR`
while worlds is private): `nix flake check` passed: core CTest 29/29, shell 150
tests.

## 2026-10-11: core 763a723, shell f1d65e1, sdk deb6158, schema 10fce4e, docs 53f9eae (public-prep)

The public-prep merges: canonical licences, no private paths or hosts in any
repository. Developer settings (gallery, video, build and bake hosts) come from
the environment or `~/.config/hyprune/dev.env`. The shell now negotiates its
newest protocol (IPC 0.19) on every install path, not 0.6 (Arch) or 0.16 (Nix).
README and the zero-to-the-trailer guide describe IPC 0.19 and the published
Lumen Reach 0.9.1 and Switchyard 0.1.1 releases. On the build host
(`scripts/nix-remote.sh`, release archives seeded with `HYPRUNE_RELEASE_DIR`
because the worlds releases are private): `nix flake check` passed: core CTest
28/28, shell 150 tests, sdk 70 pass / 2 skipped, starter 38 tests.

## 2026-10-10: core 9587032, shell 78e6749, sdk be7a020, schema f76922b (IPC 0.19)

IPC 0.18 (offload device selection, automatic power cap and its source) and
0.19 (player settings, view bob, reticle and reach limits) across schema, SDK,
shell and core. Core `9587032` also includes:
- the NVIDIA consumer offload fix;
- carry sweeps that query the world BVH (a back-face grab in Lumen Reach blocked
  the press handler for 234–239 ms on the laptop and 561 ms on the bake host; it now
  takes 0.15–0.17 ms);
- live titles for room windows;
- the room-20 smoke run;
- the remote nightly.

Core `9587032` was locked by hand before it was pushed: rev, commit time, and
`nix hash path` of its `git archive` tree on the bake host. On the bake host
(`scripts/nix-remote.sh`): `nix flake check` passed, with core CTest 27/27.

## 2026-10-10: sdk e2b458e, schema bf8d401 (derived version lists)

Schema `bf8d401` derives IPC protocol and contract versions (after `f9f357d`
derived world formats) from its versioned directories. SDK `e2b458e` vendors
it and generates `PROTOCOLS`/`ProtocolMethods` from the vendored pins
(generation fails if a pin lacks a method map). Locked by hand before those
commits were pushed: narHash from `git archive` bytes, method checked against
sdk `0cf79a4`'s existing entry, and equal to the path-override hashes on
the bake host. On the bake host: `nix flake check` passed (sdk 66 pass, 2 skipped).
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
