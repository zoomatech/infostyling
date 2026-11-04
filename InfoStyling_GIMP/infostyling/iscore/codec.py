"""ISB3 framing, CRC and the rate-1/2 convolutional code with Viterbi decoding (port of core/codec.js)."""
import zlib
from . import pack

MAGIC = bytes([0x49, 0x53, 0x30, 0x31])
HEADER_BYTES = 14
BLIND_MAGIC = bytes([0x49, 0x53, 0x42, 0x31])
BLIND_HEADER_BYTES = 20
G0 = 0x79
G1 = 0x5B
MEMORY = 6


def utf8_encode(s):
    return s.encode('utf-8', 'surrogatepass')


def utf8_decode(a):
    return bytes(a).decode('utf-8', 'replace')


def crc32(a):
    return zlib.crc32(bytes(a)) & 0xFFFFFFFF


def u32be(v):
    return [(v >> 24) & 255, (v >> 16) & 255, (v >> 8) & 255, v & 255]


def read_u32be(a, o):
    return (a[o] << 24) | (a[o + 1] << 16) | (a[o + 2] << 8) | a[o + 3]


def bytes_to_bits(a):
    out = []
    for v in a:
        out.extend(((v >> 7) & 1, (v >> 6) & 1, (v >> 5) & 1, (v >> 4) & 1, (v >> 3) & 1, (v >> 2) & 1, (v >> 1) & 1, v & 1))
    return out


def bits_to_bytes(bits, n=None):
    if n is None:
        n = len(bits) // 8
    out = bytearray(n)
    for i in range(n):
        v = 0
        for b in range(8):
            k = i * 8 + b
            v = (v << 1) | (1 if k < len(bits) and bits[k] else 0)
        out[i] = v
    return bytes(out)


BLIND_SYNC_BITS = bytes_to_bits([0xD3, 0x91, 0x5A, 0xC7, 0x2E, 0x84, 0xF1, 0x6B])


def packet(text):
    p = utf8_encode(text)
    return bytes(MAGIC) + bytes([1, 0]) + bytes(u32be(len(p))) + bytes(u32be(crc32(p))) + p


def frame_bits(text):
    return bytes_to_bits(packet(text))


def parse_frame_bytes(a):
    if len(a) < HEADER_BYTES or a[:4] != MAGIC:
        raise ValueError("Paired magic mismatch.")
    n = read_u32be(a, 6)
    p = a[HEADER_BYTES:HEADER_BYTES + n]
    if len(p) != n:
        raise ValueError("Paired frame truncated.")
    if crc32(p) != read_u32be(a, 10):
        raise ValueError("Paired CRC mismatch.")
    return {'text': utf8_decode(p), 'payloadLength': n}


STYLE = {'engraving': 1, 'impressionist': 2, 'cubist': 3, 'surreal': 4, 'penskip': 5, 'stipple': 6, 'fractal': 7}
STYLE_NAME = {v: k for k, v in STYLE.items()}


def robust_payload(text):
    raw = utf8_encode(text)
    r = pack.pack(text, raw)
    return {'bytes': r['data'], 'compressed': r['method'] != pack.PLAIN, 'method': r['method'], 'rawLength': len(raw)}


def robust_stored_bytes(text):
    return len(robust_payload(text)['bytes'])


def blind_packet(text, m):
    q = robust_payload(text)
    p = q['bytes']
    a = bytearray(BLIND_HEADER_BYTES + len(p))
    a[0:4] = BLIND_MAGIC
    a[4] = 5 if q['method'] == pack.LEXICON else 4 if q['compressed'] else 3
    a[5] = STYLE.get(m.get('style'), 0)
    a[6] = (m.get('blindCell') or 16) & 255
    a[7] = ((m.get('flags') or 0) & ~1 & 255) | (1 if q['compressed'] else 0)
    a[8:12] = bytes(u32be(len(p)))
    a[12:16] = bytes(u32be(crc32(p)))
    a[16:20] = bytes(u32be((m.get('seed') or 0) & 0xFFFFFFFF))
    a[20:] = p
    return bytes(a)


def parse_blind_header(a):
    if len(a) < BLIND_HEADER_BYTES or bytes(a[:4]) != BLIND_MAGIC:
        raise ValueError("Blind magic mismatch.")
    if a[4] < 3 or a[4] > 5:
        raise ValueError("Not ISB3.")
    compressed = a[4] >= 4 and bool(a[7] & 1)
    return {'version': a[4], 'compressed': compressed,
            'method': pack.PLAIN if not compressed else pack.LEXICON if a[4] == 5 else pack.DEFLATE,
            'style': STYLE_NAME.get(a[5], 'unknown'), 'styleId': a[5], 'blindCell': a[6], 'flags': a[7],
            'payloadLength': read_u32be(a, 8), 'crc': read_u32be(a, 12), 'seed': read_u32be(a, 16)}


def _parity(v):
    v ^= v >> 4; v ^= v >> 2; v ^= v >> 1
    return v & 1


# Trellis: for each state (0..63) and input bit, the next state and the two output bits.
NEXT = [[0, 0] for _ in range(64)]
OUTA = [[0, 0] for _ in range(64)]
OUTB = [[0, 0] for _ in range(64)]
for _s in range(64):
    for _b in range(2):
        _r = ((_s << 1) | _b) & 127
        NEXT[_s][_b] = _r & 63
        OUTA[_s][_b] = _parity(_r & G0)
        OUTB[_s][_b] = _parity(_r & G1)


