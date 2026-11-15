"""Builds fonts/private/NorthRailwayPL.ttf: the North Railway demo plus the glyphs it lacks (digits, Ł/ł, – - , .).

Digits come from the Mounties builder's shapes, scaled anisotropically so verticals end up 80 units and horizontals
120 units like North Railway's own letters. Private, local posters only (demo licence: private use).
Usage: python tools/build_northrailway_pl.py   (dev-only dependency: shapely)
"""
from __future__ import annotations

import sys
from pathlib import Path

from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from shapely import affinity
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
PRIVATE = HERE.parent / "fonts" / "private"
SRC, OUT = PRIVATE / "NorthRailway-DEMO.ttf", PRIVATE / "NorthRailwayPL.ttf"
NR_CAP, NR_STEM, NR_BAR = 800, 80, 120   # measured from North Railway's I, E and O
DIGIT_WIDTH = 360                        # like North Railway's O
SIDE = 25

sys.path.insert(0, str(HERE))
import build_indians_font as flat  # noqa: E402  (glyph outlines -> shapely)
import build_mounties_font as m    # noqa: E402  (digit shapes)

SX = DIGIT_WIDTH / 550                   # Mounties digits are ~550 wide, CAP 700
SY = NR_CAP / m.CAP
m.S, m.T = NR_STEM / SX, NR_BAR / SY     # pre-compensate so strokes land on NR weights after scaling


def draw(shape):
    pen = TTGlyphPen(None)
    for g in getattr(shape, "geoms", [shape]):
        if g.is_empty or g.area < 1 or g.geom_type != "Polygon":
            continue
        g = orient(g.simplify(0.6), sign=-1.0)
        for ring in [g.exterior, *g.interiors]:
            pts = [(round(x), round(y)) for x, y in ring.coords[:-1]]
            pen.moveTo(pts[0])
            for p in pts[1:]:
                pen.lineTo(p)
            pen.closePath()
    return pen.glyph()


def fit(shape):
    """Scale a Mounties digit into North Railway proportions and place it at the side bearing."""
    s = affinity.scale(shape, SX, SY, origin=(0, 0))
    return affinity.translate(s, SIDE - s.bounds[0], 0)


def slash(stem_x0, y_mid):
    """Diagonal bar across an L stem, for Ł/ł."""
    return Polygon([(stem_x0 - 30, y_mid - 95), (stem_x0 - 30, y_mid - 25), (stem_x0 + NR_STEM + 80, y_mid + 95),
                    (stem_x0 + NR_STEM + 80, y_mid + 25)])


def build():
    font = TTFont(str(SRC))
    cmap = font.getBestCmap()
    new = {}
    for ch, fn in zip("0123456789", [m.g_0, m.g_1, m.g_2, m.g_3, m.g_4, m.g_5, m.g_6, m.g_7, m.g_8, m.g_9]):
        shape = fit(fn()[0])
        new[ch] = (shape, int(shape.bounds[2] + SIDE))
    new["–"] = (box(SIDE, 300, SIDE + 300, 300 + NR_BAR * 0.8), 350)
    new["-"] = (box(SIDE, 300, SIDE + 180, 300 + NR_BAR * 0.8), 230)
    new["."] = (box(SIDE, 0, SIDE + 110, 110), 160)
    new[","] = (unary_union([box(SIDE, 20, SIDE + 110, 130), Polygon([(SIDE + 110, 40), (SIDE + 110, -110), (SIDE, -110)])]), 160)
    for upper, lower in (("Ł", "L"), ("ł", "l")):
        base = flat.glyph_shape(font, cmap[ord(lower if upper == "Ł" else "l")])
        height = base.bounds[3]
        new[upper] = (unary_union([base, slash(SIDE, height * 0.48)]), font["hmtx"][cmap[ord(lower if upper == "Ł" else "l")]][0])
    glyf, hmtx = font["glyf"], font["hmtx"]
    order = font.getGlyphOrder()
    for ch, (shape, adv) in new.items():
        name = f"uni{ord(ch):04X}"
        if name not in order:
            order.append(name)
        glyf[name] = draw(shape)
        hmtx[name] = (adv, int(shape.bounds[0]))
        for table in font["cmap"].tables:
            if table.isUnicode():
                table.cmap[ord(ch)] = name
    font.setGlyphOrder(order)
    font["maxp"].numGlyphs = len(order)
    for rec in font["name"].names:
        if rec.nameID in (1, 3, 4, 6, 16):
            rec.string = {1: "North Railway PL", 3: "NorthRailwayPL", 4: "North Railway PL", 6: "NorthRailwayPL",
                          16: "North Railway PL"}[rec.nameID]
    font.save(str(OUT))
    print(f"wrote {OUT} (+{len(new)} glyphs)")


if __name__ == "__main__":
    build()
