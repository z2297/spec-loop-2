# Escalations

Rendered from EscalationRecords; answers are written back into the matching entry.

## [run] "Enhance with an indent-based model" has three readings; two are measurably wrong   (status: ANSWERED)
<!-- escalation-id: run:ambiguity -->
<!-- escalation-identity: baeafe47b4d8e63d -->
- Trigger: ambiguity
- Opened: __TS__
- Context: The request's third item admits three readings that produce different slices, different risk and different meaning for every future run. Reading (A): generalise the existing Python indent model into a parameterised family and route Ruby to it. Reading (B): add a language-agnostic indent FALLBACK for every currently-unsupported extension. Reading (C): (A) plus routing .kt/.swift/.scala, which the …
- The decision: Which reading of "enhance with an indent-based model" did you intend?
- Options:
  1. (A) Ruby only - parameterise the indent family — (RECOMMENDED DEFAULT) Generalise the hardcoded 4-space step and the inconsistent tab handling out of _nesting_depth_python and _cognitive_approx into a per-language parameter, then add .rb with a def/end extractor. The narrowest reading, closest to the words, and the only one the council endorses. Ships as slice s3.
  2. (A) + Kotlin only from (C) — As (A), plus route .kt - which measurement confirms works for block-bodied 'fun' - and add Kotlin's 'when' to the language-scoped control words in s1. Excludes .swift and .scala as measurably broken. Slightly wider, still safe.
  3. (B) generic indent fallback for all unsupported extensions — Rejected by both plan-critic and guardian on the merits. Choosing it means accepting that a passing gate will no longer distinguish 'analysed and clean' from 'not analysable': .sql, .sh, .vue and .svelte files would report a passing number nobody can tell from a real measurement, in every future ru…
  4. Neither - just fix the two defects — Drop the third item entirely. s1 and s2 only. The indent model's two live under-counts (2-space bodies scoring 1 where 4-space scores 3; tab-indented Python scoring 0 at any depth) would be logged DEFERRED and left in place.
- If unanswered: pause slice s3; s1 and s2 are independent and proceed
- Answer: Neither - just fix the two defects. The indent-model EXTENSION is dropped: no Ruby, no Kotlin, no new _EXT_LANG entry, no generic fallback.
- Answered-at: 2026-09-10T14:12:03Z

## [run] The D1 fix I described to you is a safety regression; the correct fix is larger   (status: ANSWERED)
<!-- escalation-id: s1:material-assumption -->
<!-- escalation-identity: 407cefe8e4ce613f -->
- Trigger: material-assumption
- Opened: __TS__
- Context: Before this run started I told the human that fixing the phantom-function defect was 'adding foreach/using/lock/fixed/synchronized to _CONTROL_WORDS - a few lines plus tests'. That is wrong, and the correction is material enough to confirm rather than assume. _looks_like_call_or_control (quality_gate.py:948) is language-blind - _extract_functions_cbrace never receives lang - and its single call s…
- The decision: Confirm the corrected, larger scope for the phantom-function fix (slice s1)?
- Options:
  1. Language-scope the guard AND fix the skip record — (RECOMMENDED DEFAULT) Thread the extension from analyze_builtin:1088 through _extract_functions_for:1031 into _extract_functions_cbrace:918 and _looks_like_call_or_control:948 (whose unused `line` parameter is the free slot); keep today's 9 reserved words global and gate the 5 new ones on C#/Java; replace the terminal e…
  2. Language-scope the guard only — Clears the JS/Go/Rust regression but knowingly leaves the widened silent-omission hole: a supported-extension file with zero extracted functions stays absent from the gate JSON entirely, neither measured nor reported as unmeasured. Guardian names this as vector S2 and it would remain open.
  3. Ship it as I originally described — Global _CONTROL_WORDS widening, one constant, minimal diff. Accepts that the gate silently stops measuring any C, Go, Rust, JS or TS function named lock, using, fixed or foreach - deleting its existing threshold breaches - in exchange for suppressing C# phantom functions.
- If unanswered: pause slice s1; s3 is independent and proceeds
- Answer: Language-scope the guard AND fix the skip record. Thread the extension through _extract_functions_for into _extract_functions_cbrace and _looks_like_call_or_control; keep the 9 existing words global and gate the 5 new ones on C#/Java; replace the terminal elif at :1300 with an unconditional skip arm. Pin with a test that a .js method named lock is still extracted with metrics intact, plus the fir…
- Answered-at: 2026-09-10T14:12:03Z

## [run] Fixing the tab-indent under-count changes existing Python results, upward   (status: ANSWERED)
<!-- escalation-id: s3:material-assumption -->
<!-- escalation-identity: 28594e6d0516c0b8 -->
- Trigger: material-assumption
- Opened: __TS__
- Context: Generalising the indent model surfaces a live pre-existing defect that is not in the request and that neither of us knew about when the run started. _extract_functions_python measures indent with bare lstrip() (quality_gate.py:904) while _nesting_depth_python uses lstrip(' ') - spaces only (:979) - and _cognitive_approx repeats the latter (:1011). Consequence, measured by the guardian through ana…
- The decision: Fix the tab-indentation under-count as part of slice s3, knowing it can newly fail tab-indented Python that passes today?
- Options:
  1. Fix it, with its own test and CHANGELOG line — (RECOMMENDED DEFAULT) Unify tab handling across :904, :979 and :1011, expand tabs before the divide, and pin the regression with a named test asserting tab-indented Python reports depth > 0. Moves counts in the safe direction and closes a real hole in your own daily-use gate. Called for by both plan-critic (R2) and guar…
  2. Fix the step size only, leave tabs alone — Parameterise the 4-space step so Ruby measures correctly, but leave the tab inconsistency in place as pre-existing debt, logged DEFERRED. Smaller diff, no change to any existing .py result, and the tab under-count keeps shipping.
- If unanswered: proceed with the recommended option and log a decision event
- Answer: Fix the tab-indentation under-count, with its own named regression test and a CHANGELOG line.
- Answered-at: 2026-09-10T14:12:03Z

