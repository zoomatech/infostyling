"""Tract ink carrier (port of core/tract.js): black ink on white paper, one diagonal stroke per cell as in
Glyph hatch; dark cells become solid ink with a white scratch on the opposite diagonal."""
import math
from .jsm import jround, clamp
from .layout import tile_period, cell_bit
from .glyph import decode_glyphs

PAPER = 255
INK = 0
SQRT2 = math.sqrt(2)


def render_tract(src, w, h, n, bits, p, progress=None):
    c = max(6, jround(p.get('tractCell') or 10))
    period = tile_period(len(bits))
    out = bytearray(len(src))
    half = c / 2; inset = .12 * c
    tn = p.get('tractNight'); night = (24 if tn is None else tn) / 100
    tl = p.get('tractLine'); line_thr = 118 if tl is None else tl
    scratch = max(.75, .11 * c)
    seed = p.get('seed')
    m = min(3, n)
    cy = 0
    while cy * c < h:
        cx = 0
        while cx * c < w:
            x0 = cx * c; y0 = cy * c; x1 = min(w, x0 + c); y1 = min(h, y0 + c)
            s = 0; k = 0
            for y in range(y0, y1):
                i = (y * w + x0) * n
                for x in range(x0, x1):
                    s += .2126 * src[i] + .7152 * src[i + 1] + .0722 * src[i + 2]; k += 1
                    i += n
            L = s / k / 255
            bit = cell_bit(cx, cy, bits, period, seed)
            dark = L < night
            diag = (1 - bit) if dark else bit
            t = scratch if dark else c * (.04 + .10 * (1 - L))
            ln = 1 if dark else .5 + .5 * (1 - L)
            lim = (half * SQRT2 - inset) * ln
            for y in range(y0, y1):
                v = y - y0 + .5 - half
                i = (y * w + x0) * n
                for x in range(x0, x1):
                    u = x - x0 + .5 - half
                    if diag:
                        along = (u - v) / SQRT2; across = (u + v) / SQRT2
                    else:
                        along = (u + v) / SQRT2; across = (u - v) / SQRT2
                    d = max(abs(across) - t, abs(along) - lim)
                    a = clamp(.5 - d, 0, 1)
                    g = INK * (1 - a) + PAPER * a if dark else PAPER * (1 - a) + INK * a
                    if not dark and line_thr > 0:
                        l = .2126 * src[i] + .7152 * src[i + 1] + .0722 * src[i + 2]
                        g = min(g, clamp((l - line_thr + 24) / 48, 0, 1) * 255)
                    g = jround(g)
                    for q in range(m):
                        out[i + q] = g
                    if n > 3:
                        out[i + 3] = src[i + 3]
                    i += n
            cx += 1
        cy += 1
        if progress:
            progress(min(1, cy * c / h))
    return {'pixels': out, 'cell': c, 'period': period}


def decode_tract(src, w, h, n, o=None):
    d = decode_glyphs(src, w, h, n, o)
    if d:
        d['carrier'] = 'tract'
    return d
