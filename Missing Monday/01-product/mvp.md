# MVP and acceptance criteria

## One complete experience

A synthetic purchasing task stalls under the handbook. The system identifies the missing condition and asks a grounded question. The expert supplies and approves guidance. A successor uses it on a new case. A boundary case remains blocked or is correctly rejected. The UI presents the evidence and the remaining limits.

## Required

- Reproducible local rehearsal with reset and clearly labelled synthetic data.
- Distinct expert and successor views. This is role separation in a local demo, not secure enterprise authentication.
- Case evidence, permitted actions and a deterministic outcome evaluator.
- A real Meta call for gap analysis and guidance extraction.
- A gap record tied to an attempt, including non-knowledge classifications.
- Exact-version review: draft, approved, rejected, superseded or revoked.
- Successor guidance retrieved only from approved, applicable versions.
- Fresh retest with a trace of available evidence, guidance and final action.
- A report showing completed tasks, incorrect actions and expert interventions separately.
- Explicit model errors, abstention and unresolved states.

## Acceptance scenarios

1. Unknown substitution: before capture, the successor can request expert help and cannot claim successful independent completion.
2. Correct expert answer: the draft preserves supplier, machine revision, part mapping and certificate conditions, with a real answer reference.
3. Review control: rejecting the draft prevents its use; editing approved content requires a new review.
4. Positive transfer: a new eligible order is correctly completed without direct expert contact.
5. Negative transfer: an ineligible machine revision is not accepted using the same card.
6. Missing evidence: a missing certificate produces a request or escalation, not an invented certificate.
7. Non-knowledge blockage: unavailable permissions are reported separately and never counted as a knowledge dependency repaired.
8. Failure: a model timeout leaves the attempt and gap intact and displays an actionable error.
9. Revocation: revoked guidance disappears from active retrieval, while historical reports retain their original version references.

## Deliberate cuts

No production procurement, employee ranking, fine-tuning, sovereignty toggle, broad dashboard, open-weight hosting, camera capture, browser surveillance, multi-company support or agent swarm. No arbitrary tool execution. Voice is optional; a text answer is sufficient to prove the loop.

## First credible milestone

One scenario family runs end to end with real model output, reviewed guidance and a fresh deterministic test. A hand-written happy path or prefilled answer cannot stand in for the actual extraction step.
