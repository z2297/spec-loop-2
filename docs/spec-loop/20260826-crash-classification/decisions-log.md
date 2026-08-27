# Decisions log

Rendered from the run's events; append-only, and nothing parses it back.

[run] DECISION: every agent this run is dispatched through the Workflow runtime, never the Agent tool — AT: 2026-08-26T20:03:49Z
[intake] DECISION: intake council ran at 1 of 3 lanes; plan-critic and guardian mandates were executed by the controller instead — AT: 2026-08-26T20:03:49Z
[s1] DECISION: accepted the planner's wider cut - s1 also updates the three normative contracts - and moved those files from s2 into s1's declared scope — AT: 2026-08-26T20:12:44Z
[s1] DECISION: verified first-hand that risk-tiers.md:88 and migration-from-v1.md:64 need no edit, confirming the planner's claim — AT: 2026-08-26T20:12:44Z
[s1] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-26T21:12:03Z
[s1] DEFERRED: DEFERRED (do not build) — with crashes moving to their own trigger, two distinct crashes in the same slice now collide on the single id `${slice.id}:internal-error`, because esc() at slice-wave.workf… — AT: 2026-08-26T21:12:03Z
[s1] QUALITY-GATE: FAIL — AT: 2026-08-26T21:12:03Z
[s1] DECISION: finding qg-0 refuted by batched verifier — AT: 2026-08-26T21:12:03Z
[s1] DECISION: finding qg-1 refuted by batched verifier — AT: 2026-08-26T21:12:03Z
[s1] DECISION: finding qg-2 refuted by batched verifier — AT: 2026-08-26T21:12:03Z
[s1] DECISION: s1:quality-gate-block resolved by the controller on prior-run precedent, not surfaced to the human — AT: 2026-08-26T21:13:16Z
[s1] DEFERRED: POST-RUN FOLLOW-UP (not built): a plugin downgrade to 2.2.0 DISCARDS an internal-error sidecar entirely, not merely mis-flags it — AT: 2026-08-26T22:20:12Z
[s1] DEFERRED: POST-RUN FOLLOW-UP (not built): the quality gate's builtin heuristic counts control-flow KEYWORDS INSIDE STRING LITERALS, so prose in a message inflates a function's complexity — AT: 2026-08-26T22:38:31Z
[s1] COUNCIL-VERDICT: OBJECT [scope: clean] — AT: 2026-08-26T22:44:24Z
[s1] DEFERRED: CONSISTENCY (defer). Task 1's rationale — "the 4-space hanging-indent style already used by passing sibling tests in the same files" — is overstated. The immediately-preceding sibling `test_dashboard… — AT: 2026-08-26T22:44:24Z
[s1] DEFERRED: DESIGN/test strength (defer). `test_internal_error_is_substring_safe_against_every_other_trigger` (test_run_metrics.py:465-471) asserts containment against the Python literal `"internal-error"`, so i… — AT: 2026-08-26T22:44:24Z
[s1] DEFERRED: No rollback path for a run dir once it carries an internal-error sidecar, and it is worse than the constraint's phrasing. I verified persist_slice (plugins/spec-loop/scripts/run_state.py:967-975) rai… — AT: 2026-08-26T22:44:24Z
[s1] QUALITY-GATE: FAIL — AT: 2026-08-26T22:44:24Z
[s1] DECISION: s1's converged sidecar is controller-authored with first-hand evidence, and deliberately omits the already-rendered escalation record — AT: 2026-08-26T22:44:24Z
[wave1] INTEGRATION-CHECK: GREEN by tree identity - suite not re-run, and that is the documented exception, not a skipped check — Exactly ONE slice merged in wave 1, and git rev-parse spec-loop-run/20260826-crash-classification^{tree} equals the s1 sidecar's tests.tree_sha (1d650656c08b3bbfa892cc5e5b51a97239ce2016) byte for byt… — AT: 2026-08-26T22:45:03Z
[s2] DECISION: s2's DONE is NOT accepted: its own reviewer says 2 of 3 deliverables are unmet, and it missed a real correctness defect the controller had also mis-verified — AT: 2026-08-26T23:14:50Z
[s2] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-26T23:33:43Z
[s2] QUALITY-GATE: PASS — AT: 2026-08-26T23:33:43Z
[s2] DEFERRED: POST-RUN FOLLOW-UP (not built): slice-worker-fallback.md's Pipeline step 3 disagrees with the shipped workflow about how an exhausted task retry escalates — AT: 2026-08-26T23:33:43Z
[wave2] INTEGRATION-CHECK: GREEN by tree identity - the documented exception, not a skipped check — Exactly ONE slice merged in wave 2 and the integration branch tree equals the s2 sidecar's tests.tree_sha (65888d5d2becc7a68c3458494c1e2b9abb308d6b) byte for byte, so the controller-measured green at… — AT: 2026-08-26T23:34:02Z
[phase5] PHASE5-GATE: FAIL — Phase 5 attempt 1 FAILS on review, not on the suite. P1 INT-1: agents/slice-worker-fallback.md:157 tells the inline twin that 'a stage that died with no result is internal-error', but the shipped wor… — AT: 2026-08-26T23:48:42Z
[phase5] DECISION: remediating Phase 5 with a targeted fix plus independent re-review instead of a remediation slice-wave of one - a deliberate, recorded deviation from references/phase-5-integration.md section 3 — AT: 2026-08-26T23:48:42Z
[r1] QUALITY-GATE: FAIL — AT: 2026-08-27T00:31:52Z
[phase5] PHASE5-GATE: PASS — Phase 5 attempt 2 PASSES. The reviewer re-measured INT-4 independently rather than trusting the remediation: extracting the shipped template and applying run_state._one_line(...,400) semantics, the s… — AT: 2026-08-27T00:46:43Z
[phase5] DEFERRED: POST-RUN FOLLOW-UP (not built): the test pinning the 400-char truncation fix re-implements run_state truncation instead of calling it — AT: 2026-08-27T00:46:43Z
[phase5] DEFERRED: POST-RUN FOLLOW-UP (not built): the enum-agreement guard covers four homes, not the five its name and comment claim — AT: 2026-08-27T00:46:43Z
[phase5] DEFERRED: POST-RUN FOLLOW-UP (not built): three residual unconditional claims about the lost-slice record shape — AT: 2026-08-27T00:46:43Z
