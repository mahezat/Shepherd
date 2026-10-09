"""Shepherd agent: segments in, morning report out.

    python3 -m shepherd.agent                      # reads data/segments.json
    python3 -m shepherd.agent path/to/segments.json

1. build_clips + decide (rules.py) turn Cosmos/YOLO output into events.
2. A Weights & Biases serverless model writes the morning report from those
   events only. If it writes any number that isn't in the evidence, its text is
   thrown away and the plain report is used. The model never decides.
3. W&B Weave traces every step, so each report links to "what Shepherd saw".

Environment: WANDB_API_KEY, WANDB_PROJECT ("team/project" or just "project"
with WANDB_TEAM). Without a key it still runs, with the plain report and no trace.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from shepherd import rules

ROOT = Path(__file__).resolve().parent.parent
MODEL = os.environ.get("SHEPHERD_MODEL", "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B")
WANDB_BASE_URL = "https://api.inference.wandb.ai/v1"

SYSTEM = """You write the morning report for Shepherd, a camera agent that watches a small farm's chicken coop.
Rules:
- Use ONLY the facts in the JSON you are given. Every number and time you write must appear in it.
- Do not add events, counts, eggs or animals that aren't in the JSON. Say "likely laying", never "laid an egg".
- Copy each event's priority exactly: priority HIGH -> "HIGH:", LOW -> "LOW:", INFO -> "Good news:". Never relabel.
- Write one line for EVERY event in the JSON, including INFO events ("Good news:"), even when events_that_matter is 0.
- Noise is never HIGH or LOW; it goes on the "Filtered:" line.
- Plain, calm, a little dry. No exclamation marks. No markdown headers.
- Format: first line is the headline "<clips_recorded> clips recorded. <events_that_matter> that matter."
  Then one short line per event, HIGH first, then LOW, then good news, each starting with "HIGH:", "LOW:" or "Good news:", naming the event (e.g. "Fight", "Hen in the nest box") with its time and one short reason.
  Then one line starting "Filtered:" for the noise count. Under 90 words in total."""


def _project() -> str | None:
    p = os.environ.get("WANDB_PROJECT")
    team = os.environ.get("WANDB_TEAM") or os.environ.get("WANDB_ENTITY")
    if not p:
        return None
    return p if "/" in p or not team else f"{team}/{p}"


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def guard(llm_text: str, evidence_text: str) -> tuple[bool, set[str]]:
    """True when every number in the model's text also appears in the evidence."""
    extra = _numbers(llm_text) - _numbers(evidence_text)
    return (not extra and bool(llm_text.strip())), extra


def labels_match(llm_text: str, events: list[dict]) -> bool:
    """The model may not change a priority: as many HIGH / LOW / Good news lines as the rules produced."""
    lines = [l.strip().lower() for l in llm_text.splitlines()]
    got = {k: sum(l.startswith(k) for l in lines) for k in ("high:", "low:", "good news:")}
    want = {"high:": sum(e["priority"] == "HIGH" for e in events),
            "low:": sum(e["priority"] == "LOW" for e in events),
            "good news:": sum(e["priority"] == "INFO" for e in events)}
    if got != want:
        return False
    # every event must be named on its own line ("fight", "nest box", ...), not just given a label
    words = {"fight": "fight", "peck": "peck", "laying": "nest", "disturbance": "disturbance"}
    text = llm_text.lower()
    return all(words.get(e["kind"], "") in text for e in events)


# Weave is optional: the agent must run on a laptop with no key.
try:
    import weave  # type: ignore
    op = weave.op
except Exception:  # pragma: no cover
    weave = None

    def op(fn=None, **_kw):
        return fn if fn else (lambda f: f)


@op
def read_clips(segments: list[dict]) -> list[dict]:
    """Cosmos replies + YOLO counts, merged per clip."""
    return [c.evidence() for c in rules.build_clips(segments)]


