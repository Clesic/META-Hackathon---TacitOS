# Eight-day execution plan

October 27–November 3, 2026. Prepared October 26. All clock times use America/Los_Angeles; the local clock change on November 1 does not change the daily work blocks.

## Target

By November 3, have a working, reproducible Missing Monday demo, measured results, a public-ready repository, a three-minute video and an accurate submission package. Aim to submit that day after the user confirms publication and submission. Keep November 4 as buffer; the previously checked official deadline is 18:00 Pacific. Recheck the official portal before submitting.

Assumption: one builder and six focused hours per day, about 48 hours total. Breaks are additional. This is a scope-controlled plan, not a promise that every feature will fit. As of October 27, Day 1 diagnosis and the Day 2 capture-to-transfer gate have both run on Baseten. See [build status](build-status.md) and [day2-results.json](day2-results.json).

The essential story is fixed: a successor gets stuck, the expert supplies the missing condition, the system creates approved guidance, and a fresh case demonstrates transfer. A boundary case must also show that the guidance does not permit an incorrect action.

## Available resources

Follow the [resource and budget plan](resources-and-budget.md). The user reports $150 Meta API credit, $100 Baseten credit for Muse Spark Open, and ChatGPT Plus, Cursor Plus and Gemini Plus subscriptions. Use Meta as the primary runtime and existing development subscriptions for building. Baseten is conditional fallback or a small separate portability test; Gemini is optional review. No additional purchase is planned. Budget envelopes are planning limits, not spending targets.

## Day 1 — Tuesday, October 27: make the first task real

Budget: setup 45 minutes; simulator 90; storage 45; interface 60; Meta diagnosis 90; verification 30.

1. Validate the existing pack and create an isolated application structure inside Missing Monday. Keep credentials and logs private.
2. Implement the purchasing-case loader and outcome evaluator. Keep expert rules and expected answers server-side and out of learner context.
3. Implement a session, attempt actions and persisted outcomes with SQLite.
4. Build one usable task screen with evidence, permitted actions and a visible synthetic-data label.
5. Check the actual Meta credit balance and current rates; cap the first smoke-test session at $5. Connect one real Meta call that diagnoses a blockage and asks a focused expert question. Show explicit failures rather than preset output.
6. Run the first substitution case and relevant controls; save a short status note with actual results.

Deliverable: a local app where a successor can inspect a case, get stuck, and receive a useful model-generated question for the expert.

Gate: the model asks for the missing rule without knowing the hidden answer. The evaluator correctly handles positive, negative, missing-evidence and permission-control inputs. No hidden rules appear in learner responses.

If behind: use a plain HTML interface. Preserve the real API check. Full extraction and approval belong to Day 2.

