---
schema_version: 2
run_id: 20260826-crash-classification
generated: 2026-08-26T21:05:00Z
integration_branch: spec-loop-run/20260826-crash-classification
base_branch: main
base_sha: 8d0e2c1
merge_mode: single-branch
integration_gate: green-after-remediation
slice_counts: { complete: 3, split: 0, remediation: 1 }
gap_counts: { known_gaps: 15, deferred: 10, open_findings: 7 }
publish: pending
knowledge_graph: not recorded
---

# Runbook — 20260826-crash-classification

> `knowledge_graph` is `not recorded` rather than `disabled`: no `events.jsonl` event and no
> decision line in this run's artifacts mentions a knowledge-graph write either way.
> `generated` is the time this document was written; the run's own last recorded event is
> `2026-08-27T00:46:43Z`.
>
> `gap_counts` are defined so they can be checked: `known_gaps: 15` is the count of named items
> in sections 3.1, 3.3, 3.4 and 3.5 (1 + 7 + 5 + 2); `deferred: 10` is the number of `deferred`
> events in `events.jsonl`; `open_findings: 7` is the 3 P2 + 4 P3 residual findings the Phase 5
> attempt-2 reviewer raised, recorded as three deferral events and listed in section 3.2.

## Executive Readout

**What we set out to do.** The requester asserted that `budget-exhausted` was serving two
incompatible jobs — the loop's designed resource signal *and* the de facto label for every
unclassified crash — and asked for that split. The run gives machine failures their own
escalation trigger `internal-error`, narrows `budget-exhausted` to the two structural guards
that genuinely mean "out of resource", and makes a crash record diagnostic by leading with the
real exception text and the last stage/role dispatched.

**What shipped.** Three slices, all complete, on `spec-loop-run/20260826-crash-classification`
(base `main` @ `8d0e2c1`, HEAD `c5fe56e`, 21 commits). `s1`: the `internal-error` trigger
across the workflow's JSON-schema enum and all three Python `ESCALATION_TRIGGERS` tuples, a
rewritten crash record with stage attribution and controller-shaped retry/skip/stop options,
the lost-slice record, and the three normative contracts (`references/run-state-v2.md`,
`skills/escalation-gate/SKILL.md`, `agents/slice-worker-fallback.md`) — the last three moved
into `s1` mid-wave by a recorded controller decision. `s2`: the CHANGELOG entry carrying the
forward-compatibility data-loss warning, an independent staleness audit of the whole plugin
tree, plus a real correctness fix to the inline-mode behavioural spec that `s2`'s own reviewer
caught and the controller had previously mis-verified. `r1` (remediation slice): all nine
cross-slice integration findings (1 P1, 6 P2, 2 P3) plus a fifth cause-overclaim and three
follow-on inaccuracies the re-review found. No slice split.

**Integration status.** Phase 5 failed on attempt 1 (suite green at `8558a95`; the
integration-mode reviewer returned BLOCK with 1 P1, 6 P2, 2 P3) and passed on attempt 2 at
`c5fe56e` with `APPROVE_WITH_FINDINGS` at review tier 3: all nine attempt-1 findings verdicted
RESOLVED by a fresh reviewer, plus 3 P2 and 4 P3 new findings, none at the P0/P1 blocking bar.
Suite green, controller-measured first-hand at `c5fe56e` in six separate invocations —
marketplace OK; 106 tests OK in `scripts/`; 1159 tests OK in `plugins/spec-loop/scripts/`;
coverage PASS, all floors met, TOTAL 96.7% (5972/6173) against a 90% floor; 48 Node
dashboard-asset tests, 48 pass, 0 fail; `claude plugin validate .` passed. Whole-run quality
gate: 206 checks, vacuous=FALSE, 8 failures — all of them the accepted pre-existing set (7
whole-file `class_lines` plus `parameter_count` on `dispatch()`); no threshold was weakened and
nothing was added to `coverage_omit.txt`. One remediation slice. Nothing is pushed or merged:
publish state is **pending**.

**Gaps you should know about.**
- **Verifiability ceiling — read this before trusting any behavioural claim.** `plugin_root`
  was pinned for every wave to the frozen installed cache
  `~/.claude/plugins/cache/spec-loop/spec-loop/2.2.0/`, verified byte-identical to the pre-run
  repo by `diff -rq`. **Nothing this run shipped in `slice-wave.workflow.js` has ever been
  executed by anything.** The JS side is covered only by source-text contract tests, which
  prove a construct is PRESENT, not that it BEHAVES. The Python side (the three tuples,
  fail-closed validation, metrics bucketing, dashboard parsing) genuinely executes under
  `unittest` and is real evidence.
- **This run must not be sold as shortening runs.** It delivers honest, actionable,
  correctly-bucketed escalations and fast diagnosis. Wall-clock improvement is an UNPROVEN
  HYPOTHESIS, to be tested against the next run's artifacts. The requester's premise was that
  mislabelling made runs long; the controller measured the prior run (`20260825-scope-ceiling`)
  and found the human answered both crash escalations in 1.1 and 0.6 minutes, with true human
  answer latency ~35–39 min across a 568-minute active span (~6%). The cost was misdirected
  CONTROLLER DIAGNOSIS, not human idle time.
- **The intake council ran at 1 of 3 lanes.** Only `skeptic` delivered. `plan-critic` and
  `guardian` each went idle twice with no output and were stopped; the controller executed
  their mandates itself. That is a weaker guarantee than an independent panel. This run did NOT
  have a full intake council.
- Seven residual findings were deferred at the terminal gate (3 P2, 4 P3), none blocking.
- A plugin **downgrade** to 2.2.0 DISCARDS an affected run directory entirely: `persist_slice`
  raises `SidecarInvalid` and writes nothing — no sidecar, no events, no report. Repo and
  installed plugin must be updated together.
- The quality gate counts control-flow keywords inside string literals, leaving `runSliceError`
  at cognitive 14 against a threshold of 15 on a function whose real branching is one ternary.
- Stage attribution remains last-writer-wins under concurrency. The overclaiming CLAIM was
  corrected; the mechanism was not changed.
- `agents/slice-worker-fallback.md` Pipeline step 3 still diverges from the shipped workflow on
  WHICH non-budget trigger a blocked task takes.

