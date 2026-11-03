"use strict";
document.getElementById("decodeFile").onclick = () => chrome.tabs.create({ url: chrome.runtime.getURL("decode.html") }).then(() => window.close());
const DEFAULTS = { autoScan: true, minSize: 200, deepAuto: false };
chrome.storage.local.get(DEFAULTS, (s) => {
  for (const k of ["autoScan", "deepAuto"]) {
    const el = document.getElementById(k);
    el.checked = !!s[k];
    el.onchange = () => chrome.storage.local.set({ [k]: el.checked });
  }
  const min = document.getElementById("minSize");
  min.value = s.minSize;
  min.onchange = () => chrome.storage.local.set({ minSize: Math.max(32, Number(min.value) || DEFAULTS.minSize) });
});

chrome.tabs.query({ active: true, currentWindow: true }, async ([tab]) => {
  if (!tab) return;
  const area = chrome.storage.session || chrome.storage.local, k = `found:${tab.id}`;
  const list = (await area.get(k))[k] || [];
  if (!list.length) return;
  const ul = document.getElementById("found");
  ul.textContent = "";
  for (const item of list) {
    const li = document.createElement("li"), b = document.createElement("b"), span = document.createElement("span");
    b.textContent = item.mode;
    span.textContent = item.preview;
    li.append(b, span);
    li.title = "Show on page";
    li.onclick = () => chrome.tabs.sendMessage(tab.id, { type: "is-reveal", url: item.url }, { frameId: item.frameId || 0 }).then(() => window.close(), () => {});
    ul.append(li);
  }
});
