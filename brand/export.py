#!/usr/bin/env python3
"""Regenerate Hyprune's raster brand exports from the SVG masters.

Needs resvg on PATH (tested with 0.48.1) and Pillow for the opaque Apple touch
icon. Run from anywhere: python3 brand/export.py [--check]
"""
import argparse
import hashlib
import io
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

BRAND = Path(__file__).resolve().parent
SVG = BRAND / 'svg'

# App icon sizes and the drawing each one uses (size rule: H 16-47 px,
# optical room 48-95 px, full room from 96 px). The 16-unit H is drawn for
# exactly 16 px; the 32-unit H covers 17-47 px.
APP_SIZES = [16, 24, 32, 48, 64, 96, 128, 256, 512, 1024]


def app_source(size):
    if size == 16:
        return SVG / 'favicon-16-dark.svg'
    if size < 48:
        return SVG / 'favicon-32-dark.svg'
    if size < 96:
        return SVG / 'app-optical-dark.svg'
    return SVG / 'app-primary-dark.svg'


# The browser favicon keeps the approved H in every frame (tab context).
FAVICON_FRAMES = [(16, SVG / 'favicon-16-dark.svg'), (32, SVG / 'favicon-32-dark.svg'),
                  (48, SVG / 'favicon-32-dark.svg')]


def render(svg, size, out):
    subprocess.run(['resvg', '-w', str(size), '-h', str(size), str(svg), str(out)], check=True)


def pack_ico(frames):
    """ICO with PNG-compressed frames, smallest first."""
    header = struct.pack('<HHH', 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    entries, blobs = b'', b''
    for size, data in frames:
        entries += struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return header + entries + blobs


def build(out):
    (out / 'png').mkdir(parents=True)
    (out / 'web').mkdir()
    for size in APP_SIZES:
        render(app_source(size), size, out / 'png' / f'hyprune-app-{size}.png')
    frames = []
    for size, svg in FAVICON_FRAMES:
        frame = out / f'favicon-{size}.png'
        render(svg, size, frame)
        frames.append((size, frame.read_bytes()))
    (out / 'web/favicon.ico').write_bytes(pack_ico(frames))
    from PIL import Image
    touch = out / 'touch.png'
    render(BRAND / 'web/apple-touch-icon.svg', 180, touch)
    buffer = io.BytesIO()
    Image.open(touch).convert('RGB').save(buffer, 'PNG', optimize=True)
    (out / 'web/apple-touch-icon.png').write_bytes(buffer.getvalue())


def outputs(root):
    return sorted(p.relative_to(root) for p in [*(root / 'png').glob('*.png'),
                                                 root / 'web/favicon.ico', root / 'web/apple-touch-icon.png'])


def pixels(path):
    from PIL import Image
    if path.suffix == '.ico':
        data = path.read_bytes()
        count = struct.unpack('<H', data[4:6])[0]
        frames = []
        for i in range(count):
            length, offset = struct.unpack('<II', data[14 + 16 * i:22 + 16 * i])
            frame = Image.open(io.BytesIO(data[offset:offset + length]))
            frames.append((frame.size, frame.convert('RGBA').tobytes()))
        return frames
    image = Image.open(path)
    return image.size, image.convert('RGBA').tobytes()


def write_sums():
    files = sorted(p for p in BRAND.rglob('*') if p.is_file() and p.name != 'SHA256SUMS'
                   and '__pycache__' not in p.parts)
    lines = [f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(BRAND)}' for p in files]
    (BRAND / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Compare pixels with the committed exports; write nothing')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='hyprune-brand-') as temp:
        out = Path(temp)
        build(out)
        if args.check:
            stale = [str(p) for p in outputs(out) if not (BRAND / p).exists() or pixels(BRAND / p) != pixels(out / p)]
            if stale:
                sys.exit('Stale brand exports: ' + ', '.join(stale))
            print('Brand exports match the SVG masters.')
            return
        for rel in outputs(out):
            # Keep committed bytes when pixels match, so reruns are no-ops.
            if (BRAND / rel).exists() and pixels(BRAND / rel) == pixels(out / rel):
                continue
            (BRAND / rel).parent.mkdir(exist_ok=True)
            shutil.copyfile(out / rel, BRAND / rel)
    write_sums()
    print(f'Wrote {len(APP_SIZES)} app PNGs, favicon.ico, apple-touch-icon.png and SHA256SUMS.')


if __name__ == '__main__':
    main()
