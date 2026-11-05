"""High-capacity lossless channel (Full resolution): packed UTF-8 stored in the low bits of RGB
(port of core/dense.js). Survives only lossless saves (PNG, TIFF, XCF) at the original pixel size."""
from . import codec
from . import pack as P

MAGIC = bytes([0x49, 0x53, 0x44, 0x31])
HEADER = 22
HEADER_BITS = HEADER * 8


def slots(src, w, h, n):
    m = min(3, n)
    if n < 4:
        return range(0, w * h * n) if n == m else [i + k for i in range(0, w * h * n, n) for k in range(m)]
    out = []
    for i in range(0, w * h * n, n):
        if src[i + 3] == 255:
            out.append(i); out.append(i + 1); out.append(i + 2)
    return out


def count_slots(src, w, h, n):
    if n < 4:
        return w * h * min(3, n)
    s = 0
    for i in range(3, w * h * n, n):
        if src[i] == 255:
            s += 3
    return s


def capacity_bytes(slot_count, bpc):
    return max(0, (slot_count - HEADER_BITS) * bpc // 8)


def u32(v):
    return [(v >> 24) & 255, (v >> 16) & 255, (v >> 8) & 255, v & 255]


def r32(a, o):
    return (a[o] << 24) + (a[o + 1] << 16) + (a[o + 2] << 8) + a[o + 3]


def pack(text, progress=None):
    raw = codec.utf8_encode(text)
    r = P.pack(text, raw, progress)
    return {'raw': raw, 'data': r['data'], 'compressed': r['method'] != P.PLAIN, 'method': r['method']}


def header(bpc, method, raw_len, data):
    h = list(MAGIC) + [bpc, method] + u32(raw_len) + u32(len(data)) + u32(codec.crc32(data))
    return bytes(h + u32(codec.crc32(bytes(h))))


def embed(src, w, h, n, text, bpc):
    bpc = max(1, min(4, round(bpc or 2)))
    out = bytearray(src)
    s = slots(out, w, h, n)
    q = pack(text)
    raw = q['raw']; data = q['data']
    cap = capacity_bytes(len(s), bpc)
    if len(data) > cap:
        raise ValueError(f"Compressed payload is {len(data)} bytes; this layer holds {cap} bytes at {bpc} bit(s) per channel. Use more bits per channel or a larger image.")
    hd = header(bpc, q['method'], len(raw), data)
    k = 0
    for b in range(HEADER_BITS):
        bit = (hd[b >> 3] >> (7 - (b & 7))) & 1
        out[s[k]] = (out[s[k]] & 0xFE) | bit
        k += 1
    mask = (1 << bpc) - 1
    keep = ~mask & 255
    # Same bit order as the JavaScript: the payload bits, bpc at a time, most significant first, last group padded with 0.
    total = len(data) * 8
    if bpc == 1:
        for byte in data:
            for j in range(7, -1, -1):
                o = s[k]
                out[o] = (out[o] & keep) | ((byte >> j) & 1)
                k += 1
    else:
        # bpc bytes hold exactly 8 groups of bpc bits, so work through the data bpc bytes at a time.
        groups = -(-total // bpc)
        done = 0
        for c0 in range(0, len(data), bpc):
            chunk = bytes(data[c0:c0 + bpc])
            v = int.from_bytes(chunk + bytes(bpc - len(chunk)), 'big')
            for gi in range(8):
                if done >= groups:
                    break
                o = s[k]
                out[o] = (out[o] & keep) | ((v >> ((7 - gi) * bpc)) & mask)
                k += 1
                done += 1
    return {'pixels': out, 'rawBytes': len(raw), 'storedBytes': len(data), 'compressed': q['compressed'], 'capacity': cap, 'bpc': bpc}


def extract(src, w, h, n):
    s = slots(src, w, h, n)
    if len(s) < HEADER_BITS:
        return None
    hd = bytearray(HEADER)
    for b in range(HEADER_BITS):
        hd[b >> 3] |= (src[s[b]] & 1) << (7 - (b & 7))
    if bytes(hd[:4]) != MAGIC:
        return None
    if codec.crc32(hd[:18]) != r32(hd, 18):
        raise ValueError("High-capacity header found but damaged.")
    bpc = hd[4]; compressed = hd[5] & 3; raw_len = r32(hd, 6); ln = r32(hd, 10); crc = r32(hd, 14)
    if bpc < 1 or bpc > 4 or ln > capacity_bytes(len(s), bpc):
        raise ValueError("High-capacity header is invalid.")
    mask = (1 << bpc) - 1
    total = ln * 8
    groups = -(-total // bpc)
    buf = bytearray()
    k = HEADER_BITS
    gi = 0
    while gi < groups:
        v = 0
        for j in range(8):
            v <<= bpc
            if gi < groups:
                v |= src[s[k]] & mask
                k += 1
                gi += 1
        buf += v.to_bytes(bpc, 'big')
    data = bytes(buf[:ln])
    if codec.crc32(data) != crc:
        raise ValueError("High-capacity payload failed its CRC check. The image was changed after encoding (JPEG, resize, color conversion or edits).")
    raw = P.unpack(compressed, data)
    if len(raw) != raw_len:
        raise ValueError("High-capacity payload length mismatch.")
    return {'text': codec.utf8_decode(raw), 'bpc': bpc, 'rawBytes': raw_len, 'storedBytes': ln, 'compressed': bool(compressed)}
