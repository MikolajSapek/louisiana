"""Builds fonts/private/Indians.ttf after the "INDIANS" lettering of Ken Lum's "Mounties & Indians" (1989):
a shadow-only face (the Umbra principle, identified with WhatTheFont): each glyph is a Futura capital shifted by
0.08 em right / 0.03 em down, minus the letter itself (see board 2). Private, local posters only.

Usage: python tools/build_indians_font.py   (dev-only dependency: shapely; needs macOS Futura.ttc)
"""
from __future__ import annotations

import math
import os
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.basePen import BasePen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTCollection
from shapely import affinity
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

SOURCE = None  # chosen from FACE below
FACE = os.environ.get("INDIANS_FACE", "Futura Medium")
SOURCE = "/System/Library/Fonts/Supplemental/" + ("Futura.ttc" if FACE.startswith("Futura") else "GillSans.ttc")
SHADOW = tuple(float(v) for v in os.environ.get("INDIANS_SHADOW", "0.08,-0.03").split(","))  # extrusion (dx, dy), fraction of em
OUT = Path(__file__).resolve().parent.parent / "fonts" / "private" / os.environ.get("INDIANS_OUT", "Indians.ttf")
CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,-–:/&'’ĄĆĘŁŃÓŚŹŻ"
ANGLES = [32, -38, 41, -30, 36, -42, 28, -34]  # cut directions vary letter to letter, like hand cuts
GAP = 0.035     # slit width, fraction of em
SHIFT = 0.045   # how far the upper piece slides along the cut, fraction of em


class FlatPen(BasePen):
    """Collects glyph contours as flattened point lists."""

    def __init__(self, glyphset, steps=12):
        super().__init__(glyphset)
        self.contours, self.cur, self.steps = [], [], steps

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for k in range(1, self.steps + 1):
            t = k / self.steps
            a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
            self.cur.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for k in range(1, self.steps + 1):
            t = k / self.steps
            self.cur.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0],
                             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]))

    def _closePath(self):
        if len(self.cur) > 2:
            self.contours.append(self.cur)
        self.cur = []

    _endPath = _closePath


def glyph_shape(font, name):
    pen = FlatPen(font.getGlyphSet())
    font.getGlyphSet()[name].draw(pen)
    shape = Polygon()
    for contour in pen.contours:
        shape = shape.symmetric_difference(Polygon(contour).buffer(0))  # even-odd: holes cut out
    return shape


def cut(shape, angle_deg, em):
    """Slice along a diagonal through the glyph centre; slide the upper piece along the cut."""
    if shape.is_empty:
        return shape
    cx, cy = shape.centroid.x, shape.centroid.y
    big = em * 4
    upper = Polygon([(-big, GAP * em / 2), (big, GAP * em / 2), (big, big), (-big, big)])
    lower = Polygon([(-big, -GAP * em / 2), (big, -GAP * em / 2), (big, -big), (-big, -big)])
    upper = affinity.translate(affinity.rotate(upper, angle_deg, origin=(0, 0)), cx, cy)
    lower = affinity.translate(affinity.rotate(lower, angle_deg, origin=(0, 0)), cx, cy)
    a = math.radians(angle_deg)
    top = affinity.translate(shape.intersection(upper), SHIFT * em * math.cos(a), SHIFT * em * math.sin(a))
    return top.union(shape.intersection(lower)).buffer(0)


def shadow(shape, em):
    """Umbra principle (board 2): a copy shifted by SHADOW minus the letter; only the shadow is drawn.
    The 21-degree vector keeps diagonals of N, M, W from vanishing (a 45-degree one would be parallel to them)."""
    if shape.is_empty:
        return shape
    moved = affinity.translate(shape, SHADOW[0] * em, SHADOW[1] * em)
    return moved.difference(shape.buffer(1)).buffer(-1).buffer(1)


def draw(shape):
    pen = TTGlyphPen(None)
    for g in getattr(shape, "geoms", [shape]):
        if g.is_empty or g.area < 1 or g.geom_type != "Polygon":
            continue
        g = orient(g.simplify(0.8), sign=-1.0)
        for ring in [g.exterior, *g.interiors]:
            pts = [(round(x), round(y)) for x, y in ring.coords[:-1]]
            pen.moveTo(pts[0])
            for p in pts[1:]:
                pen.lineTo(p)
            pen.closePath()
    return pen.glyph()


def build():
    src = next(f for f in TTCollection(SOURCE).fonts if f["name"].getDebugName(4) == FACE)
    em = src["head"].unitsPerEm
    cmap_src, hmtx = src.getBestCmap(), src["hmtx"]
    glyphs, metrics, cmap = {}, {}, {ord(" "): "space"}
    for i, ch in enumerate(CHARS):
        name = cmap_src.get(ord(ch))
        if name is None:
            continue
        shape = shadow(glyph_shape(src, name), em)
        gname = f"g{ord(ch):04X}"
        glyphs[gname] = draw(shape)
        metrics[gname] = (hmtx[name][0], int(shape.bounds[0]) if not shape.is_empty else 0)
        cmap[ord(ch)] = gname
        if ch.lower() != ch:
            cmap[ord(ch.lower())] = gname  # caps-only, like the sign
    order = [".notdef", "space"] + list(glyphs)
    glyphs |= {".notdef": TTGlyphPen(None).glyph(), "space": TTGlyphPen(None).glyph()}
    metrics |= {".notdef": (em // 2, 0), "space": (hmtx[cmap_src[ord(" ")]][0], 0)}
    fb = FontBuilder(em, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    hhea = src["hhea"]
    fb.setupHorizontalHeader(ascent=hhea.ascent, descent=hhea.descent)
    fb.setupNameTable({"familyName": "Indians", "styleName": "Regular"})
    os2 = src["OS/2"]
    fb.setupOS2(sTypoAscender=os2.sTypoAscender, sTypoDescender=os2.sTypoDescender,
                usWinAscent=os2.usWinAscent, usWinDescent=os2.usWinDescent)
    fb.setupPost()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fb.save(str(OUT))
    print(f"wrote {OUT} with {len(order) - 2} glyphs")


if __name__ == "__main__":
    build()
