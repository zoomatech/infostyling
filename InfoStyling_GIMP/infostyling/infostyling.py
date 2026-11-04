#!/usr/bin/env python3
# InfoStyling for GIMP 3: hide text inside an image, then read it back.
# Same looks, sizes, compression and signed seal as the InfoStyling Photoshop plugin, so its images are read by
# the InfoStyling Chrome plugin and by the Photoshop plugin. Opens from Filters > InfoStyling…
import os, sys, json, time, traceback
import gi
gi.require_version('Gimp', '3.0')
gi.require_version('GimpUi', '3.0')
gi.require_version('Gegl', '0.4')
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gimp, GimpUi, Gegl, GObject, GLib, Gio, Gtk, Gdk, GdkPixbuf, Pango

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from iscore import codec, dense, brightq, glyph, chroma, fractional, decoder, looks, seal, epub, pack, engine, presets, effects as fxmod, config as isconfig

VERSION = "0.13.0"
PROC = "plug-in-infostyling"
FMT = "R'G'B'A u8"
PREVIEW_CHARS = 20000
DECODED_MAX = 5 * 1024 * 1024
TILE_W = 180


def data_dir():
    d = os.path.join(Gimp.directory(), "infostyling")
    os.makedirs(d, exist_ok=True)
    return d


def kb(n):
    if n < 10240:
        return f"{n} bytes"
    return f"{n / 1024:.0f} KB" if n < 1048576 else f"{n / 1024:.1f} KB"


def num(v):
    return f"{v:,}"


# ---------------------------------------------------------------- pixels

def read_pixels(drawable, x, y, w, h):
    buf = drawable.get_buffer()
    data = buf.get(Gegl.Rectangle.new(x, y, w, h), 1.0, FMT, Gegl.AbyssPolicy.CLAMP)
    return bytearray(data)


def write_pixels(layer, data, w, h):
    buf = layer.get_buffer()
    buf.set(Gegl.Rectangle.new(0, 0, w, h), FMT, bytes(data))
    buf.flush()
    layer.update(0, 0, w, h)


def layer_rect(layer):
    r = layer.get_offsets()
    return r[1], r[2], layer.get_width(), layer.get_height()


def source_id(name):
    import re
    m = re.search(r"\[IS5 cell=\d+ src=(\d+)\]", name or "")
    return int(m.group(1)) if m else None


def find_layer(lid):
    try:
        it = Gimp.Item.get_by_id(lid)
        return it if isinstance(it, Gimp.Layer) else None
    except Exception:
        return None


class Area:
    """The part of a layer that is read and written: the whole layer, or the canvas part of a layer that is bigger than the canvas."""
    def __init__(self, image, layer):
        self.image = image; self.layer = layer
        ox, oy, lw, lh = layer_rect(layer)
        W, H = image.get_width(), image.get_height()
        self.lx, self.ly, self.lw, self.lh = ox, oy, lw, lh
        self.canvas = False
        if ox <= 0 and oy <= 0 and ox + lw >= W and oy + lh >= H and (lw > W or lh > H):
            self.x, self.y, self.width, self.height, self.canvas = -ox, -oy, W, H, True
        else:
            self.x, self.y, self.width, self.height = 0, 0, lw, lh

    def fills_canvas(self):
        W, H = self.image.get_width(), self.image.get_height()
        return self.canvas or (self.lx == 0 and self.ly == 0 and self.lw == W and self.lh == H)

    def pixels(self, x=0, y=0, w=None, h=None):
        return read_pixels(self.layer, self.x + x, self.y + y, w or self.width, h or self.height)


def shrink(px, w, h, n, tw, th):
    out = bytearray(tw * th * 3)
    for y in range(th):
        y0 = y * h // th; y1 = max(y0 + 1, (y + 1) * h // th)
        for x in range(tw):
            x0 = x * w // tw; x1 = max(x0 + 1, (x + 1) * w // tw)
            r = g = b = 0.0; c = 0
            for yy in range(y0, y1):
                i = (yy * w + x0) * n
                for xx in range(x0, x1):
                    al = px[i + 3] / 255 if n > 3 else 1
                    r += px[i] * al + 128 * (1 - al); g += px[i + 1] * al + 128 * (1 - al); b += px[i + 2] * al + 128 * (1 - al)
                    c += 1; i += n
            o = (y * tw + x) * 3
            out[o] = int(r / c); out[o + 1] = int(g / c); out[o + 2] = int(b / c)
    return out


# ---------------------------------------------------------------- the panel

