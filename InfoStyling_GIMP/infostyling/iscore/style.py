"""The seven painterly looks (Engraving, Impressionist, Cubist, Surreal, Pen sketch, Stipple, Fractal),
port of core/style.js. Each pixel is redrawn by the look; the payload bit of its cell tilts the drawing."""
import math
from .jsm import jround, clamp
from .noise import hash2, value_noise, luminance, hue_rotate

M32 = 0xFFFFFFFF


def _fract(x):
    return x - math.floor(x)


def style_gate(style, x, y, cx, cy, p, n, sign, k):
    if style == 'engraving':
        return 1 if _fract((k['v'] + n * p['roughness'] * .15) / k['spacing']) < k['width'] / k['spacing'] else .12
    if style == 'impressionist':
        cs = p['cellSize']
        stroke = math.sin(k['u'] / max(2, cs * .22) + n * 4.5 + sign * .35)
        q = max(3, cs * .35)
        blob = value_noise(x / q, y / q, p['seed'] + 77)
        return clamp(.35 + .45 * abs(stroke) + .35 * max(0, blob), .1, 1)
    if style == 'cubist':
        cs = p['cellSize']
        lx = (x % cs) / cs; ly = (y % cs) / cs
        diag = lx + ly + n * .12 + sign * .04
        return 1 if _fract(diag * 2) < .22 or abs(lx - ly) < .045 else .35
    if style == 'surreal':
        cs = p['cellSize']
        return clamp(.45 + .4 * math.sin((k['u'] + .6 * cs * n) / max(2, cs * .18)), .08, 1)
    if style == 'penskip':
        return 1 if _fract((k['u'] + n * p['roughness'] * .35) / max(2, k['spacing'] * .75)) < .06 + .28 * k['density'] else .16
    if style == 'stipple':
        wd = max(1, k['width'])
        return 1 if hash2(math.floor(x / wd), math.floor(y / wd), p['seed'] + cx * 17 + cy * 31) < k['density'] * .42 else .1
    return clamp(.3 + .7 * abs(n), .08, 1) if style == 'fractal' else .5


