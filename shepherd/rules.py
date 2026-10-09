"""Shepherd's decision rules.

Cosmos describes each clip, YOLO counts the birds, and these rules decide.
The language model never decides anything: it only rewords the report, and
the agent throws its text away if it invents a number (see agent.py).

Pure Python, standard library only.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

HIGH, LOW, INFO = "HIGH", "LOW", "INFO"

EVENTS = ("fight", "peck", "laying", "shifting", "normal", "disturbance")
# Most serious first: when one clip has several segments, the clip takes the most serious event.
SEVERITY = ["disturbance", "fight", "peck", "laying", "shifting", "normal"]

FIGHT_GAP = timedelta(minutes=10)
LAYING_GAP = timedelta(minutes=20)
PECK_GAP = timedelta(minutes=10)

_TIME_IN_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2})_(\d{2})_(\d{2})")
_WORDS = {"zero": 0, "none": 0, "no": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
          "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}


# ---------------------------------------------------------------- parsing

def recorded_at(filename: str) -> Optional[datetime]:
    """Recording time from the Blink filename. Only the time is used, never the label words."""
    m = _TIME_IN_NAME.search(filename or "")
    if not m:
        return None
    d, hh, mm, ss = m.groups()
    return datetime.fromisoformat(f"{d}T{hh}:{mm}:{ss}")


def _first_int(text: str) -> Optional[int]:
    m = re.search(r"\d+", text or "")
    if m:
        return int(m.group())
    for w, n in _WORDS.items():
        if re.search(rf"\b{w}\b", (text or "").lower()):
            return n
    return None


def _pick(value: str, options) -> Optional[str]:
    v = (value or "").lower().replace("-", "_").replace(" ", "_")
    for o in options:
        if o in v:
            return o
    return None


def parse_reply(text: str) -> dict:
    """Parse Cosmos's reply (the format our ingest prompt asks for).

    Tolerates markdown, bullets and lower-case keys. Missing fields are None.
    `ok` is False when the reply can't be used, which becomes "can't tell".
    """
    fields: dict[str, str] = {}
    for line in (text or "").splitlines():
        line = re.sub(r"[*_`#>\-•]+", " ", line).strip()
        m = re.match(r"^([A-Za-z ]+?)\s*:\s*(.+)$", line)
        if m:
            fields[m.group(1).strip().upper().replace(" ", "_")] = m.group(2).strip()

    lighting_raw = fields.get("LIGHTING", "").lower()
    if any(w in lighting_raw for w in ("night", "infrared", "dark", "black")):
        lighting = "night"
    elif any(w in lighting_raw for w in ("day", "light", "color", "colour")):
        lighting = "day"
    else:
        lighting = None

    out = {
        "lighting": lighting,
        "total": _first_int(fields.get("TOTAL", "")),
        "event": _pick(fields.get("EVENT", ""), EVENTS),
        "where": _pick(fields.get("WHERE", ""), ("nest_box", "perch", "floor", "fence", "outside")),
        "mover": _pick(fields.get("MOVER", ""), ("other_animal", "person", "nothing_visible", "chicken")),
        "activity": fields.get("ACTIVITY", ""),
    }
    out["ok"] = out["event"] is not None
    return out


def yolo_birds(detections: Any) -> Optional[int]:
    """Most birds YOLO saw in any single frame. None when YOLO has nothing for the clip.

    The detections sidecar format isn't documented, so this walks the JSON and
    counts, per frame, the boxes whose class/label/name is "bird".
    """
    if detections in (None, {}, []):
        return None
    best = 0
    found_any = False

    def is_bird(d: dict) -> bool:
        for k in ("class", "label", "name", "class_name", "cls_name"):
            v = d.get(k)
            if isinstance(v, str) and v.lower() == "bird":
                return True
        return False

    def walk(node):
        nonlocal best, found_any
        if isinstance(node, list):
            boxes = [x for x in node if isinstance(x, dict)]
            if boxes and any(any(k in b for k in ("class", "label", "name", "class_name", "cls_name")) for b in boxes):
                found_any = True
                best = max(best, sum(1 for b in boxes if is_bird(b)))
            for x in node:
                walk(x)
        elif isinstance(node, dict):
            # e.g. {"object_classes": {"bird": 3}} or {"counts": {"bird": 3}}
            for k in ("object_classes", "counts", "class_counts"):
                v = node.get(k)
                if isinstance(v, dict) and "bird" in v and isinstance(v["bird"], (int, float)):
                    found_any = True
                    best = max(best, int(v["bird"]))
            for v in node.values():
                walk(v)

    walk(detections)
    return best if found_any else None


def yes(answer: str | None) -> Optional[bool]:
    """Cosmos's answer to a direct question: True for YES, False for NO, None if missing."""
    w = re.findall(r"[a-z]+", (answer or "").lower())
    if not w:
        return None
    return True if w[0] == "yes" else False if w[0] == "no" else None


