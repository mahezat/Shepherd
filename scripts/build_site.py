"""Build the report page into docs/ (GitHub Pages: Settings -> Pages -> main /docs).

    python3 scripts/build_site.py

Copies web/index.html, the clips, and a poster frame per clip. Run the agent first
so docs/report.json exists.
"""
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://mahezat.github.io/Shepherd/"
DESC = "Shepherd reads every clip a farm camera records and tells the farmer what matters. 16 real coop clips: 1 rooster fight found, 1 laying session, 9 filtered."
# One place for page metadata (title lives in web/index.html): description, theme, home-screen app, share card.
HEAD = (f'<meta name="description" content="{DESC}">'
        '<meta name="theme-color" content="#eef2ea" media="(prefers-color-scheme: light)">'
        '<meta name="theme-color" content="#0d1510" media="(prefers-color-scheme: dark)">'
        f'<link rel="canonical" href="{SITE}">'
        '<link rel="icon" type="image/png" href="favicon.png">'
        '<link rel="apple-touch-icon" href="apple-touch-icon.png">'
        '<link rel="manifest" href="manifest.webmanifest">'
        '<meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-title" content="Shepherd">'
        '<meta name="apple-mobile-web-app-status-bar-style" content="default">'
        '<meta property="og:type" content="website">'
        '<meta property="og:title" content="Shepherd: the morning report for your flock">'
        f'<meta property="og:description" content="{DESC}">'
        f'<meta property="og:url" content="{SITE}">'
        f'<meta property="og:image" content="{SITE}img/report.png">'
        '<meta name="twitter:card" content="summary_large_image">')
DOCS = ROOT / "docs"
(DOCS / "clips").mkdir(parents=True, exist_ok=True)
(DOCS / "thumbs").mkdir(exist_ok=True)
page = (ROOT / "web" / "index.html").read_text()
# GitHub Pages serves the file as-is, so give it a full document skeleton.
(DOCS / "index.html").write_text(
    '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
    + HEAD + '<style>body{margin:0}</style></head><body>\n' + page + '\n</body></html>\n')
for icon in ("apple-touch-icon.png", "icon-512.png", "favicon.png"):
    shutil.copy(ROOT / "web" / icon, DOCS / icon)
(DOCS / "manifest.webmanifest").write_text(json.dumps({
    "name": "Shepherd", "short_name": "Shepherd", "start_url": ".", "display": "standalone",
    "background_color": "#eef2ea", "theme_color": "#15241b",
    "icons": [{"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
              {"src": "apple-touch-icon.png", "sizes": "180x180", "type": "image/png"}]}, indent=1))
for clip in sorted((ROOT / "clips").glob("*.mp4")):
    shutil.copy(clip, DOCS / "clips" / clip.name)
    poster = DOCS / "thumbs" / (clip.stem + ".jpg")
    if not poster.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1", "-i", str(clip), "-frames:v", "1",
                        "-vf", "scale=640:-1", "-q:v", "4", str(poster)], check=True)
print("built", DOCS)
