#!/usr/bin/env bash
# Hyprune compatibility check.   curl -fsSL https://hyprune.com/check | bash
#
# Read-only: it installs, writes and changes nothing. Its only network request
# downloads the pinned manifest (try/manifest.json). No telemetry.
#   --json          machine-readable report
#   --live          check for `try --live` (load into your running Hyprland)
#   --dir DIR       folder the try would use (disk space), default ~/hyprune-try
#   --ref REF       meta repository ref for the manifest (default main)
#   --manifest SRC  manifest URL or file instead
# Exit status: 0 ready (possibly with notes), 1 not yet, 2 usage error.
set -uo pipefail

REF=${HYPRUNE_REF:-main}
MANIFEST=${HYPRUNE_MANIFEST:-}
DIR=$HOME/hyprune-try
JSON=0 LIVE=0
NIX_CMD="nix --extra-experimental-features 'nix-command flakes' run github:hyprune/hyprune#try"

parse_check_args() {
    while (($#)); do
        case $1 in
            --json) JSON=1 ;;
            --live) LIVE=1 ;;
            --dir) DIR=${2:?--dir needs a path}; shift ;;
            --ref) REF=${2:?--ref needs a ref}; shift ;;
            --manifest) MANIFEST=${2:?--manifest needs a URL or file}; shift ;;
            -h | --help) echo "usage: check.sh [--json] [--live] [--dir DIR] [--ref REF] [--manifest URL|FILE]"; exit 0 ;;
            *) echo "check: unknown option $1" >&2; exit 2 ;;
        esac
        shift
    done
    MANIFEST=${MANIFEST:-https://raw.githubusercontent.com/hyprune/hyprune/$REF/try/manifest.json}
}

# --- results -----------------------------------------------------------------
IDS=() STATES=() LABELS=() DETAILS=() FIXES=()
add() { # add ok|note|fail ID "Label" "detail" ["fix command"]
    STATES+=("$1") IDS+=("$2") LABELS+=("$3") DETAILS+=("$4") FIXES+=("${5:-}")
}
have() { command -v "$1" >/dev/null 2>&1; }
# Version comparison: version_ge 3.12.1 3.11
version_ge() { [[ $(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1) == "$2" ]]; }
# One "key": value per line in the manifest; plain bash, no sed/awk needed.
manifest_get() {
    local line re="^ *\"$1\": *\"?([^\",]*)\"?,?$"
    while IFS= read -r line; do [[ $line =~ $re ]] && { echo "${BASH_REMATCH[1]}"; return; }; done <<<"$MANIFEST_TEXT"
}

# Copy-paste install commands for this distribution, from generic names.
pkg_name() {
    case $FAMILY:$1 in
        arch:python) echo python ;;
        debian:python) echo python3 python3-venv ;;
        *:python) echo python3 ;;
        arch:eglinfo | debian:eglinfo) echo mesa-utils ;;
        fedora:eglinfo) echo egl-utils ;;
        opensuse:eglinfo) echo Mesa-demo-egl ;;
        nixos:eglinfo) echo mesa-demos ;;
        arch:build) echo base-devel cmake ninja pkgconf hyprgraphics pixman libdrm libxkbcommon pango wayland \
            wayland-protocols mesa libxml2 openssl lua libpng freetype2 fontconfig vulkan-icd-loader vulkan-headers ;;
        *:coreutils) echo coreutils ;;
        *) echo "$1" ;;
    esac
}
install_cmd() {
    local names=() n
    for n; do read -ra more <<<"$(pkg_name "$n")"; names+=("${more[@]}"); done
    case $FAMILY in
        arch) echo "sudo pacman -S --needed ${names[*]}" ;;
        fedora) echo "sudo dnf install ${names[*]}" ;;
        debian) echo "sudo apt install ${names[*]}" ;;
        opensuse) echo "sudo zypper install ${names[*]}" ;;
        nixos) echo "nix-shell -p ${names[*]}" ;;
        *) if have nix; then echo "nix profile install ${names[*]/#/nixpkgs#}"
           else echo "install with your package manager: ${names[*]}"; fi ;;
    esac
}
nix_fix() {
    if have nix; then echo "$NIX_CMD"
    else echo "sh <(curl -L https://nixos.org/nix/install) --daemon   # then: $NIX_CMD"; fi
}

