"""Signed seal (port of core/seal.js): proves who hid the text, and that neither the text nor the picture
was changed afterwards. The seal rides at the end of the hidden text, after a 0 character. It holds the
signer's name, the time, a coarse 8x8 brightness fingerprint of the finished picture, the signer's public
key and an Ed25519 signature over all of that plus the text."""
import os, time, datetime
from . import codec, ed25519

MARK = "\u0000SEAL1:"
VERSION = 1
GRID = 8
FP = GRID * GRID * 5 // 8
PK = 32
SIG = 64
NAME_MAX = 40
DOMAIN = codec.utf8_encode("InfoStyling seal 1\u0000")
AVG_MAX = 10
CELL_MAX = 40
B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def b64(a):
    s = []
    n = len(a)
    for i in range(0, n, 3):
        v = a[i] << 16 | (a[i + 1] if i + 1 < n else 0) << 8 | (a[i + 2] if i + 2 < n else 0)
        s.append(B64[v >> 18 & 63] + B64[v >> 12 & 63] + (B64[v >> 6 & 63] if i + 1 < n else "=") + (B64[v & 63] if i + 2 < n else "="))
    return "".join(s)


def unb64(s):
    s = s.rstrip("=")
    out = bytearray()
    v = k = 0
    for c in s:
        dd = B64.find(c)
        if dd < 0:
            raise ValueError("bad seal")
        v = (v << 6 | dd) & 0xFFFFFFFF
        k += 6
        if k >= 8:
            k -= 8
            out.append(v >> k & 255)
    return bytes(out[:len(s) * 3 // 4])


def hexs(a):
    return "".join("%02X" % v for v in a)


def key_id(pk):
    h = hexs(ed25519.sha512(pk)[:4])
    return h[:4] + "-" + h[4:]


def _utf16_len_trim(s):
    # JavaScript s.slice(0,-1) removes one UTF-16 unit; a whole character is the closest Python equivalent.
    return s[:-1]


def clean_name(name):
    s = str(name or "").strip()
    while len(codec.utf8_encode(s)) > NAME_MAX:
        s = _utf16_len_trim(s)
    return s


def means(px, w, h, n):
    m = [0.0] * (GRID * GRID)
    for gy in range(GRID):
        y0 = gy * h // GRID; y1 = max(y0 + 1, (gy + 1) * h // GRID)
        for gx in range(GRID):
            x0 = gx * w // GRID; x1 = max(x0 + 1, (gx + 1) * w // GRID)
            s = 0.0; c = 0
            for y in range(y0, y1, 2):
                for x in range(x0, x1, 2):
                    i = (y * w + x) * n
                    s += .299 * px[i] + .587 * px[i + 1] + .114 * px[i + 2] if n > 2 else px[i]
                    c += 1
            m[gy * GRID + gx] = s / c
    return m


def fingerprint(px, w, h, n):
    from .jsm import jround
    m = means(px, w, h, n)
    out = bytearray(FP)
    for i, v in enumerate(m):
        q = max(0, min(31, jround(v * 31 / 255)))
        for b in range(5):
            if q >> (4 - b) & 1:
                k = i * 5 + b
                out[k >> 3] |= 128 >> (k & 7)
    return bytes(out)


def unfingerprint(fp):
    q = []
    for i in range(GRID * GRID):
        v = 0
        for b in range(5):
            k = i * 5 + b
            v = v << 1 | (fp[k >> 3] >> (7 - (k & 7)) & 1)
        q.append(v * 255 / 31)
    return q


def picture_matches(fp, px, w, h, n):
    a = unfingerprint(fp); m = means(px, w, h, n)
    s = 0; worst = 0
    for i in range(len(m)):
        dd = abs(m[i] - a[i]); s += dd
        if dd > worst: worst = dd
    avg = s / len(m)
    return {'ok': avg <= AVG_MAX and worst <= CELL_MAX, 'avg': avg, 'worst': worst}


def new_keys():
    return ed25519.keypair_from_seed(ed25519.sha512(os.urandom(64) + str(time.time()).encode())[:32])


def keys_from_secret(s):
    return ed25519.keypair_from_secret(unb64(s))


def secret_text(k):
    return b64(k['secretKey'])


def body(name, t, fp, pk):
    nm = codec.utf8_encode(clean_name(name))
    t = int(t) & 0xFFFFFFFF
    return bytes([VERSION, len(nm)]) + nm + bytes([t >> 24 & 255, t >> 16 & 255, t >> 8 & 255, t & 255]) + bytes(fp) + bytes(pk)


def attach(text, s):
    return text + MARK + b64(s)


def placeholder(text, name, keys):
    """The text with a seal of the right length but no real signature, for measuring space."""
    h = ed25519.sha512(codec.utf8_encode(text[:200] + name))

    def fill(n):
        return bytes(h[i % 64] ^ (i * 151 & 255) for i in range(n))
    return attach(text, body(name, time.time(), fill(FP), keys['publicKey']) + fill(SIG))


def sign(text, name, keys, fp, t=None):
    b = body(name, time.time() if t is None else t, fp, keys['publicKey'])
    sig = ed25519.sign_detached(DOMAIN + codec.utf8_encode(text) + b, keys['secretKey'])
    return attach(text, b + sig)


def check(full, px=None, w=0, h=0, n=4):
    at = full.rfind(MARK)
    if at < 0:
        return {'text': full, 'status': "none", 'line': "Not signed."}
    text = full[:at]
    try:
        s = unb64(full[at + len(MARK):])
        nl = s[1]
        if s[0] != VERSION or len(s) != 2 + nl + 4 + FP + PK + SIG:
            raise ValueError("bad seal")
        name = codec.utf8_decode(s[2:2 + nl])
        o = 2 + nl
        t = (s[o] << 24) + (s[o + 1] << 16) + (s[o + 2] << 8) + s[o + 3]
        fp = s[o + 4:o + 4 + FP]; pk = s[o + 4 + FP:o + 4 + FP + PK]; sig = s[o + 4 + FP + PK:]; b = s[:o + 4 + FP + PK]
        date = datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%d")
        kid = key_id(pk)
        who = f'"{name}" (key ID {kid})'
        if not ed25519.verify_detached(DOMAIN + codec.utf8_encode(text) + b, sig, pk):
            return {'text': text, 'status': "tampered", 'name': name, 'date': date, 'keyId': kid, 'short': "✗ Tampered or counterfeit",
                    'line': f"✗ TAMPERED: the hidden text or its seal was changed after it was signed. The seal claims {who}."}
        if px is not None:
            m = picture_matches(fp, px, w, h, n)
            if not m['ok']:
                return {'text': text, 'status': "picture", 'name': name, 'date': date, 'keyId': kid, 'short': "✗ Picture changed",
                        'line': f"✗ PICTURE CHANGED: the text is genuine, signed by {who} on {date}, but this picture is not the one it was signed in (edited, cropped or swapped)."}
        return {'text': text, 'status': "ok", 'name': name, 'date': date, 'keyId': kid, 'short': f"✔ Signed by {name} · key {kid}",
                'line': f"✔ SIGNED by {who} on {date}. Text and picture unchanged."}
    except Exception:
        return {'text': text, 'status': "tampered", 'short': "✗ Tampered or counterfeit", 'line': "✗ TAMPERED: the seal is damaged and cannot be checked."}
