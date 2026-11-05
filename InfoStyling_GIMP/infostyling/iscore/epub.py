"""EPUB reader (port of core/epub.js): unzips the book, follows the OPF spine for reading order and
returns the chapters as plain text with paragraph breaks. DRM-protected books are refused."""
import io, re, zipfile, html
from urllib.parse import unquote

ENT = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'", "nbsp": " ", "mdash": "—", "ndash": "–", "hellip": "…",
       "lsquo": "‘", "rsquo": "’", "ldquo": "“", "rdquo": "”", "copy": "©", "shy": ""}


def entities(s):
    def rep(m):
        e = m.group(1)
        if e[0] == "#":
            try:
                return chr(int(e[2:], 16) if e[1] in "xX" else int(e[1:], 10))
            except Exception:
                return m.group(0)
        return ENT.get(e.lower(), m.group(0))
    return re.sub(r"&(#x[0-9a-f]+|#\d+|[a-z]+);", rep, s, flags=re.I)


def attr(tag, name):
    m = re.search(r"\s" + name + r"\s*=\s*(\"([^\"]*)\"|'([^']*)')", tag, re.I)
    if not m:
        return None
    return m.group(2) if m.group(2) is not None else m.group(3)


def html_text(h):
    h = re.sub(r"<head[\s\S]*?</head>", "", h, flags=re.I)
    h = re.sub(r"<(script|style)[\s\S]*?</\1>", "", h, flags=re.I)
    h = re.sub(r"<br\s*/?>", "\n", h, flags=re.I)
    h = re.sub(r"</(p|div|h[1-6]|li|blockquote|tr|section|title)>", "\n\n", h, flags=re.I)
    h = re.sub(r"<[^>]+>", "", h)
    s = entities(h)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def resolve(base, href):
    parts = (base + unquote(href.split("#")[0])).split("/")
    out = []
    for s in parts:
        if s == "..":
            if out: out.pop()
        elif s not in (".", ""):
            out.append(s)
    return "/".join(out)


def epub_text(data):
    z = zipfile.ZipFile(io.BytesIO(bytes(data)))
    names = z.namelist()

    def get(n):
        f = n if n in names else next((k for k in names if k.lower() == n.lower()), None)
        return z.read(f).decode("utf-8", "replace") if f else None
    container = get("META-INF/container.xml")
    if not container:
        raise ValueError("Not an EPUB: META-INF/container.xml is missing.")
    enc = get("META-INF/encryption.xml")
    if enc and re.search(r"<(?:\w+:)?EncryptedData\b", enc, re.I) and not re.search(r"idpf\.org/2008/embedding|ns\.adobe\.com/pdf/enc#RC", enc, re.I):
        raise ValueError("This EPUB is DRM-protected, so its text can't be read. Use a DRM-free copy.")
    m = re.search(r"<rootfile\b[^>]*>", container, re.I)
    opf_path = attr(m.group(0) if m else "", "full-path")
    if not opf_path:
        raise ValueError("EPUB has no package file.")
    opf = get(opf_path)
    if not opf:
        raise ValueError(f"EPUB package {opf_path} is missing.")
    base = opf_path[:opf_path.rfind("/") + 1] if "/" in opf_path else ""
    items = {}
    for t in re.findall(r"<(?:\w+:)?item\b[^>]*>", opf, re.I):
        i = attr(t, "id"); href = attr(t, "href")
        if i and href:
            items[i] = {'href': href, 'type': attr(t, "media-type") or ""}
    tm = re.search(r"<dc:title[^>]*>([\s\S]*?)</dc:title>", opf, re.I)
    am = re.search(r"<dc:creator[^>]*>([\s\S]*?)</dc:creator>", opf, re.I)
    title = entities(tm.group(1) if tm else "").strip()
    author = entities(am.group(1) if am else "").strip()
    chapters = []
    for t in re.findall(r"<(?:\w+:)?itemref\b[^>]*>", opf, re.I):
        it = items.get(attr(t, "idref"))
        if not it or not re.search(r"html|xml", it['type'], re.I):
            continue
        hh = get(resolve(base, it['href']))
        if hh:
            s = html_text(hh)
            if s:
                chapters.append(s)
    if not chapters:
        raise ValueError("EPUB has no readable chapters (it may be DRM-protected).")
    head = "\n".join(x for x in [title, f"by {author}" if author else ""] if x)
    return {'title': title, 'author': author, 'chapters': len(chapters), 'text': (head + "\n\n" if head else "") + "\n\n".join(chapters)}
