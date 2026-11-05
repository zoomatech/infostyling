"""Shareable brightness channel for the Invisible look (port of core/brightq.js). Bits are stored as faint
brightness patterns lined up with JPEG's own 8x8 blocks, so a JPEG save or a social-media recompress keeps
them. Each 8x8 block carries K bits, one per low-frequency pattern, nudged to an even or odd step (dithered
quantization). Red, green and blue move together, so colour is unchanged. Bits are error-corrected,
scattered in a fixed scrambled order and repeated. Images longer than 2048 px are coded on a 2048 px grid."""
import math, array
from . import codec
from . import pack as P
from .jsm import jround

MAGIC = bytes([0x49, 0x53, 0x51, 0x31])
HEADER = 17
SIDE = 2048
K = 6
SEED = 0x51b7c3a5
TAIL = 6
LO = 2
HI = 253
ZZ = [(0, 1), (1, 0), (2, 0), (1, 1), (0, 2), (0, 3)]
MODES = [{'step': 24, 'rep': 2}, {'step': 20, 'rep': 1}, {'step': 30, 'rep': 3}]
MODE = MODES[0]
M32 = 0xFFFFFFFF


def _basis():
    out = []
    for u, v in ZZ:
        cu = .5 if u else math.sqrt(.5) * .5
        cv = .5 if v else math.sqrt(.5) * .5
        b = [0.0] * 64
        for y in range(8):
            for x in range(8):
                b[y * 8 + x] = cu * cv * math.cos(math.pi * (2 * y + 1) * u / 16) * math.cos(math.pi * (2 * x + 1) * v / 16)
        out.append(b)
    return out


BASIS = _basis()


def rng(seed):
    st = [seed & M32]

    def r():
        st[0] = (st[0] + 0x6D2B79F5) & M32
        t = st[0]
        t = ((t ^ (t >> 15)) * (t | 1)) & M32
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & M32)) & M32
        return ((t ^ (t >> 14)) & M32) / 4294967296
    return r


def grid(w, h):
    L = max(w, h)
    if L <= SIDE:
        return w, h, False
    s = SIDE / L
    return max(8, jround(w * s)), max(8, jround(h * s)), True


