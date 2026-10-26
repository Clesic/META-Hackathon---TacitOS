# TacitOS

An evidence-backed support playbook that learns from observed work.

Prepared for the Meta Global AI Developer Hackathon, October 26–November 4, 2026.

## Intended demonstration

1. Observe completed synthetic support cases.
2. Use a Meta model to propose process patterns with case references.
3. Detect a contradictory case and mark the affected pattern as contested.
4. Suggest a next step for a new case, showing evidence and uncertainty.

These are planned capabilities, not a claim of a completed implementation.
The agent does not execute financial transactions.

## Development status

This initial repository contains setup documentation only. Existing local planning
documents and prototypes are excluded from this initial commit. Event-built
implementation and measured results will be added separately.

## Credentials

Keep API keys in a local `.env` file. Never put credentials in source files,
screenshots, recordings, or commits. An eventual application must call the model
from its backend so the key is not exposed in the browser.

## Data

The planned demonstration uses fictional support cases, clearly labeled synthetic.
Repeated observations are evidence of behavior, not approved business policy.
