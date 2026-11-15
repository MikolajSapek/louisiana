"""Builds fonts/Mounties.ttf: a caps-only slab with flared serifs, drawn after the "MOUNTIES" sign lettering.

Every glyph is composed from geometric parts (stems, bars, rings, flared serifs) with shapely and written as
TrueType outlines with fontTools. Lowercase maps to the capitals. Usage: python tools/build_mounties_font.py
Dev-only dependency: shapely.
"""
from __future__ import annotations

from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

OUT = Path(__file__).resolve().parent.parent / "fonts" / "Mounties.ttf"
UPM, CAP = 1000, 700
S = 172    # stem width
T = 138    # horizontal stroke
SH = 72    # serif height
SO = 70    # serif overhang past the stem
SPUR = 70  # arm-end spur length
SIDE = 24  # side bearing


# ---------- primitives ----------
def rect(x0, y0, x1, y1):
    return box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def poly(*pts):
    return Polygon(pts)


def foot(cx, w=S, y=0, up=True, left=True, right=True):
    """Flared slab serif under (or over) a stem of width w centred at cx: wider at the outer edge."""
    d = 1 if up else -1
    lo, hi = (SO if left else 0), (SO if right else 0)
    return poly(
        (cx - w / 2 - lo, y), (cx + w / 2 + hi, y),
        (cx + w / 2 + hi * 0.55, y + d * SH), (cx - w / 2 - lo * 0.55, y + d * SH),
    )


def head(cx, w=S, left=True, right=True):
    return foot(cx, w, CAP, up=False, left=left, right=right)


def stem(cx, y0=0, y1=CAP, w=S):
    return rect(cx - w / 2, y0, cx + w / 2, y1)


def spur_down(x_end, y_top, w=T):
    """Vertical flared spur hanging from the end of a top arm (E, F, T, Z)."""
    return poly((x_end - w * 0.9, y_top), (x_end, y_top), (x_end, y_top - T - SPUR), (x_end - w * 0.55, y_top - T - SPUR * 0.6))


def spur_up(x_end, y_bot, w=T):
    return poly((x_end - w * 0.9, y_bot), (x_end, y_bot), (x_end, y_bot + T + SPUR), (x_end - w * 0.55, y_bot + T + SPUR * 0.6))


def ring(cx, cy, rx, ry, tx=S, ty=T):
    outer = affinity.scale(Point(0, 0).buffer(1, 64), rx, ry).buffer(0)
    inner = affinity.scale(Point(0, 0).buffer(1, 64), rx - tx, ry - ty)
    return affinity.translate(outer.difference(inner), cx, cy)


def bowl(x_stem, y0, y1, depth):
    """D-shaped bowl attached to the right of a stem between y0 and y1."""
    ry = (y1 - y0) / 2
    r = ring(x_stem, y0 + ry, depth, ry, tx=S * 0.95, ty=T)
    return r.intersection(rect(x_stem, y0 - 1, x_stem + depth + 1, y1 + 1))


def diag(x0, y0, x1, y1, w):
    """Straight stroke of horizontal width w from (x0,y0) to (x1,y1)."""
    return poly((x0 - w / 2, y0), (x0 + w / 2, y0), (x1 + w / 2, y1), (x1 - w / 2, y1))


def bez(*pts, n=40):
    """Cubic Bezier chain through control points p0,c1,c2,p1,c1,c2,p2,... sampled to a polyline."""
    out = []
    for i in range(0, len(pts) - 1, 3):
        p0, c1, c2, p1 = pts[i:i + 4]
        for k in range(n + 1):
            t = k / n
            a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
            out.append((a * p0[0] + b * c1[0] + c * c2[0] + d * p1[0], a * p0[1] + b * c1[1] + c * c2[1] + d * p1[1]))
    return out


def stroke(points, w=None):
    """Monoline stroke along a centreline, flat ends (like a sign-painter's brush cut square)."""
    return LineString(points).buffer((w or S * 0.92) / 2, cap_style=2, join_style=1)


def u(*parts):
    return unary_union([p for p in parts if p is not None]).buffer(0)


# ---------- glyphs: (shape, advance width) ----------
def g_I():
    return u(stem(130), foot(130), head(130)), 260


def g_H():
    return u(stem(130), stem(500), rect(130, 300, 500, 300 + T), foot(130), foot(500), head(130), head(500)), 630


def g_E():
    x = 125
    return u(stem(x), rect(x, 0, 470, T), rect(x, CAP - T, 450, CAP), rect(x, 300, 400, 300 + T),
             spur_up(470, 0), spur_down(450, CAP),
             foot(x, right=False), head(x, right=False)), 520


