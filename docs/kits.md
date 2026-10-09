# Fork a kit, or start from scratch

Copy `kits/minimal` or `kits/lumen-reach` to a directory you own and edit
`kit.toml`. Kits describe defaults; the runtime remains in core and shell.

| Field | Meaning |
| --- | --- |
| `worlds` | Official package names: `minimal`, `lumen-reach`, `switchyard` |
| `initial_workspace` | Native workspace the session starts on: an area home, the world room (20) or an explicit home |
| `initial_world`, `initial_spawn` | World manifest ID (and optional spawn ID) loaded at start; not needed when `initial_workspace` is an explicit home |
| `homes` | Optional explicit homes: positive workspace ID, label, world ID, spawn ID; optional typed area ID |
| `keymap` | `core-default-v2`: copied from core's canonical `config/input.default.json` |
| `shell_theme` | `hyprune-dark`: the current built-in shell theme; other themes are rejected |
| `apps` | Trusted user kit's command argument array, workspace, exact class/title; optional world/area and owned mount |
| `settings` | Partial `hl.plugin.hyprune.config` patch: graphics, player, windows, tools, etc. |

## Workspaces come from the world

The loaded world defines where workspaces are. Core runs the world itself on the
room workspace (`windows.world_workspace`, default **20**) and gives each area a
default home at `windows.workspace_base` (default **20**) plus the area's
`workspaceSlot`. Lumen Reach's homes are therefore 21 Sun Court, 22 Array Hall,
23 Rime Vault and 24 Signal Rise; Minimal's Quiet Desk is 21. A kit needs no
`[[homes]]` for these. The generated Lua binds Super+1…9 to 21…29 (base + N).

An app targets a home by its workspace number. A mounted app on a world-defined
home also names the area's `world` and `area`, because the kit compiler doesn't
read world packages. Keep the number and area consistent with the world's slot:

```toml
[[apps]]
workspace = 22
world = "com.hyprune.lumen-reach"
area = "array-hall"
class = "HypruneArray"
title = "Array Hall terminal"
argv = ["kitty", "--class", "HypruneArray", "--title", "Array Hall terminal"]
mount = "array-hall-slot-02-operator-desk-01"
```

A kit may still add explicit `[[homes]]`, and explicit homes win: core skips a
world default whose area or workspace ID is already taken by an explicit home or
a configured location. Each explicit home also takes the Super key of its last
digit. Use them for destinations the world can't define, such as a world with no
typed areas or another world to warp to, and keep them out of the room and
area-home group (20–29), for example 30 (Super+0). A home with `area` becomes a
durable binding in core's `layout.json` as `{id,worldId,areaId}`; every explicit
home becomes a location in `locations.json` as `{id,label,worldId,spawnId}`. An app
with a mount gets a durable class/title placement in its own area. The generated
Lua rules place each starter app on its workspace. The session launcher loads the
start world, then starts the app commands once per session, without using a shell
to interpret the argument array. A kit you author can explicitly run a shell
command; treat locally supplied kits as trusted config.

Profiles generated from older kits keep their explicit homes (Lumen Reach 1–4,
dev 10/11) in the user-owned `locations.json` and `layout.json`, and explicit
homes win. To adopt the world's numbering, replace the profile as described below.

Lumen Reach's typed IDs are `sun-court`, `array-hall`, `rime-vault`, and
`signal-rise`. Their spawn IDs have the same names. Its optional world 0.2 mounts
extension is normalized by core without editing the package. Switchyard 0.2 has
only legacy station docks and an `arrival` spawn, so **omit `area`** for that
world. A future Switchyard package can add typed areas under a new world contract.

For example, add a cross-world destination to a Lumen Reach fork:

```toml
# Add "switchyard" to the top-level worlds array as well.
[[homes]]
workspace = 30
label = "Switchyard"
world = "com.hyprune.switchyard"
spawn = "arrival"
```

Select workspace 30 from Director Workspaces or Super+0 to trigger the installed
world's loading/warp lifecycle. Core derives area homes only for the world that
is loaded, so a home in another world is reachable by workspace only through an
explicit location like this one (the Director's destinations also load worlds).
Merely adding a world package to `programs.hyprune.worlds` installs it; it doesn't
invent a workspace destination. Put mappings in the kit or your user-owned
`locations.json` and restart the Hyprune session.

To start with an empty desk, delete all `[[apps]]` entries from Minimal. Keep its
`initial_workspace` and `initial_world` and create apps yourself with Super+Enter.
For a new world, author a data-only package with a `world.json`, local glTF and
attribution; give each area a `workspaceSlot` so it gets a home. Verify with
`hyprune-world-check /path/to/package` and the SDK before installing.
Nix modules currently enumerate official worlds. Custom worlds can be installed
under `$XDG_DATA_HOME/hyprune/worlds/<manifest-id>` or referenced by a world directory
in the user-owned `session.json`.

Core rejects symlinks in world roots and assets. The launcher copies Nix package
bytes into that data directory on first use, rather than linking individual
worlds or files. Existing packages remain unchanged until you move them aside.

## Apply defaults without losing edits

Fresh profiles use:

```sh
./install.sh --kit-file /path/to/my-kit/kit.toml --kit minimal --dry-run
./install.sh --kit-file /path/to/my-kit/kit.toml --kit minimal
```

`--kit-file` selects the data itself; `--kit` is just the built-in fallback.
Nix users can run `hyprune-setup install --kit /path/to/my-kit/kit.toml` with
`--world-dir /nix/store/.../share/hyprune/worlds` for additional installed worlds.
Its wrapper supplies the pinned core/plugin/default input file and Minimal world.

Starter generation uses exclusive creation, including for `input.json` and
`layout.json`. A rerun, Home Manager activation, or NixOS login preserves every
existing file, including edited files and core's persistent placements. Use
Settings for keymap edits. Edit `~/.config/hyprune/hyprune.lua` for live graphics
patches through your usual Hyprland Lua reload; unchanged settings preserve poses.

To deliberately replace a profile, **after leaving the Hyprune session**, move
`~/.config/hyprune` and `~/.local/state/hyprune` to timestamped backup directories,
then regenerate/reactivate/start the new kit. Use your XDG paths if customized.
Keep those backups until you have reviewed the new profile. Rebuilds never do
this for you. Existing world directories are also preserved; upgrade them by
explicitly moving the old directory aside and reinstalling the verified package.

The independently editable `input.json`, daemon layout, editor state and Lua
graphics config are core's current contracts, not a new TOML parser inside core.
