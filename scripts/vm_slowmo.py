"""Fourth pass, run ON THE EVENT VM after vm_zoom.py:

    python3 -u ~/shepherd/scripts/vm_slowmo.py

A peck lasts a fraction of a second, and the model samples only a few frames of a
clip, so it can fall between them. This slows every clip down 4x (so the same
moment spans 4x the frames) and asks the peck and fight questions again, on the
full frame and the 5 zoomed tiles. Answers go to checks.peck_slow / checks.fight_slow.
Runs on all clips, not just the ones we expect something in.
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
from vm_zoom import TILES

VIEWS = {"full": None, **TILES}


def slow_view(clip, name, xy, out_dir):
    out = Path(out_dir) / f"{clip.stem}_{name}_slow.mp4"
    vf = "setpts=4*PTS"
    if xy:
        x, y = xy.split(":")
        vf = f"crop=iw/2:ih/2:{x}:{y},scale=1280:720," + vf
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-vf", vf, "-an", "-q:v", "3", str(out)], check=True)
    return out


def slow_checks(clip):
    d = tempfile.mkdtemp()
    res = {"peck_slow": {}, "fight_slow": {}}
    for name, xy in VIEWS.items():
        b64 = base64.b64encode(slow_view(clip, name, xy, d).read_bytes()).decode()
        res["peck_slow"][name] = ask(b64, QUESTIONS["peck"])
        res["fight_slow"][name] = ask(b64, QUESTIONS["fight"])
    return res


def main():
    path = v.DATA / "segments.json"
    rows = json.loads(path.read_text())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda r: slow_checks(v.ROOT / "clips" / r["filename"]), rows))
    for i, (row, res) in enumerate(zip(rows, results), 1):
        row.setdefault("checks", {}).update(res)

        def yes_views(k):
            return [t for t, a in res[k].items() if (a.split() or [""])[0].strip(".,").upper() == "YES"]
        print(f"[{i}/{len(rows)}] {row['filename'][-24:-4]}  peck in: {yes_views('peck_slow') or '-'}  "
              f"fight in: {yes_views('fight_slow') or '-'}", flush=True)
    path.write_text(json.dumps(rows, indent=1, default=str))
    print("\nupdated data/segments.json. Next: bash ~/shepherd/scripts/vm_push.sh")


if __name__ == "__main__":
    main()
