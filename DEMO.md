# Demo script (3 minutes)

Numbers in [brackets] get confirmed from the app on build day.

## 1. Hook (25s)

> "Every video agent in this room watches people, cars or forklifts. Nobody's watching the animals."
>
> "We're Shepherd. We protect the ones who can't protect themselves, when nobody's there to watch."
>
> *(pause)*
>
> "Chickens."
>
> "I have a camera on my coop. It records every time something moves, so much that I'd turned the alerts off. Small farmers can't stand in the field all night, and they can't watch every clip either."

## 2. The morning report (35s)

- Open the app. The big line: **"16 clips recorded. 2 that matter."**
- Say: "This is my real coop, from yesterday afternoon to this morning. Shepherd watched every clip so I didn't have to."

## 3. The fight: HIGH (35s)

- The red card plays: **two roosters fighting through the fence, 6:20 AM, in the dark.**
- Say: "The camera recorded this 3 times. Shepherd reports it once: one fight, confirmed by three clips. 6:20 in the morning, before first light, nobody awake. That's how birds get hurt."

## 4. The peck: LOW (25s)

- The amber card: **a hen pecked while she's in the nest box.**
- Say: "This one's *worth watching*, not *wake up now*. Nest-box bullying can put a hen off laying. A motion sensor can't tell the difference between this and the fight. Shepherd can."
- Green card: "Good news: hen in the nest box 8:47 to 9:04, likely laying. It says *likely*, because no clip shows the egg."

## 5. The noise (15s)

- Open "Noise Shepherd filtered": **5 clips at 9:51 PM.**
- Say: "Motion at night, but it's just birds shifting on the perch. Filtered. You can check its work."

## 6. The guardrail (20s)

- Click **"See what Shepherd saw"** to open the W&B Weave trace.
- Say: "Cosmos describes, the rules decide, and the language model only writes the report. If it writes a number or a time that isn't in the evidence, we throw its text away. No clip, no claim."

## 7. Technical close (20s), read as bullets

- Our own footage through the **VAST DataEngine** pipeline
- A custom **Cosmos3-Reason** prompt turns every clip into an event
- **YOLO11** as the second signal; clips grouped into events
- Events written back to **VastDB** as Shepherd's memory
- **W&B** writes the report; **Weave** traces every decision
- Running on **CoreWeave**, built in **Cursor**

## 8. Last line

> "16 clips in. 2 that matter. Shepherd watches the flock, so the farmer can sleep."

---

## Prepared answers

- **Why chickens?** "It's our footage, and nobody else has it. The same rules work for anything a farmer can't watch all night: goats, sheep, a barn."
- **Didn't a chicken show up in SF?** "That one was crossing the road. Ours are picking fights."
- **Is the fight real?** "Yes. 6:20 this morning, my coop."
- **Night accuracy?** "Infrared is the hard case. That's why there's a second signal, and why anything unsure says unconfirmed."
- **Privacy?** "A coop camera: no people, private clips. I work in GRC; we kept it that way on purpose."
- **What's next?** A bedtime roll call, a sick-bird check, phone push alerts.

## What can go wrong

| Problem | Backup |
|---|---|
| The live app is slow | Keep talking: "it's reading every clip." |
| App won't deploy | Run `python3 agent.py` and show report.json plus the Weave trace |
| Cosmos misses the peck | It shows as noise. Say so honestly; the fight is the headline. |
| Cosmos miscounts | It shows as unconfirmed. That's the guardrail working, so say so. |

## Submission text (tokensand.com/vastnyc, closes 4:30)

**Short:** Shepherd reads every clip a farm camera records and tells the farmer the few that matter. On 16 real clips from our coop, it flagged a rooster fight at 6:20 AM (HIGH) and a hen pecked in the nest box (LOW), and filtered the rest.

**Built with:** VAST DataEngine, VastDB, NVIDIA Cosmos3-Reason, Cosmos Embed1, YOLO11, CoreWeave, Weights & Biases Inference + Weave, Cursor (+ NVIDIA Canary-1B if time allows).

**Needed:** repo link, demo video link, team names and emails.
