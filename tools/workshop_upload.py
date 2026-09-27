"""Upload or update Quick Deal Indicator on the Steam Workshop with Runcher's workshopper.

usage:
    python tools/workshop_upload.py update "<changelog>"      # new version of the item
    python tools/workshop_upload.py upload "<changelog>" [visibility]   # create a new item

Steam must be running and logged in with the account that owns the item. The pack is
built from mod/, then staged in build/workshop/ next to workshop/quick_deal_indicator.png
(workshopper takes the preview from "<pack name>.png" next to the pack). Visibility for
a new item: 0 public, 1 friends only, 2 private (default), 3 unlisted. Updates keep the
item's current visibility.
"""
import base64
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSHOPPER = Path(os.environ.get(
    "WORKSHOPPER", r"E:\Tools\runcher\runcher-release-assets\workshopper.exe"))
APP_ID = "1142710"  # Total War: WARHAMMER III
PUBLISHED_FILE_ID = "3809162317"
TITLE = "Quick Deal Indicator"
TAGS = "mod,ui"


def b64(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("upload", "update"):
        raise SystemExit(__doc__)
    mode, changelog = sys.argv[1], sys.argv[2]

    stage = ROOT / "build" / "workshop"
    stage.mkdir(parents=True, exist_ok=True)
    pack = stage / "quick_deal_indicator.pack"
    subprocess.run([sys.executable, str(ROOT / "tools" / "packtool.py"), "build", str(ROOT / "mod"), str(pack)],
                   check=True)
    shutil.copy(ROOT / "workshop" / "quick_deal_indicator.png", pack.with_suffix(".png"))

    args = [str(WORKSHOPPER)]
    args += ["upload"] if mode == "upload" else ["update", "--published-file-id", PUBLISHED_FILE_ID]
    args += [
        "-b", "-s", APP_ID, "-f", str(pack),
        "-t", b64(TITLE),
        "-d", b64((ROOT / "workshop" / "description.bbcode").read_text(encoding="utf-8")),
        "-c", b64(changelog),
        "--tags", TAGS,
    ]
    if mode == "upload":
        args += ["--visibility", sys.argv[3] if len(sys.argv) > 3 else "2"]

    print("running workshopper (it waits 60 s before exiting)...", flush=True)
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    ok = "Uploaded item with id" in result.stdout
    print("RESULT:", "uploaded" if ok else "FAILED (see the log above)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
