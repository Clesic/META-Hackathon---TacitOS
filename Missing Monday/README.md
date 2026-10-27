# Missing Monday

**Could your team get through Monday without its most experienced employee?**

Missing Monday rehearses that absence, finds the knowledge the team is missing, asks the expert focused questions, and checks whether someone else can now do the work.

Created October 26, 2026. Status updated October 27: a stalled attempt can be diagnosed by Meta, which asks one focused question and classifies a knowledge gap, missing evidence, or a permission problem. Typed expert approval still carries that card to a later case. Diagnosis spend is capped at $5. See [startup instructions](RUNNING.md). No real expert study or product efficacy results exist.

## Start here

1. Read [the project description](01-product/project-description.md).
2. Read [the MVP and acceptance criteria](01-product/mvp.md).
3. Follow [the eight-day execution plan](06-build/eight-day-plan.md), starting with [tomorrow’s detailed schedule](06-build/tomorrow-october-27.md).
4. Use [the synthetic company](03-scenarios/company-and-handbook.md), [fixtures](03-scenarios/cases.json), and [expert-only material](03-scenarios/expert-only/rulebook.json).
5. Read [the evaluation protocol](04-evaluation/protocol.md) before wiring prompts or displaying scores.
6. Run `python3 tools/validate_pack.py` from this folder to validate the prepared fixtures and local document links. This uses the Python standard library and makes no network calls.

## Working defaults

English product and documentation. One builder, one synthetic purchasing workflow, one expert role, one successor role. Text first; optional voice after the loop works. Meta performs gap diagnosis, focused questioning and evidence-based guidance. A deterministic simulator owns outcomes. These are reversible planning decisions, not user-confirmed facts about team size or available time.

The application starts as a safe local rehearsal. It never places real orders. It evaluates task coverage, not employee worth. A later real pilot needs an actual practitioner and fresh successor attempts.

## Contents

- [Concept and positioning](01-product/project-description.md)
- [MVP](01-product/mvp.md)
- [Business hypotheses and discovery](01-product/business-and-discovery.md)
- [Architecture](02-design/architecture.md)
- [Data contracts and transitions](02-design/data-contracts.md)
- [Experience and screen copy](02-design/experience.md)
- [Synthetic company and handbook](03-scenarios/company-and-handbook.md)
- [Scenario authoring rules](03-scenarios/README.md)
- [Evaluation protocol](04-evaluation/protocol.md)
- [Blank results record](04-evaluation/results-template.json)
- [Three-minute demo](05-demo/demo-script.md)
- [Submission draft](05-demo/submission-draft.md)
- [Resources and budget](06-build/resources-and-budget.md)
- [Eight-day execution plan: October 27–November 3](06-build/eight-day-plan.md)
- [Tomorrow: October 27, detailed schedule](06-build/tomorrow-october-27.md)
- [Original build roadmap](06-build/roadmap.md)
- [Implementation backlog](06-build/backlog.md)
- [Prompt specifications](06-build/prompts.md)
- [Security and data handling](07-governance/data-handling.md)
- [Research and source register](07-governance/research.md)
- [Decisions and outstanding dependencies](07-governance/decisions.md)
- [Hackathon checklist](07-governance/hackathon-checklist.md)

## Relationship to earlier work

This is a new project folder for the concept selected by the user. TacitOS and the downloaded Tacit and Apprentice drafts remain separate. Their existing code is not presented as an implementation of Missing Monday. Reuse may be possible after inspection, with attribution to the original development history. No source files, credentials, databases, or private logs have been copied from TacitOS.
