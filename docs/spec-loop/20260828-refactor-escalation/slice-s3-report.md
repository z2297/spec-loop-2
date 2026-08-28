# Slice s3 — ESCALATED

- **Wave:** 2
- **Branch:** spec-loop/20260828-refactor-escalation/s3
- **Commits:** b5e39c9da968dfab632d7ffcf50e0ca88b4bea7b → 64bb2d4c1e26625aa62a5c55537b0ea765c9e06b
- **Risk tier:** 3
- **Tasks completed:** 7
- **Quality gate:** FAIL — Quality gate exited 1 with JSON report. Five violations: nesting_depth exceeded in two test functions (test_refactor_radius_summary: 7 vs threshold 3, test_a_refactor_radius_event_renders_a_log_line:…
- **Iron Council:** ENDORSE_WITH_CONCERNS (13 concerns) — scope: clean
- **Review:** 2 confirmed, 3 refuted, 0 evidence-failed, 1 fix round
- **Agents used:** 18

## Residual findings

- P2: When ctx.refactor_radius is present but BOTH maxima are unusable (null, a string, or absent from a hand-built block), refactorLimits() nulls them, radiusBreaches() can never fire, and every plan lands on WITHIN with the reason 'every declared number is at or under its ceiling' — a claim no comp…
- P2: `answered` is computed from answer-KEY presence, while the same answer's content reaches the planner through answerFor() -> latestAnswer(), which requires a TRUTHY value. An answers entry whose value is empty/null ("s1:refactor-scope": "") therefore disarms the halt for that slice permanently A…
- P3: `suppressed_by_answer: true` is attached on the basis of `answered` alone, independent of the verdict, so the ordinary success path after a human answers — human says 'narrow it', planner narrows, verdict is WITHIN — emits an event that claims a suppression that never occurred. run-state-v2.md …
- P3: Confirming the implementer's explicit question: radiusPhrase's unguarded `v.thresholds.*` dereference cannot throw today. refactorAsk is reached only from the EXCEEDED return, and refactorRadiusStatus returns NOT_CONFIGURED (thresholds null) before EXCEEDED is reachable, so thresholds is always…
- P3: The stated reason for putting `summary` first is factually wrong about run_state.py. _summarize() iterates SUMMARY_TEXT_KEYS in ITS OWN priority order ('summary' first) and returns the first payload key that is present; the payload's own key order is never consulted. The corresponding mjs asser…
- P2: The PLAN_RESULT schema comment claims the planner's `basis` field is 'carried for a human reading the escalation and never parsed,' but no code path actually threads `basis` anywhere: `radiusNumbers()` normalises `plan.refactor_radius` and drops `basis` entirely, so it never reaches `verdict.me…
- P2: `radiusEvent()`'s `suppressed_by_answer` flag is set whenever an answer key exists for the slice's `refactor-scope` trigger (`answerKeysFor(slice.id, 'refactor-scope').length > 0`), independent of the current verdict's `state`. So a slice that was previously answered (e.g. the human chose 'narr…

## Escalations

- **OPEN** `s3:quality-gate-block` — verification failed

_Rendered from slice-s3-status.json; that sidecar is authoritative._
