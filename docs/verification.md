# Front-door verification

Validation date: 2026-10-08. Local only; no push, deployment, live plugin load,
owner-session compositor command, or component checkout edit.

## 2026-10-14: core 8a415a3 (v0.8.3), shell 8e987c9

Core v0.8.3 (no wire change: `shell.release` while the session is locked and a holder's
repeated `shell.claim` as a renewal, so the HUD comes back after a lock; the standing spot in
front of the player is searched past window placement zones and keep-clear volumes, and a
refusal names its rule) with its prebuilt archive for Hyprland 0.56.2 (sha256
`145ca2d8...d0268cd9`, checked against the release's `.sha256`; `abi.json` is byte-for-byte
the v0.8.2 one). Shell 8e987c9 retries a release refused while locked and claims again on the
next world entry. `try/manifest.json` names core 8a415a3 (prebuilt and source archives) and
shell 8e987c9; the Nix core package is 0.8.3 and its checks get curl (the remote runner test
fetches `file://` inputs). SDK, schema, worlds and docs pins are unchanged; try stays 0.1.5.

`nix flake check` passed on clean `git archive` snapshots (core CTest 49/49, shell 367). The
meta tests pass (81). End to end on a headless host, inside a private KWin parent with a fresh
`mktemp` HOME, `try.sh` took the prebuilt path in 23 s; in the nested window the plugin
reports `hyprune-core` 0.8.3, the player walked 8 m in Lumen Reach 0.11.2, run exited 0, and
after uninstall HOME and the runtime directory were unchanged.

## 2026-10-14: core 036d18c (v0.8.2)