# ---------------------------------------------------------------- clips

@dataclass
class Clip:
    filename: str
    time: datetime
    event: Optional[str]          # None = can't tell
    lighting: Optional[str]
    where: Optional[str]
    mover: Optional[str]
    total: Optional[int]
    birds_yolo: Optional[int]
    activity: str
    sources: list = field(default_factory=list)
    replies: list = field(default_factory=list)
    checks: dict = field(default_factory=dict)   # Cosmos's answers to the direct questions
    form_event: Optional[str] = None             # what the long-form reply said, before the checks
    zoomed: dict = field(default_factory=dict)   # which zoomed tiles Cosmos said YES on

    def evidence(self) -> dict:
        return {
            "clip": self.filename, "time": fmt_time(self.time), "event": self.event,
            "lighting": self.lighting, "where": self.where, "mover": self.mover,
            "chickens_cosmos": self.total, "birds_yolo": self.birds_yolo, "activity": self.activity,
            "form_event": self.form_event, "zoomed": self.zoomed,
            "checks": {k: v for k, v in self.checks.items() if not isinstance(v, dict)},
        }


def build_clips(segments: list[dict]) -> list[Clip]:
    """Merge segments into clips. A clip takes its most serious segment's event."""
    by_file: dict[str, list[dict]] = {}
    for s in segments:
        name = s.get("filename") or s.get("original_filename") or ""
        by_file.setdefault(name, []).append(s)

    clips = []
    for name, segs in by_file.items():
        segs.sort(key=lambda s: s.get("start_sec") or 0)
        parsed = [parse_reply(s.get("reasoning") or "") for s in segs]
        good = [p for p in parsed if p["ok"]]
        t = recorded_at(name)
        if t is None:
            continue

        def most_common(key):
            vals = [p[key] for p in good if p[key] is not None]
            return Counter(vals).most_common(1)[0][0] if vals else None

        if good:
            event = min((p["event"] for p in good), key=SEVERITY.index)
            lead = next(p for p in good if p["event"] == event)
        else:
            event, lead = None, {"activity": ""}

        # The direct yes/no questions beat the long form: the small Cosmos model
        # calls almost everything "normal" in the form but answers questions well.
        checks: dict = {}
        for s in segs:
            for k, a in (s.get("checks") or {}).items():
                if a and k not in checks:
                    checks[k] = a
        form_event = event
        where = lead.get("where") if good else None
        mover = lead.get("mover") if good else None
        if event == "disturbance" and mover == "chicken":
            event = "normal"   # a chicken moving is not a disturbance
        def any_tile(key):
            tiles = checks.get(key) or {}
            hits = [name for name, a in tiles.items() if yes(a)]
            return hits

        fight_tiles, peck_tiles = any_tile("fight_zoom"), any_tile("peck_zoom")
        zoomed = {"fight": fight_tiles, "peck": peck_tiles}
        if yes(checks.get("fight")) or fight_tiles:
            event = "fight"
        elif yes(checks.get("peck")) or peck_tiles:
            event = "peck"
            if yes(checks.get("nest")):
                where = "nest_box"
        elif yes(checks.get("nest")) and event in (None, "normal", "shifting", "laying"):
            event, where = "laying", "nest_box"
        if checks and event is None:
            event = "normal"

        counts = [c for c in (yolo_birds(s.get("detections")) for s in segs) if c is not None]
        totals = [p["total"] for p in good if p["total"] is not None]
        clips.append(Clip(
            filename=name, time=t, event=event,
            lighting=most_common("lighting"),
            where=where,
            mover=mover,
            total=max(totals) if totals else None,
            birds_yolo=max(counts) if counts else None,
            activity=lead.get("activity", ""),
            sources=[s.get("source") for s in segs],
            replies=[s.get("reasoning") or "" for s in segs],
            checks=checks, form_event=form_event, zoomed=zoomed,
        ))
    clips.sort(key=lambda c: c.time)
    return clips


