"""Ed25519 signatures (RFC 8032), pure Python, compatible with TweetNaCl's nacl.sign as used by the
Photoshop and Chrome plugins. Key pair: secret key = 32-byte seed followed by the 32-byte public key."""
import hashlib

p = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
d = -121665 * pow(121666, p - 2, p) % p
SQRT_M1 = pow(2, (p - 1) // 4, p)


def _sha512(b):
    return hashlib.sha512(b).digest()


def _add(P, Q):
    X1, Y1, Z1, T1 = P; X2, Y2, Z2, T2 = Q
    A = (Y1 - X1) * (Y2 - X2) % p
    B = (Y1 + X1) * (Y2 + X2) % p
    C = 2 * T1 * T2 * d % p
    D = 2 * Z1 * Z2 % p
    E = B - A; F = D - C; G = D + C; H = B + A
    return (E * F % p, G * H % p, F * G % p, E * H % p)


def _mul(s, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _equal(P, Q):
    if (P[0] * Q[2] - Q[0] * P[2]) % p:
        return False
    return (P[1] * Q[2] - Q[1] * P[2]) % p == 0


def _recover_x(y, sign):
    if y >= p:
        return None
    x2 = (y * y - 1) * pow(d * y * y + 1, p - 2, p)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (p + 3) // 8, p)
    if (x * x - x2) % p:
        x = x * SQRT_M1 % p
    if (x * x - x2) % p:
        return None
    if (x & 1) != sign:
        x = p - x
    return x


_gy = 4 * pow(5, p - 2, p) % p
_gx = _recover_x(_gy, 0)
G = (_gx, _gy, 1, _gx * _gy % p)


def _compress(P):
    zinv = pow(P[2], p - 2, p)
    x = P[0] * zinv % p; y = P[1] * zinv % p
    return int.to_bytes(y | ((x & 1) << 255), 32, 'little')


def _decompress(s):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, 'little')
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % p)


def _expand(seed):
    h = _sha512(seed)
    a = int.from_bytes(h[:32], 'little')
    a &= (1 << 254) - 8
    a |= (1 << 254)
    return a, h[32:]


def public_from_seed(seed):
    a, _ = _expand(seed)
    return _compress(_mul(a, G))


def keypair_from_seed(seed):
    pk = public_from_seed(seed)
    return {'publicKey': pk, 'secretKey': bytes(seed) + pk}


def keypair_from_secret(sk):
    sk = bytes(sk)
    if len(sk) != 64:
        raise ValueError("bad secret key size")
    return {'publicKey': sk[32:], 'secretKey': sk}


def sign_detached(msg, sk):
    seed = bytes(sk[:32]); pk = bytes(sk[32:])
    a, prefix = _expand(seed)
    r = int.from_bytes(_sha512(prefix + msg), 'little') % L
    R = _compress(_mul(r, G))
    h = int.from_bytes(_sha512(R + pk + msg), 'little') % L
    s = (r + h * a) % L
    return R + int.to_bytes(s, 32, 'little')


def verify_detached(msg, sig, pk):
    if len(sig) != 64 or len(pk) != 32:
        return False
    A = _decompress(bytes(pk))
    if not A:
        return False
    Rs = bytes(sig[:32])
    R = _decompress(Rs)
    if not R:
        return False
    s = int.from_bytes(sig[32:], 'little')
    if s >= L:
        return False
    h = int.from_bytes(_sha512(Rs + bytes(pk) + msg), 'little') % L
    return _equal(_mul(s, G), _add(R, _mul(h, A)))


def sha512(b):
    return _sha512(bytes(b))