Detailed blocks: [Tomorrow's plan](tomorrow-october-27.md).

## Day 2 — Wednesday, October 28: turn the expert answer into approved guidance

Budget: answer capture 60 minutes; extraction 90; review/versioning 90; end-to-end integration 60; verification 60.

1. Add the expert view with the failed attempt and focused question.
2. Accept a text answer, including “I don't know” and a correction to the scenario's premise.
3. Extract action, conditions, exceptions, required evidence and exact source quotes through a real model call.
4. Add approve, edit and reject. Approve an exact content version; edits create a draft.
5. Store the original answer, model output and review separately.
6. Verify invented citations, changed conditions and rejected cards cannot become approved guidance automatically.

Deliverable: a real answer becomes a reviewable, source-linked card that the expert can approve.

Gate: approving and rejecting materially change what the successor can retrieve. No model can approve its own card.

If behind: omit voice, rich text and multiple-card extraction. One careful card is enough.

## Day 3 — Thursday, October 29: complete the first handover loop

Budget: approved retrieval 75 minutes; fresh retest 90; report 60; boundary cases 75; buffer 60.

1. Retrieve only current approved guidance that applies to the case.
2. Start a fresh case using a frozen guidance snapshot and no direct expert contact.
3. Record the actual successor action and evaluate it independently.
4. Add a boundary case with an ineligible revision and a case with missing evidence.
5. Show task completion, incorrect actions, expert contacts and unresolved work separately.
6. Run the entire sequence from a reset database without manually altering results.

Deliverable: one working capture-to-transfer demonstration, including the negative boundary.

Gate: a fresh eligible case passes and an ineligible case is not wrongly accepted. A safe escalation is not counted as independent completion.

If behind: stop all additional scope. Days 4 and 5 become stabilization days until this gate passes.

## Day 4 — Friday, October 30: make the loop reliable and useful to a person

Budget: controls and failures 90 minutes; version lifecycle 60; usability 90; human walkthrough 60; fixes 60.

1. Add missing-permission and missing-document controls. Classify them correctly rather than calling every blockage tacit knowledge.
2. Verify timeout recovery, duplicate submissions, reset and session separation.
3. Add revocation and conflicting-guidance handling; preserve historical snapshots.
4. Improve screen hierarchy, keyboard access, loading feedback and readable evidence.
5. Have the user or another willing person try the workflow without developer narration, if available. Otherwise run a labelled developer walkthrough.
6. Record confusion and fix the issues that prevent completing the task.

Deliverable: a repeatable core flow with clear failure states.

Gate: no secret context leakage, approval bypass or false success state. Reloading does not lose completed review work.

Human dependency: the user can provide feedback or a willing tester. Do not block engineering if unavailable; do not call a developer walkthrough an independent usability study.

## Day 5 — Saturday, October 31: prepare a fair evaluation

Budget: secondary families 90 minutes; benchmark preparation 90; comparison runner 120; review 60.

1. Add duplicate-order and split-delivery families only if the core is stable. Otherwise keep one family and disclose the narrower scope.
2. Separate development cases from final test cases. Any case used to tune the system is development data.
3. Prepare fresh positive, negative and missing-evidence variants; validate them without leaking expected outcomes into model context.
4. Freeze the final case set, expert-answer corpus, guidance versions, prompt versions and model configuration; record file hashes.
5. Implement documents-only, documents-plus-raw-answers and documents-plus-approved-guidance conditions with equal tool access and budgets.
6. Test the runner on development cases only. Label simulated successor results clearly. Estimate the final evaluation cost before launching it.
7. Only if the core is stable and portability is useful, allow a separate Baseten trial capped at 45 minutes and $10. Otherwise skip it; preserve one provider/model across the primary comparison.

Deliverable: a reproducible evaluation runner and a frozen test package.

Gate: baseline C has the same underlying expert information as D. A model never receives the oracle. Unsuccessful runs remain visible.

Optional: an equal-expert-time interview comparison requires actual capture sessions; do not invent one from the scripted fixture.

## Day 6 — Sunday, November 1: measure and freeze features

Budget: benchmark execution 90 minutes; grading 90; critical fixes 60; results write-up 60; demo rehearsal 60.

1. Execute the frozen comparisons within the $35 Day 6 Meta planning envelope, retaining provider, model, request IDs, usage, estimated cost, elapsed time and failures. Reconcile actual costs and stop before paid overage.
2. Check action correctness independently and inspect whether cited evidence supports the recommendation.
3. Report numerator and denominator by condition and case family, along with expert effort where actually measured.
4. Explain where approved guidance helps, fails or performs no better than raw answers.
5. If a critical defect changes behavior, version the fix and explain the rerun; use fresh final cases if previous outcomes informed tuning.
6. Freeze features and rehearse the complete video sequence.

Deliverable: an honest results file and a stable demo build.

Gate: no fabricated expert-time measurement, no “percentage of expertise captured,” and no global readiness claim. If the comparison does not show improvement, narrow the claim and show the actual loop.

Cut rule: do not begin voice, model hosting, integrations or cosmetic extra screens after this point.

## Day 7 — Monday, November 2: record and package

Budget: clean-start check 60 minutes; recording 90; editing 90; documentation 60; final review 60.

1. Test startup from a clean environment using the documented instructions.
2. Record the real end-to-end flow, expert approval, a fresh case and a negative case.
3. Cut to about 2:50–2:55. Label synthetic actors, replay and shortened waits.
4. Present measured results only. A labelled recording of a real successful run is acceptable as a fallback; fabricated model output is not.
5. Update the README, architecture status and submission draft to match what was built.
6. Inspect the proposed public files for secrets, private logs and unrelated project content.

Deliverable: a watchable video, reproducible source package and accurate project description.

Human dependency: the user chooses narration or records it. A silent rough cut with captions can be prepared first. A real practitioner pilot is optional evidence, not a story to manufacture.

## Day 8 — Tuesday, November 3: verify and submit

Budget: regression/smoke check 60 minutes; official requirements 45; package review 75; final video review 60; publication/submission and buffer 120.

1. Verify the exact build used in the video and rerun the focused regression checks.
2. Check current official submission fields, repository access requirements and video limits.
3. Make final copy state actual model use, measured outcomes, limitations and provenance.
4. Prepare the exact repository contents and hosting choices for the user's review.
5. Obtain any necessary publication/submission authorization, then publish and submit. A planning request alone does not authorize external publication.
6. Verify required links from a logged-out view and save the submission receipt.

Deliverable: submitted entry if access and authorization are available; otherwise a complete, reviewable submission package with the exact remaining action identified.

November 4 is only for final access issues or submission recovery. Do not depend on the final hour.

## Daily working rhythm

Start with yesterday's gate and choose one observable outcome. Work in focused blocks, then demonstrate that outcome from a known state. End by recording completed behavior, commands/checks run, failures, actual model use and the next action. Do not equate code written with a verified feature.

Codex can implement, test, prepare fixtures, document results and assemble submission materials. The user is needed for personal account actions, genuine practitioner participation, final presentation preferences and any external publication/submission approval. No outreach or calendar events are scheduled by this plan.

## Scope priorities

Protect the real gap-diagnosis call, evidence-linked expert answer, explicit approval, fresh retest and independent outcome. Cut optional modalities first, extra families second and decorative reporting third. If six hours daily is unavailable, reduce breadth before weakening the proof.
