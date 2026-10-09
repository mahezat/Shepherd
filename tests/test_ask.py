"""Guard tests for semantic search (no network): python3 tests/test_ask.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shepherd import rules
from shepherd.ask import check, concept_answer, index

CLIPS = rules.build_clips(json.loads((Path(__file__).resolve().parent.parent / "data" / "segments.json").read_text()))
LAST = max(range(len(CLIPS)), key=lambda i: CLIPS[i].time)


def test_rejects_unknown_clip():
    assert check({"clips": [99], "answer": "x"}, CLIPS)


def test_accepts_quoted_ids():
    t = rules.fmt_time(CLIPS[LAST].time)
    assert check({"clips": [str(LAST)], "answer": f"At {t} a hen was in the nest box."}, CLIPS) is None


def test_rejects_time_not_on_cited_clip():
    assert check({"clips": [LAST], "answer": "At 3:12 AM a hen laid."}, CLIPS)


def test_rejects_egg_claim():
    t = rules.fmt_time(CLIPS[LAST].time)
    assert check({"clips": [LAST], "answer": f"A hen laid an egg at {t}."}, CLIPS)


def test_concepts_last_egg_is_latest_nest_clip():
    a = concept_answer("when was the last time a hen laid an egg?", CLIPS)
    assert a["clips"] and CLIPS[a["clips"][0]].time == max(CLIPS[i].time for i in a["clips"])
    assert "likely laying" in a["answer"]


def test_concepts_fight_finds_622():
    a = concept_answer("did anything hurt the birds?", CLIPS)
    assert [rules.fmt_time(CLIPS[i].time) for i in a["clips"]] == ["6:22 AM"]


def test_nothing_found():
    assert concept_answer("were there any foxes?", CLIPS)["clips"] == []


def test_index_uses_no_filename_labels():
    assert not any("egglaying" in l or "fight_" in l for l in index(CLIPS))


if __name__ == "__main__":
    fns = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for f in fns:
        f()
    print(f"{len(fns)} passed")
