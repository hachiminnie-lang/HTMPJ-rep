#!/usr/bin/env python3
"""Inline the floor-plan SVG into the page template to produce index.html.

The standalone SVG carries its own `:root` theme block so it renders correctly
when opened on its own. That block is stripped on inlining, because inside the
HTML document `:root` would target <html> and override the page's own tokens.
"""

import re
from pathlib import Path

HERE = Path(__file__).parent
SVG = HERE / "1ldk-industrial.svg"
TEMPLATE = HERE / "page.template.html"
OUT = HERE / "index.html"

MARKER = "<!--PLAN_SVG-->"


def main() -> None:
    svg = SVG.read_text(encoding="utf-8")

    # Drop the XML prolog / standalone theme block; keep everything else intact.
    svg = re.sub(r"<\?xml.*?\?>\s*", "", svg, flags=re.S)
    svg, n = re.subn(
        r'\s*<style id="plan-standalone-theme">.*?</style>', "", svg, flags=re.S
    )
    if n != 1:
        raise SystemExit(f"expected exactly 1 standalone theme block, found {n}")

    # The page sizes the drawing with CSS; fixed px attributes would fight it.
    svg = svg.replace(' width="1160" height="1747"', "", 1)

    template = TEMPLATE.read_text(encoding="utf-8")
    if MARKER not in template:
        raise SystemExit(f"marker {MARKER} missing from {TEMPLATE.name}")

    OUT.write_text(template.replace(MARKER, svg.strip()), encoding="utf-8")
    print(f"wrote {OUT.relative_to(HERE.parent)} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
