"""Second pass, run ON THE EVENT VM after vm_direct.py:

    python3 -u ~/shepherd/scripts/vm_questions.py

The small Cosmos model answers a long form loosely ("normal" for everything) but
answers direct yes/no questions well. This asks three per clip and adds them to
data/segments.json under "checks".
"""
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vm_direct as v  # reuses endpoints, auth and model discovery (doesn't rerun the clips)

QUESTIONS = {
    "fight": "Watch the whole clip, including any birds at the back behind the wire fence. "
             "Do two birds fight: jump at, chase, flap at or attack each other more than once? "
             "Answer YES or NO first, then one short sentence.",
    "peck": "Does one chicken peck at another chicken, even once? Answer YES or NO first, then one short sentence.",
    "nest": "The black plastic crate on the floor is the nest box. Is a hen sitting inside the black crate? "
            "Answer YES or NO first, then one short sentence.",
}


def ask(clip_b64, question):
    r = v.post(v.COSMOS + "/v1/chat/completions", {
        "model": v.MODEL, "temperature": 0, "max_tokens": 120,
        "messages": [{"role": "user", "content": [
            {"type": "video_url", "video_url": {"url": "data:video/mp4;base64," + clip_b64}},
            {"type": "text", "text": question}]}]})
    try:
        return r["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""


path = v.DATA / "segments.json"
rows = json.loads(path.read_text())
for i, row in enumerate(rows, 1):
    clip = v.ROOT / "clips" / row["filename"]
    b64 = base64.b64encode(clip.read_bytes()).decode()
    row["checks"] = {k: ask(b64, q) for k, q in QUESTIONS.items()}
    short = "  ".join(f"{k}={(a.split() or ['?'])[0].strip('.,').upper()}" for k, a in row["checks"].items())
    print(f"[{i}/{len(rows)}] {row['filename'][-24:-4]}  {short}", flush=True)
path.write_text(json.dumps(rows, indent=1, default=str))
print("\nupdated data/segments.json. Next: bash ~/shepherd/scripts/vm_push.sh")
