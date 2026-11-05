"""Finds and reads an ISB3 carrier whose cell size is no longer a whole number of pixels, e.g. after the
image was resized to 2048 px (port of core/fractional.js)."""
import math
from .jsm import jround
from .carrier import blind_pattern, cluster_bits, decode_grid, f32


def corr(src, w, h, n, c, x0, y0, N):
    k = 0; sy = sp = sxx = szz = syx = spx = syz = spz = 0
    Y = []; P = []; X = []; Z = []
    for j in range(N):
        for i in range(N):
            x = jround(x0 + (i + .5) * c / N - .5); y = jround(y0 + (j + .5) * c / N - .5)
            if x < 0 or y < 0 or x >= w or y >= h:
                continue
            q = (y * w + x) * n
            if n > 3 and src[q + 3] < 20:
                continue
            v = .2126 * src[q] + .7152 * src[q + 1] + .0722 * src[q + 2]
            p = blind_pattern(x - x0, y - y0, c)
            a = (i - (N - 1) / 2) / N; b = (j - (N - 1) / 2) / N
            Y.append(v); P.append(p); X.append(a); Z.append(b)
            sy += v; sp += p; sxx += a * a; szz += b * b; syx += v * a; spx += p * a; syz += v * b; spz += p * b; k += 1
    if not k:
        return 0
    my = sy / k; mp = sp / k
    by = syx / sxx if sxx else 0; bp = spx / sxx if sxx else 0
    cy = syz / szz if szz else 0; cp = spz / szz if szz else 0
    num = den = 0
    for t in range(k):
        yy = Y[t] - my - by * X[t] - cy * Z[t]
        pp = P[t] - mp - bp * X[t] - cp * Z[t]
        num += yy * pp; den += pp * pp
    return num / den if den else 0


def score(src, w, h, n, c, ox, oy, kmax):
    cols = math.floor((w - ox) / c); rows = math.floor((h - oy) / c)
    kx = min(cols, kmax); ky = min(rows, kmax)
    if kx < 8 or ky < 8:
        return 0
    s = 0; m = 0; G = 6
    for j in range(G):
        for i in range(G):
            cx = jround((i + .5) * kx / G - .5); cy = jround((j + .5) * ky / G - .5)
            s += abs(corr(src, w, h, n, c, ox + cx * c, oy + cy * c, 5)); m += 1
    return s / m


def grid(src, w, h, n, c, ox=0, oy=0):
    cols = math.floor((w - ox) / c); rows = math.floor((h - oy) / c)
    if cols < 1 or rows < 1:
        return None
    values = f32([corr(src, w, h, n, c, ox + x * c, oy + y * c, 7) for y in range(rows) for x in range(cols)])
    q = cluster_bits(values)
    q.update({'values': values, 'cols': cols, 'rows': rows, 'cell': c, 'ox': ox, 'oy': oy})
    return q


def refine(src, w, h, n, c, step, span, kmax):
    best = c; bs = -1
    f = -span
    while f <= span:
        t = c * (1 + f)
        s = score(src, w, h, n, t, 0, 0, kmax)
        if s > bs:
            bs = s; best = t
        f += step
    return {'c': best, 's': bs}


def estimate_cells(src, w, h, n, o=None):
    o = o or {}
    lo = o.get('minCell') or 4.5; hi = o.get('maxCell') or 48; r = 1.012
    lst = []
    c = lo
    while c <= hi:
        lst.append({'c': c, 's': score(src, w, h, n, c, 0, 0, 10)})
        c *= r
    peaks = [q for i, q in enumerate(lst) if (i == 0 or q['s'] >= lst[i - 1]['s']) and (i == len(lst) - 1 or q['s'] >= lst[i + 1]['s'])]
    peaks.sort(key=lambda a: -a['s'])
    peaks = peaks[:o.get('peaks') or 4]
    res = []
    for p in peaks:
        q = refine(src, w, h, n, p['c'], .002, .014, 40)
        q = refine(src, w, h, n, q['c'], .0003, .0025, 1e9)
        res.append(q)
    res.sort(key=lambda a: -a['s'])
    return res


def decode_fractional(src, w, h, n, o=None):
    o = o or {}
    for q in estimate_cells(src, w, h, n, o):
        g = grid(src, w, h, n, q['c'])
        if not g:
            continue
        r = decode_grid(g, o)
        if r:
            r.update({'cell': round(q['c'], 3), 'offX': 0, 'offY': 0, 'separation': g['separation'], 'scaleScore': q['s']})
            return r
    return None
