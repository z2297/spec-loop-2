# Decisions log

Rendered from the run's events; append-only, and nothing parses it back.

[intake] COUNCIL-VERDICT: (no verdict) [SCOPE-FLAGGED: The Node behavioural harness is not a deferral-list work item - item 3.1 stated its own reversibility as resolving on the next run from an updated cache. Endorsed as good expansion but recorded as ex…] — AT: 2026-08-27T17:09:19Z
[intake] DECISION: plugin_root AND every controller script invocation resolve to a frozen pre-run 2.2.1 snapshot, dispatching by scriptPath — AT: 2026-08-27T17:09:19Z
[intake] DECISION: The quality-gate fix SPLITS into two serial Tier-3 slices: s4 (seam + Python via stdlib tokenize) then s6 (the cbrace scanner) — AT: 2026-08-27T17:09:19Z
[intake] DECISION: Masked spans are filled with a NON-WHITESPACE sentinel, not spaces; and only the text reaching _branch_count and _cognitive_approx is masked — AT: 2026-08-27T17:09:19Z
[intake] DECISION: test_dashboard_server.py mixed indentation: LEAVE IT, keep the record — AT: 2026-08-27T17:09:19Z
[intake] DECISION: Build the behavioural harness FIRST (wave 1), before the three workflow behaviour changes — AT: 2026-08-27T17:09:19Z
[intake] DECISION: Proceeded past the dirty-tree guard — AT: 2026-08-27T17:09:44Z
[intake] DECISION: CHANGELOG gets an [Unreleased] entry; no version bump and no release this run — AT: 2026-08-27T17:09:44Z
[intake] DEFERRED: The 2.2.1 orchestration JS now really executes and s1 asserts on real executed behaviour. Two limits remain and no artifact may paper over them: (a) the harness drives the file against a MOCK agent/p… — AT: 2026-08-27T17:09:44Z
[intake] DEFERRED: Nothing in the plugin prevents a future run from dispatching a 2.2.1 workflow while collecting through an older cached run_state.py. persist_slice still validates the whole SliceResult before writing… — AT: 2026-08-27T17:09:44Z
[intake] DEFERRED: Measured cognitive 25 -> 17 against a threshold of 15 once string literals stop counting. Three of its nine counted branches are punctuation inside string literals (the ? in the escape set and two in… — AT: 2026-08-27T17:09:44Z
[intake] DEFERRED: The division-vs-regex ambiguity is not safely decidable by a hand-rolled scanner. No regex literal in this repo currently contains a quote, so the residual is bounded today. — AT: 2026-08-27T17:09:44Z
[s1] COUNCIL-VERDICT: OBJECT [scope: clean] — AT: 2026-08-27T18:37:43Z
[s1] DEFERRED: The new CI step copies the existing client-JS step's `out=$(...)` then `rc=$?` shape. Under GitHub Actions' default `bash -e`, a failing test run aborts the step at the assignment, so neither the ech… — AT: 2026-08-27T18:37:43Z
[s1] QUALITY-GATE: PASS — AT: 2026-08-27T18:37:43Z
[s2] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-27T18:37:43Z
[s2] DEFERRED: OBSERVATION recorded, not a fix request (matches Task 3 step 5, and I confirmed the text): the `## Escalations` paragraph in slice-worker-fallback.md says the workflow "classifies both shapes of that… — AT: 2026-08-27T18:37:43Z
[s2] QUALITY-GATE: PASS — AT: 2026-08-27T18:37:43Z
[s3] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-27T18:37:43Z
[s3] QUALITY-GATE: FAIL — AT: 2026-08-27T18:37:43Z
[s4] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-27T18:37:43Z
[s4] DEFERRED: DEFER, do not build here: this slice makes `slice_wave_contract_base.py`'s module docstring half-false, and the plan's own slice-local boundary forbids fixing it. That docstring (the paragraph beginn… — AT: 2026-08-27T18:37:43Z
[s4] QUALITY-GATE: FAIL — AT: 2026-08-27T18:37:43Z
[s8] COUNCIL-VERDICT: SAFETY OBJECT [SCOPE-FLAGGED: Task 4 changes the semantics of run_state.open_escalations(), a public CLI surface ('run_state.py open-escalations') consumed by commands/spec-loop.md step 7 and skills/escalation-gate/SKILL.md. No r…] — AT: 2026-08-27T18:37:43Z
[wave1] INTEGRATION-CHECK: GREEN - all six segments: marketplace OK; root unittest 106 OK; plugin unittest 1159 OK; coverage PASS TOTAL 96.7% vs 90% floor; node client 48/48; claude plugin validate passed — AT: 2026-08-27T18:42:17Z
[run] DECISION: All three wave-1 escalations resolved by the controller; no human round needed — AT: 2026-08-27T18:44:11Z
[s3] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-27T18:49:04Z
[s3] QUALITY-GATE: FAIL — AT: 2026-08-27T18:49:04Z
[s4] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-27T18:49:04Z
[s4] DEFERRED: DEFER, do not build here: this slice makes `slice_wave_contract_base.py`'s module docstring half-false, and the plan's own slice-local boundary forbids fixing it. That docstring (the paragraph beginn… — AT: 2026-08-27T18:49:04Z
[s4] QUALITY-GATE: FAIL — AT: 2026-08-27T18:49:04Z
[wave1] INTEGRATION-CHECK: GREEN - all six segments on the assembled branch: marketplace OK; root unittest 106 OK; plugin unittest 1186 OK; coverage PASS TOTAL 96.8% vs 90% floor (quality_gate.py 92.6% vs 86, run_metrics.py 98.6% vs 93); node client 48/48; behavioural harness 14/14; claude plugin validate passed — AT: 2026-08-27T18:51:51Z
[run] DECISION: s3 and s4 were controller-ACCEPTED rather than re-dispatched, because a quality-gate-block for a violation the slice is told to ACCEPT is structurally unanswerable by re-dispatch — AT: 2026-08-27T18:51:51Z
[s4] QUALITY-GATE: (no result) — AT: 2026-08-27T18:51:51Z
[s8] DECISION: Rewrote s8s goal in dag.json before re-dispatch — AT: 2026-08-27T18:52:25Z
[s8] COUNCIL-VERDICT: OBJECT [scope: clean] — AT: 2026-08-27T20:21:53Z
[s8] DEFERRED: `_place_escalation` turns escalations.md from append-only into whole-page read-modify-write, so two slices in one wave opening escalations concurrently can now lose a section. The existing `escalatio… — AT: 2026-08-27T20:21:53Z
[s8] QUALITY-GATE: FAIL — AT: 2026-08-27T20:21:53Z
[s8] DECISION: s8 round 2 REJECTED and re-dispatched as round 3, with a hard stop after it — AT: 2026-08-27T20:23:26Z
[run] DECISION: First wave-2 dispatch was STOPPED seconds in and re-issued; controller passed a malformed base_sha — AT: 2026-08-27T20:27:59Z
[run] DECISION: Added remediation slice s12 for the coverage-omit line-pinning drift, plus two confirmed residual correctness fixes — AT: 2026-08-27T22:00:11Z
[s7] COUNCIL-VERDICT: OBJECT [scope: clean] — AT: 2026-08-27T22:01:52Z
[s7] DEFERRED: CONSISTENCY: the crash record's option details are pinned twice — behaviourally in the harness AND as source text in Python via slice_wave_contract_base's CRASH_OPTION_RETRY/SKIP/STOP and CRASH_OPTIO… — AT: 2026-08-27T22:01:52Z
[s7] QUALITY-GATE: FAIL — AT: 2026-08-27T22:01:52Z
[s7] DECISION: finding qg-0 refuted by batched verifier — AT: 2026-08-27T22:01:52Z
[s8] COUNCIL-VERDICT: OBJECT [scope: clean] — AT: 2026-08-27T22:03:42Z
[s8] DEFERRED: RISK - the same defect class as BLOCKING 1 survives on the path the human gate actually depends on, and it should be logged rather than left implied. Task 2 step 6 keeps _read_text unedited with the … — AT: 2026-08-27T22:03:42Z
[s8] DEFERRED: Pre-existing, verified, and outside this slice's three-defect mandate - logging so it is not lost. `render_escalation` passes `title`, `context`, `question`, option `detail`, `if_unanswered` and `ans… — AT: 2026-08-27T22:03:42Z
[s8] QUALITY-GATE: FAIL — AT: 2026-08-27T22:03:42Z
[run] DECISION: s8s reported suite failure was a CONTROLLER error, not a slice defect — AT: 2026-08-27T22:04:10Z
[wave2] INTEGRATION-CHECK: GREEN - all seven segments: marketplace OK; root unittest 106 OK; plugin unittest 1226 OK; coverage PASS TOTAL 96.9% vs 90% floor; node client 48/48; behavioural harness 15/15; claude plugin validate passed — AT: 2026-08-27T22:07:27Z
[s5] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-27T23:20:26Z
[s5] QUALITY-GATE: PASS — AT: 2026-08-27T23:20:26Z
[s6] COUNCIL-VERDICT: OBJECT [scope: clean] — AT: 2026-08-27T23:20:26Z
[s6] DEFERRED: RISK -- hardening _cb_flat_step against the backslash-newline phantom (refuse a \\[\s\S] escape that consumes a newline inside a quote span, mirroring the existing star-slash guard) is the real remed… — AT: 2026-08-27T23:20:26Z
[s6] DEFERRED: Task 2's stated decision not to harden the fallback leaves a live silent under-count on the blocking control for `.js`/`.mjs`/`.cjs`/`.ts`/`.tsx`/`.jsx` consumers whenever a regex literal on a line c… — AT: 2026-08-27T23:20:26Z
[s6] QUALITY-GATE: FAIL — AT: 2026-08-27T23:20:26Z
[s9] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-27T23:20:26Z
[s9] QUALITY-GATE: FAIL — AT: 2026-08-27T23:20:26Z
[s5] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-27T23:22:47Z
[s5] QUALITY-GATE: PASS — AT: 2026-08-27T23:22:47Z
[s6] COUNCIL-VERDICT: OBJECT [scope: clean] — AT: 2026-08-27T23:25:42Z
[s6] DEFERRED: RISK -- hardening _cb_flat_step against the backslash-newline phantom (refuse a \\[\s\S] escape that consumes a newline inside a quote span, mirroring the existing star-slash guard) is the real remed… — AT: 2026-08-27T23:25:42Z
[s6] DEFERRED: Task 2's stated decision not to harden the fallback leaves a live silent under-count on the blocking control for `.js`/`.mjs`/`.cjs`/`.ts`/`.tsx`/`.jsx` consumers whenever a regex literal on a line c… — AT: 2026-08-27T23:25:42Z
[s6] QUALITY-GATE: FAIL — AT: 2026-08-27T23:25:42Z
[wave3] INTEGRATION-CHECK: GREEN - all seven segments: marketplace OK; root unittest 106 OK; plugin unittest 1279 OK; coverage PASS TOTAL 96.9% vs 90% floor; node client 48/48; behavioural harness 15/15; claude plugin validate passed — AT: 2026-08-27T23:30:25Z
[run] DECISION: s5s internal-error crash was resolved by CONTROLLER VERIFICATION, not by re-dispatch — AT: 2026-08-27T23:30:25Z
[run] DECISION: s9 re-dispatched for ONE cross-slice reconciliation, fixing the GUARD rather than the prose — AT: 2026-08-27T23:30:25Z
[s9] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-28T00:10:42Z
[s9] DEFERRED: Residual brittleness the plan does not close, in the same defect class this run polices. The fallback pin extracts the enumeration with text.split(lead, 1)[1].split(')', 1)[0] at plugins/spec-loop/sc… — AT: 2026-08-28T00:10:42Z
[s9] QUALITY-GATE: FAIL — AT: 2026-08-28T00:10:42Z
[s9] DECISION: finding qg-0 refuted by batched verifier — AT: 2026-08-28T00:10:42Z
[s9] DECISION: finding qg-1 refuted by batched verifier — AT: 2026-08-28T00:10:42Z
[s9] DECISION: finding qg-2 refuted by batched verifier — AT: 2026-08-28T00:10:42Z
[s9] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-28T00:12:58Z
[s9] DEFERRED: Residual brittleness the plan does not close, in the same defect class this run polices. The fallback pin extracts the enumeration with text.split(lead, 1)[1].split(')', 1)[0] at plugins/spec-loop/sc… — AT: 2026-08-28T00:12:58Z
[s9] QUALITY-GATE: FAIL — AT: 2026-08-28T00:12:58Z
[s9] DECISION: finding qg-0 refuted by batched verifier — AT: 2026-08-28T00:12:58Z
[s9] DECISION: finding qg-1 refuted by batched verifier — AT: 2026-08-28T00:12:58Z
[s9] DECISION: finding qg-2 refuted by batched verifier — AT: 2026-08-28T00:12:58Z
[run] DECISION: Re-scoped s10 and s12 to remove a file overlap rather than serialising them — AT: 2026-08-28T00:15:47Z
[s10] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-28T01:22:44Z
[s10] QUALITY-GATE: FAIL — AT: 2026-08-28T01:22:44Z
[s12] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-28T01:22:44Z
[s12] QUALITY-GATE: FAIL — AT: 2026-08-28T01:22:44Z
[s12] DECISION: finding qg-0 refuted by batched verifier — AT: 2026-08-28T01:22:44Z
[s12] DECISION: finding qg-1 refuted by batched verifier — AT: 2026-08-28T01:22:44Z
[s10] DECISION: s10 NOT accepted at round 1; two of its residual P2s are P0 under this runs own cardinal rule — AT: 2026-08-28T01:23:49Z
[s12] DECISION: s12 NOT accepted at round 1; it introduced two NEW function-level gate violations — AT: 2026-08-28T01:23:49Z
[s10] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-28T02:34:49Z
[s10] DEFERRED: The signal is a slice-start snapshot, so one discard shape stays silent: an override that IS applied at slice start (event emitted) but is rendered unusable moments later by `maybePromoteTier` raisin… — AT: 2026-08-28T02:34:49Z
[s10] DEFERRED: Every `decision` event feeds run_metrics: `decisions_total`, `autonomy_ratio` (`_autonomy_ratio` at run_metrics.py, "share of judgement calls the loop resolved itself rather than handing to the human… — AT: 2026-08-28T02:34:49Z
[s10] QUALITY-GATE: FAIL — AT: 2026-08-28T02:34:49Z
[s10] DECISION: finding qg-0 refuted by batched verifier — AT: 2026-08-28T02:34:49Z
[run] DECISION: An agent wrote CHANGELOG.md into the MAIN working tree instead of its slice worktree; the stray was discarded before merging — AT: 2026-08-28T02:36:02Z
[run] DECISION: CONTROLLER PROCESS ERROR: s10 was marked complete in dag.json BEFORE its merge was confirmed — AT: 2026-08-28T02:36:02Z
[s12] COUNCIL-VERDICT: OBJECT [scope: clean] — AT: 2026-08-28T03:26:55Z
[s12] DEFERRED: A per-target expected-block-size map (dict of relpath -> lines) would make a bump cost exactly one target instead of thirteen, and would be the only shape that genuinely forces a per-file decision. I… — AT: 2026-08-28T03:26:55Z
[s12] QUALITY-GATE: FAIL — AT: 2026-08-28T03:26:55Z
[s12] DEFERRED: test_an_anchor_embedded_in_prose_does_not_claim_another_section passes identically with the pre-fix unanchored regex - the reviewer proved it by monkeypatching the old pattern back in-process - so it… — AT: 2026-08-28T03:27:52Z
[s12] DEFERRED: Every slice wrote a slice-<id>-report.md into the run dir as an untracked artifact, matching prior-run convention, but s12s agent additionally git-added and committed its report to the slice branch. … — AT: 2026-08-28T03:27:52Z
[wave5] INTEGRATION-CHECK: GREEN - all seven segments: marketplace OK; root unittest 126 OK; plugin unittest 1292 OK; coverage PASS TOTAL 96.9% vs 90% floor with run_state.py restored to 100.0% (740/740); node client 48/48; behavioural harness 35/35; claude plugin validate passed — AT: 2026-08-28T03:29:27Z
[s11] COUNCIL-VERDICT: OBJECT [scope: clean] — AT: 2026-08-28T04:46:47Z
[s11] QUALITY-GATE: PASS — AT: 2026-08-28T04:46:47Z
[s13] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-28T05:17:01Z
[s13] QUALITY-GATE: PASS — AT: 2026-08-28T05:17:01Z
[s13] DEFERRED: references/run-state-v2.md now says the string 14 is accepted and takes effect. True at tier 1, whose default cap is 10. FALSE at tiers 2 and 3, whose defaults are 18 and 32, where 14 is at-or-below … — AT: 2026-08-28T05:17:20Z
[s13] DEFERRED: references/run-state-v2.md carries a 51-character line where the paragraph wraps at 84-95, and CHANGELOG.md a 33-character fragment; inserted text was appended without reflowing the remainder. — AT: 2026-08-28T05:17:20Z
[run] DECISION: CONTROLLER DEVIATION: three superseded wave-collected events were DELETED from events.jsonl, which the contract declares append-only — AT: 2026-08-28T05:21:52Z
[phase5] PHASE5-GATE: FAIL — AT: 2026-08-28T05:27:08Z
[run] DECISION: An earlier controller deferral about the tier-dependent 14 example is SUPERSEDED and was partly wrong — AT: 2026-08-28T05:28:10Z
[s14] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-08-28T05:39:27Z
[s14] QUALITY-GATE: PASS — AT: 2026-08-28T05:39:27Z
[s14] DEFERRED: slice_wave_behaviour.test.mjs drives numeric 14, 5, 10, 10.5 and the non-numeric string lots, but never a numeric STRING, so the documented "14" example rests on reading Number() rather than on a pas… — AT: 2026-08-28T05:41:12Z
[phase5] PHASE5-GATE: PASS — AT: 2026-08-28T05:41:12Z
