# Fork a kit, or start from scratch

Copy `kits/minimal` or `kits/lumen-reach` to a directory you own and edit
`kit.toml`. Kits describe defaults; the runtime remains in core and shell.

| Field | Meaning |
| --- | --- |
| `worlds` | Official package names: `minimal`, `lumen-reach`, `switchyard` |
| `homes` | Actual positive workspace ID, label, world ID, spawn ID; optional typed area ID |
| `keymap` | `core-default-v2`: copied from core's canonical `config/input.default.json` |
| `shell_theme` | `hyprune-dark`: the current built-in shell theme; other themes are rejected |
| `apps` | Trusted user kit's command argument array, workspace, exact class/title, optional owned mount |
| `settings` | Partial `hl.plugin.hyprune.config` patch: graphics, player, windows, tools, etc. |

Bindings go into core's `layout.json` as `{id,worldId,areaId}`. Locations go into
`locations.json` as `{id,label,worldId,spawnId}`. An app with a mount gets a durable
class/title placement in its own home. The generated Lua rules place each starter
app on its workspace. The session launcher starts the app commands once per
session, without using a shell to interpret the argument array. A kit you author
can explicitly run a shell command; treat locally supplied kits as trusted config.

Lumen Reach's typed IDs are `sun-court`, `array-hall`, `rime-vault`, and
`signal-rise`. Their spawn IDs have the same names. Its optional world 0.2 mounts
extension is normalized by core without editing the package. Switchyard 0.2 has
only legacy station docks and an `arrival` spawn, so **omit `area`** for that
world. A future Switchyard package can add typed areas under a new world contract.

For example, add a cross-world destination to a Lumen Reach fork:

```toml
# Add "switchyard" to the top-level worlds array as well.
[[homes]]
workspace = 5
label = "Switchyard"
world = "com.hyprune.switchyard"
spawn = "arrival"
```

Select workspace 5 from Director Workspaces or Super+5 to trigger the installed
world's loading/warp lifecycle. Merely adding a world package to `programs.hyprune.worlds`
installs it; it doesn't invent a workspace destination. Put mappings in the kit
or your user-owned `locations.json` and restart the Hyprune session.

To start with an empty desk, delete all `[[apps]]` entries from Minimal. Keep its
single `[[homes]]` entry and create apps yourself with Super+Enter. For a new
world, author a data-only package with a `world.json`, local glTF and attribution;
verify with `hyprune-world-check /path/to/package` and the SDK before installing.
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
