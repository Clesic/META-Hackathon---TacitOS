# Tomorrow: Tuesday, October 27

## Outcome by the end of the day

Open Missing Monday locally, start a synthetic purchasing case, inspect its evidence and request help. A real Meta call should identify the missing substitution condition and produce a focused question for the expert. The app must preserve the attempt and correctly distinguish knowledge gaps from missing documents or permissions.

This is the first vertical slice. Expert extraction, approval and transfer are the next two days. Tomorrow's goal is not a fully finished product.

Assumption: six focused hours. Example schedule: 09:00–16:15 Pacific with 75 minutes of breaks. Move the whole schedule if needed; the order and time budgets matter more than the starting clock time. Nothing has been added to a calendar.

## Resources tomorrow

Use Meta API for the actual product call and the existing ChatGPT/Codex or Cursor development workflow to build it. Check available Meta credits and current pricing, then limit the first smoke-test session to $5 within the Days 1–3 $25 envelope. Keep Baseten as a fallback only if Meta access is confirmed blocked. No Gemini review or new service setup is required tomorrow. See [resources and budget](resources-and-budget.md).

## 09:00–09:45 — Establish the application boundary

1. Run `python3 tools/validate_pack.py` from the Missing Monday folder. Record its result.
2. Inspect the existing parent repository and ignore rules before creating files. Do not initialize a nested repository by accident or modify TacitOS.
3. Create a minimal Python application layout: `app/`, `app/static/`, `tests/` and a dependency file with tested versions.
4. Prepare the local environment and start command. Use FastAPI, SQLite and plain HTML/CSS/JavaScript unless an installed dependency or existing reusable component gives a clear benefit.
5. Make `GET /health` respond and serve an initial page from the designated static folder only. Do not expose the project directory.
6. Define where the private key will be read from. Reuse an authorized private configuration path without displaying or copying its contents into the repository. Document missing-key behavior.

Output: a runnable skeleton and known configuration boundary.

Check: the app starts and stops cleanly; `/health` responds; expert-only fixture paths are not served. A short inspection of reusable TacitOS client code is allowed, but do not import its old workflow or spend the morning refactoring it.

## 09:45–11:15 — Implement the rehearsal and independent outcome

1. Load the public `cases.json` fields into typed case objects. Explicitly select allowed response fields.
2. Keep evaluation data in a separate server-side service that the model cannot call.
3. Implement the permitted actions: accept, reject, request evidence, escalate and report permission issue.
4. Validate action type and required case/session IDs before processing.
5. Implement or adapt the prepared oracle as a clearly labelled synthetic simulator. It evaluates submitted actions; it does not generate expert guidance.
6. Create focused tests for eligible substitution, wrong revision, wrong certificate, missing certificate, standard completion and missing permissions.
7. Test a public case response and assembled model context for accidental hidden-answer fields.

Output: a deterministic rehearsal engine with meaningful tests.

Check: known cases receive the intended outcomes; a request for missing evidence is safe handling but not independent completion. A model cannot award itself success. Do not let the learner read the grading explanation before submitting a final decision.

## 11:15–11:30 — Break

## 11:30–12:15 — Persist sessions and attempts

1. Create SQLite tables for sessions, attempts and actions. Store timestamps in UTC.
2. Add session creation, current-case retrieval and action-submission endpoints.
3. Record actor type, evidence inspected, direct expert contacts and final action separately.
4. Use unique action IDs to make retries idempotent.
5. Preserve submitted actions and evaluator results. Do not overwrite old outcomes when the page reloads.
6. Implement a clearly labelled local demo reset that affects only this application's synthetic session data.

Output: one attempt survives a reload and can be reset deliberately.

Check: duplicate submission does not double-count an expert contact or final action; another session cannot accidentally retrieve the wrong attempt.

## 12:15–13:00 — Lunch

## 13:00–14:00 — Build the first usable screen