**Key decisions made autonomously.**
- Every agent this run was dispatched through the Workflow runtime, never the Agent tool:
  Agent-tool teammate delivery was broken this session (6 of 7 dispatches returned no output,
  including a control agent whose entire prompt was "reply with exactly SMOKE-OK, do not use
  any tools"), while a Workflow probe returned both a schema-forced object and a plain string
  correctly in 15.6s with 0 errors.
- Intake council ran at 1 of 3 lanes; the controller performed the risk lane and the design
  positions itself, and recorded that as a run limitation rather than papering over it.
- `s1`'s scope was widened mid-wave to include the three normative contracts, and those files
  were moved from `s2` into `s1`'s declared file list so no false over-scope flag was raised.
- `s1`'s quality-gate escalation was resolved by the controller on prior-run precedent instead
  of being surfaced to the human: seven `class_lines` findings and one `parameter_count`
  finding accepted as pre-existing (verified against base `8d0e2c1`), three NEW `nesting_depth`
  violations treated as a genuine block and fixed.
- `s2`'s self-reported DONE was NOT accepted: its own reviewer found 2 of 3 deliverables unmet
  and a real correctness defect the controller had itself mis-verified; a targeted fix round
  followed before merge.
- Phase 5 was remediated with a targeted fix plus an independent re-reviewer instead of the
  contract's prescribed remediation slice-wave of one — a deliberate, recorded deviation, taken
  because the terminal verification bar is unchanged (Phase 5 re-runs from step 1 with a fresh
  suite, a fresh whole-run gate and a fresh integration reviewer).
- Human-answered escalations: none during execution. The only escalation opened
  (`s1:quality-gate-block`) was controller-resolved by precedent. The human answered three
  intake questions before any code was written: A1 — stop and fix the agent-delivery harness
  first (no code changed, no branch created at that point); A2 — exactly ONE new trigger value,
  named `internal-error`, covering both machine-failure shapes; A3 — scope is classification
  plus stage attribution, automatic retry stays OUT, and the run must not be sold as shortening
  runs.

**How to verify / operate.** Run the suite as SIX separate invocations from the repo root —
never as one command, because a monolithic call near the 10-minute tool ceiling gets killed and
reads as a false red: `python3 scripts/validate_marketplace.py .` ;
`python3 -m unittest discover -s scripts -p "test_*.py"` ;
`python3 -m unittest discover -s plugins/spec-loop/scripts -p "test_*.py"` ;
`python3 scripts/measure_coverage.py` ;
`node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs` ;
`claude plugin validate .`. Then re-prove backward compatibility with the executable
three-command baseline, run against the REPO copy of the scripts (with
`P=~/.claude/plugins/cache/spec-loop/spec-loop/2.2.0/scripts` only as the script source for
the frozen comparison): `python3 $P/dag.py validate --run-dir
docs/spec-loop/20260825-scope-ceiling` must print `{"ok": true, "errors": []}`;
`python3 $P/run_state.py open-escalations --run-dir docs/spec-loop/20260825-scope-ceiling` must
print `[]`; `python3 $P/run_metrics.py compute docs/spec-loop/20260825-scope-ceiling` must show
`safety.escalations.by_trigger == {"budget-exhausted": 2, "council-objection": 2,
"material-assumption": 1, "quality-gate-block": 2}` byte-identical. To operate: the merged
`slice-wave.workflow.js` takes effect only after a plugin reinstall, so until you reinstall,
the new classification is not live; and once you do, run directories written by this version
are NOT readable by 2.2.0, so update the repo and the installed plugin together and never
downgrade with an affected run dir on disk. No CI thresholds, coverage floors or `CAPS` values
were changed by this run. This run wrote no `metrics.json`; the only recorded cost figures are
wave 1 round 2 at 16 agents, 1,016,853 subagent tokens, 3,725,869 ms.

---

## 1. What Was Built

| Slice | Goal (abbreviated) | Files / subsystems | Branch → head | Status |
|---|---|---|---|---|
| **s1** (tier 3) | Give machine failures their own trigger `internal-error`; narrow `budget-exhausted` to the agent cap and stage token floor; make the crash record diagnostic by naming the stage/role dispatched. Covers the JS schema enum, `runSliceError()`, the wave-entry lost-slice record, a `stage` field on slice state set from the `role` `dispatch()` already receives, all three Python `ESCALATION_TRIGGERS` tuples, the now-false catch-all comment, and tests for every one. **Amended mid-wave** to also update the three normative contracts. | `workflows/slice-wave.workflow.js`, `scripts/run_state.py`, `scripts/run_metrics.py`, `scripts/dashboard_server.py`, `scripts/slice_wave_contract_base.py`, `scripts/test_slice_wave_contract.py`, `scripts/test_run_state.py`, `scripts/test_run_metrics.py`, `scripts/test_dashboard_server.py`, `references/run-state-v2.md`, `skills/escalation-gate/SKILL.md`, `agents/slice-worker-fallback.md` — subsystems: wave-orchestration, run-state, metrics, dashboard, contract-tests | `spec-loop/20260826-crash-classification/s1` → `6ac5fe7` (merge `f9f2bd8`) | complete (sidecar `DONE`) |
| **s2** (tier 2) | The one deliverable s1 does not cover plus an INDEPENDENT staleness audit read against s1's merged diff: (1) the CHANGELOG entry carrying the forward-compat warning; (2) an audit that no stale claim about the old classification survives anywhere in `plugins/spec-loop/`, treating s1's own greps as claims to re-verify; (3) read-confirmation that `references/risk-tiers.md:88` and `references/migration-from-v1.md:64` need no edit. | `CHANGELOG.md`, `references/risk-tiers.md`, `references/migration-from-v1.md`, `agents/slice-worker-fallback.md`, `scripts/test_slice_wave_contract_scope.py` — subsystems: release-notes, contracts, consistency-audit | `spec-loop/20260826-crash-classification/s2` → `c190781` (merge `8558a95`) | complete (sidecar `DONE`) |
| **r1** (tier 3, **remediation slice**) | Phase-5 remediation: fix all nine cross-slice integration-review findings (1 P1, 6 P2, 2 P3), then the fifth overclaim instance and three follow-on inaccuracies the re-review found. | `workflows/slice-wave.workflow.js`, `agents/slice-worker-fallback.md`, `references/run-state-v2.md`, `skills/escalation-gate/SKILL.md`, `scripts/slice_wave_contract_base.py`, `scripts/test_slice_wave_contract_crash.py`, `scripts/test_run_metrics.py`, `CHANGELOG.md` — subsystems: wave-orchestration, contracts, inline-mode, contract-tests | `spec-loop/20260826-crash-classification/r1` → `3b0bbf8` (merge `c5fe56e`) | complete (sidecar `DONE`) |

Per-slice execution facts, from the sidecars (authoritative):

| Slice | Tasks | Council verdict | Review | Quality gate | Agents | Suite at head |
|---|---|---|---|---|---|---|
| s1 | 5 completed | OBJECT, 11 concerns, scope clean | 8 confirmed / 8 refuted / 0 evidence-failed / 3 fix rounds | FAIL — accepted, 8 pre-existing failures, 0 new | 19 | GREEN at `6ac5fe7`: 106 + 1153 tests OK, coverage 96.7%, 48 node, validate OK |
| s2 | 3 completed | ENDORSE_WITH_CONCERNS, 8 concerns, scope clean | 0 confirmed / 0 refuted / 1 fix round | PASS on its own diff (one whole-file `class_lines` finding, pre-existing) | 10 | GREEN at `c190781`: 106 + 1154 tests OK, coverage 96.7%, 48 node, validate OK |
| r1 | 2 completed | SKIPPED (remediation) | 9 confirmed / 0 refuted / 2 fix rounds | FAIL — accepted, same 8 pre-existing | 3 | GREEN at `3b0bbf8`: 106 + 1159 tests OK, coverage 96.7%, 48 node, validate OK |

Files changed across `8d0e2c1..c5fe56e`: 17 files, 583 insertions, 58 deletions. The only
change to `scripts/coverage_omit.txt` is a two-line renumbering of two pre-existing
`__main__` entry-shim entries (`run_metrics.py:2174-2175` → `:2175-2176`,
`run_state.py:1103-1104` → `:1104-1105`); nothing was added to it.

Wave structure: wave 1 = `s1` (workflow run `wf_be128c72-ab8`), wave 2 = `s2`
(`wf_063c09cb-d8a`), both recorded `collected` in `dag.json`; `r1` ran as wave 3 through
targeted single-agent Workflows and has no `wave-dispatched`/`wave-collected` event pair.
**`polish` was disabled for both waves**, so the simplifier could not reword the very
orchestration file under change and break the source-text contract assertions. Wave 1 also
never returned a usable sidecar: the wave returned `ESCALATED` with `tests: null` on both
rounds and the follow-up targeted rounds produce no sidecar, so the s1 and r1 sidecars are
**controller-authored with first-hand evidence** — every suite and gate figure in them was
measured by the controller directly, not copied from an agent's self-report.

## 2. Business Logic Now Enforced

Line citations below are as the artifacts record them; some line numbers moved between slices
(for example the crash record is cited as `:886` in the s1 sidecar and `:892` in the shipped
CHANGELOG), so treat them as the artifact's own anchors rather than a single snapshot.

**The trigger set.** `EscalationRecord.trigger` now has seven values. The enum lives at
`slice-wave.workflow.js:40` and is mirrored by the `ESCALATION_TRIGGERS` tuple in
`run_state.py`, `run_metrics.py` and `dashboard_server.py`. `budget-exhausted` was never
removed and its position in the enum is unchanged — only its meaning narrows — so the completed
run `20260825-scope-ceiling` keeps validating, keeps rendering, and keeps bucketing as itself
rather than degrading to `other`.

**`budget-exhausted` means a resource, and only a resource.** It is raised solely by the two
structural guards: the per-slice agent cap (`slice-wave.workflow.js:425`, `CAPS = { 1: 10, 2:
18, 3: 32 }`) and the per-stage token floor (`:427`, `BUDGET_STAGE_FLOOR = 60_000`). Both keep
their existing wording verbatim. It is not a judgment trigger and it is deliberately not
prompt-answerable.

**`internal-error` means the loop's own machinery failed, in exactly two shapes.** One value,
by human decision (A2), covering the catch-all in `runSliceError()` (`:892`) and the
wave-entry slice-returned-nothing record (`:919`). It is substring-safe in both directions
against all six pre-existing values, which `run_metrics.py:1692`'s legacy matcher requires. It
is NOT in `ANSWERABLE_TRIGGERS` and has no `answerFor` site — a crash's answer (retry this
slice / skip it / stop the run) is a CONTROLLER action, and there is nothing for an agent
prompt to apply. `ANSWERABLE_TRIGGERS` is unchanged at exactly the five judgment triggers.

