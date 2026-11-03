# InfoStyling Decoder: complete install steps (macOS)

Sources: Apple, "Packaging a web extension for Safari", "Running your Safari web extension", and Safari User Guide "Change website access for extensions" (2026). Chrome, "Cross-origin network requests" and the `chrome.contextMenus` reference.

---

## A. Chrome

1. Download `InfoStyling_Decoder_0.7.0_chrome.zip`.
2. Open Finder and go to your Downloads folder.
3. Double-click `InfoStyling_Decoder_0.7.0_chrome.zip`. macOS creates a folder named `InfoStyling_Decoder`.
4. Move the `InfoStyling_Decoder` folder somewhere permanent, for example your home folder. Chrome loads the extension from this folder every time it starts, so if you delete or move the folder, the extension stops working.
5. Open Chrome.
6. Click the address bar, type `chrome://extensions`, and press Return.
7. Turn on the **Developer mode** switch in the top-right corner of the page.
8. Click **Load unpacked** at the top left.
9. In the file dialog, select the `InfoStyling_Decoder` folder (the one that contains `manifest.json`) and click **Select**.
10. Check that the **InfoStyling Decoder 0.7.0** card appears with no red **Errors** button.
11. Click the puzzle-piece (Extensions) icon on the right of the Chrome toolbar.
12. Click the pin icon next to **InfoStyling Decoder**. Its blue icon now stays on the toolbar, where the red count badge appears.
13. Click the InfoStyling icon and check that **Auto-scan images on pages** is ticked. It is on by default.
14. Test auto-scan: open a web page that has an InfoStyled image, at least 200 px on each side. Wait a few seconds. The toolbar icon shows a red number, and a speech balloon with the hidden text appears over the image.
15. Test right-click: right-click any image and choose **Decode InfoStyling**. A balloon says **Decoding…**, then shows the text or "No hidden message found".
16. In a balloon, click **Copy** to copy the text, **Save .txt** to download it, or **×** to shrink it to a 💬 chip. Click the chip to open the balloon again.
17. Click the toolbar icon to see the list of messages found on the page. Click an entry to scroll to its image.

**To update later:** replace the files in the `InfoStyling_Decoder` folder, open `chrome://extensions`, and click the circular-arrow reload button on the InfoStyling Decoder card.

---

## B. Safari: quick temporary install (no Xcode)

1. Do Chrome steps 1–4 to get the unzipped `InfoStyling_Decoder` folder.
2. Open Safari.
3. In the menu bar, choose **Safari > Settings…**.
4. Click the **Advanced** tab.
5. Tick **Show features for web developers**. In Safari 16 and earlier it's called **Show Develop menu in menu bar**.
6. Click the **Developer** tab, which is now visible.
7. Tick **Allow unsigned extensions**. Enter your Mac password if asked.
8. On the same **Developer** tab, click **Add Temporary Extension…**.
9. Select the `InfoStyling_Decoder` folder (or the zip) and click **Select**.
10. Safari switches to the **Extensions** tab and lists InfoStyling Decoder under **Temporary**.
11. Select **InfoStyling Decoder** in the list, and make sure its checkbox is ticked.
12. On the right, choose **Always Allow on Every Website**. It needs this to fetch and scan images on any site.
13. Close the Settings window.
14. Test with Chrome steps 14–17. The menu item is the same: right-click an image and choose **Decode InfoStyling**.

Safari removes temporary extensions after 24 hours or when you quit Safari. **Allow unsigned extensions** also resets when you quit. Repeat steps 2–13 each time.

---

## C. Safari: permanent install with Xcode (`safari-web-extension-packager`)

Apple has renamed the tool. It used to be `safari-web-extension-converter`.

1. Open the **App Store**, search for **Xcode**, and click **Get**, then **Install**.
2. Open **Xcode** once and let it finish installing its components, accepting the license if asked. Then quit Xcode.
3. Do Chrome steps 1–3, so the unzipped folder is at `~/Downloads/InfoStyling_Decoder`. If you put it somewhere else, change the path in step 6.
4. Open **Terminal** (Applications > Utilities > Terminal).
5. Create the output folder:

```bash
mkdir -p ~/Developer
```

6. Run the packager:

```bash
xcrun safari-web-extension-packager ~/Downloads/InfoStyling_Decoder \
  --project-location ~/Developer/InfoStylingSafari \
  --app-name "InfoStyling Decoder" \
  --bundle-identifier com.zoomatech.infostyling.decoder \
  --swift --macos-only --copy-resources
```

7. If the packager shows a confirmation summary, check the values and confirm.
8. Read the warnings in Terminal. They list any manifest keys Safari doesn't support, which Safari ignores.
9. Xcode opens the new project automatically. If it doesn't, open the `.xcodeproj` file inside `~/Developer/InfoStylingSafari`.
10. In Xcode's toolbar, open the **Scheme** menu next to the Run (▶) and Stop (■) buttons and select the **InfoStyling Decoder** macOS app.
11. Choose **Product > Run**, or click ▶. Xcode builds the extension, embeds it in the app, and launches the app. You can quit the app once it opens.
12. Open Safari and choose **Safari > Settings…**.
13. Click **Advanced** and tick **Show features for web developers**.
14. Click **Developer** and tick **Allow unsigned extensions**. Enter your password if asked. You need this unless the project is signed with your Apple Developer account, and it resets when you quit Safari.
15. Click the **Extensions** tab.
16. Find **InfoStyling Decoder** in the list on the left and tick its checkbox.
17. With it selected, choose **Always Allow on Every Website** on the right.
18. Close Settings.
19. Test with Chrome steps 14–17.

**To update later:** edit the files, then in Xcode choose **Product > Build**.

**To add iPhone/iPad later:** run this in Terminal, then build the iOS scheme in Xcode. Right-click menus aren't supported in iOS Safari, but auto-scan and the badge are.

```bash
xcrun safari-web-extension-packager --rebuild-project ~/Developer/InfoStylingSafari/InfoStyling\ Decoder/InfoStyling\ Decoder.xcodeproj
```

---

## D. Encoding settings that survive JPEG and resizing (Photoshop plugin, Robust mode)

1. In the InfoStyling panel, set **Encoding mode** to **Robust**.
2. Set **ISB3 carrier cell size** to **16** if the image's longest side is up to 4096 px, or **24** if it's up to 6144 px.
3. Set **ISB3 carrier strength** to **74** or higher (never below 50).
4. Apply, export, and test by right-clicking the uploaded image in Chrome.
