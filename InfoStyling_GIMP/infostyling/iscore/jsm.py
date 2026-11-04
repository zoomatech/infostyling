"""Small helpers that reproduce JavaScript number behaviour exactly, so this port
writes and reads the same bits as the Photoshop plugin and the Chrome plugin."""
import math
M32 = 0xFFFFFFFF


def jround(x):
    """JavaScript Math.round: halves round up (towards +infinity)."""
    f = math.floor(x)
    return f + 1 if x - f >= 0.5 else f


def imul(a, b):
    """Math.imul as an unsigned 32-bit result."""
    return ((a & M32) * (b & M32)) & M32


def s32(v):
    v &= M32
    return v - 0x100000000 if v & 0x80000000 else v


def clamp(v, a, b):
    return a if v < a else b if v > b else v


def u8(v):
    """Store a number into a JavaScript Uint8Array (truncate, wrap)."""
    if v != v or v in (math.inf, -math.inf):
        return 0
    return int(v) & 255