**A crash record must claim only what the code can prove.** This is the run's signature rule
and its hardest-won one. The record leads with the real exception text, then the last
stage/role dispatched, then the fixed classification prose — in that guaranteed order, because
`render_escalation()` collapses the context through `_one_line(..., 400)` and only the first
400 characters reach `escalations.md`. It says "after" the stage, not "in" it, and states that
`state.stage` is the most recent dispatch, never cleared and overwritten by concurrent
fan-outs — "a starting point, not a culprit". On cause it asserts only that neither structural
guard *raised* its escalation record, and explicitly says the failure may be a loop or
agent-contract bug and may equally be a host- or agent-layer resource failure, with the
exception text as the evidence rather than the label. The title branches so that a
pre-dispatch crash reads "slice crashed before any agent was dispatched" instead of the
ungrammatical "crashed after before any agent was dispatched". All three options open with
"The CONTROLLER must act on this at the next dispatch", and Skip and Stop each state that
nothing in the loop enforces them.

**Five categorical cause overclaims are now banned by name.** A *categorical cause overclaim*
is a statement about a failure's cause that the code cannot prove. The run found five, each
discovered only after the previous one was fixed:

1. the crash context — "This is a loop or agent-contract bug, NOT a cap or budget limit";
2. `references/run-state-v2.md`, carrying the same categorical cause claim (disclosed by the
   fixer, not in the original findings);
3. the lost-slice record — "Not a resource limit.";
4. the CHANGELOG — "a resource request for a failure that no resource would have prevented",
   asserted of EVERY uncaught error and contradicting the same entry's own text nineteen lines
   above;
5. the lost-slice record again — "Neither structural guard FIRED", the same word already
   corrected in its sibling eleven lines up, and the remediation had additionally edited
   `CHANGELOG.md:25` to describe that record as already correct, replacing an accurate line
   with an inaccurate one.

All five are pinned as forbidden-phrase constants in `slice_wave_contract_base.py`:
`CRASH_STAGE_OVERCLAIM`, `CRASH_GUARD_ORIGIN_OVERCLAIM`, `CRASH_CAUSE_OVERCLAIM`,
`CRASH_BUDGET_DENIAL_OVERCLAIM`, `GUARD_FIRED_OVERCLAIM` — the last banned across the WHOLE
workflow source so it cannot return in either record. Two independent sweeps hunted a sixth
and found none: the r1 lane ran the pattern's tells
(`fired|came from|originat|would have prevented|no resource|rule out|never reaches|not a
budget|caused by|the cause is`) across the whole plugin tree and `CHANGELOG.md`, read all 26
hits in context, and the Phase 5 attempt-2 reviewer independently read for the *pattern*
rather than the five pinned phrases across every changed string literal, all four normative
docs and the whole Unreleased CHANGELOG block. **That this class recurred five times, twice in
the same record, is the run's strongest evidence that the original premise was right: the
codebase's habit was to assert a cause it could not prove.**

**The inline-mode twin must classify identically.** `agents/slice-worker-fallback.md` is the
behavioural spec for inline mode, not prose. Two real defects in it were fixed: `:46` claimed
"Hitting a cap or a bound with work outstanding is a `budget-exhausted` escalation" while the
shipped workflow classifies a spent replan as `council-objection` (`:548`/`:558`), a spent task
retry as `ambiguity` (`:636`), and findings surviving fix rounds as
`review-block`/`quality-gate-block` (`:779`) — and `:157` told the twin that "a stage that died
with no result is `internal-error`" when the workflow classifies a planner no-result (`:481`)
and a task no-result (`:636` via `taskBlockReason` `:608`) as `ambiguity`. That second one was
the P1: `ambiguity` has an `answerFor` site (`:316`) and `internal-error` deliberately has
none, so the divergence converted an ANSWERABLE escalation into an unanswerable one.

**Cross-file enum agreement is now pinned by an executed test.** Before `r1`, nothing in the
suite asserted that the trigger enum's homes agreed; an edit touching one home would have
stayed fully green while `run_state.py`'s fail-closed validator silently discarded an entire
sidecar, its events and its report. `TestTheTriggerEnumAgreesAcrossAllFiveHomes` asserts the
three Python tuples are identical and that the workflow's enum source line carries exactly
those values in order, anchored so a moved line fails loudly. (Its name overstates its reach —
see §6.)

**Blast radius, verified from code and deliberately not "fixed".** A crash's blast radius is
already exactly one slice: `runSlice()` (`:859-866`) catches and returns an ESCALATED result
rather than rethrowing, so `parallel()` (`:871`) and every sibling slice are unaffected. Sibling
isolation already held and was left alone.

## 3. Gaps, Deferrals and Limitations

Each item: **what** · **why deferred** · **reversibility**.

### 3.1 Verifiability ceiling (the one that outranks the rest)