1. Display “Missing Monday” and “Synthetic rehearsal — no real orders.”
2. Show the case facts and public handbook side by side, or stacked on a small screen.
3. Add evidence inspection and action controls with a short reason field.
4. Add “I need the expert” to record the dependency and request diagnosis.
5. Add clear loading, error and saved states. Preserve the entered reason on failure.
6. Make the controls keyboard accessible and use text as well as color for outcomes.

Output: a person can complete the rehearsal interaction without using developer tools.

Check: no hidden rule or expected action is embedded in page data, HTML or browser responses. The interface never shows a fake model response while a request is pending.

## 14:00–14:15 — Break

## 14:15–15:45 — Add one genuine Meta diagnosis

1. Check the current provider request format and chosen model access before integrating. Earlier TacitOS verification is a lead, not evidence that Missing Monday works.
2. Implement a server-side adapter with a timeout, bounded retries and safe error messages. Do not log the key or raw authentication errors.
3. Construct context from the current case, public handbook, approved guidance if any, and attempt trace. There is no approved guidance on Day 1.
4. Use the gap-analyst prompt in `prompts.md` and validate the output fields and category.
5. Run a real diagnosis of the stalled substitution case.
6. Check that the result asks which supplier/part/revision/certificate conditions allow substitution rather than revealing the hidden rule as established knowledge.
7. Exercise a missing-permission control. It should identify access as the issue, rather than ask the expert to invent a purchasing policy.
8. Save a private run record with model ID, prompt version, timing, request ID if available and actual response. Record failure if the call fails.

Output: a model-generated expert question displayed alongside the case and evidence.

Check: the question refers to actual available facts and does not claim the answer is already known. Structural validation alone is not enough; inspect its meaning.

Fallback: after a short diagnosis of an access or account problem, check whether the reported Baseten Muse Spark Open offer can restore the live model path within the existing block. Verify its access and pricing first; label the provider and preserve the same context boundaries. If that is not straightforward, continue the UI and adapter error path. A mock may support development only if visibly labelled; it does not satisfy the live-model gate. Record the exact blocker for the next day. Do not silently switch to canned answers.

## 15:45–16:15 — Verify and preserve the day's result

1. Run the focused tests and fixture validation.
2. Restart the app and repeat the first case from a clean session.
3. Capture a short local screen recording or screenshots if convenient, without keys or unrelated tabs. This is development evidence, not the final demo.
4. Write a short build-status note: what works, what remains, actual test results, actual Meta results and the next task.
5. Inspect changed files and ignored files. If local commits are appropriate, include only this project's changes, never unrelated staged work. Do not push or publish.
6. Prepare Day 2's first task: a text answer box linked to the recorded gap.

Output: reproducible startup instructions, actual verification evidence and a precise handoff to Day 2.

## End-of-day acceptance checklist

- [ ] Missing Monday starts locally using a documented command.
- [ ] The successor sees only public case information and handbook material.
- [ ] Actions and expert-help requests are persisted once.
- [ ] The simulator handles the selected positive, negative and control cases correctly.
- [ ] A real Meta call produces a grounded question, or the live-model gate is explicitly recorded as blocked.
- [ ] No API key, expert rulebook or expected-outcome data is exposed to the browser or model context.
- [ ] Errors are visible, and no preset response is presented as live AI output.
- [ ] The build-status note separates implemented functionality from plans.

The day is fully successful only if the live-model gate passes. A partial day can still deliver the runnable simulator and a documented integration blocker; report that honestly.

## What Codex can do without further decisions

Implement the skeleton, simulator, storage, minimal interface and adapter; write and run focused tests; inspect public API documentation; validate context boundaries; prepare a local status note. These steps do not require a real expert or production data.

## Your useful contribution tomorrow

Spend about 15 minutes trying the screen and answering: “Is it clear why the successor got stuck, and why this question is being asked?” This can be included during the final verification block or done later. If model access requires a personal account action, complete that when prompted. No other preference decision is required before the synthetic build starts.

## Do not spend tomorrow on

Logo design, animation, voice recording, model committees, open-weight hosting, real integrations, public deployment, new product concepts or all three scenario families. One functioning question grounded in an actual failed task is the day's proof.
