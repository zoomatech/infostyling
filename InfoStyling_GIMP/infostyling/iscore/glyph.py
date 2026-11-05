"""Glyph hatch carrier, after Xerox DataGlyphs (port of core/glyph.js): one diagonal ink stroke per cell,
"/" is a 1 bit and "\\" is a 0 bit. Uses the ISB3 frame and tile layout, so decode_grid reads it."""
import math
from .jsm import jround, clamp
from .layout import tile_period, cell_bit
from .carrier import cluster_bits, decode_grid, f32

PAPER = (246, 241, 229)
SQRT2 = math.sqrt(2)


def cell_stats(src, w, h, n, x0, y0, c):
    r = g = b = 0; k = 0
    for y in range(y0, min(h, y0 + c)):
        i = (y * w + x0) * n
        for x in range(x0, min(w, x0 + c)):
            r += src[i]; g += src[i + 1]; b += src[i + 2]; k += 1
            i += n
    return (r / k, g / k, b / k) if k else (255, 255, 255)


def render_glyphs(src, w, h, n, bits, p, progress=None):
    c = max(6, jround(p.get('glyphCell') or 12))
    period = tile_period(len(bits))
    out = bytearray(len(src))
    inset = .14 * c; half = c / 2
    gw_ = p.get('glyphWeight')
    weight = clamp((60 if gw_ is None else gw_) / 100, 0, 1)
    seed = p.get('seed')
    lim = half * SQRT2 - inset
    m = min(3, n)
    cy = 0
    while cy * c < h:
        cx = 0
        while cx * c < w:
            x0 = cx * c; y0 = cy * c
            col = cell_stats(src, w, h, n, x0, y0, c)
            L = (.2126 * col[0] + .7152 * col[1] + .0722 * col[2]) / 255
            bit = cell_bit(cx, cy, bits, period, seed)
            t = c * (.055 + (.06 + .22 * weight) * (1 - L))
            ink = [v * .42 * (1 - .5 * L) for v in col]
            for y in range(y0, min(h, y0 + c)):
                v = y - y0 + .5 - half
                i = (y * w + x0) * n
                for x in range(x0, min(w, x0 + c)):
                    u = x - x0 + .5 - half
                    if bit:
                        along = (u - v) / SQRT2; across = (u + v) / SQRT2
                    else:
                        along = (u + v) / SQRT2; across = (u - v) / SQRT2
                    d = max(abs(across) - t, abs(along) - lim)
                    a = clamp(.5 - d, 0, 1)
                    for kk in range(m):
                        out[i + kk] = jround(PAPER[kk] * (1 - a) + ink[kk] * a)
                    if n > 3:
                        out[i + 3] = src[i + 3]
                    i += n
            cx += 1
        cy += 1
        if progress:
            progress(min(1, cy * c / h))
    return {'pixels': out, 'cell': c, 'period': period}


def lum_at(src, w, h, n, x, y):
    xi = clamp(jround(x), 0, w - 1); yi = clamp(jround(y), 0, h - 1)
    i = (yi * w + xi) * n
    return .2126 * src[i] + .7152 * src[i + 1] + .0722 * src[i + 2]


FS = (.22, .3, .38, .62, .7, .78)


def lean(src, w, h, n, c, x0, y0):
    s = b = 0
    for f in FS:
        s += lum_at(src, w, h, n, x0 + f * c - .5, y0 + (1 - f) * c - .5)
        b += lum_at(src, w, h, n, x0 + f * c - .5, y0 + f * c - .5)
    return (b - s) / 6


def score(src, w, h, n, c, ox, oy, kmax=1e9):
    cols = math.floor((w - ox) / c); rows = math.floor((h - oy) / c)
    if cols < 12 or rows < 12:
        return 0
    kx = min(cols, kmax); ky = min(rows, kmax)
    s = 0
    G = min(12, kx)
    for j in range(G):
        for i in range(G):
            cx = jround((i + .5) * kx / G - .5); cy = jround((j + .5) * ky / G - .5)
            s += abs(lean(src, w, h, n, c, ox + cx * c, oy + cy * c))
    return s / (G * G)


