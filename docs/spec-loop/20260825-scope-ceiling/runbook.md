---
schema_version: 2
run_id: 20260825-scope-ceiling
generated: 2026-08-26T02:40:00Z
integration_branch: spec-loop-run/20260825-scope-ceiling
base_branch: main
base_sha: f3eac927f12dc68fb7750f8e7815e30457628051
merge_mode: single-branch
integration_gate: green-after-remediation
slice_counts: { complete: 4, split: 0, remediation: 0 }
gap_counts: { known_gaps: 6, deferred: 8, open_findings: 0 }
publish: pending
knowledge_graph: disabled
---

## Executive Readout

**What we set out to do.** The request asked spec-loop 2 to stop scaling only in the
direction of adding work: build a durable scope ceiling into the data model, give the
council's minimality lane real weight, add a non-blocking over-scope flag that records scope
creep without vetoing it, and log deferred scope so it is never silently re-admitted as a
later finding.

**What shipped.** s1: an optional, absent-tolerant run-level `scope_ceiling` in `dag.json`,
validated only when present and pinned to survive `mark`/`record-wave`/`ingest-split`.
s2: the Python-side durable record channels — fail-closed `critique.over_scope` type-checking
in `validate_sidecar`, unconditional rendering in `_summarize`, pinned council-verdict payload
facts, and null-honest `run_metrics` counters. s3: threading the run-level ceiling through the
wave packet and both `commands/spec-loop.md` call sites, the optional record-only
`over_scope` CRITIQUE field, the weighted scope lane promoted onto `plan-critic` with panel
size unchanged, one `deferred` event per defer-hinted concern emitted only when the plan
proceeds, advisory-only deferred-scope framing in the reviewer prompt, and — as a
human-approved scope increase this run logged against itself — two guards for unguarded
optional-field reads in `slice-wave.workflow.js` (`r.commits.head` and siblings; an
`answerFor` injection path for `quality-gate-block`). s4: docs and `CHANGELOG.md`
consolidation, explicitly framing what the mechanism does and does not claim. No slice split;
no remediation slice was needed.

**Integration status.** Suite GREEN on `spec-loop-run/20260825-scope-ceiling` at `2aba63f`
(all six segments run fresh: `validate_marketplace` OK, 106 + 1133 unittests OK, coverage PASS
on every per-file and total floor — `run_state.py` 100.0% 671/671 vs a 95 floor, TOTAL 96.7%
5972/6173 vs a 90 floor — 48/48 node, `claude plugin validate` OK). The whole-run quality gate
is FAIL-ACCEPTED and explicitly not vacuous: 7 findings, all whole-file `class_lines`, zero
function-level, every one of the seven already over 300 non-blank lines before this run
started, none of the three files this run created among them. Cross-slice integration review
(one `pr-reviewer`, integration mode, session model, high effort, over `f3eac92..HEAD`) found
no P0 and no P1 — nothing reached the Tier-3 blocking bar — so zero remediation slices were
opened. Its four findings (two actionable P2, one informational P2 needing no action, one P3)
were closed by a single inline controller-dispatched pass, commit `2aba63f`, touching only
comments, docstrings, docs and tests. Phase 5 ran twice (attempt 1 before the inline fix,
attempt 2 after); both PASS. Publish choice is **pending** — the human has not yet been asked.

**Gaps you should know about.**
- Only one of the five requirements reduces the effort of scope expansion: requirement 2's
  weighted scope lane on `plan-critic`. The ceiling, the `over_scope` record, the `deferred`
  channel, and the two counters build durable recording and non-re-admission of already-logged
  scope — they do not prevent scope from expanding in the first place.
- Nothing this run added to `slice-wave.workflow.js` has ever been executed. The loop resolves
  its workflow from the installed plugin cache, and even wave 4 ran a patched cache copy, not
  the merged file. Its "coverage" is a node parse plus source-text presence checks and a
  handful of extracted pure helpers run under real node — presence is not behaviour. First real
  execution is next run's job.
- Two more instances of the same unguarded-optional-read defect class survive by design in
  `slice-wave.workflow.js` — `plan.escalation.*` on the ESCALATE branch and `plan.split` on the
  SPLIT branch — found by the council, logged with file:line evidence, and deliberately not
  fixed because they fall outside the approved two-fix scope increase.
