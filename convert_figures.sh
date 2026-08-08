#!/usr/bin/env bash
# Convert real-world-scale SVG figures (e.g. Inkscape drawings made to actual physical
# dimensions, like the lab floor plan) into print-sized PDFs for MSc_thesis/5-Figures/.
#
# Why this exists (two fixes, both automatic):
# 1. rsvg-convert preserves an SVG's declared physical page size by default. A floor plan
#    drawn at 1:1 scale (e.g. width="1050cm") converts to a PDF page 1050cm wide, which
#    exceeds pdfTeX's ~575cm hard dimension limit and fails to compile. This script scales
#    each SVG down so its longer side is at most MAX_CM, computed automatically from the
#    SVG's own declared size -- so it keeps working if you resize the drawing later.
# 2. Inkscape's stock hatch/pattern fills generate an empty <pattern> that links to its real
#    content via xlink:href, which librsvg doesn't reliably resolve -- hatching silently
#    renders as nothing. flatten_svg_patterns.py rewrites those into self-contained patterns
#    first, so this only needs fixing here, not by hand in Inkscape every time.
#
# Usage:
#   ./convert_figures.sh
# Re-run any time a source SVG changes. To add a new figure, add a line to the FIGURES
# mapping below.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIGURES_DIR="$REPO_ROOT/MSc_thesis/5-Figures"
MAX_CM=25   # cap the longer side of the output PDF page at this many cm

if ! command -v rsvg-convert >/dev/null 2>&1; then
    echo "!! rsvg-convert not found. Install it (e.g. 'sudo pacman -S librsvg' / 'sudo apt install librsvg2-bin') and re-run." >&2
    exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

# source SVG (relative to repo root) -> output PDF filename (in MSc_thesis/5-Figures/)
declare -A FIGURES=(
    ["lab floor plan.svg"]="Lab_Floor_Plan.pdf"
    ["heights.svg"]="Test_Location_Heights.pdf"
)

for rel_src in "${!FIGURES[@]}"; do
    src="$REPO_ROOT/$rel_src"
    out="$FIGURES_DIR/${FIGURES[$rel_src]}"

    if [[ ! -f "$src" ]]; then
        echo "!! source not found, skipping: $rel_src" >&2
        continue
    fi

    flat="$WORKDIR/$(basename "$rel_src").flat.svg"
    python3 "$REPO_ROOT/flatten_svg_patterns.py" "$src" "$flat"

    w_cm=$(grep -m1 -oE 'width="[0-9.]+cm"' "$flat" | grep -oE '[0-9.]+' || true)
    h_cm=$(grep -m1 -oE 'height="[0-9.]+cm"' "$flat" | grep -oE '[0-9.]+' || true)

    if [[ -z "$w_cm" || -z "$h_cm" ]]; then
        echo "!! could not find cm-unit width/height in $rel_src -- converting at 1:1 (may fail if the page is oversized)" >&2
        rsvg-convert -f pdf -o "$out" "$flat"
        echo "Converted (1:1): $rel_src -> ${FIGURES[$rel_src]}"
        continue
    fi

    zoom=$(python3 -c "print(min(1.0, $MAX_CM / max($w_cm, $h_cm)))")
    rsvg-convert -z "$zoom" -f pdf -o "$out" "$flat"
    echo "Converted: $rel_src (${w_cm}x${h_cm} cm) -> ${FIGURES[$rel_src]} (zoom=$zoom)"
done
