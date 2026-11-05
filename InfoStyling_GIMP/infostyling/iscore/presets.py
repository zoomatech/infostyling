"""One-click shortcut settings (port of core/presets.js)."""
from . import layout, dense, codec

SOCIAL_CELLS = [16, 20, 24, 28, 32, 40]
SMALL_CELL = 12
SHARE_SIDE = 2048
MIN_SHARED_CELL = 8


def social_cell(w, h):
    """Smallest carrier cell that still spans ~8 px after a platform resizes the long side to 2048."""
    L = max(w, h)
    if L <= SHARE_SIDE:
        return SMALL_CELL
    for c in SOCIAL_CELLS:
        if c * SHARE_SIDE / L >= MIN_SHARED_CELL:
            return c
    return SOCIAL_CELLS[-1]


def book_plan(w, h, n, text, slot_count=None, progress=None):
    """Fewest bits per channel (start at 1, invisible) that hold the compressed text."""
    slots = w * h * min(3, n) if slot_count is None else slot_count
    q = dense.pack(text, progress)
    raw = q['raw']; data = q['data']
    for bpc in range(1, 5):
        cap = dense.capacity_bytes(slots, bpc)
        if len(data) <= cap:
            return {'bpc': bpc, 'cap': cap, 'stored': len(data), 'raw': len(raw)}
    return {'bpc': 0, 'cap': dense.capacity_bytes(slots, 4), 'stored': len(data), 'raw': len(raw)}
