# Start here (teammate brief)

## What we're building, in 30 seconds

**Shepherd** is a video agent for small farms. A motion camera on our chicken coop records a clip every time something moves, which is far too many for anyone to watch. Shepherd reads every clip with NVIDIA Cosmos, groups repeat clips into one event, decides how urgent each event is, and hands the farmer one morning report with the clip behind every line.

On our real footage (16 clips, in `clips/`), the result should be:

> **16 clips recorded. 2 that matter.**
> HIGH: two roosters fighting through the fence, 6:20 AM, in the dark (3 clips, reported as one fight)
> LOW: a hen pecked while she's in the nest box, 8:47 AM
> Good news: hen in the nest box 8:47–9:04, likely laying
> Filtered: everything else, including 5 clips of birds shifting at 9:51 PM

**The pitch:** "Every video agent in this room watches people, cars or forklifts. Nobody's watching the animals." In SF, none of the 30 public projects were about animals.

## Where everything is

| File | What it's for |
|---|---|
| `DESIGN.md` | **The spec.** Rules, honesty guardrails, sponsor map. Read this first. |
| `PROMPTS.md` | Paste-in Cursor prompts, in order, with target times |
| `DEMO.md` | The 3-minute demo script and submission text |
| `prompts/cosmos_ingest_prompt.txt` | The instructions Cosmos follows for every clip |
| `clips/` | Our 16 real coop clips. The recording time is in each filename. |

## Today

| Time | What |
|---|---|
| 9:30 | Building starts |
| ~10:00 | Clips uploaded and indexing (PROMPTS step 2) |
| 10:45–12:30 | Rules + agent + morning report (steps 4–5) |
| 12:30 | Lunch |
| 12:45–2:15 | Web app deployed at /app (step 6) |
| 2:15 | Voice, **only** if everything else works (step 7) |
| 2:45 | Code pushed to this repo (step 8). **Required for submission.** |
| 3:30 | Record the demo video |
| **4:30** | **Submission closes** at tokensand.com/vastnyc (repo link + video link + names and emails) |

## Who does what (suggested)

- **On the VM:** work through PROMPTS.md in order. Only 2 people per team can launch a VM, so if we both have one, split it: one person does steps 2–5 (ingest, rules, agent), the other does step 6 (the app) once step 5 produces `out/report.json`.
- **Mahmoud:** stage and demo, DEMO.md, the demo video, submission. He has Claude reviewing the Cosmos output and fixing prompts. When step 3 prints its table, send it his way.

## Ground rules

- **Never commit keys or passwords.** Credentials live in the VM's environment. Don't copy them into code.
- **Never decide from filename labels** (fight, egglaying). They're for humans. Only Cosmos and YOLO decide. A judge will ask.
- **Upload clips as private** (`is_public=false`).
- **No internet video.** Only our own footage.
- **Push to GitHub early and often.** Last time Mahmoud's team lost a win because the repo link was missing.
- When Cosmos or YOLO is unsure, Shepherd says **"unconfirmed"** or **"can't tell."** That's a feature; don't hide it.