# ---------------------------------------------------------------- events

def fmt_time(t: datetime) -> str:
    return t.strftime("%-I:%M %p")


def _runs(clips: list[Clip], gap: timedelta) -> list[list[Clip]]:
    runs: list[list[Clip]] = []
    for c in clips:
        if runs and c.time - runs[-1][-1].time <= gap:
            runs[-1].append(c)
        else:
            runs.append([c])
    return runs


def _confirmed(run: list[Clip], kind: str) -> tuple[bool, str]:
    if len(run) >= 2:
        return True, f"{len(run)} clips agree"
    if kind in ("fight", "peck") and any((c.birds_yolo or 0) >= 2 for c in run):
        return True, "YOLO sees 2+ birds"
    if kind == "disturbance" and run[0].mover in ("other_animal", "person"):
        return False, "one clip only"
    return False, "one clip only"


def _event(kind, priority, title, run, why, extra=None) -> dict:
    confirmed, basis = _confirmed(run, kind)
    e = {
        "kind": kind, "priority": priority, "title": title,
        "start": fmt_time(run[0].time), "end": fmt_time(run[-1].time),
        "start_iso": run[0].time.isoformat(), "end_iso": run[-1].time.isoformat(),
        "clips": [c.filename for c in run], "clip_count": len(run),
        "confirmed": confirmed, "confirmed_by": basis, "why": why,
        "evidence": [c.evidence() for c in run],
    }
    if extra:
        e.update(extra)
    return e


