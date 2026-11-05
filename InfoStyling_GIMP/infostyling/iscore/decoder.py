"""Blind (camera) and paired decoding (port of core/decoder.js)."""
from . import codec
from .carrier import cluster_bits, try_image, f32
from .geometry import radial_undistort, perspective_rectify, rotate_quarter, rotate_image
from .jsm import jround


def decode_blind(src, w, h, c, options=None):
    o = {'deep': True, 'camera': False, 'maxPilotErrors': 10, 'rotationHint': 0}
    o.update(options or {})
    data, ww, hh = src, w, h
    if o.get('lensK1') or o.get('lensK2'):
        data, ww, hh = radial_undistort(data, ww, hh, c, o.get('lensK1'), o.get('lensK2'))
    quad = o.get('quad')
    if quad and len(quad) == 4:
        data, ww, hh = perspective_rectify(data, ww, hh, c, quad, o.get('rectWidth'), o.get('rectHeight'))
    r = try_image(data, ww, hh, c, o)
    if r:
        r.update({'deskewAngle': 0, 'quarterTurns': 0, 'rectified': bool(quad), 'rectWidth': ww, 'rectHeight': hh})
        return r
    for q in range(1, 4):
        qd, qw, qh = rotate_quarter(data, ww, hh, c, q)
        r = try_image(qd, qw, qh, c, o)
        if r:
            r.update({'deskewAngle': q * 90, 'quarterTurns': q, 'rectified': bool(quad)})
            return r
    hint = float(o.get('rotationHint') or 0)
    if abs(hint) > .01:
        rd, rw, rh = rotate_image(data, ww, hh, c, hint)
        oo = dict(o); oo['camera'] = False
        r = try_image(rd, rw, rh, c, oo)
        if r:
            r.update({'deskewAngle': hint, 'quarterTurns': 0, 'rectified': bool(quad)})
            return r
    if o.get('camera'):
        mx = max(0, float(o.get('maxAngle') or 12)); st = max(2, float(o.get('angleStep') or 4))
        a = st
        while a <= mx:
            for ang in (a, -a):
                rd, rw, rh = rotate_image(data, ww, hh, c, ang)
                oo = dict(o); oo['camera'] = False
                oo['cellSizes'] = [max(6, jround(o['hintCell']))] if o.get('hintCell') else None
                r = try_image(rd, rw, rh, c, oo)
                if r:
                    r.update({'deskewAngle': ang, 'quarterTurns': 0, 'rectified': bool(quad)})
                    return r
            a += st
    raise ValueError("No valid ISB3 camera tile recovered.")


def decode_paired(src, enc, w, h, c, p):
    cell = max(4, jround(p['cellSize']))
    cols = -(-w // cell); rows = -(-h // cell)
    deltas = []
    for gy in range(rows):
        for gx in range(cols):
            s = 0; n = 0
            for y in range(gy * cell, min(h, (gy + 1) * cell), 2):
                for x in range(gx * cell, min(w, (gx + 1) * cell), 2):
                    i = (y * w + x) * c
                    if c > 3 and src[i + 3] < 16:
                        continue
                    s += (.2126 * enc[i] + .7152 * enc[i + 1] + .0722 * enc[i + 2]) - (.2126 * src[i] + .7152 * src[i + 1] + .0722 * src[i + 2])
                    n += 1
            deltas.append(s / n if n else 0)
    cl = cluster_bits(f32(deltas))
    raw = cl['bits']
    if len(raw) < codec.HEADER_BYTES * 8:
        raise ValueError("Not enough paired cells.")
    for inv in (False, True):
        bits = bytearray(b ^ (1 if inv else 0) for b in raw)
        try:
            hd = codec.bits_to_bytes(bits[:codec.HEADER_BYTES * 8], codec.HEADER_BYTES)
            ln = codec.read_u32be(hd, 6)
            by = codec.bits_to_bytes(bits[:(codec.HEADER_BYTES + ln) * 8], codec.HEADER_BYTES + ln)
            r = codec.parse_frame_bytes(by)
            return {'text': r['text'], 'confidence': cl['separation']}
        except Exception:
            pass
    raise ValueError("Paired channel did not decode.")