# --- checks ------------------------------------------------------------------
check_os() {
    local ID='' ID_LIKE='' PRETTY_NAME=''
    # shellcheck disable=SC1091
    [[ -r /etc/os-release ]] && . /etc/os-release
    ARCH=$(uname -m)
    case " $ID $ID_LIKE " in
        *" nixos "*) FAMILY=nixos ;;
        *" arch "*) FAMILY=arch ;;
        *" fedora "* | *" rhel "*) FAMILY=fedora ;;
        *" debian "* | *" ubuntu "*) FAMILY=debian ;;
        *suse*) FAMILY=opensuse ;;
        *) FAMILY=other ;;
    esac
    if [[ $(uname -s) != Linux ]]; then add fail os "OS" "$(uname -s): Hyprune needs Linux"; return; fi
    case $FAMILY in
        arch) add ok os "OS" "${PRETTY_NAME:-Arch Linux} ($ARCH)" ;;
        nixos) add ok os "OS" "${PRETTY_NAME:-NixOS} ($ARCH): use the Nix path" "$NIX_CMD" ;;
        *) add note os "OS" "${PRETTY_NAME:-unknown} ($ARCH): the prebuilt core targets Arch Linux; elsewhere use the Nix path" "$(nix_fix)" ;;
    esac
}

check_session() {
    local socket=${WAYLAND_DISPLAY:-} runtime=${XDG_RUNTIME_DIR:-/run/user/$(id -u)} name='' sway
    [[ -n $socket && $socket != /* ]] && socket=$runtime/$socket
    if [[ -z $socket || ! -S $socket ]]; then
        WAYLAND=0
        add fail session "Wayland session" "${XDG_SESSION_TYPE:-no graphical session}: the nested window needs a Wayland session" \
            "log into a Wayland session (Plasma, GNOME, Hyprland) and rerun from its terminal"
        return
    fi
    WAYLAND=1
    if [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]]; then name=Hyprland
    elif [[ -n ${SWAYSOCK:-} ]]; then name=sway
    else name=${XDG_CURRENT_DESKTOP:-unknown compositor}; fi
    # Nested Hyprland binds xdg_wm_base v6; wayland-info shows what the session offers.
    if have wayland-info; then
        local v
        v=$(timeout 3 wayland-info 2>/dev/null | sed -n "s/.*'xdg_wm_base',.*version: *\([0-9]*\).*/\1/p" | head -1)
        if [[ -n $v && $v -lt 6 ]]; then
            add fail session "Wayland session" "$name offers xdg_wm_base v$v; the nested window needs v6" \
                "run from a KWin, GNOME or Hyprland session, or use --live inside Hyprland"
            return
        fi
    elif [[ $name == sway ]] && sway=$(sway --version 2>/dev/null | grep -o '[0-9][0-9.]*' | head -1) && ! version_ge "$sway" 1.13; then
        add fail session "Wayland session" "sway $sway offers xdg_wm_base v5; the nested window needs v6" \
            "run from a KWin, GNOME or Hyprland session, or use --live inside Hyprland"
        return
    fi
    add ok session "Wayland session" "$name (${WAYLAND_DISPLAY})"
}

check_hyprland() {
    local want out commit abi='' running=''
    want=$(manifest_get hyprland)
    want=${want:-unknown}
    HYPR_OK=0 ABI=''
    if ! have Hyprland; then
        if [[ $FAMILY == arch ]]; then
            add fail hyprland "Hyprland" "not installed (need $want)" "$(install_cmd hyprland)"
        else
            add fail hyprland "Hyprland" "not installed (need $want); the Nix path brings it" "$(nix_fix)"
        fi
        return
    fi
    out=$(XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/tmp} Hyprland --version 2>/dev/null)
    HYPR_VERSION=$(sed -n 's/^Hyprland \([0-9][0-9.]*\).*/\1/p' <<<"$out" | head -1)
    commit=$(sed -n 's/.* at commit \([0-9a-f]\{40\}\).*/\1/p' <<<"$out" | head -1)
    hlib() { sed -n "s/^$1: built against \([0-9]*\.[0-9]*\).*/\1/p" <<<"$out" | head -1; }
    # The plugin ABI hash: commit plus the major.minor of each hypr* library.
    [[ -n $commit ]] && abi="${commit}_aq_$(hlib Aquamarine)_hu_$(hlib Hyprutils)_hg_$(hlib Hyprgraphics)_hc_$(hlib Hyprcursor)_hlg_$(hlib Hyprlang)"
    if [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} ]] && have hyprctl; then
        running=$(hyprctl version -j 2>/dev/null | sed -n 's/.*"tag": *"v\{0,1\}\([^"]*\)".*/\1/p' | head -1)
    fi
    ABI=$abi
    if [[ $HYPR_VERSION != "$want" ]]; then
        local fix
        if [[ $FAMILY == arch ]]; then
            fix="sudo pacman -U https://archive.archlinux.org/packages/h/hyprland/$(manifest_get hyprlandArchPackage)-$ARCH.pkg.tar.zst   # or: $NIX_CMD"
        else fix=$(nix_fix); fi
        add fail hyprland "Hyprland" "${HYPR_VERSION:-unknown version} installed; Hyprune's plugin ABI needs exactly $want" "$fix"
        return
    fi
    HYPR_OK=1
    if [[ -n $running && $running != "$want" ]]; then
        add note hyprland "Hyprland" "$want installed, but the running session is $running: log out and back in before --live"
    else
        add ok hyprland "Hyprland" "$want${running:+ (running)}"
    fi
    if [[ $LIVE == 1 && -z ${HYPRLAND_INSTANCE_SIGNATURE:-} ]]; then
        add fail live "Live mode" "--live loads into a running Hyprland session; none found" "run from a terminal inside Hyprland, or drop --live for the nested window"
    fi
}

