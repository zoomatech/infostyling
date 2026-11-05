"""Text compressor for hidden text (port of core/cm.js). It predicts each bit from the text before it:
contexts of the last 1 to 6 characters, the current and previous word, and a long-match model. The
predictions are mixed and arithmetic-coded. The model is primed with the built-in English lexicon.
Encoder and decoder run the identical model, bit for bit the same as the JavaScript version."""
import math, os, array, zlib
from .jsm import jround

TBITS = 21
TSIZE = 1 << TBITS
TMASK = TSIZE - 1
N = 7
NI = N + 2
MBITS = 20
M32 = 0xFFFFFFFF


def _f32(vals):
    return array.array('f', vals)


ST = _f32([jround(math.log(((i + .5) / 4096) / (1 - (i + .5) / 4096)) * 1024) / 1024 for i in range(4096)])
SQ = _f32([jround(65536 / (1 + math.exp(-((i - 2048) / 128)))) / 65536 for i in range(4096)])
STL = list(ST)
SQL = list(SQ)
APM_ROW = [jround(1 / (1 + math.exp(-(j - 16) / 2)) * 65535) for j in range(33)]


def squash(x):
    i = jround(x * 128) + 2048
    return SQL[0 if i < 0 else 4095 if i > 4095 else i]


def H(a, b):
    return ((((a ^ ((b * 0x9E3779B1) & M32)) * 0x2545F491) & M32) ^ (a >> 15)) & M32


class Model:
    def __init__(self, empty=False):
        if empty:
            return
        self.t = array.array('H', [32768]) * (TSIZE * N)
        self.n = bytearray(TSIZE * N)
        self.w = array.array('f', [.25]) * (256 * NI)
        self.apm = array.array('H', APM_ROW) * 65536
        self.mt = array.array('i', [0]) * (1 << MBITS)
        self.mm = array.array('H', [49152]) * 128
        self.buf = bytearray(1 << 16)
        self.pos = 0; self.mp = 0; self.ml = 0; self.mexp = 0; self.mi = 0
        self.h = [0] * N
        self.idx = [0] * N
        self.x = [0.0] * NI
        self.c0 = 1; self.c4 = 0; self.c8 = 0; self.word = 0; self.b2 = 0; self.bit = 0
        self.pr = .5; self.pm = .5; self.ai = 0; self.aw = 0.0
        self.ctx()

    ARRAYS = ('t', 'n', 'w', 'apm', 'mt', 'mm', 'buf')
    SCALARS = ('pos', 'mp', 'ml', 'mexp', 'mi', 'c0', 'c4', 'c8', 'word', 'b2', 'bit', 'pr', 'pm', 'ai', 'aw')

    def clone(self):
        m = Model(True)
        for k in self.ARRAYS:
            setattr(m, k, getattr(self, k)[:])
        for k in self.SCALARS:
            setattr(m, k, getattr(self, k))
        m.h = self.h[:]; m.idx = self.idx[:]; m.x = self.x[:]
        return m

    def ctx(self):
        c = self.c4
        h = self.h
        h[0] = 0
        h[1] = H(1, c & 0xff)
        h[2] = H(2, c & 0xffff)
        h[3] = H(3, c & 0xffffff)
        h[4] = H(4, c)
        h[5] = H(5, H(c, self.c8))
        h[6] = H(H(6, self.word), self.b2)

    # p() and update() are inlined in _code() for speed; these readable versions are kept for reference and tests.
    def p(self):
        return _step(self, None)

    def prime(self, data):
        _run(self, data, None)


PRIME, ENCODE, DECODE = 0, 1, 2


