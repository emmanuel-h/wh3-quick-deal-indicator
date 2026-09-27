# Publishing on the Steam Workshop

The mod is published as Workshop item **3809162317**:
https://steamcommunity.com/sharedfiles/filedetails/?id=3809162317

The game's own mod manager (TWMM) can't upload mods, and the Steam website can't create
or update Workshop files. Uploads go through **workshopper**, the Steam uploader that
ships with [Runcher](https://github.com/Frodo45127/runcher) (community tool by the RPFM
author).

## One-time setup

1. Download Runcher from https://github.com/Frodo45127/runcher/releases (the
   `...-windows-msvc.zip`) and extract it. It's already in
   `E:\Tools\runcher\runcher-release-assets\` on this PC. If you put it elsewhere, set
   the `WORKSHOPPER` environment variable to the full path of `workshopper.exe`.
2. Python 3.14+ (see [DEBUG.md](../DEBUG.md) section 3 for how to install it).
3. Steam must be **running and logged in** with the account that owns the item.

## Publishing a new version

1. Make sure the tests pass and the version number in
   `mod/script/campaign/mod/quick_deal_indicator.lua` (`VERSION`) is updated.
2. If the features changed, update `workshop/description.bbcode` (it replaces the
   Workshop description on every upload).
3. Open a terminal in the repository and run:

   ```powershell
   python tools/workshop_upload.py update "1.0.1: what changed"
   ```

   The script builds the pack, puts it in `build/workshop/` next to a copy of
   `workshop/quick_deal_indicator.png` (the preview), and calls workshopper.
4. Wait about a minute (workshopper waits 60 s before exiting). The last line must be
   `RESULT: uploaded`. In the log, a successful upload looks like this (the
   "Invalid UpdateStatus" line is normal):

   ```
   [INFO] Copying pack and preview from ...
   [INFO] Uploading content of size: ...
   [INFO] Committing changes...
   [INFO] Invalid UpdateStatus. This is an error, or the upload finished.
   [INFO] Uploaded item with id PublishedFileId(3809162317)
   ```

5. Tag the version on GitHub and attach the pack to a release (see the README).

## What the upload sets

| Field | Value |
|---|---|
| Game | 1142710 (WARHAMMER III) |
| Title | Quick Deal Indicator |
| Description | `workshop/description.bbcode` (Steam BBCode) |
| Preview | `workshop/quick_deal_indicator.png` (256×256, must sit next to the pack with the same name) |
| Tags | `mod,ui` (workshopper keeps `mod` first and at most 2 tags; WH3 categories are `graphical, campaign, units, battle, ui, maps, overhaul, compilation, cheat`) |
| Changelog | the text you pass to the script |

Visibility is changed on the Workshop page (**Change visibility** in the right column):
Public, Friends-only, Hidden or Unlisted. Updates keep the current visibility.

## Creating a brand-new item (only if the current one is lost)

```powershell
python tools/workshop_upload.py upload "1.0.0: first release" 2
```

The last number is the visibility: 0 public, 1 friends only, 2 private, 3 unlisted.
The log shows `Published item with id PublishedFileId(<new id>)`: put that id in
`PUBLISHED_FILE_ID` in `tools/workshop_upload.py` and in this file.

## Workshop copy vs local copy

Uploading subscribes you to the item, so Steam downloads it into
`steamapps\workshop\content\1142710\3809162317\`. If a local
`data\quick_deal_indicator.pack` exists too, the launcher can list the mod twice: keep
only one ticked (the local one while developing, the Workshop one to check what players
get).
