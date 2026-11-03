# InfoStyling Decoder 0.7.0 (Chrome MV3, Safari-convertible)

Finds and shows hidden InfoStyling text in web images.

- **Auto-scan** (on by default): images of at least 200 px are scanned. When a hidden message is found, the toolbar icon shows a red count badge and the text appears in a comic speech balloon over the image. Click × to shrink it to a 💬 chip, and click the chip to open it again.
- **Right-click → Decode InfoStyling** on any image runs a full decode, including the slower deep scan, and always shows a result.
- **Toolbar popup**: lists the messages found on the current page (click one to jump to it) and has the settings (auto-scan, minimum size, deep scan while auto-scanning).
- **Decode order**: High capacity (LSB + deflate) first, then Robust ISB3. Robust tries a scale search first, so it still reads images that were resized after encoding. With deep scan on, it then runs the plugin's full `decodeBlind`.
- **Cross-origin images**: the service worker fetches them using its host permissions, then decodes on an `OffscreenCanvas`, so the page's canvas never gets tainted. `blob:` images, and browsers whose worker has no `OffscreenCanvas`, are decoded in the page instead.

## Install

See `INSTALL_STEPS.md` for complete step-by-step instructions: Chrome, a temporary Safari install, a permanent Safari install with Xcode, and encoding settings.

## Files

| File | Purpose |
|---|---|
| `manifest.json` | MV3 manifest |
| `background.js` | Context menu, cross-origin fetch, decode, toolbar badge |
| `content.js` | Speech balloon, auto-scan, local fallback decode |
| `popup.html/js` | Found-messages list and settings |
| `lib/infostyling-core.js` | Bundle of the plugin's decoder modules (`core/codec, math, layout, carrier, geometry, decoder, dense`, pako), plus the web-only `core/fractional.js` scale search |