- The `over_scope: true` marker on a `deferred` event is member-level, not per-concern: a
  council member that flags the plan over-scope stamps every concern it raised, including
  unrelated ones. Found by the integration review; fixed by documenting the real semantics
  everywhere the marker is named plus a behavioural test pinning the propagation, not by a
  schema change.
- `run_metrics.py` double-counts deferrals by design today (`deferrals_total` vs
  `concerns_deferred`) and `by_member` attribution reads null because the workflow emits
  `panel[]`, not `member` — both deferred at intake, reporting-integrity issues only, nothing
  gates on either number.
- `escalations.md` carries stale bookkeeping: two `budget-exhausted` records (s2, s3) still
  render `status: OPEN` and two `quality-gate-block` records render `status: ANSWERED` with a
  blank answer field, artifacts of the same escalation id firing more than once during a wave.
  Every sidecar's own `escalations[]` array shows the true, single, resolved outcome, and
  `metrics.json`'s own `safety.escalations` block independently corroborates the real machine
  state — total 7, open 0, answered 7 — confirming the stale `OPEN` sections are a rendering
  artifact only.
- A `.spec-loop/quality-gate.json` overlay so the plugin's own scripts aren't held to a gate
  authored for consumer repos was deliberately deferred as a post-run follow-up, not built.

**Key decisions made autonomously.** (1) The weighted scope lane is a promoted mandate on the
existing `plan-critic`, not a 14th council member — a counted new member measurably changes
veto arithmetic at every tier. (2) Deferred scope is enforced by advisory prompt framing only;
`blocking()` is never filtered by it at any severity, closing an injection channel a mechanical
suppressor would have opened. (3) `over_scope` is a record parallel to `safety`, never a
`FINDING.category` value, so it can never reach the blocking bar through `blocking()`. (4) The
installed plugin cache was updated 2.0.0 → 2.1.0 before wave 1, rather than running four waves
on a stale cache with five known bugs. (5) The two workflow guard fixes in s3 were approved as
a deliberate, logged scope increase; two structurally identical defects found afterward were
deferred rather than fixed, as the mechanism's own first real test. Every escalation the loop
raised was answered by a human: the scope-lane shape, the requirement-5 enforcement mechanism,
the plugin-version update, two `quality-gate-block`s on pre-existing `class_lines` debt (s1,
s2), and one genuine `budget-exhausted` (s3, a `StructuredOutput` retry-cap exhaustion in the
final verify agent, distinct from two earlier crashes mislabelled as budget exhaustion by the
same catch-all).

**How to verify / operate.** Run, from the repo root, each as its own invocation: `python3
scripts/validate_marketplace.py .` ; `python3 -m unittest discover -s scripts -p test_*.py` ;
`python3 -m unittest discover -s plugins/spec-loop/scripts -p test_*.py` ; `python3
scripts/measure_coverage.py` ; `node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs`
; `claude plugin validate .`. `docs/spec-loop/20260825-scope-ceiling/metrics.json` records
`safety.deferrals_total` 8, `safety.over_scope_deferrals` 3, `safety.council.over_scope_flags`
null, `safety.council.concerns_deferred` 8, `safety.council.safety_objections` 1,
`safety.decisions_total` 17, `safety.autonomy_ratio` 0.7083, and `safety.escalations` total 7 /
open 0 / answered 7. Two nuances keep those figures honest rather than flattering: the 3
`over_scope_deferrals` are events the controller wrote by hand, so the
event→sidecar→log→metrics *channel* is exercised while the workflow's own `deferralEvents`
*producer* is not; and `over_scope_flags` reading null beside a populated sibling is this run's
single best piece of live null-honest evidence — a naive 0 there would have asserted "nothing
was over scope" when the truth is "nothing was measured," because the councils that produced
those verdicts ran on the pre-mechanism cache workflow and cannot emit the flag at all. To
exercise the new mechanism for real, reinstall the plugin from this branch/main after merge,
then run a slice whose plan or council verdict can plausibly trip the ceiling.

---

