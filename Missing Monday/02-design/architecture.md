# Proposed architecture

Status: design only. Preferred simple stack: Python/FastAPI, SQLite and a small browser interface. Final package versions should be pinned at implementation time. No separate vector database or job service is needed for the first few dozen cases.

## Components

- Rehearsal runner exposes cases, documents and allowed actions.
- Attempt recorder stores a sequence of evidence requests, decisions and expert contacts.
- Model adapter sends bounded, role-specific context to Meta and validates structured output.
- Gap service classifies the blockage and requests missing context.
- Guidance service stores versioned cards and exact-version approvals.
- Transfer runner launches fresh cases against a frozen guidance snapshot.
- Evaluation service reads held-out expected outcomes outside the model context.
- Report view links claims to attempts, card versions and test outcomes.

## Context isolation

The successor can access the public handbook, the current case and approved applicable cards. The gap analyst can access the stalled attempt, available public evidence and already-approved cards. The extractor sees the expert's submitted answer. Neither receives the entire hidden rulebook or expected-outcome file.

The expert-only fixture supports an explicitly simulated expert for development. It must never be sent to the successor or copied into a public UI response. The evaluator reads the oracle locally after the attempt. Serving the project directory as a static folder would violate these boundaries; serve only the designated frontend assets.

## Model responsibilities

Use one Meta model for diagnosis, question formation and extraction initially. A model ID is configuration, not an assumption that access is available. Earlier TacitOS documentation reports a successful `muse-spark-1.3` experiment; this is historical context, not verification of the new project's integration.

Tools should be constrained operations such as `read_public_document`, `get_attempt`, `propose_gap`, `request_expert_answer` and `draft_guidance`. Approval, oracle access and business execution are not model tools. Validate referenced IDs, required fields, field lengths and allowed enum values. Semantic evidence checks still require review; valid JSON alone proves little.

## Evidence and deterministic evaluation

The scenario engine, not model prose, determines whether a final action satisfies a synthetic rule. Missing facts are unknown, not false. A safe escalation may avoid error but is not independent task completion. The report distinguishes safe handling, completion and direct expert dependence.

Use fixed held-out fixtures for the benchmark. Adaptive generated cases belong to exploration until validated and frozen. Keep model failures as failures or missing results, never substitute a canned response and report model success.

## Reliability

Store a run before starting a model request. Bound timeouts and retries; use idempotency keys for card creation and approval. Resume safely after a timeout. Log prompt version, model ID, request ID if available, usage, latency and status without credentials. Do not log raw provider error bodies by default.

## Planned endpoints

`POST /sessions`, `GET /sessions/{id}/case`, `POST /attempts`, `POST /attempts/{id}/actions`, `POST /attempts/{id}/analyze-gap`, `POST /gaps/{id}/answers`, `POST /answers/{id}/extract`, `POST /cards/{id}/versions/{version}/review`, `POST /sessions/{id}/retests`, `GET /sessions/{id}/report`.

These are proposed contracts, not working routes. A future real pilot needs authentication and authorization beyond the local role switch.

## Resource allocation update

Use Meta API as the primary runtime under the [resource plan](../06-build/resources-and-budget.md). Keep the model adapter small. Baseten Muse Spark Open is a conditional fallback or separately labelled portability experiment, not a second mandatory runtime. Store provider and model in each run record and freeze both for benchmark comparisons. ChatGPT, Cursor and Gemini subscriptions are development/review resources, not application dependencies.
