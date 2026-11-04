"""Packs text for hiding, using whichever is smallest: the built-in-lexicon compressor (cm.py), deflate,
or plain bytes (port of core/pack.js). Method codes: 0 plain, 1 deflate, 2 lexicon compressor.
The last packing is kept, so the space figures and the encoder use the same result."""
import zlib
from . import cm

PLAIN, DEFLATE, LEXICON = 0, 1, 2
BIG = 262144
CACHE_DIR = None  # set by the plugin: where the primed lexicon model is kept
_last = None


def deflate_raw(raw):
    c = zlib.compressobj(9, zlib.DEFLATED, -15, 8, zlib.Z_DEFAULT_STRATEGY)
    return c.compress(bytes(raw)) + c.flush()


def inflate_raw(data):
    d = zlib.decompressobj(-15)
    return d.decompress(bytes(data)) + d.flush()


def _pick(raw, c):
    z = None
    try:
        z = deflate_raw(raw)
    except Exception:
        pass
    r = {'method': PLAIN, 'data': bytes(raw)}
    if z is not None and len(z) < len(r['data']):
        r = {'method': DEFLATE, 'data': z}
    if c is not None and len(c) < len(r['data']):
        r = {'method': LEXICON, 'data': c}
    return r


def base(progress=None):
    return cm.base(CACHE_DIR, progress)


def pack(text, raw, progress=None):
    global _last
    if _last is not None and _last[0] == text:
        return _last[1]
    r = _pick(raw, cm.encode(bytes(raw), base(), progress))
    _last = (text, r)
    return r


def ready(text):
    return _last is not None and _last[0] == text


def unpack(method, data, progress=None):
    if method == LEXICON:
        return cm.decode(bytes(data), base(), progress)
    if method == DEFLATE:
        return inflate_raw(data)
    return bytes(data)
