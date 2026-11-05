#!/bin/bash
# InfoStyling imagemagick installer for macOS. Double-click to run.
cd "$(dirname "$0")" || exit 1
HERE="$PWD"
msg(){ osascript -e 'on run argv' -e 'display dialog (item 1 of argv) buttons {"OK"} default button "OK" with title "InfoStyling" with icon note' -e 'end run' "$1" >/dev/null 2>&1; }
ask(){ osascript -e 'on run argv' -e 'display dialog (item 1 of argv) buttons {"Cancel", (item 2 of argv)} default button 2 with title "InfoStyling" with icon note' -e 'end run' "$1" "$2" >/dev/null 2>&1; }
fail(){ echo; echo "NOT INSTALLED: $1"; msg "NOT INSTALLED: $1"; echo; read -r -p "Press Return to close this window." _; exit 1; }
finish(){ echo; echo "$1"; msg "$1"; echo; read -r -p "Press Return to close this window." _; exit 0; }
running(){ [ "$(osascript -e "application id \"$1\" is running" 2>/dev/null)" = "true" ]; }
V="0.13.0"
echo "InfoStyling for ImageMagick $V installer"; echo
P="$HERE/InfoStyling_ImageMagick"
[ -f "$P/infostyling-magick.js" ] || fail "The InfoStyling_ImageMagick folder is missing from this folder. Download the installer again."
ask "This installs InfoStyling for ImageMagick $V.

If ImageMagick, Node or Homebrew are missing, it installs them too (this needs the internet and may ask for your Mac password)." "Install" || { echo "Cancelled."; exit 0; }
B=""; for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && { B="$b"; break; }; done
if [ -z "$B" ] && { ! command -v magick >/dev/null 2>&1 && ! command -v convert >/dev/null 2>&1 || ! command -v node >/dev/null 2>&1; }; then
  echo "1. Installing Homebrew (it installs ImageMagick and Node)."
  echo "   Type your Mac password and press Return. Nothing shows while you type."
  sudo -v || fail "Your Mac password was not accepted, so Homebrew could not be installed."
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || fail "Homebrew did not install. The messages above say why."
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && { B="$b"; break; }; done
  [ -n "$B" ] || fail "Homebrew did not install. The messages above say why."
else
  echo "1. Homebrew: $( [ -n "$B" ] && echo "found $B" || echo "not needed" )"
fi
if [ -n "$B" ]; then
  eval "$("$B" shellenv)"
  L="eval \"\$($B shellenv)\""
  grep -qF "$L" ~/.zshrc 2>/dev/null || echo "$L" >> ~/.zshrc
fi
echo "2. Checking ImageMagick and Node..."
NEED=""
command -v magick >/dev/null 2>&1 || command -v convert >/dev/null 2>&1 || NEED="imagemagick"
command -v node >/dev/null 2>&1 || NEED="$NEED node"
if [ -n "$NEED" ]; then
  echo "   Installing:$NEED"
  "$B" install $NEED || fail "Homebrew could not install$NEED. The messages above say why."
fi
command -v node >/dev/null 2>&1 || fail "Node is still missing."
command -v magick >/dev/null 2>&1 || command -v convert >/dev/null 2>&1 || fail "ImageMagick is still missing."
echo "3. Copying the tool to ~/InfoStyling_ImageMagick"
rm -rf ~/InfoStyling_ImageMagick
cp -R "$P" ~/InfoStyling_ImageMagick || fail "Could not copy the tool to your home folder."
xattr -dr com.apple.quarantine ~/InfoStyling_ImageMagick 2>/dev/null
echo "4. Adding the infostyling command"
grep -q 'alias infostyling=' ~/.zshrc 2>/dev/null || echo 'alias infostyling="node ~/InfoStyling_ImageMagick/infostyling-magick.js"' >> ~/.zshrc
echo "5. Testing: hiding and reading text in a test picture..."
TD=$(mktemp -d)
if command -v magick >/dev/null 2>&1; then M=magick; else M=convert; fi
"$M" -size 1200x800 plasma:fractal "$TD/test.png" || fail "ImageMagick could not make a test picture."
node ~/InfoStyling_ImageMagick/infostyling-magick.js hide "$TD/test.png" --look invisible --text "InfoStyling installer test" --out "$TD/test_out.jpg" || fail "The test hide did not work. The messages above say why."
node ~/InfoStyling_ImageMagick/infostyling-magick.js read "$TD/test_out.jpg" --save "$TD/read.txt" >/dev/null || fail "The test read did not work."
grep -q "InfoStyling installer test" "$TD/read.txt" || fail "The test picture did not read back correctly."
rm -rf "$TD"
echo "   Test passed."
finish "InfoStyling for ImageMagick $V is installed and tested.

Open a NEW Terminal window and type:
infostyling --help"
