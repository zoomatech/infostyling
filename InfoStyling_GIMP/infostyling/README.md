# InfoStyling for GIMP 3 (v0.14.0)

Hide text inside an image, then read it back. This is the GIMP version of the InfoStyling Photoshop plugin v0.14.0:
the same 11 looks, the same Shareable (JPEG) and Full resolution (PNG) sizes, the same compression (built-in English
lexicon) and the same signed seal. Images it makes are read by the InfoStyling Chrome plugin 0.14.0 and the
Photoshop plugin v0.14.0, and it reads theirs.

Open it from **Filters > InfoStyling…** with an RGB image open.

## Files

- `infostyling.py` — the GIMP plug-in and its panel
- `iscore/` — the InfoStyling engine, ported line for line from the Photoshop plugin's `core/` folder
- `iscore/lexicon.bin` — the built-in English lexicon (must never be edited)

## Notes

- Written in plain Python, so it needs nothing beyond GIMP 3. Large images take longer than in Photoshop
  (a painterly look on a 4000 × 2200 px image takes a few minutes).
- The first time you hide or read text, GIMP spends about 30 seconds learning the built-in lexicon, then keeps
  it in `infostyling/infostyling_lexicon_model.bin` inside the GIMP settings folder, so later runs start at once.
- Your signing key is kept in `infostyling/sealkey.txt` inside the GIMP settings folder. It is a different key from
  your Photoshop plugin's key, so it shows a different key ID.
