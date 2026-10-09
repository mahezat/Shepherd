"""Run ON THE EVENT VM (plain terminal, no Cursor needed):

    python3 ~/shepherd/scripts/vm_ingest.py            # upload, wait, export
    python3 ~/shepherd/scripts/vm_ingest.py --export   # skip upload, just export again

Uploads every clip in clips/ with our Cosmos prompt, waits for the pipeline
(Cosmos Reason + YOLO + Embed -> VastDB), then writes data/segments.json.
Standard library only. Never prints credentials.
"""
import glob
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
UPLOADS = DATA / "uploads.json"
CTX = ssl.create_default_context()
if os.environ.get("SHEPHERD_INSECURE"):
    CTX.check_hostname = False
    CTX.verify_mode = ssl.CERT_NONE


def load_config():
    cfg = {}
    files = sorted(glob.glob("/config/*.config"))
    if files:
        for line in Path(files[0]).read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("INGRESS_URL", "USERNAME", "PASSWORD"):
        cfg[k] = os.environ.get(k) if k != "USERNAME" else cfg.get(k) or os.environ.get(k)
        cfg[k] = cfg[k] or ""
    # USERNAME in the env is the Linux user; prefer the team config's value.
    if files:
        for line in Path(files[0]).read_text().splitlines():
            if line.startswith("USERNAME="):
                cfg["USERNAME"] = line.split("=", 1)[1].strip().strip('"')
            if line.startswith("PASSWORD="):
                cfg["PASSWORD"] = line.split("=", 1)[1].strip().strip('"')
            if line.startswith("INGRESS_URL="):
                cfg["INGRESS_URL"] = line.split("=", 1)[1].strip().strip('"')
    if not cfg.get("INGRESS_URL"):
        sys.exit("No INGRESS_URL found in /config/*.config or the environment.")
    return cfg["INGRESS_URL"].rstrip("/"), cfg["USERNAME"], cfg["PASSWORD"]


BACKEND, USER, PASSWORD = load_config()
TOKEN = None


def call(method, path, body=None, headers=None, raw=False, timeout=120):
    url = path if path.startswith("http") else BACKEND + path
    h = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
    h.update(headers or {})
    data = body
    if isinstance(body, (dict, list)):
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=timeout) as r:
            payload = r.read()
            return payload if raw else (json.loads(payload) if payload else None)
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_detail": e.read().decode(errors="replace")[:500]}


def login():
    global TOKEN
    TOKEN = None
    r = call("POST", "/api/v1/auth/login", {"username": USER, "password": PASSWORD})
    if not r or "access_token" not in r:
        sys.exit(f"Login failed: {r}")
    TOKEN = r["access_token"]
    print("logged in as", USER)


def multipart(fields, file_field, file_path):
    b = uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        out.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    out.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{file_path.name}\"\r\n"
               f"Content-Type: video/mp4\r\n\r\n".encode())
    out.append(file_path.read_bytes())
    out.append(f"\r\n--{b}--\r\n".encode())
    return b"".join(out), {"Content-Type": f"multipart/form-data; boundary={b}"}


def upload_all():
    prompt = (ROOT / "prompts" / "cosmos_ingest_prompt.txt").read_text().strip()
    cfg = call("GET", "/api/v1/metadata/ingest-config") or {}
    (RAW / "ingest-config.json").write_text(json.dumps(cfg, indent=1))
    types = [t.get("value", t) if isinstance(t, dict) else t for t in cfg.get("capture_types", [])]
    capture = next((t for t in types if "surveil" in str(t).lower()), types[0] if types else None)
    limit = cfg.get("custom_prompt_max_length", 800)
    if len(prompt) > limit:
        sys.exit(f"Prompt is {len(prompt)} chars, limit is {limit}.")
    uploads = {}
    for clip in sorted((ROOT / "clips").glob("*.mp4")):
        fields = {"is_public": "false", "tags": "shepherd", "custom_prompt": prompt,
                  "camera_id": "coop_cam-1", "location": "coop"}
        if capture:
            fields["capture_type"] = capture
        body, h = multipart(fields, "file", clip)
        r = call("POST", "/api/v1/videos/upload", body, h, timeout=300)
        if isinstance(r, dict) and r.get("_error") == 401:
            login()
            r = call("POST", "/api/v1/videos/upload", body, h, timeout=300)
        key = (r or {}).get("object_key")
        print(("uploaded  " if key else "FAILED    ") + clip.name, "" if key else r)
        if key:
            uploads[clip.name] = key
    UPLOADS.write_text(json.dumps(uploads, indent=1))
    return uploads