**What.** `plugin_root` was pinned for every wave to the installed cache
`~/.claude/plugins/cache/spec-loop/spec-loop/2.2.0/`, verified byte-identical to the pre-run
repo by `diff -rq` (only `.in_use` and `__pycache__` differ). Nothing this run shipped in
`slice-wave.workflow.js` has been executed by anything — not by the waves, not by the suite.
Its coverage is source-text contract assertions, which prove a construct is present and cannot
prove it behaves. **Why.** The alternative is a self-modifying loop across wave boundaries.
**Reversibility.** Resolves itself on the next run dispatched from an updated cache; that run
is the first real behavioural exercise of this code.

The one genuine behavioural verification the run does get: slice worktrees contain the modified
repo code and slices run the test suite there, so the modified **Python** really is executed by
`unittest`. It does not feed back into orchestration.

### 3.2 Residual findings deferred at the terminal gate (7: 3 P2, 4 P3)

Phase 5 attempt 2 returned `APPROVE_WITH_FINDINGS` with 3 P2 and 4 P3 new findings, none at or
above the P0/P1 blocking bar. Recorded as three deferral events:

- **INTG-1 (P2) — the truncation test re-implements the renderer it protects.**
  `test_slice_wave_contract_crash.py:186` does `" ".join(filled.split())[:CRASH_CONTEXT_RENDER_LIMIT - 1]`,
  a local copy of `run_state.py:188-190`, with the limit duplicated as
  `CRASH_CONTEXT_RENDER_LIMIT = 400` in `slice_wave_contract_base.py:151` against a bare `400`
  literal at `run_state.py:467`. If the production limit or the collapsing changes, the test
  keeps passing while the stage attribution silently vanishes from `escalations.md` again — the
  exact regression it exists to prevent. **Why deferred.** Attempt 2 passed at the P0/P1 bar
  and the run had already deviated once from the remediation contract; polishing P2s at the
  terminal gate is unbounded. **Reversibility.** Trivial — the module already imports
  `run_state`; assert against `run_state.render_escalation()` output and name the 400.
- **INTG-2 (P2) — the enum-agreement guard covers four homes, not the five its name claims.**
  `slice_wave_contract_base.py:93` says five homes then enumerates four;
  `TestTheTriggerEnumAgreesAcrossAllFiveHomes` asserts across those four code homes. The
  unpinned fifth is the PROSE enumeration in the docs, including
  `agents/slice-worker-fallback.md:152-153` — the inline twin spec, which is exactly where this
  run found its P1 divergence. This is the run's own defect class one level up: a name and a
  comment claiming more coverage than exists. **Reversibility.** Trivial — rename to four
  homes and record the prose as deliberately unpinned, or add a doc-prose assertion.
- **INTG-3 (P2) and INTG-4/5/6/7 (P3) — residual unconditional claims about the lost-slice
  record shape.** The lost-slice record differs from the caught-exception record, and prose
  describing `internal-error` generically keeps overstating what it carries. `CHANGELOG.md:31`
  asserts the record carries three controller-named options, but the lost-slice record offers
  only "Re-run the wave to retry this slice". `escalation-gate/SKILL.md:78` says the
  lost-slice record states its own missing diagnostics, which it does not, and implies
  skip/stop options it does not offer. `slice-worker-fallback.md:99` has a broken
  cross-reference (the no-result rule lives in Escalations, not Pipeline step 4) and `:98`
  describes behaviour for a real `BLOCKED` the workflow does not have. `test_run_state.py:200`
  cites a line number this same diff invalidated — the INT-9 defect class recurring in a file
  the remediation sweep did not re-check (the fail-closed check moved `:204` to `:205` when the
  `internal-error` continuation line landed).

### 3.3 Earlier deferrals (7 more deferral events)

- **A plugin downgrade to 2.2.0 DISCARDS an affected run dir entirely.** `persist_slice`
  (`run_state.py:967-975`) validates the whole `SliceResult` before writing anything and raises
  `SidecarInvalid` on an unrecognised trigger — so under 2.2.0 an `internal-error` slice
  produces **no sidecar, no events and no report at all**, not a wrongly-labelled record. The
  slice reports ESCALATED with nothing on disk saying why, and the diagnostic this run exists
  to deliver is lost entirely. Re-running the slice under 2.2.0 will not recover the record,
  because it was never written. **Why deferred.** Closing it needed only a release note, which
  is what `s2` shipped; the code-level fix (a downgrade path) is a capability addition.
  **Reversibility.** Trivial as documentation; the data loss itself is not reversible after the
  fact. `schema_version` stays `2` by human decision — the change is additive to an enum.
- **The quality gate counts control-flow keywords inside string literals.** The implementer's
  first wording for the crash options contained three occurrences of "when" inside string
  literals, and `quality_gate.py`'s builtin JS heuristic counted them as branches, pushing
  `runSliceError` to cyclomatic 12 (threshold 10) and cognitive 22 (threshold 15) — on a
  function whose real branching is one ternary. After rewording, it measures cyclomatic 8,
  cognitive 14, method_lines 12, nesting 1. **Cognitive 14 against a threshold of 15 is thin
  headroom, and it is thin only because prose counts as control flow**: a future editor adding
  one `if` or `for` to any user-facing string in that function will trip the gate on code whose
  real complexity did not change, and the natural "fix" would be to degrade the operator-facing
  message. **Why deferred.** This run changes classification and reporting, not the gate.
  **Reversibility.** Trivial — strip string literals before the builtin keyword scan, or exempt
  string contents from the heuristics.
- **Stage attribution is last-writer-wins under concurrency — the CLAIM was corrected, not the
  mechanism.** `state.stage` is a single field shared by concurrent dispatches (the critic panel
  via `parallel()` `:580-582`; reviewer lanes alongside the gate `:694-699`), so the named stage
  may not be the one that threw, and the wave-entry lost-slice record carries no stage at all.
  **Why deferred.** The run's scope ceiling forbids redesigning stage tracking. **Reversibility.**
  The correction is safe as-is: the record now says it reports the most recent dispatch, both doc
  sites match, and because the exception text travels with the record a mislabel is
  self-correcting rather than silent.
- **`slice-worker-fallback.md` Pipeline step 3 still diverges on WHICH non-budget trigger
  applies.** `:98` tells the inline twin to escalate an exhausted per-task retry as
  "material-assumption or review-block as fits", while the shipped workflow classifies exactly
  that as `ambiguity` (`slice-wave.workflow.js:636`). **Why deferred.** Outside the fixer's
  brief; fixing it would have been a silent rewrite of a pipeline step. **Consequence is
  bounded:** an inline run raises a judgment trigger either way and all three are
  human-answerable, so nothing is mislabelled as a resource problem. **Reversibility.** Trivial.
- **Two crashes in one slice collide on one escalation id.** With crashes on their own trigger,
  two distinct crashes in the same slice share `${slice.id}:internal-error`, because `esc()`
  (`:255`) emits no round suffix despite the contract documenting `<slice-id>:<trigger>[:<round>]`;
  the second record merges into the first in `run_metrics.merge_escalation_records` and in the
  rendered `escalations.md`, so one of two diagnoses is lost. **Why deferred (do not build).**
  Strictly no worse than before — all three meanings previously collided on `:budget-exhausted`
  — and the scope ceiling explicitly forbids touching the `esc()` id scheme because `answerFor`
  matching (`:539`) depends on it. **Reversibility.** Requires an id-scheme change.
