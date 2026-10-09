# Demo script (3 minutes), real results

Everything below is what Shepherd actually produced on our 16 real clips today.

## 1. Hook (25s)

> "Every video agent in this room watches people, cars or forklifts. Nobody's watching the animals."
>
> "We're Shepherd. We protect the ones who can't protect themselves, when nobody's there to watch."
>
> *(pause)*
>
> "Chickens."
>
> "My coop camera records every time something moves, so much that I'd turned the alerts off. Small farmers can't stand in the field all night, and they can't watch every clip either."

## 2. The report (30s)

- Open the page. Big line: **"16 clips recorded. 1 matters."**
- Say: "My real coop, 3:34 yesterday afternoon to 9 this morning. NVIDIA Cosmos watched every clip. Fifteen were normal chicken business. One wasn't."

## 3. The fight (45s): the technical heart

- The red card: **"Fight, in the dark, 6:22 AM."** Play the clip; point at the back fence.
- Say: "Two roosters fighting through the fence before sunrise. At full frame the fight is a few dozen pixels in infrared, and the small Cosmos model said *normal*. So Shepherd zooms: it cuts every clip into five tiles and asks again. In the center tile, Cosmos saw the fight. It found zero fights in the other 15 clips."
- Point at the badge: "Confirmed by two signals: the full frame flagged a disturbance, the zoom saw a fight."

## 4. Good news (20s)

- Green card: **"Hen in the nest box, likely laying, 8:47 to 9:04 AM."**
- Say: "Six clips of a hen shifting in the box. Shepherd reports one session, not six alerts. It says *likely*, because no clip shows the egg."

## 5. The guardrail (30s)

- Say: "NVIDIA's Nemotron on W&B writes the report, but the rules decide. Shepherd checks every draft: no new numbers, no changed priorities, every event named. Earlier today Nemotron invented a second alert, twice, and Shepherd threw both drafts away."
- On your laptop (logged in), open **wandb.ai/maxmoud/shepherd/weave** → Traces. Point at the **…reason** column ("model changed a priority", "model wrote numbers…"), then open a rejected run → **write_report** → Output → **rejected** to show the invented alert.
- Say: "Every Cosmos answer, every rule and every rejected draft is traced. No clip, no claim."

## 6. Technical close (20s), read as bullets

- 16 of our own clips, uploaded to the **VAST AI OS**; every event is written to **VastDB** with its evidence and read back to verify (vast/write_events.py)
- **NVIDIA Cosmos Reason** on **CoreWeave** GPUs: a structured description, three yes/no checks and 5 zoomed tiles per clip
- **YOLO11** bird counts
- Rules group repeat clips into one event and set the urgency
- **NVIDIA Nemotron** on **W&B Inference** writes the report; a guard rejects invented numbers or alerts
- **W&B Weave** traces every decision; built with **Cursor**

## 7. Last line

> "Sixteen clips in. One that mattered. Shepherd watches the flock, so the farmer can sleep."

---

## Prepared answers

- **Why chickens?** "It's our footage, and nobody else has it. The same rules work for anything a farmer can't watch all night: goats, sheep, a barn."
- **Didn't a chicken show up in SF?** "That one was crossing the road. Ours are picking fights."
- **What did it miss?** "Be honest: there was also one peck in the nest box at 8:47, and the small model didn't catch it, even zoomed in. Two other fight clips came back normal too. We show what Cosmos actually said; we didn't tune it to the answer."
- **Only if a judge asks "is the data in VastDB right now?"**: "The writer's built and in the repo; today the organizers' VastDB couldn't take the load, so we ran the same Cosmos and YOLO endpoints directly. It writes the moment the endpoint's back." Don't bring this up yourself.
- **Privacy?** "A coop camera: no people. I work in GRC; we kept it that way on purpose."
- **What's next?** A bedtime roll call, sick-bird checks, phone alerts, and the bigger Cosmos model for small, far-away action.

## What can go wrong

| Problem | Backup |
|---|---|
| Page won't load | The repo's docs/ folder has the same page; or show report.json |
| Video won't play | Use the poster frame and describe it |
| Weave link asks for login | Only your team can view it (no public option on this plan); show it from your own logged-in laptop |

## Submission text (tokensand.com/vastnyc, closes 4:30)

**Short:** Shepherd reads every clip a farm camera records and tells the farmer what matters. On 16 real clips from our coop, NVIDIA Cosmos (with a zoom pass for small, far-away action) found a rooster fight at 6:22 AM and a laying session, and filtered the rest. A guard rejected Nemotron's report drafts when they invented an alert.

**Built with:** VAST AI OS, NVIDIA Cosmos Reason, YOLO11, CoreWeave GPUs, NVIDIA Nemotron on Weights & Biases Inference, W&B Weave, Cursor.

**Links:** repo github.com/mahezat/Shepherd · report page (share it as public first) · demo video.