def g_F():
    x = 125
    return u(stem(x), rect(x, CAP - T, 450, CAP), rect(x, 290, 390, 290 + T), spur_down(450, CAP),
             foot(x), head(x, right=False)), 490


def g_L():
    x = 125
    return u(stem(x), rect(x, 0, 460, T), spur_up(460, 0), foot(x, right=False), head(x)), 500


def g_T():
    return u(stem(280), rect(40, CAP - T, 520, CAP), spur_down(120, CAP), affinity.scale(spur_down(120, CAP), -1, 1, origin=(280, 0)),
             foot(280)), 560


def g_O():
    return ring(320, CAP / 2, 285, CAP / 2), 640


def g_C():
    r = ring(310, CAP / 2, 270, CAP / 2).difference(poly((310, CAP / 2), (700, CAP + 60), (700, -60)))
    return u(r, spur_down(530, CAP - 70, w=T * 0.9), spur_up(530, 70, w=T * 0.9).intersection(rect(0, 0, 700, CAP))), 590


def g_G():
    c, w = g_C()
    return u(c, rect(330, 250, 560, 250 + T * 0.9), stem(505, 40, 330, w=S * 0.9)), 600


def g_D():
    x = 125
    return u(stem(x), rect(x, 0, 300, T), rect(x, CAP - T, 300, CAP), bowl(300, 0, CAP, 280),
             foot(x, right=False), head(x, right=False)), 630


def g_B():
    x = 125
    return u(stem(x), rect(x, 0, 300, T), rect(x, CAP - T, 280, CAP), rect(x, 330, 300, 330 + T),
             bowl(280, 330, CAP, 220), bowl(300, 0, 330 + T, 250), foot(x, right=False), head(x, right=False)), 590


def g_P():
    x = 125
    return u(stem(x), rect(x, CAP - T, 290, CAP), rect(x, 300, 290, 300 + T), bowl(290, 300, CAP, 250),
             foot(x), head(x, right=False)), 580


def g_R():
    p, _ = g_P()
    return u(p, diag(330, 330, 500, 0, S * 1.05), foot(500, w=S * 1.05, left=False)), 600


def g_U():
    bottom = ring(330, 260, 250, 260).intersection(rect(0, -1, 700, 260))
    return u(stem(130, 260, CAP), stem(530, 260, CAP, w=S * 0.8), bottom, head(130), head(530, w=S * 0.8)), 660


def g_N():
    return u(stem(110, 0, CAP, w=S * 0.62), stem(510, 0, CAP, w=S * 0.62), diag(140, CAP, 480, 0, S * 1.05),
             foot(110, w=S * 0.62), head(510, w=S * 0.62), head(110, w=S * 0.62, right=False)), 620


def g_M():
    return u(stem(115, 0, CAP, w=S * 0.7), stem(655, 0, CAP, w=S * 0.95), diag(150, CAP, 385, 120, S * 0.95),
             diag(620, CAP, 385, 120, S * 0.75), foot(115, w=S * 0.7), foot(655, w=S * 0.95),
             head(115, w=S * 0.7, right=False), head(655, w=S * 0.95, left=False)), 770


def g_A():
    return u(diag(300, CAP, 95, 0, S * 1.05), diag(300, CAP, 505, 0, S * 0.75), rect(170, 170, 430, 170 + T * 0.9),
             rect(225, CAP - 40, 365, CAP), foot(95, w=S * 1.05), foot(505, w=S * 0.75)).intersection(rect(-60, 0, 700, CAP)), 600


def g_V():
    return u(diag(95, CAP, 300, 0, S * 1.05), diag(505, CAP, 300, 0, S * 0.75), head(95, w=S * 1.05), head(505, w=S * 0.75)).intersection(rect(-60, 0, 700, CAP)), 600


def g_W():
    return u(diag(90, CAP, 230, 0, S), diag(390, CAP, 230, 0, S * 0.7), diag(390, CAP, 550, 0, S),
             diag(690, CAP, 550, 0, S * 0.7), head(90, w=S), head(690, w=S * 0.7)).intersection(rect(-60, 0, 800, CAP)), 780


def g_K():
    x = 125
    return u(stem(x), diag(530, CAP, x + 40, 280, S * 0.75), diag(x + 150, 360, 530, 0, S * 1.05),
             foot(x), head(x), foot(530, w=S * 1.05, left=False), head(500, w=S * 0.75, left=False)), 600


def g_X():
    return u(diag(95, CAP, 505, 0, S * 1.05), diag(505, CAP, 95, 0, S * 0.75), foot(95, w=S * 0.75), foot(505, w=S * 1.05),
             head(95, w=S * 1.05), head(505, w=S * 0.75)), 600


