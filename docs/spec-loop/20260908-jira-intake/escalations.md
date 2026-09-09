# Escalations

Rendered from EscalationRecords; answers are written back into the matching entry.

## [run] Jira access mechanism is undecided and not planner-resolvable   (status: ANSWERED)
<!-- escalation-id: run:council-objection:jira-access -->
<!-- escalation-identity: 12c01c6339759c96 -->
- Trigger: council-objection
- Opened: 2026-09-09T01:05:00Z
- Context: All three intake council members objected on this point. Verified in-session: no jira/acli CLI on PATH, no JIRA_*/ATLASSIAN_* env vars, and the Atlassian MCP connector is installed but UNAUTHENTICATED (only authenticate/complete_authentication exposed). The candidates are disjoint slice sets and the deciding factor - which credential the human will provision - no planner can answer.
- The decision: How should the intake command reach Jira?
- Options:
- If unanswered: halt decomposition; the run cannot be shaped without this
- Answer: Stdlib REST script + env vars (JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN), mirroring pr_resolver.py's Bitbucket lane; coverage-gated with mocked transport. MCP transport rejected: unauthenticated here, and invisible to every CI gate.
- Answered-at: 2026-09-09T01:13:08Z

## [run] First irreversible external write, specified without dedupe, dry-run, or a write-time gate   (status: ANSWERED)
<!-- escalation-id: run:council-objection:write-safety -->
<!-- escalation-identity: c62ddc0ca03a8920 -->
- Trigger: council-objection
- Opened: 2026-09-09T01:05:00Z
- Context: This is the plugin's first mutating external-service call. pr_resolver.py is read-only by doctrine (test_pr_resolver.py pins get_method()=='GET') and peer-review.md records provider write-back as deliberately deferred. Jira comments notify watchers and have no idempotency key, so a re-run from a fresh clone would double-post to a production tracker.
- The decision: How should the write path behave before anything is posted to a live card?
- Options:
- If unanswered: halt decomposition; the run cannot be shaped without this
- Answer: Render, confirm, then post. Nothing is posted by default; comment bodies are rendered locally and shown, and a second explicit confirmation arms the write. Dedupe matches a visible marker in the comment body read back from the issue's PAGINATED comment list; the local artifact is an audit cache, never the gate.
- Answered-at: 2026-09-09T01:13:08Z

## [run] Card-derived artifacts would land in committed, pushed repo paths with no redaction   (status: ANSWERED)
<!-- escalation-id: run:council-objection:card-data-residency -->
<!-- escalation-identity: 0f0a19698559cab6 -->
- Trigger: council-objection
- Opened: 2026-09-09T01:05:00Z
- Context: Guardian raised this with a safety flag. Jira cards routinely carry customer data, PII and pasted secrets. run-state-v2.md:260 makes request.md the verbatim request, docs/spec-loop is tracked (228 committed files), and the remote git@github.com:z2297/spec-loop-2.git was verified PUBLIC this run. The plugin's only redaction floor (knowledge_graph.py:145) applies to the vault-write path only.
- The decision: Where should card-derived artifacts live?
- Options:
- If unanswered: halt decomposition; the run cannot be shaped without this
- Answer: Untracked by default: written to a gitignored path, with the command ensuring the ignore entry exists before writing. Nothing derived from a card can be committed or pushed by accident.
- Answered-at: 2026-09-09T01:13:08Z

## [run] 'Break down work' has readings that duplicate an existing decomposer   (status: ANSWERED)
<!-- escalation-id: run:ambiguity:breakdown-granularity -->
<!-- escalation-identity: 6a8364df17910d42 -->
- Trigger: ambiguity
- Opened: 2026-09-09T01:05:00Z
- Context: The request asks the loop to 'automatically break down work'. spec-loop.md Phase 0 step 7 already decomposes into slices, and --from-plan already exists as a handoff seam that treats plan text as data, never instructions. plan-critic recorded a second decomposer as over-scope; the alternative reading (Jira sub-task creation) would widen the comments-only write ceiling.
- The decision: What should the breakdown actually produce?
- Options:
- If unanswered: halt decomposition; the run cannot be shaped without this
- Answer: A refined request file plus a PRINTED /spec-loop:spec-loop --from-plan <path> handoff. Slice decomposition stays with the controller. This makes 'never starts work without confirmation' structural: the intake command cannot invoke the loop.
- Answered-at: 2026-09-09T01:13:08Z

## [j1] verification failed   (status: ANSWERED)
<!-- escalation-id: j1:quality-gate-block -->
<!-- escalation-identity: e97c830217d99aec -->
- Trigger: quality-gate-block
- Opened: (not recorded)
- Context: suite: All suite segments passed: validate_marketplace OK; 126 tests (scripts); 1583 tests (plugins/spec-loop/scripts); 1709 tests in measure_coverage with all coverage floors met; 98 node tests for slice_wave modules; 48 node tests for dashboard_assets with coverage reporting.; quality: FAIL (summary_pass=false — Quality gate exit code 1: 25 violations detected. summary.pass is false. Main viola…
- The decision: Verification cannot pass automatically. Guide, accept, or drop?
- Options:
  1. Proceed with the recommended default — (RECOMMENDED DEFAULT) suite: All suite segments passed: validate_marketplace OK; 126 tests (scripts); 1583 tests (plugins/spec-loop/scripts); 1709 tests in measure_coverage with all coverage floors met; 98 node tests for slice_wave modules; 48 node tests for dashboard_assets with coverage reporting.; quality: FAIL (summ…
- If unanswered: pause this slice; continue all independent slices
- Answer: CONTROLLER-RESOLVED BY PRECEDENT (run 20260825-scope-ceiling s1:quality-gate-block, 'ACCEPT AS PRE-EXISTING DEBT, no threshold weakened'; runbook: 'a new function-level violation a slice's own code introduces remains a genuine block'; re-applied at 20260826 s1, 20260827 s3/s4/s7, 20260828 s1/s3, and 20260904 s7 which required a NEW test's nesting_depth 4 be flattened). Controller re-measured the …
- Answered-at: 2026-09-09T02:31:58Z

## [j1] verification failed   (status: ANSWERED)
<!-- escalation-id: j1:quality-gate-block:2 -->
<!-- escalation-identity: 663c79bbcef6a21f -->
- Trigger: quality-gate-block
- Opened: (not recorded)
- Context: suite: All 6 suite segments passed: marketplace validation, 126 script tests, 1588 plugin tests, 1714 coverage tests (all floors met), 98 slice_wave tests, 48 dashboard_assets tests; quality: FAIL (summary_pass=false — Quality gate exited with status 1; 4 measured violations in summary.failures array)
- The decision: Verification cannot pass automatically. Guide, accept, or drop?
- Options:
  1. Proceed with the recommended default — (RECOMMENDED DEFAULT) suite: All 6 suite segments passed: marketplace validation, 126 script tests, 1588 plugin tests, 1714 coverage tests (all floors met), 98 slice_wave tests, 48 dashboard_assets tests; quality: FAIL (summary_pass=false — Quality gate exited with status 1; 4 measured violations in summary.failures arr…
- If unanswered: pause this slice; continue all independent slices
- Answer: RE-CLOSED. This id was answered once already; persisting the DONE sidecar re-appended its embedded escalation-opened record, which re-opened it. The answer is unchanged and stands: ACCEPT. All ordered fixes are controller-verified applied at f79156b, the gate is down to 4 failures of 799 checks with zero unforced function-level violations, and the slice is now DONE on the controller first-hand si…
- Answered-at: 2026-09-09T03:11:15Z

## [j1] Answer without a matching escalation entry   (status: ANSWERED)
<!-- escalation-id: j1:quality-gate-block:3 -->
- Opened: (not recorded — no escalation-opened entry was rendered)
- Answer: ACCEPTED AND CLOSED BY THE CONTROLLER - no further dispatch. The wave's verify stage is deterministic on the gate's exit code, so it re-raised this identical record on all three dispatches and would do so indefinitely: dispatch 3 returned the SAME head f79156b with no new commit and 221k subagent tokens spent replaying cached agents. Continuing to re-dispatch is provably non-terminating, so the c…
- Answered-at: 2026-09-09T03:11:00Z

## [j2] verification failed   (status: ANSWERED)
<!-- escalation-id: j2:quality-gate-block -->
<!-- escalation-identity: 98d77a01a9197e81 -->
- Trigger: quality-gate-block
- Opened: (not recorded)
- Context: suite: All 6 suite segments passed: marketplace validation OK; 126 root scripts tests passed; 1636 spec-loop plugin scripts tests passed; 1762 tests passed with all coverage floors met; 98 node.js slice wave tests passed; 48 dashboard assets tests passed; quality: FAIL (summary_pass=false — Gate exited 1 (measured failure). JSON report parsed successfully. Two whole-file class_lines violations re…
- The decision: Verification cannot pass automatically. Guide, accept, or drop?
- Options:
  1. Proceed with the recommended default — (RECOMMENDED DEFAULT) suite: All 6 suite segments passed: marketplace validation OK; 126 root scripts tests passed; 1636 spec-loop plugin scripts tests passed; 1762 tests passed with all coverage floors met; 98 node.js slice wave tests passed; 48 dashboard assets tests passed; quality: FAIL (summary_pass=false — Gate ex…
- If unanswered: pause this slice; continue all independent slices
- Answer: GATE ACCEPTED by precedent; THREE correctness fixes ordered. Do exactly these and nothing else. GATE - controller re-measured at the slice base f6ed728 rather than trusting either report: TWO failures of 429 checks, both whole-file class_lines (jira_intake.py 386, measure_coverage.py 539, against 300). ZERO function-level violations. Accepted as pre-existing debt per run 20260825-scope-ceiling s1…
- Answered-at: 2026-09-09T04:16:34Z

## [j2] verification failed   (status: ANSWERED)
<!-- escalation-id: j2:quality-gate-block:2 -->
<!-- escalation-identity: 06e095de4de84f89 -->
- Trigger: quality-gate-block
- Opened: (not recorded)
- Context: suite: All suite segments passed: marketplace validation OK; 126 Python unit tests (scripts); 1649 Python unit tests (plugins/spec-loop/scripts); 1775 coverage tests with all floors met; 98 node tests (slice_wave); 48 node tests (dashboard assets); quality: FAIL (summary_pass=false — Gate report shows summary.pass=false with three violations, all whole-file class_lines metrics (pre-existing debt)…
- The decision: Verification cannot pass automatically. Guide, accept, or drop?
- Options:
  1. Proceed with the recommended default — (RECOMMENDED DEFAULT) suite: All suite segments passed: marketplace validation OK; 126 Python unit tests (scripts); 1649 Python unit tests (plugins/spec-loop/scripts); 1775 coverage tests with all floors met; 98 node tests (slice_wave); 48 node tests (dashboard assets); quality: FAIL (summary_pass=false — Gate report sh…
- If unanswered: pause this slice; continue all independent slices
- Answer: GATE ACCEPTED. THREE fixes ordered, then return DONE. Do exactly these. GATE - controller re-measured at base f6ed728: THREE failures of 524 checks, all whole-file class_lines (jira_intake.py 437, test_jira_intake.py 381, measure_coverage.py 539 against 300). ZERO function-level violations. Accepted per run 20260825-scope-ceiling s1: no threshold weakened, no file split, nothing added to coverage…
- Answered-at: 2026-09-09T04:49:17Z

## [j2] Slice j2 is already fully implemented and committed on its branch   (status: ANSWERED)
<!-- escalation-id: j2:ambiguity -->
<!-- escalation-identity: a2aa06a1ecfe3c52 -->
- Trigger: ambiguity
- Opened: (not recorded)
- Context: Working read-only in /Users/zachmcmurry/Documents/Repos/spec-loop-2/.worktrees/spec-loop/20260908-jira-intake/j2 (branch spec-loop/20260908-jira-intake/j2, clean tree, HEAD c0bdca3), every named file of slice j2 already exists and is committed by ~14 commits including fix rounds: plugins/spec-loop/commands/jira-intake.md (151 lines, allowed-tools exactly ["AskUserQuestion","Bash","Read","Write"] …
- The decision: Slice j2's goal appears already delivered on this branch. How should the workflow proceed?
- Options:
  1. Treat j2 as built — (RECOMMENDED DEFAULT) Skip re-planning and send this worktree straight to review/verify (validate_marketplace.py, both unittest discovery runs, measure_coverage.py, the node --test suites). No plan file is needed; a new plan would only re-derive already-committed code.
  2. Send the residual gap — If this planner was dispatched because verification, review, or the quality gate failed, re-dispatch with that failure output attached; I will plan a narrow fix slice scoped to exactly that failure rather than the whole j2 goal.
  3. Authorize a rewrite — Explicitly approve replacing the committed jira_intake.py / jira-intake.md work with a freshly planned implementation. That is a rewrite of roughly 1900 existing lines and is not advisable without a stated defect.
- If unanswered: pause this slice; continue all independent slices
- Answer: OPTION 2 - SEND THE RESIDUAL GAP. You are correct that the slice GOAL is delivered; do not re-plan the goal and do not rewrite anything. Plan a NARROW fix slice scoped to exactly the three defects below, all of which the controller reproduced first-hand through the real callables at branch head c0bdca3. Two earlier fix rounds landed (43c7e5d validate_record, dfb1047 front-matter escaping, 60d41a8…
- Answered-at: 2026-09-09T04:52:30Z

## [j2] verification failed   (status: ANSWERED)
<!-- escalation-id: j2:quality-gate-block -->
<!-- escalation-identity: 829ebfd764fc1dd4 -->
- Trigger: quality-gate-block
- Opened: (not recorded)
- Context: suite: All suite segments passed. Marketplace validation: OK. Python tests: 126 + 1659 + 1785 (with 3 skipped) all OK, coverage PASS (97.0% total, all per-file and total floors met). Node tests: 98 + 48 all passed.; quality: FAIL (summary_pass=false — Gate exited with code 1. Output shows summary.pass false with 2 violations in summary.failures array: jira_intake.py class_lines 492 (threshold 300…
- The decision: Verification cannot pass automatically. Guide, accept, or drop?
- Options:
  1. Proceed with the recommended default — (RECOMMENDED DEFAULT) suite: All suite segments passed. Marketplace validation: OK. Python tests: 126 + 1659 + 1785 (with 3 skipped) all OK, coverage PASS (97.0% total, all per-file and total floors met). Node tests: 98 + 48 all passed.; quality: FAIL (summary_pass=false — Gate exited with code 1. Output shows summary.p…
- If unanswered: pause this slice; continue all independent slices
- Answer: ACCEPT and CLOSE. All three ordered defects are controller-verified applied at d3cc117: every card-derived surface (description, summary/H1, acceptance-criteria item, risk text, gap question, embedded comment body) now renders exactly TWO lines equal to '---', down from 3-4 on five of six; validate_record rejects a None scalar and a non-list comments with a mapped IntakeError; and the 'duplicate …
- Answered-at: 2026-09-09T05:19:20Z

## [j3] verification failed   (status: ANSWERED)
<!-- escalation-id: j3:quality-gate-block -->
<!-- escalation-identity: fac8b9fbb4f27efd -->
- Trigger: quality-gate-block
- Opened: (not recorded)
- Context: suite: All suite segments passed. Segment 1: validate_marketplace OK. Segment 2: 126 tests passed. Segment 3: 1729 tests passed. Segment 4: 1855 tests passed (3 skipped), all coverage floors met. Segment 5: 98 node tests passed. Segment 6: 48 node tests passed.; quality: FAIL (summary_pass=false — Quality gate produced valid JSON. Gate exit code 1. All violations are whole-file class_lines breach…
- The decision: Verification cannot pass automatically. Guide, accept, or drop?
- Options:
  1. Proceed with the recommended default — (RECOMMENDED DEFAULT) suite: All suite segments passed. Segment 1: validate_marketplace OK. Segment 2: 126 tests passed. Segment 3: 1729 tests passed. Segment 4: 1855 tests passed (3 skipped), all coverage floors met. Segment 5: 98 node tests passed. Segment 6: 48 node tests passed.; quality: FAIL (summary_pass=false — …
- If unanswered: pause this slice; continue all independent slices
- Answer: GATE ACCEPTED. ONE BLOCKING DEFECT plus four accuracy fixes. Then return DONE. GATE - controller re-measured at base 4060156: FIVE failures of 531 checks, ALL whole-file class_lines (jira_client.py 812, jira_intake.py 507, test_jira_client.py 1178, test_jira_intake.py 475, measure_coverage.py 539, against 300). ZERO function-level violations. Accepted per run 20260825-scope-ceiling s1: no thresho…
- Answered-at: 2026-09-09T06:35:38Z

## [j3] slice crashed after verify:1   (status: ANSWERED)
<!-- escalation-id: j3:internal-error -->
<!-- escalation-identity: bae23bfda1d1a6d5 -->
- Trigger: internal-error
- Opened: (not recorded)
- Context: Error: agent({schema}): StructuredOutput retry cap (5) exceeded — 5 failed calls with no valid output — last StructuredOutput error: Output does not match required schema: root: must have required property 'suite', root: must have required property 'quality', root: must have required property 'head_sha', root: must have required property 'tree_sha'. Last stage/role dispatched before the failure: …
- The decision: Retry this slice, skip it and continue the run, or stop the run to diagnose the exception?
- Options:
  1. Retry this slice — (RECOMMENDED DEFAULT) Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice, keeping the committed work on its branch.
  2. Skip this slice — The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and dispatch only the independent slices. Nothing in the loop enforces a skip — the default re-dispatch procedure would retry it.
  3. Stop the run — The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so the exception can be diagnosed before more agents are spent. Nothing in the loop stops the run by itself.
- If unanswered: pause this slice; continue all independent slices
- Answer: RETRY THIS SLICE, scoped to ONE remaining documentation defect. The crash is not a blocker: it hit at verify:1 on a StructuredOutput retry cap, AFTER 4 tasks had committed, and the controller has independently confirmed the committed work is sound. Do not re-plan the lane, do not re-derive committed code. WHAT IS ALREADY GOOD, controller-verified at head 560dceb through the real callables: the bl…
- Answered-at: 2026-09-09T07:17:03Z

## [r1] Answer without a matching escalation entry   (status: ANSWERED)
<!-- escalation-id: r1:internal-error -->
- Opened: (not recorded — no escalation-opened entry was rendered)
- Answer: CLOSED BY THE CONTROLLER - no retry needed. The crash hit at verify:1 on a StructuredOutput retry cap AFTER all 3 tasks had committed (second occurrence of this same crash shape this run; j3 hit it too). No work was lost. All three remediation items are controller-verified applied at f441f7e: _http_get now maps a bare TimeoutError to JiraError and leaks neither the token nor the email; the error …
- Answered-at: 2026-09-09T08:09:54Z

