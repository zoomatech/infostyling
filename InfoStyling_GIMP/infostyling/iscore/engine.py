"""What the Apply filter and Read buttons do, with no GIMP code in it, so it can be tested on its own.
Same steps as the Photoshop plugin's app.js: draw the look, sign, hide the text, read it back."""
from . import codec, dense, brightq, glyph, chroma, tract, carrier, fractional, decoder, effects, looks, seal, style, presets, pack
from .jsm import jround

ART = ("glyph", "colorpop", "tract")


def blend(orig, styled, c, mask):
    """Mixes the styled pixels into the original by a 0-255 selection mask (one byte per pixel)."""
    if mask is None:
        return styled
    out = bytearray(len(styled))
    m = 0
    for i in range(0, len(styled), c):
        t = mask[m] / 255
        for k in range(c):
            out[i + k] = jround(orig[i + k] * (1 - t) + styled[i + k] * t)
        m += 1
    return out


def carrier_art(data, w, h, n, frame, p, progress=None):
    if p['style'] == "tract":
        return tract.render_tract(data, w, h, n, frame, {'tractCell': p['blindCell'], 'seed': p['seed']}, progress)['pixels']
    if p['style'] == "glyph":
        return glyph.render_glyphs(data, w, h, n, frame, {'glyphCell': p['blindCell'], 'seed': p['seed']}, progress)['pixels']
    return chroma.render_color_pop(data, w, h, n, frame, {'colorCell': p['blindCell'], 'seed': p['seed']}, progress)['pixels']


def draw_look(text, plain, p, src, w, h, n, mask, progress=None):
    """The look drawn on the pixels, before the text is hidden. Full resolution draws its visible art from the start of the plain text."""
    data = src
    st = p['style']
    if st in ART:
        if p['mode'] == "dense":
            data = carrier_art(data, w, h, n, codec.v3_frame_bits(plain[:64], {'style': "none", 'blindCell': p['blindCell'], 'seed': p['seed']}), p, progress)
    elif st != "none":
        vis = style.render(src, w, h, n, codec.frame_bits(plain[:64] if p['mode'] == "dense" else text), p, progress)
        data = blend(src, vis['pixels'], n, mask)
    return effects.apply(data, w, h, n, p.get('fx') or {}, p['seed'])


def hide(data, text, p, w, h, n, progress=None):
    """Hides the text in the drawn pixels; returns the encoder's result with the new pixels."""
    if p['mode'] == "dense":
        return dense.embed(data, w, h, n, text, p['bpc'])
    if p['style'] == "none":
        return brightq.embed(data, w, h, n, text, progress=progress)
    frame = codec.v3_frame_bits(text, {'style': p['style'], 'blindCell': p['blindCell'], 'seed': p['seed']})
    if p['style'] in ART:
        return {'pixels': carrier_art(data, w, h, n, frame, p, progress)}
    return carrier.apply_blind_carrier(data, w, h, n, frame, p, progress)


def sized(text, name, keys):
    """Text plus a stand-in seal of the same length, for measuring space; the plain text when not signing."""
    return seal.placeholder(text, name, keys) if name and text else text


def encode(src, w, h, n, plain, look_id, route, seed, fx=None, sign=None, mask=None, step=None):
    """Draws the look and hides plain in it. sign = (name, keys) or None. step(label, fraction) reports progress.
    Returns {'pixels', 'text' (what was hidden, seal included), 'q' (the plan), 'info'}."""
    def prog(label):
        return (lambda f: step(label, f)) if step else None
    name = sign[0] if sign else ""
    keys = sign[1] if sign else None
    sz = sized(plain, name, keys)
    q = looks.plan(look_id, w, h, sz, {}, route, prog("Compressing your text"))
    if not q['fits']:
        f = looks.footprint(look_id, w, h, q['stored'], route)
        png = route == "full"
        lab = looks.by_id(look_id)['label']
        raise ValueError(f"Too long: your text takes {f['takes']:,} bytes and {lab} has {f['avail']:,} bytes available at "
                         f"{'Full resolution (PNG)' if png else 'Shareable (JPEG)'}.{' Use a larger image.' if png else ' Shorten it, or press Full resolution (PNG).'}")
    p = looks.profile(look_id, q['cell'], seed)
    p['mode'] = "dense" if route == "full" else "robust"
    p['bpc'] = q.get('bpc') or 2
    p['fx'] = fx or {}
    text = plain
    if sign:
        if p['mode'] == "dense" or p['style'] == "none":
            fp = seal.fingerprint(draw_look(plain, plain, p, src, w, h, n, mask, prog("Drawing the look")), w, h, n)
        else:
            ph = seal.placeholder(plain, name, keys)
            first = hide(draw_look(ph, plain, p, src, w, h, n, mask, prog("Drawing the look for the seal")), ph, p, w, h, n, prog("Measuring the seal"))
            fp = seal.fingerprint(first['pixels'], w, h, n)
        text = seal.sign(plain, name, keys, fp)
    drawn = draw_look(text, plain, p, src, w, h, n, mask, prog("Drawing the look"))
    e = hide(drawn, text, p, w, h, n, prog("Hiding the text"))
    return {'pixels': e['pixels'], 'text': text, 'q': q, 'p': p, 'info': e}


