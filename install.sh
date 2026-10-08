#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if ! command -v python3 >/dev/null 2>&1; then
  if [[ " ${*} " == *" --dry-run "* ]]; then
    echo 'Dry run: Python 3.11+ is required to inspect kits; no changes made.'
    echo 'On Arch: sudo pacman -S --needed python'
    exit 0
  fi
  echo 'Install Python 3.11+ first (Arch: sudo pacman -S --needed python).' >&2
  exit 1
fi
exec python3 "$SCRIPT_DIR/runtime/install.py" "$@"