## 1. What Was Built

| Slice | Goal | Files / subsystems | Branch + head commit | Status |
|---|---|---|---|---|
| s1 | Optional, absent-tolerant run-level `scope_ceiling` in `dag.json`; `dag.py` validation only when present; `test_dag.py` covers the absent case, malformed-refusal, and preservation across mutators; `coverage_omit.txt` re-verified | `plugins/spec-loop/scripts/dag.py`, `test_dag.py`, `references/run-state-v2.md`, `scripts/coverage_omit.txt` — dag contract, coverage gate | `spec-loop/20260825-scope-ceiling/s1` @ `7932366` | complete |
| s2 | Durable Python-side record channels: `validate_sidecar` fail-closed type-check on `critique.over_scope`; unconditional `_summarize` rendering; pinned council-verdict payload facts; null-honest `run_metrics` counters (`safety.over_scope_deferrals` at run-wide `safety` top level, not under `council`) | `run_state.py`, `test_run_state.py`, `run_metrics.py`, `test_run_metrics.py`, `references/run-state-v2.md`, `scripts/coverage_omit.txt` — run-state persistence, metrics, coverage gate | `spec-loop/20260825-scope-ceiling/s2` @ `ece9588` | complete |
| s3 | Sole owner of `slice-wave.workflow.js` and the council contract: thread ceiling through `packet()`/`CTX` and both `commands/spec-loop.md` call sites; optional record-only `over_scope` CRITIQUE field; weighted scope lane on `plan-critic` (panel size unchanged); one `deferred` event per defer-hinted concern, emitted only when the plan proceeds; advisory-only deferred framing in reviewer prompts; `disposition_hint` fold\|defer router; doc updates across guardian/skeptic/pr-reviewer/slice-worker-fallback/risk-tiers/escalation-gate; plus the human-approved scope increase — guarding `r.commits.head` and sibling optional reads, and wiring `answerFor` for `quality-gate-block` | `workflows/slice-wave.workflow.js`, `commands/spec-loop.md`, `agents/plan-critic.md`, `agents/guardian.md`, `agents/skeptic.md`, `agents/pr-reviewer.md`, `agents/slice-worker-fallback.md`, `references/risk-tiers.md`, `skills/escalation-gate/SKILL.md` — wave pipeline, council contract, controller | `spec-loop/20260825-scope-ceiling/s3` @ `2fec12a` | complete |
| s4 | Docs/CHANGELOG consolidation; sole owner of `CHANGELOG.md` and both READMEs; reconciled and completed s3's existing CHANGELOG entry rather than duplicating it; states plainly that requirement 2 is the only effort-reducing lever and that the rest is recording, not prevention | `plugins/spec-loop/README.md`, `README.md`, `references/migration-from-v1.md`, `CHANGELOG.md` — docs | `spec-loop/20260825-scope-ceiling/s4` @ `2381156` | complete |

An additional controller-dispatched inline fix, commit `2aba63f`, closed the three actionable
findings from the Phase 5 cross-slice review. It is not a fifth slice — no remediation slice
was opened, because nothing reached the blocking bar — and it changed only comments,
docstrings, docs and tests.

No slice split. No remediation slice was opened at any point in this run.

## 2. Business Logic — Rules The Code Now Enforces

- `dag.json` may carry an optional run-level `scope_ceiling` (a flat string list mirroring the
  existing `shared_constraints[]` precedent). `dag.py` validates it only when present, mirroring
  the pre-existing `waves` field's absent-tolerant pattern; a `dag.json` without the key still
  validates and still marks. A malformed `scope_ceiling` entry, once present, makes the whole
  dag contract-invalid, and `_load_for_mutation` then refuses every subsequent mutation for that
  run — deliberate, matching the existing `waves` precedent.
- `critique.over_scope`, when present on a slice sidecar, is fail-closed type-checked by
  `validate_sidecar`: a non-object record, a non-boolean `flag`, or a non-string/non-null
  `reason` invalidates the whole sidecar and `persist_slice` writes nothing — a human ruling
  that strictness, not leniency, is the right default for a new optional field.
