#!/usr/bin/env python3
"""Hyprune app icons for the hicolor theme, shared by Nix and the Arch installer.

Usage: icons.py DEST [--brand DIR] copies the icons under DEST/hicolor.
"""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
NAME = 'hyprune'
# brand/export.py renders each size from the drawing the size rule calls for:
# H 16-47 px, optical room 48-95 px, full room from 96 px.
SIZES = [16, 24, 32, 48, 64, 128, 256, 512]
SCALABLE = 'svg/app-primary-dark.svg'


def hicolor_files(brand=ROOT / 'brand'):
    """(source, path relative to the icon root) pairs."""
    files = [(brand / f'png/{NAME}-app-{size}.png', Path(f'hicolor/{size}x{size}/apps/{NAME}.png'))
             for size in SIZES]
    files.append((brand / SCALABLE, Path(f'hicolor/scalable/apps/{NAME}.svg')))
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dest', type=Path)
    parser.add_argument('--brand', type=Path, default=ROOT / 'brand')
    args = parser.parse_args()
    for source, relative in hicolor_files(args.brand):
        target = args.dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


if __name__ == '__main__':
    main()