def g_Y():
    return u(diag(95, CAP, 300, 330, S * 1.05), diag(505, CAP, 300, 330, S * 0.75), stem(300, 0, 340),
             foot(300), head(95, w=S * 1.05), head(505, w=S * 0.75)), 600


def g_Z():
    return u(rect(60, 0, 500, T), rect(80, CAP - T, 480, CAP), diag(460, CAP - T, 100, T, S * 1.1),
             spur_down(80 + T * 0.9, CAP), spur_up(500, 0)).intersection(rect(40, 0, 520, CAP)), 560


def g_J():
    hook = ring(220, 230, 190, 230).intersection(rect(0, -1, 600, 230))
    return u(stem(330, 230, CAP), hook, head(330), stem(80, 150, 260, w=S * 0.8)), 470


def g_Q():
    o, w = g_O()
    return u(o, diag(330, 80, 520, -110, S * 0.9)), w


def g_S():
    w = S * 0.9
    spine = bez((455, 600), (380, 690), (150, 690), (135, 545), (120, 400), (470, 390), (470, 205),
                (470, 30), (160, 10), (90, 120))
    return u(stroke(spine, w), spur_down(500, CAP - 40, w=T * 0.8).intersection(rect(400, 350, 560, CAP)),
             spur_up(60 + T * 0.8, 40, w=T * 0.8).intersection(rect(0, 0, 160, 350))), 570


# digits
def g_0():
    return ring(275, CAP / 2, 225, CAP / 2), 550


def g_1():
    return u(stem(270), poly((200, CAP), (270 + S / 2, CAP), (270 - S / 2, CAP - 160), (110, CAP - 210)), foot(270)), 540


def g_2():
    w = S * 0.9
    curve = bez((110, 545), (130, 700), (440, 720), (440, 520), (440, 380), (200, 300), (95, 60))
    return u(stroke(curve, w), rect(70, 0, 490, T), spur_up(490, 0)), 550


def g_3():
    w = S * 0.85
    top = bez((95, 560), (140, 710), (430, 710), (420, 540), (410, 420), (300, 390), (215, 390))
    bot = bez((215, 390), (330, 390), (460, 360), (455, 205), (450, 20), (150, 0), (85, 140))
    return u(stroke(top, w), stroke(bot, w)), 545


def g_4():
    return u(stem(390), diag(390, CAP, 70, 200, S * 0.8), rect(60, 160, 520, 160 + T), foot(390)), 560


def g_5():
    w = S * 0.9
    bowl_ = bez((150, 400), (230, 450), (470, 450), (465, 220), (460, 10), (160, 0), (90, 130))
    return u(stroke(bowl_, w), rect(110, CAP - T, 480, CAP), stem(150, 360, CAP, w=w), spur_down(480, CAP)), 545


def g_6():
    w = S * 0.9
    arc = bez((450, 640), (380, 720), (110, 700), (100, 360), (95, 120), (190, 20), (300, 20),
              (440, 20), (480, 150), (470, 240), (460, 380), (330, 420), (240, 400), (170, 385), (120, 330), (110, 260))
    return u(stroke(arc, w)), 560


def g_7():
    return u(rect(70, CAP - T, 500, CAP), diag(470, CAP - T, 220, 0, S), spur_down(70 + T * 0.9, CAP)), 540


def g_8():
    return u(ring(280, 520, 200, 180, tx=S * 0.85), ring(280, 190, 235, 190)), 560


def g_9():
    rot = affinity.rotate(g_6()[0], 180, origin=(280, CAP / 2))
    return rot, 560


# punctuation
def g_period():
    return rect(60, 0, 60 + S, S), 270


def g_comma():
    return u(rect(60, 20, 60 + S, S + 20), poly((60 + S, 40), (60 + S, -110), (60, -110))), 270


def g_hyphen():
    return rect(50, 260, 330, 260 + T), 380


def g_endash():
    return rect(40, 260, 520, 260 + T), 560


def g_quote():
    return rect(60, CAP - 220, 60 + S * 0.8, CAP), 240


def g_colon():
    return u(rect(60, 0, 60 + S, S), rect(60, 380, 60 + S, 380 + S)), 270


def g_slash():
    return diag(80, -40, 380, CAP + 40, S * 0.8), 460


def g_amp():
    w = S * 0.85
    path = bez((520, 0), (380, 160), (150, 420), (150, 560), (150, 680), (360, 690), (350, 560),
               (340, 450), (90, 380), (90, 200), (90, 40), (330, 0), (470, 260))
    return u(stroke(path, w), rect(400, 250, 590, 250 + T * 0.8), foot(560, w=S * 0.6, left=False)), 610


