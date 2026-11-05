#!/bin/bash
# InfoStyling chrome installer for macOS. Double-click to run.
cd "$(dirname "$0")" || exit 1
HERE="$PWD"
msg(){ osascript -e 'on run argv' -e 'display dialog (item 1 of argv) buttons {"OK"} default button "OK" with title "InfoStyling" with icon note' -e 'end run' "$1" >/dev/null 2>&1; }
ask(){ osascript -e 'on run argv' -e 'display dialog (item 1 of argv) buttons {"Cancel", (item 2 of argv)} default button 2 with title "InfoStyling" with icon note' -e 'end run' "$1" "$2" >/dev/null 2>&1; }
fail(){ echo; echo "NOT INSTALLED: $1"; msg "NOT INSTALLED: $1"; echo; read -r -p "Press Return to close this window." _; exit 1; }
finish(){ echo; echo "$1"; msg "$1"; echo; read -r -p "Press Return to close this window." _; exit 0; }
running(){ [ "$(osascript -e "application id \"$1\" is running" 2>/dev/null)" = "true" ]; }
V="0.13.0"
echo "InfoStyling Chrome plugin $V installer"; echo
P="$HERE/InfoStyling_Decoder"
[ -f "$P/manifest.json" ] || fail "The InfoStyling_Decoder folder is missing from this folder. Download the installer again."
C="$HOME/Library/Application Support/Google/Chrome"
[ -d "/Applications/Google Chrome.app" ] || [ -d "$HOME/Applications/Google Chrome.app" ] || [ -d "$C" ] || fail "Google Chrome was not found. Install Chrome from google.com/chrome first."
# Where Chrome already loads the InfoStyling_Decoder folder from (if it was installed before)
OLD=$(grep -ho '"path": *"[^"]*InfoStyling_Decoder[^"]*"' "$C"/*/Preferences "$C"/*/"Secure Preferences" 2>/dev/null | sed -e 's/^"path": *"//' -e 's/"$//' -e 's#\\/#/#g' | while read -r p; do [ -f "$p/manifest.json" ] && echo "$p"; done | head -1)
if [ -n "$OLD" ]; then T="$OLD"; else T="$HOME/InfoStyling_Decoder"; fi
ask "This installs the InfoStyling Chrome plugin $V into:
$T" "Install" || { echo "Cancelled."; exit 0; }
if [ -d "$T" ] && [ -n "$(ls -A "$T" 2>/dev/null)" ] && ! grep -q '"name": "InfoStyling Decoder"' "$T/manifest.json" 2>/dev/null; then fail "$T already holds other files. Move them, then run this installer again."; fi
echo "1. Copying the plugin to $T"
mkdir -p "$T" || fail "Could not create $T"
find "$T" -mindepth 1 -delete 2>/dev/null
cp -R "$P/." "$T/" || fail "Could not copy the plugin to $T"
xattr -dr com.apple.quarantine "$T" 2>/dev/null
diff -rq "$P" "$T" >/dev/null || fail "The copy in $T does not match. Try again."
grep -q "\"version\": \"$V\"" "$T/manifest.json" || fail "The copied plugin is not version $V."
echo "2. Opening Chrome's Extensions page..."
printf '%s' "$T" | pbcopy
osascript -e 'tell application "Google Chrome"' -e 'activate' -e 'if (count of windows) = 0 then make new window' -e 'set URL of active tab of front window to "chrome://extensions"' -e 'end tell' >/dev/null 2>&1 || open -a "Google Chrome"
if [ -n "$OLD" ]; then
  finish "InfoStyling Chrome plugin $V is copied into the folder Chrome already uses.

Last step, in Chrome's Extensions page (chrome://extensions):
click the round reload arrow on the InfoStyling Decoder card. It then shows 0.13.0."
else
  finish "InfoStyling Chrome plugin $V is copied to your home folder (InfoStyling_Decoder). Do not move or delete that folder.

Last steps, in Chrome's Extensions page (chrome://extensions):
1. Turn on Developer mode (top right).
2. Click Load unpacked (top left).
3. Press Command+Shift+G, then Command+V, then Return. (The folder's location is already copied.)
4. Click Select.
5. On the InfoStyling Decoder card click Details, then turn on Allow access to file URLs.
6. Click the puzzle-piece icon in Chrome's toolbar and pin InfoStyling Decoder."
fi