def _run(m, mode, data, count, st, out):
    """Runs the model over bytes. PRIME: learn data. ENCODE: learn data and arithmetic-code it into out.
    DECODE: read count bytes from the coded data (st holds the coder state and read position) into out.
    st = [x1, x2, x, readpos] is the coder state, carried across calls."""
    t = m.t; nn = m.n; w = m.w; apm = m.apm; mt = m.mt; mm = m.mm; h = m.h; idx = m.idx; x = m.x
    ST_ = STL; SQ_ = SQL
    buf = m.buf
    pos = m.pos; mp = m.mp; ml = m.ml; mexp = m.mexp; mi = m.mi
    c0 = m.c0; c4 = m.c4; c8 = m.c8; word = m.word; b2 = m.b2; bitn = m.bit
    floor = math.floor
    x1, x2, xv, rp = st
    dlen = len(data)
    rng = range(N)
    rngi = range(NI)
    bits_range = range(7, -1, -1)
    total = count if mode == DECODE else len(data)
    for ci in range(total):
        c = 0 if mode == DECODE else data[ci]
        for b in bits_range:
            # ---- predict
            wo = c0 * NI
            k0 = (c0 * 0x6F4F2A35) & M32
            dot = 0.0
            for i in rng:
                j = i * TSIZE + ((h[i] + k0) & TMASK)
                idx[i] = j
                s = ST_[t[j] >> 4]
                x[i] = s
                dot += w[wo + i] * s
            if ml > 0:
                bm = buf[mp]
                e = (bm >> (7 - bitn)) & 1
                if ((bm | 256) >> (8 - bitn)) != c0:
                    ml = 0
                    x[N] = 0.0
                else:
                    mexp = e
                    mi = (ml if ml < 63 else 63) * 2 + e
                    s = ST_[mm[mi] >> 4]
                    x[N] = s if e else -s
            else:
                x[N] = 0.0
            x[N + 1] = .25
            dot += w[wo + N] * x[N] + w[wo + N + 1] * .25
            q = dot * 128
            fq = floor(q)
            qi = (fq + 1 if q - fq >= .5 else fq) + 2048
            pm = SQ_[0 if qi < 0 else 4095 if qi > 4095 else qi]
            s = (-7.999 if dot < -7.999 else 7.999 if dot > 7.999 else dot) * 2 + 16
            lo = floor(s)
            fr = s - lo
            ai = (((c4 & 0xff) << 8) | c0) * 33 + lo
            pa = (apm[ai] * (1 - fr) + apm[ai + 1] * fr) / 65536
            pr = (pm + 3 * pa) / 4
            if pr > .9999: pr = .9999
            elif pr < .0001: pr = .0001
            # ---- code
            if mode == PRIME:
                bit = (c >> b) & 1
            elif mode == ENCODE:
                bit = (c >> b) & 1
                xm = x1 + floor((x2 - x1) * (1 - pr))
                if bit: x1 = xm + 1
                else: x2 = xm
                while ((x1 ^ x2) & 0xff000000) == 0:
                    out.append(x2 >> 24)
                    x1 = (x1 << 8) & M32
                    x2 = ((x2 << 8) | 255) & M32
            else:
                xm = x1 + floor((x2 - x1) * (1 - pr))
                bit = 1 if xv > xm else 0
                if bit: x1 = xm + 1
                else: x2 = xm
                while ((x1 ^ x2) & 0xff000000) == 0:
                    x1 = (x1 << 8) & M32
                    x2 = ((x2 << 8) | 255) & M32
                    xv = ((xv << 8) | (data[rp] if rp < dlen else 0)) & M32
                    rp += 1
                c = (c << 1) | bit
            # ---- update
            for i in rng:
                j = idx[i]
                k = nn[j]
                tv = t[j]
                t[j] = int(tv + ((65535 if bit else 0) - tv) / (k + 1.6))
                if k < 60: nn[j] = k + 1
            if ml > 0 and x[N] != 0:
                mv = mm[mi]
                mm[mi] = int(mv + ((65535 if bit == mexp else 0) - mv) / 32)
            le = .012 * (bit - pm)
            for i in rngi:
                w[wo + i] = w[wo + i] + le * x[i]
            g = 65535 if bit else 0
            av = apm[ai]
            apm[ai] = int(av + (g - av) * (1 - fr) / 40)
            av = apm[ai + 1]
            apm[ai + 1] = int(av + (g - av) * fr / 40)
            c0 = (c0 << 1) | bit
            bitn += 1
            if c0 >= 256:
                cc = c0 & 255
                c8 = ((c8 << 8) | (c4 >> 24)) & M32
                c4 = ((c4 << 8) | cc) & M32
                c0 = 1
                bitn = 0
                if pos >= len(buf):
                    buf.extend(bytes(len(buf)))
                buf[pos] = cc
                pos += 1
                if ml > 0:
                    ml += 1
                    mp += 1
                hk = H(c4, c8 & 0xffff) >> (32 - MBITS)
                if ml == 0 and pos >= 6:
                    p = mt[hk]
                    if p > 0:
                        l = 0
                        while l < 32 and p - 1 - l >= 0 and buf[p - 1 - l] == buf[pos - 1 - l]:
                            l += 1
                        if l >= 6:
                            ml = l
                            mp = p
                mt[hk] = pos
                lc = cc + 32 if 65 <= cc <= 90 else cc
                if 97 <= lc <= 122 or cc == 39 or cc >= 128:
                    word = H(word, lc)
                elif word:
                    b2 = word
                    word = 0
                h[1] = H(1, c4 & 0xff)
                h[2] = H(2, c4 & 0xffff)
                h[3] = H(3, c4 & 0xffffff)
                h[4] = H(4, c4)
                h[5] = H(5, H(c4, c8))
                h[6] = H(H(6, word), b2)
        if mode == DECODE:
            out.append(c)
    m.buf = buf
    m.pos = pos; m.mp = mp; m.ml = ml; m.mexp = mexp; m.mi = mi
    m.c0 = c0; m.c4 = c4; m.c8 = c8; m.word = word; m.b2 = b2; m.bit = bitn
    st[0] = x1; st[1] = x2; st[2] = xv; st[3] = rp


