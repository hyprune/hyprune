# Hyprune brand

Source of truth for Hyprune's logo (Traverse 08 v2, plus the Bold mono weight).
Other repositories vendor files from here and record the meta-repo commit and
SHA-256 of each copied file (see [Vendoring](#vendoring)).

The mark is one complete isometric room with a single gate: a player, two
unequal windows and footsteps leaving through the opening. The companion **H**
uses the same angles, rounded ends and a dipped floor.

## Files

| Path | What |
|---|---|
| `svg/primary-{dark,light,mono}.svg` | Full-detail room, transparent. 96 px and up. |
| `svg/primary-optical-{dark,light,mono}.svg` | Optical room (simplified detail). 48–95 px. |
| `svg/monogram-16-*.svg`, `svg/monogram-32-*.svg` | H companion. 16-unit drawing at exactly 16 px; 32-unit drawing at 17–47 px. |
| `svg/lockup-{dark,light,mono}.svg`, `svg/lockup-panel-*.svg` | Mark + `hyprune` wordmark (path lettering, no font). 336 px wide and up. |
| `svg/app-{primary,optical}-{dark,light}.svg`, `svg/favicon-{16,32}-*.svg` | App tiles on a rounded navy/paper square. |
| `svg/bold/mark-bold-mono.svg` | Bold one-ink mark, 64 px and up. |
| `svg/bold/mark-bold-optical-mono.svg` | Bold optical mark, 32–63 px (use the H below 32 px). |
| `svg/bold/lockup-bold-horizontal-mono.svg` | Bold horizontal lockup, 240 px wide and up. |
| `svg/bold/lockup-bold-horizontal-small-mono.svg` | Bold lockup with simplified windows, 160–239 px wide. |
| `svg/bold/lockup-bold-stacked-mono.svg` | Bold stacked lockup (square), 160 px wide and up. |
| `png/hyprune-app-<N>.png` | App icon exports, N = 16, 24, 32, 48, 64, 96, 128, 256, 512, 1024. |
| `web/favicon.svg`, `web/favicon.ico` | Browser favicon: H on navy; ICO has 16/32/48 frames. |
| `web/apple-touch-icon.{svg,png}` | 180 × 180 opaque touch icon, full-bleed navy. |
| `export.py` | Regenerates every PNG and the ICO from the SVGs. |
| `SHA256SUMS` | Hashes of every file here; vendoring notes cite them. |

Mono and Bold SVGs draw with `currentColor`: inline them (or use them as a mask)
and set the colour from the surrounding theme. Apply opacity to the whole group
so overlapping strokes don't darken.

## Choosing a drawing

Pick by the rendered size in physical pixels:

| Size | Colour / app icon | One ink next to the wordmark, watermarks |
|---|---|---|
| 16 px | H, 16-unit drawing | H mono 16 |
| 17–31 px | H, 32-unit drawing | H mono 32 |
| 32–47 px | H, 32-unit drawing | H mono 32, or Bold optical |
| 48–63 px | Optical room | Bold optical |
| 64–95 px | Optical room | Bold mark |
| 96 px and up | Primary room | Bold mark |

- Lockups: regular 336 px wide and up; Bold horizontal 240 px and up, Bold
  small 160–239 px, Bold stacked 160 px and up.
- Use **Bold** for one-ink work beside the wordmark and for capture watermarks;
  it matches the lettering's weight. Bold doesn't replace the colour mark or
  the favicon.
- The favicon keeps the H in all three ICO frames (tab context); app icons
  follow the size rule above.

## Colours

| Role | On navy `#0f1a27` | On paper `#f3f7f3` |
|---|---|---|
| Architecture | `#5fa9a4` (6.43:1) | `#456c6c` (5.37:1) |
| Window / mint | `#8fe8bf` (12.08:1) | `#287567` (5.07:1) |
| Window / cyan | `#86d3dc` (10.33:1) | `#2b7182` (5.13:1) |
| Player + lettering | `#d4ffe6` (16.07:1) | `#0f1a27` (16.21:1) |

The light relatives also exceed 5:1 on white.

## Space, size and don'ts

- Clear space: 2x, where x is the player width (16 units): keep **32 source
  units** beyond the visible ink. Bold assets use the same 32 units.
- Minimums: primary 96 px, optical room 48 px, H 16 px, regular lockup 336 px wide.
- Use the paired palette (dark on navy, light on paper). Keep the single route
  opening. Don't shrink the full room to 16 px. Don't stretch, mirror or add
  glow. Don't re-centre the player.

### Capture watermark

Decorative only, never on the live HUD. Bold one-ink lockup, bottom-right,
inset by the clear space, 50–60% group opacity. Ink adapts to the area
underneath: white over dark areas, navy `#0f1a27` over bright ones (pale stone
defeats white even at 60%). Use opaque ink or a plate when the mark must carry
information.

## Regenerating exports

```sh
python3 brand/export.py          # rewrite PNG/ICO exports that changed, refresh SHA256SUMS
python3 brand/export.py --check  # fail if exports differ from the SVGs (pixel compare)
```

Needs `resvg` (exports were made with 0.48.1) and Pillow. Unchanged pixels keep
their committed bytes, so a rerun with no SVG change is a no-op. After editing
any file here, rerun the export so `SHA256SUMS` stays current.

## Vendoring

Copy files, don't fork them. In the receiving repo, keep a short note next to
the copies (for example `BRAND.md`) listing: this repo's commit, each copied
path, and its SHA-256 from `SHA256SUMS`. Inline SVG embedded in code must keep
the path data unchanged; note which master it came from.

## Licence and provenance

Original Hyprune artwork by Hyprune contributors, designed for this project
(Traverse 08 v2, 2026-10-09; Bold weight the same day). Licensed
**CC-BY-4.0** (<https://creativecommons.org/licenses/by/4.0/>), like the rest of
Hyprune's original art. Attribution: "Hyprune logo by Hyprune contributors,
CC-BY-4.0". The licence covers copyright in the artwork; it grants no trademark
rights, so don't use the mark in a way that suggests endorsement. SVGs contain
no rasters, fonts or external resources. The repository's MIT licence covers
`export.py`.
