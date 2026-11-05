# InfoStyling installers for macOS (0.13.0)

Double-click installers for each plugin. Each download is one zip:

| Zip | Contains |
|---|---|
| `InfoStyling_Photoshop_Installer_0.13.0.zip` | `Install InfoStyling for Photoshop.command` + `InfoStyling_v0.13.0.ccx` |
| `InfoStyling_Chrome_Installer_0.13.0.zip` | `Install InfoStyling for Chrome.command` + `InfoStyling_Decoder/` |
| `InfoStyling_GIMP_Installer_0.13.0.zip` | `Install InfoStyling for GIMP.command` + `infostyling/` |
| `InfoStyling_ImageMagick_Installer_0.13.0.zip` | `Install InfoStyling for ImageMagick.command` + `InfoStyling_ImageMagick/` |

The plugin files inside each zip are the released 0.13.0 files, unchanged.

What each installer does:

- **Photoshop**: closes Photoshop, removes the old InfoStyling plugin, installs the .ccx with Adobe's Unified Plugin Installer Agent, checks the plugin list, reopens Photoshop.
- **Chrome**: copies `InfoStyling_Decoder` into the folder Chrome already loads it from (or `~/InfoStyling_Decoder` the first time), opens `chrome://extensions` and shows the last clicks (Load unpacked the first time, Reload after that). Chrome 137+ no longer lets outside programs load an extension, so those clicks stay manual until the Chrome Web Store listing is live.
- **GIMP**: closes GIMP, copies `infostyling` into `~/Library/Application Support/GIMP/3.x/plug-ins/` for each GIMP 3 version found, reopens GIMP.
- **ImageMagick**: installs Homebrew, ImageMagick and Node if missing, copies the tool to `~/InfoStyling_ImageMagick`, adds the `infostyling` command to `~/.zshrc`, then hides and reads a test message to prove it works.

The installers are not signed by Apple, so the first time macOS shows a warning. Open **System Settings > Privacy & Security**, scroll down, click **Open Anyway** next to the installer's name, then enter your Mac password.