- `over_scope` is a top-level field on the CRITIQUE/council-verdict contract, structurally
  parallel to `safety`, and by binding shared-constraint it must never reach the verdict
  rollup, the split-suppression condition, the objection selection, or the replan veto
  (`slice-wave.workflow.js:401/403/405/408`). It is never a `FINDING.category` value, so
  `blocking()` — which filters on severity alone — can never turn a scope judgement into a
  block at any tier.
- The weighted scope lane is a promoted mandate on the existing `plan-critic` agent, not a new
  council member; council panel size is unchanged at every tier, so no veto threshold shifted.
- Deferred scope gets exactly one durable `deferred` event per defer-hinted concern, emitted
  only on the path where the plan proceeds to execution — never for a discarded SPLIT plan and
  never for a plan that stayed on an unresolved council objection. `append_event` does no
  de-duplication, so guarding the emission site, not filtering downstream, is what prevents
  re-inflation of `deferrals_total` on resume.
- Deferred scope reaches the reviewer only as quoted advisory prompt data, with explicit
  "file a genuinely blocking finding regardless" framing. `blocking()`'s output is untouched by
  any deferral list, at any severity — the human-ruled choice among three designs at intake,
  made specifically to close a prose-injection channel that a mechanical suppressor would have
  opened.
- Pre-existing whole-file `class_lines` violations are accepted as debt for every slice in this
  run under one human ruling recorded as shared constraint #13; a NEW function-level violation
  a slice's own code introduces is still a genuine block and must be fixed. s1 and s2 each
  cleared their self-introduced function-level findings via extraction while leaving
  pre-existing whole-file debt untouched; s3 decomposed `runSlice` (cyclomatic 116 / cognitive
  446 / method_lines 158 at slice base) below every threshold and split its own new 422-line
  test file into three modules, because the acceptance ruling only covers debt that predates
  the slice.

## 3. Gaps & Deferred

- **What:** Only requirement 2 (the weighted scope lane) reduces the effort of scope expansion.
  **Why deferred:** by design — requirements 1, 3, 4, and 5 were scoped as recording and
  non-re-admission mechanisms, not prevention, per the request's own framing.
  **Reversibility:** n/a — this is the shipped design, not an open item.
- **What:** Nothing added to `slice-wave.workflow.js` this run has ever executed; the loop runs
  off the installed plugin cache, and even wave 4 ran a patched cache copy, not the merged repo
  file. **Why deferred:** the run's own verifiability ceiling — the JS carries no coverage gate
  and this run's loop cannot exercise its own new mechanism. **Reversibility:** high — resolves
  automatically on the next plugin reinstall/run; flagged as the highest-value follow-up.
- **What:** Two more unguarded-optional-read defects of the same class survive in
  `slice-wave.workflow.js` — `plan.escalation.*` on ESCALATE, `plan.split` on SPLIT — found by
  the council, logged with file:line evidence. **Why deferred:** outside the human-approved
  two-fix scope increase; fixing them now would itself have been the scope creep this run
  exists to contain. **Reversibility:** trivial — both are one-line guards, same shape as the
  two that were fixed.
- **What:** The `over_scope: true` deferred-event marker is member-level, not per-concern — a
  member that flags the plan over-scope stamps every concern it raised, including unrelated
  ones. **Why deferred (as a design, not a defect):** the per-concern-schema alternative was
  considered and rejected as too large a contract change this late in the run; the chosen fix is
  documenting the real semantics plus a test pinning the actual propagation (commit `2aba63f`).
  **Reversibility:** moderate — a future per-concern schema remains possible without touching
  what already shipped.
- **What:** `run_metrics.py` double-counts deferrals (`safety.deferrals_total` vs
  `_council_stats.concerns_deferred`) and `by_member` attribution reads null because the
  workflow emits `panel[]`, not `member`. **Why deferred:** logged at intake as reporting-
  integrity issues only; nothing gates on either number, and deeper `run_metrics` restructuring
  sits outside this run's scope ceiling. **Reversibility:** high.
- **What:** The pre-existing `fixableByReplan` vs `fixable_by_replan` casing mismatch across the
  three council agent docs is left unfixed. **Why deferred:** fixing docs a slice merely happens
  to open is exactly the scope creep this run exists to contain; logged at intake.
  **Reversibility:** trivial.
