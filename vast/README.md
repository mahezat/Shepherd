# Shepherd's VAST work

This directory owns the VAST integration only. The teammate owns `shepherd/`, `web/`, `docs/` and `scripts/vm_*.py`.

## On the event VM

From the Shepherd checkout, install the official VastDB SDK:

```bash
python3 -m pip install -r vast/requirements.txt
```

If the VM refuses system package installation, use its existing Python environment or create a venv under ignored `out/` and run the commands with that environment's Python.

### 1. Check the upload batch

```bash
python3 -u vast/check_pipeline.py --pods --export-if-processing
```

The checker reads the assigned `/config/*.config` without printing credentials; authenticates normally; checks all sixteen original upload keys from `data/uploads.json`; and verifies matching VAST original-video URIs and readable reasoning segments. An HTTP 200 with zero indexed uploads is not reported as success. `--pods` reads only the assigned team's pod status and restart counts.

If at least one of the uploaded clips has completed reasoning, the wrapper runs the teammate's exact command:

```bash
python3 -u scripts/vm_ingest.py --export
```

It first backs up the current direct-GPU segment file under ignored `out/`, because the export script can replace it with a partial result. It records the exporter exit code and rechecks readiness. Do not push that export's application/data changes without coordinating with the teammate.

Evidence goes to `out/vast-pipeline-check.json`. If processing remains unverified, show event staff that receipt and ask:

> Team 32 uploaded sixteen private coop clips at approximately 15:04 UTC. The batch still has no verified indexed reasoning results. Please check DataEngine ingestion, worker backlog and the team's VSS table/backend readiness. Upload keys and current HTTP/pod status are available on the VM.

The saved explore response previously listed zero indexed chunks. That historical file is not a live health check.

### 2. Review the event write

```bash
python3 -u vast/write_events.py
```

This prints the assigned team bucket, existing `VDB_SCHEMA`, target `shepherd_events`, exact column schema and row IDs. It writes the review plan to ignored `out/vast-write-plan.json` and does not connect to VastDB or create a table.

The [official write skill](https://github.com/vast-data/vast-builders-challenge/blob/main/.cursor/skills/vast-database/vastdb-write/SKILL.md) says: “Confirm the target **schema / table** and column schema with the user before creating.” Review/approve this plan before the next command.

### 3. Write and verify

```bash
python3 -u vast/write_events.py --write
```

This connects to the assigned `S3_ENDPOINT` data VIP using the existing team credentials and bucket. It creates `shepherd_events` as a sibling in the already configured schema, inserts missing snapshot rows, then reads them in a separate committed transaction and compares every source field. An existing incompatible table causes a failure requiring coordination.

Repeat writes of the same report and segment snapshot insert zero duplicate rows. A changed source snapshot gets new IDs, preserving provenance. The receipt includes verified row IDs, source hashes, insertion count and read-back count at `out/vast-write-receipt.json`.

Stored fields preserve the original event JSON, report/model/Weave provenance, recording timestamps and separate UTC storage time. `source_confirmed` is the report's claim, not independent verification. Audit flags identify contradictions with saved checks and the limitations of nest/YOLO/repeated-clip observations. Writing results does not verify pipeline indexing or semantic search; the receipt states that explicitly.

This writer always consumes the **current** `docs/report.json`. If the teammate regenerated the report, pull first and review the new plan before writing.

## Local checks and delivery

```bash
python3 -m unittest discover -s vast -p 'test_*.py' -v
```

Tests use synthetic service/SDK fixtures and the current report for parsing. They do not count as live sponsor proof.

Push only the files in `vast/`:

```bash
git add vast/
git commit -m "Persist Shepherd events in team VastDB with read-back proof"
git push origin main
```

No credentials, output receipts or application files belong in this commit.