def render(src, width, height, components, bits, p, progress=None):
    out = bytearray(len(src))
    cell = max(4, jround(p['cellSize']))
    cols = -(-width // cell)
    strength = clamp(p['strength'] / 100, 0, 1)
    contrast = clamp(p['contrast'] / 100, 0, 1)
    luma = clamp(p['luminance'] / 100, 0, 1)
    hue = clamp(p['hue'] / 100, 0, 1)
    inv = clamp(p['inversion'] / 100, 0, 1)
    carrier = clamp(p['carrier'] / 100, 0, 1)
    wamp = max(0, p['wobble']) * strength
    wscale = max(2, p['wobbleScale'])
    pbias = clamp(p['payloadWobble'] / 100, 0, 1)
    oct_ = clamp(jround(p['octaves']), 1, 7)
    pers = clamp(p['persistence'], .1, .95)
    lac = clamp(p['lacunarity'], 1.1, 4)
    angle = p['orientation'] * math.pi / 180
    nx = -math.sin(angle); ny = math.cos(angle)
    ca = math.cos(angle); sa = math.sin(angle)
    style = p['style']
    seed = p['seed']
    density = clamp(p['density'] / 100, .02, 1)
    lw = max(.6, p['lineWidth'])
    spacing = max(lw + 1, p['cellSize'] * (.12 + (1 - density) * .35))
    k = {'density': density, 'width': lw, 'spacing': spacing, 'u': 0.0, 'v': 0.0}
    nb = len(bits)
    C = components
    floor = math.floor
    # Octave frequencies and weights, as fbm() uses them.
    octs = []
    amp = 1.0; freq = 1.0; norm = 0.0
    for i in range(oct_):
        octs.append((freq, amp, i * 1013))
        norm += amp; amp *= pers; freq *= lac
    w17 = wscale * 1.7
    if style == 'cubist':
        qcub = max(2, cell * .18 * strength)
    for y in range(height):
        cy = y // cell
        for x in range(width):
            cx = x // cell
            ci = cy * cols + cx
            bit = 1 if bits[ci % nb] else 0
            sign = 1 if bit else -1
            # fbm(x/wscale, y/wscale, seed+ci*3)
            fx = x / wscale; fy = y / wscale; sd = seed + ci * 3
            total = 0.0
            for fq, am, so in octs:
                px_ = fx * fq; py_ = fy * fq
                xi = floor(px_); yi = floor(py_)
                tx = px_ - xi; ty = py_ - yi
                tx = tx * tx * (3 - 2 * tx); ty = ty * ty * (3 - 2 * ty)
                s3 = ((sd + so) * 1442695041)
                ax = xi * 374761393; ay = yi * 668265263
                bx = ax + 374761393; by = ay + 668265263
                hv = (ax + ay + s3) & M32; hv ^= hv >> 13; hv = (hv * 1274126177) & M32; hv ^= hv >> 16; a = hv / 4294967295
                hv = (bx + ay + s3) & M32; hv ^= hv >> 13; hv = (hv * 1274126177) & M32; hv ^= hv >> 16; b = hv / 4294967295
                hv = (ax + by + s3) & M32; hv ^= hv >> 13; hv = (hv * 1274126177) & M32; hv ^= hv >> 16; c = hv / 4294967295
                hv = (bx + by + s3) & M32; hv ^= hv >> 13; hv = (hv * 1274126177) & M32; hv ^= hv >> 16; d = hv / 4294967295
                ab = a + (b - a) * tx; cd = c + (d - c) * tx
                total += ((ab + (cd - ab) * ty) * 2 - 1) * am
            n = total / norm if norm else 0
            wobble = n * wamp * (1 + sign * .45 * pbias)
            sx = x + nx * wobble; sy = y + ny * wobble
            if style == 'surreal':
                from .noise import fbm
                w2 = fbm(x / w17, y / w17, seed + 991, oct_, pers, lac)
                sx += ca * w2 * wamp * .65; sy += sa * w2 * wamp * .65
            elif style == 'cubist':
                if qcub > 2.1:
                    sx = jround(sx / qcub) * qcub; sy = jround(sy / qcub) * qcub
            # sampleNearest
            xs = jround(sx); ys = jround(sy)
            xs = 0 if xs < 0 else width - 1 if xs > width - 1 else xs
            ys = 0 if ys < 0 else height - 1 if ys > height - 1 else ys
            si = (ys * width + xs) * C
            r = src[si]; g = src[si + 1]; b = src[si + 2]
            al = src[si + 3] if C > 3 else 255
            i = (y * width + x) * C
            if al == 0:
                out[i] = r; out[i + 1] = g; out[i + 2] = b
                if C > 3: out[i + 3] = al
                continue
            if style in ('engraving', 'impressionist', 'surreal', 'penskip'):
                k['u'] = x * ca + y * sa
                k['v'] = -x * sa + y * ca
            gate = style_gate(style, x, y, cx, cy, p, n, sign, k)
            st = strength * gate
            y0 = .2126 * r + .7152 * g + .0722 * b
            cg = 1 + sign * contrast * st * .42
            r = y0 + (r - y0) * cg; g = y0 + (g - y0) * cg; b = y0 + (b - y0) * cg
            bias = sign * (2 + 18 * carrier) * strength * (.45 + .55 * gate) + sign * 10 * luma * st
            r += bias; g += bias; b += bias
            if inv > 0:
                t = inv * st * (.42 if bit else .13)
                r = r + (255 - r - r) * t; g = g + (255 - g - g) * t; b = b + (255 - b - b) * t
            r, g, b = hue_rotate(r, g, b, sign * hue * st * .55 + n * hue * strength * .22)
            if style == 'stipple' and gate > .7:
                m = 14 + 48 * strength
                if bit:
                    r -= m; g -= m; b -= m
                else:
                    r += m * .72; g += m * .72; b += m * .72
            elif style == 'penskip' and gate > .7:
                t = 238 if bit else 25
                m = .08 + .34 * strength
                r = r + (t - r) * m; g = g + (t - g) * m; b = b + (t - b) * m
            elif style == 'engraving' and gate > .7:
                kk = 12 + 42 * strength
                r -= kk; g -= kk; b -= kk
            v = jround(r); out[i] = 0 if v < 0 else 255 if v > 255 else v
            v = jround(g); out[i + 1] = 0 if v < 0 else 255 if v > 255 else v
            v = jround(b); out[i + 2] = 0 if v < 0 else 255 if v > 255 else v
            if C > 3: out[i + 3] = al
        if progress and not (y & 31):
            progress(y / height)
    return {'pixels': out}