- **The substring-safety test pins the naming constraint but never exercises the matcher.**
  `test_internal_error_is_substring_safe_against_every_other_trigger`
  (`test_run_metrics.py:465-471`) asserts containment against the Python literal
  `"internal-error"` and never runs `_legacy_match_triggers` (`run_metrics.py:1693`), the code
  the constraint exists to protect; it would stay green if that matcher's semantics changed.
  **Reversibility.** Trivial — feed v1 prose containing `internal-error` through the legacy path.
- **`test_dashboard_server.py` is now in a knowingly mixed indentation state.** The reindent
  that cleared the new `nesting_depth` violations left immediately-adjacent siblings
  (`:1246-1249` at column 36, `:1267` at column 55) on the old paren-aligned style; they escape
  the gate only because they are not in the diff, and the gate ruling correctly barred touching
  them. Recorded so the next editor meets a deliberate state, not a surprise.

### 3.4 Scope-ceiling items that remain genuine gaps

- **A `budget-exhausted` answer still has no mechanical effect.** The human says "raise the cap"
  and nothing raises it. Pre-existing, unchanged by this run, and a capability addition rather
  than a classification fix: it needs a controller-side path to thread a raised cap into a
  re-dispatch, touching `commands/spec-loop.md` and the wave args contract. Explicitly deferred.
- **No automatic retry of a crashed stage.** Ruled OUT by the scope ceiling and confirmed by the
  human (A3). The `skeptic` lane considered it and explicitly declined to escalate for it,
  calling classification "a real, independently justified fix (honesty, correct metrics
  bucketing, `escalation-gate` contract integrity) even if it turns out to save 10 minutes
  rather than 160."
- **The duplicate-section bug in rendered `escalations.md` is untouched**, deferred by run
  `20260825-scope-ceiling` with its own record. It shaped this run's mechanics twice: wave 1
  round 2 was deliberately not re-persisted, and the `s1` escalation record was deliberately
  omitted from the converged sidecar, both to avoid re-emitting `escalation-opened` for an
  already-answered id.
- **A crash always escalates the human, as scoped.** Recorded by the `skeptic` lane as a named
  design choice, not a gap.
- **A truncation limit remains, and the CHANGELOG states it honestly.** The guaranteed ordering
  is not a promise that both diagnostics fit: measured against the longest stage text, an
  exception message past ~286 characters pushes the stage attribution out of the rendered
  context entirely, and its "starting point, not a culprit" caveat drops at ~200. The Phase 5
  attempt-2 reviewer independently re-measured those thresholds as exactly 287 and 201.

### 3.5 Process limitations of this run

- **The intake council ran at 1 of 3 lanes.** `skeptic` delivered a full premise verdict
  (ENDORSE_WITH_CONCERNS, no safety flag) whose two recommendations became shared constraints 7
  and 8. `plan-critic` was dispatched 19:26Z, went idle 19:35:32Z with no output, was re-prompted
  for text-only delivery, went idle again 19:37:29Z, and was stopped at 19:38Z. `guardian` was
  dispatched 19:26Z, idle 19:35:55Z, re-prompted, idle again, stopped 19:40Z. The controller
  executed the risk mandate itself (R1–R6, with commands run and output read) and formed its own
  design positions. **This is a weaker guarantee than an independent panel, and this run must not
  be described as having had a full intake council.**