def _prime(m, data):
    _run(m, PRIME, data, 0, [0, M32, 0, 0], None)


Model.prime = _prime

SLICE = 65536


def encode(data, model, progress=None):
    """Packs bytes; progress(fraction) is called between 64 KB slices."""
    n = len(data)
    out = []
    while True:
        b = n & 127
        n //= 128
        out.append(b | 128 if n else b)
        if not n:
            break
    st = [0, M32, 0, 0]
    for i in range(0, len(data), SLICE):
        _run(model, ENCODE, data[i:i + SLICE], 0, st, out)
        if progress:
            progress(min(1.0, (i + SLICE) / len(data)))
    x1 = st[0]
    out.extend((x1 >> 24, (x1 >> 16) & 255, (x1 >> 8) & 255, x1 & 255))
    return bytes(out)


def decode(data, model, progress=None):
    pos = 0; ln = 0; mul = 1
    while True:
        b = data[pos]; pos += 1
        ln += (b & 127) * mul
        mul *= 128
        if not (b & 128):
            break
    xv = 0
    for i in range(4):
        xv = ((xv << 8) | (data[pos] if pos < len(data) else 0)) & M32
        pos += 1
    st = [0, M32, xv, pos]
    out = []
    done = 0
    while done < ln:
        k = min(SLICE, ln - done)
        _run(model, DECODE, data, k, st, out)
        done += k
        if progress:
            progress(done / ln)
    return bytes(out)


# ---- the primed model, cached on disk so the 400 KB lexicon is learned only once per computer
_primed = None


def lexicon_bytes():
    with open(os.path.join(os.path.dirname(__file__), 'lexicon.bin'), 'rb') as f:
        return f.read()


CACHE_VERSION = b'ISCM1'


def _save(m, path):
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(CACHE_VERSION)
        import pickle
        sc = {k: getattr(m, k) for k in Model.SCALARS}
        sc['h'] = m.h
        meta = pickle.dumps(sc, protocol=4)
        f.write(len(meta).to_bytes(4, 'big')); f.write(meta)
        for k in Model.ARRAYS:
            raw = zlib.compress(bytes(getattr(m, k)), 1)
            f.write(len(raw).to_bytes(4, 'big')); f.write(raw)
    os.replace(tmp, path)


def _load(path):
    import pickle
    with open(path, 'rb') as f:
        if f.read(len(CACHE_VERSION)) != CACHE_VERSION:
            return None
        meta = pickle.loads(f.read(int.from_bytes(f.read(4), 'big')))
        m = Model(True)
        types = {'t': 'H', 'w': 'f', 'apm': 'H', 'mt': 'i', 'mm': 'H'}
        for k in Model.ARRAYS:
            raw = zlib.decompress(f.read(int.from_bytes(f.read(4), 'big')))
            if k in types:
                a = array.array(types[k]); a.frombytes(raw); setattr(m, k, a)
            else:
                setattr(m, k, bytearray(raw))
    m.h = meta.pop('h')
    for k, v in meta.items():
        setattr(m, k, v)
    m.idx = [0] * N; m.x = [0.0] * NI
    if len(m.t) != TSIZE * N or len(m.n) != TSIZE * N:
        return None
    return m


def base(cache_dir=None, progress=None):
    """A fresh copy of the lexicon-primed model."""
    global _primed
    if _primed is None:
        path = os.path.join(cache_dir, 'infostyling_lexicon_model.bin') if cache_dir else None
        if path and os.path.exists(path):
            try:
                _primed = _load(path)
            except Exception:
                _primed = None
        if _primed is None:
            m = Model()
            lex = lexicon_bytes()
            for i in range(0, len(lex), SLICE):
                _prime(m, lex[i:i + SLICE])
                if progress:
                    progress(min(1.0, (i + SLICE) / len(lex)))
            _primed = m
            if path:
                try:
                    os.makedirs(cache_dir, exist_ok=True)
                    _save(m, path)
                except Exception:
                    pass
    return _primed.clone()
