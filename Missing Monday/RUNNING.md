# Run Missing Monday locally

Requires Python 3.9 or later. No packages, API keys or internet access are required for this foundation build.

From the Missing Monday folder:

```sh
python3 -m app.server
```

Open http://127.0.0.1:8766 in your browser. Stop with Ctrl+C. To use a different port: `python3 -m app.server --port 8767`.

Run checks:

```sh
python3 -m unittest discover -s tests -v
python3 tools/validate_pack.py
```

## Guided rehearsal

Open order details, handbook or approved-guidance status. Select the opened sources that support your decision, enter your reasoning or question, and choose an action. Help, evidence and access requests create saved gap records. Categories are selected by the participant or the explicit request type, not inferred by AI.

To rehearse the handover, start `S01 · Rehearsal`, ask the expert, then type Morgan’s answer and choose **Approve this version**. Start `S02 · Fresh case` and open **Approved exception guidance**. That card is the text you typed. A different browser session cannot see it. Rejecting an answer does not publish it.

Use attempt history to revisit prior cases and their cited action trail. Existing requests without a category remain unclassified gaps.

## What works

All 22 synthetic cases, public handbook, saved sessions and attempts, reason capture, expert-help requests, typed expert approval, fresh-case retrieval of approved cards, independently evaluated practice outcomes and session totals. Reloading restores the browser's current session. A new session preserves earlier database records and switches the browser to a fresh session. There is no deletion button yet.

SQLite data is saved in `runs/missing-monday.sqlite3`, excluded by the project ignore rules. You can use `--db /path/to/another.sqlite3` for an isolated rehearsal. Browser local storage holds a random session access token; clearing it starts a new session. This is a local demo, not production authentication. Do not expose the server beyond loopback or use real employee information.

## Draft recovery

Unsubmitted notes, selected action, gap category and citations are saved per attempt in this browser. Reloading or switching attempts restores them. Browser storage may be unavailable or cleared; a visible message reports a storage failure. Submitted records are stored separately in SQLite. Reviewing a completed attempt does not change its original evidence exposure.

## Boundaries

Model calls use Baseten `meta-models/muse-spark-open-1026`. **Diagnose why this stalled** asks one question. **Suggest the next step** recommends an action from the opened evidence and any approved card. **Draft the card** turns the expert’s own words into a quotable card. **Break the card** proposes two or three harder orders from the approved substitution card, then grades them locally. None of these calls sees the hidden rulebook. Diagnose, suggest, and break do not approve a card. A failed attack opens a tighter draft and leaves the previous card approved until that new wording is approved. Spend for this database is capped at $5. A failed call leaves the saved rehearsal unchanged.

The page, script, stylesheet, and favicon are the only files served. The handbook is explicitly selected; hidden expert rules and oracle files are not served. The server reads expected outcomes locally for synthetic grading. These development cases are public and must not be presented as a private held-out benchmark.

## Design decision

This setup uses Python's standard-library HTTP server and SQLite to avoid an installation dependency. It is appropriate for a bounded local prototype only. The earlier FastAPI proposal can be adopted when a richer API becomes useful; it is not an installed dependency today.