def explore_all():
    items, offset = [], 0
    while True:
        r = call("GET", f"/api/v1/videos/explore?scope=mine&limit=100&offset={offset}")
        page = (r or {}).get("items") or (r or {}).get("videos") or (r or {}).get("results") or (r if isinstance(r, list) else [])
        items += page
        total = (r or {}).get("total") if isinstance(r, dict) else None
        offset += 100
        if not page or total is None or offset >= total:
            break
    return items, r


def find_original(item_list, key):
    for it in item_list:
        blob = json.dumps(it)
        if key in blob:
            return it.get("original_video") or next(
                (v for v in it.values() if isinstance(v, str) and key in v and v.startswith("s3://")), None)
    return None


def segments_for(original):
    q = urllib.parse.urlencode({"original_video": original})
    r = call("GET", f"/api/v1/tools/segments?{q}")
    if isinstance(r, dict):
        for k in ("segments", "items", "results", "data"):
            if isinstance(r.get(k), list):
                return r[k], r
        return [], r
    return (r or []), r


def text_of(seg):
    for k in ("reasoning_content", "reasoning", "caption", "description", "text"):
        if isinstance(seg.get(k), str) and seg[k].strip():
            return seg[k]
    return ""


def export(uploads):
    deadline = time.time() + 25 * 60
    pending = dict(uploads)
    found = {}
    while pending and time.time() < deadline:
        items, last = explore_all()
        (RAW / "explore.json").write_text(json.dumps(last, indent=1)[:2_000_000])
        for name, key in list(pending.items()):
            orig = find_original(items, key)
            if not orig:
                continue
            segs, rawseg = segments_for(orig)
            if segs and all(text_of(s) for s in segs):
                found[name] = (orig, segs)
                del pending[name]
        print(f"indexed {len(found)}/{len(uploads)}" + (" ... waiting" if pending else ""))
        if pending:
            time.sleep(20)
            if time.time() - LOGIN_AT > 20 * 60:
                login()
    rows = []
    for name, (orig, segs) in found.items():
        for s in segs:
            src = s.get("source") or s.get("segment_source") or s.get("s3_uri")
            det = None
            if src:
                d = call("GET", "/api/v1/videos/detections?" + urllib.parse.urlencode({"source": src}))
                det = None if isinstance(d, dict) and d.get("_error") else d
            rows.append({
                "filename": name, "original_video": orig, "source": src,
                "start_sec": s.get("start_sec", s.get("start_time", s.get("segment_start"))),
                "end_sec": s.get("end_sec", s.get("end_time", s.get("segment_end"))),
                "reasoning": text_of(s), "detections": det,
                "raw": {k: v for k, v in s.items() if not isinstance(v, list) or len(v) < 50},
            })
    (DATA / "segments.json").write_text(json.dumps(rows, indent=1, default=str))
    print(f"\nwrote data/segments.json: {len(rows)} segments from {len(found)} clips")
    if pending:
        print("NOT indexed yet:", ", ".join(pending), "\nRun again later with --export")
    print()
    for r in rows:
        line = " ".join(r["reasoning"].split())[:90]
        print(f"{r['filename'][-24:-4]}  {line}")


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    RAW.mkdir(exist_ok=True)
    login()
    LOGIN_AT = time.time()
    if "--export" in sys.argv and UPLOADS.exists():
        ups = json.loads(UPLOADS.read_text())
    else:
        ups = upload_all()
    export(ups)
    print("\nNext: bash ~/shepherd/scripts/vm_push.sh")