check_core() {
    local url headers missing=() m tool
    url=$(manifest_get corePrebuiltUrl)
    CORE=none
    [[ $HYPR_OK == 1 ]] || return
    if [[ -n $url && $url == *"$ARCH"* && -n $ABI && $ABI == "$(manifest_get hyprlandAbi)" ]]; then
        CORE=prebuilt
        add ok core "Hyprune core" "prebuilt for your Hyprland ABI ($(manifest_get coreVersion))"
        return
    fi
    if [[ -n $url && -n $ABI && $ABI != "$(manifest_get hyprlandAbi)" ]]; then
        m="your Hyprland build's ABI differs from the prebuilt core's; "
    else
        m="no prebuilt core is published for this pin yet; "
    fi
    if [[ $FAMILY != arch ]]; then
        add fail core "Hyprune core" "${m}building it is only validated on Arch" "$(nix_fix)"
        return
    fi
    headers=$(pkg-config --modversion hyprland 2>/dev/null)
    for tool in cmake ninja c++ pkg-config strip; do have "$tool" || missing+=("$tool"); done
    if [[ $headers != "$(manifest_get hyprland)" ]] || ((${#missing[@]})) ||
        ! pkg-config --exists pixman-1 libdrm xkbcommon hyprgraphics pangocairo wayland-server lua libxml-2.0 \
            openssl libpng freetype2 fontconfig vulkan gbm 2>/dev/null; then
        add fail core "Hyprune core" "${m}it builds from source into the folder, which needs build tools and Hyprland ${headers:+$headers }headers" \
            "$(install_cmd build hyprland)"
        return
    fi
    CORE=source
    add note core "Hyprune core" "${m}it builds from source into the folder (about 5-15 minutes)"
}

check_gpu() {
    local card vendor driver names=() es='' renderer='' line
    for card in /sys/class/drm/card[0-9]*; do
        [[ $card == *-* || ! -r $card/device/vendor ]] && continue
        vendor=$(<"$card/device/vendor")
        driver=$(basename "$(readlink "$card/device/driver" 2>/dev/null)")
        case $vendor in 0x8086) vendor=Intel ;; 0x1002) vendor=AMD ;; 0x10de) vendor=NVIDIA ;; esac
        names+=("$vendor ($driver)")
    done
    GPU_NAMES=${names[*]}
    if ((${#names[@]} == 0)); then
        # shellcheck disable=SC2034 # read by check_nix
        GPU_NAMES=''
        add note gpu "GPU" "no DRM GPU visible (container or VM?)"
    elif (($(printf '%s\n' "${names[@]}" | sort -u | wc -l) > 1)); then
        add note gpu "GPU" "${names[*]}: hybrid graphics; the nested window renders on your desktop's GPU"
    elif ((${#names[@]} > 1)); then
        add ok gpu "GPU" "${#names[@]}x ${names[0]}"
    else
        add ok gpu "GPU" "${names[0]}"
    fi
    # GL drivers keep shader caches under ~/.cache; switch them off so the probe writes nothing.
    local nocache=(env MESA_SHADER_CACHE_DISABLE=true MESA_GLSL_CACHE_DISABLE=true __GL_SHADER_DISK_CACHE=0)
    if have eglinfo; then
        local egl
        egl=$("${nocache[@]}" eglinfo -B 2>/dev/null)
        line=$(grep -m1 'OpenGL ES profile version' <<<"$egl")
        es=$(grep -o 'OpenGL ES [0-9.]*' <<<"$line" | head -1)
        renderer=$(grep -m1 'OpenGL ES profile renderer' <<<"$egl" | sed 's/.*renderer: *//')
    elif have python3; then
        line=$("${nocache[@]}" python3 -I -c "$GL_PROBE" 2>/dev/null)
        es=$(grep -o 'OpenGL ES [0-9.]*' <<<"$line" | head -1)
        renderer=${line#*|}
    fi
    es=${es#OpenGL ES }
    if [[ -z $es ]] && have eglinfo; then
        add note egl "EGL / GLES" "eglinfo finds no OpenGL ES device: check your GPU driver"
    elif [[ -z $es ]]; then
        add note egl "EGL / GLES" "could not query (install eglinfo to check)" "$(install_cmd eglinfo)"
    elif ! version_ge "$es" 3.0; then
        add fail egl "EGL / GLES" "OpenGL ES $es; Hyprune needs 3.0 or newer"
    elif [[ $renderer == *llvmpipe* || $renderer == *softpipe* ]]; then
        add note egl "EGL / GLES" "OpenGL ES $es on software rendering ($renderer): expect low frame rates"
    else
        add ok egl "EGL / GLES" "OpenGL ES $es${renderer:+, ${renderer# }}"
    fi
}
# Fallback GLES probe (no eglinfo): a surfaceless EGL context, nothing drawn.
GL_PROBE='
import ctypes as C, ctypes.util as U
egl = C.CDLL(U.find_library("EGL") or "libEGL.so.1"); gl = C.CDLL(U.find_library("GLESv2") or "libGLESv2.so.2")
P = C.c_void_p; egl.eglGetPlatformDisplay.restype = egl.eglGetDisplay.restype = egl.eglCreateContext.restype = P
egl.eglGetPlatformDisplay.argtypes = [C.c_uint, P, P]; egl.eglInitialize.argtypes = [P, P, P]
egl.eglChooseConfig.argtypes = [P, P, P, C.c_int, P]; egl.eglCreateContext.argtypes = [P, P, P, P]
egl.eglMakeCurrent.argtypes = [P, P, P, P]; gl.glGetString.restype = C.c_char_p
for d in (egl.eglGetPlatformDisplay(0x31DD, None, None), egl.eglGetDisplay(None)):
    cfg, n = P(), C.c_int()
    if not d or not egl.eglInitialize(d, None, None) or not egl.eglBindAPI(0x30A0): continue
    if not egl.eglChooseConfig(d, (C.c_int * 5)(0x3040, 0x40, 0x3033, 0, 0x3038), C.byref(cfg), 1, C.byref(n)) or n.value < 1: continue
    ctx = egl.eglCreateContext(d, cfg, None, (C.c_int * 3)(0x3098, 3, 0x3038))
    if ctx and egl.eglMakeCurrent(d, None, None, ctx):
        print(gl.glGetString(0x1F02).decode(), "|", gl.glGetString(0x1F01).decode()); break
'

check_tools() {
    local py qs want missing=() t
    want=$(manifest_get python)
    if py=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null) && version_ge "$py" "${want:-3.11}"; then
        if python3 -c 'import venv, ensurepip' 2>/dev/null; then add ok python "Python" "$py"
        else add fail python "Python" "$py without venv/ensurepip" "$(install_cmd python)"; fi
    else
        add fail python "Python" "${py:-not installed}; need ${want:-3.11}+" "$(install_cmd python)"
    fi
    want=$(manifest_get quickshell)
    if have qs || have quickshell; then
        qs=$({ qs --version || quickshell --version; } 2>/dev/null | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1)
        if [[ -n $qs ]] && ! version_ge "$qs" "$want"; then add note quickshell "Quickshell" "$qs; tested with $want or newer"
        else add ok quickshell "Quickshell" "${qs:-present}"; fi
    else
        case $FAMILY in
            arch) add fail quickshell "Quickshell" "not installed" "$(install_cmd quickshell)" ;;
            fedora) add fail quickshell "Quickshell" "not installed" "sudo dnf copr enable errornointernet/quickshell && sudo dnf install quickshell" ;;
            *) add fail quickshell "Quickshell" "not installed; not packaged for this distribution, the Nix path brings it" "$(nix_fix)" ;;
        esac
    fi
    for t in curl tar zstd sha256sum; do have "$t" || missing+=("$t"); done
    if ((${#missing[@]})); then
        add fail tools "Download tools" "missing: ${missing[*]}" "$(install_cmd "${missing[@]/sha256sum/coreutils}")"
    else
        add ok tools "Download tools" "curl, tar, zstd, sha256sum"
    fi
    if have kitty; then add ok terminal "Terminal" "kitty (desk terminals in the world)"
    else add note terminal "Terminal" "kitty not found: the world's desk terminals stay empty" "$(install_cmd kitty)"; fi
}

check_resources() {
    local need path free ram key supply on_battery=0
    need=$(manifest_get diskMiB)
    [[ $CORE == source ]] && need=$(manifest_get diskSourceMiB)
    need=${need:-1000}
    path=$DIR
    while [[ ! -d $path ]]; do path=$(dirname "$path"); done
    read -r _ _ _ free _ < <(df -Pk "$path" | tail -1)
    free=$((free / 1024))
    if ((free < need)); then add fail disk "Disk space" "$free MiB free in $path; need $need MiB" "free some space, or pass --dir on a larger disk"
    else add ok disk "Disk space" "$free MiB free in $path (need $need MiB)"; fi
    while read -r key ram _; do [[ $key == MemTotal: ]] && break; done </proc/meminfo
    ram=$((ram / 1024))
    if ((ram < 4096)); then add fail ram "Memory" "$ram MiB; Hyprune needs 4 GiB or more"
    elif ((ram < 8192)); then add note ram "Memory" "$ram MiB: close heavy apps first"
    else add ok ram "Memory" "$ram MiB"; fi
    for supply in /sys/class/power_supply/*; do
        [[ -r $supply/type && $(<"$supply/type") == Battery && $(<"$supply/status") == Discharging ]] 2>/dev/null && on_battery=1
    done
    ((on_battery)) && add note power "Power" "on battery: the world renders continuously; plug in for a long session"
}

check_nix() {
    if have nix; then
        local extra=''
        [[ $FAMILY != nixos && " ${GPU_NAMES:-} " == *NVIDIA* ]] && extra='; NVIDIA outside NixOS needs nixGL'
        add ok nix "Nix" "present: \`$NIX_CMD\` brings the pinned Hyprland$extra"
    fi
}

collect_checks() {
    MANIFEST_TEXT=$(if [[ -f $MANIFEST ]]; then cat "$MANIFEST"; else curl -fsSL --proto '=https,file' "$MANIFEST"; fi 2>/dev/null)
    if [[ -z $MANIFEST_TEXT ]]; then
        add fail manifest "Manifest" "could not read $MANIFEST" "check your network connection and rerun"
    fi
    check_os
    check_session
    check_hyprland
    check_core
    check_gpu
    check_tools
    check_resources
    check_nix
    local fails=0 notes=0 s
    for s in "${STATES[@]}"; do
        [[ $s == fail ]] && fails=$((fails + 1))
        [[ $s == note ]] && notes=$((notes + 1))
    done
    # The Nix path brings Hyprland, core and Quickshell itself: it needs a session and room.
    if ((fails)) && have nix && [[ $WAYLAND == 1 ]] && ! any_failed disk ram egl manifest; then VERDICT=nix
    elif ((fails)); then VERDICT=not-yet
    elif ((notes)); then VERDICT=notes
    else VERDICT=ready; fi
    FAILS=$fails
}

# True if any check in the given IDs failed (those the Nix path cannot fix).
any_failed() {
    local i id
    for i in "${!IDS[@]}"; do
        [[ ${STATES[i]} == fail ]] || continue
        for id; do [[ ${IDS[i]} == "$id" ]] && return 0; done
    done
    return 1
}

# --- output ------------------------------------------------------------------
json_str() { local s=$1; s=${s//\\/\\\\}; s=${s//\"/\\\"}; s=${s//$'\t'/\\t}; s=${s//$'\n'/\\n}; printf '"%s"' "$s"; }
report_json() {
    local i sep=''
    printf '{"verdict":%s,"distro":%s,"core":%s,"checks":[' "$(json_str "$VERDICT")" "$(json_str "$FAMILY")" "$(json_str "$CORE")"
    for i in "${!IDS[@]}"; do
        printf '%s{"id":%s,"status":%s,"label":%s,"detail":%s,"fix":%s}' "$sep" "$(json_str "${IDS[i]}")" \
            "$(json_str "${STATES[i]}")" "$(json_str "${LABELS[i]}")" "$(json_str "${DETAILS[i]}")" "$(json_str "${FIXES[i]}")"
        sep=,
    done
    printf ']}\n'
}
report_text() {
    local i mark
    echo "Hyprune compatibility check (read-only)"
    for i in "${!IDS[@]}"; do
        case ${STATES[i]} in ok) mark='✓' ;; note) mark='⚠' ;; *) mark='✗' ;; esac
        printf '  %s %-16s %s\n' "$mark" "${LABELS[i]}" "${DETAILS[i]}"
        [[ -n ${FIXES[i]} && ${STATES[i]} != ok ]] && printf '      fix: %s\n' "${FIXES[i]}"
    done
    echo
    case $VERDICT in
        ready) echo "✓ ready: curl -fsSL https://hyprune.com/try | bash" ;;
        notes) echo "⚠ ready with notes (see ⚠ above): curl -fsSL https://hyprune.com/try | bash" ;;
        nix) echo "⚠ ready with notes: the lines marked ✗ block the script path; use the Nix path: $NIX_CMD" ;;
        *) echo "✗ not yet: fix the $FAILS line(s) marked ✗, then rerun this check."
           [[ $FAMILY != arch ]] && echo "  The Nix path skips the distribution packages: $(nix_fix)" ;;
    esac
}

check_main() {
    parse_check_args "$@"
    collect_checks
    if ((JSON)); then report_json; else report_text; fi
    [[ $VERDICT != not-yet ]]
}

# try.sh sources this file with HYPRUNE_CHECK_LIB=1 and calls collect_checks itself.
[[ -n ${HYPRUNE_CHECK_LIB:-} ]] || check_main "$@"
