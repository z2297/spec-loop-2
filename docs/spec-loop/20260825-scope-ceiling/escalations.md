# Escalations

Rendered from EscalationRecords; answers are written back into the matching entry.

## [intake] Where should the weighted scope lane live - promoted role or a new council member?   (status: ANSWERED)
<!-- escalation-id: intake:council-objection-scope-lane -->
- Trigger: council-objection
- Opened: (not recorded)
- Context: Requirement 2 offered a council member OR a promoted role as an open either/or. The loop could not decide because a counted new member provably changes veto thresholds: state.critique blocks iff objections.length*2 > verdicts.length (slice-wave.workflow.js:401), so panel 1->2 kills plan-critic solo Tier-2 veto and panel 3->4 raises --thorough Tier 3 from 2 objections to 3. Guardian set its safety…
- The decision: Should the weighted scope lane be a promoted mandate on plan-critic, both a promoted role and a Tier-3 lane, or a dedicated Tier-3 agent only?
- Options:
  1. Promoted role on plan-critic — (RECOMMENDED DEFAULT) Panel size unchanged so no veto dilution; reaches Tier 2, the default tier; no 14th agent and no inline-mode or README touchpoints
  2. Both: promoted role + Tier-3 lane — Fixes the scaling asymmetry but needs arithmetic exclusion at :401 and adds a 14th agent with ~6 doc touchpoints
  3. Dedicated Tier-3 agent only — Cleanest symmetry with guardian but leaves Tier 2, most slices, with today single low-effort plan-critic
- If unanswered: pause decomposition; the whole run depends on this shape
- Answer: Promoted role on plan-critic. The scope lane is a promoted mandate on the existing member; panel size is unchanged at every tier and no 14th agent is created.
- Answered-at: 2026-08-25T17:52:29Z

## [intake] How should requirement 5 do-not-re-implement be enforced?   (status: ANSWERED)
<!-- escalation-id: intake:council-objection-req5 -->
- Trigger: council-objection
- Opened: (not recorded)
- Context: Guardian set safety.flag true on this specifically. Any prose-matched filter over the blocking set at slice-wave.workflow.js:469 can silently drop a genuine P0: FINDING has no security category so security defects arrive as correctness or errors, meaning no category allowlist can protect them, and the match key would be agent-authored deferral prose, which is also an injection channel into the bl…
- The decision: Should deferred scope be enforced by advisory prompt framing only, by a constrained mechanical suppressor, or by recording alone with no deferral list reaching the reviewer?
- Options:
  1. Advisory only, never delete a finding — (RECOMMENDED DEFAULT) Deferred list is quoted prompt data with file-a-genuinely-blocking-finding-regardless framing; blocking() untouched; clears the safety flag; all three lanes converge here
  2. Constrained mechanical suppressor — Enforced in code but never touches P0, every drop emits an event naming the finding and matched deferral, Python-side tests required
  3. Record only, reviewer sees no deferral list — Closes the prose-injection channel entirely but a reviewer will re-raise deferred scope because nothing tells it not to
- If unanswered: pause s3; the anti-re-admission mechanism cannot be designed without this
- Answer: Advisory only, never delete a finding. Deferred scope is quoted advisory prompt data with explicit file-a-genuinely-blocking-finding-regardless framing; blocking() output is never filtered at any severity. This clears the guardian safety flag.
- Answered-at: 2026-08-25T17:52:29Z

## [run] Installed plugin is 2.0.0 with five bugs already fixed in 2.1.0   (status: ANSWERED)
<!-- escalation-id: run:material-assumption-runtime-version -->
- Trigger: material-assumption
- Opened: (not recorded)
- Context: The loop resolves agents, hooks, workflow and scripts from the installed plugin cache, which is stale at 2.0.0. Running four waves on it means running on the guard false positive that caused two false gate PASSes in run 20260807, agent-self-labeled gate verdicts, wave re-dispatch that re-runs merged slices, run_state cwd-drift fragments, and undetected vacuous gate passes. The controller cannot f…
- The decision: Update the plugin to 2.1.0 and resume, proceed on 2.0.0 with controller-side mitigations, or snapshot the repo plugin to scratch?
- Options:
  1. Update to 2.1.0, then resume — (RECOMMENDED DEFAULT) all intake state is on disk and resumable; nothing implemented yet
  2. Proceed now on 2.0.0 with mitigations — prompt-level workarounds for bugs already fixed in code
  3. Snapshot the repo plugin to scratch — fixes scripts and workflow but not the guard hook or agent definitions
