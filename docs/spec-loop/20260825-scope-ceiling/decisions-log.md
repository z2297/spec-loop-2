# Decisions log

Rendered from the run's events; append-only, and nothing parses it back.

[intake] DECISION: plugin_root pinned to the installed 2.0.0 cache, not this repo — AT: 2026-08-25T17:51:52Z
[intake] DECISION: serial s1->s2->s3->s4 chain, overriding the full-council recommendation to parallelise s1 and s2 — AT: 2026-08-25T17:51:52Z
[intake] DECISION: scope ceiling is run-level only, mirroring shared_constraints[]; no per-slice non_goals field — AT: 2026-08-25T17:51:52Z
[intake] COUNCIL-VERDICT: SAFETY OBJECT — AT: 2026-08-25T17:51:52Z
[intake] DEFERRED: run_metrics by_member reads payload.member, a key the workflow never emits (it emits panel[]), so per-lane attribution of a scope flag will read null — AT: 2026-08-25T17:52:29Z
[intake] DEFERRED: metrics will double-count deferrals once the wave emits deferred events: _safety_metrics counts deferrals_total while _council_stats independently counts the same texts as concerns_deferred — AT: 2026-08-25T17:52:29Z
[intake] DEFERRED: the pre-existing fixableByReplan vs fixable_by_replan casing mismatch in all three council agent docs is left unfixed — AT: 2026-08-25T17:52:29Z
[intake] DEFERRED: dashboard surfacing of the new over-scope flag is not built - three server allowlists and two client allowlists would need changes — AT: 2026-08-25T17:52:29Z
[run] DECISION: human chose to update the installed plugin to 2.1.0 and resume, rather than run four waves on stale 2.0.0 machinery — AT: 2026-08-25T17:57:44Z
[run] DECISION: installed plugin updated 2.0.0 -> 2.1.0; the 2.1.0 cache is byte-identical to the repo plugin dir and carries the fixed guard — AT: 2026-08-25T17:59:13Z
[s1] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS — AT: 2026-08-25T18:42:57Z
[s1] QUALITY-GATE: FAIL — AT: 2026-08-25T18:42:57Z
[s1] DECISION: the P2 round-trip test is added by one inline implementer on the existing s1 branch, not by re-dispatching the wave — AT: 2026-08-25T18:59:22Z
[run] DECISION: class_lines is accepted as pre-existing debt for every slice in this run; each later quality-gate-block on the same metric resolves by this precedent without asking again — AT: 2026-08-25T19:00:10Z
[run] DEFERRED: POST-RUN FOLLOW-UP (not built this run): add a .spec-loop/quality-gate.json overlay so the plugin's own scripts are not held to a gate authored for consumer repos — AT: 2026-08-25T19:00:10Z
[s1] QUALITY-GATE: FAIL — AT: 2026-08-25T19:04:33Z
[wave1] INTEGRATION-CHECK: GREEN (evidence transferred by tree identity, suite not re-run) — integration check wave 1: GREEN by tree identity with s1's verified suite — AT: 2026-08-25T19:05:24Z
[s2] DECISION: s2's goal amended in dag.json: s1 already fixed the run_state.py coverage_omit entry that s2 was declared sole owner of — AT: 2026-08-25T19:06:23Z
[run] DECISION: added a 13th shared constraint telling every remaining slice not to spend fix rounds on pre-existing class_lines — AT: 2026-08-25T19:06:50Z
[s2] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS — AT: 2026-08-25T20:01:55Z
[s2] DECISION: guarded the unguarded r.commits.head read in THIS RUN'S persisted workflow script copy, then resumed wave 2 from the journal — AT: 2026-08-25T20:03:45Z
[s2] DECISION: HUMAN RULING: critique.over_scope stays fail-closed; the gap to close is the missing tests, not the strictness — AT: 2026-08-25T21:00:25Z
[s3] DECISION: HUMAN RULING: both slice-wave.workflow.js defects are fixed in s3 - an accepted, deliberate scope increase — AT: 2026-08-25T21:00:25Z
[s2] QUALITY-GATE: FAIL — AT: 2026-08-25T21:25:44Z
[wave2] INTEGRATION-CHECK: GREEN (evidence transferred by tree identity, suite not re-run) — integration check wave 2: GREEN by tree identity with s2's verified suite — AT: 2026-08-25T21:26:04Z
[s2] QUALITY-GATE: FAIL — AT: 2026-08-25T21:26:37Z
[s3] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS — AT: 2026-08-25T22:28:00Z
[s3] DEFERRED: two more instances of the same unguarded-optional-read defect stay UNFIXED in slice-wave.workflow.js, by deliberate application of this run's own defer router — AT: 2026-08-25T22:28:34Z
[s3] DEFERRED: s3 touched three files outside its declared list - run-state-v2.md, test_run_state.py, and a new 478-line test_slice_wave_contract.py — AT: 2026-08-25T22:28:34Z
[run] DECISION: CONTROLLER ERROR, recorded: dispatching a wave by workflow name discards any patch made to a prior wave's persisted script — AT: 2026-08-25T22:28:34Z
[s3] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS — AT: 2026-08-25T23:44:03Z
[s3] QUALITY-GATE: FAIL — AT: 2026-08-25T23:44:03Z
[s3] DECISION: a NEW file introduced by a slice that exceeds class_lines IS the slice's to fix - the human's acceptance covers pre-existing debt only — AT: 2026-08-25T23:44:22Z
[s3] DEFERRED: s3 edited CHANGELOG.md, which s4 was made sole owner of specifically to avoid a multi-way merge — AT: 2026-08-25T23:44:22Z
[s3] QUALITY-GATE: FAIL — AT: 2026-08-26T00:11:56Z
[wave3] INTEGRATION-CHECK: GREEN (evidence transferred by tree identity, suite not re-run) — integration check wave 3: GREEN by tree identity with s3's verified suite — AT: 2026-08-26T00:12:10Z
[wave4] DECISION: wave 4 runs on the PLUGIN-CACHE workflow plus the guard patch, not on the freshly-merged s3 version — AT: 2026-08-26T01:30:24Z
[s4] QUALITY-GATE: PASS — AT: 2026-08-26T02:08:21Z
[wave4] INTEGRATION-CHECK: GREEN (evidence transferred by tree identity, suite not re-run) — integration check wave 4: GREEN by tree identity with s4's verified suite — AT: 2026-08-26T02:08:39Z
[phase5] DECISION: Phase 5 metrics must be computed with the REPO copy of run_metrics.py, not the plugin cache - the cache predates this run's counters — AT: 2026-08-26T02:13:38Z
[phase5] PHASE5-GATE: PASS — phase 5 attempt 1: suite green on the assembled whole; whole-run gate non-vacuous with only accepted pre-existing class_lines — AT: 2026-08-26T02:13:38Z
[phase5] PHASE5-GATE: PASS — phase 5 attempt 1 PASS: suite green, non-vacuous gate with only accepted pre-existing findings, cross-slice review clean at the blocking bar with 4 non-blocking findings — AT: 2026-08-26T02:21:49Z
[phase5] DECISION: the three actionable integration findings are fixed by ONE inline pass, not a remediation slice - none reached the blocking bar, so no wave is owed — AT: 2026-08-26T02:21:49Z
[phase5] PHASE5-GATE: PASS — phase 5 attempt 2 PASS: suite green after the inline finding fixes; gate non-vacuous with only accepted pre-existing findings; integration review clean — AT: 2026-08-26T02:33:03Z
[phase5] DEFERRED: POST-RUN FOLLOW-UP (not built): escalations.md renders duplicate sections per escalation id, two of them stale-OPEN on a finished run — AT: 2026-08-26T02:39:19Z