- **Root cause of that, and of the run's dispatch discipline.** Agent-tool teammate delivery was
  broken this session. The artifacts record two counts at two points: `answers-recorded.md` A1
  records 5 of 6 dispatches returning no output in the launching session (both `Explore` agents,
  `plan-critic`, `guardian`, and a trivial control agent whose entire prompt was "reply with
  exactly SMOKE-OK, do not use any tools"); the later run-level decision event records 6 of 7 for
  the session. A Workflow probe (`wf_3f177193-fe1`) in the same session dispatched two agents —
  one schema-forced, one plain — and both returned correctly in 15.6s with 0 errors and 0 empty
  results, proving the failure is specific to the Agent-tool mailbox path and not to subagents
  generally. Consequence: every agent this run, including the Phase 5 cross-slice reviewer and
  this runbook writer, was routed through the Workflow runtime.

## 4. Requirement Traceability — and WHICH kind of evidence backs each

Two kinds of evidence exist in this run, and they are not interchangeable:

- **EXECUTED** — real test execution against code that actually runs (the Python side, under
  `unittest discover`).
- **SOURCE-TEXT ONLY** — a contract assertion that a construct is PRESENT in
  `slice-wave.workflow.js`. It cannot prove the construct behaves, because that file was never
  executed by this run.

| Requirement (from `request.md`) | Status | Evidence, and its kind |
|---|---|---|
| A crash produces an escalation whose trigger is NOT `budget-exhausted` | delivered | **SOURCE-TEXT ONLY** — `test_the_catch_all_emits_internal_error_not_budget_exhausted`; shipped at `slice-wave.workflow.js:892` (`esc(slice, 'internal-error', ...)`) |
| …whose context names the failing stage and the exception | delivered, with a named limit | **SOURCE-TEXT ONLY** — `test_the_crash_record_carries_the_real_exception_text`, `test_the_crash_record_names_the_last_dispatched_stage_without_overclaiming`, `test_the_real_exception_text_leads_the_context_not_the_boilerplate`, `test_the_stage_attribution_survives_the_400_char_context_render`. "Stage" is the last dispatched role, not a per-throw stage (§3.3); attribution can still be truncated past ~286 chars of exception text (§3.4) |
| …whose options are retry/skip/stop rather than raise-the-budget | delivered | **SOURCE-TEXT ONLY** — `test_the_options_are_controller_actions_not_resource_requests`, `test_every_option_says_the_controller_must_act_on_it`; Skip and Stop each state nothing in the loop enforces them |
| A genuine agent-cap or token-floor hit still produces `budget-exhausted`, wording unchanged | delivered | **SOURCE-TEXT ONLY** — `test_the_structural_guards_keep_their_budget_exhausted_wording`; guards at `:425`/`:427` untouched |
| Every consumer handles the new trigger; `run_metrics.py` buckets it separately in `escalations.by_trigger` | delivered | **EXECUTED** — `test_internal_error_buckets_as_itself_not_other` (not demoted to `other`), `test_escalation_trigger_accepts_internal_error` and `test_escalation_trigger_still_rejects_a_bogus_value` (both directions of the fail-closed validator), `test_internal_error_parses_out_of_an_escalation_id` and `test_a_record_trigger_of_internal_error_is_kept_as_itself` (dashboard) |
| The new trigger is pinned NON-answerable by a mirror of `test_slice_wave_contract.py:131`; `ANSWERABLE_TRIGGERS` unchanged | delivered | **MIXED** — `test_internal_error_is_not_injected_into_any_prompt` asserts `answerFor(slice, 'internal-error')` is absent from the workflow source (**SOURCE-TEXT ONLY**) and that `internal-error` is absent from `ANSWERABLE_TRIGGERS` (**EXECUTED** against the imported Python constant) |
| Substring-safe in both directions against all six existing triggers | delivered, weakly | **EXECUTED** but shallow — `test_internal_error_is_substring_safe_against_every_other_trigger` pins the naming constraint and never exercises `_legacy_match_triggers` (§3.3) |
| The full suite is green | delivered | **EXECUTED** — controller-measured first-hand at `c5fe56e`: marketplace OK; 106 tests OK; 1159 tests OK; coverage PASS TOTAL 96.7% (5972/6173); 48 node tests 48 pass 0 fail; `claude plugin validate .` passed |
| The previous run's artifacts still parse and render | delivered | **EXECUTED** — the three-command back-compat baseline, re-proven a third time against the fully remediated code: `dag.py validate` → `ok:true errors:[]`; `open-escalations` → `[]`; `by_trigger` byte-identical at `budget-exhausted 2, council-objection 2, material-assumption 1, quality-gate-block 2` |
| Carry the classification through `references/run-state-v2.md`, `skills/escalation-gate/SKILL.md`, `agents/slice-worker-fallback.md` | delivered | **REVIEW EVIDENCE** — all three edited in `s1` and corrected again in `r1` (INT-1, INT-5, INT-7, INT-8/9); the inline twin now classifies identically, with the reason stated. Doc prose is NOT pinned by any test (§3.2, INTG-2) |
| Confirm `references/risk-tiers.md:88` and `references/migration-from-v1.md:64` need no edit | delivered | **READ EVIDENCE, three independent readings** — accurate under the narrowed meaning; `risk-tiers.md:88`'s claim that the per-slice agent caps are the `budget-exhausted` record's "only source" was FALSE before this run and is TRUE after it — a doc claim this run repaired without editing it |
| Forward-compat warning in the CHANGELOG | delivered | **REVIEW EVIDENCE** — the Phase 5 reviewer confirmed the downgrade warning is factually accurate against `persist_slice`; its stated ~286/~200 truncation thresholds were independently re-measured as 287 and 201 |
| Cross-file enum agreement pinned | delivered, over-named | **EXECUTED** — `TestTheTriggerEnumAgreesAcrossAllFiveHomes` confirmed to actually execute (it matches `validate.yml`'s `test_*.py` discovery) and to actually fail on divergence in any of the four code homes; the fifth "home" (doc prose) is unpinned (§3.2) |
| Automatic retry of a crashed stage | **deferred** | Ruled OUT by the scope ceiling, by the `skeptic` lane's explicit decision not to escalate, and by human answer A3 |
| A controller-side path that makes a `budget-exhausted` answer actually raise CAPS | **deferred** | Recorded as an explicit deferral; a capability addition, not a classification fix |
| "Fixing the label will make runs shorter" | **NOT CLAIMED, by design** | Shared constraint 7. The mechanism is misdirected controller diagnosis, not human idle; wall-clock improvement is an unproven hypothesis for the next run |

## 5. Decisions Summary

**Human-answered, at intake, before any code was written** (`answers-recorded.md` — settled;
a future session must not re-ask them):

- **A1 — Execution: STOP and fix the harness first**, chosen over inline implementation without
  waves and over trying one wave and aborting. No code was changed and no branch was created at
  that point; the repo was untouched at `main` @ `8d0e2c1`.
- **A2 — Trigger shape: ONE new value, named `internal-error`**, covering both the caught
  exception and the slice-returned-nothing case. Rejected: two values (`internal-error` +
  `slice-lost`) as roughly double the surface for information the title already carries;
  `workflow-fault` as jargon that invites confusion with the Workflow tool.
- **A3 — Scope: classification plus stage attribution.** Auto-retry stays OUT and is a recorded
  deferral. Stage attribution is IN and load-bearing, on the corrected measurement. Accepted with
  the framing correction that this run must not be sold as shortening runs.

**Answered escalations during execution:** exactly one record exists, and no human answered it.

- **`s1:quality-gate-block` — "verification failed" — status ANSWERED, answered-at
  2026-08-26T21:13:42Z, CONTROLLER-RESOLVED BY PRECEDENT**, not surfaced to the human. The
  precedent is run `20260825-scope-ceiling`'s own `s1:quality-gate-block` human ruling ("ACCEPT
  AS PRE-EXISTING DEBT, no threshold weakened") and its runbook's carve-out ("a new
  function-level violation a slice's own code introduces remains a genuine block"). Controller
  measured the gate first-hand at slice head `99c45aa`: 124 checks, 11 failures, non-vacuous.
  Split by provenance against base `8d0e2c1`: seven `class_lines` findings ACCEPTED as
  pre-existing (every file was already 882–2804 lines at base; none is a new file); one
  `parameter_count` finding on `dispatch()` (5 > 4) ACCEPTED as pre-existing (the signature
  `dispatch(slice, state, role, prompt, opts)` is byte-identical at base and head); three
  `nesting_depth` findings (8/7/5 against a threshold of 3) NOT accepted and fixed, because both
  named functions have zero occurrences at base. No threshold was weakened and nothing was added
  to `coverage_omit.txt`. The same answer additionally mandated four honesty fixes — context
  ordering, the stage-attribution claim ("FIX THE CLAIM, NOT THE MECHANISM"), a missing
  `_enum_or_none` test, and one explicit non-fix (the "Skip this slice" option promises a
  controller action with no mechanism; `dag.py` has only pending/complete/split, so recording it
  honestly needs a new slice state the ceiling forbids).

**Material controller decisions (autonomous):**

1. **All agents through the Workflow runtime, never the Agent tool** (reversibility: trivial) —
   see §3.5 for the delivery-failure evidence and the `wf_3f177193-fe1` probe.
2. **Intake council ran at 1 of 3 lanes; the controller executed the missing mandates**
   (reversibility: n/a) — no safety flag, no majority OBJECT, so the outcome was
   proceed-with-concerns, recorded as a run limitation.
3. **`s1`'s wider cut accepted mid-wave** — the planner's Task 6 also updated the three normative
   contracts it had just shipped against, reading them from the shipped code. Accepted because it
   avoids both the stale-docs failure mode and a second wave; `dag.json` was amended to move those
   files from `s2` into `s1`'s declared list so the declaration matched reality and no false
   over-scope flag was raised.
4. **`risk-tiers.md:88` and `migration-from-v1.md:64` verified first-hand as needing no edit** —
   `conventions.md` had listed both as must-change; that inventory was over-broad.
5. **`s1:quality-gate-block` resolved on precedent rather than surfaced** (reversibility:
   moderate) — see above. Recorded in the same decision: the sidecar returned `tests: null`, which
   was FALSE; the controller had run all six segments green first-hand.
6. **Three quality-gate findings (`qg-0`, `qg-1`, `qg-2`) refuted by a batched finding-verifier**,
   each with quoted source as the refutation.
7. **`s1`'s converged sidecar is controller-authored, and deliberately omits the already-rendered
   escalation record** (reversibility: moderate) — the wave returned ESCALATED with `tests: null`
   on both rounds and the targeted rounds produce no sidecar. Carrying `s1:quality-gate-block` in
   `escalations[]` again would have re-emitted `escalation-opened` and reproduced the known
   duplicate-section render bug; its full acceptance rationale is preserved verbatim in
   `quality.detail`, so nothing is lost. Round 2's `events[]` ARE carried (minus
   `escalation-opened`) because round 2 was never persisted and those payloads are the only record
   of its sixteen dispatches.
8. **`s2`'s self-reported DONE was NOT accepted** (reversibility: high) — its own reviewer raised
   three findings that went through zero fix rounds because all three sat below the tier-2
   blocking bar, and two were substantive: a real correctness defect in a behavioural spec, and
   plan non-conformance (only Task 1 delivered; the audit that exists precisely to re-verify s1's
   self-reported clean greps was itself self-reported). `dag.json` was amended to add the two files
   the fix needed so the fix was in-scope by declaration.
9. **Phase 5 remediated by a targeted fix plus an independent re-reviewer** (reversibility: high) —
   a deliberate, recorded deviation from `references/phase-5-integration.md` section 3, which
   prescribes a remediation slice dispatched as a slice-wave of one.
10. **Both wave integration checks were GREEN by tree identity, not by re-running the suite** —
    exactly one slice merged in each wave and the integration branch's tree hash equalled that
    slice's sidecar `tests.tree_sha` byte for byte (`1d650656…` for wave 1, `65888d5d…` for wave
    2), so the first-hand green transfers and re-running would measure the same tree twice. Logged
    per the controller contract's tree-identity exception — the documented exception, not a
    skipped check.

