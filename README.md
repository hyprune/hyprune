# Hyprune

**Your desktop is a place.** Walk between workspace homes, keep a terminal on a
desk, pull a window into reach, and warp to the next part of your day.

This is Hyprune's front door: compatible core, Quickshell shell, SDK, original
worlds and starter kits. Start in our vision, then change every part of it.
[hyprune.com](https://hyprune.com) · [Roadmap](https://hyprune.com/roadmap/) ·
[Keymap](https://hyprune.com/keymap/)

![A live terminal on a Sun Court desk in Lumen Reach](docs/images/sun-court.jpg)

Early preview, targeting **Hyprland 0.56.2**. Core, shell and SDK speak IPC
**0.19**; the shell negotiates its newest supported protocol with core. Component
repositories are currently private. Minimal is self-contained. **Lumen Reach 0.9.1**
(world format 0.7) and **Switchyard 0.1.1** are published releases, pinned by URL
and hash in [worlds/releases.json](worlds/releases.json) and fetched by the kits
that use them. Dedicated DRM/hardware-cursor acceptance still needs a supervised
hardware checklist; container tests cannot verify it.

| Kit | First experience | Graphics | Distribution |
| --- | --- | --- | --- |
| `lumen-reach` | Sun Court, Array Hall, Rime Vault, Signal Rise; desk terminals and btop kiosk | High; switch to `intel` for a lighter tier | Lumen Reach 0.9.1 release |
| `minimal` | One quiet home, terminal, workspace wall and spare lectern; 12 triangles, no textures | Intel tier, bloom off, reduced motion | Included, original CC0 |
| `dev` | Switchyard plus a typed debug home; SDK doctor/mock and U debug capture | Auto | Switchyard 0.1.1 release |

All kits use core's M3B keymap and the shell's built-in dark theme. The loaded
world defines where workspaces are: the world itself runs on room workspace 20,
and each area's home is 20 plus its slot (Lumen Reach: 21 Sun Court, 22 Array
Hall, 23 Rime Vault, 24 Signal Rise; Minimal's Quiet Desk: 21). Kits launch their
apps on those homes and bind Super+1…9 to 21…29. Switchyard has legacy station
docks and no areas, so dev maps it as an explicit destination on workspace 30
(Super+0) without inventing typed home/mount contracts. GPU suitability depends
on hardware and output resolution; Minimal has no measured iGPU frame-rate
guarantee yet.

## Install

Access to the private component repositories is required until they become public.
Use a read-only GitHub token through Nix's `access-tokens` configuration, or the
[local Docker overrides](docs/contributing.md). No token belongs in the lockfile.

**Nix profile / other Linux distributions:**

```sh
nix profile install github:hyprune/hyprune#kit-minimal
hyprune-setup install
# Log out. From a TTY:
hyprune-session
```

`default` is the Minimal bundle; `kit-lumen-reach` and `kit-dev` also fetch the
corresponding release worlds. Outside the Nix profile, configure those kits with
`hyprune-setup install --kit /path/to/kits/<kit>/kit.toml --world-dir /path/to/world-package/share/hyprune/worlds`.
For a new kit, first move the existing starter config and layout aside as described
in [kit authoring](docs/kits.md). Nix modules supply these paths automatically.

**NixOS:** add `inputs.hyprune.url = "github:hyprune/hyprune"` to your flake, then:

```nix
imports = [ inputs.hyprune.nixosModules.default ];
programs.hyprune = {
  enable = true;
  kit = "minimal"; # or "lumen-reach", "dev"
  worlds = [];    # additional "lumen-reach", "switchyard", "minimal"
  settings.graphics = { quality = "intel"; reduced_motion = true; };
};
```

Rebuild and choose **Hyprune (minimal)** at login, or run `Hyprland` from a TTY.
The module selects the same pinned compositor used to compile the plugin, plus
its matching portal. Use Hyprune as the session entry point; UWSM credential
handoff is not implemented.

**Home Manager:** use `inputs.hyprune.homeManagerModules.default` with the same
`programs.hyprune` options. It sets `configType = "lua"`, the plugin path in
`wayland.windowManager.hyprland.plugins`, and a user-owned Lua include. Launch
Home Manager's `Hyprland` wrapper from a TTY. On NixOS, enable the system's
`programs.hyprland` with `inputs.hyprune.packages.${pkgs.stdenv.hostPlatform.system}.hyprland`
and its matching portal for system integration; let Home Manager own this user's
kit. Use one Hyprune module per user/session, rather than applying both starters.

**Arch script:** with Hyprland 0.56.2 installed:

```sh
git clone https://github.com/hyprune/hyprune
cd hyprune
./install.sh --kit minimal --dry-run
./install.sh --kit minimal
# Add ~/.local/bin to PATH. Log out, then start from a TTY:
hyprune-session
```

The script checks both the compositor binary and plugin-header version, builds
the pinned core and SDK, installs the Python bridge in a private venv, and uses
Arch's Quickshell. It uses CMake because core has no hyprpm manifest; see the
[proposal and helper-path prerequisite](proposals/README.md). It doesn't change
the compositor version for you. A newer Arch Hyprland must be deliberately
replaced with a matching build, or use Nix's pinned compositor.

Your normal Hyprland config is separate. To use it, pass
`--hyprland-config ~/.config/hypr/hyprland.lua`: the script displays the exact
diff, asks, and writes a timestamped backup before adding an include. There is
no unattended approval flag and no live reload/plugin-load command. Then launch
`hyprune-session --config ~/.config/hypr/hyprland.lua` from a TTY.

The script also puts the Hyprune app icon in `~/.local/share/icons/hicolor` and
writes a login-screen entry to `~/.local/share/hyprune/install/share/wayland-sessions/`;
it prints the `sudo install` line that lists Hyprune on your login screen, and
never runs it for you.

`./install.sh --uninstall --dry-run` previews removal; `--uninstall` removes
unchanged wrappers and icons and moves the installed build to a rollback backup. Removing
the include also requires its own diff/confirmation. Config, state, worlds,
backups and distro dependencies remain yours. Rerunning install preserves edits
and existing worlds. **Fedora/Debian package installation is not implemented or
validated**; the script reports that honestly and stops. Nix is the available
packaging path there.

## Zero to the trailer

Choose `lumen-reach`. With a release archive you already downloaded, the
[local archive path](docs/zero-to-the-trailer.md) works offline.

1. Install the kit and start its Hyprune session. Press **Super+F12** to enter
   the world. **F12** always returns to the desktop.
2. Walk toward Sun Court's workspace wall with **WASD**, **HJKL**, or arrows;
   move the mouse to look. Space jumps, Shift runs.
3. Hold **TAB for one second**, then release: Director Map stays open. Escape
   closes it. Settings edits the independently watched keymap.
4. Press **Super+1** for Sun Court's home (workspace 21), then **Super+Enter**
   for an extra terminal there. Aim at it on the wall, hold **Super+left
   mouse** to pull/carry it, and move it onto the spare desk. Slot **2**, tag
   the window, then click the desk to mount it. **E** uses it in place;
   **Super+TAB** returns to walking.
5. Hold TAB, open **Workspaces**, and select **Array Hall**. Core takes you
   to that home (workspace 22). **Super+2** also selects it. Warp out to
   another installed world through its mapped workspace; add `dev`'s
   Switchyard destination (workspace 30) to a forked kit for a cross-world
   trip. **F** brings an aimed app or workspace into native 2D; Super+TAB
   brings you back.

The full illustrated walk-through is
[docs/zero-to-the-trailer.md](docs/zero-to-the-trailer.md), ready to wire into
the documentation site. Still-image labels reflect the capture's earlier input
revision; the instructions here use the current M3B keymap.

## Make it yours

Kits are TOML data, compiled into the existing Lua, input JSON, workspace-location
JSON and persistent layout contracts. Files under `~/.config/hyprune` and
`~/.local/state/hyprune` are written only when absent. Changing the module's kit
or settings supplies new defaults for a fresh profile; it does not overwrite an
existing profile. [Fork a kit or start from scratch](docs/kits.md).

Code and docs: MIT. Quiet Desk: CC0-1.0. Lumen Reach gallery stills: Hyprune
contributors, CC-BY-4.0, resized without retouching;
[image provenance](docs/images/provenance.json). Logo and app icons: Hyprune
contributors, CC-BY-4.0; usage rules and exports in [brand/](brand/README.md). No prototype/game assets are used.

[Contributor builds and Docker testing](docs/contributing.md) ·
[Verification report](docs/verification.md) · [Owner release checklist](docs/releases.md)
