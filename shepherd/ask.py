"""Ask Shepherd a question about the coop, in plain English.

    python3 -m shepherd.ask "when was the last time a hen laid an egg?"

Semantic search over what Cosmos saw in every clip. NVIDIA Nemotron (W&B Inference) reads the
question and the clip index (one line per clip: time, Cosmos's description, its yes/no answers,
the rules' event) and picks the clips that answer it, by meaning rather than keywords.

The same guard as the report: the model may only cite clips that exist, every time it writes must
belong to a clip it cited, and the clip is always returned so the farmer can watch it. Without a
key, or if the model's answer fails the guard twice, a small concept matcher answers instead and
says so. Every question is traced in W&B Weave.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from shepherd import rules
from shepherd.agent import MODEL, WANDB_BASE_URL, _project, op, weave

ROOT = Path(__file__).resolve().parent.parent

SYSTEM = """You answer a farmer's question about their chicken coop camera, using ONLY the clip index you are given.
Each index line is one real clip: [id] date time | what the camera model saw | its yes/no answers | Shepherd's event.
Find the clips that answer the question by meaning (an egg means a hen in the nest box / crate; hurt means fight or peck).
Reply with JSON only: {"clips": [ids, most relevant first], "answer": "one or two plain sentences"}.
Rules: every time you write must be the time of a clip you list. The camera cannot see eggs: never say an egg was laid or that egg-laying happened; say "a hen was in the nest box, likely laying".
If nothing in the index answers the question, reply {"clips": [], "answer": "Nothing in the recorded clips shows that."}"""

# Concept matcher for running without a model: words in the question -> what to look for in a clip.
CONCEPTS = {
    "laying": (r"\b(egg|eggs|lay|laid|laying|nest|crate|brood)", lambda c: rules.yes(c.checks.get("nest")) or c.event == "laying"),
    "fight": (r"\b(fight|fought|fighting|rooster|roosters|hurt|injur|attack|flap)", lambda c: c.event == "fight"),
    "peck": (r"\b(peck|pecked|pecking|bully|bullied)", lambda c: c.event == "peck"),
    "night": (r"\b(night|dark|perch|roost|sleep)", lambda c: c.lighting == "night"),
}


def index(clips: list[rules.Clip]) -> list[str]:
    lines = []
    for i, c in enumerate(clips):
        checks = "; ".join(f"{k}: {str(v)[:70]}" for k, v in c.checks.items() if isinstance(v, str))
        ev = _evidence(c)
        extra = f" | zoom/slow-motion view: {ev}" if ev != c.activity and ev not in checks else ""
        lines.append(f"[{i}] {c.time:%b %-d} {rules.fmt_time(c.time)} | {c.activity} | {checks}{extra} | event: {c.event or 'cant_tell'}")
    return lines


def _times(text: str) -> set[str]:
    return {re.sub(r"\s+", " ", t.upper()) for t in re.findall(r"\b\d{1,2}:\d{2}\s*[AaPp]\.?[Mm]\.?", text.replace(".", ""))}


def check(answer: dict, clips: list[rules.Clip]) -> str | None:
    """None if the answer is grounded, else why it was rejected."""
    ids = answer.get("clips")
    if isinstance(ids, list):  # models often quote the ids
        ids = answer["clips"] = [int(i.strip(" []")) if isinstance(i, str) and i.strip(" []").isdigit() else i for i in ids]
    if not isinstance(ids, list) or not all(isinstance(i, int) and 0 <= i < len(clips) for i in ids):
        return "it cited a clip that doesn't exist"
    text = str(answer.get("answer", "")).strip()
    if not text:
        return "it returned no answer"
    allowed = {rules.fmt_time(clips[i].time).upper() for i in ids}
    extra = _times(text) - allowed
    if extra:
        return f"it wrote times that aren't on the clips it cited: {sorted(extra)}"
    if re.search(r"\b(laid an egg|an egg was laid|egg was seen|egg.laying (was|happened|occurred))", text.lower()):
        return "it claimed an egg; the camera can't see one"
    return None


def concept_answer(question: str, clips: list[rules.Clip]) -> dict:
    q = question.lower()
    hits = [k for k, (pat, _) in CONCEPTS.items() if re.search(pat, q)]
    if not hits:
        return {"clips": [], "answer": "Nothing in the recorded clips shows that."}
    test = CONCEPTS[hits[0]][1]
    ids = [i for i, c in enumerate(clips) if test(c)]
    if not ids:
        return {"clips": [], "answer": "Nothing in the recorded clips shows that."}
    ids.sort(key=lambda i: clips[i].time, reverse="first" not in q)
    c = clips[ids[0]]
    what = {"laying": "a hen was in the nest box, likely laying", "fight": "birds were fighting",
            "peck": "a bird pecked another", "night": "birds were on the perch at night"}[hits[0]]
    return {"clips": ids, "answer": f"{c.time:%b %-d}, {rules.fmt_time(c.time)}: {what}. {len(ids)} clip(s) match."}


def _evidence(c: rules.Clip) -> str:
    """The Cosmos answer that best explains why this clip matched."""
    if c.event == "fight":
        for k in ("fight_zoom", "fight_slow", "fight"):
            v = c.checks.get(k)
            if isinstance(v, dict):
                v = next((a for a in v.values() if rules.yes(a)), None)
            if isinstance(v, str) and rules.yes(v):
                return v
    if rules.yes(c.checks.get("nest")):
        return c.checks["nest"]
    return c.activity


@op
def ask(question: str, segments: list[dict]) -> dict:
    clips = rules.build_clips(segments)
    idx = index(clips)
    key = os.environ.get("WANDB_API_KEY")
    rejected, result, source = [], None, "concept matcher (no model key)"
    if key:
        from openai import OpenAI
        headers = {"OpenAI-Project": _project()} if _project() else None
        client = OpenAI(base_url=WANDB_BASE_URL, api_key=key, default_headers=headers)
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": "Clip index:\n" + "\n".join(idx) + f"\n\nQuestion: {question}"}]
        for _ in range(2):
            try:
                resp = client.chat.completions.create(
                    model=MODEL, temperature=0, max_tokens=400, messages=messages,
                    extra_body={"chat_template_kwargs": {"enable_thinking": False}})
                raw = (resp.choices[0].message.content or "").strip()
                m = re.search(r"\{.*\}", raw, re.S)
                cand = json.loads(m.group(0)) if m else {}
                why = check(cand, clips) if m else "it didn't return JSON"
            except Exception as e:
                why, raw = f"model error: {type(e).__name__}", ""
            if not why:
                result, source = cand, MODEL
                break
            rejected.append({"text": raw[:400], "why": why})
            messages += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": f"Rejected: {why}. Answer again following the rules exactly."}]
        if result is None:
            source = "concept matcher (model answer rejected)"
    if result is None:
        result = concept_answer(question, clips)
    cited = [clips[i] for i in result["clips"]]
    return {
        "question": question, "answer": result["answer"], "source": source, "rejected": rejected,
        "clips": [{"clip": c.filename, "time": f"{c.time:%b %-d} {rules.fmt_time(c.time)}", "saw": _evidence(c),
                   "nest": c.checks.get("nest"), "event": c.event} for c in cited],
    }


def main(argv: list[str]) -> None:
    question = " ".join(argv[1:]) or "When was the last time a hen laid an egg?"
    segments = json.loads((ROOT / "data" / "segments.json").read_text())
    if weave is not None and _project() and os.environ.get("WANDB_API_KEY"):
        weave.init(_project())
    out = ask(question, segments)
    print(f"Q: {out['question']}\nA: {out['answer']}")
    for c in out["clips"][:3]:
        print(f"   {c['time']}  clips/{c['clip']}\n            Cosmos: {c['saw']}")
    if len(out["clips"]) > 3:
        print(f"   ... and {len(out['clips']) - 3} more clip(s)")
    print(f"[answered by: {out['source']}]" + (f"  rejected drafts: {len(out['rejected'])}" if out["rejected"] else ""))


if __name__ == "__main__":
    main(sys.argv)