def decide(clips: list[Clip]) -> dict:
    """Turn clips into events, noise and can't-tell. Returns everything the report needs."""
    used: set[str] = set()
    events: list[dict] = []

    # HIGH: something that isn't a chicken moved
    dist = [c for c in clips if c.mover in ("other_animal", "person")
            or (c.event == "disturbance" and c.mover not in ("chicken",))]
    for run in _runs(dist, FIGHT_GAP):
        who = "a person" if any(c.mover == "person" for c in run) else "another animal"
        night = any(c.lighting == "night" for c in run)
        title = f"Disturbance: {who} at the coop" + (", after dark" if night else "")
        events.append(_event("disturbance", HIGH, title, run,
                             "Something other than the flock moved in the coop."))
        used.update(c.filename for c in run)

    # HIGH: fights, one event per run of clips
    fights = [c for c in clips if c.event == "fight" and c.filename not in used]
    for run in _runs(fights, FIGHT_GAP):
        night = any(c.lighting == "night" for c in run)
        where = " through the fence" if any(c.where == "fence" for c in run) else ""
        title = f"Fight{where}" + (", in the dark" if night else "")
        events.append(_event("fight", HIGH, title, run,
                             "Birds fighting can injure each other; nobody was there to break it up.",
                             {"night": night}))
        used.update(c.filename for c in run)

    # INFO: laying sessions (nest-box clips, including a peck that happens in the box)
    nest = [c for c in clips if c.filename not in used and
            (c.event == "laying" or (c.event in ("peck", "shifting", "normal") and c.where == "nest_box"))]
    sessions = []
    for run in _runs(nest, LAYING_GAP):
        sessions.append({
            "start": fmt_time(run[0].time), "end": fmt_time(run[-1].time),
            "start_dt": run[0].time, "end_dt": run[-1].time,
            "clips": [c.filename for c in run], "clip_count": len(run),
            "egg_seen": False,  # no clip shows the egg, so it's "likely laying"
        })

    # LOW: pecks; inside a laying session it's nest-box bullying
    pecks = [c for c in clips if c.event == "peck" and c.filename not in used]
    for run in _runs(pecks, PECK_GAP):
        in_session = next((s for s in sessions
                           if s["start_dt"] - timedelta(minutes=5) <= run[0].time <= s["end_dt"] + timedelta(minutes=5)), None)
        if in_session:
            title = "A hen was pecked while in the nest box"
            why = "Nest-box bullying can put a hen off laying. Worth watching, not urgent."
        else:
            title = "One hen pecked another"
            why = "Worth watching if it keeps happening. Not urgent."
        events.append(_event("peck", LOW, title, run, why))
        used.update(c.filename for c in run)

    for s in sessions:
        used.update(s["clips"])
        events.append({
            "kind": "laying", "priority": INFO,
            "title": "Hen in the nest box, likely laying",
            "start": s["start"], "end": s["end"],
            "start_iso": s["start_dt"].isoformat(), "end_iso": s["end_dt"].isoformat(),
            "clips": s["clips"], "clip_count": s["clip_count"],
            "confirmed": s["clip_count"] >= 2, "confirmed_by": f"{s['clip_count']} clips",
            "why": "No clip shows the egg, so Shepherd says likely.",
            "evidence": [c.evidence() for c in clips if c.filename in s["clips"]],
        })

    cant_tell = [c for c in clips if c.event is None and c.filename not in used]
    noise = [c for c in clips if c.filename not in used and c.event is not None]

    order = {HIGH: 0, LOW: 1, INFO: 2}
    events.sort(key=lambda e: (order[e["priority"]], e["start_iso"]))

    day_totals = [c.total for c in clips if c.lighting == "day" and c.total is not None]
    matter = [e for e in events if e["priority"] in (HIGH, LOW)]
    return {
        "clips_recorded": len(clips),
        "clips_that_matter": sum(e["clip_count"] for e in matter),
        "events_that_matter": len(matter),
        "flock_size_seen": max(day_totals) if day_totals else None,
        "events": events,
        "noise": [c.evidence() for c in noise],
        "cant_tell": [c.evidence() for c in cant_tell],
        "first_clip": fmt_time(clips[0].time) if clips else None,
        "last_clip": fmt_time(clips[-1].time) if clips else None,
    }


def plain_report(result: dict) -> str:
    """The report with no language model at all. Also the fallback."""
    lines = [f"{result['clips_recorded']} clips recorded. {result['events_that_matter']} "
             f"{'thing' if result['events_that_matter'] == 1 else 'things'} that matter."]
    for e in result["events"]:
        span = e["start"] if e["start"] == e["end"] else f"{e['start']} to {e['end']}"
        label = {"HIGH": "HIGH", "LOW": "LOW", "INFO": "Good news"}[e["priority"]]
        clips = f"{e['clip_count']} clip{'s' if e['clip_count'] != 1 else ''}"
        lines.append(f"{label}: {e['title']}, {span} ({clips}). {e['why']}")
    n = len(result["noise"])
    if n:
        lines.append(f"Filtered: {n} clip{'s' if n != 1 else ''} of normal chicken business.")
    if result["cant_tell"]:
        lines.append(f"Can't tell: {len(result['cant_tell'])} clip(s). Worth a human look.")
    return "\n".join(lines)
