# InfoStyling for ImageMagick 0.13.0

The Photoshop plugin v0.13.0, as a Terminal tool that uses ImageMagick to open and save pictures.
Same 11 looks, Shareable (JPEG) and Full resolution (PNG), same compression, same signed seal.
Pictures it makes read in the Chrome plugin 0.13.0 and the Photoshop plugin 0.13.0.

The hiding, reading, compression and seal code is the Photoshop plugin's own `core/`, `lib/`,
`config.js` and `engine.js`, copied unchanged. Only `infostyling-magick.js` is new.

## Install on a Mac (once)

1. Open **Terminal** (Applications > Utilities > Terminal).
2. If you do not have Homebrew yet, paste this and press Return (it asks for your Mac password):

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

3. Install ImageMagick and Node (Node runs the tool):

```
brew install imagemagick node
```

4. Put the tool in place. Download `InfoStyling_ImageMagick_0.13.0.zip`, then paste:

```
cd ~/Downloads
[ -f InfoStyling_ImageMagick_0.13.0.zip ] && [ ! -d InfoStyling_ImageMagick ] && unzip -oq InfoStyling_ImageMagick_0.13.0.zip
rm -rf ~/InfoStyling_ImageMagick
cp -R "$(dirname "$(find ~/Downloads -maxdepth 3 -name infostyling-magick.js | head -1)")" ~/InfoStyling_ImageMagick
grep -q 'alias infostyling=' ~/.zshrc 2>/dev/null || echo 'alias infostyling="node ~/InfoStyling_ImageMagick/infostyling-magick.js"' >> ~/.zshrc
source ~/.zshrc
infostyling --help
```

## Use

Hide text (Shareable JPEG, signed):

```
infostyling hide ~/Pictures/photo.jpg --look invisible --text "Your text here" --sign "Steve"
```

Hide a whole book (Full resolution PNG):

```
infostyling hide ~/Pictures/photo.jpg --look engraving --size full --file ~/Documents/book.txt
```

Read hidden text:

```
infostyling read ~/Pictures/photo_invisible.jpg
```

See how much text each look holds in a picture:

```
infostyling space ~/Pictures/photo.jpg --text "Your text here"
```

Looks: `invisible`, `glyph`, `colorpop`, `tract`, `engraving`, `impressionist`, `cubist`, `surreal`,
`penskip` (Pen sketch), `stipple`, `fractal`. Run `infostyling --help` for every option
(seed, cover effects, output file, camera reading).

## Notes

- The saved file goes next to the picture as `PICTURE_LOOK.jpg` (Shareable) or `.png` (Full), unless `--out` is given.
- Every save is re-opened and read back; it prints `✓ APPLIED` and `Verified` when it reads correctly.
- Signing key: made once and kept in `~/.infostyling/sealkey`. It is a different key from the Photoshop
  plugin's, so it shows a different key ID.
- Shareable JPEGs are saved at ImageMagick quality 95 (of 100) with full color detail.
- Any picture ImageMagick opens works as input (JPEG, PNG, TIFF, HEIC, PSD, and more). Transparent areas are filled with white.
