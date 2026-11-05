"""Pilot and interleaving layout of the ISB3 tile (port of core/layout.js)."""
from . import codec
from .noise import hash2

PILOT_SIZE = 7
PILOT_RADIUS = 3
DATA_OFFSET = 5
PILOT = [1,1,0,0,1,0,1,0,0,1,1,0,1,1,1,0,1,0,1,1,0,0,1,1,0,0,0,1,1,1,1,0,1,0,0,0,1,0,1,1,1,0,1,0,0,1,0,1,1]


def morton_decode(n):
    x = y = b = 0
    while n > 0:
        x |= (n & 1) << b; n >>= 1
        y |= (n & 1) << b; n >>= 1
        b += 1
    return x, y


def morton_encode(x, y):
    n = 0; s = 0
    while x or y:
        n |= (x & 1) << s; s += 1
        n |= (y & 1) << s; s += 1
        x >>= 1; y >>= 1
    return n


_rel_cache = []


def data_rel(k):
    while len(_rel_cache) <= k:
        kk = len(_rel_cache)
        block = kk // 256; i = kk & 255
        perm = (i * 73 + 19) & 255
        qx, qy = morton_decode(block * 256 + perm)
        _rel_cache.append((DATA_OFFSET + qx, DATA_OFFSET + qy))
    return _rel_cache[k]


_period_cache = {}


def tile_period(n):
    if n in _period_cache:
        return _period_cache[n]
    mx = 0
    for k in range(n):
        q = data_rel(k)
        if q[0] > mx: mx = q[0]
        if q[1] > mx: mx = q[1]
    r = max(12, 5 + mx)
    _period_cache[n] = r
    return r


def blind_capacity_bytes(w, h, cell):
    c = max(8, round_js(cell or 16))
    limit = min(w // c, h // c)
    if limit < 12:
        return 0
    lo = 0; hi = 65535
    while lo < hi:
        m = -(-(lo + hi + 1) // 2)
        if tile_period(codec.v3_frame_bit_length(m)) <= limit:
            lo = m
        else:
            hi = m - 1
    return lo


def round_js(v):
    from .jsm import jround
    return jround(v)


def cell_bit(cx, cy, bits, period, seed):
    x = cx % period
    y = cy % period
    if x <= 6 and y <= 6:
        return PILOT[y * 7 + x]
    if x >= 8 and y >= 8:
        raw = morton_encode(x - 8, y - 8)
        block = raw // 256; perm = raw & 255
        i = (((perm - 19) & 255) * 249) & 255
        k = block * 256 + i
        if k < len(bits):
            return bits[k]
    return 1 if hash2(cx, cy, ((seed or 0) ^ 0x33c0ffee)) >= .5 else 0
