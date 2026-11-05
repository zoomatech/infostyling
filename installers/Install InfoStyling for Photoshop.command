#!/bin/bash
# InfoStyling photoshop installer for macOS. Double-click to run.
cd "$(dirname "$0")" || exit 1
HERE="$PWD"
msg(){ osascript -e 'on run argv' -e 'display dialog (item 1 of argv) buttons {"OK"} default button "OK" with title "InfoStyling" with icon note' -e 'end run' "$1" >/dev/null 2>&1; }
ask(){ osascript -e 'on run argv' -e 'display dialog (item 1 of argv) buttons {"Cancel", (item 2 of argv)} default button 2 with title "InfoStyling" with icon note' -e 'end run' "$1" "$2" >/dev/null 2>&1; }
fail(){ echo; echo "NOT INSTALLED: $1"; msg "NOT INSTALLED: $1"; echo; read -r -p "Press Return to close this window." _; exit 1; }
finish(){ echo; echo "$1"; msg "$1"; echo; read -r -p "Press Return to close this window." _; exit 0; }
running(){ [ "$(osascript -e "application id \"$1\" is running" 2>/dev/null)" = "true" ]; }
V="0.13.0"
echo "InfoStyling Photoshop plugin $V installer"; echo
I="/Library/Application Support/Adobe/Adobe Desktop Common/RemoteComponents/UPI/UnifiedPluginInstallerAgent/UnifiedPluginInstallerAgent.app/Contents/MacOS/UnifiedPluginInstallerAgent"
F="$HERE/InfoStyling_v$V.ccx"
[ -f "$F" ] || fail "InfoStyling_v$V.ccx is missing from this folder. Download the installer again."
[ -x "$I" ] || fail "The Adobe plugin installer was not found. Install Adobe Creative Cloud and Photoshop first."
ask "This installs the InfoStyling Photoshop plugin $V.

Photoshop will be closed first. Save your work before you click Install." "Install" || { echo "Cancelled."; exit 0; }
echo "1. Closing Photoshop..."
if running com.adobe.Photoshop; then
  osascript -e 'tell application id "com.adobe.Photoshop" to quit' >/dev/null 2>&1
  for i in $(seq 1 120); do running com.adobe.Photoshop || break; sleep 1; done
  running com.adobe.Photoshop && fail "Photoshop did not close. Close Photoshop, then double-click this installer again."
fi
echo "2. Removing the old InfoStyling plugin (if any)..."
"$I" --remove "InfoStyling"
echo "3. Installing InfoStyling $V..."
"$I" --install "$F"
echo "4. Checking..."
L=$("$I" --list all 2>&1)
echo "$L" | grep -i -A2 infostyl
echo "$L" | grep -qi infostyl || fail "Photoshop's plugin list does not show InfoStyling. The messages above say why."
echo "5. Opening Photoshop..."
open -b com.adobe.Photoshop
finish "InfoStyling Photoshop plugin $V is installed.

In Photoshop choose Plugins > InfoStyling."
