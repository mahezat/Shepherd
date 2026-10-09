import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shepherd.rules import HIGH, INFO, LOW, build_clips, decide, parse_reply, plain_report, recorded_at, yolo_birds


def reply(lighting, total, event, where, mover="chicken", activity="Something happens."):
    return (f"LIGHTING: {lighting}\nTOTAL: {total}\nEVENT: {event}\nWHERE: {where}\n"
            f"MOVER: {mover}\nACTIVITY: {activity}")


def seg(name, text, birds=None):
    det = None if birds is None else {"frames": [[{"class": "bird"}] * birds]}
    return {"filename": name, "source": f"s3://x/{name}", "start_sec": 0, "reasoning": text, "detections": det}


# A stand-in for our real footage. The labels in filenames are deliberately
# scrambled in one test to prove decisions never read them.
DAY = [seg("coopcam_2026-10-08T15_34_34.mp4", reply("day", 6, "normal", "floor")),
       seg("coopcam_2026-10-08T15_35_00.mp4", reply("day", 7, "normal", "floor"))]
NIGHT = [seg(f"coopcam_2026-10-08T21_5{i}_00.mp4", reply("night", 2, "shifting", "perch")) for i in range(1, 6)]
FIGHT = [seg("coopcam_fight3_2026-10-09T06_20_41.mp4", reply("night (infrared)", 3, "fight", "fence"), birds=2),
         seg("coopcam_fight2_2026-10-09T06_20_59.mp4", reply("night", 3, "fight", "fence")),
         seg("coopcam_fight_2026-10-09T06_22_30.mp4", reply("night", 3, "fight", "floor"))]
NEST = [seg("coopcam_egglaying_2026-10-09T08_47_56.mp4", reply("day", 5, "peck", "nest_box"), birds=2)] + \
       [seg(f"coopcam_egglaying_2026-10-09T0{t}.mp4", reply("day", 4, "laying", "nest_box"))
        for t in ("8_57_49", "9_03_08", "9_03_45", "9_04_00", "9_04_15")]
ALL = DAY + NIGHT + FIGHT + NEST


class Parse(unittest.TestCase):
    def test_time_from_filename(self):
        self.assertEqual(recorded_at("coopcam_fight_2026-10-09T06_22_30.mp4").isoformat(), "2026-10-09T06:22:30")

    def test_markdown_and_word_numbers(self):
        p = parse_reply("**LIGHTING:** Night, infrared\n- TOTAL: three\n* EVENT: Fight\nWHERE: fence")
        self.assertEqual((p["lighting"], p["total"], p["event"], p["where"]), ("night", 3, "fight", "fence"))

    def test_garbage_is_cant_tell(self):
        self.assertFalse(parse_reply("A coop with some chickens in it.")["ok"])

    def test_yolo_formats(self):
        self.assertEqual(yolo_birds({"frames": [[{"label": "bird"}, {"label": "bird"}], [{"label": "bird"}]]}), 2)
        self.assertEqual(yolo_birds({"object_classes": {"bird": 3, "person": 0}}), 3)
        self.assertIsNone(yolo_birds(None))


class Decide(unittest.TestCase):
    def setUp(self):
        self.r = decide(build_clips(ALL))

    def test_headline(self):
        self.assertEqual(self.r["clips_recorded"], 16)
        self.assertEqual(self.r["events_that_matter"], 2)

    def test_three_fight_clips_are_one_high_event(self):
        fights = [e for e in self.r["events"] if e["kind"] == "fight"]
        self.assertEqual(len(fights), 1)
        f = fights[0]
        self.assertEqual((f["priority"], f["clip_count"], f["start"]), (HIGH, 3, "6:20 AM"))
        self.assertTrue(f["confirmed"])
        self.assertIn("in the dark", f["title"])
        self.assertIn("through the fence", f["title"])

    def test_peck_in_nest_box_is_low_bullying(self):
        p = next(e for e in self.r["events"] if e["kind"] == "peck")
        self.assertEqual(p["priority"], LOW)
        self.assertIn("nest box", p["title"])
        self.assertTrue(p["confirmed"])  # YOLO saw 2 birds

    def test_laying_session_is_one_info_event(self):
        lay = [e for e in self.r["events"] if e["kind"] == "laying"]
        self.assertEqual(len(lay), 1)
        self.assertEqual((lay[0]["priority"], lay[0]["start"], lay[0]["end"], lay[0]["clip_count"]),
                         (INFO, "8:47 AM", "9:04 AM", 6))
        self.assertIn("likely", lay[0]["title"])

    def test_night_shifting_is_noise(self):
        self.assertEqual(len(self.r["noise"]), 7)  # 5 night + 2 day

    def test_order_high_low_info(self):
        self.assertEqual([e["priority"] for e in self.r["events"]], [HIGH, LOW, INFO])

    def test_flock_size_learned_from_day(self):
        self.assertEqual(self.r["flock_size_seen"], 7)

    def test_labels_in_filenames_are_ignored(self):
        swapped = [dict(s, filename=s["filename"].replace("fight", "egglaying")) for s in FIGHT]
        r = decide(build_clips(swapped))
        self.assertEqual(r["events"][0]["kind"], "fight")

    def test_single_unconfirmed_fight(self):
        r = decide(build_clips([seg("coopcam_2026-10-09T06_20_41.mp4", reply("night", 2, "fight", "floor"))]))
        self.assertFalse(r["events"][0]["confirmed"])

    def test_other_animal_is_high(self):
        r = decide(build_clips([seg("coopcam_2026-10-09T02_00_00.mp4",
                                    reply("night", 4, "disturbance", "floor", mover="other_animal"))]))
        self.assertEqual((r["events"][0]["priority"], r["events"][0]["kind"]), (HIGH, "disturbance"))

    def test_unparseable_clip_is_cant_tell(self):
        r = decide(build_clips([seg("coopcam_2026-10-09T02_00_00.mp4", "blurry")]))
        self.assertEqual(len(r["cant_tell"]), 1)
        self.assertEqual(r["events"], [])

    def test_plain_report(self):
        text = plain_report(self.r)
        self.assertTrue(text.startswith("16 clips recorded. 2 things that matter."))
        self.assertIn("Filtered: 7 clips", text)


if __name__ == "__main__":
    unittest.main()
