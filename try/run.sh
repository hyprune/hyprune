#!/usr/bin/env bash
# Start Hyprune from this try folder. Config, state and caches stay in the folder.
#   ./run               a nested Hyprland window in your current Wayland session
#   ./run --size WxH    window size (default 1600x900)
#   ./run --live        load into your running Hyprland, for this login only
#   ./run --stop        undo --live: unload Hyprune, restore your session
#   ./run --status      show the --live state and logs
# Uninstall: ./uninstall (deletes this folder; nothing else to undo).
set -euo pipefail
DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
WORLD=$(<"$DIR/.world")
PY=$DIR/venv/bin/python
export XDG_CONFIG_HOME=$DIR/config XDG_STATE_HOME=$DIR/state XDG_DATA_HOME=$DIR/data XDG_CACHE_HOME=$DIR/cache
export PATH=$DIR/bin:$PATH
export HYPRUNE_PLUGIN=$DIR/core/lib/hyprune-core.so HYPRUNE_DAEMON=$DIR/core/bin/hypruned \
    HYPRUNE_RENDERER=$DIR/core/bin/hyprune-renderer
unset HYPRUNE_PACKAGED_WORLD_DIRS HYPRUNE_LIBRARY_DIR HYPRUNE_SOCKET HYPRUNE_TOKEN_FD
live() {
    HYPRUNE_LIVE_BUILD_DIR=$DIR/core/live/build/live HYPRUNE_SHELL_DIR=$DIR/shell \
        "$PY" "$DIR/core/live/dev/live/live.py" "$@"
}

card() {
    cat <<EOF

  Hyprune: $1
  Click into the window first. Super chords also work with Alt here.
    Move    W A S D or arrows, mouse to look, Space up, Ctrl down, Shift sprint
    Act     E use a window in place, F focus it, left click: primary, 1-5 tools
    Menu    hold Tab        Keymap  https://hyprune.com/keymap/
    Leave   Back or Alt+Tab: free cursor; Alt+F12: world <-> desktop; Alt+1..4: homes
    Quit    Alt+Shift+Q, close the window, or Ctrl+C in this terminal

EOF
}

case ${1:-} in
    '' | --size)
        if [[ ${1:-} == --size ]]; then export HYPRUNE_TRY_SIZE=${2:?--size needs WxH, e.g. 1280x720}; fi
        [[ -n ${WAYLAND_DISPLAY:-} ]] || { echo "run: needs a Wayland session (WAYLAND_DISPLAY is unset)" >&2; exit 1; }
        card "a nested window (${HYPRUNE_TRY_SIZE:-1600x900}); your own session is untouched."
        # The nested session gets its own runtime dir, deleted on exit, and reaches your
        # session through an absolute socket path. Hyprland's socket paths must stay under
        # 108 bytes, so a long runtime base falls back to /tmp.
        [[ $WAYLAND_DISPLAY == /* ]] || export WAYLAND_DISPLAY=${XDG_RUNTIME_DIR:?}/$WAYLAND_DISPLAY
        base=$XDG_RUNTIME_DIR
        ((${#base} <= 20)) || base=/tmp
        runtime=$(mktemp -d "$base/ht.XXXX")
        trap 'cp "$runtime"/hypr/*/hyprland.log "$DIR/state/hyprland.log" 2>/dev/null; rm -rf "$runtime"' EXIT
        log=$DIR/state/session.log
        echo "  (logs: $log)"
        code=0
        XDG_RUNTIME_DIR=$runtime "$PY" "$DIR/meta/runtime/session.py" --window --enter >"$log" 2>&1 || code=$?
        if ((code)); then tail -5 "$log"; echo "run: the session ended with code $code; full log: $log" >&2; fi
        exit "$code" ;;
    --live)
        [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]] || { echo "run --live: start it from a terminal inside Hyprland" >&2; exit 1; }
        cat <<EOF
WARNING: --live loads Hyprune's plugin into the Hyprland session you are using now.
It changes nothing on disk and ends with this login, but a plugin crash takes your
session (and unsaved work) with it. The way back:
    $DIR/run --stop      (also works from a TTY: Ctrl+Alt+F3, log in, run it)
EOF
        if [[ ${2:-} != --yes ]]; then
            read -rp "Load into this session now? [y/N] " answer </dev/tty || answer=
            [[ $answer == [yY]* ]] || { echo "Nothing changed."; exit 0; }
        fi
        live up --world "$DIR/data/hyprune/worlds/$WORLD"
        echo "Undo with: $DIR/run --stop" ;;
    --stop) live down ;;
    --status) live status ;;
    -h | --help) sed -n '2,8p' "${BASH_SOURCE[0]}" ;;
    *) echo "run: unknown option $1 (try --help)" >&2; exit 2 ;;
esac