**Controller errors, corrected by independent lanes — stated as errors.** Three times this run an
independent lane corrected a claim the controller had itself confirmed:

1. **Mis-verified `agents/slice-worker-fallback.md:46` as accurate.** The controller anchored on
   the word "cap" and ignored "bound". The shipped workflow classifies a spent replan as
   `council-objection`, a spent per-task retry as `ambiguity`, and findings surviving fix rounds as
   `review-block`/`quality-gate-block` — not `budget-exhausted`. The slice-planner made the same
   error and `s1` sharpened it by adding an authoritative cross-reference at `:150` pointing
   straight at the wrong paragraph. Only `s2`'s reviewer caught it.
2. **Reported the prior run's human-idle time as ~3.3h.** The first script read the LAST
   `escalation-answered` event per id instead of the first — a direct consequence of the known
   duplicate-render bug, which writes two such events per id. Measured first-open to FIRST answer,
   the human answered the `s2` crash in 1.1 min and the `s3` crash in 0.6 min; true human answer
   latency across the entire 568-minute run was ~35–39 min (intake 21.5 concurrent, s1 quality gate
   16.2, the two crashes 1.7 combined), about 6%. A roughly 50× error, corrected before it could
   drive scope. Any reasoning citing "161 minutes of human idle" is working from a corrected-away
   figure.
3. **Its own fix instruction broke the run's headline diagnostic.** Instructing the fixer to lead
   the crash context with the exception text protected the exception but pushed "Last stage/role
   dispatched before the failure" to offset ~545 of a ~913-char context, past `run_state.py:467`'s
   400-char render truncation — so the stage attribution never reached `escalations.md` while the
   title still asserted "slice crashed after `<stage>`", and the comment claimed the ordering
   prevented exactly this. Caught as INT-4 by the Phase 5 integration review, fixed so both
   diagnostics lead (attribution now ends at offset 68–154; independently re-measured by the
   re-review lane at 165, with its caveat at 251), and pinned by
   `test_the_stage_attribution_survives_the_400_char_context_render`.

**Recorded deviations from the run's own contracts:**

- Phase 5 remediation used a targeted fix plus an independent re-reviewer instead of a remediation
  slice-wave of one. The stated rationale: all nine findings were precise, localized and already
  carried written remedies from a high-effort reviewer (seven prose edits, one string reordering,
  one test addition); a full slice-wave would spend a planner, a council panel and six task
  implementers re-deriving a task list the reviewer had already written, at roughly 60 minutes and
  1M tokens versus about 15 minutes and 150k — measured against this run's own three prior targeted
  rounds, which converged 3 agents in 22 minutes where full rounds took 16 agents in 62. **The
  verification bar was unchanged**: Phase 5 re-runs from step 1 either way, so the remediation was
  re-judged by a fresh full suite, a fresh whole-run quality gate with an explicit vacuous check,
  and a fresh integration-mode reviewer over the cumulative diff — the same authoritative gate that
  had just returned BLOCK — with an independent re-reviewer lane additionally ahead of it.
- `polish` was disabled for both waves, so the simplifier could not reword the orchestration file
  under change and break the source-text contract assertions.
- The `s1` and `r1` sidecars were controller-authored with first-hand evidence, because the waves
  returned `tests: null` and targeted rounds produce no sidecar.
- The `s1` escalation record was deliberately omitted from the converged sidecar to avoid
  re-triggering the known duplicate-render bug, with its acceptance rationale preserved in
  `quality.detail`.

## 6. Integration Gate Result

**Suite command** (six segments, each its own invocation):

```
python3 scripts/validate_marketplace.py .
python3 -m unittest discover -s scripts -p "test_*.py"
python3 -m unittest discover -s plugins/spec-loop/scripts -p "test_*.py"
python3 scripts/measure_coverage.py
node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs
claude plugin validate .
```

**Attempt 1 — FAIL, on review, not on the suite.** At `8558a95`: suite GREEN (marketplace OK;
106 tests OK; 1154 tests OK; coverage PASS all floors met, TOTAL 96.7% (5972/6173); 48 node tests
48 pass 0 fail; plugin validate passed). Whole-run quality gate: 166 checks, vacuous=FALSE
(explicitly read per the contract), 8 failures, all the accepted pre-existing set. Cross-slice
review: **BLOCK** — 1 P1, 6 P2, 2 P3 from a single integration-mode `pr-reviewer` over
`8d0e2c1..8558a95`, at review tier 3. The P1 was the inline-twin classification divergence
(INT-1); INT-4 was the controller's own truncation regression; INT-2 was the fourth cause
overclaim; INT-6 was the missing enum-agreement guard. The reviewer also confirmed the core held:
all five homes agree, `budget-exhausted` survives everywhere, `state.stage` never leaks into the
sidecar, and the CHANGELOG's downgrade warning is factually accurate against `persist_slice`.

**Attempt 2 — PASS.** At `c5fe56e`: suite GREEN (marketplace OK; 106 tests OK; **1159 tests OK**;
coverage PASS all floors met, TOTAL 96.7% (5972/6173); 48 node tests 48 pass 0 fail; plugin
validate passed). Whole-run quality gate: **206 checks, vacuous=FALSE, 8 failures — all the
accepted pre-existing set** (7 whole-file `class_lines` + `parameter_count` on `dispatch()`).
Historical-run back-compat re-proven a third time against the fully remediated code:
`dag.py validate` → `ok:true errors:[]`; `by_trigger` byte-identical at `budget-exhausted 2,
council-objection 2, material-assumption 1, quality-gate-block 2`. Cross-slice review:
**APPROVE_WITH_FINDINGS @ tier 3** — all NINE attempt-1 findings verdicted RESOLVED against the
shipped tree by a fresh integration-mode reviewer, plus 3 P2 and 4 P3 new findings, none at or
above the P0/P1 blocking bar.

Three things the attempt-2 reviewer re-measured independently rather than trusting the
remediation: it reconstructed the shipped context template from source and applied
`run_state._one_line(..., 400)` semantics (stage attribution ends at offset 165, its caveat at 251,
worst-case stage text, both inside the 400-char render; the CHANGELOG's stated ~286/~200
thresholds measured exactly 287 and 201); it confirmed the new enum-agreement test actually
executes under `validate.yml`'s `test_*.py` discovery and actually fails on divergence in any of
the four code homes; and it ran an independent sixth-overclaim sweep by pattern rather than by the
five pinned phrases, across every changed string literal, all four normative docs and the whole
Unreleased CHANGELOG block, finding none — including checking "it died outside `runSlice`'s
try/catch" against `runStages`' return paths for the one way it could be false. It also confirmed
the converse failure mode is absent: the record is not over-hedged, and leads with the exception
text, the stage, and three labelled controller options.

