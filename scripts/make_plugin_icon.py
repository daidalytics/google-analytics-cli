"""Render the Claude Code plugin icon (.claude-plugin/icon.png).

A white prompt chevron and a rising amber trend line on navy, in the colors of
the CLI's OAuth success page. Dev-only; Pillow is not a project dependency:

    uv run --with pillow python scripts/make_plugin_icon.py

The developer portal takes this file as the plugin's listing icon only the first
time the plugin is saved or submitted there; changing it later has no effect.
"""

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024  # output px per side (portal accepts 512-2048)
SS = 4  # supersampling factor, for clean anti-aliased edges
NAVY, WHITE, AMBER = "#1a1a2e", "#ffffff", "#dd973a"
OUTPUT = Path(__file__).resolve().parent.parent / ".claude-plugin" / "icon.png"


def _dot(draw: ImageDraw.ImageDraw, x: float, y: float, r: float, color: str) -> None:
    draw.ellipse(((x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS), fill=color)


def _stroke(draw: ImageDraw.ImageDraw, pts: list, width: float, color: str) -> None:
    """Polyline drawn as a union of capsules: exact round caps and joins.

    Pillow's own wide lines leave notches at joints, which show at icon sizes.
    """
    r = width / 2
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        length = math.hypot(x2 - x1, y2 - y1)
        nx, ny = -(y2 - y1) / length * r, (x2 - x1) / length * r
        quad = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
        draw.polygon([(x * SS, y * SS) for x, y in quad], fill=color)
    for x, y in pts:
        _dot(draw, x, y, r, color)


def render() -> Image.Image:
    # Coordinates are in 1024-px space; content stays in the central safe area
    # so a rounded-corner mask applied by the portal can't clip it.
    img = Image.new("RGB", (SIZE * SS, SIZE * SS), NAVY)
    draw = ImageDraw.Draw(img)
    _stroke(draw, [(258, 330), (440, 512), (258, 694)], 84, WHITE)  # prompt chevron
    _stroke(draw, [(506, 694), (612, 574), (694, 634), (786, 418)], 60, AMBER)  # trend
    _dot(draw, 786, 418, 56, AMBER)  # trend endpoint
    return img.resize((SIZE, SIZE), Image.LANCZOS)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT
    render().save(out, "PNG", optimize=True)
    print(f"Wrote {out}")
