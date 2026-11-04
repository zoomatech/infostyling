"""Cover effects applied before the text is hidden: blur, lens flare, bloom, chromatic aberration,
vignette, film grain (port of core/effects.js)."""
import math
from .jsm import jround, clamp, u8
from .noise import hash2

EFFECTS = [("blur", "Gaussian blur"), ("flare", "Lens flare"), ("bloom", "Bloom / glow"), ("chroma", "Chromatic aberration"), ("vignette", "Vignette"), ("grain", "Film grain")]


def box_pass(a, w, h, n, r, horizontal):
    if r < 1:
        return a
    out = bytearray(a)
    m = min(3, n)
    ln = w if horizontal else h
    lines = h if horizontal else w
    win = 2 * r + 1
    for L in range(lines):
        for k in range(m):
            if horizontal:
                idx = lambda t: (L * w + t) * n + k
            else:
                idx = lambda t: (t * w + L) * n + k
            s = 0
            for t in range(-r, r + 1):
                s += a[idx(clamp(t, 0, ln - 1))]
            for t in range(ln):
                out[idx(t)] = jround(s / win)
                s += a[idx(min(ln - 1, t + r + 1))] - a[idx(max(0, t - r))]
    return out


def gaussian(a, w, h, n, radius):
    r = max(0, jround(radius / math.sqrt(3)))
    if r < 1:
        return bytearray(a)
    o = a
    for _ in range(3):
        o = box_pass(o, w, h, n, r, True)
        o = box_pass(o, w, h, n, r, False)
    return o


def screen(c, l):
    return 255 - (255 - c) * (1 - clamp(l, 0, 1))


def flare(a, w, h, n, amt, seed):
    out = bytearray(a)
    R = max(w, h)
    fx = w * (.18 + .3 * hash2(1, 2, seed)); fy = h * (.1 + .2 * hash2(3, 4, seed))
    cx = w / 2; cy = h / 2; k = amt / 100
    ghosts = [(-.35, .05, (.5, .8, 1)), (.35, .03, (1, .6, .3)), (.6, .07, (.4, 1, .6)), (.9, .04, (.8, .5, 1)), (1.3, .1, (.3, .6, 1))]
    for y in range(h):
        for x in range(w):
            i = (y * w + x) * n
            if n > 3 and a[i + 3] == 0:
                continue
            dx = x - fx; dy = y - fy; d = math.hypot(dx, dy)
            r = g = b = 0
            core = math.exp(-((d / (R * .05)) ** 2)); glow = math.exp(-d / (R * .18)) * .45
            ring = math.exp(-(((d - R * .22) / (R * .006)) ** 2)) * .18
            streak = math.exp(-((dy / (R * .004)) ** 2)) * math.exp(-abs(dx) / (R * .5)) * .7
            r += core + glow * 1 + ring * .9 + streak * .6
            g += core + glow * .75 + ring * .7 + streak * .8
            b += core + glow * .45 + ring * 1 + streak * 1
            for t, s, c in ghosts:
                gx = fx + (cx - fx) * 2 * t; gy = fy + (cy - fy) * 2 * t
                gd = math.hypot(x - gx, y - gy) / (R * s)
                e = .16 * (1 - gd * gd * gd) if gd < 1 else 0
                r += e * c[0]; g += e * c[1]; b += e * c[2]
            out[i] = u8(screen(a[i], r * k))
            if n > 1: out[i + 1] = u8(screen(a[i + 1], g * k))
            if n > 2: out[i + 2] = u8(screen(a[i + 2], b * k))
    return out


def bloom(a, w, h, n, amt):
    bright = bytearray(len(a))
    for i in range(0, len(a), n):
        l = .2126 * a[i] + .7152 * a[i + 1] + .0722 * a[i + 2]
        t = clamp((l - 150) / 105, 0, 1)
        for k in range(min(3, n)):
            bright[i + k] = u8(a[i + k] * t)
        if n > 3:
            bright[i + 3] = a[i + 3]
    bl = gaussian(bright, w, h, n, max(w, h) * .012 * (.5 + amt / 50))
    out = bytearray(a)
    k = amt / 100 * 1.4
    for i in range(0, len(a), n):
        for c in range(min(3, n)):
            out[i + c] = u8(screen(a[i + c], bl[i + c] / 255 * k))
    return out


def chroma(a, w, h, n, amt):
    out = bytearray(a)
    cx = w / 2; cy = h / 2; R = math.hypot(cx, cy); s = amt / 100 * .012
    if n < 3:
        return out
    for y in range(h):
        for x in range(w):
            i = (y * w + x) * n
            dx = x - cx; dy = y - cy
            f = math.hypot(dx, dy) / R
            sx1 = clamp(jround(x + dx * s * f), 0, w - 1); sy1 = clamp(jround(y + dy * s * f), 0, h - 1)
            sx2 = clamp(jround(x - dx * s * f), 0, w - 1); sy2 = clamp(jround(y - dy * s * f), 0, h - 1)
            out[i] = a[(sy1 * w + sx1) * n]
            out[i + 2] = a[(sy2 * w + sx2) * n + 2]
    return out


def vignette(a, w, h, n, amt):
    out = bytearray(a)
    cx = w / 2; cy = h / 2; R = math.hypot(cx, cy); k = amt / 100 * .85
    for y in range(h):
        for x in range(w):
            i = (y * w + x) * n
            t = clamp((math.hypot(x - cx, y - cy) / R - .35) / .65, 0, 1)
            f = 1 - k * t * t * (3 - 2 * t)
            for c in range(min(3, n)):
                out[i + c] = u8(jround(a[i + c] * f))
    return out


def grain(a, w, h, n, amt, seed):
    out = bytearray(a)
    s = amt * .5
    for y in range(h):
        for x in range(w):
            i = (y * w + x) * n
            v = (hash2(x, y, seed) + hash2(x, y, seed + 7) - 1) * s
            for c in range(min(3, n)):
                out[i + c] = clamp(jround(a[i + c] + v), 0, 255)
    return out


def apply(src, w, h, n, fx, seed):
    a = src

    def on(k):
        return fx.get(k) and fx[k].get('on') and fx[k].get('amount', 0) > 0
    if on('blur'): a = gaussian(a, w, h, n, fx['blur']['amount'] / 100 * max(w, h) * .02)
    if on('bloom'): a = bloom(a, w, h, n, fx['bloom']['amount'])
    if on('flare'): a = flare(a, w, h, n, fx['flare']['amount'], seed)
    if on('chroma'): a = chroma(a, w, h, n, fx['chroma']['amount'])
    if on('vignette'): a = vignette(a, w, h, n, fx['vignette']['amount'])
    if on('grain'): a = grain(a, w, h, n, fx['grain']['amount'], seed)
    return a
