# Submission copy

## Name

Missing Monday

## One sentence

Missing Monday rehearses an experienced employee's absence, captures the missing condition in the expert's words, and checks whether someone else can use that card on a new order.

## Problem

A purchasing handbook says to follow the approved substitution procedure. It does not contain the procedure. The team discovers that only when the experienced buyer is away.

## What the demo shows

One synthetic company, Alder Works. All orders are fictional.

1. Order S01 offers part P-100B instead of P-100. Baseten, using `meta-models/muse-spark-open-1026`, calls this a knowledge gap and asks whether an approved substitution procedure covers offering P-100B for ordered P-100. The hidden rule is not in that question.
2. The expert states the condition. Baseten drafts a card that must quote that answer. The expert approves the exact wording. The model cannot approve its own card.
3. Fresh order S02 has revision R2 and certificate C-B. The model suggests accept from the approved card. The order is completed without calling the expert again.
4. Boundary order S05 has certificate C-A. The model suggests reject because that certificate is outside the card. The order is not accepted.

The browser recording of this sequence is `05-demo/missing-monday-demo.mp4` (2:53). That recording spent $0.02678. An earlier scripted run of the same sequence is in `06-build/day2-results.json` and spent $0.02572. Both are one synthetic family, not a measure of a real team's readiness.

## Model

Product calls use Baseten model `meta-models/muse-spark-open-1026`. The key is the hackathon key and does not work with the public model id. Diagnosis, card drafting, and the next-step suggestion are separate calls. Each failed or empty model response leaves the attempt unchanged. Local spend for a database stops at $5.

## Differentiation

The loop connects a stalled attempt, a quoted expert card, and an independent check on a fresh order, including an order the card excludes. Interviews and absence exercises already exist. This demo does not claim to have invented knowledge transfer.

## Limitations

The cases are synthetic and cover one purchasing workflow. Passing them does not certify a role or prove a buyer will pay. An earlier suggestion on the excluded order asked for the expert again instead of rejecting. The suggestion instruction now says an order outside the card is a reject, and the recorded demo's suggestion rejected certificate C-A. A field study has not been run. The demo video has no spoken narration.
