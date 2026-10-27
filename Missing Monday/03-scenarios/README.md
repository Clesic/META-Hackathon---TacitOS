# Scenario fixtures and leakage boundaries

`cases.json` contains learner-visible case facts. `expert-only/rulebook.json` contains hidden rules and scripted expert answers for development. `evaluator-only/expected.json` contains expected actions. Do not send the latter two files to the successor, gap analyst, public browser or ordinary retrieval index.

The complete pack is readable to its developer. A fair evaluation still requires the runtime to enforce these context boundaries. Repository access is not an acceptable successor tool. Public release of fixtures permits reproduction but does not make a model result on them a private benchmark.

## Prepared cases

Each of three rule families has one discovery case, two positive transfer variants, two boundary variants and one missing-evidence case. Four controls cover ordinary completion, insufficient information, missing permissions and a documented escalation. This gives 22 cases, not 22 measured results.

Case order is not a label. Human-readable IDs are useful for development, but the benchmark should use opaque aliases and shuffled order so names do not reveal the family or expected action. Titles must remain neutral. Build a separate fresh benchmark before making external performance claims.

## Authoring constraints

A fresh case must change meaningful inputs, not just the order ID. Include both eligible and ineligible examples to catch overgeneralized guidance. Keep hidden rules outside model prompts. Generated cases must be checked for realistic facts and unambiguous outcomes before entering the frozen test set.

The synthetic expert can read its rulebook only after a focused question. It should answer that question, not dump unrelated rules. Scripted answers test extraction and plumbing. They do not prove the system can elicit tacit knowledge from a real person.

## Fixture validation

The included tool checks identifiers, splits, allowed actions, expected outcomes and local Markdown links. It recomputes the synthetic expected action from a separate rule implementation. Passing it establishes fixture consistency, not model accuracy, successful knowledge capture or product readiness.