@op
def apply_rules(segments: list[dict]) -> dict:
    """The rules decide: events, priorities, noise, can't tell."""
    return rules.decide(rules.build_clips(segments))


@op
def write_report(result: dict) -> dict:
    """W&B model words the report; the guardrail keeps it honest."""
    plain = rules.plain_report(result)
    facts = {k: result[k] for k in ("clips_recorded", "events_that_matter", "first_clip", "last_clip")}
    facts["events"] = [{k: e[k] for k in ("priority", "title", "start", "end", "clip_count", "confirmed", "why")}
                       for e in result["events"]]
    facts["noise_clips"] = len(result["noise"])
    facts["cant_tell_clips"] = len(result["cant_tell"])

    key = os.environ.get("WANDB_API_KEY")
    if not key:
        return {"text": plain, "source": "template", "reason": "no WANDB_API_KEY"}
    try:
        from openai import OpenAI
        headers = {"OpenAI-Project": _project()} if _project() else None
        client = OpenAI(base_url=WANDB_BASE_URL, api_key=key, default_headers=headers)
    except Exception as e:
        return {"text": plain, "source": "template", "reason": f"client error: {e}"[:300]}

    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": json.dumps(facts)}]
    rejected = []
    for attempt in range(2):  # one retry, told exactly why it was rejected
        try:
            resp = client.chat.completions.create(
                model=MODEL, temperature=0.2, max_tokens=600, messages=messages,
                # Nemotron thinks by default and can spend every token doing it; the report needs no reasoning.
                extra_body={"chat_template_kwargs": {"enable_thinking": False}})
            text = (resp.choices[0].message.content or "").strip()
        except Exception as e:  # network, quota, model name
            return {"text": plain, "source": "template", "rejected": rejected,
                    "reason": f"model error: {type(e).__name__}: {e}"[:300]}
        ok, extra = guard(text, plain + " " + json.dumps(facts))
        if not ok:
            why = f"it wrote numbers not in the evidence: {sorted(extra)}" if extra else "it returned nothing"
        elif not labels_match(text, result["events"]):
            why = "it dropped or renamed an event, or changed a priority (HIGH / LOW / Good news) that the rules set"
        else:
            # The headline is a count, so it always comes from the rules, word for word.
            lines = text.splitlines()
            lines[0] = plain.splitlines()[0]
            return {"text": "\n".join(lines), "source": MODEL, "rejected": rejected}
        rejected.append({"text": text, "why": why})
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": f"Rejected: {why}. Rewrite following the rules exactly."}]
    return {"text": plain, "source": "template", "rejected": rejected,
            "reason": "model text rejected twice: " + rejected[-1]["why"]}


@op
def morning_report(segments: list[dict]) -> dict:
    clips = read_clips(segments)
    result = apply_rules(segments)
    report = write_report(result)
    return {"report": report, "result": result, "clips": clips}


def run(path: Path) -> dict:
    segments = json.loads(path.read_text())
    project = _project()
    trace_url = None
    if weave is not None and project and os.environ.get("WANDB_API_KEY"):
        weave.init(project)
        out, call = morning_report.call(segments)
        trace_url = getattr(call, "ui_url", None)
    else:
        out = morning_report(segments)
    out["trace_url"] = trace_url
    out["model"] = MODEL
    out["data_source"] = path.name
    return out


def main(argv: list[str]) -> None:
    path = Path(argv[1]) if len(argv) > 1 else ROOT / "data" / "segments.json"
    out = run(path)
    for d in (ROOT / "out", ROOT / "docs"):
        d.mkdir(exist_ok=True)
        (d / "report.json").write_text(json.dumps(out, indent=2, default=str))
    print(out["report"]["text"])
    print(f"\n[report by: {out['report']['source']}]", out["report"].get("reason", ""))
    if out["trace_url"]:
        print("Weave trace:", out["trace_url"])


if __name__ == "__main__":
    main(sys.argv)
