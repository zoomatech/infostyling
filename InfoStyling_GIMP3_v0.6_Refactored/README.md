# InfoStyling GIMP 3 v0.6 — Refactored from v0.5

This build refactors the v0.5 Python plug-in without changing the ISB3 carrier format. Image processing is separated from GIMP procedure/UI code so the codec and signal-processing modules can be tested independently.

## Architecture

- `infostyling/core/codec.py` — ISB3 framing, CRC, convolutional/Viterbi codec
- `infostyling/core/mathutil.py` — reusable numerical/noise/color primitives
- `infostyling/core/style.py` — seven visible style engines
- `infostyling/core/layout.py` — pilot/interleaving layout and capacity
- `infostyling/core/carrier.py` — carrier render/scan, pilot detection and crop/grid recovery
- `infostyling/core/geometry.py` — rotation, homography, perspective and lens transforms
- `infostyling/core/decoder.py` — blind and camera decode orchestration
- `infostyling/core/__init__.py` — small public façade used by the plug-in
- `infostyling/config.py` — declarative procedure/profile parameter definitions
- `infostyling/gimp_host.py` — GIMP/GEGL adapter helpers
- `infostyling/infostyling.py` — procedure orchestration and registration

GIMP's current developer guidance distinguishes organizational plug-in code from intensive image processing; this refactor keeps that boundary explicit. A future production-speed implementation can replace the pure-Python pixel core with a compiled GEGL operation without rewriting the procedure/UI layer.

## Validation

- Python modules compile with `py_compile`
- exact ISB3 frame bits match v0.5
- blind encode/decode raster roundtrip passes
- camera identity rectification passes
- rotated-image camera correction passes
- cross-language Photoshop↔GIMP raster decode passes both directions

## Install

Copy the `infostyling` folder into the GIMP 3 plug-ins directory and ensure `infostyling.py` is executable on macOS/Linux. Restart GIMP; actions appear under **Filters > Artistic**.
