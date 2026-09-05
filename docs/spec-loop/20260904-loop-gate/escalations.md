# Escalations

Rendered from EscalationRecords; answers are written back into the matching entry.

## [run] Gate B's audience: repo-wide or scoped to the controller session?   (status: ANSWERED)
<!-- escalation-id: run:council-objection -->
- Trigger: council-objection
- Opened: 2026-09-04T20:17:47Z
- Context: Probe B2 (run by the controller, two turns in one headless session) established that stop_hook_active resets to false on every new user turn: turn 1 fired false-block-true, turn 2 fired false-block-true again. That single fact resolves both council safety readings at once. Guardian's worry that Gate B might be a one-shot per session - protecting only the first wave boundary, which is exactly the …
- The decision: How should Gate B's audience be bounded?
- Options:
  1. Scope to the controller session — (RECOMMENDED DEFAULT) Phase 1 and Resume write .controller-session beside .active; the new gates fire only when the payload's session_id matches. Applied ONLY to the two new gates so check_bash and check_write keep their verified 2026-07-07 Task-subagent coverage. Cost: after a --resume in a fresh session the gate is in…
  2. Keep it repo-wide — Simpler and survives a change of session identity, but any session in the repo eats one forced continuation per turn while a run is active, and one stale .active blocks every turn end in the repo indefinitely.
- If unanswered: hold the whole run; all three change what gets built
- Answer: Scope to controller session
- Answered-at: 2026-09-04T20:17:47Z

## [run] Ship Gate A unverified, bank it unregistered, or drop it this run?   (status: ANSWERED)
<!-- escalation-id: run:council-objection:2 -->
- Trigger: council-objection
- Opened: 2026-09-04T20:17:47Z
- Context: Three independent problems converged on Gate A. Its firing is UNRESOLVED on 2.1.260 because AskUserQuestion is absent from print mode's tool list, so there was never a call to match - an absence of opportunity, not a negative result. Guardian found it would deny the controller's own dirty-tree escalation on the --resume path, with its reason text recommending the unsafe path. And it breaks /spec-…
- The decision: What should this run ship for Gate A?
- Options:
  1. Drop Gate A this run — (RECOMMENDED DEFAULT) Ship Gate B session-scoped plus all the prose, including the open-the-escalation-record-before-asking line that fixes guardian's R1 on its own merits. Gate A becomes a deferred record with a tracked probe follow-up. This narrows the human's earlier 'Gates + prose' choice to one gate.
  2. Build the code, leave it unregistered — Code and tests land behind a one-line activation; dead code until verified.
  3. Build and register it now — Full approved scope; either does nothing or does harm on the resume path.
- If unanswered: hold the whole run; all three change what gets built
- Answer: Drop Gate A this run
- Answered-at: 2026-09-04T20:17:47Z

## [run] Marker tracking: untrack and gitignore, or leave as-is?   (status: ANSWERED)
<!-- escalation-id: run:material-assumption -->
- Trigger: material-assumption
- Opened: 2026-09-04T20:17:47Z
- Context: Guardian found .active was committed in 5de8f42 and a413b93 though run-state-v2.md:272 states it is never committed; a pushed .active would gate every clone once Gate B ships. Verifying that surfaced a controller error: the pre-run housekeeping commit 4b91d69 committed runs 20260827 and 20260828's .done and .publish-choice markers on the reasoning that runs 20260825 and 20260826 track theirs by c…
- The decision: How should the run-state markers be handled?
- Options:
  1. Untrack and gitignore them — (RECOMMENDED DEFAULT) Stop tracking every marker across all four prior runs, add .active, .done, .publish-choice and .paused to .gitignore, and correct the housekeeping commit's effect. Matches the stated doctrine, removes the pushed-marker hazard permanently, and ends the dirty-tree friction every run starts with.
  2. Leave them tracked — No history touched, but every future run starts dirty, a pushed .active gates every clone, and run-state-v2.md:272 stays false in practice.
- If unanswered: hold the whole run; all three change what gets built
- Answer: Untrack and gitignore them
- Answered-at: 2026-09-04T20:17:47Z

## [s1] council objects: s1 invents a FIFTH run-state marker, `.controller-session`,   (status: ANSWERED)
<!-- escalation-id: s1:council-objection -->
- Trigger: council-objection
- Opened: (not recorded)
- Context: s1 invents a FIFTH run-state marker, `.controller-session`, which the run's marker-hygiene slice does not know about. s3 (deps: [], so it can land in the same wave or before s1) pins `MARKERS = ('.active', '.done', '.paused', '.publish-choice')` in a new doctrine test, appends exactly those four literals to .gitignore, and rewrites plugins/spec-loop/references/run-state-v2.md to say 'all four mar…
- The decision: Should `.controller-session` be folded into the marker-hygiene set (s3's MARKERS tuple, the .gitignore block, and run-state-v2.md's Markers section, making it five markers), or should s1 avoid introducing a new on-disk marker at all?
- Options:
  1. Fold it in: keep s1's marker design, and in the same replan pass extend s3 to treat `.controller-session` as a fifth marker -- add it to MARKERS, to the .gitignore block, and to run-state-v2.md's Markers list (changing 'all four' to 'all five' there), and add a dep s3 -> s1 or state the shared marker set as a run-level constraint so whichever lands first cannot contradict the other. s1's own prose should also state once that `.controller-session` is never committed, so the doctrine and the enforcement agree. — (RECOMMENDED DEFAULT) critic-recommended default
- If unanswered: pause this slice; continue all independent slices
- Answer: Fold it in — and it is already folded in. s3 shipped .controller-session as the fifth marker (test_doctrine_marker_hygiene.py MARKERS line 41-43 and .gitignore lines 14-19), so the plan lines your objection cites are stale against the merged artifact. Replan on the integration branch: keep the .controller-session design, state once in the prose that it is never committed, and do NOT touch .gitign…
- Answered-at: 2026-09-04T20:50:06Z

## [s7] verification failed   (status: ANSWERED)
<!-- escalation-id: s7:quality-gate-block -->
- Trigger: quality-gate-block
- Opened: (not recorded)
- Context: suite: All 10 suite segments passed: segment 1 (validate_marketplace.py) OK; segment 2 (unittest scripts) 126 tests OK; segment 3 (unittest plugins/spec-loop/scripts) 1471 tests OK; segment 4 (measure_coverage.py) 1597 tests with 3 skipped, coverage check PASS; segment 5 (dashboard_assets/index.test.mjs) 48 tests OK; segment 6 (slice_wave_behaviour.test.mjs) 35 tests OK; segment 7 (slice_wave_rad…
- The decision: Verification cannot pass automatically. Guide, accept, or drop?
- Options:
  1. Proceed with the recommended default — (RECOMMENDED DEFAULT) suite: All 10 suite segments passed: segment 1 (validate_marketplace.py) OK; segment 2 (unittest scripts) 126 tests OK; segment 3 (unittest plugins/spec-loop/scripts) 1471 tests OK; segment 4 (measure_coverage.py) 1597 tests with 3 skipped, coverage check PASS; segment 5 (dashboard_assets/index.tes…
- If unanswered: pause this slice; continue all independent slices
- Answer: Refactor, then finish the register correction the evidence now supports. THREE things. (1) THE BLOCK. The violation is real and the threshold stands: nesting_depth 4 exceeds 3 in test_the_per_turn_flag_fact_is_confirmed_with_its_evidence in the new test_doctrine_platform_probes.py. Flatten it - a guard clause, a helper, or a comprehension instead of the nested block - so the assertion set is unch…
- Answered-at: 2026-09-05T00:36:37Z