BASE = {
    "A": g_A, "B": g_B, "C": g_C, "D": g_D, "E": g_E, "F": g_F, "G": g_G, "H": g_H, "I": g_I, "J": g_J,
    "K": g_K, "L": g_L, "M": g_M, "N": g_N, "O": g_O, "P": g_P, "Q": g_Q, "R": g_R, "S": g_S, "T": g_T,
    "U": g_U, "V": g_V, "W": g_W, "X": g_X, "Y": g_Y, "Z": g_Z,
    "zero": g_0, "one": g_1, "two": g_2, "three": g_3, "four": g_4, "five": g_5, "six": g_6, "seven": g_7,
    "eight": g_8, "nine": g_9, "period": g_period, "comma": g_comma, "hyphen": g_hyphen, "endash": g_endash,
    "quotesingle": g_quote, "colon": g_colon, "slash": g_slash, "ampersand": g_amp,
}
CHARS = {c: c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"} | {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven",
    "8": "eight", "9": "nine", ".": "period", ",": "comma", "-": "hyphen", "–": "endash", "'": "quotesingle",
    "’": "quotesingle", ":": "colon", "/": "slash", "&": "ampersand",
}


# Polish letters: base + mark
def acute(cx):
    return poly((cx - 30, CAP + 40), (cx + 60, CAP + 40), (cx + 150, CAP + 170), (cx + 40, CAP + 170))


def dot(cx):
    return rect(cx - 65, CAP + 45, cx + 65, CAP + 165)


def ogonek(x):
    return u(ring(x - 40, -10, 90, 95, tx=60, ty=50).intersection(rect(-100, -200, x - 40, -10)), rect(x - 60, -40, x, 10))


def polish():
    out = {}
    for base, mark in {"O": "acute", "S": "acute", "C": "acute", "N": "acute", "Z": "acute", "Z_dot": "dot",
                       "A": "ogonek", "E": "ogonek"}.items():
        shape, w = BASE[base.split("_")[0]]()
        cx = w / 2
        extra = {"acute": acute(cx - 40), "dot": dot(cx), "ogonek": ogonek(w - 60)}[mark]
        out[base + "_" + mark if "_" not in base else base] = (u(shape, extra), w)
    lshape, lw = g_L()
    out["Lslash"] = (u(lshape, diag(60, 230, 330, 470, T * 0.85).intersection(rect(0, 200, 400, 520))), lw)
    return out


POLISH_CHARS = {"Ó": "O_acute", "Ś": "S_acute", "Ć": "C_acute", "Ń": "N_acute", "Ź": "Z_acute", "Ż": "Z_dot",
                "Ą": "A_ogonek", "Ę": "E_ogonek", "Ł": "Lslash"}


def draw(shape):
    pen = TTGlyphPen(None)
    geoms = getattr(shape, "geoms", [shape])
    for g in geoms:
        if g.is_empty or g.area < 1:
            continue
        g = orient(g.simplify(0.6), sign=-1.0)  # TrueType: outer contours clockwise
        for ring_ in [g.exterior, *g.interiors]:
            pts = [(round(x), round(y)) for x, y in ring_.coords[:-1]]
            pen.moveTo(pts[0])
            for p in pts[1:]:
                pen.lineTo(p)
            pen.closePath()
    return pen.glyph()


def build():
    glyphs = {name: fn() for name, fn in BASE.items()} | polish()
    order = [".notdef", "space"] + list(glyphs)
    outlines = {".notdef": TTGlyphPen(None).glyph(), "space": TTGlyphPen(None).glyph()}
    metrics = {".notdef": (500, 0), "space": (260, 0)}
    for name, (shape, width) in glyphs.items():
        shape = affinity.translate(shape, SIDE, 0)
        outlines[name] = draw(shape)
        metrics[name] = (int(width + 2 * SIDE), int(shape.bounds[0]) if not shape.is_empty else 0)
    cmap = {ord(" "): "space"}
    for ch, name in (CHARS | POLISH_CHARS).items():
        cmap[ord(ch)] = name
        if ch.lower() != ch:
            cmap[ord(ch.lower())] = name  # caps-only font: lowercase uses the capitals
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(outlines)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=900, descent=-220)
    fb.setupNameTable({"familyName": "Mounties", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=900, sTypoDescender=-220, usWinAscent=920, usWinDescent=240, sCapHeight=CAP, sxHeight=CAP)
    fb.setupPost()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fb.save(str(OUT))
    web_copy = OUT.parent.parent / "static" / "fonts" / OUT.name  # same file for the page's draggable labels
    web_copy.parent.mkdir(parents=True, exist_ok=True)
    web_copy.write_bytes(OUT.read_bytes())
    print(f"wrote {OUT} with {len(glyphs)} glyphs")


if __name__ == "__main__":
    build()
