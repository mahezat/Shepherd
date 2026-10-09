"""Third pass, run ON THE EVENT VM after vm_questions.py:

    python3 -u ~/shepherd/scripts/vm_zoom.py

Far-away action (a fight at the back fence, in infrared) is only a few dozen pixels
tall, too small for the nano Cosmos model at full frame. This cuts every clip into
4 zoomed quarters (2x2 tiles, each scaled back up to 1280x720) and asks the fight
and peck questions on each tile. Answers go to checks.fight_zoom / checks.peck_zoom.
"""
import base64
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vm_direct as v
from vm_questions import QUESTIONS, ask

TILES = {"top-left": "0:0", "top-right": "iw/2:0", "bottom-left": "0:ih/2", "bottom-right": "iw/2:ih/2",
         "center": "iw/4:ih/4"}  # center catches action that sits on a seam


def tile(clip, name, xy, out_dir):
    out = Path(out_dir) / f"{clip.stem}_{name}.mp4"
    x, y = xy.split(":")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip),
                    "-vf", f"crop=iw/2:ih/2:{x}:{y},scale=1280:720", "-an", "-q:v", "3", str(out)], check=True)
    return out


def zoom_checks(clip):
    d = tempfile.mkdtemp()
    res = {"fight_zoom": {}, "peck_zoom": {}}
    for name, xy in TILES.items():
        b64 = base64.b64encode(tile(clip, name, xy, d).read_bytes()).decode()
        res["fight_zoom"][name] = ask(b64, QUESTIONS["fight"])
        res["peck_zoom"][name] = ask(b64, QUESTIONS["peck"])
    return res


def main():
    path = v.DATA / "segments.json"
    rows = json.loads(path.read_text())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda r: zoom_checks(v.ROOT / "clips" / r["filename"]), rows))
    for i, (row, res) in enumerate(zip(rows, results), 1):
        row.setdefault("checks", {}).update(res)

        def yes_tiles(k):
            return [t for t, a in res[k].items() if (a.split() or [""])[0].strip(".,").upper() == "YES"]
        print(f"[{i}/{len(rows)}] {row['filename'][-24:-4]}  fight in: {yes_tiles('fight_zoom') or '-'}  "
              f"peck in: {yes_tiles('peck_zoom') or '-'}", flush=True)
    path.write_text(json.dumps(rows, indent=1, default=str))
    print("\nupdated data/segments.json. Next: bash ~/shepherd/scripts/vm_push.sh")


if __name__ == "__main__":
    main()