- If unanswered: do not dispatch wave 1
- Answer: Update to 2.1.0, then resume. The plugin is refreshed from origin/main, which already contains the 2.1.0 release commit f3eac92, before wave 1 is dispatched.
- Answered-at: 2026-08-25T17:57:44Z

## [s1] verification failed   (status: ANSWERED)
<!-- escalation-id: s1:quality-gate-block -->
- Trigger: quality-gate-block
- Opened: (not recorded)
- Context: suite: All 6 suite segments passed: marketplace validation OK; 106 tests in scripts; 1028 tests in plugins/spec-loop/scripts; 1134 tests in coverage measurement with 3 skipped, all coverage floors met (96.6% total); 48 node tests; plugin validation passed.; quality: FAIL (summary_pass=false — Quality gate exit code 1. Two class_lines violations: dag.py at 650 lines exceeds threshold of 300; test_…
- The decision: Verification cannot pass automatically. Guide, accept, or drop?
- Options:
  1. Proceed with the recommended default — (RECOMMENDED DEFAULT) suite: All 6 suite segments passed: marketplace validation OK; 106 tests in scripts; 1028 tests in plugins/spec-loop/scripts; 1134 tests in coverage measurement with 3 skipped, all coverage floors met (96.6% total); 48 node tests; plugin validation passed.; quality: FAIL (summary_pass=false — Quali…
- If unanswered: pause this slice; continue all independent slices
- Answer: USER RULING - ACCEPT AS PRE-EXISTING DEBT, no threshold weakened, plus one added test. (a) The two residual class_lines findings (dag.py 650 vs 300, test_dag.py 762 vs 300) are accepted for this run. Controller-measured evidence: both files already violated on the integration branch at 573 and 704 non-blank before s1 wrote a line, and the gate has NEVER passed on plugins/spec-loop/scripts/ - 172 …
- Answered-at: 2026-08-25T18:59:10Z

## [s1] verification failed   (status: ANSWERED)
<!-- escalation-id: s1:quality-gate-block -->
- Trigger: quality-gate-block
- Opened: (not recorded)
- Context: suite: All 6 suite segments passed: marketplace validation OK; 106 tests in scripts; 1028 tests in plugins/spec-loop/scripts; 1134 tests in coverage measurement with 3 skipped, all coverage floors met (96.6% total); 48 node tests; plugin validation passed.; quality: FAIL (summary_pass=false — Quality gate exit code 1. Two class_lines violations: dag.py at 650 lines exceeds threshold of 300; test_…
- The decision: Verification cannot pass automatically. Guide, accept, or drop?
- Options:
  1. Proceed with the recommended default — (RECOMMENDED DEFAULT) suite: All 6 suite segments passed: marketplace validation OK; 106 tests in scripts; 1028 tests in plugins/spec-loop/scripts; 1134 tests in coverage measurement with 3 skipped, all coverage floors met (96.6% total); 48 node tests; plugin validation passed.; quality: FAIL (summary_pass=false — Quali…
- If unanswered: pause this slice; continue all independent slices
- Answer:
- Answered-at:

## [s2] wave interrupted   (status: ANSWERED)
<!-- escalation-id: s2:budget-exhausted -->
- Trigger: budget-exhausted
- Opened: (not recorded)
- Context: undefined is not an object (evaluating 'r.commits.head')
- The decision: The wave hit a hard limit. Raise budget/caps and resume, or accept committed work?
- Options:
  1. Proceed with the recommended default — (RECOMMENDED DEFAULT) undefined is not an object (evaluating 'r.commits.head')
- If unanswered: pause this slice; continue all independent slices
- Answer: RE-ANSWERED to close a bookkeeping artifact, not a new question. The original answer stands verbatim: this was never a resource limit but an unguarded r.commits.head read whose TypeError the workflow's catch-all mislabels as budget-exhausted; it was resolved by guarding the read in this run's persisted script copy and resuming from the journal. The record reopened only because the controller brie…
- Answered-at: 2026-08-25T21:26:56Z

## [s2] Answer without a matching escalation entry   (status: ANSWERED)
<!-- escalation-id: s2:quality-gate-block -->
- Opened: (not recorded — no escalation-opened entry was rendered)
- Answer: CONTROLLER-RESOLVED BY IN-RUN PRECEDENT (human ruling on s1:quality-gate-block, recorded as a run-scope decision), not re-surfaced. Controller-measured the gate at s2 HEAD 6be15a0: exactly FOUR failures remain and every one is a whole-file class_lines finding - run_metrics.py 1831, run_state.py 894, test_run_metrics.py 1321, test_run_state.py 1147, all against a 300 threshold. All four files were…
- Answered-at: 2026-08-25T21:00:25Z

## [s2] wave interrupted   (status: OPEN)
<!-- escalation-id: s2:budget-exhausted -->
- Trigger: budget-exhausted
- Opened: (not recorded)
- Context: undefined is not an object (evaluating 'r.commits.head')
- The decision: The wave hit a hard limit. Raise budget/caps and resume, or accept committed work?
- Options:
  1. Proceed with the recommended default — (RECOMMENDED DEFAULT) undefined is not an object (evaluating 'r.commits.head')
- If unanswered: pause this slice; continue all independent slices
- Answer:
- Answered-at:

## [s2] verification failed   (status: ANSWERED)
<!-- escalation-id: s2:quality-gate-block -->
- Trigger: quality-gate-block
- Opened: (not recorded)
- Context: suite: All 6 suite segments passed: validate_marketplace OK; 106 scripts tests; 1069 spec-loop/scripts tests; 1175 coverage tests (all coverage floors met); 48 node tests; claude plugin validation OK.; quality: FAIL (summary_pass=false — Quality gate exited with code 1. Four class_lines violations: run_metrics.py 1831 lines (threshold 300), run_state.py 894 lines (threshold 300), test_run_metrics…
- The decision: Verification cannot pass automatically. Guide, accept, or drop?
- Options:
  1. Proceed with the recommended default — (RECOMMENDED DEFAULT) suite: All 6 suite segments passed: validate_marketplace OK; 106 scripts tests; 1069 spec-loop/scripts tests; 1175 coverage tests (all coverage floors met); 48 node tests; claude plugin validation OK.; quality: FAIL (summary_pass=false — Quality gate exited with code 1. Four class_lines violations:…
- If unanswered: pause this slice; continue all independent slices
- Answer:
- Answered-at:

## [s3] wave interrupted   (status: ANSWERED)
<!-- escalation-id: s3:budget-exhausted -->
- Trigger: budget-exhausted
- Opened: (not recorded)
- Context: undefined is not an object (evaluating 'r.commits.head')
- The decision: The wave hit a hard limit. Raise budget/caps and resume, or accept committed work?
- Options:
  1. Proceed with the recommended default — (RECOMMENDED DEFAULT) undefined is not an object (evaluating 'r.commits.head')
- If unanswered: pause this slice; continue all independent slices
- Answer: CONTROLLER-RESOLVED. Genuine agent failure this time, not a mislabeled crash and not a resource limit: the FINAL verify agent hit the StructuredOutput retry cap - 5 calls with no schema-valid output - and the catch-all again reported it as budget-exhausted. Everything before it succeeded: 7 tasks, the Tier-3 two-reviewer panel, the batched finding-verifier, one fix round and the simplify polish a…
- Answered-at: 2026-08-25T23:44:03Z

## [s3] wave interrupted   (status: OPEN)
<!-- escalation-id: s3:budget-exhausted -->
- Trigger: budget-exhausted
- Opened: (not recorded)
- Context: agent({schema}): StructuredOutput retry cap (5) exceeded — 5 failed calls with no valid output
- The decision: The wave hit a hard limit. Raise budget/caps and resume, or accept committed work?
- Options:
  1. Proceed with the recommended default — (RECOMMENDED DEFAULT) agent({schema}): StructuredOutput retry cap (5) exceeded — 5 failed calls with no valid output
- If unanswered: pause this slice; continue all independent slices
- Answer:
- Answered-at:

## [s3] wave interrupted   (status: ANSWERED)
<!-- escalation-id: s3:budget-exhausted -->
- Trigger: budget-exhausted
- Opened: (not recorded)
- Context: agent({schema}): StructuredOutput retry cap (5) exceeded — 5 failed calls with no valid output
- The decision: The wave hit a hard limit. Raise budget/caps and resume, or accept committed work?
- Options:
  1. Proceed with the recommended default — (RECOMMENDED DEFAULT) agent({schema}): StructuredOutput retry cap (5) exceeded — 5 failed calls with no valid output
- If unanswered: pause this slice; continue all independent slices
- Answer:
- Answered-at:

