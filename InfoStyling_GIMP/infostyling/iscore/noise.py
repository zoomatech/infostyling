"""Numeric, noise and colour helpers (port of core/math.js)."""
import math
from .jsm import jround, clamp

M32 = 0xFFFFFFFF


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    return t * t * (3 - 2 * t)


def fract(x):
    return x - math.floor(x)


def hash2(x, y, seed):
    n = (int(x) * 374761393 + int(y) * 668265263 + int(seed) * 1442695041) & M32
    n ^= n >> 13
    n = (n * 1274126177) & M32
    n ^= n >> 16
    return n / 4294967295


def value_noise(x, y, seed):
    xi = math.floor(x); yi = math.floor(y)
    tx = x - xi; ty = y - yi
    tx = tx * tx * (3 - 2 * tx); ty = ty * ty * (3 - 2 * ty)
    s3 = seed * 1442695041
    ax = xi * 374761393; ay = yi * 668265263
    bx = ax + 374761393; by = ay + 668265263
    hv = (ax + ay + s3) & M32; hv ^= hv >> 13; hv = (hv * 1274126177) & M32; hv ^= hv >> 16; a = hv / 4294967295
    hv = (bx + ay + s3) & M32; hv ^= hv >> 13; hv = (hv * 1274126177) & M32; hv ^= hv >> 16; b = hv / 4294967295
    hv = (ax + by + s3) & M32; hv ^= hv >> 13; hv = (hv * 1274126177) & M32; hv ^= hv >> 16; c = hv / 4294967295
    hv = (bx + by + s3) & M32; hv ^= hv >> 13; hv = (hv * 1274126177) & M32; hv ^= hv >> 16; d = hv / 4294967295
    ab = a + (b - a) * tx
    cd = c + (d - c) * tx
    return (ab + (cd - ab) * ty) * 2 - 1


def value_noise_ref(x, y, seed):
    xi = math.floor(x); yi = math.floor(y)
    tx = x - xi; ty = y - yi
    tx = tx * tx * (3 - 2 * tx); ty = ty * ty * (3 - 2 * ty)
    a = hash2(xi, yi, seed); b = hash2(xi + 1, yi, seed); c = hash2(xi, yi + 1, seed); d = hash2(xi + 1, yi + 1, seed)
    ab = a + (b - a) * tx
    cd = c + (d - c) * tx
    return (ab + (cd - ab) * ty) * 2 - 1


def fbm(x, y, seed, octaves, pers, lac):
    amp = 1; freq = 1; total = 0; norm = 0
    for i in range(octaves):
        total += value_noise(x * freq, y * freq, seed + i * 1013) * amp
        norm += amp
        amp *= pers
        freq *= lac
    return total / norm if norm else 0


def luminance(r, g, b):
    return .2126 * r + .7152 * g + .0722 * b


def hue_rotate(r, g, b, a):
    if abs(a) < 1e-8:
        return r, g, b
    ca = math.cos(a); sa = math.sin(a)
    y = .299 * r + .587 * g + .114 * b
    i = .596 * r - .274 * g - .322 * b
    q = .211 * r - .523 * g + .312 * b
    ii = i * ca - q * sa
    qq = i * sa + q * ca
    return (clamp(y + .956 * ii + .621 * qq, 0, 255), clamp(y - .272 * ii - .647 * qq, 0, 255), clamp(y - 1.106 * ii + 1.703 * qq, 0, 255))


def sample_nearest(src, w, h, c, x, y):
    x = clamp(jround(x), 0, w - 1); y = clamp(jround(y), 0, h - 1)
    i = (y * w + x) * c
    if c >= 3:
        return src[i], src[i + 1], src[i + 2], (src[i + 3] if c > 3 else 255)
    v = src[i]
    return v, (src[i + 1] if c > 1 else v), v, 255