- **What:** Dashboard surfacing of the new `over_scope` flag is not built (three server
  allowlists, two client allowlists would need changes). **Why deferred:** explicitly
  out-of-scope dashboard UI/UX work per the request; the existing `safety` flag is equally
  invisible on both dashboards today, so this is parity, not a regression. **Reversibility:**
  high.
- **What:** A `.spec-loop/quality-gate.json` overlay so the plugin's own scripts aren't held to
  a gate authored for consumer repos was deliberately not built. **Why deferred:** mid-run
  quality-gate config writes are guard-blocked by design, and this run's scope ceiling forbids
  quality-gate threshold/metric/blocking-semantics work. **Reversibility:** trivial — logged as
  a named post-run follow-up to build via `/spec-loop:quality-gate`.
- **What:** `escalations.md` contains two `budget-exhausted` records (s2, s3) still rendered as
  `status: OPEN` and two `quality-gate-block` records (s1, s2) rendered `status: ANSWERED` with
  a blank answer field. **Why flagged rather than resolved:** these are duplicate renderings of
  escalation ids that fired more than once within a wave; each slice's own sidecar
  `escalations[]` array (the authoritative source) shows a single, fully-answered record for
  each trigger, and `decisions-log.md` independently confirms every one was resolved.
  `metrics.json`'s own `safety.escalations` block independently corroborates the true machine
  state — total 7, open 0, answered 7 — confirming these stale `OPEN`/blank-answer sections are
  a rendering artifact only, not a real open escalation. This is a log-hygiene artifact of
  `escalations.md`, not an unresolved blocking issue in the run — but a reader of that file
  alone would see two open records and two answered-but-blank ones, so it is recorded here
  plainly. **Reversibility:** trivial (a rendering fix, not a data-loss issue).
- **What:** `metrics.json` (`docs/spec-loop/20260825-scope-ceiling/metrics.json`, computed with
  the repo copy of `run_metrics.py`, not the plugin cache) records `safety.deferrals_total` 8,
  `safety.over_scope_deferrals` 3, `safety.council.over_scope_flags` null,
  `safety.council.concerns_deferred` 8, `safety.council.safety_objections` 1,
  `safety.decisions_total` 17, `safety.autonomy_ratio` 0.7083, and `safety.escalations` total 7
  / open 0 / answered 7. **The nuance to hold onto:** the 3 `over_scope_deferrals` are events
  the controller wrote by hand while resolving review residuals, so the
  event→sidecar→log→metrics *channel* is exercised while the workflow's own `deferralEvents`
  *producer* is not; and `over_scope_flags` reading null beside a populated sibling is the
  single best piece of live evidence this run produced for its own null-honest design — a naive
  0 there would have asserted "nothing was over scope" when the truth is "nothing was
  measured," since the councils that produced those verdicts ran on the pre-mechanism cache
  workflow. **Reversibility:** n/a — this is measured fact, not an open item.

## 4. Requirement Traceability

| Requirement | Status | Evidence |
|---|---|---|
| 1. Scope ceiling in the data model, reaching planner/critic/reviewer/implementer via the packet | delivered | `dag.json.scope_ceiling` (optional, absent-tolerant), validated by `dag.py` (s1, commit `7932366`); threaded through `packet()`/`CTX` and both `commands/spec-loop.md` call sites (s3, commit `f2cc7ec`) |
| 2. Weighted scope lane in the council, scaling minimality pressure like risk pressure | delivered | Scope mandate promoted on `plan-critic`, panel size unchanged at every tier (s3, commit `328bb5d`); human-answered escalation `intake:council-objection-scope-lane` settled the promoted-role-vs-new-member choice |
| 3. Over-scope flag, structurally parallel to `safety.flag`, with different consequences | delivered | `critique.over_scope` optional CRITIQUE field, fail-closed type-check in `validate_sidecar` (s2, commit `9cb2903`); `{flag, reason}` pinned into the council-verdict payload (s3) |
| 4. The flag records; it does not veto — flagged work still ships | delivered | Shared constraint "RECORD-ONLY FLAG" binds `over_scope` out of the verdict rollup, split-suppression, objection selection, and replan veto (`slice-wave.workflow.js:401/403/405/408`); demonstrated live when s3's two approved workflow-guard fixes shipped as a logged, flagged scope increase rather than being dropped |
| 5. Deferred scope logged once, never re-implemented or re-admitted as a review finding | delivered | One `deferred` event per defer-hinted concern, emitted only on the plan-proceeds path (s3, `recordDeferrals()`, fixed to run before every Stage-C early return per review residual); advisory-only reviewer framing, never a findings filter (human-answered escalation `intake:council-objection-req5`); demonstrated live when the council's two newly-found workflow defects were logged and deliberately not built |

