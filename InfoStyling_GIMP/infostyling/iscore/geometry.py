"""Rotation, perspective and lens corrections for reading photos of prints (port of core/geometry.js)."""
import math
from .jsm import jround, clamp


def bilinear(src, w, h, c, x, y, ch):
    if x < 0 or y < 0 or x > w - 1 or y > h - 1:
        return 0 if (ch == 3 and c > 3) else 127
    x0 = math.floor(x); y0 = math.floor(y)
    x1 = min(w - 1, x0 + 1); y1 = min(h - 1, y0 + 1)
    tx = x - x0; ty = y - y0
    k = min(ch, c - 1)
    a = src[(y0 * w + x0) * c + k]; b = src[(y0 * w + x1) * c + k]
    d = src[(y1 * w + x0) * c + k]; e = src[(y1 * w + x1) * c + k]
    ab = a + (b - a) * tx; de = d + (e - d) * tx
    return ab + (de - ab) * ty


def _px(v):
    v = jround(v)
    return 0 if v < 0 else 255 if v > 255 else v


def rotate_quarter(src, w, h, c, t):
    t %= 4
    if t == 0:
        return bytearray(src), w, h
    nw = h if t % 2 else w; nh = w if t % 2 else h
    out = bytearray(nw * nh * c)
    for y in range(h):
        for x in range(w):
            if t == 1:
                dx = h - 1 - y; dy = x
            elif t == 2:
                dx = w - 1 - x; dy = h - 1 - y
            else:
                dx = y; dy = w - 1 - x
            si = (y * w + x) * c; di = (dy * nw + dx) * c
            out[di:di + c] = src[si:si + c]
    return out, nw, nh


def rotate_image(src, w, h, c, deg):
    a = deg * math.pi / 180; ca = math.cos(a); sa = math.sin(a)
    nw = max(1, math.ceil(abs(w * ca) + abs(h * sa))); nh = max(1, math.ceil(abs(w * sa) + abs(h * ca)))
    out = bytearray(nw * nh * c)
    cx = (w - 1) / 2; cy = (h - 1) / 2; ocx = (nw - 1) / 2; ocy = (nh - 1) / 2
    for y in range(nh):
        for x in range(nw):
            dx = x - ocx; dy = y - ocy
            sx = ca * dx + sa * dy + cx; sy = -sa * dx + ca * dy + cy
            i = (y * nw + x) * c
            for ch in range(c):
                out[i + ch] = _px(bilinear(src, w, h, c, sx, sy, ch))
    return out, nw, nh


def solve_linear(A, b):
    n = len(b)
    M = [r[:] + [b[i]] for i, r in enumerate(A)]
    for col in range(n):
        pivot = col
        for r in range(col + 1, n):
            if abs(M[r][col]) > abs(M[pivot][col]):
                pivot = r
        if abs(M[pivot][col]) < 1e-12:
            raise ValueError("Degenerate quadrilateral.")
        M[col], M[pivot] = M[pivot], M[col]
        d = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= d
        for r in range(n):
            if r != col:
                f = M[r][col]
                for j in range(col, n + 1):
                    M[r][j] -= f * M[col][j]
    return [r[n] for r in M]


def homography_rect_to_quad(w, h, q):
    src = [(0, 0), (w - 1, 0), (w - 1, h - 1), (0, h - 1)]
    A = []; b = []
    for i in range(4):
        x, y = src[i]; X, Y = q[i]
        A.append([x, y, 1, 0, 0, 0, -x * X, -y * X]); b.append(X)
        A.append([0, 0, 0, x, y, 1, -x * Y, -y * Y]); b.append(Y)
    z = solve_linear(A, b)
    return z + [1]


def perspective_rectify(src, w, h, c, quad, tw=0, th=0):
    dist = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])
    aw = jround((dist(quad[0], quad[1]) + dist(quad[3], quad[2])) / 2)
    ah = jround((dist(quad[0], quad[3]) + dist(quad[1], quad[2])) / 2)
    tw = max(64, jround(tw or aw)); th = max(64, jround(th or ah))
    H = homography_rect_to_quad(tw, th, quad)
    out = bytearray(tw * th * c)
    for y in range(th):
        for x in range(tw):
            z = H[6] * x + H[7] * y + 1
            sx = (H[0] * x + H[1] * y + H[2]) / z; sy = (H[3] * x + H[4] * y + H[5]) / z
            i = (y * tw + x) * c
            for ch in range(c):
                out[i + ch] = _px(bilinear(src, w, h, c, sx, sy, ch))
    return out, tw, th


def radial_undistort(src, w, h, c, k1, k2):
    k1 = float(k1 or 0); k2 = float(k2 or 0)
    if abs(k1) < 1e-10 and abs(k2) < 1e-10:
        return bytearray(src), w, h
    out = bytearray(len(src))
    cx = (w - 1) / 2; cy = (h - 1) / 2; scale = max(cx, cy)
    for y in range(h):
        for x in range(w):
            nx = (x - cx) / scale; ny = (y - cy) / scale
            r2 = nx * nx + ny * ny; f = 1 + k1 * r2 + k2 * r2 * r2
            sx = cx + nx * f * scale; sy = cy + ny * f * scale
            i = (y * w + x) * c
            for ch in range(c):
                out[i + ch] = _px(bilinear(src, w, h, c, sx, sy, ch))
    return out, w, h
