"""One-click looks: what each tile does, how much text it holds, and its preview (port of core/looks.js)."""
from .config import PRESETS
from . import brightq, codec, layout, style, carrier, glyph, chroma, tract, presets, dense

LOOKS = [
    {'id': "none", 'label': "Invisible", 'note': "Photo stays as it is"},
    {'id': "glyph", 'label': "Glyph hatch", 'note': "Diagonal strokes", 'cell': 12},
    {'id': "colorpop", 'label': "Color Pop", 'note': "Bold color tiles", 'cell': 20},
    {'id': "tract", 'label': "Tract ink", 'note': "Black ink comic", 'cell': 8},
    {'id': "engraving", 'label': "Engraving", 'note': "Banknote lines"},
    {'id': "impressionist", 'label': "Impressionist", 'note': "Painterly strokes"},
    {'id': "cubist", 'label': "Cubist", 'note': "Faceted blocks"},
    {'id': "surreal", 'label': "Surreal", 'note': "Melting waves"},
    {'id': "penskip", 'label': "Pen sketch", 'note': "Skipping pen lines"},
    {'id': "stipple", 'label': "Stipple", 'note': "Ink dots"},
    {'id': "fractal", 'label': "Fractal", 'note': "Swirling noise"},
]


def by_id(i):
    for l in LOOKS:
        if l['id'] == i:
            return l
    return None


def art_look(i):
    return i in ("glyph", "colorpop", "tract")


def robust_cell(look, w, h):
    return look.get('cell') or presets.social_cell(w, h)


def share_space(i, w, h):
    return brightq.capacity_bytes(w, h) if i == "none" else layout.blind_capacity_bytes(w, h, robust_cell(by_id(i), w, h))


def plan(i, w, h, text, memo, route, progress=None):
    look = by_id(i)
    if memo.get('bytes') is None:
        memo['bytes'] = len(codec.utf8_encode(text or ""))
    nbytes = memo['bytes']
    if not look or not nbytes:
        return {'look': look, 'bytes': nbytes, 'route': None}
    cell = robust_cell(look, w, h)
    if route == "share":
        cap = share_space(i, w, h)
        if memo.get('stored') is None:
            memo['stored'] = codec.robust_stored_bytes(text)
        return {'look': look, 'bytes': nbytes, 'route': route, 'cell': cell, 'cap': cap, 'stored': memo['stored'], 'fits': memo['stored'] <= cap}
    if memo.get('dense') is None:
        memo['dense'] = presets.book_plan(w, h, 3, text, None, progress)
    b = memo['dense']
    return {'look': look, 'bytes': nbytes, 'route': "full", 'cell': cell, 'bpc': b['bpc'], 'cap': b['cap'], 'stored': b['stored'], 'fits': bool(b['bpc'])}


def profile(i, cell, seed):
    p = dict(PRESETS.get(i) or PRESETS['engraving'])
    p.update({'style': i, 'seed': seed, 'blindCell': cell, 'fx': {}})
    if i == "glyph": p['glyphCell'] = cell
    if i == "colorpop": p['colorCell'] = cell
    if i == "tract": p['tractCell'] = cell
    return p


def render_look(i, src, w, h, n, bits, cell, seed, progress=None):
    p = profile(i, cell, seed)
    if i == "glyph": return glyph.render_glyphs(src, w, h, n, bits, {'glyphCell': cell, 'seed': seed}, progress)['pixels']
    if i == "colorpop": return chroma.render_color_pop(src, w, h, n, bits, {'colorCell': cell, 'seed': seed}, progress)['pixels']
    if i == "tract": return tract.render_tract(src, w, h, n, bits, {'tractCell': cell, 'seed': seed}, progress)['pixels']
    if i == "none": return bytearray(src)
    return style.render(src, w, h, n, codec.frame_bits("InfoStyling preview"), p, progress)['pixels']


def preview(i, src, w, h, n, full_w, full_h, seed):
    if i == "none":
        try:
            return brightq.embed(src, w, h, n, "InfoStyling preview")['pixels']
        except Exception:
            return bytearray(src)
    look = by_id(i)
    cell = robust_cell(look, full_w, full_h)
    bits = codec.v3_frame_bits("InfoStyling preview", {'style': "none" if art_look(i) else i, 'blindCell': cell, 'seed': seed})
    art = render_look(i, src, w, h, n, bits, cell, seed)
    return art if art_look(i) else carrier.apply_blind_carrier(art, w, h, n, bits, profile(i, cell, seed))['pixels']


def footprint(i, w, h, stored, route):
    if route == "full":
        avail = (dense.HEADER + dense.capacity_bytes(w * h * 3, 4)) * 8
        takes = (dense.HEADER + stored) * 8
    elif i == "none":
        avail = brightq.slot_count(w, h)
        takes = brightq.coded_bits(stored)
    else:
        avail = codec.v3_frame_bit_length(share_space(i, w, h))
        takes = codec.v3_frame_bit_length(stored)
    return {'avail': -(-avail // 8), 'takes': -(-takes // 8), 'over': takes > avail,
            'short': -(-max(0, takes - avail) // 8), 'left': max(0, avail - takes) // 8}
