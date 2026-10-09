# Build day: Cursor prompts, in order

Paste each block into the Cursor agent on the event VM (`cd ~/vast-builders-challenge && agent`).
Wait for each step to finish. Times are targets. **Submission closes 4:30 PM.**

---

## 0. 9:45 – Health check

```
run a git pull, then check that everything is working. List env variable NAMES only, never values.
```

## 1. 9:50 – Get our project and clips

```
Clone https://github.com/mahezat/Shepherd into ~/shepherd. Read DESIGN.md: it's the spec for
everything we build today. Our 16 clips are in ~/shepherd/clips and the Cosmos prompt is in
~/shepherd/prompts/cosmos_ingest_prompt.txt.
```

## 2. 9:55 – Upload the clips (start early: indexing takes minutes)

```
Use the ingest/upload-video skill to upload every .mp4 in ~/shepherd/clips, one request per file.
Choices, so you don't need to ask:
- visibility: private (is_public=false)
- prompt mode: custom prompt = the exact contents of ~/shepherd/prompts/cosmos_ingest_prompt.txt
- camera_id: coop_cam-1, location: coop
- capture_type: closest value from ingest-config (surveillance if it exists)
- tags: shepherd
Show the confirmation table once, upload, report each object_key, then poll explore (scope=mine)
until all are indexed. Save a map of object_key -> original filename to ~/shepherd/out/uploads.json
(the filename holds the recording time).
```

## 3. 10:20 – Check what Cosmos wrote

```
For every coop_cam-1 segment, print a table: original filename, segment start, the Cosmos
LIGHTING / TOTAL / EVENT / WHERE / MOVER lines, and the YOLO "bird" count (max in any single frame,
from videos/detections). Flag any segment whose reply doesn't follow the format.
```

**Check by eye:** the 3 fight clips should say `fight`, the 5 clips at 21:5x should say `shifting`,
the nest clips should say `laying`, and the 08_47_56 clip should say `peck`. If not, paste the table to
Claude and we'll adjust the prompt and re-ingest just those clips.

## 4. 10:45 – The rules (the core)

```
Write ~/shepherd/shepherd/rules.py implementing the "How a clip becomes a decision", "The rules"
and "Rules that keep it honest" sections of DESIGN.md exactly.
- Recording time comes from the filename (coopcam_..._YYYY-MM-DDTHH_MM_SS.mp4). NEVER use the label
  words in the filename (fight, egglaying, ...) for any decision; only Cosmos and YOLO decide.
- Parse each Cosmos reply into fields (missing -> None, unparseable -> "can't tell").
- Group consecutive clips with the same event: fights within 10 min, nest-box/laying within 20 min.
- A peck that falls inside a laying session becomes "nest-box bullying" (LOW).
- Confirmed = 2+ clips in the group agree, or YOLO sees >= 2 birds for a fight or peck.
- Every event carries its clip list, start and end times, and a facts dict of the numbers it used.
Write unit tests with made-up Cosmos replies covering every rule, and run them.
```

## 5. 11:30 – The agent + morning report + memory

```
Write ~/shepherd/agent.py:
1. Pull all coop_cam-1 segments (reasoning, YOLO count, source, original filename) and run rules.py.
2. Ask a Weights & Biases serverless inference model (OpenAI-compatible; WANDB_API_KEY,
   WANDB_TEAM, WANDB_PROJECT from the env; list the models and pick a Llama or Qwen instruct model)
   to write the morning report from the rule output only, in the format in DESIGN.md. If the report
   contains any number or time that isn't in the facts, throw it away and use a plain template.
3. Headline: "[N] clips recorded. [M] that matter." (M = HIGH + LOW events.)
4. Trace parse, grouping, rules and the LLM call with W&B Weave
   (weave.init(f"{WANDB_TEAM}/{WANDB_PROJECT}"), @weave.op), and save each event's trace URL.
5. Use the vastdb-write skill to write each event and the report to a new VastDB table
   shepherd_events in our team's database.
6. Save ~/shepherd/out/report.json. Run it and show me the report.
```

## 6. 12:45 – The app (on CoreWeave, not localhost)

```
Use the deploy-app-no-registry skill to deploy a one-page web app at /app called "Shepherd".
- Top: the morning report card. Big line: "[N] clips recorded. [M] that matter."
- One card per event: HIGH red, LOW amber, laying session green. Each shows the headline, the
  time range, a "confirmed" / "unconfirmed, check the clip" badge, the clips playing inline
  (videos/stream with ?token=), and a "See what Shepherd saw" link to the Weave trace.
- A collapsed "Noise Shepherd filtered" list with those clips, so judges can check them.
- Dark green and cream, readable from across a room, works on a phone screen.
Tell me how to open it (workshop.thecosmoslabs.com -> App).
```

## 7. 2:15 – Stretch, only if everything above works: voice (Canary)

```
Add a mic button to the app: record WAV directly in the browser (Web Audio, not webm), send it to
Canary-1B at $CANARY_1B_URL/v1/audio/transcriptions (see gpu/model-smoke-test; a /v1/models 404 is
normal), then answer the transcript with the W&B model using report.json only. Add a .wav upload
box as a fallback if the browser blocks the mic.
```

## 8. 2:45 – Push the code to GitHub (required)

```
In ~/shepherd: add a .gitignore (out/, .env, __pycache__), scan everything for keys or passwords
first, commit, and push to https://github.com/mahezat/Shepherd main. If git asks for credentials,
run gh auth login with the device-code flow and tell me the code.
```

Fallback: tell Claude, and Claude pushes the code from its side.

## 9. 3:30 – Record the demo video. 4:15 – Submit.

Follow DEMO.md. Go to https://tokensand.com/vastnyc → Submit your project. You need the repo link,
the video link, the description, and names and emails.