def read_known(px, w, h, n, look_id, route, cell):
    """Reads back an image this plugin just made, knowing its look: fast, no searching."""
    if route == "full":
        return dense.extract(px, w, h, n)
    if look_id == "none":
        return brightq.extract(px, w, h, n)
    if look_id in ("glyph", "tract"):
        return glyph.decode_glyphs(px, w, h, n, {'cell': cell})
    if look_id == "colorpop":
        return chroma.decode_color_pop(px, w, h, n, {'cell': cell})
    g = carrier.extract_grid(px, w, h, n, cell)
    return carrier.decode_grid(g, {'maxPilotErrors': 10})


def _with_cell(d, c):
    if d:
        d.update({'cell': c, 'offX': 0, 'offY': 0})
    return d


def any_decode(px, w, h, n, opts=None, step=None):
    """Reads hidden text from any image, the same channels and order as the Photoshop plugin. Images straight
    from InfoStyling are tried first at their known mark sizes, which is quick; then the full searches for resized
    or cropped images, which take longer in GIMP."""
    o = opts or {}

    def say(t):
        if step:
            step(t, None)
    if not o.get('after_brightq'):
        try:
            hc = dense.extract(px, w, h, n)
            if hc:
                hc['kind'] = "Full resolution (high capacity)"
                return hc
        except Exception:
            pass
        say("Looking for the Invisible look…")
        try:
            bq = brightq.extract(px, w, h, n)
            if bq:
                bq['kind'] = "Invisible (brightness)"
                return bq
        except Exception:
            pass
    say("Looking for marks at the sizes InfoStyling uses…")
    quick = [("Glyph hatch", lambda: glyph.decode_glyphs(px, w, h, n, {'cell': 12})),
             ("Tract ink", lambda: glyph.decode_glyphs(px, w, h, n, {'cell': 8})),
             ("Color Pop", lambda: chroma.decode_color_pop(px, w, h, n, {'cell': 20}))]
    sc = presets.social_cell(w, h)
    for c in [sc] + [x for x in (12, 16, 20, 24, 28, 32, 40) if x != sc]:
        quick.append(("ISB3 robust", lambda c=c: _with_cell(carrier.decode_grid(carrier.extract_grid(px, w, h, n, c), {'maxPilotErrors': 10}), c)))
    for kind, fn in quick:
        try:
            d = fn()
            if d:
                d['kind'] = kind if kind != "ISB3 robust" else "ISB3 robust"
                return d
        except Exception:
            pass
    if o.get('quick'):
        return None
    say("Searching resized images (slow)…")
    try:
        d = fractional.decode_fractional(px, w, h, n, {'maxPilotErrors': 10})
        if d:
            d['kind'] = "ISB3 robust"
            return d
    except Exception:
        pass
    say("Searching Glyph hatch and Tract ink at every size (slow)…")
    try:
        d = glyph.decode_glyphs(px, w, h, n, {})
        if d:
            d['kind'] = "Glyph hatch"
            return d
    except Exception:
        pass
    say("Searching Color Pop at every size (slow)…")
    try:
        d = chroma.decode_color_pop(px, w, h, n, {})
        if d:
            d['kind'] = "Color Pop"
            return d
    except Exception:
        pass
    say("Searching the ISB3 carrier (slow)…")
    try:
        d = decoder.decode_blind(px, w, h, n, {'deep': o.get('deep', True), 'camera': o.get('camera', False), 'rotationHint': o.get('rotationHint', 0)})
        if d:
            d['kind'] = "ISB3 robust"
            return d
    except Exception:
        pass
    return None
