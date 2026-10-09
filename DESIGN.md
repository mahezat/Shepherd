# Shepherd: Design

> Shepherd reads every clip your farm camera records and tells you the ones that matter, because nobody's watching the animals.

## Mission

Predators and problems don't keep business hours, and small farmers can't stand in the field all night. Round-the-clock monitoring is priced for industrial operations. Meanwhile the cameras small farms do have record so much noise that people switch the alerts off.

Shepherd has two goals:

- **Animal welfare:** no bird gets hurt because nobody was watching.
- **Farmer resources:** the watch a small farm can't afford to hire.

## What makes it different

We checked the 30 public SF projects from this series. About 10 were safety "detect and alert" tools for warehouses and traffic, and **none were about animals or farms**. Shepherd's edges:

1. **The first agent for animals,** on real footage from our own coop.
2. **It filters noise instead of adding it.** The headline number is "16 clips recorded, 2 that matter."
3. **It turns a run of clips into one event.** A motion camera records the same fight or the same hen many times; Shepherd reports it once.
4. **Its output is a morning report,** one card you read with coffee, not a dashboard.

## The footage (real, our own coop, 16 clips)

| Clips | Recorded | What it shows | Expected result |
|---|---|---|---|
| 2 | Oct 8, 3:34–3:35 PM | Daytime, chickens being chickens | Noise. Also used to learn the flock size. |
| 5 | Oct 8, 9:51–9:55 PM | Night, birds shifting at rest | Noise: motion at night, nothing wrong |
| 3 | Oct 9, 6:20–6:22 AM | Two roosters fighting through the fence, in the dark (first light was about 6:32, sunrise 7:00) | **One HIGH event** |
| 6 | Oct 9, 8:47–9:04 AM | A hen in the nest box, shifting; in one clip another hen pecks her | **One laying session**, plus **one LOW event** (the peck) |

Every filename holds its recording time: `coopcam_[label_]YYYY-MM-DDTHH_MM_SS.mp4`. The labels are for us; Shepherd must **never** read them. It uses only the time.

## How a clip becomes a decision

1. **Cosmos Reason describes the clip** in a fixed format (`prompts/cosmos_ingest_prompt.txt`): lighting, how many chickens, the event (fight, peck, laying, shifting, normal, disturbance), where it happened, what moved, and one sentence.
2. **YOLO counts the birds** as a second signal.
3. **Clips are grouped into events.** Consecutive clips with the same event, close in time, form one event: within 10 minutes for a fight, within 20 for a nest-box session.
4. **The rules decide** (table below).
5. **The W&B model writes the morning report** from the rule output only.

## The rules (written as code at the event)

| Event | Fires when | Priority |
|---|---|---|
| **Fight** | Cosmos says fight. One event per group of clips. "At night" gets added when the lighting is night. | HIGH |
| **Disturbance** | The mover is another animal or a person | HIGH |
| **Peck** | Cosmos says peck. If it lands during a nest-box session: "nest-box bullying, worth watching." | LOW |
| **Laying session** | Nest-box clips grouped into one session: "hen in the nest box 8:47–9:04, likely laying." Not an alert; good news. | INFO |
| **Noise** | Shifting, normal, or nothing visible. Counted and listed, never alerted. | — |

## Rules that keep it honest

- **Confirmed vs unconfirmed.** An event is "confirmed" when two signals agree: two or more clips in the group say the same thing, or YOLO sees at least 2 birds in a fight or peck. Otherwise it reads "unconfirmed, check the clip."
- **"Likely laying," never "1 egg,"** unless a clip actually shows the egg.
- **Can't tell.** If Cosmos's reply can't be parsed, the clip is listed as "can't tell." Never a guess.
- **No clip, no claim.** Every line in the report links to its clips.
- **The language model only writes sentences.** If its text contains a number or time that isn't in the evidence, the text is thrown out and a plain template is used instead.
- **Flock size is learned,** from the most chickens seen together in a day clip. Never hard-coded.

## The morning report (the product)

One card, readable on a phone:

> **16 clips recorded. 2 that matter.**
> HIGH: Two roosters fighting through the fence at 6:20 AM, in the dark (3 clips).
> LOW: A hen was pecked while in the nest box at [time]. Nest-box bullying can put a hen off laying.
> Good news: a hen in the nest box 8:47–9:04 AM, likely laying.
> Filtered: 11 clips of normal chicken business, including 5 at 9:51 PM.

## Sponsor map

| Sponsor | Role |
|---|---|
| **VAST DataEngine + S3** | Our clips go through the pipeline with our custom Cosmos prompt |
| **VastDB** | Holds Cosmos's descriptions and YOLO's detections. **Shepherd writes its events and morning report back to VastDB** as its memory. |
| **VAST search** | Finds moments across the archive ("show me every fight") |
| **NVIDIA Cosmos3-Reason** | The core: what happened in each clip |
| **NVIDIA YOLO11** | The second signal: bird counts |
| **NVIDIA Cosmos Embed1** | Search embeddings, through the pipeline |
| **NVIDIA Canary-1B** | Stretch goal: ask "anything happen last night?" out loud |
| **CoreWeave** | GPUs for every model, and the app runs on their cluster |
| **W&B Inference** | Writes the morning report |
| **W&B Weave** | Traces every decision ("see what Shepherd saw") |
| **Cursor** | Where we build |

## Back pocket (Q&A only)

- A bedtime roll call: everyone on the perch at dusk
- A wake-up check: a hen that doesn't come down in the morning
- A sick-bird check: a bird that stays in a corner
- Push alerts to a phone
- Any animal that beds down at night: goats, sheep, a barn