def conv_encode(bits):
    out = bytearray((len(bits) + MEMORY) * 2)
    state = 0
    k = 0
    nb = len(bits)
    for i in range(nb + MEMORY):
        b = 1 if i < nb and bits[i] else 0
        out[k] = OUTA[state][b]; out[k + 1] = OUTB[state][b]
        k += 2
        state = NEXT[state][b]
    return out


# Precomputed per-state transitions as flat lists for the Viterbi loop.
_TR = []
for _s in range(64):
    for _b in range(2):
        _TR.append((_s, _b, NEXT[_s][_b], OUTA[_s][_b], OUTB[_s][_b]))


def conv_decode(bits, count, confidence=None, end_zero=False):
    steps = min(count, len(bits) // 2)
    if not steps:
        return bytearray(0)
    INF = 1e30
    prev = [INF] * 64
    prev[0] = 0.0
    back = bytearray(steps * 64)
    choice = bytearray(steps * 64)
    tr = _TR
    for t in range(steps):
        nxt = [INF] * 64
        r0 = 1 if bits[t * 2] else 0
        r1 = 1 if bits[t * 2 + 1] else 0
        if confidence is not None:
            w0 = confidence[t * 2] or 0; w0 = w0 if w0 > 0 else 0
            w1 = confidence[t * 2 + 1] or 0; w1 = w1 if w1 > 0 else 0
        else:
            w0 = w1 = 1
        base = t * 64
        # cost of each (a,b) output pair this step
        ca = ((w0 if r0 else 0), (0 if r0 else w0))
        cb = ((w1 if r1 else 0), (0 if r1 else w1))
        for s, bit, ns, a, b in tr:
            bs = prev[s]
            if bs >= INF / 2:
                continue
            c = bs + ca[a] + cb[b]
            if c < nxt[ns]:
                nxt[ns] = c
                back[base + ns] = s
                choice[base + ns] = bit
        prev = nxt
    state = 0
    if not end_zero:
        best = prev[0]
        for s in range(1, 64):
            if prev[s] < best:
                best = prev[s]; state = s
    out = bytearray(steps)
    for t in range(steps - 1, -1, -1):
        out[t] = choice[t * 64 + state]
        state = back[t * 64 + state]
    return out


def v3_frame_bits(text, m):
    return bytearray(BLIND_SYNC_BITS) + conv_encode(bytes_to_bits(blind_packet(text, m)))


def v3_frame_bit_length(n):
    return len(BLIND_SYNC_BITS) + 2 * ((BLIND_HEADER_BYTES + n) * 8 + MEMORY)


def sync(bits, pos=0):
    S = BLIND_SYNC_BITS
    d = 0; di = 0
    for i in range(len(S)):
        k = pos + i
        v = bits[k] if k < len(bits) else None
        if v != S[i]:
            d += 1
        if v == S[i]:
            di += 1
    inv = 0
    if di < d:
        d = di; inv = 1
    return d, inv


def decode_block(bits, conf, start, nbytes, tail, end_zero, inv):
    count = nbytes * 8 + tail
    ln = count * 2
    nb = len(bits)
    coded = bytearray(ln)
    weights = [0.0] * ln if conf is not None else None
    for i in range(ln):
        k = start + i
        v = bits[k] if k < nb else 0
        coded[i] = (v ^ (1 if inv else 0)) & 1 if k < nb else (1 if inv else 0)
        if weights is not None:
            weights[i] = (conf[k] if k < len(conf) else 0) or 0
    dec = conv_decode(coded, count, weights, end_zero)
    return bits_to_bytes(dec[:count - tail], nbytes)


def decode_v3_header_bits(bits, conf, max_sync_errors=14):
    d, inv = sync(bits)
    if d > max_sync_errors:
        raise ValueError("ISB3 sync mismatch.")
    return {'meta': parse_blind_header(decode_block(bits, conf, len(BLIND_SYNC_BITS), BLIND_HEADER_BYTES, 0, False, inv)),
            'syncErrors': d, 'inverted': bool(inv)}


def decode_v3_bits(bits, conf, max_sync_errors=14, max_payload=1048576):
    S = len(BLIND_SYNC_BITS)
    c = []
    p = 0
    while p + S + BLIND_HEADER_BYTES * 16 <= len(bits):
        d, inv = sync(bits, p)
        if d <= max_sync_errors:
            c.append((d, p, inv))
        p += 1
    c.sort(key=lambda q: q[0])  # stable, like JS sort
    last = None
    for d, p, inv in c:
        try:
            start = p + S
            h = parse_blind_header(decode_block(bits, conf, start, BLIND_HEADER_BYTES, 0, False, inv))
            if h['payloadLength'] > max_payload:
                continue
            total = BLIND_HEADER_BYTES + h['payloadLength']
            need = (total * 8 + MEMORY) * 2
            if start + need > len(bits):
                continue
            a = decode_block(bits, conf, start, total, MEMORY, True, inv)
            header = parse_blind_header(a[:BLIND_HEADER_BYTES])
            pl = a[BLIND_HEADER_BYTES:]
            if crc32(pl) != header['crc']:
                raise ValueError("ISB3 CRC mismatch.")
            raw = pack.unpack(header['method'], pl)
            return {'text': utf8_decode(raw), 'payloadLength': len(raw), 'storedLength': len(pl),
                    'compressed': bool(header['compressed']), 'meta': header, 'syncErrors': d}
        except Exception as e:
            last = e
    raise ValueError(str(last) if last else "No ISB3 synchronization found.")
