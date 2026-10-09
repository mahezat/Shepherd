"""Build the report page into docs/ (GitHub Pages: Settings -> Pages -> main /docs).

    python3 scripts/build_site.py

Copies web/index.html, the clips, and a poster frame per clip. Run the agent first
so docs/report.json exists.
"""
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
(DOCS / "clips").mkdir(parents=True, exist_ok=True)
(DOCS / "thumbs").mkdir(exist_ok=True)
page = (ROOT / "web" / "index.html").read_text()
# GitHub Pages serves the file as-is, so give it a full document skeleton.
(DOCS / "index.html").write_text(
    '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
    '<style>body{margin:0}</style></head><body>\n' + page + '\n</body></html>\n')
for clip in sorted((ROOT / "clips").glob("*.mp4")):
    shutil.copy(clip, DOCS / "clips" / clip.name)
    poster = DOCS / "thumbs" / (clip.stem + ".jpg")
    if not poster.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1", "-i", str(clip), "-frames:v", "1",
                        "-vf", "scale=640:-1", "-q:v", "4", str(poster)], check=True)
print("built", DOCS)
