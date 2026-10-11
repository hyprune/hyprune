#!/usr/bin/env bash
# Try Hyprune from one folder.   curl -fsSL https://hyprune.com/try | bash
#   ... | bash -s -- [--dir DIR] [--world NAME] [--live] [--dry-run] [--no-run] [--ref REF]
#
# 1. Runs the compatibility check (check.sh). If something is missing it prints
#    the install commands and stops: it never runs a package manager or sudo.
# 2. Downloads into ONE folder (default ~/hyprune-try), checking every sha256:
#    core built for your Hyprland (or builds it there from source), the shell
#    with a private Python venv, and the world release.
# 3. Writes DIR/run and DIR/uninstall. Config, state and caches stay in DIR:
#    no login items, session entries, config edits or files elsewhere.
# 4. Starts DIR/run: a nested Hyprland window inside your current session.
#    --live instead loads into your running Hyprland (asks first; DIR/run --stop).
set -euo pipefail

step() { printf '\n==> %s\n' "$*"; }
die() { echo "try: $*" >&2; exit 1; }
fetch() { curl -fsSL --proto '=https,file' --retry 2 "$1" ${2:+-o "$2"}; }
verify() { echo "$2  $1" | sha256sum -c --quiet - >/dev/null 2>&1 || die "$1: sha256 mismatch, refusing it"; }

main() {
    local ref=${HYPRUNE_REF:-main} base=${HYPRUNE_BASE:-} dir=$HOME/hyprune-try world='' live=0 dry=0 run=1 here=''
    while (($#)); do
        case $1 in
            --dir) dir=${2:?--dir needs a path}; shift ;;
            --world) world=${2:?--world needs a name}; shift ;;
            --live) live=1 ;;
            --dry-run) dry=1 ;;
            --no-run) run=0 ;;
            --ref) ref=${2:?--ref needs a ref}; shift ;;
            -h | --help) echo "usage: try.sh [--dir DIR] [--world NAME] [--live] [--dry-run] [--no-run] [--ref REF]"; return ;;
            *) die "unknown option $1 (try --help)" ;;
        esac
        shift
    done
    dir=$(realpath -m "$dir")
    # From a checkout, use its files; piped, use the meta repository at --ref.
    if [[ -f ${BASH_SOURCE[0]:-} ]]; then here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd); fi
    if [[ -z $base && -n $here && -f $here/try/manifest.json ]]; then base=file://$here; fi
    base=${base:-https://raw.githubusercontent.com/hyprune/hyprune/$ref}

    step "Checking this computer (read-only)"
    # shellcheck source=try/check.sh
    HYPRUNE_CHECK_LIB=1 source <(fetch "$base/try/check.sh") || die "cannot load $base/try/check.sh"
    local check_args=(--dir "$dir" --manifest "$base/try/manifest.json")
    ((live)) && check_args+=(--live)
    set +e # check.sh is written for plain bash, without errexit
    parse_check_args "${check_args[@]}"
    collect_checks
    report_text
    set -e
    [[ $VERDICT == ready || $VERDICT == notes ]] || die "stopped before downloading anything; fix the ✗ lines above and rerun."

    local releases record wid wversion wurl wsha
    world=${world:-$(manifest_get world)}
    releases=$(fetch "$base/worlds/releases.json") || die "cannot read worlds/releases.json"
    record=$(python3 -c 'import json,sys; r=json.loads(sys.argv[1]).get(sys.argv[2]); r and r["published"] and print(r["id"], r["version"], r["url"], r["sha256"])' \
        "$releases" "$world") || true
    [[ -n $record ]] || die "no published world named $world in worlds/releases.json"
    read -r wid wversion wurl wsha <<<"$record"
    fetch "$base/kits/$world/kit.toml" >/dev/null || die "no kit for world $world"

    step "Plan"
    echo "  folder  $dir (everything goes here; ./uninstall deletes it)"
    if [[ $CORE == prebuilt ]]; then echo "  core    prebuilt $(manifest_get coreVersion) for Hyprland $(manifest_get hyprland)"
    else echo "  core    hyprune/core@$(manifest_get coreRev | cut -c1-7), built from source here (5-15 minutes)"; fi
    echo "  shell   hyprune/shell@$(manifest_get shellRev | cut -c1-7) and a private Python venv (jsonschema from PyPI)"
    echo "  world   $wid $wversion"
    if ((live)); then echo "  then    $dir/run --live (asks first)"; else echo "  then    $dir/run: a nested Hyprland window"; fi
    if ((dry)); then echo; echo "Dry run: nothing was downloaded or written."; return; fi

    if [[ -e $dir && ! -f $dir/.hyprune-try ]]; then die "$dir exists and is not a Hyprune try folder; pick another --dir"; fi
    mkdir -p "$dir"/{meta,downloads,bin,config,state,data,cache}
    manifest_get tryVersion >"$dir/.hyprune-try"
    echo "$wid" >"$dir/.world"
    local f
    mkdir -p "$dir/meta/try" "$dir/meta/worlds"
    printf '%s\n' "$MANIFEST_TEXT" >"$dir/meta/try/manifest.json"
    printf '%s\n' "$releases" >"$dir/meta/worlds/releases.json"
    for f in try/check.sh try/run.sh try/prepare.py runtime/setup.py runtime/session.py runtime/install.py \
        runtime/icons.py "kits/$world/kit.toml"; do
        mkdir -p "$(dirname "$dir/meta/$f")"
        fetch "$base/$f" "$dir/meta/$f"
    done

    get_core "$dir"
    get_shell "$dir"
    get_world "$dir" "$wid" "$wversion" "$wurl" "$wsha"

    step "Writing config into $dir"
    "$dir/venv/bin/python" "$dir/meta/try/prepare.py" --folder "$dir" --kit "$dir/meta/kits/$world/kit.toml" \
        --plugin "$dir/core/lib/hyprune-core.so" --input-default "$dir/core/share/hyprune/input.default.json"
    install -m755 "$dir/meta/try/run.sh" "$dir/run"
    write_uninstall "$dir/uninstall"
    rm -rf "$dir/downloads"

    step "Ready"
    echo "  start      $dir/run          (nested window; --size 1280x720 for a smaller one)"
    echo "  live       $dir/run --live   (your running Hyprland, this login only; undo: --stop)"
    echo "  uninstall  $dir/uninstall    (deletes the folder; nothing else to undo)"
    if ((run)) && [[ -t 1 && -e /dev/tty ]]; then
        if ((live)); then exec "$dir/run" --live </dev/tty; else exec "$dir/run" </dev/null; fi
    fi
}

