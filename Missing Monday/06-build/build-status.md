# Build status — October 27, 2026

Local app foundation implemented with Python standard library HTTP server, SQLite and HTML/CSS/JavaScript. Start with `python3 -m app.server`; see [run instructions](../RUNNING.md).

Working: 22 synthetic cases, public handbook, saved attempts, reasons, expert-help requests, idempotent action submissions, session isolation, independent synthetic grading and practice totals. Browser check confirmed case start and saved expert-help request. That smoke-test attempt remains in the browser session; start a new session for your own rehearsal.

Validation: seven automated tests pass, covering all 22 expected fixture actions, help versus independent completion, duplicate/conflicting retries, completed attempts, persistence, public field boundaries, invalid requests and local HTTP access protections. Fixture/link validation also passes. These are software checks, not AI performance results.

No Meta or Baseten requests; API spend $0. AI gap diagnosis, expert answers, versioned approval and fresh transfer evaluation remain unimplemented. No deployment or publication. The dependency-free server replaces the proposed FastAPI stack for this local foundation only.

Next: add a server-side Meta adapter and grounded gap diagnosis within the initial $5 testing cap, after verifying actual pricing and available credits.

## Guided rehearsal update

Evidence opening and citations are now persisted. The interface requires an opened source for new decisions and records the participant's stated blocker as an open gap. History supports revisiting any attempt and its action trail. Existing requests survive migration. Ten automated tests pass, including new evidence-reference validation, scoped/idempotent inspection, saved gap persistence and repeated missing-evidence requests. Browser verification covered a new case, opening guidance, citing it and saving a specific knowledge question. No AI diagnosis or provider spending.

## Review fixes — October 27

- Closed an evidence-validation bypass: null/omitted evidence cannot create new actions. Every new action must cite an opened source. Earlier uncited historical actions remain readable.
- Corrected grading so an unnecessary evidence request is not automatically labelled safe handling. Pausing is reported separately from an appropriate next step.
- Reading documents after a final submission no longer modifies the original exposure record.
- Added per-attempt browser draft recovery for text, choices, citations and retry IDs. The selected attempt also survives reload. Draft storage is device-local; actual submitted work remains in SQLite.
- Serialised UI requests to avoid changing attempts while another request is saving, added recovery for unavailable stored sessions, highlighted the current attempt, and hid irrelevant gap-category controls for final decisions.

Verification: 14 automated tests pass; JavaScript syntax check passes; browser test verified text/citation restoration after reload and action-dependent controls. No model integration, live expert study or provider spending occurred.

## Handover loop — October 27

A successor question in the knowledge or unknown category can now be approved or rejected. Approval stores the typed answer as the next version for that case family and shows it, with the original question, when a later case in the same session opens approved guidance. Rejection stores no card. Another session cannot read the card. The case list is grouped into rehearsal, fresh, boundary and handbook cases, and the three stage labels follow the open attempt.

Verification: 16 automated tests pass, including same-session retrieval, a second approval being refused, and a rejected answer staying unpublished. The model is still not called.