Core v0.8.2 (no wire change: the offload power floor under 20 W GPUs, characters upload
over several ticks, indexed collision queries, spec-gloss character colours, X11 menu
owners) with its prebuilt archive for Hyprland 0.56.2 (sha256 `0320c311...26da5aa4d`,
checked against the release's `.sha256`; `abi.json` is byte-for-byte the v0.8.1 one).
`try/manifest.json` names core 036d18c (prebuilt and source archives); the Nix core
package is 0.8.2. Shell, SDK, schema, worlds and docs pins are unchanged; try stays 0.1.5.

`nix flake check` passed on clean `git archive` snapshots (core CTest 49/49). The meta
tests pass (81). End to end on a headless host, inside a private KWin parent with a fresh
`mktemp` HOME, `try.sh` took the prebuilt path in 17 s; in the nested window the plugin
reports `hyprune-core` 0.8.2, the player walked 8 m in Lumen Reach 0.11.2, run exited 0,
and after uninstall HOME and the runtime directory were unchanged.

## 2026-10-14: Lumen Reach 0.11.2 (worlds 7668f58), docs 3ff6c50

Lumen Reach 0.11.2 (the valley terrain carries the sky panorama: no horizon seam; rock
cliffs under the plinths): `worlds/releases.json` pins the published archive (sha256
`e8aaba3f...51dcf2b9b` checked after download, 53,905,509 bytes, Nix hash
`sha256-6Kq6P6lW...`). Core, shell, SDK and schema are unchanged; try stays 0.1.5.

`nix flake check` passed on clean `git archive` snapshots. The meta tests pass (81). End to
end on a headless host, inside a private KWin parent with a fresh `mktemp` HOME, `try.sh`
installed Lumen Reach 0.11.2 from its release in 16 s, the player walked 8 m, run exited 0,
and after uninstall HOME and the runtime directory were unchanged.

## 2026-10-13: core d1abbcb (v0.8.1), docs a19fa80

Core v0.8.1 (no wire change: offload draws assets added mid-session, the waypoint route
line on the ground and round obstructions, waypoints cleared on arrival, 4K marker labels,
display names for characters, recall spreads windows, recordings with every tool) with its
prebuilt archive for Hyprland 0.56.2 (sha256 `0215a3f8...e2cf4811`, checked against the
release's `.sha256`; `abi.json` is byte-for-byte the v0.8.0 one). `try/manifest.json`
names core d1abbcb (prebuilt and source archives); the Nix core package is 0.8.1; docs
a19fa80 adds the RFC-0004 and RFC-0012 amendments. shell, sdk, schema, worlds and the
world and library records are unchanged; `try.sh`, `check.sh` and `install.py` did not
change, so try stays 0.1.5.

`nix flake check` passed on clean `git archive` snapshots (core CTest 49/49, starter 81
tests). The meta tests pass (81). End to end on a headless host, inside a private KWin
parent with a fresh `mktemp` HOME, `try.sh` took the prebuilt path in 17 s; in the nested
window the plugin reports `hyprune-core` 0.8.1, the player walked 8 m, run exited 0, and
after uninstall HOME and the runtime directory were unchanged.

## 2026-10-13: core d3780e0 (v0.8.0), shell bc5d217, sdk 8d394be (0.10.0), schema 86fa42d (0.12.0), docs 7eeabec (IPC 0.26)

Core v0.8.0 (IPC 0.26: the debug tool on the wire, the companion's pace, whole pocket lists)
with its prebuilt archive for Hyprland 0.56.2 (sha256 `44951420...f34fb9472`, checked against
the release's `.sha256`; `abi.json` is byte-for-byte the v0.7.2 one). `try/manifest.json`
names core d3780e0 (prebuilt and source archives), shell bc5d217 and sdk 8d394be. The Nix
core package is 0.8.0 and the SDK package 0.10.0 (new `npmDepsHash`). worlds 6bb6420 and
the world and library records are unchanged; `try.sh`, `check.sh` and `install.py` did not
change, so try stays 0.1.5.

`nix flake check` passed on clean `git archive` snapshots (core CTest, shell tests, SDK 188
tests with 2 skipped, starter 81 tests with 1 skipped). The meta tests pass (81). End to end
on a headless host, inside a private KWin parent with a fresh `mktemp` HOME, `try.sh` took
the prebuilt path in 15 s; in the nested window the plugin reports `hyprune-core` 0.8.0, the
player walked 8 m, run exited 0, and after uninstall HOME and the runtime directory were
unchanged.

## 2026-10-13: Lumen Reach 0.11.1; worlds 6bb6420, docs 26591a5

`worlds/releases.json` pins Lumen Reach 0.11.1 (world format 0.9; fixes from live
testing: flush surfaces no longer depth-fight, no drain pipe stubs on the rooftop, unlit
valley terrain, residents stop in front of the screens), sha256 `940c630b...8284d`,
downloaded from the release and checked against it. `flake.lock` and
`component-pins.json` name worlds 6bb6420 and docs 26591a5; core, shell, sdk and schema
are unchanged, so try stays 0.1.5 (`try.sh` and `install.py` did not change).

`nix flake check` passed on clean `git archive` snapshots (the release-world check builds
`world-lumen-reach-0.11.1` from the pinned URL and hash). The meta tests pass (81). On a
headless host, inside a private KWin parent with a fresh `mktemp` HOME, `try.sh --dry-run`
planned core 0.7.2 (prebuilt), Lumen Reach 0.11.1 and hyprune-starter 0.2.0 and wrote
nothing.

## 2026-10-13: core 970f029 (v0.7.2), shell 61e9df6, docs 9d34605; try 0.1.5

Core v0.7.2 (no wire change) with its prebuilt archive for Hyprland 0.56.2 (same ABI
hash). The archive carries `bin/hyprune-demo-source`, the demo source a newly placed machine
starts with; the Nix core package and `install.py` now install it too. `try/manifest.json`
names core 970f029 (prebuilt and source archives) and shell 61e9df6. Try is 0.1.5 because
`install.py`, which try fetches, changed. sdk 2899916 (0.9.0), schema c694b36 (0.11.0),
worlds c331205 and the world and library records are unchanged.

`nix flake check` passed on clean `git archive` snapshots: core CTest 48/48, shell 352
tests (2 skipped), starter 81 tests (1 skipped); the SDK derivation is unchanged. The
meta tests pass (81). End to end on a headless host, inside a private KWin parent with a
fresh `mktemp` HOME:
- `try.sh` (0.1.5) took the prebuilt path. It installed core 0.7.2 at 970f029, Lumen
  Reach 0.11.0 and hyprune-starter 0.2.0 (14 objects).
- `hyprune-demo-source` from the try folder's core prints a value.
- `hyprune source list` lists the Official and Community registry sources.
- In the nested window the plugin reports `hyprune-core` 0.7.2, and the four residents
  walk.
- Director > Objects lists the starter's library objects.
- The source helper runs with `--token-refresh`.

## 2026-10-13: core 233118a (v0.7.1), shell e165fef, sdk 2899916, schema c694b36, docs bc7ffd5, worlds c331205 (IPC 0.25)

Core v0.7.1 (IPC 0.25 companions; the world root honours `XDG_DATA_HOME`) with its
prebuilt archive for Hyprland 0.56.2 (same ABI hash). `try/manifest.json` names core
233118a (prebuilt and source archives), shell e165fef, and sdk 2899916 for the CLI that
try builds. The Nix packages are core 0.7.1 and SDK 0.9.0 (its npmDepsHash follows the
lock). Schema 0.11.0. World and library records are unchanged (Lumen Reach 0.11.0,
hyprune-starter 0.2.0); tryVersion stays 0.1.4.

`nix flake check` passed on clean `git archive` snapshots: core CTest 45/45, shell 344
tests (1 skipped), sdk 186 tests (184 pass, 2 skipped), starter 81 tests (1 skipped).
The meta tests pass (81). End to end on a headless host, inside a private KWin parent
with a fresh `mktemp` HOME:
- `try.sh` took the prebuilt path. It installed core 0.7.1 at 233118a, Lumen Reach
  0.11.0 and the pinned hyprune-starter 0.2.0 library (14 objects), and wrote content
  records for both.
- `hyprune source list` from the try folder lists the Official and Community registry
  sources.
- In the nested window the loaded plugin reports `hyprune-core` 0.7.1
  (`hyprctl plugin list`), active in Lumen Reach, and the four residents walk.
- Director > Objects lists the starter's objects in the catalog (marked Library).
  Director > Library shows the two installs and both sources.
- The session started the source helper with `--token-refresh`, and it stopped with the
  session.

## 2026-10-12: sdk 3fe9393 (@hyprune/sdk 0.6.1)

SDK 0.6.1: the client holds the hello from its response frame, so an event that core
writes right behind it (in the same read) no longer drops the connection. The Nix SDK
package is version 0.6.1; its npmDepsHash follows the lock (the lock's own version field
changed it). `nix flake check` passed on clean `git archive` snapshots of the pinned
revisions.

## 2026-10-13: core f486fbb (v0.6.0), shell bc3d3cb, sdk 501eabd, schema 1741b94, docs 93b3fd3, worlds f9302c0 (IPC 0.24)

Core v0.6.0 (IPC 0.24: data sources, gauges, machines) with its prebuilt archive for
Hyprland 0.56.2 (same ABI hash). The archive carries the source helper. `try/manifest.json`
names core f486fbb (prebuilt and source archives) and shell bc3d3cb. The Nix packages
are core 0.6.0 and SDK 0.7.0 (its npmDepsHash follows the lock). Schema 0.9.0. Records:
Lumen Reach 0.11.0 (world format 0.9) in `worlds/releases.json`, hyprune-starter 0.2.0 in
`libraries/releases.json`; both archives were downloaded and their sha256 and Nix hashes
checked. Try 0.1.3 also fetches `runtime/session-daemon`, so a try session renews the
source helper's grant like an installed one.

`nix flake check` passed on clean `git archive` snapshots: core CTest 44/44, shell 311
tests (1 skipped), sdk 139 tests (137 pass, 2 skipped), starter 54 tests (1 skipped).
The meta tests pass (54). End to end on a headless host, inside a private KWin parent
with a fresh `mktemp` HOME:
- `try.sh` took the prebuilt path and installed core 0.6.0 at f486fbb and Lumen Reach
  0.11.0.
- In the nested window the loaded plugin reports `hyprune-core` 0.6.0
  (`hyprctl plugin list`), active in Lumen Reach.
- The four residents walk (NPC agents in the plugin diagnostics).
- The session started the source helper from the try folder with `--token-refresh`; it
  connected to core as `com.hyprune.sources` and stopped with the session.

## 2026-10-12: core 09abc14 (v0.5.0), shell c85606d, sdk 274e6d0, schema 2878a5e, docs 578dc32 (IPC 0.23)

Core v0.5.0 (the NPC stage, IPC 0.23; no new launch grant) with its prebuilt archive for
Hyprland 0.56.2 (same ABI hash). `try/manifest.json` names core 09abc14 (prebuilt and
source archives) and shell c85606d; the Nix packages are core 0.5.0 and SDK 0.6.0 (its
npmDepsHash follows the lock). Schema 0.8.0; worlds unchanged (Lumen Reach 0.10.3).
`nix flake check` passed on clean `git archive` snapshots: core CTest 42/42, shell 277
tests (1 skipped), sdk 126 pass / 2 skipped, starter 47 tests (1 skipped). End to end on
a headless host, inside a private KWin parent with a fresh `mktemp` HOME: `try.sh` took
the prebuilt path and installed core 0.5.0 at 09abc14, and in the nested window the
loaded plugin reports `hyprune-core` 0.5.0 (`hyprctl plugin list`), active in Lumen Reach.

## 2026-10-12: core 0c95641 (v0.4.0, the first prebuilt core)

Core v0.4.0 ships a prebuilt archive for Hyprland 0.56.2 (`abiHash`
`efb50993…_aq_0.15_hu_0.14_hg_0.5_hc_0.1_hlg_0.6`). `try/manifest.json` names it
(`coreVersion`, `corePrebuiltUrl`, `corePrebuiltSha256`) and keeps the source archive of
0c95641 for other ABIs; the Nix core package is version 0.4.0. `nix flake check` passed
on clean `git archive` snapshots (core CTest 40/40, starter 47 tests). End to end on a
headless host, inside a private KWin parent with an empty HOME: `try.sh` took the
prebuilt path (about 7 s, no build log), installed core 0.4.0 at 0c95641 with the
matching ABI and Lumen Reach 0.10.3, and `run` brought up the nested 1600x900 window in
the world (the plugin active at the arrival spawn, the shell's HUD on screen).

## 2026-10-12: worlds d155516, schema ab7a2a8, sdk 73cfa63, docs 4857140; Lumen Reach 0.10.3

Lumen Reach 0.10.3 (plain Sun Court paving) replaces 0.10.2 in `worlds/releases.json`.
`libraries/releases.json` pins the first official object library, `hyprune-starter`
0.1.0 (`com.hyprune.starter`, object format 0.10), per RFC-0011; its archive was
downloaded and matches the pinned sha256 and nixHash. Schema 0.7.0 and SDK 0.5.0 (the
Nix SDK package's version and npmDepsHash follow its lock). Core stays b55058b.
`nix flake check` passed on clean `git archive` snapshots: sdk 110 pass / 2 skipped,
starter 47 tests (1 skipped), the world-format check on the published Lumen Reach 0.10.3.

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
libraries/releases.json     official object library releases (RFC-0011)
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
