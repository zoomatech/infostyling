"""Color Pop carrier (port of core/chroma.js): a saturated, posterized mosaic whose tiles are shaded warmer
(1 bit) or cooler (0 bit) on the blue-yellow (Cb) axis only, as a smooth bump per tile."""
import math
from .jsm import jround, clamp
from .layout import tile_period, cell_bit
from .carrier import cluster_bits, decode_grid, f32

PI = math.pi


def cb(r, g, b):
    return -.168736 * r - .331264 * g + .5 * b


def bump(u, v):
    return math.sin(PI * u) * math.sin(PI * v)


def to_rgb(Y, Cb, Cr):
    return (Y + 1.402 * Cr, Y - .344136 * Cb - .714136 * Cr, Y + 1.772 * Cb)


def in_gamut(q):
    return all(0 <= v <= 255 for v in q)


def render_color_pop(src, w, h, n, bits, p, progress=None):
    c = max(8, jround(p.get('colorCell') or 20))
    period = tile_period(len(bits))
    out = bytearray(len(src))
    cs_ = p.get('colorSaturation'); sat = 1 + 1.6 * clamp((70 if cs_ is None else cs_) / 100, 0, 1)
    levels = jround(p.get('colorLevels') or 6)
    cst = p.get('colorStrength'); amp = 10 + 22 * clamp((60 if cst is None else cst) / 100, 0, 1)
    seed = p.get('seed')
    bu = [math.sin(PI * ((xx + .5) / c)) for xx in range(c)]
    cy = 0
    while cy * c < h:
        cx = 0
        while cx * c < w:
            x0 = cx * c; y0 = cy * c; x1 = min(w, x0 + c); y1 = min(h, y0 + c)
            r = g = b = 0; k = 0
            for y in range(y0, y1):
                i = (y * w + x0) * n
                for x in range(x0, x1):
                    r += src[i]; g += src[i + 1]; b += src[i + 2]; k += 1
                    i += n
            r /= k; g /= k; b /= k
            Y = .299 * r + .587 * g + .114 * b
            Yp = jround(Y / 255 * (levels - 1)) / (levels - 1) * 255
            Yp = 28 + (.65 * Yp + .35 * Y) * 200 / 255
            s = 1 if cell_bit(cx, cy, bits, period, seed) else -1
            Cb = cb(r, g, b) * sat
            Cr = (.5 * r - .418688 * g - .081312 * b) * sat
            t = 1.0
            while t >= 0:
                if in_gamut(to_rgb(Yp, Cb * t, Cr * t)) and in_gamut(to_rgb(Yp, Cb * t + s * amp, Cr * t)):
                    Cb *= t; Cr *= t
                    break
                if t < .07:
                    Cb = 0; Cr = 0
                t -= .0625
            for y in range(y0, y1):
                v = (y - y0 + .5) / c
                sv = math.sin(PI * v)
                i = (y * w + x0) * n
                for x in range(x0, x1):
                    q0, q1, q2 = to_rgb(Yp, Cb + s * amp * (bu[x - x0] * sv), Cr)
                    v0 = jround(q0); v1 = jround(q1); v2 = jround(q2)
                    out[i] = 0 if v0 < 0 else 255 if v0 > 255 else v0
                    out[i + 1] = 0 if v1 < 0 else 255 if v1 > 255 else v1
                    out[i + 2] = 0 if v2 < 0 else 255 if v2 > 255 else v2
                    if n > 3:
                        out[i + 3] = src[i + 3]
                    i += n
            cx += 1
        cy += 1
        if progress:
            progress(min(1, cy * c / h))
    return {'pixels': out, 'cell': c, 'period': period}


def cb_at(src, w, h, n, x, y):
    xi = clamp(jround(x), 0, w - 1); yi = clamp(jround(y), 0, h - 1)
    i = (yi * w + xi) * n
    return cb(src[i], src[i + 1], src[i + 2])


def tile_value(src, w, h, n, c, x0, y0, N, norm=False):
    k = 0; sy = sp = sxx = szz = syx = spx = syz = spz = 0
    Y = []; P = []; X = []; Z = []
    for j in range(N):
        for i in range(N):
            u = (i + .5) / N; v = (j + .5) / N
            val = cb_at(src, w, h, n, x0 + u * c - .5, y0 + v * c - .5)
            p = bump(u, v); a = u - .5; b = v - .5
            Y.append(val); P.append(p); X.append(a); Z.append(b)
            sy += val; sp += p; sxx += a * a; szz += b * b; syx += val * a; spx += p * a; syz += val * b; spz += p * b; k += 1
    my = sy / k; mp = sp / k; by = syx / sxx; bp = spx / sxx; cy = syz / szz; cp = spz / szz
    num = den = ey = 0
    for t in range(k):
        yy = Y[t] - my - by * X[t] - cy * Z[t]
        pp = P[t] - mp - bp * X[t] - cp * Z[t]
        num += yy * pp; den += pp * pp; ey += yy * yy
    if norm:
        return num / math.sqrt(den * ey) if den and ey else 0
    return num / den if den else 0


