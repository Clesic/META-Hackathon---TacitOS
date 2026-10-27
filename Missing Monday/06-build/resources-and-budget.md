# Resources and budget

Updated October 26, 2026 from the user's stated resources. These are reported entitlements, not verified current balances. No credit has been spent, account connected or deployment created by this planning update.

## Decision on October 27

Product model calls use the hackathon Baseten model `meta-models/muse-spark-open-1026` and the reported $100 credit. The public model id does not accept this key. Cursor remains the editor. ChatGPT is not an application runtime. Meta stays available only when `MODEL_PROVIDER=meta`. The first diagnosis session stays inside a $5 local cap.

## Use now: Meta API — $150 credit

Primary runtime for gap diagnosis, focused expert questions, guidance extraction and successor assistance. Keep one model and one provider in the first implementation. Verify the exact model, account mode, current pricing and remaining credits before live work. Record provider, model, usage and estimated cost for every run; reconcile against the provider's billing view.

Suggested planning envelopes, not expected costs or permission to exhaust credits:

- Days 1–3: up to $25 for connectivity, extraction and the first full loop.
- Days 4–5: up to $20 for robustness and evaluation development.
- Day 6: up to $35 for frozen comparisons and justified reruns.
- Days 7–8: up to $20 for recording and final checks.
- Keep $50 unallocated for unexpected problems or unused.

These sum to $150 of reported credit. Reduce them if the actual available balance is lower. Do not spend simply to use a credit allowance. No additional purchases or paid overage are planned. Before a batch, estimate its upper cost using current rates, token caps and bounded retries. Stop if the available-credit budget is uncertain or insufficient.

## Keep available: Baseten — $100 credit

The user reports a hackathon offer for Muse Spark Open with up to 2 million tokens per minute. Treat the throughput as an advertised upper limit, not a performance guarantee, budget or free-token allocation. Confirm entitlement, expiry, endpoint, model identifier, billing basis and rate limits before use.

Useful triggers:

1. A confirmed Meta API availability/access problem blocks the core and Baseten access works.
2. After the core is stable, a small portability experiment answers a concrete question about running the same workflow on an open-weight Meta model.

Otherwise leave this credit unused. No committee, self-hosted GPU deployment or extra infrastructure is needed. Hosted open weights do not establish sovereign operation.

For a discretionary comparison, cap initial spending at $10 and integration effort at 45 minutes on Day 5; skip if it risks the core schedule. The remaining $90 stays in reserve. An essential fallback needs a revised explicit budget based on real provider pricing and the remaining balance, not an assumption that the primary plan fits unchanged.

Use an explicit provider setting and record the selected provider/model. Do not silently switch providers during a benchmark or demo. Run all comparison conditions on the same model; any Baseten comparison is a separate experiment. The existing small model-adapter boundary is sufficient; do not build a general multi-provider framework.

## Use selectively: ChatGPT Plus

Use the existing chat/Codex workflow for planning, implementation help, debugging, test design and submission editing within the actual account allowance. No additional OpenAI API integration is needed for Missing Monday. OpenAI documents subscription usage and API pricing separately; do not count Plus as an API cash budget. Check actual account limits when needed.

Source checked October 26: [official OpenAI pricing documentation](https://learn.chatgpt.com/docs/pricing).

## Use selectively: Cursor Plus

Record the subscription name as supplied by the user; do not infer a specific tier, quota or API entitlement. Use the existing editor for code navigation, local debugging and focused implementation work if it is already convenient. Choose one active editing workflow at a time; avoid competing edits from Cursor and Codex. No separate setup project or upgrade is necessary.

## Optional: Gemini Plus

Record the subscription name as supplied; exact capabilities and limits have not been verified. A useful role is a manual second opinion on development scenarios, unclear UX copy or the final pitch. This is optional, not a daily dependency or an app integration. Use synthetic material and development cases only. Another AI's agreement is not independent evidence that the product works; retain the deterministic oracle and real human review.

## Day-by-day use

- Day 1: Meta live diagnosis; existing ChatGPT/Codex or Cursor workflow for building. Record remaining credits and cap the first smoke-test session at $5, within the $25 Days 1–3 envelope. No Baseten setup unless Meta is blocked.
- Days 2–3: Meta extraction and approved guidance. Existing development subscription for implementation and debugging.
- Day 4: optional brief Gemini review of usability or development-case blind spots; skip if it creates extra work.
- Day 5: budget the final evaluation. Optional Baseten trial only if a useful trigger is met; do not expand the core scope.
- Day 6: frozen evaluation using a single chosen provider/model across conditions. Log costs and actual failures.
- Day 7: use the existing writing assistant for concise narration and submission copy. Optional Gemini critique of clarity; no unverified performance claims.
- Day 8: final checks and accurate provider attribution. No new subscriptions, model integrations or hosting experiments.

## Avoid

Adding resources just because they are available; buying new subscriptions; treating chat subscriptions as backend API credits; chasing rate-limit capacity the demo does not need; mixing models across comparison conditions; presenting hosted Baseten inference as private company infrastructure; inferring account access from an offer email alone.
