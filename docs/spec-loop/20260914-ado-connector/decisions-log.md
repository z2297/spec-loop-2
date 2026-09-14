# Decisions log

Rendered from the run's events; append-only, and nothing parses it back.

[run] DECISION: Cut the integration branch from main, not from the checked-out fix/run-recording-gaps. — AT: 2026-09-14T13:48:23Z
[run] DECISION: Proceeded with one untracked file present (docs/spec-loop/spec-loop-last-two-runs.pdf) rather than escalating. — AT: 2026-09-14T13:48:23Z
[run] DECISION: ado_client.py uses hand-rolled stdlib urllib REST with an env-var PAT, mirroring jira_client.py - NOT the Azure CLI, despite pr_resolver.py being the repo existing ADO precedent via `az repos pr show… — AT: 2026-09-14T13:48:23Z
[run] DECISION: ADO_PROJECT is OPTIONAL and absent by default. Resolve on the project-optional route with org+id, derive project from System.TeamProject, and if ADO_PROJECT is set treat it as an assertion that refus… — AT: 2026-09-14T13:48:23Z
[wave1] DECISION: Ended the turn at the wave-1 boundary WITHOUT re-dispatching, and did NOT write .paused. — AT: 2026-09-14T14:03:57Z
[run] DECISION: Coverage-gate registration stays a5-exclusive (trailing), against the council split recommendation that each slice register its own module. Amended shared_constraints and a5 goal to remove an ambigui… — AT: 2026-09-14T14:05:34Z
[wave1] DECISION: Restored the integration branch working tree to clean after a wave-1 agent wrote the coverage-gate registration into the MAIN checkout instead of its slice worktree. Both diffs preserved under docs/s… — AT: 2026-09-14T15:09:40Z
[run] DECISION: Registration belongs to the LAST slice that modifies a module, not to a trailing wiring slice and not to every slice. ado_intake.py -> a3 (done, measured 96.3% -> floor 91). ado_client.py -> a2. a5 n… — AT: 2026-09-14T15:09:40Z
[a1] COUNCIL-VERDICT: OBJECT (10 concerns) [SCOPE-FLAGGED: Plan task 7 steps 5-8 modified scripts/measure_coverage.py and scripts/coverage_omit.txt, which are not in a1's declared file set and which the run's amended shared_constraints and the recorded cover…] — AT: 2026-09-14T16:15:01Z
[a1] QUALITY-GATE: FAIL — Quality gate exit code 1. Summary: pass=false. Violations: 12 total - two class_lines violations (ado_client 865 lines, test_ado_client 887 lines, both threshold 300), redirect_request has 6 paramete… — AT: 2026-09-14T16:15:01Z
[a3] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS (7 concerns) [scope: clean] — AT: 2026-09-14T16:15:01Z
[a3] QUALITY-GATE: FAIL — 3 whole-file class_lines violation(s) — AT: 2026-09-14T16:15:01Z
[wave1] DECISION: Both wave-1 sidecars were reconstructed by the controller from the workflow journal rather than persisted from the wave return value. — AT: 2026-09-14T16:15:35Z
[a3] DECISION: accepted 3 quality-gate violation(s) for a3: class_lines plugins/spec-loop/scripts/ado_intake.py, class_lines plugins/spec-loop/scripts/test_ado_intake.py, class_lines scripts/measure_coverage.py — AT: 2026-09-14T16:15:35Z
[a1] DECISION: accepted 3 quality-gate violation(s) for a1: class_lines plugins/spec-loop/scripts/ado_client.py, class_lines plugins/spec-loop/scripts/test_ado_client.py, parameter_count plugins/spec-loop/scripts/a… — AT: 2026-09-14T16:15:54Z
[a3] DECISION: 3 accepted violation fingerprint(s) supplied for a3: class_lines plugins/spec-loop/scripts/ado_intake.py, class_lines plugins/spec-loop/scripts/test_ado_intake.py, class_lines scripts/measure_coverag… — AT: 2026-09-14T16:25:03Z
[a3] RE-ENTRY: re-entered at verify from head ba3e2f8 (0 order(s), 2 fix round(s) already spent) — AT: 2026-09-14T16:25:03Z
[a3] QUALITY-GATE: FAIL — measured at verify:1 on ba3e2f8: 0 violation(s), 3 accepted — AT: 2026-09-14T16:25:03Z
[a1] DECISION: 3 accepted violation fingerprint(s) supplied for a1: class_lines plugins/spec-loop/scripts/ado_client.py, class_lines plugins/spec-loop/scripts/test_ado_client.py, parameter_count plugins/spec-loop/s… — AT: 2026-09-14T16:25:03Z
[a1] RE-ENTRY: re-entered at fix from head 6ae96ee (7 order(s), 2 fix round(s) already spent) — AT: 2026-09-14T16:25:03Z
[a1] QUALITY-GATE: FAIL — measured at gate on 6ae96ee: 9 violation(s), 3 accepted — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-0 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-1 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-2 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-3 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-4 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-5 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-6 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-7 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-8 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-fix-1 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-fix-2 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-fix-3 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-fix-4 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-fix-5 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-fix-6 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] DECISION: finding qg-fix-7 refuted by batched verifier — AT: 2026-09-14T16:25:03Z
[a1] QUALITY-GATE: FAIL — measured at verify:1 on 6ae96ee: 9 violation(s), 3 accepted — AT: 2026-09-14T16:25:03Z
[wave1] INTEGRATION-CHECK: GREEN — Exactly ONE slice merged this round (a3) and the integration branch tree sha equals slice a3's verified tests.tree_sha byte for byte, so the slice's full six-segment GREEN evidence transfers by tree … — AT: 2026-09-14T16:25:46Z
[a1] DECISION: accepted 9 quality-gate violation(s) for a1: nesting_depth plugins/spec-loop/scripts/test_ado_client.py:test_headings_get_the_heading_prefix, nesting_depth plugins/spec-loop/scripts/test_ado_client.p… — AT: 2026-09-14T16:26:46Z
[a1] DECISION: 12 accepted violation fingerprint(s) supplied for a1: class_lines plugins/spec-loop/scripts/ado_client.py, class_lines plugins/spec-loop/scripts/test_ado_client.py, parameter_count plugins/spec-loop/… — AT: 2026-09-14T16:30:50Z
[a1] RE-ENTRY: re-entered at verify from head 6ae96ee (0 order(s), 2 fix round(s) already spent) — AT: 2026-09-14T16:30:50Z
[a1] QUALITY-GATE: FAIL — measured at verify:1 on 6ae96ee: 0 violation(s), 12 accepted — AT: 2026-09-14T16:30:50Z
[wave1] INTEGRATION-CHECK: GREEN — All six segments on the integration branch at a39272b: marketplace valid; 126 root tests OK; 2030 plugin tests OK; coverage 2156 tests, ado_intake.py 96.3% vs floor 91, TOTAL 97.1% (7702/7928), all f… — AT: 2026-09-14T16:33:44Z
[a2] DECISION: Wave 2 dispatches a2 with three accepted violation fingerprints supplied up front: class_lines on ado_client.py, class_lines on test_ado_client.py, and parameter_count on ado_client.py:redirect_reque… — AT: 2026-09-14T16:34:22Z
[a2] DECISION: 3 accepted violation fingerprint(s) supplied for a2: class_lines plugins/spec-loop/scripts/ado_client.py, class_lines plugins/spec-loop/scripts/test_ado_client.py, parameter_count plugins/spec-loop/s… — AT: 2026-09-14T18:04:48Z
[a2] REFACTOR-RADIUS: refactor radius WITHIN: every declared number is at or under its ceiling (compared: rewrite_ratio, touched_existing_files) — AT: 2026-09-14T18:04:48Z
[a2] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-09-14T18:04:48Z
[a2] DEFERRED: THE DEDUPE GATE IS TOCTOU ACROSS INVOCATIONS. run_comment_lane reads the comment list once and then posts the whole pending batch from that snapshot (plan lines 1323-1342, correctly documented). Two … — AT: 2026-09-14T18:04:48Z
[a2] QUALITY-GATE: FAIL — measured at gate on 7dafe52: 14 violation(s), 2 accepted — AT: 2026-09-14T18:04:48Z
[a2] DECISION: accepted fingerprint(s) matched no measured violation: parameter_count plugins/spec-loop/scripts/ado_client.py:redirect_request (stale, renamed, or already refactored) — AT: 2026-09-14T18:04:48Z
[a2] QUALITY-GATE: FAIL — measured at verify:1 on caeaa7d: 1 violation(s), 2 accepted — AT: 2026-09-14T18:04:48Z
[a2] DECISION: accepted 1 quality-gate violation(s) for a2: class_lines scripts/measure_coverage.py — AT: 2026-09-14T18:06:04Z
[a2] DECISION: 3 accepted violation fingerprint(s) supplied for a2: class_lines plugins/spec-loop/scripts/ado_client.py, class_lines plugins/spec-loop/scripts/test_ado_client.py, class_lines scripts/measure_coverag… — AT: 2026-09-14T18:11:59Z
[a2] RE-ENTRY: re-entered at fix from head caeaa7d (4 order(s), 1 fix round(s) already spent) — AT: 2026-09-14T18:11:59Z
[a2] QUALITY-GATE: FAIL — measured at gate on caeaa7d: 0 violation(s), 3 accepted — AT: 2026-09-14T18:11:59Z
[a2] DECISION: finding prose-1 refuted by batched verifier — AT: 2026-09-14T18:11:59Z
[a2] DECISION: finding prose-2 refuted by batched verifier — AT: 2026-09-14T18:11:59Z
[a2] DECISION: finding prose-3 refuted by batched verifier — AT: 2026-09-14T18:11:59Z
[a2] DECISION: finding prose-4 refuted by batched verifier — AT: 2026-09-14T18:11:59Z
[a2] QUALITY-GATE: FAIL — measured at verify:1 on caeaa7d: 0 violation(s), 3 accepted — AT: 2026-09-14T18:11:59Z
[run] DECISION: Stop routing controller fix orders through slice.entry.orders at review_tier 3. The four prose fixes are being moved into slice a5 GOAL instead, where the planner turns them into tasks. — AT: 2026-09-14T18:11:59Z
[wave2] INTEGRATION-CHECK: GREEN — Exactly ONE slice merged (a2) and the integration branch tree equals a2's verified tests.tree_sha byte for byte, so its full six-segment GREEN evidence transfers and the post-merge suite was delibera… — AT: 2026-09-14T18:13:19Z
[a4] REFACTOR-RADIUS: refactor radius WITHIN: every declared number is at or under its ceiling (compared: rewrite_ratio, touched_existing_files) — AT: 2026-09-14T18:29:25Z
[a4] COUNCIL-VERDICT: OBJECT [SCOPE-FLAGGED: The slice cannot satisfy its own binding constraint 'Baseline stays green: all six CI gates' without editing plugins/spec-loop/README.md, which the run scope ceiling assigns to slice a5 ('The .gitign…] — AT: 2026-09-14T18:29:25Z
[a4] REFACTOR-RADIUS: refactor radius WITHIN: every declared number is at or under its ceiling (compared: rewrite_ratio, touched_existing_files) — AT: 2026-09-14T19:14:54Z
[a4] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-09-14T19:14:54Z
[a4] DEFERRED: THE ADO TWIN OF TestTheArtifactRootIsGitignored LANDS IN NEITHER SLICE. test_doctrine_jira_intake.py:153 pins that '.spec-loop-jira/' is in the repo's own .gitignore; .gitignore currently has only th… — AT: 2026-09-14T19:14:54Z
[a4] QUALITY-GATE: FAIL — measured at gate on 1bfaca6: 5 violation(s), 0 accepted — AT: 2026-09-14T19:14:54Z
[a4] QUALITY-GATE: PASS — measured at verify:1 on 85c1e77: 0 violation(s), 0 accepted — AT: 2026-09-14T19:14:54Z
[wave3] INTEGRATION-CHECK: GREEN — Exactly ONE slice merged (a4) and the integration tree equals a4's verified tests.tree_sha, so its full six-segment GREEN evidence transfers (Phase 2 step 6 exemption). a4 also passed the quality gat… — AT: 2026-09-14T19:15:19Z
[a5] REFACTOR-RADIUS: refactor radius WITHIN: every declared number is at or under its ceiling (compared: rewrite_ratio, touched_existing_files) — AT: 2026-09-14T20:09:57Z
[a5] COUNCIL-VERDICT: ENDORSE_WITH_CONCERNS [scope: clean] — AT: 2026-09-14T20:09:57Z
[a5] QUALITY-GATE: FAIL — measured at gate on 5189f3c: 2 violation(s), 0 accepted — AT: 2026-09-14T20:09:57Z
[a5] DECISION: finding r0-a5-001 closed without test evidence — kept open: the fixer named no covering test (tests_added) for a correctness finding — AT: 2026-09-14T20:09:57Z
[a5] QUALITY-GATE: FAIL — measured at verify:1 on 6a4267d: 2 violation(s), 0 accepted — AT: 2026-09-14T20:09:57Z
[a5] DECISION: accepted 2 quality-gate violation(s) for a5: class_lines plugins/spec-loop/scripts/ado_client.py, class_lines plugins/spec-loop/scripts/test_ado_client.py — AT: 2026-09-14T20:09:57Z
[a5] DECISION: 2 accepted violation fingerprint(s) supplied for a5: class_lines plugins/spec-loop/scripts/ado_client.py, class_lines plugins/spec-loop/scripts/test_ado_client.py — AT: 2026-09-14T20:13:20Z
[a5] RE-ENTRY: re-entered at verify from head 6a4267d (0 order(s), 2 fix round(s) already spent) — AT: 2026-09-14T20:13:20Z
[a5] QUALITY-GATE: FAIL — measured at verify:1 on 6a4267d: 0 violation(s), 2 accepted — AT: 2026-09-14T20:13:20Z
[phase5] PHASE5-GATE: GREEN — Controller-measured first-hand on the integration branch, all six segments: marketplace valid; 126 root tests OK; 2143 plugin tests OK; coverage 2269 tests, ado_client.py 99.3% vs floor 94, ado_intak… — AT: 2026-09-14T20:15:57Z
[phase5] DECISION: No remediation slice. The integration review returned PASS with no safety flag and all five cross-slice seams sound; its three findings are non-blocking and are recorded as follow-ons in the runbook. — AT: 2026-09-14T20:21:24Z
[phase5] DEFERRED: VERIFIED FIRST-HAND by the controller. test_doctrine_jira_intake.py carries TWO pins for the artifact root: test_the_command_names_the_gitignored_artifact_root (the command prose) at :149 AND a separ… — AT: 2026-09-14T20:27:34Z
[run] DECISION: Release version 2.6.0 (minor bump from 2.5.1). — AT: 2026-09-14T20:32:24Z
[run] DECISION: {"main": "7be1df0", "published": "merged onto main and released as 2.6.0; main and tag v2.6.0 pushed to origin", "state": "closed", "tag": "v2.6.0"} — AT: 2026-09-14T20:37:18Z
