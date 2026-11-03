"use strict";
// InfoStyling Decoder content script: comic speech balloon over decoded images, auto-scan, local decode fallback.
(() => {
  if (window.__infoStylingDecoder) return;
  window.__infoStylingDecoder = true;

  const PREVIEW = 5000000;
  const balloons = new Map(); // img element -> balloon record
  let lastContextImg = null;

  document.addEventListener("contextmenu", (e) => {
    const t = e.target;
    lastContextImg = t instanceof HTMLImageElement ? t : (t && t.closest && t.closest("img")) || null;
  }, true);

  const srcOf = (img) => img.currentSrc || img.src || "";

  function findImage(srcUrl) {
    if (lastContextImg && (srcOf(lastContextImg) === srcUrl || lastContextImg.src === srcUrl)) return lastContextImg;
    for (const img of document.images) if (srcOf(img) === srcUrl || img.src === srcUrl) return img;
    return lastContextImg;
  }

  const CSS = `
    :host{all:initial}
    [hidden]{display:none!important}
    .wrap{position:relative;filter:drop-shadow(0 6px 14px rgba(0,0,0,.28));transform-origin:24px 100%;animation:pop .32s cubic-bezier(.2,1.6,.4,1)}
    @keyframes pop{0%{transform:scale(.2);opacity:0}100%{transform:scale(1);opacity:1}}
    .balloon{box-sizing:border-box;position:relative;background:#fffef6;color:#111;border:3px solid #111;border-radius:22px;padding:10px 14px 10px;
      font:15px/1.4 "Comic Neue","Comic Sans MS","Chalkboard SE","Marker Felt",cursive,sans-serif}
    .tail{position:absolute;left:30px;bottom:-22px;width:0;height:0;border-left:14px solid transparent;border-right:14px solid transparent;border-top:24px solid #111;transform:skewX(-22deg)}
    .tail::after{content:"";position:absolute;left:-9px;top:-27px;border-left:9px solid transparent;border-right:9px solid transparent;border-top:17px solid #fffef6}
    .head{display:flex;align-items:center;gap:6px;margin-bottom:2px}
    .title{flex:1;font-weight:700;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#1f4fd1}
    .err .title{color:#b3261e}
    .text{margin:2px 0;max-height:min(55vh,520px);overflow-y:auto;overscroll-behavior:contain;white-space:pre-wrap;word-break:break-word;padding-right:6px}
    .meta{color:#666;font:11px/1.3 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;margin-top:4px}
    .row{display:flex;gap:6px;margin-top:6px}
    button{font:12px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;border:2px solid #111;background:#ffe14d;color:#111;border-radius:999px;padding:1px 10px;cursor:pointer}
    button:hover{background:#ffd000}
    .x{border:none;background:none;font-size:18px;line-height:1;padding:0 2px}
    .x:hover{background:none;color:#b3261e}
    .chip{all:unset;cursor:pointer;width:34px;height:34px;border-radius:50%;background:#ffe14d;border:3px solid #111;display:grid;place-items:center;font:18px/1 sans-serif;box-shadow:0 3px 10px rgba(0,0,0,.3)}
  `;

  function place(rec) {
    const s = rec.host.style;
    const r = rec.img && rec.img.isConnected ? rec.img.getBoundingClientRect() : null;
    if (!r || (r.width === 0 && r.height === 0)) {
      s.position = "fixed"; s.top = "16px"; s.right = "16px"; s.left = "auto"; s.width = "360px";
      return;
    }
    s.position = "absolute"; s.right = "auto";
    if (rec.collapsed) {
      s.width = "auto";
      s.left = `${r.left + window.scrollX + 8}px`;
      s.top = `${r.top + window.scrollY + 8}px`;
      return;
    }
    // Balloon floats over the upper part of the image, tail pointing down into it.
    const w = Math.max(220, Math.min(r.width - 24, 420));
    s.width = `${w}px`;
    s.left = `${Math.max(4, r.left + window.scrollX + Math.min(16, Math.max(0, (r.width - w) / 2)))}px`;
    s.top = `${Math.max(4, r.top + window.scrollY + 12)}px`;
    { const t = rec.root.querySelector(".text"), long = t.textContent.length > 1500, cap = long ? Math.min(520, innerHeight * 0.55) : 220; t.style.maxHeight = `${Math.round(Math.max(long ? 160 : 72, Math.min(cap, long ? Math.max(r.height - 150, innerHeight * 0.45) : r.height - 150)))}px`; }
  }

  function balloonFor(img) {
    let rec = img && balloons.get(img);
    if (rec) return rec;
    const host = document.createElement("infostyling-balloon");
    host.style.zIndex = "2147483646";
    const root = host.attachShadow({ mode: "closed" });
    root.innerHTML = `<style>${CSS}</style>
      <div class="wrap"><div class="balloon"><div class="head"><span class="title"></span><button class="x" title="Close">×</button></div>
      <div class="text" hidden></div><div class="row" hidden><button class="copy">Copy</button><button class="save">Save .txt</button></div>
      <div class="meta"></div><div class="tail"></div></div></div>
      <button class="chip" title="Show hidden InfoStyling text" hidden>💬</button>`;
    rec = { img, host, root, text: "", collapsed: false };
    const wrap = root.querySelector(".wrap"), chip = root.querySelector(".chip");
    const setCollapsed = (c) => { rec.collapsed = c; wrap.hidden = c; chip.hidden = !c; place(rec); };
    rec.setCollapsed = setCollapsed;
    root.querySelector(".x").onclick = () => {
      if (rec.ok) setCollapsed(true); // keep a small 💬 chip on the image to reopen it
      else { host.remove(); if (img) balloons.delete(img); }
    };
    chip.onclick = () => setCollapsed(false);
    root.querySelector(".copy").onclick = async (e) => {
      try { await navigator.clipboard.writeText(rec.text); e.target.textContent = "Copied!"; } catch { e.target.textContent = "Copy failed"; }
      setTimeout(() => (e.target.textContent = "Copy"), 1500);
    };
    root.querySelector(".save").onclick = () => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([rec.text], { type: "text/plain;charset=utf-8" }));
      a.download = "infostyling-decoded.txt";
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    };
    document.documentElement.appendChild(host);
    if (img) balloons.set(img, rec);
    place(rec);
    return rec;
  }

  function show(img, state, title, text, meta) {
    const rec = balloonFor(img);
    rec.ok = state === "ok";
    const balloon = rec.root.querySelector(".balloon"), body = rec.root.querySelector(".text"), row = rec.root.querySelector(".row");
    balloon.className = `balloon ${state}`;
    rec.root.querySelector(".title").textContent = title;
    rec.text = text || "";
    body.hidden = row.hidden = !text;
    body.textContent = text ? (text.length > PREVIEW ? `${text.slice(0, PREVIEW)}\n\n… ${text.length - PREVIEW} more characters (use Copy or Save).` : text) : "";
    rec.root.querySelector(".meta").textContent = meta || "";
    rec.setCollapsed(false);
  }

  function render(img, r) {
    // A signed message shows the seal check as the title: green when it checks out, red when tampered or counterfeit.
    if (r && r.ok && r.seal) show(img, r.seal.status === "ok" ? "ok" : "err", r.seal.short, r.text, `${r.seal.line}
${r.mode} · ${r.detail} · ${r.width}×${r.height} px · ${(r.ms / 1000).toFixed(1)} s`);
    else if (r && r.ok) show(img, "ok", `Hidden message · ${r.mode}`, r.text, `${r.detail} · ${r.width}×${r.height} px · ${(r.ms / 1000).toFixed(1)} s`);
    else show(img, "err", "No hidden message found", "", (r && (r.robustError ? `${r.error} (${r.robustError})` : r.error)) || "Unknown error");
  }

  const replaceAll = () => balloons.forEach(place);
  window.addEventListener("resize", replaceAll);
  window.addEventListener("load", replaceAll);

  // ---- local decode (blob: URLs, or browsers whose worker lacks OffscreenCanvas) ----
  async function ensureCore() {
    if (window.InfoStylingCore) return;
    const r = await chrome.runtime.sendMessage({ type: "is-need-core" });
    if (!r || !r.ok || !window.InfoStylingCore) throw new Error((r && r.error) || "Decoder library could not be loaded");
  }

  async function decodeLocally(url, dataUrl, deep) {
    await ensureCore();
    const blob = await (await fetch(dataUrl || url)).blob();
    let w, h, data;
    const c = document.createElement("canvas");
    if (typeof createImageBitmap === "function") {
      const bmp = await createImageBitmap(blob, { colorSpaceConversion: "none", premultiplyAlpha: "none" });
      w = c.width = bmp.width; h = c.height = bmp.height;
      const g = c.getContext("2d", { willReadFrequently: true }); g.drawImage(bmp, 0, 0); bmp.close();
      data = g.getImageData(0, 0, w, h).data;
    } else {
      const im = new Image(); im.src = URL.createObjectURL(blob); await im.decode();
      w = c.width = im.naturalWidth; h = c.height = im.naturalHeight;
      const g = c.getContext("2d", { willReadFrequently: true }); g.drawImage(im, 0, 0);
      data = g.getImageData(0, 0, w, h).data;
    }
    await new Promise((r) => setTimeout(r, 30)); // let the "Decoding…" balloon paint first
    return window.InfoStylingCore.decodePixels(data, w, h, { deep });
  }

  async function finish(url, r, deep) {
    if (r && r.local) {
      try { r = await decodeLocally(url, r.dataUrl, deep); } catch (e) { r = { ok: false, error: e.message }; }
    }
    if (r && r.ok) chrome.runtime.sendMessage({ type: "is-found", url, mode: r.mode, preview: r.text.slice(0, 160) }).catch(() => {});
    return r;
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === "is-status") {
      show(findImage(msg.srcUrl), "", "InfoStyling", "", msg.text);
      sendResponse(true);
    } else if (msg.type === "is-result") {
      const img = findImage(msg.srcUrl);
      finish(msg.srcUrl, msg.result, true).then((r) => render(img, r));
      sendResponse(true);
    } else if (msg.type === "is-reveal") {
      for (const [img, rec] of balloons) if (srcOf(img) === msg.url && rec.ok) { rec.setCollapsed(false); img.scrollIntoView({ block: "center", behavior: "smooth" }); setTimeout(() => place(rec), 600); }
      sendResponse(true);
    }
    return false;
  });

  // ---- auto-scan ----
  let settings = { autoScan: true, minSize: 200, deepAuto: false };
  const scanned = new WeakMap(); // img -> url scanned
  const pending = [];
  let busy = false, observer = null, timer = 0;

  function candidates() {
    const out = [];
    for (const img of document.images) {
      const url = srcOf(img);
      if (!url || scanned.get(img) === url || balloons.has(img)) continue;
      if (!img.complete || img.naturalWidth < settings.minSize || img.naturalHeight < settings.minSize) continue;
      if (/\.svg(\?|#|$)/i.test(url) || url.startsWith("data:image/svg")) continue;
      scanned.set(img, url);
      out.push(img);
    }
    return out;
  }

  async function pump() {
    if (busy) return;
    busy = true;
    while (settings.autoScan && pending.length) {
      const img = pending.shift(), url = srcOf(img);
      let r;
      try {
        r = await chrome.runtime.sendMessage({ type: "is-scan", url });
        r = await finish(url, r, settings.deepAuto);
      } catch (e) { r = null; }
      if (r && r.ok) render(img, r); // auto-scan stays silent on images without a payload
    }
    busy = false;
  }

  function scan() {
    if (!settings.autoScan) return;
    pending.push(...candidates());
    pump();
  }

  const schedule = () => { clearTimeout(timer); timer = setTimeout(scan, 700); };
  document.addEventListener("load", (e) => { if (settings.autoScan && e.target instanceof HTMLImageElement) schedule(); }, true);

  function applySettings() {
    if (settings.autoScan) {
      scan();
      if (!observer) {
        observer = new MutationObserver(schedule);
        observer.observe(document.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: ["src", "srcset"] });
      }
    } else if (observer) {
      observer.disconnect(); observer = null; pending.length = 0;
    }
  }

  chrome.storage.local.get(settings, (s) => { settings = { ...settings, ...s }; applySettings(); });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    for (const k of Object.keys(changes)) settings[k] = changes[k].newValue;
    applySettings();
  });
})();