## [s1] SAFETY - council objects: Task 1 is a net loss of detection on the language it targets   (status: ANSWERED)
<!-- escalation-id: s1:council-objection -->
<!-- escalation-identity: 9ad4b4637e6c5b16 -->
- Trigger: council-objection
- Opened: (not recorded)
- Context: _CBRACE_DEF_RE (quality_gate.py:149-151) only matches a signature whose { sits on the SAME line. Where a C# method brace is on its own line but a control-statement brace is not, the enclosing method is never extracted and the phantom foreach/using/lock record is the SOLE measurement of that method body. Gating the four words on .cs therefore removes the only function-level signal for that code. T…
- The decision: Removing the phantom foreach/using/lock records from .cs also removes the only measurement of those blocks where the enclosing method is not extracted. Is that detection loss acceptable, or must the fix keep a measurement for a control block that no extracted function encloses?
- Options:
  1. Make the suppression conditional on coverage rather than unconditional: suppress a per-extension keyword match only when an already-collected function record's [start, end] span encloses the match line; otherwise keep today's record (over-count, the permitted direction). Put the enclosure test in a new PURE helper called from the loop, not in the body of _extract_functions_cbrace, whose cognitive complexity is already exactly 15. Ship with an Allman-brace .cs golden fixture pinning that the FAIL survives, alongside the K&R fixture pinning the record is dropped when the method IS extracted, and name the residual in the CHANGELOG. — (RECOMMENDED DEFAULT) critic-recommended default
- If unanswered: pause this slice; continue all independent slices
- Answer: HUMAN RULING - adopt the critic-recommended default: make the suppression CONDITIONAL ON COVERAGE, not unconditional. In _extract_functions_cbrace, suppress a per-extension keyword match ONLY when an already-collected function record's [start, end] span encloses the match line; otherwise keep today's record, which is an over-count and therefore the permitted direction. Put the enclosure test in a…
- Answered-at: 2026-09-10T14:30:17Z

## [s1] verification failed   (status: ANSWERED)
<!-- escalation-id: s1:quality-gate-block -->
<!-- escalation-identity: b15a7387bbc4ad72 -->
- Trigger: quality-gate-block
- Opened: (not recorded)
- Context: suite: All 7 suite segments passed: marketplace validation OK; 126 scripts unit tests OK; 1809 plugin unit tests OK; coverage 97.2% (floor 90%); 48 dashboard asset tests OK; 136 wave slice tests OK; plugin validation OK; quality: FAIL (summary_pass=false, 2 open, 0 accepted — Gate produced valid JSON. Exit code 1. Two violations measured: both class_lines at file scope in quality_gate.py (1567 li…
- The decision: Verification cannot pass automatically. Guide, accept, or drop?
- Options:
  1. Accept the listed violations as pre-existing debt — (RECOMMENDED DEFAULT) The CONTROLLER must act on this at the next dispatch: record the acceptance (redispatch.py accept-violations, then redispatch.py args) and re-dispatch with slice.entry {stage: "verify", head}.
  2. Provide fix orders — The CONTROLLER must act on this at the next dispatch: re-dispatch with slice.entry {stage: "fix", head, orders: [...]} so the FIXER receives them, or — for a red suite — answer this id and re-dispatch with {stage: "verify", head} so the debug-fixer reads it.
  3. Drop the slice — The CONTROLLER must act on this at the next dispatch: exclude the slice from the re-dispatched wave and record the drop. The loop drops nothing by itself.
- If unanswered: pause this slice; continue all independent slices
- Answer: MECHANICAL ACCEPTANCE under this run's standing class_lines ruling - not re-adjudicated. The ruling was recorded at intake citing run 20260825-scope-ceiling (human answer: ACCEPT AS PRE-EXISTING DEBT, no threshold weakened) and run 20260826-crash-classification (class_lines accepted as pre-existing debt for every slice in the run under one ruling; a new function-level violation a slice's own code…
- Answered-at: 2026-09-10T15:32:02Z

## [s3] slice crashed after verify:1   (status: ANSWERED)
<!-- escalation-id: s3:internal-error -->
<!-- escalation-identity: 0572d9d31b34ba69 -->
- Trigger: internal-error
- Opened: (not recorded)
- Context: Error: agent({schema}): StructuredOutput retry cap (5) exceeded — 5 failed calls with no valid output — last StructuredOutput error: Output does not match required schema: root: must have required property 'suite', root: must have required property 'quality', root: must have required property 'head_sha', root: must have required property 'tree_sha'. Last stage/role dispatched before the failure: …
- The decision: Retry this slice, skip it and continue the run, or stop the run to diagnose the exception?
- Options:
  1. Retry this slice — (RECOMMENDED DEFAULT) Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice, keeping the committed work on its branch.
  2. Skip this slice — The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and dispatch only the independent slices. Nothing in the loop enforces a skip — the default re-dispatch procedure would retry it.
  3. Stop the run — The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so the exception can be diagnosed before more agents are spent. Nothing in the loop stops the run by itself.
- If unanswered: pause this slice; continue all independent slices
- Answer: RETRY the slice, and the gate result is resolved by acceptance rather than by a fix. Two separate determinations, both controller-measured first-hand rather than read off the sidecar. (1) THE CRASH. s3:internal-error is a machine failure, not a judgment: the verify:1 verifier exceeded a StructuredOutput retry cap (5 failed calls, last error 'must have required property suite/quality/head_sha/tree…
- Answered-at: 2026-09-10T16:55:27Z

## [s3] 1 blocking finding(s) unresolved after 2 fix rounds   (status: ANSWERED)
<!-- escalation-id: s3:review-block -->
<!-- escalation-identity: c7fd42d6572cf199 -->
- Trigger: review-block
- Opened: (not recorded)
- Context: P1 -:0 — CHANGELOG.md ONLY - one bullet, no code. The s3 entry's bolded direction claim asserts that this change moves existing .py results UPWARD. That is measurably false in one direction and the s3 review reproduced it. Counterexample, valid Python accepted by ast.parse: `class K:\n\tdef f(self, a):\n return a\n` scored nesting_depth 4 at base 26adcad and scores 3 at head fb7a3f1 - a nesting v…
- The decision: Accept the residual findings, provide guidance, or drop the slice?
- Options:
  1. Provide fix orders — (RECOMMENDED DEFAULT) The CONTROLLER must act on this at the next dispatch: re-dispatch with slice.entry {stage: "fix", head, orders: [...]} so the FIXER receives them, or — for a red suite — answer this id and re-dispatch with {stage: "verify", head} so the debug-fixer reads it.
  2. Accept the residual as-is — The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and take no further work from it — never hand-write a DONE sidecar.
  3. Drop the slice — The CONTROLLER must act on this at the next dispatch: exclude the slice from the re-dispatched wave and record the drop. The loop drops nothing by itself.
- If unanswered: pause this slice; continue all independent slices
- Answer: CONTROLLER DETERMINATION - the finding is ADDRESSED; proceed to verify. This is not an override of a reviewer's quality judgment, because the finding is not a reviewer's judgment: order-0 IS the controller's own fix order, injected verbatim as a synthetic P1 with file '-', line 0 and outside_diff true. Verified first-hand against the diff fb7a3f1..a580350, clause by clause. (1) 'State BOTH direct…
- Answered-at: 2026-09-10T17:04:50Z

## [run] Phase 5 passed, but three P2 findings mean the run would ship two measurably false release-note claims   (status: ANSWERED)
<!-- escalation-id: phase5:material-assumption -->
<!-- escalation-identity: e475035ade281dc1 -->
- Trigger: material-assumption
- Opened: 2026-09-10T17:29:34Z
- Context: Phase 5 PASSED on both halves - suite green on the assembled whole, whole-run gate non-vacuous with only the three accepted pre-existing violations, and the integration review returned NO P0 and NO P1. Under references/risk-tiers.md, findings below the blocking bar are recorded as residual and never fixed, and phase-5-integration.md calls for a remediation slice only when steps 1-2 surface FAILUR…
- The decision: Spend one remediation slice on F1-F4, or publish the run as it stands with all eight findings recorded as residuals?
- Options:
  1. Remediate F1-F4, then publish — (RECOMMENDED DEFAULT) One remediation slice, dispatched as a slice-wave of one at tier 3: complete the tab fix so it survives masking, correct the two false CHANGELOG claims and the stale docstring, add the missing down-direction test with its measured before/after, and collapse the duplicated enclosure bound into one h…
  2. Publish as-is — Accept all eight as recorded residuals and go straight to the runbook and the publish choice. Defensible on the contract - nothing is at or above the blocking bar, the suite is green, the composed never-under-count invariant was verified across 62 real files, 8 adversarial fixtures and 4000 randomi…
- If unanswered: proceed with the recommended option and log a decision event
- Answer: REMEDIATE F1-F4 in one slice, then publish. Human also chose a publish path beyond the offered options: push to main and cut a new release, which authorises the merge, the push, and scripts/release.py (version bump, [Unreleased] rolled into a dated section, marketplace.json archive entry, git tag) - to be run only after remediation and a fresh Phase 5 pass, with the version level confirmed first.
- Answered-at: 2026-09-10T17:31:36Z

## [r1] slice crashed after verify:1   (status: ANSWERED)
<!-- escalation-id: r1:internal-error -->
<!-- escalation-identity: 2bc68f4d668c89de -->
- Trigger: internal-error
- Opened: (not recorded)
- Context: Error: agent({schema}): StructuredOutput retry cap (5) exceeded — 5 failed calls with no valid output — last StructuredOutput error: Output does not match required schema: root: must have required property 'suite', root: must have required property 'quality', root: must have required property 'head_sha', root: must have required property 'tree_sha'. Last stage/role dispatched before the failure: …
- The decision: Retry this slice, skip it and continue the run, or stop the run to diagnose the exception?
- Options:
  1. Retry this slice — (RECOMMENDED DEFAULT) Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice, keeping the committed work on its branch.
  2. Skip this slice — The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and dispatch only the independent slices. Nothing in the loop enforces a skip — the default re-dispatch procedure would retry it.
  3. Stop the run — The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so the exception can be diagnosed before more agents are spent. Nothing in the loop stops the run by itself.
- If unanswered: pause this slice; continue all independent slices
- Answer: RETRY the slice at verify. Two determinations, both controller-measured first-hand at the real head 7aba97ea7d05498a264b6378854d04f49025d206. (1) THE CRASH is the SECOND occurrence of an identical failure this run: the verify:1 verifier exceeded a StructuredOutput retry cap of 5, last error 'must have required property suite/quality/head_sha/tree_sha'. s3 attempt 1 died exactly the same way, at e…
- Answered-at: 2026-09-10T18:30:31Z