`integration_gate: green-after-remediation`. Both wave-level integration checks were GREEN by
tree identity (§5, decision 10).

## 7. How to Verify and Operate

**Verify the code.** Run the six segments above from the repo root, each as its own call. Never
run them as one command: a monolithic invocation near the 10-minute tool ceiling gets killed and
reads as a false red. Expected at `c5fe56e`: `OK: marketplace and all plugins valid (.)`; `Ran 106
tests` → `OK`; `Ran 1159 tests` → `OK`; `PASS: all per-file and total floors met`, TOTAL 96.7%
(5972/6173) against a 90% total floor; 48 node tests, 48 pass, 0 fail; `Validation passed`. Segment
2 prints CHANGELOG-rolling chatter (`rolled CHANGELOG [Unreleased] -> [1.1.0]`) — that is
release-tooling fixture noise against a temp dir, not a real edit; the tree stays clean. Do not
"fix" it.

**Verify backward compatibility** with the executable three-command baseline, run against the REPO
copy of the scripts (running them against the frozen cache makes the check vacuous):

```
P=~/.claude/plugins/cache/spec-loop/spec-loop/2.2.0/scripts
python3 $P/dag.py validate --run-dir docs/spec-loop/20260825-scope-ceiling
  -> {"ok": true, "errors": []}
python3 $P/run_state.py open-escalations --run-dir docs/spec-loop/20260825-scope-ceiling
  -> []
python3 $P/run_metrics.py compute docs/spec-loop/20260825-scope-ceiling
  -> safety.escalations.by_trigger == {"budget-exhausted": 2, "council-objection": 2,
     "material-assumption": 1, "quality-gate-block": 2}
```

The `by_trigger` map is the sharpest check: it proves `budget-exhausted` still buckets as itself
rather than being silently demoted to `"other"` by `_normalize_trigger`, and that no historical
record got re-classified. What would break it: removing `budget-exhausted` from any tuple or enum,
or renaming it. **Never do either.**

**Verify the quality gate honestly.** Read `vacuous` explicitly. The expected result on this tree
is 8 failures, all pre-existing: seven whole-file `class_lines` (`dashboard_server.py` 1362,
`run_metrics.py` 1843, `run_state.py` 918, `test_dashboard_server.py` 2467, `test_run_metrics.py`
1348, `test_run_state.py` 1269, `slice-wave.workflow.js` 805, all against a 300 threshold) plus
`parameter_count` on `dispatch()` (5 vs 4). No threshold was weakened, and nothing was added to
`coverage_omit.txt` (its only diff is a two-line renumbering of existing `__main__` entry-shim
entries). `run_state.py` sits at 100.0% coverage against a 95% floor, so any uncovered line added
there drops it immediately.

**New gates and guards this run introduced** (no thresholds changed):

- `plugins/spec-loop/scripts/test_slice_wave_contract_crash.py` — a new contract module (+257
  lines) for the `internal-error` classification. Modules were split purely to keep each module's
  whole-file `class_lines` under 300; place any new contract test so both stay under it, and use
  named snippet constants in `slice_wave_contract_base.py` rather than inline literals in
  assertions.
- `TestTheTriggerEnumAgreesAcrossAllFiveHomes` — asserts the three Python `ESCALATION_TRIGGERS`
  tuples are identical and that the workflow's enum source line carries exactly those values in
  order, anchored so a moved line fails loudly. Confirmed to execute under `validate.yml`'s
  `test_*.py` discovery. Covers four code homes; doc prose is not pinned.
- Five forbidden-phrase constants in `slice_wave_contract_base.py` (`CRASH_STAGE_OVERCLAIM`,
  `CRASH_GUARD_ORIGIN_OVERCLAIM`, `CRASH_CAUSE_OVERCLAIM`, `CRASH_BUDGET_DENIAL_OVERCLAIM`,
  `GUARD_FIRED_OVERCLAIM`) plus `CRASH_CONTEXT_RENDER_LIMIT = 400`. `GUARD_FIRED_OVERCLAIM` is
  banned across the whole workflow source.

**Operate it.**

1. **Reinstall the plugin before expecting any of the JS behaviour.** The loop resolves its
   workflow from the installed plugin cache, so the merged `slice-wave.workflow.js` takes effect
   only after a reinstall. Until then the new classification is inert — and until then it has also
   never run anywhere.
2. **Update the repo and the installed plugin together, and do not downgrade.** `run_state.py`'s
   validator is fail-closed. A repo emitting `internal-error` against a 2.2.0 install produces a
   sidecar that `persist_slice` rejects before writing anything: no sidecar, no events, no report,
   and the slice reports ESCALATED with nothing on disk saying why. Run directories written by this
   version are not readable by 2.2.0, and re-running the slice under 2.2.0 will not recover the
   record because it was never written. `schema_version` stays `2` — the change is additive.
3. **When a crash escalation arrives, read the exception text first.** The record deliberately does
   not name a cause. The stage it names is the last dispatched role — a starting point, not a
   culprit — and under concurrent fan-out it may not be the stage that threw. If the exception
   message runs past roughly 286 characters, expect the stage attribution to be truncated out of
   the rendered `escalations.md` context; read the sidecar's record for the full text.
4. **`internal-error` is not answerable by an agent.** Retry / skip / stop are controller actions,
   and nothing in the loop enforces skip or stop. Answering the escalation changes nothing
   mechanically; the controller must act at the next dispatch.
5. **When editing `runSliceError`'s operator-facing strings, watch the gate.** Cognitive complexity
   sits at 14 against a threshold of 15, and it is that high only because the gate's builtin
   heuristic counts control-flow keywords inside string literals. Adding one `if` or `for` to a
   message will trip the gate on unchanged logic. Do not degrade the message to satisfy it — fix
   the heuristic, or accept and record the finding.

**Cost and metrics.** This run wrote no `metrics.json`, so no consolidated cost figures exist. What
is recorded: wave 1 round 2 — 16 agents, 1,016,853 subagent tokens, 3,725,869 ms; agents used per
sidecar — `s1` 19, `s2` 10, `r1` 3 (32 total). Baseline suite on the integration branch before any
change: green, six segments, ~55s, at tree `ac3c87ff47aae461144e75e5e49faf7c74d7b904`. Recorded
timestamps span the intake dispatch at 2026-08-26T19:26Z to the Phase 5 PASS at
2026-08-27T00:46:43Z — about 5h20m by subtraction of those two recorded times; the run's
`events.jsonl` entries carry no per-event timestamps, so a finer breakdown is not recorded.

**The one measurement to take next run.** Whether honest classification and stage attribution
actually shorten a run is untested. Test it against the next run's artifacts: measure crash-to-wave-
resume windows and controller diagnosis time, not human answer latency — the prior run's human
answered both crash escalations in about a minute, and the expensive part was working out what the
label had hidden.

---

_Artifacts: `docs/spec-loop/20260826-crash-classification/` — `dag.json`, `events.jsonl` (87
events), `escalations.md`, `decisions-log.md`, `request.md`, `conventions.md`,
`council-intake.md`, `controller-positions.md`, `answers-recorded.md`, `slice-{s1,s2,r1}-status.json`
(authoritative per slice), `slice-{s1,s2,r1}-report.md`, `plans/{s1,s2}.md`,
`packages/{s1-round1,s2-round1,integration-1,integration-2}.md`. Where an artifact records nothing,
this runbook says so rather than filling the gap._
