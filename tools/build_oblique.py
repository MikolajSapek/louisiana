"""Builds slanted (oblique) copies of the private Indians fonts: every outline skewed by SLANT degrees.
Private, local posters only. Usage: python tools/build_oblique.py"""
from __future__ import annotations

import math
from pathlib import Path

from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

PRIVATE = Path(__file__).resolve().parent.parent / "fonts" / "private"
SLANT = -12  # degrees; negative leans left (backslant, the owner chose this)
SOURCES = ["Indians", "IndiansBold", "IndiansBoldOutline"]


def oblique(name: str) -> None:
    font = TTFont(str(PRIVATE / f"{name}.ttf"))
    gs, glyf = font.getGlyphSet(), font["glyf"]
    skew = (1, 0, math.tan(math.radians(SLANT)), 1, 0, 0)
    for gname in font.getGlyphOrder():
        pen = TTGlyphPen(gs)
        gs[gname].draw(TransformPen(pen, skew))
        glyf[gname] = pen.glyph()
    font["post"].italicAngle = -SLANT
    font.save(str(PRIVATE / f"{name}Italic.ttf"))
    print("wrote", PRIVATE / f"{name}Italic.ttf")


if __name__ == "__main__":
    for source in SOURCES:
        oblique(source)