def grid(src, w, h, n, c, ox=0, oy=0):
    cols = math.floor((w - ox) / c); rows = math.floor((h - oy) / c)
    if cols < 12 or rows < 12:
        return None
    vals = [lean(src, w, h, n, c, ox + x * c, oy + y * c) for y in range(rows) for x in range(cols)]
    values = f32(vals)
    q = cluster_bits(values)
    q.update({'values': values, 'cols': cols, 'rows': rows, 'cell': c, 'ox': ox, 'oy': oy})
    return q


def _frange(a, b, st):
    v = a
    while v < b:
        yield v
        v += st


def best_offset(src, w, h, n, c, kmax, st):
    b = {'s': -1, 'x': 0, 'y': 0}
    y = 0
    while y < c - .01:
        x = 0
        while x < c - .01:
            v = score(src, w, h, n, c, x, y, kmax)
            if v > b['s']:
                b = {'s': v, 'x': x, 'y': y}
            x += st
        y += st
    return b


def nudge(src, w, h, n, q, kmax):
    b = dict(q); b['s'] = score(src, w, h, n, q['c'], q['x'], q['y'], kmax)
    dy = -1.5
    while dy <= 1.5:
        dx = -1.5
        while dx <= 1.5:
            x = q['x'] + dx; y = q['y'] + dy
            if not (x < 0 or y < 0):
                v = score(src, w, h, n, q['c'], x, y, kmax)
                if v > b['s']:
                    b = dict(q); b.update({'x': x, 'y': y, 's': v})
            dx += .5
        dy += .5
    return b


def refine(src, w, h, n, q, step, span, kmax):
    best = q
    f = -span
    while f <= span + 1e-9:
        t = q['c'] * (1 + f)
        v = score(src, w, h, n, t, q['x'], q['y'], kmax)
        if v > best['s'] or (best is q and f == -span):
            best = {'c': t, 's': v, 'x': q['x'], 'y': q['y']}
        f += step
    return best


def estimate_cells(src, w, h, n, o):
    lst = []
    c = o.get('minCell') or 3.6
    mx = o.get('maxCell') or 48
    while c <= mx:
        b = best_offset(src, w, h, n, c, 10, max(1, c / 6))
        d = {'c': c}; d.update(b)
        lst.append(d)
        c *= 1.006
    peaks = [q for i, q in enumerate(lst) if (i == 0 or q['s'] >= lst[i - 1]['s']) and (i == len(lst) - 1 or q['s'] >= lst[i + 1]['s'])]
    peaks.sort(key=lambda a: -a['s'])
    peaks = peaks[:o.get('peaks') or 6]
    res = []
    for p in peaks:
        q = dict(p); q.update(best_offset(src, w, h, n, p['c'], 12, 1))
        for k, st, sp in ((40, .002, .014), (200, .0005, .003), (1e9, .0002, .001)):
            q = refine(src, w, h, n, q, st, sp, k)
            q = nudge(src, w, h, n, q, k)
        res.append(q)
    res.sort(key=lambda a: -a['s'])
    return res


def decode_glyphs(src, w, h, n, o=None):
    o = o or {}
    cands = [{'c': o['cell'], 'x': o.get('x', 0), 'y': o.get('y', 0)}] if o.get('cell') else estimate_cells(src, w, h, n, o)
    for q in cands:
        g = grid(src, w, h, n, q['c'], q['x'], q['y'])
        if not g:
            continue
        oo = {'maxPilotErrors': 10}; oo.update(o)
        d = decode_grid(g, oo)
        if d:
            d.update({'cell': round(q['c'], 3), 'offX': round(q['x'], 2), 'offY': round(q['y'], 2), 'carrier': 'glyph'})
            return d
    return None
