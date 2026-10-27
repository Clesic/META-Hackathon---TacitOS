# Data contracts and state transitions

All entities have an ID, creation time and schema version. Use UTC in stored timestamps and the user's timezone for displayed schedules. Changes preserve the original evidence.

## Case

`case_id`, `family`, `split`, `data_class`, `title`, `facts`, `available_document_ids`, `allowed_actions`.

Splits: `discovery`, `transfer`, `boundary`, `control`. Cases do not carry expected answers into the client. Fixtures are synthetic. Role permissions determine which facts and documents are visible.

## Attempt

`attempt_id`, `session_id`, `case_id`, `actor_type`, `guidance_snapshot_ids`, `actions`, `expert_contact_count`, `started_at`, `completed_at`, `status`.

Actor type is `human_successor` or `simulated_successor`; never merge those result groups. Actions record type, timestamp, submitted arguments and tool outcome. Status is `in_progress`, `submitted`, `blocked` or `failed`. The model cannot self-assign a passing evaluation.

## Gap

`gap_id`, `attempt_id`, `category`, `missing_distinction`, `evidence_refs`, `expert_question`, `status`.

Categories: `knowledge`, `permission`, `tool_failure`, `missing_case_data`, `ambiguous_task`, `unknown`. Lifecycle: `identified` → `question_pending` → `answered` → `guidance_approved` → `retest_pending` → `transfer_demonstrated`. Failed tests return to `retest_pending` or reopen the question. Use `out_of_scope` for non-knowledge gaps needing another owner.

`transfer_demonstrated` applies only to referenced cases and versions. Avoid a global `solved` flag.

## Expert answer

`answer_id`, `gap_id`, `expert_id`, `text`, optional `transcript_segments`, `submitted_at`. Quotes must be exact substrings or exact referenced transcript segments. Preserve the original answer when a card is edited.

## Guidance version

`card_id`, `version`, `previous_version`, `claim`, `conditions`, `exceptions`, `required_evidence`, `action`, `abstain_when`, `source_answer_ids`, `source_quotes`, `entity_refs`, `status`, `review`.

Statuses: `draft`, `approved`, `rejected`, `superseded`, `revoked`. Review contains reviewer ID, timestamp and the reviewed content hash. Editing any material field creates a new draft version. Approval means the expert endorses this representation; it is not independent proof of truth. Contradictory approved cards trigger escalation and review rather than a silent winner.

## Evaluation and dependency record

`evaluation_id`, `attempt_id`, `oracle_version`, `correct_action`, `safe_handling`, `independent_completion`, `evidence_sufficient`, `notes`.

Dependency record: workflow, originating gap, severity rationale, card versions, tested case IDs, outcomes, last tested time and remaining limits. Severity is a disclosed prioritization judgment; no model-generated probability of business failure.

## Invariants

Only current approved versions enter new guidance snapshots. Historical snapshots never mutate. No pass without an independently evaluated submitted action. No inference that a zero-contact attempt was successful. No dependency removal claim from replaying its training case. Repeated delivery of the same action ID does not change counts. Deleting or revoking evidence blocks new use and flags affected results for review under the retention policy.
