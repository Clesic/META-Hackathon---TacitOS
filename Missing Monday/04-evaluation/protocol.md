# Evaluation: does the handover actually improve?

## Primary question

With a fixed budget of expert time, does Missing Monday help a successor correctly complete fresh tasks with fewer direct expert interventions than simpler ways of capturing the same knowledge?

## Comparisons

A. Public documents only.
B. Public documents plus a conventional expert interview.
C. Public documents plus the same raw expert answers collected by Missing Monday.
D. Public documents plus Missing Monday's approved, conditional guidance.

B versus D tests the end-to-end capture strategy under equal expert time. C versus D isolates the representation and review effect with the same information. A establishes the starting limitation; winning against A alone is not sufficient evidence of differentiation.

Use the same answering model, tool permissions and maximum action budget for automated comparisons. Record configuration differences. For human comparisons, use fresh cases and counterbalanced case sets or separate participants to reduce practice effects. One person trying the identical case twice cannot establish transfer.

## Measurements

- Independent completion: correct task completion without direct expert contact, divided by eligible test tasks.
- Incorrect-action rate: incorrect submitted actions divided by all submitted decisions; also give task-level counts.
- Safe-handling rate: correct completions plus appropriate requests/escalations divided by all test tasks.
- Expert effort: actual minutes and intervention count, including reviewing and correcting cards.
- Time to task resolution; retain timeouts and failures in the report.
- Evidence support: guidance claims actually supported by cited material, not just existing citation IDs.
- Boundary performance: correct handling of negative cases and missing information.

Report numerator and denominator by condition and case family. Keep unanswerable and permission-control cases separate from independently completable tasks. A falling contact count with more wrong actions is failure, not improvement.

## Frozen protocol

1. Prepare and version training cases, fresh tests and hidden expected outcomes.
2. Hash the fixture files before benchmark runs and record hashes in results.
3. Collect expert answers without exposing held-out cases or expected outcomes.
4. Freeze guidance and raw-answer corpora before final testing.
5. Run conditions on equivalent fresh cases; record model, prompts, settings and available evidence.
6. Grade against the local oracle, with human review of explanations and citations.
7. Publish every attempted run or a stated, prespecified exclusion rule. Never select only the winning take.

Repeatedly watching held-out failures and revising prompts converts those cases into development data. Create new held-out cases for the final comparison. Synthetic family rules are intentionally simple; results do not establish generalization to real organizations.

## Dependency claims

A dependency can be marked “transfer demonstrated on tested cases” only after approved guidance and a fresh correct attempt with no direct expert contact. Include boundary coverage and unresolved conditions. Do not report a percentage of total expertise captured, a predicted retirement risk or organization-wide readiness.

## Real pilot, later

Use a practitioner to validate realism and provide knowledge absent from the initial materials. Use a successor to perform fresh cases. Secure the appropriate participation and data arrangements. Report a single pilot as a case study, not a statistically established business effect.

## Predeclared failure signals

Unsupported guidance, invented conditions, leakage of oracle answers, using draft guidance, increased incorrect actions, or gains explained entirely by access to extra raw information weaken or invalidate the claimed benefit. Log them explicitly. No results have yet been collected for Missing Monday.