def score(src, w, h, n, c, ox, oy, kmax=1e9):
    cols = math.floor((w - ox) / c); rows = math.floor((h - oy) / c)
    if cols < 12 or rows < 12:
        return 0
    kx = min(cols, kmax); ky = min(rows, kmax); G = min(10, kx)
    s = 0
    for j in range(G):
        for i in range(G):
            cx = jround((i + .5) * kx / G - .5); cy = jround((j + .5) * ky / G - .5)
            s += abs(tile_value(src, w, h, n, c, ox + cx * c, oy + cy * c, 5, True))
    return s / (G * G)


def grid(src, w, h, n, c, ox=0, oy=0):
    cols = math.floor((w - ox) / c); rows = math.floor((h - oy) / c)
    if cols < 12 or rows < 12:
        return None
    values = f32([tile_value(src, w, h, n, c, ox + x * c, oy + y * c, 6) for y in range(rows) for x in range(cols)])
    q = cluster_bits(values)
    q.update({'values': values, 'cols': cols, 'rows': rows, 'cell': c, 'ox': ox, 'oy': oy})
    return q


def best_offset(src, w, h, n, c, kmax, st):
    b = {'s': -1, 'x': 0, 'y': 0}; sm = 0; m = 0
    y = 0
    while y < c - .01:
        x = 0
        while x < c - .01:
            v = score(src, w, h, n, c, x, y, kmax)
            sm += v; m += 1
            if v > b['s']:
                b = {'s': v, 'x': x, 'y': y}
            x += st
        y += st
    b['peak'] = b['s'] - sm / m
    return b


def nudge(src, w, h, n, q, kmax):
    b = dict(q); b['s'] = score(src, w, h, n, q['c'], q['x'], q['y'], kmax)
    st = max(.5, q['c'] / 16)
    dy = -3 * st
    while dy <= 3 * st:
        dx = -3 * st
        while dx <= 3 * st:
            x = q['x'] + dx; y = q['y'] + dy
            if not (x < 0 or y < 0):
                v = score(src, w, h, n, q['c'], x, y, kmax)
                if v > b['s']:
                    b = dict(q); b.update({'x': x, 'y': y, 's': v})
            dx += st
        dy += st
    return b


def refine(src, w, h, n, q, step, span, kmax):
    best = None
    f = -span
    while f <= span + 1e-9:
        t = q['c'] * (1 + f)
        v = score(src, w, h, n, t, q['x'], q['y'], kmax)
        if best is None or v > best['s']:
            best = {'c': t, 's': v, 'x': q['x'], 'y': q['y']}
        f += step
    return best


def estimate_cells(src, w, h, n, o):
    lst = []
    c = o.get('minCell') or 5
    mx = o.get('maxCell') or 64
    while c <= mx:
        b = best_offset(src, w, h, n, c, 10, max(1, c / 5))
        d = {'c': c}; d.update(b); lst.append(d)
        c *= 1.01
    peaks = [q for i, q in enumerate(lst) if (i == 0 or q['peak'] >= lst[i - 1]['peak']) and (i == len(lst) - 1 or q['peak'] >= lst[i + 1]['peak'])]
    peaks.sort(key=lambda a: -a['peak'])
    peaks = peaks[:o.get('peaks') or 5]
    res = []
    for p in peaks:
        q = dict(p); q.update(best_offset(src, w, h, n, p['c'], 12, max(.5, p['c'] / 12)))
        for k, st, sp in ((40, .002, .014), (200, .0005, .003), (1e9, .0002, .001)):
            q = refine(src, w, h, n, q, st, sp, k)
            q = nudge(src, w, h, n, q, k)
        res.append(q)
    res.sort(key=lambda a: -a['s'])
    return res


def decode_color_pop(src, w, h, n, o=None):
    o = o or {}
    cands = [{'c': o['cell'], 'x': o.get('x', 0), 'y': o.get('y', 0)}] if o.get('cell') else estimate_cells(src, w, h, n, o)
    for q in cands:
        g = grid(src, w, h, n, q['c'], q['x'], q['y'])
        if not g:
            continue
        oo = {'maxPilotErrors': 10}; oo.update(o)
        d = decode_grid(g, oo)
        if d:
            d.update({'cell': round(q['c'], 3), 'offX': round(q['x'], 2), 'offY': round(q['y'], 2), 'carrier': 'colorpop'})
            return d
    return None
