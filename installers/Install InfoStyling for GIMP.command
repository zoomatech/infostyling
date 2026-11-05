#!/bin/bash
# InfoStyling gimp installer for macOS. Double-click to run.
cd "$(dirname "$0")" || exit 1
HERE="$PWD"
msg(){ osascript -e 'on run argv' -e 'display dialog (item 1 of argv) buttons {"OK"} default button "OK" with title "InfoStyling" with icon note' -e 'end run' "$1" >/dev/null 2>&1; }
ask(){ osascript -e 'on run argv' -e 'display dialog (item 1 of argv) buttons {"Cancel", (item 2 of argv)} default button 2 with title "InfoStyling" with icon note' -e 'end run' "$1" "$2" >/dev/null 2>&1; }
fail(){ echo; echo "NOT INSTALLED: $1"; msg "NOT INSTALLED: $1"; echo; read -r -p "Press Return to close this window." _; exit 1; }
finish(){ echo; echo "$1"; msg "$1"; echo; read -r -p "Press Return to close this window." _; exit 0; }
running(){ [ "$(osascript -e "application id \"$1\" is running" 2>/dev/null)" = "true" ]; }
V="0.13.0"
echo "InfoStyling GIMP plugin $V installer"; echo
P="$HERE/infostyling"
[ -f "$P/infostyling.py" ] || fail "The infostyling folder is missing from this folder. Download the installer again."
APP=$(ls -d /Applications/GIMP*.app "$HOME/Applications/"GIMP*.app 2>/dev/null | head -1)
G="$HOME/Library/Application Support/GIMP"
VERS=""
if [ -n "$APP" ]; then
  AV=$(defaults read "$APP/Contents/Info" CFBundleShortVersionString 2>/dev/null)
  case "$AV" in 3.*) VERS="$(echo "$AV" | cut -d. -f1-2)";; esac
fi
for d in "$G"/3.*; do [ -d "$d" ] && VERS="$VERS $(basename "$d")"; done
VERS=$(echo $VERS | tr ' ' '\n' | sort -u | tr '\n' ' ')
[ -n "${VERS// /}" ] || fail "GIMP 3 was not found. Install GIMP 3 from gimp.org, open it once, quit it, then double-click this installer again."
ask "This installs the InfoStyling GIMP plugin $V.

GIMP will be closed first. Save your work before you click Install." "Install" || { echo "Cancelled."; exit 0; }
echo "1. Closing GIMP..."
if pgrep -f "GIMP[^/]*\.app/Contents/MacOS" >/dev/null; then
  [ -n "$APP" ] && osascript -e "tell application \"$(basename "$APP" .app)\" to quit" >/dev/null 2>&1
  for i in $(seq 1 120); do pgrep -f "GIMP[^/]*\.app/Contents/MacOS" >/dev/null || break; sleep 1; done
  pgrep -f "GIMP[^/]*\.app/Contents/MacOS" >/dev/null && fail "GIMP did not close. Close GIMP, then double-click this installer again."
fi
n=1
for v in $VERS; do
  n=$((n+1)); D="$G/$v/plug-ins"
  echo "$n. Installing into GIMP $v: $D/infostyling"
  mkdir -p "$D" || fail "Could not create $D"
  rm -rf "$D/infostyling"
  cp -R "$P" "$D/infostyling" || fail "Could not copy the plugin into $D"
  chmod 755 "$D/infostyling" "$D/infostyling/iscore" "$D/infostyling/infostyling.py"
  xattr -dr com.apple.quarantine "$D/infostyling" 2>/dev/null
  diff -rq "$P" "$D/infostyling" >/dev/null || fail "The copy in $D/infostyling does not match. Try again."
done
[ -n "$APP" ] && { echo "Opening GIMP..."; open "$APP"; }
finish "InfoStyling GIMP plugin $V is installed.

In GIMP open a picture, then choose Filters > InfoStyling..."
