#!/usr/bin/env bash
# Uses a persistent store cache; never starts a compositor or passes GPU/session sockets.
set -euo pipefail
SCRIPT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
COMPONENT_ROOT=${HYPRUNE_COMPONENT_ROOT:-$(dirname -- "$SCRIPT_ROOT")}
NIX_ARGS=(--extra-experimental-features 'nix-command flakes' --option cores 3 --option max-jobs 2
  --option extra-substituters https://hyprland.cachix.org
  --option extra-trusted-public-keys 'hyprland.cachix.org-1:a7pgxzMz7+chwVL3/pzj6jIBMioiJM7ypFP8PwtkuGc=')
OVERRIDES=()
for repo in core shell sdk worlds schema docs; do
  if [[ ! -d "$COMPONENT_ROOT/$repo" ]]; then
    echo "Missing local checkout: $COMPONENT_ROOT/$repo" >&2
    exit 1
  fi
  OVERRIDES+=(--override-input "$repo" "path:/components/$repo")
done
if [[ $# -eq 0 ]]; then
  set -- flake check --print-build-logs
fi
exec docker run --rm \
  -v "$SCRIPT_ROOT:/src" -v "$COMPONENT_ROOT:/components:ro" \
  -e "HYPRUNE_HOST_UID=$(id -u)" -e "HYPRUNE_HOST_GID=$(id -g)" \
  -v hyprune-nix-store:/nix -w /src nixos/nix:latest \
  sh -c 'git config --global --add safe.directory /src
    result=0; nix "$@" || result=$?
    # Nix snapshots the Git index and may create tree objects as container root.
    chown -R "$HYPRUNE_HOST_UID:$HYPRUNE_HOST_GID" /src/.git/objects
    exit "$result"' sh \
  "${NIX_ARGS[@]}" "$@" --no-write-lock-file "${OVERRIDES[@]}"