Requirement 2 is called out in §2 and the Executive Readout as the only one of the five that
reduces the *effort* of scope expansion; requirements 1, 3, 4, and 5 are recording and
non-re-admission mechanisms by design, and "delivered" above means the mechanism was built and
demonstrated as specified — not that scope expansion itself is now prevented.

## 5. Decisions Summary

Material autonomous decisions, from `decisions-log.md` and `events.jsonl`:

- The plugin cache pinned to the installed version, not the repo, because this run edits the
  loop's own machinery — pointing `plugin_root` at the repo mid-run would make the loop
  self-modifying across wave boundaries.
- Slices run serial (s1→s2→s3→s4), overriding a full-council recommendation to parallelise s1
  and s2.
- The scope ceiling is run-level only, mirroring `shared_constraints[]`; no per-slice
  `non_goals` field was added.
- `class_lines` is accepted as pre-existing debt for every slice in this run under one ruling
  (shared constraint #13, added after s1's first `quality-gate-block`); a new function-level
  violation a slice's own code introduces remains a genuine block. s3 later distinguished this
  further: a NEW file a slice creates that exceeds `class_lines` is the slice's to fix, since the
  acceptance covers pre-existing debt only, not debt a slice invents.
- s2's declared goal was amended in `dag.json` mid-run because s1 had already fixed the
  `run_state.py` coverage-omit entry s2 was to be sole owner of.
- The controller recorded its own error: dispatching a wave by workflow name discards any patch
  made to a prior wave's persisted script copy — this caused wave 3 to hit the identical
  `r.commits.head` defect wave 2 had already hit and patched, costing roughly 57 minutes and
  701k tokens repeating a known bug (per the dispatch context; not independently verifiable from
  the artifacts read here beyond the decisions-log entry recording the cause).
- Phase 5's three actionable integration-review findings were closed by one inline pass rather
  than a remediation slice, because none reached the P0/P1 blocking bar and the run's own
  pattern (three prior residual-fix passes) supported handling them inline without spending a
  wave.

Every human-answered escalation:

- `intake:council-objection-scope-lane` — Promoted role on `plan-critic`; panel size unchanged
  at every tier; no 14th agent.
- `intake:council-objection-req5` — Advisory only, never delete a finding; `blocking()` untouched
  at any severity.
- `run:material-assumption-runtime-version` — Update the installed plugin 2.0.0 → 2.1.0, then
  resume, rather than run on a cache with five known bugs.
- `s1:quality-gate-block` (first occurrence) — Accept the two `class_lines` findings as
  pre-existing debt, no threshold weakened, plus one added regression-pin test.
- `s2:budget-exhausted` — Not a resource limit; an unguarded `r.commits.head` read whose
  `TypeError` the catch-all mislabelled as budget exhaustion; resolved by guarding the read in
  the run's persisted script copy and resuming from the journal.
- `s2:quality-gate-block` — Resolved by the in-run precedent already set on s1, not re-asked.
- `s3:budget-exhausted` — A genuine `StructuredOutput` retry-cap exhaustion (5 failed calls) in
  the final verify agent, distinct from the two crashes mislabelled as budget exhaustion
  elsewhere in the run; resolved by accepting the committed work through that point.

## 6. Integration Gate Result

Phase 5 ran twice. Attempt 1 (suite GREEN at `89067a4`; whole-run quality gate FAIL-ACCEPTED and
explicitly non-vacuous — 7 whole-file `class_lines` findings, zero function-level, all
pre-existing; cross-slice `pr-reviewer` review in integration mode over `f3eac92..HEAD`, session
model, high effort, returned no P0/P1 and four non-blocking findings) passed. The three
actionable findings (two P2 needing a fix, one P3 doc-precision gap; a fourth P2 was
informational, corroborating an already-deferred metrics double-count, and needed no action)
were closed by one inline controller-dispatched pass, commit `2aba63f`, touching only comments,
docstrings, docs and tests — no runtime behaviour changed. Attempt 2, re-run fresh on all six
suite segments at `2aba63f`, passed with the identical accepted 7-finding quality-gate profile
and the review carried forward clean. No remediation slice was opened at any point, because
nothing in either attempt reached the Tier-3 blocking bar (P0 or P1). Integration branch head is
`2aba63f`.

## 7. How to Verify & Operate

Run each of the following as its own tool invocation from the repo root (this is the exact
six-segment command every slice and both Phase 5 attempts used):

```
python3 scripts/validate_marketplace.py .
python3 -m unittest discover -s scripts -p test_*.py
python3 -m unittest discover -s plugins/spec-loop/scripts -p test_*.py
python3 scripts/measure_coverage.py
node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs
claude plugin validate .
```

Expected result on this branch at `2aba63f`: marketplace validation OK; 106 tests in `scripts/`;
1133 tests in `plugins/spec-loop/scripts/`; coverage PASS on every per-file and total floor
(`run_state.py` 100.0% 671/671 vs a 95 floor, TOTAL 96.7% 5972/6173 vs a 90 floor); 48/48 node
tests; `claude plugin validate` passes. The quality gate itself reports FAIL with exactly seven
whole-file `class_lines` findings and zero function-level findings — this is the accepted,
human-ruled state for this repo's own scripts, not a regression to chase.

This run introduced no new CI gates, scripts, or thresholds — the human ruling explicitly
forbade weakening or adding to quality-gate thresholds, metrics, or blocking semantics, and no
slice touched them. `docs/spec-loop/20260825-scope-ceiling/metrics.json` now holds this run's
own counters (schema keys `generated_at`, `performance`, `quality`, `run_id`,
`run_schema_detected`, `safety`, `sources`, `tokens`, `schema_version`). It must be computed
with **the repo copy** of `plugins/spec-loop/scripts/run_metrics.py`, not the installed plugin
cache's copy — the cache predates this run's counters and silently omits them. That distinction
mattered mid-run: the controller briefly ran the stale cache copy of `run_metrics.py`, read a
*missing* key back as a null-honest `None`, and briefly misdiagnosed a shipped counter as broken
before catching that it had read the wrong script entirely; re-running against the repo copy's
`compute --write` against this run's `events.jsonl` is what produced the figures below. Figures:
`safety.deferrals_total` 8, `safety.over_scope_deferrals` 3, `safety.council.over_scope_flags`
null, `safety.council.concerns_deferred` 8, `safety.council.safety_objections` 1,
`safety.decisions_total` 17, `safety.autonomy_ratio` 0.7083, `safety.escalations` total 7 / open
0 / answered 7 (`by_trigger`: `budget-exhausted` 2, `council-objection` 2,
`material-assumption` 1, `quality-gate-block` 2; basis `events-jsonl+sidecar-v2`). Two nuances
keep those figures honest rather than flattering: the 3 `over_scope_deferrals` are events the
**controller** wrote by hand while resolving review residuals, so the
event→sidecar→log→metrics *channel* is exercised while the workflow's own `deferralEvents`
*producer* is not; and `over_scope_flags` reading null next to a populated sibling is the single
best piece of live evidence this run produced for its own null-honest design — an
implementation that returned 0 there would have asserted "nothing was over scope" when the true
state is "nothing was measured," because the councils that produced those verdicts ran on the
pre-mechanism cache workflow and cannot emit the flag at all.

To operate the new mechanism for real (not by reading, by execution): merge or publish this
branch, reinstall the plugin so the cache picks up `slice-wave.workflow.js`'s edits, and run a
slice whose plan or council verdict is likely to trip the scope ceiling — that will be the first
run in which any of this run's workflow-side changes actually execute.
