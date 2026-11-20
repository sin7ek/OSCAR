# OSCAR GUI branding

The GUI branding is presentation-only. It does not change the Go!, Review, Collection, or Settings workflows.

## Artwork files

Put the operator-approved artwork in `src/oscar/assets/`:

- `OSCAR-header.png`: the original wide logo, transparent background (no crop, stretching, or redrawing).
- `favicon-16.png` and `favicon-32.png`: browser favicons derived from the supplied circular artwork.
- `apple-touch-icon.png`: 180×180 PNG for mobile bookmarks.

The original supplied `OSCAR-favicon.png` should be retained as the master in the separate source-artwork package.

The assets are intentionally optional at application startup: a missing header image falls back to text and missing icons do not affect navigation or APIs. Only allowlisted local PNG names may be served by `/brand/{filename}`. The package-data configuration includes these PNGs in the installed Docker application.

## Review checklist

1. Confirm original header lettering and portrait are unchanged.
2. Confirm no distortion or horizontal overflow on desktop and narrow mobile viewports.
3. Confirm the browser tab icon displays clearly at 16×16 and 32×32.
4. Confirm all four tabs and the normal Go! workflow still function.
5. Run `pytest` and Docker preview build; conduct an explicit Unraid GUI smoke test before merging.
6. Preserve archive data, extraction logs, metadata, and existing container configuration.

**Important:** A PR containing code but not the approved binary artwork is incomplete and should stay a draft until the images are committed and checked.
