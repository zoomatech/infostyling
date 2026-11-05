"""ISB3 brightness carrier: writes and reads the tiled data pattern, finds pilots and decodes the grid
(port of core/carrier.js)."""
import math
from . import codec
from .jsm import jround, clamp
from .layout import PILOT_SIZE, PILOT_RADIUS, PILOT, data_rel, tile_period, cell_bit

TAU = math.pi * 2


def blind_pattern(x, y, c):
    u = (x + .5) / c; v = (y + .5) / c; t = TAU
    return (math.sin(t * (u + 2 * v + .137)) + .72 * math.sin(t * (2 * u - v + .371)) + .48 * math.cos(t * (u - v + .719))) / 2.2


def apply_blind_carrier(src, w, h, n, bits, p, progress=None):
    out = bytearray(src)
    cell = max(8, jround(p.get('blindCell') or 16))
    bs = p.get('blindStrength')
    amp = 3 + 19 * clamp((68 if bs is None else bs) / 100, 0, 1)
    period = tile_period(len(bits))
    seed = p.get('seed')
    # Rounded brightness change per position inside a cell, for a 1 bit and a 0 bit.
    pos = [[jround(amp * blind_pattern(lx, ly, cell)) for lx in range(cell)] for ly in range(cell)]
    neg = [[jround(-amp * blind_pattern(lx, ly, cell)) for lx in range(cell)] for ly in range(cell)]
    cols = -(-w // cell)
    m = min(3, n)
    for y in range(h):
        cy = y // cell; ly = y - cy * cell
        prow = pos[ly]; nrow = neg[ly]
        signs = [cell_bit(cx, cy, bits, period, seed) for cx in range(cols)]
        i = y * w * n
        for x in range(w):
            if n > 3 and out[i + 3] < 20:
                i += n
                continue
            cx = x // cell
            d = prow[x - cx * cell] if signs[cx] else nrow[x - cx * cell]
            if d:
                for k in range(m):
                    v = out[i + k] + d
                    out[i + k] = 0 if v < 0 else 255 if v > 255 else v
            i += n
        if progress and not (y & 63):
            progress(y / h)
    return {'pixels': out, 'period': period, 'cell': cell}


def cluster_bits(v):
    if not len(v):
        return {'bits': bytearray(0), 'separation': 0, 'threshold': 0}
    import bisect
    srt = sorted(v)
    pre = [0.0]
    acc = 0.0
    for x in srt:
        acc += x
        pre.append(acc)
    n = len(srt)
    a = srt[0]; b = srt[-1]
    for _ in range(10):
        # a value goes to a when it is at least as close to a as to b
        if a <= b:
            k = bisect.bisect_right(srt, (a + b) / 2) if a < b else n
        else:
            k = n - bisect.bisect_left(srt, (a + b) / 2)
        if a <= b:
            na = k; sa = pre[k]; nb = n - k; sb = pre[n] - pre[k]
        else:
            nb = n - k; sb = pre[n - k]; na = k; sa = pre[n] - pre[n - k]
        if na: a = sa / na
        if nb: b = sb / nb
    lo = min(a, b); hi = max(a, b); t = (lo + hi) / 2
    return {'bits': bytearray(1 if x >= t else 0 for x in v), 'separation': hi - lo, 'threshold': t}


def f32(v):
    import array
    return array.array('f', v)


def _lum(src, i, n):
    if n >= 3:
        return .2126 * src[i] + .7152 * src[i + 1] + .0722 * src[i + 2]
    v = src[i]
    g = src[i + 1] if n > 1 else v
    return .2126 * v + .7152 * g + .0722 * v


def detrend(s):
    if not s:
        return 0
    sy = sp = sxx = syy = syx = spx = syy1 = spy = 0
    for y, p, x, z in s:
        sy += y; sp += p; sxx += x * x; syy += z * z; syx += y * x; spx += p * x; syy1 += y * z; spy += p * z
    n = len(s)
    my = sy / n; mp = sp / n
    by = syx / sxx if sxx else 0; bp = spx / sxx if sxx else 0
    cy = syy1 / syy if syy else 0; cp = spy / syy if syy else 0
    num = den = 0
    for y, p, x, z in s:
        yy = y - my - by * x - cy * z
        pp = p - mp - bp * x - cp * z
        num += yy * pp; den += pp * pp
    return num / den if den else 0


_pat_cache = {}


def _pattern_samples(cell, N):
    k = (cell, N)
    if k not in _pat_cache:
        out = []
        for sy in range(N):
            for sx in range(N):
                lx = min(cell - 1, max(0, jround((sx + .5) * cell / N - .5)))
                ly = min(cell - 1, max(0, jround((sy + .5) * cell / N - .5)))
                out.append((lx, ly, blind_pattern(lx, ly, cell), (sx - (N - 1) / 2) / N, (sy - (N - 1) / 2) / N))
        _pat_cache[k] = out
    return _pat_cache[k]


_w_cache = {}


def _weights(cell, N):
    """Detrended pattern weights: with every sample present, the detrended correlation equals sum(y*w)/sum(w*w)."""
    k = (cell, N)
    if k not in _w_cache:
        smp = _pattern_samples(cell, N)
        n = len(smp)
        sp = sum(p for _, _, p, _, _ in smp); sxx = sum(x * x for _, _, _, x, _ in smp); szz = sum(z * z for *_, z in smp)
        spx = sum(p * x for _, _, p, x, _ in smp); spz = sum(p * z for _, _, p, _, z in smp)
        mp = sp / n; bp = spx / sxx if sxx else 0; cp = spz / szz if szz else 0
        ws = [p - mp - bp * x - cp * z for _, _, p, x, z in smp]
        den = sum(v * v for v in ws)
        _w_cache[k] = ([(lx, ly) for lx, ly, *_ in smp], ws, den, max(lx for lx, *_ in smp), max(ly for _, ly, *_ in smp))
    return _w_cache[k]


_lum_cache = [None, None, None]


def lum_of(src, w, h, n):
    """Brightness of every pixel, worked out once per image; None when some pixels are nearly transparent."""
    if _lum_cache[0] is src and _lum_cache[1] == len(src):
        return _lum_cache[2]
    import array
    L = None
    if n < 4 or bytes(src[3::n]).count(255) == w * h or min(src[3::n]) >= 20:
        if n >= 3:
            L = array.array('d', (.2126 * src[i] + .7152 * src[i + 1] + .0722 * src[i + 2] for i in range(0, w * h * n, n)))
    _lum_cache[0] = src; _lum_cache[1] = len(src); _lum_cache[2] = L
    return L


_off_cache = {}


def cell_correlation(src, w, h, n, cell, x0, y0, N):
    pos, ws, den, mx, my = _weights(cell, N)
    if x0 + mx < w and y0 + my < h and den:
        L = lum_of(src, w, h, n)
        if L is not None:
            k = (cell, N, w)
            offs = _off_cache.get(k)
            if offs is None:
                offs = _off_cache[k] = list(zip([ly * w + lx for lx, ly in pos], ws))
            base = y0 * w + x0
            acc = 0.0
            for o, wt in offs:
                acc += L[base + o] * wt
            return acc / den
    return _cell_correlation_slow(src, w, h, n, cell, x0, y0, N)


def _cell_correlation_slow(src, w, h, n, cell, x0, y0, N):
    s = []
    for lx, ly, p, ax, az in _pattern_samples(cell, N):
        x = x0 + lx; y = y0 + ly
        if x >= w or y >= h:
            continue
        i = (y * w + x) * n
        if n > 3 and src[i + 3] < 20:
            continue
        s.append((_lum(src, i, n), p, ax, az))
    return detrend(s)


def extract_grid(src, w, h, n, cell, ox=0, oy=0):
    cell = max(8, jround(cell)); ox = max(0, jround(ox)); oy = max(0, jround(oy))
    cols = (w - ox) // cell; rows = (h - oy) // cell
    if cols < 1 or rows < 1:
        return {'bits': bytearray(0), 'values': f32([]), 'separation': 0, 'threshold': 0, 'cols': cols, 'rows': rows}
    vals = []
    for y in range(rows):
        for x in range(cols):
            vals.append(cell_correlation(src, w, h, n, cell, ox + x * cell, oy + y * cell, 7))
    values = f32(vals)
    q = cluster_bits(values)
    q.update({'values': values, 'cols': cols, 'rows': rows, 'cell': cell, 'ox': ox, 'oy': oy})
    return q


def gbit(g, x, y):
    if 0 <= x < g['cols'] and 0 <= y < g['rows']:
        return g['bits'][y * g['cols'] + x]
    return None


def gconf(g, x, y):
    if 0 <= x < g['cols'] and 0 <= y < g['rows']:
        return abs(g['values'][y * g['cols'] + x] - g['threshold'])
    return 0


def rotate(dx, dy, o):
    o %= 4
    if o == 1: return -dy, dx
    if o == 2: return -dx, -dy
    if o == 3: return dy, -dx
    return dx, dy


def pilot_distance(g, ax, ay, o):
    d = 0
    for y in range(-3, 4):
        for x in range(-3, 4):
            rx, ry = rotate(x, y, o)
            b = gbit(g, ax + rx, ay + ry)
            if b is None:
                return 999
            d += b != PILOT[(y + PILOT_RADIUS) * PILOT_SIZE + x + PILOT_RADIUS]
    return d


_PC = [bin(i).count("1") for i in range(128)]
_PAT = None


def _pilot_rows():
    global _PAT
    if _PAT is None:
        _PAT = []
        for o in range(4):
            grid = [[0] * 7 for _ in range(7)]
            for y in range(-3, 4):
                for x in range(-3, 4):
                    rx, ry = rotate(x, y, o)
                    grid[ry + 3][rx + 3] = PILOT[(y + 3) * 7 + x + 3]
            _PAT.append([sum(grid[r][j] << j for j in range(7)) for r in range(7)])
    return _PAT


def pilots(g, mx=10):
    out = []
    cols = g['cols']; rows = g['rows']; bits = g['bits']
    pat = _pilot_rows()
    # rowint bit k = bits[y*cols + k]
    rowint = []
    for y in range(rows):
        v = 0
        seg = bits[y * cols:(y + 1) * cols]
        v = int(''.join('1' if c else '0' for c in reversed(seg)) or '0', 2)
        rowint.append(v)
    PC = _PC
    for y in range(3, rows - 3):
        r0, r1, r2, r3, r4, r5, r6 = rowint[y - 3:y + 4]
        for x in range(3, cols - 3):
            sh = x - 3
            w0 = (r0 >> sh) & 127; w1 = (r1 >> sh) & 127; w2 = (r2 >> sh) & 127; w3 = (r3 >> sh) & 127
            w4 = (r4 >> sh) & 127; w5 = (r5 >> sh) & 127; w6 = (r6 >> sh) & 127
            for o in range(4):
                p = pat[o]
                d = PC[w0 ^ p[0]] + PC[w1 ^ p[1]] + PC[w2 ^ p[2]] + PC[w3 ^ p[3]] + PC[w4 ^ p[4]] + PC[w5 ^ p[5]] + PC[w6 ^ p[6]]
                if d <= mx:
                    out.append({'x': x, 'y': y, 'o': o, 'd': d})
    out.sort(key=lambda a: a['d'])
    return out


def read_bits(g, a, count, partial=False):
    bits = bytearray(count); conf = [0.0] * count
    cols = g['cols']; rows = g['rows']; gb = g['bits']; gv = g['values']; th = g['threshold']
    o = a['o']; ax = a['x']; ay = a['y']
    for k in range(count):
        qx, qy = data_rel(k)
        rx, ry = rotate(qx, qy, o)
        x = ax + rx; y = ay + ry
        if 0 <= x < cols and 0 <= y < rows:
            j = y * cols + x
            bits[k] = gb[j]
            conf[k] = f32r(abs(gv[j] - th))
        else:
            if not partial:
                return None
    return bits, conf


def f32r(v):
    import struct
    return struct.unpack('f', struct.pack('f', v))[0]


def combine(copies, count):
    bits = bytearray(count); conf = [0.0] * count
    for i in range(count):
        score = 0; total = 0
        for c in copies:
            w = max(0, c['conf'][i] or 0) * (c.get('quality') or 1)
            if not w:
                continue
            score += (1 if c['bits'][i] else -1) * w
            total += w
        bits[i] = 1 if score >= 0 else 0
        conf[i] = f32r(total)
    S = codec.BLIND_SYNC_BITS
    for i in range(min(len(S), count)):
        bits[i] = S[i]
        if not conf[i]:
            conf[i] = f32r(.001)
    return bits, conf


def header(g, a):
    n = len(codec.BLIND_SYNC_BITS) + codec.BLIND_HEADER_BYTES * 16
    r = read_bits(g, a, n)
    if not r:
        return None
    try:
        hd = codec.decode_v3_header_bits(r[0], r[1], 14)
        return hd if hd['meta']['payloadLength'] <= 65535 else None
    except Exception:
        return None


def decode_grid(g, o):
    mpe = o.get('maxPilotErrors')
    pp = pilots(g, 10 if mpe is None else mpe)
    if not pp:
        return None
    cands = []
    for a in pp[:72]:
        hd = header(g, a)
        if not hd:
            continue
        total = codec.v3_frame_bit_length(hd['meta']['payloadLength'])
        r = read_bits(g, a, total)
        if not r:
            continue
        try:
            d = codec.decode_v3_bits(r[0], r[1], 14)
            d.update({'anchor': a, 'copies': 1, 'pilotErrors': a['d']})
            return d
        except Exception:
            cands.append({'a': a, 'h': hd, 'bits': r[0], 'conf': r[1], 'total': total, 'quality': max(.2, (11 - a['d']) / 11)})
    groups = {}
    order = []
    for c in cands:
        m = c['h']['meta']
        k = (m['payloadLength'], m['crc'], m['styleId'], m['seed'])
        if k not in groups:
            groups[k] = []; order.append(k)
        groups[k].append(c)
    for k in order:
        a = groups[k]; n = a[0]['total']
        if len(a) < 2 or not all(x['total'] == n for x in a):
            continue
        bits, conf = combine(a, n)
        try:
            d = codec.decode_v3_bits(bits, conf, 18)
            d.update({'anchor': a[0]['a'], 'copies': len(a), 'pilotErrors': a[0]['a']['d']})
            return d
        except Exception:
            pass
    hn = len(codec.BLIND_SYNC_BITS) + codec.BLIND_HEADER_BYTES * 16
    for o2 in range(4):
        a = [x for x in pp if x['o'] == o2 and x['d'] <= 7][:24]
        if not a:
            continue

        def q(x, cnt):
            b, c = read_bits(g, x, cnt, True)
            return {'a': x, 'bits': b, 'conf': c, 'quality': max(.15, (8 - x['d']) / 8)}
        hb, hc = combine([q(x, hn) for x in a], hn)
        try:
            hd = codec.decode_v3_header_bits(hb, hc, 0)
            if hd['meta']['payloadLength'] > 65535:
                continue
        except Exception:
            continue
        total = codec.v3_frame_bit_length(hd['meta']['payloadLength'])
        zb, zc = combine([q(x, total) for x in a], total)
        try:
            d = codec.decode_v3_bits(zb, zc, 0)
            d.update({'anchor': a[0], 'copies': len(a), 'pilotErrors': a[0]['d'], 'partialCombined': True})
            return d
        except Exception:
            pass
    return None


def cells(hint, camera):
    out = []

    def add(v):
        v = max(6, min(64, jround(v)))
        if v not in out:
            out.append(v)
    if hint:
        add(hint)
        if camera:
            for f in [.5, .625, .75, .8, .875, .9, .95, 1.05, 1.1, 1.125, 1.2, 1.25, 1.33, 1.5, 1.75, 2]:
                add(hint * f)
    for v in [8, 10, 12, 14, 16, 18, 20, 22, 24, 28, 32, 36, 40, 48]:
        add(v)
    return out


def phases(cell):
    s = max(1, cell // 4)
    return [(x, y) for y in range(0, cell, s) for x in range(0, cell, s)]


def phase_score(src, w, h, n, cell, ox, oy):
    cell = max(8, jround(cell))
    cols = (w - ox) // cell; rows = (h - oy) // cell
    if cols < 8 or rows < 8:
        return 0
    s = 0
    for y in range(5):
        for x in range(5):
            cx = min(cols - 1, max(0, jround((x + .5) * cols / 5 - .5)))
            cy = min(rows - 1, max(0, jround((y + .5) * rows / 5 - .5)))
            s += abs(cell_correlation(src, w, h, n, cell, ox + cx * cell, oy + cy * cell, 5))
    return s / 25


def try_image(src, w, h, n, o):
    lst = o.get('cellSizes') or cells(o.get('hintCell'), o.get('camera'))
    for cell in lst:
        g = extract_grid(src, w, h, n, cell)
        r = decode_grid(g, o)
        if r:
            r.update({'cell': cell, 'offX': 0, 'offY': 0, 'separation': g['separation']})
            return r
    if not o.get('deep'):
        return None
    hc = o.get('hintCell')
    if hc:
        hv = max(6, jround(hc))
        ordered = [hv] + [x for x in lst if x != hv]
    else:
        ordered = lst
    for cell in ordered:
        coarse = [{'x': q[0], 'y': q[1], 'score': phase_score(src, w, h, n, cell, q[0], q[1])} for q in phases(cell) if q[0] or q[1]]
        coarse.sort(key=lambda a: -a['score'])
        seen = set(); fine = []; rad = max(1, cell // 4)
        for q in coarse[:5]:
            for y in range(max(0, q['y'] - rad), min(cell, q['y'] + rad + 1)):
                for x in range(max(0, q['x'] - rad), min(cell, q['x'] + rad + 1)):
                    if (x, y) in seen:
                        continue
                    seen.add((x, y))
                    fine.append({'x': x, 'y': y, 'score': phase_score(src, w, h, n, cell, x, y)})
        fine.sort(key=lambda a: -a['score'])
        for q in fine[:14]:
            g = extract_grid(src, w, h, n, cell, q['x'], q['y'])
            r = decode_grid(g, o)
            if r:
                r.update({'cell': cell, 'offX': q['x'], 'offY': q['y'], 'separation': g['separation']})
                return r
    return None
