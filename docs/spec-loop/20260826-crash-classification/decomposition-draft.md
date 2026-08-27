# Draft decomposition — 20260826-crash-classification (for intake critique)

Deliberately COARSE: the slice-planner owns the right-size gate and may SPLIT.
Two slices, two waves. Kept small on purpose — the previous run took 9h28m across four
waves, and wave count is a direct wall-clock multiplier.

## s1 — Classify machine failures separately from resource limits  (risk_tier 3)

**Goal.** `budget-exhausted` stops being the label for anything that is not a genuine
structural resource limit. Unclassified failures get their own trigger with an honest
title, context, question, and options.

**Why tier 3.** Edits the loop's own orchestration (`slice-wave.workflow.js`) AND a
fail-closed validator (`run_state.py:204`) whose rejection turns a good slice into an
ESCALATED one. Nothing this run ships in the workflow is executed by this run, so the only
coverage is source-text contract tests — which raises, not lowers, the review bar.

**Must land atomically** (see conventions.md hard constraint 1): the JS enum at `:40` and
`run_state.py:67` cannot be split across slices without leaving an intermediate commit at
which the loop cannot persist its own sidecars.

**Scope.**
1. Add the new trigger value(s) to `slice-wave.workflow.js:40` and to all three Python
   tuples (`run_state.py:67`, `run_metrics.py:119`, `dashboard_server.py:149`).
2. Rewrite `runSliceError()` `:856` to emit the new classification. Title, context and
   question must describe a machine failure; options must be retry / skip this slice / stop
   the run — NOT "raise budget/caps".
3. Decide and implement the wave-entry "slice lost" case `:878` (third conflated meaning).
4. Stage attribution: `state` has no current-stage field (`initSliceState` `:450`). Add one
   — or reuse the `role` already passed to `dispatch()` `:430` — so the crash context says
   what was in flight instead of only the exception string.
5. Add a contract test mirroring `test_slice_wave_contract.py:131` pinning the new trigger
   as NON-answerable. Do NOT add it to `ANSWERABLE_TRIGGERS`.
6. Sweep the stale comment `:637-646` that asserts the old relabelling as current behavior.
7. Keep `budget-exhausted` in every enum/tuple with its existing wording at `:425`/`:427`,
   and keep `test_dashboard_server.py:1235-1245` green.

**Files.** `workflows/slice-wave.workflow.js`, `scripts/run_state.py`,
`scripts/run_metrics.py`, `scripts/dashboard_server.py`,
`scripts/test_slice_wave_contract.py`, `scripts/slice_wave_contract_base.py`,
`scripts/test_run_state.py`, `scripts/test_run_metrics.py`,
`scripts/test_dashboard_server.py`.

**Coverage watch.** `run_state.py` is at 100% against a 95% floor; `run_metrics.py` 98.6%
against 93%. Add the test with the change.

## s2 — Sweep the contracts and the inline twin to match shipped code  (risk_tier 1, deps: s1)

**Goal.** Every normative document and the inline-mode twin describe the classification
that s1 actually shipped.

**Why after s1, never parallel.** KG pattern `write-docs-from-shipped-code-never-from-the-plan`:
a documentation slice that transcribes planning artifacts produces a confidently wrong
document. s2 must read s1's merged diff.

**Why not tier 1 in spirit only.** `agents/slice-worker-fallback.md` is the behavioral spec
for the inline-mode executor, not prose. If it keeps the old classification, inline runs keep
the defect. Planner may argue for tier 2 on that ground.

**Scope.** `references/run-state-v2.md:101`; `skills/escalation-gate/SKILL.md:72-80`
("**Two** things that are deliberately NOT judgment triggers" -> three; "exactly five
triggers" wording); `agents/slice-worker-fallback.md:46` and `:146`;
`references/risk-tiers.md:88`; `references/migration-from-v1.md:64`. Plus a CHANGELOG entry.

## Open design questions for the council

**Q1 — one new trigger or two?** Three meanings are conflated today (conventions.md).
Case 2 (caught exception) and case 3 (slice returned nothing) are both machine failures but
differ in what the human can do. One value covering both, or two?

**Q2 — the name.** Must not contain, nor be contained by, any existing trigger name
(`run_metrics.py:1692` substring-matches). Candidates: `internal-error`, `slice-lost`,
`workflow-fault`, `unclassified-failure`. `internal-error` collides with nothing.

**Q3 — is stage attribution (s1 scope item 4) separable, or does the crash context stay a
bare exception string in this run?** It is the difference between "something threw" and
"stageVerify threw while dispatching role=verify".

**Q4 — does narrowing `budget-exhausted` while leaving it with no mechanical answer path
(the human's "raise the cap" answer changes nothing) leave the run half-done?** The request
puts that OUT of scope as a capability addition. Is that the right line?