class Panel:
    def __init__(self, image, layer):
        self.image = image
        self.start_layer = layer
        self.picked = looks.LOOKS[0]['id']
        self.route = "share"
        self.file_text = None
        self.file_name = None
        self.last_decoded = ""
        self.busy = False
        self.keys = None
        self._ckey = None
        self._pkey = None
        self._pqueue = []
        self.state = {'seed': isconfig.DEFAULT_SEED, 'fx': {}, 'signName': ""}
        self.load_state()
        pack.CACHE_DIR = data_dir()
        self.build()

    # ---- settings
    def state_path(self):
        return os.path.join(data_dir(), "settings.json")

    def load_state(self):
        try:
            with open(self.state_path(), encoding="utf-8") as f:
                q = json.load(f)
            if isinstance(q.get('seed'), int): self.state['seed'] = q['seed']
            if isinstance(q.get('fx'), dict): self.state['fx'] = q['fx']
            if isinstance(q.get('signName'), str): self.state['signName'] = q['signName']
        except Exception:
            pass

    def save_state(self):
        try:
            with open(self.state_path(), "w", encoding="utf-8") as f:
                json.dump(self.state, f)
        except Exception:
            pass

    # ---- small widgets
    def label(self, text="", cls=None, wrap=True, sel=False):
        l = Gtk.Label(label=text, xalign=0)
        l.set_line_wrap(wrap)
        if wrap:
            l.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        l.set_selectable(sel)
        if cls:
            l.get_style_context().add_class(cls)
        return l

    def section(self, title):
        f = Gtk.Frame()
        f.get_style_context().add_class("box")
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        v.set_border_width(8)
        t = self.label(title, "sectionTitle")
        v.pack_start(t, False, False, 0)
        f.add(v)
        self.main.pack_start(f, False, False, 0)
        return v

    def textview(self, rows, editable=True, mono=False):
        tv = Gtk.TextView()
        tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        tv.set_editable(editable)
        if mono:
            tv.set_monospace(True)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_min_content_height(rows * 20)
        sw.set_shadow_type(Gtk.ShadowType.IN)
        sw.add(tv)
        return tv, sw

    def tv_text(self, tv):
        b = tv.get_buffer()
        return b.get_text(b.get_start_iter(), b.get_end_iter(), True)

    def css(self):
        p = Gtk.CssProvider()
        p.load_from_data(b"""
        .sectionTitle { font-weight: bold; }
        .small { font-size: 90%; }
        .over { color: #e5484d; font-weight: bold; }
        .space { border: 1px solid rgba(128,128,128,.45); border-radius: 4px; padding: 7px; }
        .space.over { border-color: #e5484d; color: #e5484d; }
        .tile { border: 2px solid rgba(128,128,128,.45); border-radius: 5px; padding: 4px; }
        .tile.picked { border: 3px solid #2680eb; background-color: rgba(38,128,235,.12); }
        .tilename { font-weight: bold; }
        .tilenote { font-size: 85%; }
        .tilespace { font-size: 85%; font-weight: bold; }
        .working { color: #2680eb; font-weight: bold; }
        .ok { color: #2d9d78; font-weight: bold; border: 2px solid #2d9d78; border-radius: 4px; padding: 7px; }
        .bad { color: #e5484d; font-weight: bold; border: 2px solid #e5484d; border-radius: 4px; padding: 7px; }
        .ph { background-color: rgba(128,128,128,.25); }
        """)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def set_cls(self, w, cls_list, on):
        ctx = w.get_style_context()
        for c in cls_list:
            ctx.remove_class(c)
        if on:
            ctx.add_class(on)

    # ---- layout, same order and wording as the Photoshop panel
    def build(self):
        GimpUi.init("infostyling")
        self.css()
        d = GimpUi.Dialog(title=f"InfoStyling {VERSION}", role="infostyling")
        d.add_button("_Close", Gtk.ResponseType.CLOSE)
        d.set_default_size(460, 900)
        self.dialog = d
        outer = Gtk.ScrolledWindow()
        outer.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main.set_border_width(12)
        outer.add(self.main)
        d.get_content_area().pack_start(outer, True, True, 0)

        h = self.label("InfoStyling", None); h.set_markup("<span size='x-large' weight='bold'>InfoStyling</span>")
        self.main.pack_start(h, False, False, 0)
        self.main.pack_start(self.label("Hide text inside an image, then read it back.", "small"), False, False, 0)

        # 1. Your text
        s = self.section("1. Your text")
        self.message, sw = self.textview(4)
        self.message.get_buffer().connect("changed", self.on_message)
        s.pack_start(sw, False, False, 0)
        row = Gtk.Box(spacing=6)
        b = Gtk.Button(label="Load text or EPUB file…"); b.connect("clicked", lambda *_: self.run(self.load_file, "Load file")); row.pack_start(b, True, True, 0)
        b = Gtk.Button(label="Clear"); b.connect("clicked", self.on_clear); row.pack_start(b, False, False, 0)
        s.pack_start(row, False, False, 0)
        self.payload_size = self.label("No text yet.", "small")
        s.pack_start(self.payload_size, False, False, 0)
        s.pack_start(self.label("Sign as (your name). Leave blank for no seal.", "small"), False, False, 0)
        self.sign_name = Gtk.Entry(); self.sign_name.set_placeholder_text("Your name")
        self.sign_name.set_text(self.state.get('signName') or "")
        self.sign_name.connect("changed", self.on_sign_name)
        s.pack_start(self.sign_name, False, False, 0)
        self.key_id = self.label("", "small", sel=True)
        s.pack_start(self.key_id, False, False, 0)

        # 2. Looks
        s = self.section("2. Click a look, choose Shareable or Full resolution, then press Apply filter")
        hint = self.label("", "small")
        hint.set_markup("Previews show the middle of your image. <b>Shareable</b> saves a JPEG that survives social media (short text). "
                        "<b>Full resolution</b> saves a lossless PNG that holds a whole book, but must be shared as the original file.")
        s.pack_start(hint, False, False, 0)
        row = Gtk.Box(spacing=12)
        self.out_share = Gtk.RadioButton.new_with_label(None, "Shareable (JPEG)")
        self.out_full = Gtk.RadioButton.new_with_label_from_widget(self.out_share, "Full resolution (PNG)")
        self.out_share.connect("toggled", self.on_route)
        row.pack_start(self.out_share, False, False, 0); row.pack_start(self.out_full, False, False, 0)
        s.pack_start(row, False, False, 0)
        self.space = self.label("", "space")
        s.pack_start(self.space, False, False, 0)
        grid = Gtk.Grid(column_spacing=8, row_spacing=8, column_homogeneous=True)
        self.tiles = {}
        group = None
        for k, l in enumerate(looks.LOOKS):
            ev = Gtk.EventBox()
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.get_style_context().add_class("tile")
            img = Gtk.Image()
            img.set_size_request(TILE_W, 60)
            img.get_style_context().add_class("ph")
            rb = Gtk.RadioButton.new_with_label_from_widget(group, l['label']) if group else Gtk.RadioButton.new_with_label(None, l['label'])
            group = group or rb
            rb.get_child().get_style_context().add_class("tilename")
            rb.connect("toggled", self.on_pick_radio, l['id'])
            note = self.label(l['note'], "tilenote")
            sp = self.label("", "tilespace")
            for wdg in (img, rb, note, sp):
                box.pack_start(wdg, False, False, 0)
            ev.add(box)
            ev.connect("button-press-event", lambda w, e, i=l['id']: self.pick(i))
            grid.attach(ev, k % 2, k // 2, 1, 1)
            self.tiles[l['id']] = {'box': box, 'img': img, 'radio': rb, 'space': sp}
        s.pack_start(grid, False, False, 0)
        b = Gtk.Button(label="Refresh previews"); b.connect("clicked", lambda *_: self.previews(True)); s.pack_start(b, False, False, 0)
        self.apply_btn = Gtk.Button(label="Apply filter")
        self.apply_btn.get_style_context().add_class("suggested-action")
        self.apply_btn.connect("clicked", self.on_apply)
        s.pack_start(self.apply_btn, False, False, 0)
        self.look_status = self.label("", None, sel=True)
        s.pack_start(self.look_status, False, False, 0)

        # 3. Read
        s = self.section("3. Read hidden text")
        b = Gtk.Button(label="Read hidden text from this image"); b.get_style_context().add_class("suggested-action")
        b.connect("clicked", lambda *_: self.run(lambda: self.decode(False), "Read")); s.pack_start(b, False, False, 0)
        self.read_btn = b
        self.decoded, sw = self.textview(4, editable=False, mono=True)
        s.pack_start(sw, False, False, 0)
        b = Gtk.Button(label="Save decoded text…"); b.connect("clicked", lambda *_: self.run(self.save_file, "Save file")); s.pack_start(b, False, False, 0)

        self.status = self.label("Ready.", None, sel=True)
        self.main.pack_start(self.status, False, False, 0)

        # Advanced
        exp = Gtk.Expander(label="Show advanced settings ▸")
        exp.connect("notify::expanded", lambda e, *_: e.set_label(("Hide" if e.get_expanded() else "Show") + " advanced settings " + ("▾" if e.get_expanded() else "▸")))
        adv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        adv.set_border_width(6)
        exp.add(adv)
        self.main.pack_start(exp, False, False, 0)
        row = Gtk.Box(spacing=6); row.pack_start(self.label("Seed", wrap=False), False, False, 0)
        self.seed = Gtk.SpinButton.new_with_range(-2147483648, 2147483647, 1)
        self.seed.set_value(self.state.get('seed', isconfig.DEFAULT_SEED))
        self.seed.connect("value-changed", self.on_seed)
        row.pack_start(self.seed, True, True, 0); adv.pack_start(row, False, False, 0)
        row = Gtk.Box(spacing=6)
        b = Gtk.Button(label="Read photo of a print"); b.connect("clicked", lambda *_: self.run(lambda: self.decode(True), "Camera read")); row.pack_start(b, True, True, 0)
        b = Gtk.Button(label="Read using source layer"); b.connect("clicked", lambda *_: self.run(self.paired, "Paired read")); row.pack_start(b, True, True, 0)
        adv.pack_start(row, False, False, 0)
        adv.pack_start(self.label("Cover effects (added to every look)", "sectionTitle"), False, False, 0)
        self.fx = {}
        for k, lab in fxmod.EFFECTS:
            st = self.state['fx'].get(k) or {'on': False, 'amount': 40}
            row = Gtk.Box(spacing=6)
            cb = Gtk.CheckButton(label=lab); cb.set_active(bool(st.get('on')))
            sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1); sc.set_value(st.get('amount', 40)); sc.set_size_request(140, -1)
            cb.connect("toggled", self.on_fx); sc.connect("value-changed", self.on_fx)
            row.pack_start(cb, True, True, 0); row.pack_start(sc, False, False, 0)
            adv.pack_start(row, False, False, 0)
            self.fx[k] = (cb, sc)
        self.respect_sel = Gtk.CheckButton(label="Filter only inside the active selection")
        self.deep = Gtk.CheckButton(label="Deep search when reading (slower)"); self.deep.set_active(True)
        self.camera_search = Gtk.CheckButton(label="Automatic angle search (much slower)")
        for wdg in (self.respect_sel, self.deep, self.camera_search):
            adv.pack_start(wdg, False, False, 0)
        adv.pack_start(self.label("Photo-of-a-print recovery", "sectionTitle"), False, False, 0)

        def field(lab, wdg):
            r = Gtk.Box(spacing=6); r.pack_start(self.label(lab, wrap=False), False, False, 0); r.pack_start(wdg, True, True, 0); adv.pack_start(r, False, False, 0)
            return wdg
        self.rotation = field("Rotation correction (degrees)", Gtk.SpinButton.new_with_range(-30, 30, .5)); self.rotation.set_digits(1)
        self.quad = Gtk.Entry(); self.quad.set_text("0,0;100,0;100,100;0,100")
        adv.pack_start(self.label("Artwork corners as % of selected raster: TL; TR; BR; BL"), False, False, 0); adv.pack_start(self.quad, False, False, 0)
        self.rect_w = field("Rectified width (0 auto)", Gtk.SpinButton.new_with_range(0, 100000, 1))
        self.rect_h = field("Rectified height (0 auto)", Gtk.SpinButton.new_with_range(0, 100000, 1))
        self.k1 = field("Lens k1", Gtk.SpinButton.new_with_range(-.5, .5, .005)); self.k1.set_digits(3)
        self.k2 = field("Lens k2", Gtk.SpinButton.new_with_range(-.5, .5, .005)); self.k2.set_digits(3)
        adv.pack_start(self.label("For a photographed print, enter the four artwork corners clockwise. If you know the original exported pixel dimensions, entering them as rectified width/height speeds recovery.", "small"), False, False, 0)

        self.pick(self.picked)
        d.show_all()
        GLib.timeout_add(1800, self.tick)
        GLib.idle_add(self.first)

    def first(self):
        self.capacity(True)
        self.previews(False)
        return False

    # ---- what is open
    def active(self):
        """The selected layer of the image this panel was opened on, as an Area."""
        try:
            if not self.image.is_valid():
                return None
            ls = self.image.get_selected_layers()
            layer = ls[0] if ls else None
            if layer is None:
                return None
            return Area(self.image, layer)
        except Exception:
            return None

    def source(self, a):
        """An InfoStyled copy is never re-encoded: clicks and previews always start from the original layer it was made from."""
        if not a:
            return a
        sid = source_id(a.layer.get_name())
        src = find_layer(sid) if sid else None
        if not src:
            return a
        return Area(self.image, src)

    def full_layer(self):
        a = self.active()
        if not a:
            raise ValueError("Open an image first.")
        if not a.fills_canvas():
            raise ValueError(f"Select a layer that fills the whole canvas (or use Image > Flatten Image) and try again. "
                             f"Layer is {a.lw}x{a.lh} px; canvas is {self.image.get_width()}x{self.image.get_height()} px.")
        return a

    # ---- events
    def message_text(self):
        return self.file_text if self.file_text is not None else self.tv_text(self.message)

    def on_message(self, *_):
        if self._setting_file:
            return
        if self.file_text is not None:
            self.file_text = None; self.file_name = None
        self.schedule_capacity()

    _setting_file = False
    _cap_timer = None

    def schedule_capacity(self):
        if self._cap_timer:
            GLib.source_remove(self._cap_timer)
        self._cap_timer = GLib.timeout_add(400, self._cap_now)

    def _cap_now(self):
        self._cap_timer = None
        self.capacity()
        return False

    def on_clear(self, *_):
        self.file_text = None; self.file_name = None
        self._setting_file = True
        self.message.get_buffer().set_text("")
        self._setting_file = False
        self.capacity()

    def on_sign_name(self, *_):
        self.state['signName'] = self.sign_name.get_text()
        self.save_state()
        self.schedule_capacity()

    def on_seed(self, *_):
        self.state['seed'] = int(self.seed.get_value())
        self.save_state()
        self.previews(True)

    def on_fx(self, *_):
        for k, (cb, sc) in self.fx.items():
            self.state['fx'][k] = {'on': cb.get_active(), 'amount': int(sc.get_value())}
        self.save_state()

    def on_route(self, *_):
        self.route = "share" if self.out_share.get_active() else "full"
        self.pick(None)
        self.capacity(True)

    def on_pick_radio(self, rb, i):
        if rb.get_active() and self.picked != i:
            self.pick(i)

    def pick(self, i):
        if i:
            self.picked = i
        for l in looks.LOOKS:
            t = self.tiles[l['id']]
            on = l['id'] == self.picked
            self.set_cls(t['box'], ["picked"], "picked" if on else None)
            if on and not t['radio'].get_active():
                t['radio'].set_active(True)
        if not self.busy:
            self.apply_btn.set_label(f"Apply filter: {looks.by_id(self.picked)['label']}, {'Shareable (JPEG)' if self.route == 'share' else 'Full resolution (PNG)'}")
        if i:
            self.capacity(True)
        return True

    def tick(self):
        if not self.dialog.get_visible():
            return False
        if not self.busy:
            self.capacity()
            self.previews(False)
        return True

    def seed_value(self):
        return int(self.seed.get_value())

    def effects(self):
        return {k: {'on': cb.get_active(), 'amount': int(sc.get_value())} for k, (cb, sc) in self.fx.items()}

    def pump(self):
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)

    def say_status(self, t):
        self.status.set_text(t)
        self.pump()

    def result(self, text, kind=None):
        self.look_status.set_text(text)
        self.set_cls(self.look_status, ["working", "ok", "bad"], kind)
        self.pump()

    def run(self, fn, label):
        if self.busy:
            return
        self.busy = True
        try:
            fn()
        except Exception as e:
            self.say_status(f"{label} failed: {e}")
        finally:
            self.busy = False
            Gimp.progress_end()

    # ---- keys
    def get_keys(self):
        if not self.keys:
            path = os.path.join(data_dir(), "sealkey.txt")
            try:
                with open(path, encoding="utf-8") as f:
                    self.keys = seal.keys_from_secret(f.read().strip())
            except Exception:
                self.keys = None
            if not self.keys:
                self.keys = seal.new_keys()
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(seal.secret_text(self.keys))
                    os.chmod(path, 0o600)
                except Exception:
                    pass
            self.key_id.set_text(f"Your key ID: {seal.key_id(self.keys['publicKey'])}. Publish it so people can tell your seal from a counterfeit.")
        return self.keys

    def sized(self, text, name):
        return seal.placeholder(text, name, self.get_keys()) if name and text else text

    # ---- space figures
    def set_tile_space(self, i, text, over):
        sp = self.tiles[i]['space']
        sp.set_text(text)
        self.set_cls(sp, ["over"], "over" if over else None)

    def set_space(self, text, over):
        self.space.set_text(text)
        self.set_cls(self.space, ["over"], "over" if over else None)

    def capacity(self, force=False):
        a = self.active()
        typed = self.message_text()
        name = self.sign_name.get_text().strip()
        key = f"{(a.layer.get_id(), a.width, a.height) if a else '-'}|{name}|{len(typed)}|{typed[:200]}|{typed[-200:]}|{self.route}|{self.picked}"
        if not force and key == self._ckey:
            return
        self._ckey = key
        text = self.sized(typed, name)
        nbytes = len(codec.utf8_encode(text)) if typed else 0
        self.payload_size.set_text(f"{num(len(typed))} characters typed or loaded.")
        memo = {'bytes': nbytes}
        n = len(typed)
        size = "Shareable (JPEG)" if self.route == "share" else "Full resolution (PNG)"
        if not a:
            for l in looks.LOOKS:
                self.set_tile_space(l['id'], "", False)
            self.set_space(f"Your text uses: {num(n)} characters\nOpen an image to see how much text each look can hold.", False)
            return
        if nbytes > pack.BIG and not pack.ready(text):
            for l in looks.LOOKS:
                self.set_tile_space(l['id'], "Measuring…", False)
            self.set_space(f"Your text: {num(n)} characters.\nMeasuring how small it packs…", False)
            self.pump()
            if self.busy:
                return
            self.busy = True
            try:
                pack.pack(text, codec.utf8_encode(text), lambda f: (Gimp.progress_update(f), self.pump()))
            finally:
                self.busy = False
        pick = None
        for l in looks.LOOKS:
            q = looks.plan(l['id'], a.width, a.height, text, memo, self.route) if nbytes else None
            f = looks.footprint(l['id'], a.width, a.height, q['stored'] if q else 0, self.route)
            over = bool(q) and f['over']
            if l['id'] == self.picked:
                pick = (l, f, over)
            t = f"Bytes available: {num(f['avail'])}"
            if q:
                t += f"\nYour text takes: {num(f['takes'])} bytes\n" + (f"TOO LONG by {num(f['short'])} bytes" if over else f"Bytes left: {num(f['left'])}")
            self.set_tile_space(l['id'], t, over)
        extra = f"\n{pick[0]['label']}, {size}: {num(pick[1]['avail'])} bytes available, your text takes {num(pick[1]['takes'])} bytes." if pick and nbytes else ""
        self.set_space(f"Your text: {num(n)} characters.{extra}", bool(pick) and pick[2])

    # ---- previews: a crop from the middle of the layer at full scale, drawn with each look, then shrunk to tile size
    def previews(self, force):
        a = self.source(self.active())
        if not a or not a.width or not a.height:
            return
        seed = self.seed_value()
        key = (a.layer.get_id(), a.width, a.height, seed)
        if not force and key == self._pkey:
            return
        self._pkey = key
        cw = min(a.width, 640, round(min(a.height, 400) * 1.6))
        ch = min(a.height, round(cw / 1.6))
        left = (a.width - cw) // 2; top = (a.height - ch) // 2
        try:
            crop = a.pixels(left, top, cw, ch)
        except Exception as e:
            self._pkey = None
            self.say_status("Preview failed: " + str(e))
            return
        self._pjob = (key, crop, cw, ch, a.width, a.height, seed)
        self._pqueue = [l['id'] for l in looks.LOOKS]
        GLib.idle_add(self._preview_next)

    def _preview_next(self):
        if not self._pqueue or self._pjob is None:
            return False
        if self.busy:
            return True
        key, crop, cw, ch, W, H, seed = self._pjob
        if key != self._pkey:
            return False
        i = self._pqueue.pop(0)
        try:
            px = looks.preview(i, crop, cw, ch, 4, W, H, seed)
            tw = min(TILE_W, cw); th = max(1, round(ch * tw / cw))
            rgb = shrink(px, cw, ch, 4, tw, th)
            pb = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes(rgb)), GdkPixbuf.Colorspace.RGB, False, 8, tw, th, tw * 3)
            self.tiles[i]['img'].set_from_pixbuf(pb)
        except Exception as e:
            self.say_status("Preview failed: " + str(e))
        return bool(self._pqueue)

    # ---- Apply filter: hide the text with this look, verify, ask where to save, save, then re-open the saved file and read it back
    def on_apply(self, *_):
        if self.busy:
            return
        look = looks.by_id(self.picked)
        self.busy = True
        self.apply_btn.set_sensitive(False)
        self.apply_btn.set_label("Working… please wait")
        self.result(f"Applying {look['label']}…", "working")
        try:
            self.one_click(self.picked, self.route)
        except Exception as e:
            self.result("✗ NOT APPLIED. " + str(e), "bad")
        finally:
            self.busy = False
            Gimp.progress_end()
            self.apply_btn.set_sensitive(True)
            self.pick(None)

    def progress(self, label, frac):
        if label:
            self.say_status(label + ("…" if not label.endswith("…") else ""))
        if frac is not None:
            Gimp.progress_update(max(0.0, min(1.0, frac)))
        self.pump()

    def one_click(self, i, route):
        plain = self.message_text()
        name = self.sign_name.get_text().strip()
        if not plain:
            raise ValueError("Type or load the text to hide first (step 1).")
        look = looks.by_id(i)
        png = route == "full"
        a = self.source(self.full_layer())
        if png:
            if self.image.get_base_type() != Gimp.ImageBaseType.RGB:
                raise ValueError("High capacity needs an RGB image: Image > Mode > RGB.")
            if self.image.get_precision() != Gimp.Precision.U8_NON_LINEAR:
                raise ValueError("High capacity needs an 8-bit image: Image > Precision > 8 bit integer (Perceptual gamma).")
        Gimp.progress_init(f"InfoStyling {look['label']}")
        sized = self.sized(plain, name)
        if not pack.ready(sized):
            self.result("Compressing your text…", "working")
        q = looks.plan(i, a.width, a.height, sized, {}, route, lambda f: self.progress("Compressing your text", f))
        if not q['fits']:
            f = looks.footprint(i, a.width, a.height, q['stored'], route)
            raise ValueError(f"Too long: your text takes {num(f['takes'])} bytes and {look['label']} has {num(f['avail'])} bytes available at "
                             f"{'Full resolution (PNG)' if png else 'Shareable (JPEG)'}.{' Use a larger image.' if png else ' Shorten it, or press Full resolution (PNG).'}")
        self.result(f"{look['label']}: hiding {kb(q['bytes'])} of text" + (f" as a lossless PNG at {q['bpc']} bit/ch" if png else
                    f" as a sharing-safe JPEG ({'8×8 brightness patterns' if i == 'none' else str(q['cell']) + 'px marks'})") + "…", "working")
        src = a.pixels()
        w, h = a.width, a.height
        mask = None
        if self.respect_sel.get_active() and i not in ("none", "glyph", "colorpop", "tract"):
            try:
                if not Gimp.Selection.is_empty(self.image):
                    sel = self.image.get_selection()
                    ox = a.lx + a.x; oy = a.ly + a.y
                    mask = bytearray(sel.get_buffer().get(Gegl.Rectangle.new(ox, oy, w, h), 1.0, "Y u8", Gegl.AbyssPolicy.NONE))
            except Exception:
                mask = None
        sign = (name, self.get_keys()) if name else None
        e = engine.encode(src, w, h, 4, plain, i, route, self.seed_value(), self.effects(), sign, mask, self.progress)
        text = e['text']
        # A new layer above the source holds the result.
        self.image.undo_group_start()
        try:
            src_layer = a.layer
            tag = 'HC' if png else e['p']['style']
            layer = Gimp.Layer.new(self.image, f"InfoStyled • {tag} • {src_layer.get_name()} [IS5 cell={e['p']['blindCell']} src={src_layer.get_id()}]",
                                   w, h, Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
            parent = src_layer.get_parent()
            self.image.insert_layer(layer, parent, self.image.get_item_position(src_layer))
            layer.set_offsets(a.lx + a.x, a.ly + a.y)
            write_pixels(layer, e['pixels'], w, h)
            for l in self.image.get_layers():
                if l.get_id() != layer.get_id() and (l.get_name() or "").startswith("InfoStyled •"):
                    try:
                        l.set_visible(False)
                    except Exception:
                        pass
            self.image.set_selected_layers([layer])
        finally:
            self.image.undo_group_end()
        Gimp.displays_flush()
        self.progress("Checking the new layer", None)
        back = read_pixels(layer, 0, 0, w, h)
        d = engine.read_known(back, w, h, 4, i, route, q['cell'])
        if not d or d['text'] != text:
            raise ValueError("verification decode did not match")
        # Save
        fname = self.save_dialog(self.doc_name() + f"_{i}{'.png' if png else '.jpg'}", png)
        if not fname:
            self.result(f"✓ APPLIED {look['label']}: hidden and verified on a new layer. Save cancelled, so nothing was written to disk.", "ok")
            return
        base = os.path.basename(fname)
        self.result(f"{look['label']} applied. Saving {base} and checking it…", "working")
        self.export(layer, fname, png)
        check, seal_check = self.verify_file(fname, text, name, i, route, q['cell'])
        good = check.startswith("Verified")
        self.result(f"{'✓ APPLIED' if good else '⚠ APPLIED, BUT CHECK FAILED:'} {look['label']}: saved {base}.\n{check}"
                    + (f"\nSeal on the saved file: {seal_check}" if seal_check else "")
                    + ("\nShare the PNG file itself. JPEG conversion or resizing destroys book-size text." if png else "\nSurvives JPEG and resizing by social media."),
                    "ok" if good else "bad")
        self.say_status("Ready.")

    def doc_name(self):
        n = ""
        try:
            f = self.image.get_file()
            n = f.get_basename() if f else ""
        except Exception:
            pass
        n = n or (self.image.get_name() or "image")
        return os.path.splitext(n)[0]

    def save_dialog(self, suggested, png):
        dlg = Gtk.FileChooserDialog(title="Save the InfoStyled image", parent=self.dialog, action=Gtk.FileChooserAction.SAVE)
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Save", Gtk.ResponseType.ACCEPT)
        dlg.set_do_overwrite_confirmation(True)
        dlg.set_current_name(suggested)
        try:
            f = self.image.get_file()
            if f and f.get_parent():
                dlg.set_current_folder(f.get_parent().get_path())
        except Exception:
            pass
        flt = Gtk.FileFilter()
        flt.set_name("PNG image" if png else "JPEG image")
        for p in (["*.png"] if png else ["*.jpg", "*.jpeg"]):
            flt.add_pattern(p)
        dlg.add_filter(flt)
        r = dlg.run()
        fn = dlg.get_filename() if r == Gtk.ResponseType.ACCEPT else None
        dlg.destroy()
        self.pump()
        if fn and not os.path.splitext(fn)[1].lower() in ((".png",) if png else (".jpg", ".jpeg")):
            fn += ".png" if png else ".jpg"
        return fn

    def export(self, layer, fname, png):
        """Saves a copy that shows only the InfoStyled layer, as a top-quality JPEG or a lossless PNG."""
        w, h = layer.get_width(), layer.get_height()
        img = Gimp.Image.new(w, h, Gimp.ImageBaseType.RGB)
        try:
            l2 = Gimp.Layer.new_from_drawable(layer, img)
            img.insert_layer(l2, None, 0)
            l2.set_offsets(0, 0)
            l2.set_visible(True)
            pdb = Gimp.get_pdb()
            proc = pdb.lookup_procedure("file-png-export" if png else "file-jpeg-export")
            c = proc.create_config()
            c.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
            c.set_property("image", img)
            c.set_property("file", Gio.File.new_for_path(fname))
            if png:
                c.set_property("save-transparent", True)
            else:
                c.set_property("quality", 0.98)
            r = proc.run(c)
            if r.index(0) != Gimp.PDBStatusType.SUCCESS:
                raise ValueError(f"GIMP could not save {os.path.basename(fname)}.")
        finally:
            img.delete()

    def verify_file(self, fname, text, name, i, route, cell):
        img = None
        try:
            img = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(fname))
            l = img.get_layers()[0]
            w, h = l.get_width(), l.get_height()
            px = read_pixels(l, 0, 0, w, h)
            d = engine.read_known(px, w, h, 4, i, route, cell)
            if (not d or d['text'] != text) and route == "share" and i not in ("none",):
                d = fractional.decode_fractional(px, w, h, 4, {'maxPilotErrors': 10})
            if not d or d['text'] != text:
                return "WARNING: the saved file did not decode. Try a larger image.", ""
            sc = ""
            if name:
                c = seal.check(d['text'], px, w, h, 4)
                sc = c['line']
                if c['status'] != "ok":
                    return "WARNING: the saved file did not decode. Try a larger image.", sc
            return "Verified: re-opened the saved file and decoded the message (CRC valid).", sc
        except Exception as e:
            return f"WARNING: could not re-open the saved file to verify it ({e}).", ""
        finally:
            if img:
                try:
                    img.delete()
                except Exception:
                    pass

    # ---- Read
    def show_decoded(self, text):
        self.last_decoded = text
        if len(text) > DECODED_MAX:
            text = text[:DECODED_MAX] + f"\n\n… {len(text) - DECODED_MAX} more characters. Use \"Save decoded text…\" for the full text."
        self.decoded.get_buffer().set_text(text)

    def sealed(self, full, px, w, h):
        c = seal.check(full, px, w, h, 4)
        self.show_decoded(c['text'])
        return "\n" + c['line']

    def decode(self, camera):
        a = self.active()
        if not a:
            raise ValueError("Select an encoded/exported raster layer.")
        Gimp.progress_init("InfoStyling Read")
        self.say_status("Reading…")
        w, h = a.lw, a.lh
        px = read_pixels(a.layer, 0, 0, w, h)
        if not camera:
            hc = dense.extract(px, w, h, 4)
            if hc:
                sl = self.sealed(hc['text'], px, w, h)
                self.say_status(f"High-capacity decode OK • {kb(hc['rawBytes'])} of text • {hc['bpc']} bit/ch • CRC valid." + sl)
                return
            self.say_status("Looking for the Invisible look…")
            bq = brightq.extract(px, w, h, 4)
            if bq:
                sl = self.sealed(bq['text'], px, w, h)
                self.say_status(f"Invisible (brightness) decode OK • {kb(bq['rawBytes'])} of text • CRC valid." + sl)
                return
        opts = {'deep': self.deep.get_active(), 'camera': self.camera_search.get_active(), 'rotationHint': self.rotation.get_value()}
        if camera:
            qt = self.quad.get_text()
            pts = [s.strip() for s in qt.split(";") if s.strip()]
            try:
                quad = [[float(v) for v in s.split(",")] for s in pts]
                if len(quad) != 4 or any(len(p) != 2 for p in quad):
                    raise ValueError()
            except Exception:
                raise ValueError("Corners must be TLx,TLy;TRx,TRy;BRx,BRy;BLx,BLy")
            opts.update({'quad': [[p[0] * (w - 1) / 100, p[1] * (h - 1) / 100] for p in quad], 'rectWidth': self.rect_w.get_value(),
                         'rectHeight': self.rect_h.get_value(), 'lensK1': self.k1.get_value(), 'lensK2': self.k2.get_value()})
            self.say_status("Reading the photo of a print (slow)…")
            d = decoder.decode_blind(px, w, h, 4, opts)
        else:
            d = engine.any_decode(px, w, h, 4, {'after_brightq': True, 'deep': opts['deep'], 'camera': opts['camera'], 'rotationHint': opts['rotationHint']},
                                  lambda t, f: self.say_status(t))
            if not d:
                raise ValueError("No valid ISB3 camera tile recovered.")
        if camera:
            c = seal.check(d['text'], None)
            self.show_decoded(c['text'])
            sl = "\n" + c['line']
        else:
            sl = self.sealed(d['text'], px, w, h)
        car = d.get('carrier')
        kind = "Glyph hatch" if car == "glyph" else "Color Pop" if car == "colorpop" else "ISB3 " + ("camera" if camera else "robust")
        self.say_status(f"{kind} decode OK • {len(codec.utf8_encode(d['text']))} bytes • style {d['meta']['style']} • carrier {d.get('cell')}px • "
                        f"offset {d.get('offX', 0)},{d.get('offY', 0)} • {d.get('copies') or 1} tile source(s) • rotation correction {d.get('deskewAngle') or 0}° • CRC valid." + sl)

    def paired(self):
        a = self.active()
        if not a:
            raise ValueError("Select an InfoStyled output layer.")
        nm = a.layer.get_name()
        sid = source_id(nm)
        src = find_layer(sid) if sid else None
        if not sid:
            raise ValueError("Source-layer ID is not present in this layer name.")
        if not src:
            raise ValueError("Paired source layer not found.")
        import re
        w, h = a.lw, a.lh
        enc = read_pixels(a.layer, 0, 0, w, h)
        sx, sy, sw, sh = layer_rect(src)
        orig = read_pixels(src, a.lx - sx, a.ly - sy, w, h)
        m = re.search(r"InfoStyled • (\w+)", nm)
        cm_ = re.search(r"\[IS5 cell=(\d+)", nm)
        lid = m.group(1) if m and looks.by_id(m.group(1)) else "engraving"
        d = decoder.decode_paired(orig, enc, w, h, 4, looks.profile(lid, int(cm_.group(1)) if cm_ else 16, self.seed_value()))
        sl = self.sealed(d['text'], enc, w, h)
        self.say_status(f"Paired diagnostic decode OK • {len(codec.utf8_encode(d['text']))} bytes • confidence {d['confidence']:.2f} • CRC valid." + sl)

    # ---- files
    def load_file(self):
        dlg = Gtk.FileChooserDialog(title="Load text or EPUB file", parent=self.dialog, action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Open", Gtk.ResponseType.ACCEPT)
        r = dlg.run()
        fn = dlg.get_filename() if r == Gtk.ResponseType.ACCEPT else None
        dlg.destroy()
        self.pump()
        if not fn:
            return
        base = os.path.basename(fn)
        book = None
        with open(fn, "rb") as f:
            data = f.read()
        if fn.lower().endswith(".epub"):
            book = epub.epub_text(data)
            text = book['text']
        else:
            text = data.decode("utf-8", "replace")
        self.file_text = text
        self.file_name = base
        self._setting_file = True
        self.message.get_buffer().set_text(text[:PREVIEW_CHARS] + "\n…" if len(text) > PREVIEW_CHARS else text)
        self._setting_file = False
        self.say_status(f"Loaded {base}: {book['title'] or 'EPUB'}, {book['chapters']} chapter(s) as plain text." if book else f"Loaded {base}.")
        self.capacity()

    def save_file(self):
        t = self.last_decoded
        if not t:
            raise ValueError("Nothing decoded yet.")
        dlg = Gtk.FileChooserDialog(title="Save decoded text", parent=self.dialog, action=Gtk.FileChooserAction.SAVE)
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Save", Gtk.ResponseType.ACCEPT)
        dlg.set_do_overwrite_confirmation(True)
        dlg.set_current_name("decoded.txt")
        r = dlg.run()
        fn = dlg.get_filename() if r == Gtk.ResponseType.ACCEPT else None
        dlg.destroy()
        if not fn:
            return
        with open(fn, "w", encoding="utf-8") as f:
            f.write(t)
        self.say_status(f"Saved {len(t)} characters to {os.path.basename(fn)}.")


def run_panel(procedure, run_mode, image, drawables, config, data):
    if run_mode != Gimp.RunMode.INTERACTIVE:
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, GLib.Error("InfoStyling runs interactively: Filters > InfoStyling…"))
    Gegl.init(None)
    layer = drawables[0] if drawables else None
    p = Panel(image, layer)
    p.dialog.run()
    p.dialog.destroy()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)


class InfoStyling(Gimp.PlugIn):
    def do_set_i18n(self, name):
        return False

    def do_query_procedures(self):
        return [PROC]

    def do_create_procedure(self, name):
        p = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, run_panel, None)
        p.set_image_types("RGB*")
        p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.DRAWABLES | Gimp.ProcedureSensitivityMask.NO_DRAWABLES)
        p.set_menu_label("_InfoStyling…")
        p.add_menu_path("<Image>/Filters")
        p.set_documentation("Hide text inside an image, then read it back",
                            "InfoStyling: the same looks, Shareable/Full resolution, compression and signed seal as the InfoStyling Photoshop plugin.", name)
        p.set_attribution("zoomatech", "zoomatech", "2026")
        return p


Gimp.main(InfoStyling.__gtype__, sys.argv)