get_core() {
    local dir=$1 url sha
    rm -rf "$dir/core"
    if [[ $CORE == prebuilt ]]; then
        step "Core: prebuilt for Hyprland $(manifest_get hyprland)"
        url=$(manifest_get corePrebuiltUrl) sha=$(manifest_get corePrebuiltSha256)
        fetch "$url" "$dir/downloads/core.tar.gz"
        verify "$dir/downloads/core.tar.gz" "$sha"
        tar -C "$dir/downloads" -xzf "$dir/downloads/core.tar.gz"
        mv "$dir/downloads/hyprune-core" "$dir/core"
    else
        step "Core: building hyprune/core@$(manifest_get coreRev | cut -c1-7) from source (5-15 minutes, log: $dir/build.log)"
        url=$(manifest_get coreSourceUrl) sha=$(manifest_get coreSourceSha256)
        fetch "$url" "$dir/downloads/core-src.tar.gz"
        verify "$dir/downloads/core-src.tar.gz" "$sha"
        mkdir -p "$dir/downloads/src" "$dir/downloads/tmp"
        tar -C "$dir/downloads/src" --strip-components=1 -xzf "$dir/downloads/core-src.tar.gz"
        TMPDIR=$dir/downloads/tmp HYPRLAND_VERSION=$(manifest_get hyprland) HYPRUNE_REV=$(manifest_get coreRev) \
            bash "$dir/downloads/src/dev/release/build.sh" "$dir/downloads/out" >"$dir/build.log" 2>&1 ||
            { tail -20 "$dir/build.log"; die "core build failed; full log: $dir/build.log"; }
        tar -C "$dir/downloads" -xzf "$dir"/downloads/out/*.tar.gz
        mv "$dir/downloads/hyprune-core" "$dir/core"
    fi
    # Hyprland refuses a plugin built for another ABI; say so before it does.
    [[ $(sed -n 's/.*"abiHash":"\([^"]*\)".*/\1/p' "$dir/core/abi.json") == "$ABI" ]] ||
        die "core was built for another Hyprland ABI ($(<"$dir/core/abi.json")), yours is $ABI"
    if ldd "$dir/core/lib/hyprune-core.so" | grep 'not found'; then
        die "the core plugin needs the libraries above; update your system (sudo pacman -Syu) and rerun"
    fi
}

