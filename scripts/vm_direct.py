"""Fallback, run ON THE EVENT VM when the DataEngine pipeline is stuck:

    python3 -u ~/shepherd/scripts/vm_direct.py

Sends each clip straight to the NVIDIA Cosmos3-Reason and YOLO11 GPU endpoints on
CoreWeave (the same models the pipeline uses) and writes data/segments.json in
the same format. Standard library only (uses ffmpeg for frames if Cosmos refuses video).
"""
import base64
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def config():
    cfg = dict(os.environ)
    for f in sorted(glob.glob("/config/*.config"))[:1]:
        for line in Path(f).read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                cfg.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return cfg


CFG = config()
# The organizers' gpu/model-smoke-test skill pins the shared GPU host; use it when the env doesn't say.
GPU_HOST = CFG.get("GPU_HOST", "166.19.38.112")
COSMOS = (CFG.get("COSMOS3_REASON_URL") or f"http://{GPU_HOST}:8001").rstrip("/")
YOLO = (CFG.get("YOLO_URL") or f"http://{GPU_HOST}:8002").rstrip("/")
print("Cosmos endpoint:", COSMOS, "| YOLO endpoint:", YOLO, flush=True)
AUTH = {"Authorization": f"Bearer {CFG['GPU_BEARER_TOKEN']}"} if CFG.get("GPU_BEARER_TOKEN") else {}
if not COSMOS:
    sys.exit("COSMOS3_REASON_URL not found in the environment or /config/*.config")


def post(url, body, timeout=300):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **AUTH}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_detail": e.read().decode(errors="replace")[:400]}
    except Exception as e:
        return {"_error": type(e).__name__, "_detail": str(e)[:400]}


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=AUTH), timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"_error": str(e)[:200]}


models = get(COSMOS + "/v1/models")
MODEL = (models.get("data") or [{}])[0].get("id") or CFG.get("COSMOS3_REASON_MODEL", "nvidia/cosmos3-reason")
print("Cosmos model:", MODEL, flush=True)
PROMPT = (ROOT / "prompts" / "cosmos_ingest_prompt.txt").read_text().strip()


def frames_as_images(clip):
    if not shutil.which("ffmpeg"):
        return None
    d = tempfile.mkdtemp()
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(clip), "-vf", "fps=1,scale=640:-1", f"{d}/f%02d.jpg"], check=False)
    imgs = sorted(Path(d).glob("*.jpg"))[:6]
    return [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()}}
            for p in imgs] or None


def ask_cosmos(clip):
    b64 = base64.b64encode(clip.read_bytes()).decode()
    attempts = [
        [{"type": "video_url", "video_url": {"url": "data:video/mp4;base64," + b64}}],
    ]
    imgs = frames_as_images(clip)
    if imgs:
        attempts.append(imgs)
    last = None
    for media in attempts:
        r = post(COSMOS + "/v1/chat/completions", {
            "model": MODEL, "temperature": 0, "max_tokens": 400,
            "messages": [{"role": "user", "content": media + [{"type": "text", "text": PROMPT}]}]})
        text = ((r.get("choices") or [{}])[0].get("message") or {}).get("content") if "choices" in r else None
        if text:
            return text, ("video" if media[0]["type"] == "video_url" else "frames")
        last = r
    return "", f"failed: {json.dumps(last)[:300]}"


def ask_yolo(clip):
    if not YOLO:
        return None
    b64 = base64.b64encode(clip.read_bytes()).decode()
    r = post(YOLO + "/v1/infer", {"video_base64": b64, "filename": clip.name, "include_frames": True})
    return None if "_error" in r else r


def main():
    rows = []
    clips = sorted((ROOT / "clips").glob("*.mp4"))
    for i, clip in enumerate(clips, 1):
        text, how = ask_cosmos(clip)
        det = ask_yolo(clip)
        rows.append({"filename": clip.name, "original_video": None, "source": f"clips/{clip.name}",
                     "start_sec": 0, "end_sec": None, "reasoning": text, "detections": det,
                     "raw": {"cosmos_input": how, "cosmos_model": MODEL, "path": "direct-to-GPU-endpoint"}})
        line = " ".join(text.split())[:80] if text else how
        print(f"[{i}/{len(clips)}] {clip.name[-24:-4]}  {line}", flush=True)

    DATA.mkdir(exist_ok=True)
    (DATA / "segments.json").write_text(json.dumps(rows, indent=1, default=str))
    ok = sum(1 for r in rows if r["reasoning"])
    print(f"\nwrote data/segments.json: Cosmos answered {ok}/{len(rows)} clips")
    print("Next: bash ~/shepherd/scripts/vm_push.sh")


if __name__ == "__main__":
    main()
