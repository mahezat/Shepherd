# Handoff: Jev escalation + Twilio SMS

**Owner:** teammate (Codex). **Deadline:** pushed by **3:00 PM**. Submission closes 4:30.
Mahmoud and Claude are on the demo video; Claude needs `out/escalations.json` and the SMS text for it.

## What to build

After Shepherd's rules produce events (`docs/report.json`), a separate step asks **Jev** (TypeSafe AI's
decision model) whether each event should be escalated to the farmer right now. If yes, send an **SMS via
Twilio**. This is third-party analysis that runs **alongside** the pipeline. It never blocks or changes the
report, and Shepherd's rules still decide what an event is and how urgent it is.

```
docs/report.json events ──> escalate/run.py ──> Jev: "text the farmer now?" (probability)
                                         └──> if yes: Twilio SMS (or preview) ──> out/escalations.json
```

## File ownership (important)

- Create everything under a **new `escalate/` folder** only.
- **Don't edit** `shepherd/`, `web/`, `docs/`, `video/`, `scripts/` or the clips. Claude owns those and is changing them now.
- Never commit keys. Read them from env vars; `.env` is gitignored.

## Inputs

`docs/report.json` → `result.events[]`. Each event has: `kind` (fight, peck, laying, disturbance), `priority`
(HIGH, LOW, INFO), `title`, `start`, `end`, `clip_count`, `confirmed`, `confirmed_by`, `why`, `clips[]`,
`evidence[]` (per clip: Cosmos answers, YOLO count, activity text).
Today's real data has 2 events: a HIGH fight at 6:22 AM and an INFO laying session 8:47 to 9:04 AM.

## Jev (TypeSafe AI)

- Endpoint: `POST https://api.typesafe.ai/v1/systemone`, header `Authorization: Bearer $TYPESAFE_API_KEY`.
  (Reachable; currently returns "Must supply an API key". We still need a key from console.typesafe.ai/keys.
  Their signups were paused in late September; ask the organizers if nobody has one.)
- Check the key: `GET https://api.typesafe.ai/v1/models`.
- One request per event. `state` = a short text summary built from the event (title, time, priority, why,
  confirmed_by, and each clip's Cosmos activity line). Suggested questions:

```json
{
  "model": "jev-latest",
  "state": "Coop camera, Fredon NJ. Event: Fight, in the dark, 6:22 AM. Shepherd priority: HIGH. Confirmed: full frame flagged a disturbance; Cosmos saw a fight in the center and 4x slow motion view. Why: Birds fighting can injure each other; nobody was there to break it up.",
  "questions": {
    "escalate": { "type": "noul", "instructions": "Should the farmer be texted about this right now, before morning?" },
    "welfare_risk": { "type": "score", "instructions": "How much risk is there to the animals' welfare?", "criteria": ["None", "Low", "Moderate", "High"] }
  }
}
```

- Response: `answers.escalate.noul` (probability of yes, 0 to 1), `answers.welfare_risk.score` and `.confidence`,
  plus `model` (log the versioned model name) and `usage`.
- Decision: escalate when `noul >= 0.5`. **Never escalate INFO events** (good news), even if Jev says yes.
  Log Jev's answer either way.
- If there's no key or the call fails: record `"jev": "unavailable"` and fall back to the rules (escalate only
  HIGH). Don't pretend Jev answered.

## Twilio SMS

- Env: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM` (a Twilio number), `FARMER_PHONE`.
  Mahmoud has the SID and token; get them from him directly, **not** through the repo or a chat log.
- Send: `POST https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json`, basic auth SID:token,
  form fields `To`, `From`, `Body`. Use the REST API with Python's standard library or `twilio` from pip.
- Message body (keep it under 160 characters):
  `Shepherd: HIGH at your coop. Fight, in the dark, 6:22 AM. Confirmed by 2 signals. See the clip: https://mahezat.github.io/Shepherd/`
- **Reality check, verified against Twilio's docs today:** the account is a **trial** with **no phone number**.
  Trials can only text up to 5 verified numbers and **can't send custom message bodies**, and US texting needs
  A2P 10DLC or toll-free verification, which takes days and needs a paid account. So:
  - Build `--send` mode properly, but default to **preview mode**: write the exact message to
    `out/escalations.json` with `"sent": false, "reason": "..."` and print it.
  - If Twilio's Console offers a **Virtual Phone** / "Try SMS" route, try one real test there and record the
    message SID if it works.
  - Never report `"sent": true` unless Twilio returned a message SID.

## Output: `out/escalations.json` (also print a short table)

```json
[{
  "event_title": "Fight, in the dark", "time": "6:22 AM", "priority": "HIGH",
  "jev": { "model": "jev-1.x", "escalate": 0.93, "welfare_risk": 2.6, "confidence": 0.88 },
  "decision": "escalate",
  "sms": { "to": "+1...last4", "body": "Shepherd: HIGH at your coop. ...", "sent": false, "reason": "preview mode: trial account" }
}]
```

Mask the phone number in output (last 4 digits only).

## Done means

1. `python3 escalate/run.py` runs with no keys (preview, Jev unavailable) and with keys, and writes the file.
2. `python3 escalate/test_escalate.py` passes: INFO never escalates; HIGH plus Jev yes escalates; no key falls back
   honestly; `sent` is only true with a SID; no secrets printed.
3. A short `escalate/README.md` describing the above.
4. Pushed to `main` by 3:00 PM. Tell Mahmoud the real Jev numbers (or "Jev unavailable") and whether any SMS
   actually sent. Claude puts exactly that in the video, with no claims beyond it.

## Pitch line (for reference)

"Shepherd's rules decide what happened. Jev, a fast decision model, decides whether it's worth waking the
farmer, without slowing anything down. Then Twilio texts them the clip."
