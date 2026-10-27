# Implementation backlog

All items below are unimplemented unless explicitly marked in a later status update.

## B01: loader and simulator — first

Load public cases independently from hidden rules. Expose only allowed facts. Evaluate actions against the synthetic oracle. Acceptance: all prepared fixture expectations agree with the simulator; model context contains no hidden file contents.

## B02: storage and sessions

Create sessions, append-only attempt actions, model-run records and reset support. Acceptance: repeated action IDs do not duplicate effects; sessions cannot read each other's data accidentally.

## B03: model adapter

Configure a server-side key and model ID. Add bounded timeout, validated output, safe errors and local trace recording. Acceptance: missing keys fail clearly; no authorization header enters logs or client responses; actual model output is saved as such.

## B04: gap diagnosis

Provide case, public evidence and failed attempt. Parse category, missing distinction, citations and question. Acceptance: missing access yields a permission gap; absent substitution guidance yields a knowledge gap without inventing the substitution rule.

## B05: answer extraction and review

Create versioned guidance from submitted expert answers. Require real quote matches and approval of a content hash. Acceptance: edits become drafts; rejected cards cannot be retrieved; reviewers can correct scope.

## B06: successor guidance

Filter approved versions by workflow and conditions; return evidence or a request for missing facts. Acceptance: unknown machine revision or certificate cannot be assumed eligible. Conflicting cards cause review.

## B07: fresh retests

Freeze a guidance snapshot and assign an unused test case. Acceptance: completion is determined independently; expert contact is counted; reused training cases are not credited as transfer.

## B08: focused interface

Build start, task, expert review and evidence views. Acceptance: keyboard operation works, synthetic status is visible and errors preserve entered work.

## B09: evaluation runner

Execute comparisons with fixed model settings and shuffled case aliases. Store fixture hashes, prompts, usage, costs when known and outcomes. Acceptance: every attempted run has a record; missing results stay missing; no average conceals negative-case failures.

## B10: packaging

Write accurate run instructions, inspect the export, record the real demo and update submission copy. Acceptance: a fresh local setup can reproduce the deterministic flow, and the live model path either succeeds or reports configuration failure honestly.

## Tests that matter

Prioritize leakage boundaries, approval bypass, version edits, negative cases, missing fields, duplicate submission, model timeouts, oracle consistency and score calculations. Do not confuse tests of the synthetic rules with evaluation of model intelligence.
