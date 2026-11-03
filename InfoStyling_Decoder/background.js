"use strict";
// InfoStyling Decoder service worker: context menu, cross-origin image fetch (host permissions), pixel decode.
importScripts("lib/infostyling-core.js");

const MENU_ID = "infostyling-decode";
const MAX_BYTES = 60 * 1024 * 1024;
const CAN_DECODE_HERE = typeof OffscreenCanvas !== "undefined" && typeof createImageBitmap === "function";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: MENU_ID, title: "Decode InfoStyling", contexts: ["image"] });
  });
  chrome.storage.local.get({ autoScan: true, minSize: 200, deepAuto: false }, (s) => chrome.storage.local.set(s));
});

// One decode at a time keeps the worker responsive and memory bounded.
let queue = Promise.resolve();
const serial = (fn) => (queue = queue.then(fn, fn));

async function fetchImage(url, { credentials, requireImage }) {
  // file:// images are readable here only when "Allow access to file URLs" is on for this extension.
  if (/^file:/i.test(url) && !(await chrome.extension.isAllowedFileSchemeAccess())) throw Object.assign(new Error("No file access"), { noFileAccess: true });
  if (!/^(https?:|data:|file:)/i.test(url)) throw Object.assign(new Error("Local-only URL"), { local: true });
  const res = await fetch(url, { credentials, cache: "force-cache", redirect: "follow" });
  if (!res.ok) throw new Error(`Image request failed: HTTP ${res.status}`);
  const type = (res.headers.get("content-type") || "").toLowerCase();
  if (requireImage && type && !type.startsWith("image/")) throw new Error(`Not an image (${type})`);
  const len = Number(res.headers.get("content-length") || 0);
  if (len > MAX_BYTES) throw new Error("Image is larger than 60 MB");
  const blob = await res.blob();
  if (blob.size > MAX_BYTES) throw new Error("Image is larger than 60 MB");
  return blob;
}

async function pixelsFromBlob(blob) {
  // colorSpaceConversion "none" keeps the stored pixel values exact, which the High-capacity channel needs.
  const bmp = await createImageBitmap(blob, { colorSpaceConversion: "none", premultiplyAlpha: "none" });
  const c = new OffscreenCanvas(bmp.width, bmp.height);
  const g = c.getContext("2d", { willReadFrequently: true });
  g.drawImage(bmp, 0, 0);
  bmp.close();
  return g.getImageData(0, 0, c.width, c.height);
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = () => reject(r.error);
    r.readAsDataURL(blob);
  });
}

// Returns a decode result, or {local:true, dataUrl?} when the page must decode it (blob: URLs, or no OffscreenCanvas e.g. older Safari).
async function decodeUrl(url, opts) {
  let blob;
  try {
    blob = await fetchImage(url, opts);
  } catch (e) {
    if (e.local) return { local: true };
    throw e;
  }
  if (!CAN_DECODE_HERE) return { local: true, dataUrl: await blobToDataUrl(blob) };
  const img = await pixelsFromBlob(blob);
  return InfoStylingCore.decodePixels(img.data, img.width, img.height, { deep: opts.deep });
}

async function send(target, msg) {
  const opt = { frameId: target.frameId };
  try {
    return await chrome.tabs.sendMessage(target.tabId, msg, opt);
  } catch (e) {
    // Page was open before the extension was installed: inject the content script, then retry.
    await chrome.scripting.executeScript({ target: { tabId: target.tabId, frameIds: [target.frameId] }, files: ["content.js"] });
    return chrome.tabs.sendMessage(target.tabId, msg, opt);
  }
}

async function injectCore(tabId, frameId) {
  await chrome.scripting.executeScript({ target: { tabId, frameIds: [frameId || 0] }, files: ["lib/infostyling-core.js"] });
}

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== MENU_ID || !tab || !info.srcUrl) return;
  const target = { tabId: tab.id, frameId: info.frameId || 0 };
  const srcUrl = info.srcUrl;
  send(target, { type: "is-status", srcUrl, text: "Decoding…" }).catch(() => {});
  serial(async () => {
    let result;
    try {
      // srcUrl comes from the browser's own click data, so cookies may be sent to reach signed-in images.
      result = await decodeUrl(srcUrl, { credentials: "include", requireImage: false, deep: true });
      if (result.local) await injectCore(target.tabId, target.frameId);
    } catch (e) {
      result = { ok: false, error: e.message };
      if (e.noFileAccess) {
        // Without file access the image can't be read at all, so hand the user the file picker page instead.
        result.error = "Turn on \"Allow access to file URLs\" for InfoStyling Decoder in chrome://extensions, or choose the file on the tab that just opened.";
        chrome.tabs.create({ url: chrome.runtime.getURL(`decode.html?from=${encodeURIComponent(srcUrl)}`), index: tab.index + 1 });
      }
    }
    await send(target, { type: "is-result", srcUrl, result, source: "menu" }).catch(() => {});
  });
});

// ---- toolbar badge: count of images with hidden messages on each tab ----
const area = chrome.storage.session || chrome.storage.local;
const key = (tabId) => `found:${tabId}`;

async function recordFound(tabId, item) {
  const k = key(tabId);
  const list = (await area.get(k))[k] || [];
  if (!list.some((x) => x.url === item.url)) list.push(item);
  await area.set({ [k]: list });
  await chrome.action.setBadgeBackgroundColor({ tabId, color: "#d93025" });
  if (chrome.action.setBadgeTextColor) await chrome.action.setBadgeTextColor({ tabId, color: "#ffffff" });
  await chrome.action.setBadgeText({ tabId, text: String(list.length) });
  await chrome.action.setTitle({ tabId, title: `InfoStyling: ${list.length} hidden message${list.length === 1 ? "" : "s"} on this page` });
}

async function clearFound(tabId) {
  await area.remove(key(tabId));
  await chrome.action.setBadgeText({ tabId, text: "" });
  await chrome.action.setTitle({ tabId, title: "InfoStyling Decoder" });
}

chrome.tabs.onUpdated.addListener((tabId, info) => { if (info.status === "loading" && info.url) clearFound(tabId).catch(() => {}); });
chrome.tabs.onRemoved.addListener((tabId) => { area.remove(key(tabId)); });

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!sender.tab) return false;
  if (msg && msg.type === "is-found" && typeof msg.url === "string") {
    recordFound(sender.tab.id, { url: msg.url.slice(0, 2048), frameId: sender.frameId || 0, mode: String(msg.mode || ""), preview: String(msg.preview || "").slice(0, 160) })
      .then(() => sendResponse(true), () => sendResponse(false));
    return true;
  }
  if (msg && msg.type === "is-scan" && typeof msg.url === "string") {
    // URLs from content scripts: no cookies, image content-types only, and only decoded text goes back.
    chrome.storage.local.get({ deepAuto: false }, (s) => {
      serial(async () => {
        try {
          const r = await decodeUrl(msg.url, { credentials: "omit", requireImage: true, deep: !!s.deepAuto });
          if (r.local) await injectCore(sender.tab.id, sender.frameId);
          sendResponse(r);
        } catch (e) {
          sendResponse({ ok: false, error: e.message });
        }
      });
    });
    return true;
  }
  if (msg && msg.type === "is-need-core") {
    injectCore(sender.tab.id, sender.frameId).then(() => sendResponse({ ok: true }), (e) => sendResponse({ ok: false, error: e.message }));
    return true;
  }
  return false;
});