def slot_count(w, h):
    gw, gh, _ = grid(w, h)
    return (gw // 8) * (gh // 8) * K


def capacity_bytes(w, h, mode=MODE):
    coded = slot_count(w, h) // mode['rep']
    return max(0, (coded // 2 - TAIL) // 8 - HEADER)


_cache = {}


def layout(n):
    if _cache.get('n') == n:
        return _cache
    r = rng(SEED)
    perm = list(range(n))
    for i in range(n - 1, 0, -1):
        j = math.floor(r() * (i + 1))
        perm[i], perm[j] = perm[j], perm[i]
    dith = array.array('f', [r() for _ in range(n)])
    _cache.clear()
    _cache.update({'n': n, 'perm': perm, 'dith': list(dith)})
    return _cache


def luma(src, w, h, n, g):
    gw, gh, scaled = g
    if n > 2:
        Y = [.299 * src[i] + .587 * src[i + 1] + .114 * src[i + 2] for i in range(0, w * h * n, n)]
    else:
        Y = [float(src[i]) for i in range(0, w * h * n, n)]
    if not scaled:
        return Y
    out = [0.0] * (gw * gh)
    xr = []
    for x in range(gw):
        x0 = x * w // gw
        x1 = max(x0 + 1, (x + 1) * w // gw)
        xr.append((x0, x1))
    for y in range(gh):
        y0 = y * h // gh
        y1 = max(y0 + 1, (y + 1) * h // gh)
        rows = [Y[yy * w:(yy + 1) * w] for yy in range(y0, y1)]
        ny = y1 - y0
        o = y * gw
        for x in range(gw):
            x0, x1 = xr[x]
            s = 0.0
            for row in rows:
                for xx in range(x0, x1):
                    s += row[xx]
            out[o + x] = s / ((x1 - x0) * ny)
    return out


def coeffs(Y, gw, bw, bh):
    C = [0.0] * (bw * bh * K)
    for by in range(bh):
        for bx in range(bw):
            o = (by * bw + bx) * K
            blk = []
            for y in range(8):
                row = (by * 8 + y) * gw + bx * 8
                blk.extend(Y[row:row + 8])
            for k in range(K):
                b = BASIS[k]
                s = 0.0
                for i in range(64):
                    s += b[i] * blk[i]
                C[o + k] = s
    return C


def header(method, raw_len, data):
    h = bytearray(HEADER)
    h[0:4] = MAGIC
    h[4] = method
    h[5:9] = bytes(codec.u32be(raw_len))
    h[9:13] = bytes(codec.u32be(len(data)))
    h[13:17] = bytes(codec.u32be(codec.crc32(data)))
    return h


def r32(a, o):
    return (a[o] << 24) + (a[o + 1] << 16) + (a[o + 2] << 8) + a[o + 3]


def to_bits(b):
    out = bytearray(len(b) * 8)
    for i in range(len(out)):
        out[i] = (b[i >> 3] >> (7 - (i & 7))) & 1
    return out


def embed(src, w, h, n, text, mode=MODE, progress=None):
    """Hides text; returns new pixels. Raises when the text does not fit."""
    g = grid(w, h)
    gw, gh, scaled = g
    bw = gw // 8; bh = gh // 8; N = bw * bh * K
    cap = capacity_bytes(w, h, mode)
    q = codec.robust_payload(text)
    if len(q['bytes']) > cap:
        raise ValueError(f"The text packs to {len(q['bytes'])} bytes; this image holds {cap} bytes when shared.")
    frame = bytes(header(q['method'], q['rawLength'], q['bytes'])) + bytes(q['bytes'])
    coded = codec.conv_encode(to_bits(frame))
    L = layout(N)
    M = len(coded)
    nan = float('nan')
    target = [nan] * N
    out = bytearray(src)
    step = mode['step']
    rep = mode['rep']
    C = coeffs(luma(out, w, h, n, g), gw, bw, bh)
    perm = L['perm']; dith = L['dith']
    for r in range(rep):
        for j in range(M):
            s = perm[j * rep + r]
            d = dith[s] * 2 * step
            b = coded[j]
            v = C[s] - d - b * step
            target[s] = jround(v / (2 * step)) * 2 * step + d + b * step
    for pss in range(4):
        Y = luma(out, w, h, n, g)
        D = [0.0] * (gw * gh)
        C = coeffs(Y, gw, bw, bh)
        moved = 0
        for by in range(bh):
            for bx in range(bw):
                o = (by * bw + bx) * K
                blk = None
                for k in range(K):
                    t = target[o + k]
                    if t != t:
                        continue
                    dc = t - C[o + k]
                    if abs(dc) < .25:
                        continue
                    moved += 1
                    if blk is None:
                        blk = [0.0] * 64
                    b = BASIS[k]
                    for i in range(64):
                        blk[i] += dc * b[i]
                if blk is None:
                    continue
                mx = -1e9; mn = 1e9
                for y in range(8):
                    row = (by * 8 + y) * gw + bx * 8
                    for x in range(8):
                        v = Y[row + x] + blk[y * 8 + x]
                        if v > mx: mx = v
                        if v < mn: mn = v
                if mx > HI and mn - (mx - HI) >= LO:
                    shift = HI - mx
                elif mn < LO and mx + (LO - mn) <= HI:
                    shift = LO - mn
                else:
                    shift = 0
                for y in range(8):
                    row = (by * 8 + y) * gw + bx * 8
                    for x in range(8):
                        D[row + x] = blk[y * 8 + x] + shift
        if progress:
            progress((pss + 1) / 4)
        if not moved:
            break
        apply(out, w, h, n, g, D)
    return {'pixels': out, 'storedBytes': len(q['bytes']), 'rawBytes': q['rawLength'], 'capacity': cap, 'mode': mode}


def apply(out, w, h, n, g, D):
    """Adds a brightness change to R, G and B; bilinear upscale from the 2048 grid when scaled."""
    gw, gh, scaled = g
    m = min(3, n)
    if scaled:
        xs = []
        for x in range(w):
            fx = min(gw - 1, max(0, (x + .5) * gw / w - .5))
            x0 = math.floor(fx)
            xs.append((x0, min(gw - 1, x0 + 1), fx - x0))
    for y in range(h):
        if scaled:
            fy = min(gh - 1, max(0, (y + .5) * gh / h - .5))
            y0 = math.floor(fy)
            y1 = min(gh - 1, y0 + 1)
            fy -= y0
            r0 = y0 * gw; r1 = y1 * gw
        i = y * w * n
        for x in range(w):
            if not scaled:
                d = D[y * w + x]
            else:
                x0, x1, fx = xs[x]
                d = (D[r0 + x0] * (1 - fx) + D[r0 + x1] * fx) * (1 - fy) + (D[r1 + x0] * (1 - fx) + D[r1 + x1] * fx) * fy
            if d:
                for c in range(m):
                    v = jround(out[i + c] + d)
                    out[i + c] = 0 if v < 0 else 255 if v > 255 else v
            i += n


def soft(C, L, step, N):
    s = [0.0] * N
    dith = L['dith']
    for i in range(N):
        r = (C[i] - dith[i] * 2 * step) / step
        k = jround(r)
        s[i] = (1 if (k & 1) else -1) * (.5 - abs(r - k))
    return array.array('f', s)


def read_coded(sv, L, M, rep):
    b = bytearray(M); c = [0.0] * M
    perm = L['perm']
    for j in range(M):
        t = 0.0
        for r in range(rep):
            t += sv[perm[j * rep + r]]
        b[j] = 1 if t >= 0 else 0
        c[j] = abs(t)
    return b, list(array.array('f', c))


def bits_to_bytes(b, n):
    out = bytearray(n)
    lim = min(n * 8, len(b))
    for i in range(lim):
        if b[i]:
            out[i >> 3] |= 1 << (7 - (i & 7))
    return out


def extract(src, w, h, n, progress=None):
    """Reads the text back, or returns None when no channel is found."""
    g = grid(w, h)
    gw, gh, scaled = g
    bw = gw // 8; bh = gh // 8; N = bw * bh * K
    if bw < 4 or bh < 4:
        return None
    L = layout(N)
    C = coeffs(luma(src, w, h, n, g), gw, bw, bh)
    for mode in MODES:
        sv = soft(C, L, mode['step'], N)
        slots = N // mode['rep']
        hb = HEADER * 8
        if slots < 2 * (hb + TAIL):
            continue
        rb, rc = read_coded(sv, L, (hb + TAIL) * 2, mode['rep'])
        hd = bits_to_bytes(codec.conv_decode(rb, hb + TAIL, rc, False)[:hb], HEADER)
        if bytes(hd[:4]) != MAGIC:
            continue
        ln = r32(hd, 9); raw_len = r32(hd, 5); crc = r32(hd, 13)
        count = (HEADER + ln) * 8 + TAIL
        M = count * 2
        if ln > capacity_bytes(w, h, mode) or M * mode['rep'] > N:
            continue
        rb, rc = read_coded(sv, L, M, mode['rep'])
        allb = bits_to_bytes(codec.conv_decode(rb, count, rc, True)[:count - TAIL], HEADER + ln)
        data = bytes(allb[HEADER:])
        if codec.crc32(data) != crc:
            continue
        raw = P.unpack(allb[4] & 3, data)
        if len(raw) != raw_len:
            continue
        return {'text': codec.utf8_decode(raw), 'rawBytes': len(raw), 'storedBytes': ln, 'mode': mode, 'carrier': 'brightness'}
    return None


def coded_bits(ln):
    return ((HEADER + ln) * 8 + TAIL) * 2 * MODE['rep']
