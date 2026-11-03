"use strict";
// Decodes a file the user picks or drops. Local files never reach the extension through file:// URLs, so this page is the local-file path.
const $ = (id) => document.getElementById(id);
const drop = $("drop"), input = $("file"), status = $("status"), meta = $("meta"), out = $("out"), textEl = $("text");
let lastText = "", lastName = "message";

function setStatus(msg, err) { status.hidden = false; status.textContent = msg; status.className = err ? "err" : ""; }

async function pixelsFromBlob(blob) {
  const bmp = await createImageBitmap(blob, { colorSpaceConversion: "none", premultiplyAlpha: "none" });
  const c = new OffscreenCanvas(bmp.width, bmp.height);
  const g = c.getContext("2d", { willReadFrequently: true });
  g.drawImage(bmp, 0, 0);
  bmp.close();
  return g.getImageData(0, 0, c.width, c.height);
}

async function decodeFile(file) {
  if (!file) return;
  lastName = file.name.replace(/\.[^.]+$/, "") || "message";
  out.hidden = true; meta.textContent = "";
  setStatus(`Decoding ${file.name}…`);
  await new Promise((r) => setTimeout(r, 30));
  try {
    const img = await pixelsFromBlob(file);
    const r = InfoStylingCore.decodePixels(img.data, img.width, img.height, { deep: $("deep").checked });
    if (r && r.ok) {
      if (r.seal) setStatus(`${r.seal.line} (${r.mode})`, r.seal.status !== "ok"); else setStatus(`Hidden message · ${r.mode}`);
      meta.textContent = `${file.name} · ${r.detail} · ${r.width}×${r.height} px · ${(r.ms / 1000).toFixed(1)} s`;
      lastText = r.text; textEl.textContent = r.text; out.hidden = false;
    } else {
      setStatus("No hidden message found", true);
      meta.textContent = `${file.name} · ${(r && (r.robustError ? `${r.error} (${r.robustError})` : r.error)) || "Unknown error"}`;
    }
  } catch (e) {
    setStatus("Could not read this image", true);
    meta.textContent = `${file.name} · ${e.message}`;
  }
}

drop.onclick = () => input.click();
drop.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } };
input.onchange = () => { decodeFile(input.files[0]); input.value = ""; };
for (const t of ["dragenter", "dragover"]) drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("over"); });
for (const t of ["dragleave", "drop"]) drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.remove("over"); });
drop.addEventListener("drop", (e) => decodeFile(e.dataTransfer.files[0]));
// Dropping outside the box should not navigate away from the page.
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => { e.preventDefault(); if (e.target !== drop) decodeFile(e.dataTransfer.files[0]); });

$("copy").onclick = () => navigator.clipboard.writeText(lastText);
$("save").onclick = () => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([lastText], { type: "text/plain" }));
  a.download = `${lastName}_hidden.txt`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};

const hint = new URLSearchParams(location.search).get("from");
if (hint) setStatus(`Chrome blocks extensions from reading ${decodeURIComponent(hint.split("/").pop())} on a file:// page. Choose that file here to decode it.`);
