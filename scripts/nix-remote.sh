#!/usr/bin/env bash
# Heavy Nix builds/checks on a remote build host over SSH, in the same
# nixos/nix container as scripts/nix-docker.sh. Components are clean
# `git archive` snapshots at the flake.lock revisions (no GitHub token leaves
# this machine). HYPRUNE_RELEASE_DIR may hold release tarballs to seed as fixed
# outputs, since the private release assets need credentials to download.
# Usage: scripts/nix-remote.sh build .#core   (default: flake check)
set -euo pipefail
SCRIPT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
COMPONENT_ROOT=${HYPRUNE_COMPONENT_ROOT:-$(dirname -- "$SCRIPT_ROOT")}
HOST=${HYPRUNE_BUILD_HOST:?set HYPRUNE_BUILD_HOST to an SSH host with Docker}
REMOTE=${HYPRUNE_BUILD_DIR:-hyprune-nixbuild}
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/src" "$STAGE/components" "$STAGE/releases"
# Tracked and untracked (not ignored) files of this repo, as a path flake.
git -C "$SCRIPT_ROOT" ls-files -z -co --exclude-standard | (cd "$SCRIPT_ROOT" && xargs -0 cp --parents -t "$STAGE/src")
OVERRIDES=()
for repo in core shell sdk worlds schema docs; do
  rev=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["nodes"][sys.argv[2]]["locked"]["rev"])' \
    "$SCRIPT_ROOT/flake.lock" "$repo")
  mkdir "$STAGE/components/$repo"
  git -C "$COMPONENT_ROOT/$repo" archive "$rev" | tar -x -C "$STAGE/components/$repo"
  OVERRIDES+=(--override-input "$repo" "path:/components/$repo")
done
if [[ -n ${HYPRUNE_RELEASE_DIR:-} ]]; then
  cp "$HYPRUNE_RELEASE_DIR"/*.tar.zst "$STAGE/releases/"
fi
if [[ $# -eq 0 ]]; then
  set -- flake check --print-build-logs
fi
rsync -a --delete "$STAGE/" "$HOST:$REMOTE/"
printf -v ARGS '%q ' --extra-experimental-features 'nix-command flakes' --option cores 0 --option max-jobs 8 \
  --option extra-substituters https://hyprland.cachix.org \
  --option extra-trusted-public-keys 'hyprland.cachix.org-1:a7pgxzMz7+chwVL3/pzj6jIBMioiJM7ypFP8PwtkuGc=' \
  "$@" --no-write-lock-file "${OVERRIDES[@]}"
# shellcheck disable=SC2029 # ARGS is quoted locally on purpose.
ssh "$HOST" "docker run --rm -v \"\$HOME/$REMOTE/src:/src\" -v \"\$HOME/$REMOTE/components:/components:ro\" \
  -v \"\$HOME/$REMOTE/releases:/releases:ro\" -v hyprune-nix-store:/nix -w /src nixos/nix:latest \
  sh -c 'for f in /releases/*.tar.zst; do [ -e \"\$f\" ] && nix-store --add-fixed sha256 \"\$f\" >/dev/null; done; exec nix \"\$@\"' sh $ARGS"