get_shell() {
    local dir=$1
    step "Shell: hyprune/shell@$(manifest_get shellRev | cut -c1-7) and its Python venv"
    fetch "$(manifest_get shellUrl)" "$dir/downloads/shell.tar.gz"
    verify "$dir/downloads/shell.tar.gz" "$(manifest_get shellSha256)"
    rm -rf "$dir/shell" "$dir/venv"
    mkdir "$dir/shell"
    tar -C "$dir/shell" --strip-components=1 -xzf "$dir/downloads/shell.tar.gz"
    python3 -m venv "$dir/venv"
    "$dir/venv/bin/pip" install --quiet --no-cache-dir --disable-pip-version-check -r "$dir/shell/requirements.txt"
    printf '#!/bin/sh\nexec "%s/venv/bin/python" "%s/shell/bridge/launch.py" "$@"\n' "$dir" "$dir" >"$dir/bin/hyprune-shell"
    chmod 755 "$dir/bin/hyprune-shell"
}

get_world() {
    local dir=$1 id=$2 version=$3 url=$4 sha=$5 worlds=$1/data/hyprune/worlds
    if grep -qs "\"version\": *\"$version\"" "$worlds/$id/world.json"; then return; fi  # rerun: keep it
    step "World: $id (sha256 from worlds/releases.json)"
    fetch "$url" "$dir/downloads/world.tar.zst"
    verify "$dir/downloads/world.tar.zst" "$sha"
    rm -rf "${worlds:?}/${id:?}" "$dir/downloads/world"
    mkdir -p "$worlds" "$dir/downloads/world"
    # The installer's extractor rejects links, devices, traversal and oversize archives.
    "$dir/venv/bin/python" -c 'import sys; sys.path.insert(0, sys.argv[1]); from install import extract_world; extract_world(*sys.argv[2:])' \
        "$dir/meta/runtime" "$dir/downloads/world.tar.zst" "$dir/downloads/world" "$id"
    "$dir/core/bin/hyprune-world-check" "$dir/downloads/world/$id" >/dev/null
    mv "$dir/downloads/world/$id" "$worlds/$id"
}

write_uninstall() {
    cat >"$1" <<'EOF'
#!/bin/sh
# Delete this Hyprune try folder. Nothing outside it was written.
dir=$(cd "$(dirname "$0")" && pwd)
[ -f "$dir/.hyprune-try" ] || { echo "not a Hyprune try folder: $dir" >&2; exit 1; }
if [ -f "$dir/state/hyprune/live/state.json" ] && ! grep -q '"phase": "down"' "$dir/state/hyprune/live/state.json"; then
    "$dir/run" --stop || { echo "run --stop failed; Hyprune is still loaded live" >&2; exit 1; }
fi
if [ "${1:-}" != --yes ]; then
    printf 'Delete %s? [y/N] ' "$dir"
    read -r answer </dev/tty || answer=
    case $answer in [yY]*) ;; *) echo "Kept."; exit 0 ;; esac
fi
rm -rf "$dir" && echo "Removed $dir."
EOF
    chmod 755 "$1"
}

main "$@"
