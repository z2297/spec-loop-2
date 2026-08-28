---
schema_version: 2
run_id: 20260828-refactor-escalation
generated: 2026-08-28T20:30:00Z
integration_branch: spec-loop-run/20260828-refactor-escalation
base_branch: main
base_sha: d67cff6e255fc363e93cea410e0d7bc2cff1aae6
merge_mode: single-branch
integration_gate: green-after-remediation
slice_counts: { complete: 8, split: 0, remediation: 2 }
gap_counts: { known_gaps: 12, deferred: 12, open_findings: 3 }
publish: pending
knowledge_graph: enabled
---

# Executive Readout

**What we set out to do and what shipped.** The request came from a failure observed in a
sibling repository: the loop had correctly identified that a slice implied a ~5,000-line
refactor against a 30-line real behavioral diff, but only said so after the work was already
done. The ask was an escalation point that lets a human weigh a heavy-refactor trade-off
*before* the effort is spent, in a fast-iterating team sharing one repository. What shipped is
a `refactor-scope` escalation trigger that fires at PLAN time: the slice planner declares its
own ratio of existing-lines-rewritten to net-behavior-lines, and a deterministic JavaScript
predicate — never an agent's opinion — decides whether that ratio breaches a configurable
ceiling and halts the run before any implementation work starts. Eight slices shipped it in
five waves: s1 added the `refactor_radius` threshold block to the quality-gate config and fixed
the config-overlay merge so a repo overlay merges it key-wise instead of replacing it wholesale;
s2 added the new `refactor-scope` enum value across all eight pinned touchpoints; s3 built the
core mechanism (pure predicate, escalation, answer-injection, ctx threading, and an
every-evaluation observability event); s4 closed the silent-replan leak in
`resolveCouncilObjection` and guarded three unguarded optional reads; s5 wired the controller's
`refactor_radius` ctx key and planner doctrine; s6 closed out README/CHANGELOG/risk-tier
documentation; and two remediation slices, s7 and s8, fixed four and then one further correctness
defect discovered in s3's radius mechanism by its own code review, respectively.

**The council changed the design at intake.** All three intake council members (plan-critic,
guardian, skeptic) returned OBJECT with no safety flag, and the human answered four batched
questions before any slice was planned. First, what actually failed in the motivating jobs-repo
run was "it asked, but too late" — the defect was TIMING, not detection, which is why the
checkpoint had to sit at plan time. Second, the human chose to build the declared-ratio trigger
plus fix the separately-discovered replan leak, with no git-history blast-radius mining this run.
Third, "minimal disruption to others" was read as BOTH candidate meanings, in order: firing
rarely is the hard constraint that governs threshold choice, and teammate blast radius is a
secondary, deferred concern. Fourth, the human chose to ship DEFAULT ON with conservative
thresholds, deliberately overriding guardian's opt-in recommendation, explicitly accepting that
every existing installation gains this halt on its next run after upgrade.

**What was deliberately NOT built, and why.** Teammate blast-radius measurement — other-author
churn windows, competing-branch enumeration, file-size mining — was placed on the run's scope
ceiling and left out. All three council members independently found it unreliable in this
specific repository: a competing-branch count would tally the loop's own sibling
`spec-loop/<run-id>/*` worktree branches as if they were competing teammates; this repository is
effectively single-author, so other-author churn is near-zero and the mechanism could never be
meaningfully exercised here; and file-size thresholds would fire on ordinary slices in a repo
whose hottest files already run 1,061–2,187 lines. It is recorded as deferred, not deleted, and
a second, post-implementation measurement checkpoint was likewise scoped out as a genuine but
separate mechanism with its own stage and failure modes.

**The honest limits, stated plainly.** The ratio numbers driving the halt are the planner's own
PRE-EXECUTION DECLARATION — a proxy the planner states about its own intended plan, not a
measured diff — so a refactor that blows up mid-implementation, after the plan was declared
small, is invisible to this gate. It ships DEFAULT ON, so every existing installation gains this
new halt behavior on its very next run after upgrading, with conservative thresholds chosen to
fire rarely rather than to catch every case. A plan that is revised after a council OBJECT is
NOT re-evaluated against the radius ceiling — the gate runs once, at the first plan, and the
replan path can walk past it with no halt and not even a NOT_MEASURED record; this is documented
as a known gap, not fixed, because raising the trigger from any stage other than plan was placed
outside this run's scope. The replan re-check that s4 built to close the *silent-absorption* leak
is a single `plan-critic` seat rather than the original three-member panel, and its prompt does
not carry the text of the objection it is supposed to be re-checking — so it can endorse a
revision that ignored the original objection as long as the revision reads well on its own terms.
And the pre-existing catch-all that mislabels an unhandled JavaScript TypeError
(`fix.commits.base`) as a `budget-exhausted` escalation is unchanged; it recurred during this very
run (in s2, wave 1) and was resolved by controller judgment rather than by a code fix, exactly as
it was the first time this pattern was seen in an earlier run.

**Which parts are levers and which are records.** This run's own knowledge graph carries the
lesson that recording a judgment is not the same as acting on it. The `refactor-scope` trigger
built here is a genuine LEVER: an ENDORSE-or-EXCEEDED plan-time verdict that halts the run and
requires a human answer before implementation proceeds, with that answer read back into the next
dispatch through the existing `answerFor()` injection path. The existing `critique.over_scope`
marker, deliberately left untouched, remains a RECORD only — it flags new-scope creep for a human
to read later but never halts anything, and this run's shared constraints explicitly forbid
redefining it. The observability event this run added on every radius evaluation (including
no-fire and not-measured cases) is also a RECORD, not a lever — it exists so a silent-exclusion
defect (a threshold that quietly declines to fire) is always visible in `events.jsonl`, per this
repository's standing rule that a narrowing predicate must be observable.

**Three defects the run found that nobody asked it to look for.** First, code review during s3
surfaced — and s4 was built to close — a silent-replan leak in `resolveCouncilObjection`
(`slice-wave.workflow.js:643-652`): a council objection could be absorbed by a single unchecked
replan retry with no re-critique and no human contact. Second, the human's own fourth intake
decision named a defect in the quality-gate config overlay merge (`quality_gate.py:230`), where
`merged.update(overlay)` replaced an entire non-special config block wholesale instead of merging
it key-wise; s1 fixed this as a load-bearing prerequisite for teams actually tuning the new
thresholds. Third, an unguarded `fix.commits.base` property read aborted wave 1 of this very run
(slice s2) with an unhandled JavaScript TypeError that the installed workflow's catch-all
mislabelled as a `budget-exhausted` escalation; the controller resolved it by judgment (the work
was already complete and committed) and s4 added the guard, though the underlying mislabelling
in the catch-all itself was left unfixed as a known, pre-existing pattern.

**Integration status.** Integration branch `spec-loop-run/20260828-refactor-escalation`
(base `main` at `d67cff6`, 44 commits, single-branch merge mode). The final 10-segment suite is
green: marketplace validation OK, 126 root tests, 1,398 plugin tests, coverage PASS at TOTAL
97.0% (6,248/6,443) against a 90 floor with `run_state.py` at 100%, 48/48 dashboard tests, 35/35
behaviour tests, 38/38 radius tests, 9/9 radius-partial tests, 16/16 replan tests, and
`claude plugin validate` OK. The whole-run quality gate is FAIL-ACCEPTED and explicitly not
vacuous (909 checks measured over the 43-commit diff): all nine surviving failures fall into two
adjudicated categories — seven whole-file `class_lines` breaches on files already far over the
300-line threshold before this run started, and two mis-attributions of high complexity to
`over`, a one-line boolean arrow no slice in this run ever edited. Zero genuine function-level
violations on newly written code survive. The cross-slice integration review (one `pr-reviewer`,
integration mode, session model, high effort, over `d67cff6..HEAD`) returned verdict SOUND with
no P0 and no P1, so zero Phase 5 remediation slices were opened; it found two P2/P3 documentation
findings, both closed inline in commit `65b32d6`, and Phase 5 then passed a second time on
re-verification. Two of the eight slices (s7, s8) are remediation slices for defects s3's own
review found in itself. Publish choice is pending — the human has not yet been asked.

**Gaps you should know about.**
- The plan-time radius ceiling is evaluated once, on the first plan; a plan produced by the
  council-objection replan path is never re-evaluated against it (deferred by design, s3).
- The replan re-check (s4) is a single blind `plan-critic` seat whose prompt does not carry the
  original objection text, and it narrows the silent-absorption leak rather than closing it.
- A config with exactly one usable ceiling and one mistyped/unusable ceiling can still return a
  `WITHIN_PARTIAL` state with an empty `compared[]` — a WITHIN-family token for an evaluation
  that compared nothing (s8's own review, unresolved after three remediation passes).
- Config-shape validation of the `refactor_radius` block does not exist: a mistyped
  `max_rewrite_ratio` (e.g. the string `"0.5"`) silently becomes `null` and the run completes
  without halting, with only a per-slice event line as the trace.
- Teammate blast-radius measurement (git-mining based) is out of scope entirely, deliberately
  deferred rather than built, per all three council members' verified findings that it is
  unreliable in this repository's shape.
- The pre-existing `budget-exhausted` mislabelling of unhandled JavaScript TypeErrors recurred in
  this run (s2) and remains unfixed.

**Key decisions made autonomously, plus every human-answered escalation.**
- Intake council-objection (human-answered): timing was the defect, not detection; build the
  ratio trigger and fix the replan leak, no git mining; "minimal disruption" means fire-rarely
  as the hard constraint with teammate blast radius deferred; ship default-on with conservative
  thresholds, overriding guardian's opt-in recommendation.
- s1 quality-gate-block (human-answered path, controller-executed): ACCEPTED on precedent from
  run `20260825-scope-ceiling` — all surviving violations are whole-file `class_lines` breaches
  on files already over 300 lines at base; zero function-level violations survived.
- s2 budget-exhausted (human-answered path, controller-executed): RESOLVED as a mislabelled
  unhandled TypeError, not a real budget exhaustion; the slice's work was already complete and
  committed, so it was accepted rather than re-dispatched.
- s3 quality-gate-block (human-answered path, controller-executed): ACCEPTED on the same
  pre-existing-file precedent as s1.
- s4 quality-gate-block (human-answered path, controller-executed): PARTIALLY accepted — one
  pre-existing whole-file violation accepted, but two genuine new function-level violations
  (`acceptRevisedPlan` over both complexity thresholds) were routed to a new remediation slice
  (s7) rather than accepted.
- s7 quality-gate-block (human-answered path, controller-executed): ACCEPTED after re-measuring
  against the correct slice base; the one non-pre-existing pair of violations was proven to be a
  measurement artefact of the builtin heuristic's mis-attribution to the one-line `over` arrow.
- s8 quality-gate-block (human-answered path, controller-executed): ACCEPTED on the same
  mis-attribution, now proven by observing the identical unchanged function measure differently
  (14/16, then 15/19, then 11/15) across three different diff windows with byte-identical source.
- The controller stopped remediating the radius verdict after three passes (s3, s7, s8) and
  accepted the remaining residuals as documented known gaps rather than opening a fourth
  remediation slice.

**How to verify / operate.** Run each of the ten test segments as its own tool call (never
chained — a chained invocation has twice been killed at the 10-minute ceiling and read as a false
red): `python3 scripts/validate_marketplace.py .`; `python3 -m unittest discover -s scripts -p
test_*.py`; `python3 -m unittest discover -s plugins/spec-loop/scripts -p test_*.py`; `python3
scripts/measure_coverage.py`; `node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs`;
`node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs`; `node --test
plugins/spec-loop/scripts/slice_wave_radius.test.mjs`; `node --test
plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs`; `node --test
plugins/spec-loop/scripts/slice_wave_replan.test.mjs`; `claude plugin validate .`. Inspect the
new config surface with `--print-config` (the one door to the effective `refactor_radius`
thresholds). Full machine-readable run metrics are at
`docs/spec-loop/20260828-refactor-escalation/metrics.json`.

---

## 1. What Was Built

| Slice | Goal | Files / subsystems | Branch + head | Status |
|---|---|---|---|---|
| s1 | Add `refactor_radius` threshold block to quality-gate config (default-ON, conservative), fix overlay merge to merge key-wise, document in `commands/quality-gate.md` | `quality_gate.py`, `test_quality_gate.py`, `commands/quality-gate.md`; subsystem: config | `spec-loop/20260828-refactor-escalation/s1` @ `854fa1d` | complete (ESCALATED → accepted) |
| s2 | Add `refactor-scope` enum value across all eight pinned touchpoints (JS enum, three Python tuples, fallback-agent prose incl. count word, run-state-v2 union, `TRIGGER_PROSE_LEAD`, `ANSWERABLE_TRIGGERS`) | `slice-wave.workflow.js`, `run_state.py`, `run_metrics.py`, `dashboard_server.py`, `slice_wave_contract_base.py`, `test_slice_wave_contract_crash.py`, `slice-worker-fallback.md`, `run-state-v2.md`; subsystems: escalation, contract | `spec-loop/20260828-refactor-escalation/s2` @ `4d1a03d` | complete (ESCALATED → accepted) |
| s3 | Build the mechanism: `refactor_radius` on `PLAN_RESULT`, pure guarded predicate, escalation from plan stage, `answerFor()` injection, ctx threading, every-evaluation observability event | `slice-wave.workflow.js`, `slice_wave_contract_base.py`, `test_slice_wave_contract.py`, `slice_wave_behaviour.test.mjs`; subsystems: workflow, escalation | `spec-loop/20260828-refactor-escalation/s3` @ `64bb2d4` | complete (ESCALATED → accepted) |
| s4 | Close the silent-replan leak in `resolveCouncilObjection`; guard three unguarded optional reads (incl. the `fix.commits.base` crash from s2); fix `fixableByReplan`/`fixable_by_replan` prose drift in four agent docs | `slice-wave.workflow.js`, `slice_wave_contract_base.py`, `test_slice_wave_contract.py`, `slice_wave_behaviour.test.mjs`, `plan-critic.md`, `guardian.md`, `skeptic.md`, `slice-worker-fallback.md`; subsystems: workflow, council | `spec-loop/20260828-refactor-escalation/s4` @ `3e03074` | complete (ESCALATED → partially accepted, 2 findings routed to s7) |
| s5 | Controller/agent doctrine: `refactor_radius` ctx key in `commands/spec-loop.md`, planner instructed to declare its own numbers, escalation-gate doctrine promoted from five to six judgment triggers | `commands/spec-loop.md`, `slice-planner.md`, `escalation-gate/SKILL.md`; subsystems: controller, planner-agent, doctrine | `spec-loop/20260828-refactor-escalation/s5` @ `2b48a07` | complete (DONE) |
| s6 | Documentation close-out: five-to-six trigger prose in README/risk-tiers, README component counts, CHANGELOG entry stating honest limits | `README.md`, `risk-tiers.md`, `CHANGELOG.md`; subsystem: docs | `spec-loop/20260828-refactor-escalation/s6` @ `ca89a10` | complete (DONE) |
| s7 (remediation) | Remediate four verified defects in s3's radius mechanism (thread `basis` through to the event/escalation, fix `answered` truthiness, add explicit no-usable-ceiling branch, fix `suppressed_by_answer` to key off verdict); decompose `acceptRevisedPlan` below complexity thresholds | `slice-wave.workflow.js`, `slice_wave_radius.test.mjs`, `test_slice_wave_contract_radius.py`, `slice_wave_replan.test.mjs`; subsystems: workflow, escalation | `spec-loop/20260828-refactor-escalation/s7` @ `40c46d6` | complete (ESCALATED → accepted) |
| s8 (remediation) | Close the last silent-exclusion instance: a PARTIALLY unusable ceiling must not be reported as WITHIN; make the verdict per-dimension honest with `compared[]`/`skipped[]` | `slice-wave.workflow.js`, `slice_wave_radius.test.mjs`, `test_slice_wave_contract_radius.py`; subsystems: workflow, escalation | `spec-loop/20260828-refactor-escalation/s8` @ `18aaf3f` | complete (ESCALATED → accepted) |

No slice split. Five waves total: wave 1 (s1, s2), wave 2 (s3), wave 3 (s4, s5), wave 4 (s7),
wave 5 (s6, s8). Two slices (s7, s8) are remediation slices, both opened to fix correctness
defects that s3's own code review found in itself, not defects found by an external gate.

## 2. Business Logic Now Enforced

Shared constraints from `dag.json`, now load-bearing across the codebase:

- The radius checkpoint fires at PLAN time, before implementation effort is spent — a direct
  answer to "it asked, but too late." A post-implementation check would not satisfy the request.
- No threshold comparison may be reached by JavaScript type coercion. An explicit null/type guard
  returns a "not measured" state before any `>=` comparison, because `undefined >= n` is `false`
  and `null >= 0` is `true`; since this ships default-on, a coercion bug would silently mis-halt
  every installation.
- When measurement fails or is absent, the run fails open and records loudly (null, never 0, is
  recorded as not-measured). When measurement succeeds and exceeds a threshold, the run fails
  closed and halts. These are deliberately asymmetric and must not be collapsed into one rule.
  (Confirmed extended further by s8: a *partially* usable ceiling must report exactly which
  dimensions were compared and which were skipped, never claim a comparison that did not happen.)
- Every radius evaluation emits an event carrying both the measured numbers and the thresholds
  compared against — including no-fire and not-measured cases — so a threshold that silently
  declines to fire is always visible in `events.jsonl`.
- The `refactor-scope` trigger joined `ANSWERABLE_TRIGGERS` and is read back via `answerFor()` in
  the plan-stage prompt; a trigger the orchestrator never reads back would be structurally
  unanswerable by re-dispatch (a constraint this repository already learned the hard way).
- Every optional agent-return field is now read guarded across the three previously-unguarded
  sites in `slice-wave.workflow.js`, including the exact `fix.commits.base` read that crashed
  wave 1 of this run.
- Thresholds reach the workflow only through `ctx` (the `--print-config` → `commands/spec-loop.md`
  → CTX field list path); the workflow itself has no filesystem or process access and must never
  read config directly.
- The quality-gate config overlay now merges its recognized blocks key-wise instead of replacing
  them wholesale, so a repo-level overlay can tune individual `refactor_radius` numbers without
  discarding the rest of the block.
- The silent-replan leak is closed: a council objection resolved by replan is now re-checked (by
  a single `plan-critic` seat) before the revised plan proceeds, rather than accepted on
  `revised.status === 'PLANNED'` alone.

Delivered behavior per slice: s1 ships the config surface and its documentation; s2 makes the
new trigger a first-class, pinned-test-enforced enum member; s3 is the mechanism itself
(predicate, escalation, event, injection); s4 is the replan-safety fix plus the guarded reads;
s5/s6 are the controller/doctrine/documentation surface that makes the mechanism discoverable
and operable; s7 and s8 progressively tighten the honesty of the verdict the mechanism reports
when its own configuration is partially or fully unusable.

## 3. Gaps & Deferred

- **What:** A plan produced by the post-council-objection replan path is never radius-evaluated.
  **Why deferred:** `refactorRadiusGate` runs once inside `stagePlan`; the replan path reassigns
  the plan afterward and re-running the gate would mean raising the trigger from a stage other
  than plan, which this run's scope ceiling explicitly forbids. **Reversibility:** the gap is a
  design choice documented in a code comment and the CHANGELOG; closing it later requires a
  design decision about which stage owns re-evaluation, not just a code change. (Source: s3
  deferred, DESIGN.)
- **What:** The node-driver test plumbing (`shutil.which`/`mkstemp`/`subprocess.run`/
  `json.loads`/cleanup, ~18 lines) is now duplicated a third time in `test_slice_wave_contract_radius.py`.
  **Why deferred:** the natural shared home, `WorkflowSourceTestCase` in
  `slice_wave_contract_base.py`, was already at 299 of its 300-line ceiling; extraction was
  blocked inside this slice. **Reversibility:** trivial once a small shared driver module (or
  headroom in the base file) exists. (Source: s3 deferred, CONSISTENCY.)
- **What:** The replan re-check (s4) is a single `plan-critic` seat rather than the original
  panel, and its prompt reuses a from-scratch critique template that never names the objection
  under test, so it can endorse a revision that never actually addressed the original concern.
  **Why deferred:** this narrows the leak this slice exists to close rather than eliminating it;
  fully closing it would mean carrying objection context into the recheck prompt and possibly
  re-involving the original objecting council member. **Reversibility:** moderate — a prompt and
  dispatch-shape change, not a data-model change. (Source: s4 residual review findings.)
- **What:** The re-check verdict (`replan-recheck` event) is not rendered into
  `decisions-log.md` — it is not in `run_state.py`'s `DECISION_EVENTS` list, so on the path where
  a revision the council rejected proceeds anyway, the only trace is the raw sidecar event.
  **Why deferred:** adding it to `DECISION_EVENTS` is a new `run_state.py` branch, and this run's
  binding constraint requires a coverage-executing test in the same change (floor 95, currently
  measured at 100% — the tightest margin in the repo). **Reversibility:** trivial, contingent on
  writing that test. (Source: s4 deferred.)
- **What:** One additional agent dispatch per objected slice is now spent against the fixed
  per-tier agent cap (`CAPS = {1:10, 2:18, 3:32}`). **Why deferred:** it fails closed
  (an availability escalation, not a correctness or integrity issue), so no mitigation was
  required in this slice, but the honest-limits framing should say the re-check is not free
  against the cap. **Reversibility:** n/a (accepted trade-off). (Source: s4 deferred.)
- **What:** A config with one usable and one unusable/mistyped ceiling can still return
  `WITHIN_PARTIAL` when zero dimensions were actually comparable (an empty `compared[]`), which
  is the motivating declared-ratio case from the original jobs-repo incident. **Why deferred:**
  the controller stopped remediating the radius verdict after three passes (s3 → s7 → s8) and
  accepted this as a documented known gap rather than opening a fourth remediation slice.
  **Reversibility:** moderate — the payload already carries honest `compared`/`skipped` arrays,
  so a fix is additive to an existing verdict shape, not a redesign. (Source: s8 residual review
  findings; run decision at 2026-08-28T20:06:01Z.)
- **What:** `radiusCoverage()`'s notion of "enabled" (`limits.enabled !== false`) diverges from
  `refactorRadiusStatus()`'s (`!limits.enabled`) for falsy-but-not-`false` values; unreachable
  today because the one producer of `limits.enabled` on both the JS and Python paths always
  normalizes to a strict boolean, but latent duplication. **Reversibility:** trivial (a small
  refactor to share one predicate). (Source: s8 residual review findings.)
- **What:** No schema/type validation exists for the `refactor_radius` config block; a mistyped
  `max_rewrite_ratio` (e.g. the string `"0.5"`) silently normalizes to `null` and stays that way
  for every slice of every run until a human happens to read an event payload. **Why deferred:**
  fail-open is the run's stated invariant, and config-shape validation, dashboards, and
  `run_metrics` rollups for this trigger were all placed on this run's explicit scope ceiling.
  **Reversibility:** moderate — would need its own validation pass in `quality_gate.py`'s config
  loader. (Source: s8 deferred; also the run's own stated honest-limit.)
- **What:** `suppressed_by_answer` changed meaning mid-repository-history: pre-s7 events set it
  on any answered slice regardless of verdict; post-s7 events set it only on a waived EXCEEDED
  verdict. **Why deferred:** no current consumer (`run_metrics.py`, `dashboard_server.py`,
  `run_state.py`) reads this field beyond generic rendering, so nothing breaks today — but a
  future cross-run rollup counting waived halts would silently mix two semantics.
  **Reversibility:** n/a without a migration; flagged as a known gap rather than built. (Source:
  s7 deferred.)
- **What:** Teammate blast-radius measurement (other-author churn, competing-branch enumeration,
  file-size mining) is entirely out of scope this run. **Why deferred:** all three council
  members independently found it unreliable in this specific repository — it would count the
  loop's own sibling worktree branches as competing teammates, this repository is effectively
  single-author so the mechanism could never be dogfooded, and file-size thresholds would fire
  on ordinary slices given this repo's 1,061–2,187-line hot files. **Reversibility:** high — a
  wholly separate future mechanism, deliberately not started. (Source: `dag.json`
  `scope_ceiling`; human intake decision 3.)
- **What:** The pre-existing catch-all that mislabels an unhandled JavaScript TypeError as a
  `budget-exhausted` escalation recurred in this run (s2, `fix.commits.base`) and remains
  unfixed. **Why deferred:** out of scope for this run's stated goal; resolved by controller
  judgment at the time rather than by a code fix. **Reversibility:** n/a — a known, recurring
  pattern from an earlier run, still present. (Source: `escalations.md` s2 entry;
  `decisions-log.md`.)

Open findings not yet remediated (per sidecar `review.residual[]`, all judged acceptable by the
controller rather than fixed): the `WITHIN_PARTIAL`-with-empty-`compared[]` case (s8, P2, above);
the `radiusCoverage`/`refactorRadiusStatus` enabled-predicate divergence (s8, P3, latent only);
and the `suppressed_by_answer` semantic drift across repository history (s7, P3, no live
consumer). No P1 or P0 finding survives anywhere in the run; the whole-run quality gate's nine
residual findings are all pre-existing whole-file line-count debt or a measurement artefact, not
new defects.

## 4. Requirement Traceability

| Requirement (from `request.md`) | Status | Evidence |
|---|---|---|
| A refactor-blast-radius signal computed from the slice PLAN, pre-execution | delivered | s3 built `refactor_radius` on `PLAN_RESULT` and the pure `refactorRadiusGate`/predicate, dispatched from `stagePlan`, before any task/implementer agent runs (commits through `64bb2d4`). |
| Thresholds carried in the existing quality-gate config file, with a repo-level overlay that tunes them per repository | delivered | s1 added the `refactor_radius` block to `quality_gate.py` and fixed `load_config`'s overlay merge to merge key-wise (commit `854fa1d`); `commands/quality-gate.md` documents both the step-1 key list and the written schema. |
| A new escalation kind emitted through the existing escalation channel, with a working answer-injection path | delivered | s2 added `refactor-scope` to all eight pinned enum touchpoints including `ANSWERABLE_TRIGGERS`; s3 wired `answerFor(slice, 'refactor-scope')` into `planPrompt` (commit `64bb2d4`). |
| Controller / workflow / agent-packet plumbing and docs + CHANGELOG updates | delivered | s5 added the `refactor_radius` ctx key in `commands/spec-loop.md` and planner doctrine; s6 closed out README, `risk-tiers.md`, and the CHANGELOG (commit `ca89a10`). |
| "Minimal disruption to a rapid-iterating team" — fire rarely (hard constraint) and/or account for teammate blast radius (secondary) | partial | Fire-rarely is delivered via conservative default thresholds (s1) and the null-honest fail-open/fail-closed split (s3, s7, s8). Teammate blast-radius measurement itself is explicitly deferred, not built — see §3. |
| Do not change the semantics of the existing run-level `scope_ceiling` or `critique.over_scope` | delivered (as a non-change) | No slice touched `critique.over_scope` or the CRITIQUE schema; `dag.json`'s `scope_ceiling` explicitly forbids it and no sidecar reports touching it. |
| No git-hosting or CI integration (no PR-size bots, server-side hooks) | delivered (as a non-change) | No slice added any git-hosting or CI-side component; s8's addition of a new Node test module to the existing `.github/workflows/validate.yml` runner list was judged in-scope by the council as registering a test in an existing runner, not a new CI integration (s8 `over_scope` judgment). |
| Post-hoc measurement must not be the ONLY trigger (a post-implementation confirmation may complement it, not replace it) | delivered (as a non-change) | No post-implementation measurement checkpoint was built this run; it remains on the scope ceiling as a future, separate mechanism (§3). |
| Fix the separately-discovered silent-replan leak (`resolveCouncilObjection`) | delivered, with residual gap | s4 added a re-check before an objection-driven replan proceeds (commit `3e03074`). The re-check is a single blind `plan-critic` seat whose prompt does not carry the original objection text — narrows, does not eliminate, the leak (§3). |
| State the honest limits (proxy vs. measured diff; default-on behavior change; levers vs. records) explicitly in CHANGELOG/runbook | delivered | s6's CHANGELOG entry states the proxy/measured-diff distinction and the default-on consequence (commit `ca89a10`); this runbook's Executive Readout states the levers-vs-records distinction explicitly. |

## 5. Decisions Summary

Material `decision` events (24 total in `events.jsonl`) and every answered escalation, usable as
precedent for future runs:

- **Fail open loudly when unmeasured; fail closed when measured and over threshold** — the two
  halves of the radius gate's core invariant, established at intake and never collapsed.
- **Justify the new enum value by answer-key namespacing, not by doctrine visibility** — the
  `refactor-scope` trigger earns its own enum slot because riding an existing trigger's answer
  key (e.g. `material-assumption`) would let a later answer shadow an earlier one out of the
  prompt via `latestAnswer`'s newest-round-only semantics — a correctness argument, not a
  cosmetic one.
- **Keep the silent-replan fix in scope even though the human's answer implied it was not the
  jobs-repo cause** — the human's diagnosis of the motivating incident was about timing, not the
  replan leak, but the council-verified defect was kept in scope anyway as a genuine correctness
  fix found along the way.
- **Do not build enum backward-compat, forward-compat, or version-skew handling** — guardian
  verified all three are already safe by existing design (no persisted-sidecar re-validation
  need, `_normalize_trigger`/`_enum_or_none` already handle unknown values, JS/Python resolve
  from the same plugin root), so building them would have been wasted work.
- **Accept both wave-1 slices (s1, s2) on controller-run evidence instead of re-dispatching the
  wave** — after the s2 crash, the controller independently re-ran the full suite in each
  worktree rather than burning a re-dispatch on already-complete, already-committed work.
- **Human-approved scope increase: guard all three unguarded optional reads in
  `slice-wave.workflow.js`, folded into s4** — rather than opening a separate slice, the fix for
  the crash-causing read was folded into the already-planned s4 (replan-leak) slice.
- **Extend the run's test command incrementally, twice** — from 7 to 8 segments after s3 added a
  new executing test module (`slice_wave_behaviour.test.mjs`'s radius coverage), then to 9 after
  s4's replan harness, and to 10 after s8's radius-partial module — each time because a new test
  module the original command did not cover was added mid-run.
- **Open remediation slice s7 for four correctness defects s3's own review found in itself**, and
  **widen s7's scope to also decompose `acceptRevisedPlan` below the complexity thresholds** — s7
  was expanded once, in wave 4, before dispatch, rather than opening a third slice.
- **Resolve the CHANGELOG merge conflict in place rather than opening a remediation slice** — a
  mechanical merge-conflict resolution, judged not to warrant a full slice.
- **Stop remediating the radius verdict after three passes (s3 → s7 → s8); accept the remaining
  residuals as documented known gaps** — a deliberate stopping rule against an otherwise
  open-ended chain of "the reviewer found one more edge case in the fix for the last edge case."
- **Accept the s7 gate failure as a heuristic mis-measurement, and record the gate's own false
  positive as a known gap** rather than contorting working code to satisfy a builtin-heuristic
  function-span attribution bug.
- **Close the integration review's two findings inline rather than opening a Phase 5 remediation
  slice** — both were P2/P3 documentation-only findings, below the Tier-3 P0/P1 blocking bar,
  matching precedent from run `20260825`.

Every escalation raised was answered and closed (7 total: 1 intake council-objection, 5
quality-gate-block, 1 budget-exhausted). Full text of each is above the fold in this runbook's
Executive Readout and in `escalations.md`/`events.jsonl`; none was left open under
proceed-and-log.

## 6. Integration Gate Result

Phase 5 ran twice, both PASS. **Attempt 1** (tier 3): suite green across 10 segments on the
assembled integration branch (marketplace OK; 126 root; 1,398 plugin; coverage PASS TOTAL 97.0%,
6,248/6,443 vs. a 90 floor; 48/48 dashboard; 35/35 behaviour; 38/38 radius; 9/9 radius-partial;
16/16 replan; plugin validate OK). Cross-slice review verdict: SOUND, no P0, no P1, zero
remediation slices opened. The reviewer (one `pr-reviewer`, integration mode, session model, high
effort, over `d67cff6..HEAD`, 43 commits / 8 slices) independently confirmed all five shared
constraints hold end to end, that the eight enum touchpoints agree under a real parse, that the
`refactor_radius` ctx chain is coherent and the workflow never touches `fs`/`process`, that the
replan leak is genuinely closed, and that no duplicated helper survived eight slices touching one
file. It found two documentation-only findings: a P2 (README names three Node harness modules
where four exist, and the doctrine test guarding that line hardcoded the literal count instead of
counting the tree, which is why the drift passed undetected) and a P3 (a stale importer count in
`slice_wave_contract_base.py`'s docstring). Both were closed inline in commit `65b32d6`, which
also rewrote the doctrine guard to count the tree rather than assert a literal string — the
controller independently re-verified the new guard by reverting the README to its stale wording,
observing the test fail, and restoring it. **Attempt 2** re-ran the same 10 segments after that
commit: green, unchanged results, both integration-review findings confirmed closed.

The whole-run quality gate is FAIL-ACCEPTED, explicitly not vacuous: 909 checks measured over the
43-commit diff, satisfying the anti-vacuous guard by measurement rather than assumption. All
nine surviving failures fall into two adjudicated categories: seven whole-file `class_lines`
breaches on files already far over the 300-line threshold before this run started
(`dashboard_server.py` 1,362; `quality_gate.py` 1,403, up from 1,363; `run_metrics.py` 1,852;
`run_state.py` 1,080, up from 1,078; `test_quality_gate.py` 1,629, up from 1,508;
`test_run_state.py` 1,758; `slice-wave.workflow.js` 1,327, up from 939), and two mis-attributions
of high complexity to `over`, a one-line boolean arrow (`const over = (v, max) => v !== null &&
max !== null && v > max`) that no slice in this run ever edited — proven a measurement artefact
by observing it score differently (14/16, then 15/19, then 11/15) across different diff windows
while the source stayed byte-identical. No threshold was weakened at any point to reach this
result. The one genuine function-level violation this run produced,
`acceptRevisedPlan` at cyclomatic 12 / cognitive 22, was decomposed by s7 and no longer appears
in any `summary.failures`.

## 7. How to Verify & Operate

Run each test segment as its own tool call — never chain them; a chained invocation has twice
been killed at this repository's 10-minute tool ceiling and misread as a false red:

```
python3 scripts/validate_marketplace.py .
python3 -m unittest discover -s scripts -p test_*.py
python3 -m unittest discover -s plugins/spec-loop/scripts -p test_*.py
python3 scripts/measure_coverage.py
node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs
node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
node --test plugins/spec-loop/scripts/slice_wave_radius.test.mjs
node --test plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs
node --test plugins/spec-loop/scripts/slice_wave_replan.test.mjs
claude plugin validate .
```

This is the Phase 5 suite command that produced the green result in §6, extended three times
during the run (7 → 8 → 9 → 10 segments) as new executing test modules were added by s3, s4, and
s8 respectively. `.github/workflows/validate.yml` is the CI equivalent and enforces its own
min-test-count floors so `node --test` cannot silently exit 0 on zero registered tests.

**New operational surface introduced by this run:**
- A new `refactor_radius` block in the quality-gate config (`~/.claude/spec-loop-2/quality-gate.json`
  global, `.spec-loop/quality-gate.json` repo overlay), default-ON with conservative thresholds.
  Inspect the effective merged configuration with the config surface's `--print-config`
  door — this is the only path the workflow itself is allowed to receive thresholds through; it
  has no filesystem or process access of its own.
- A new `refactor-scope` escalation trigger, now one of the eight (not the prior seven) values in
  the escalation trigger enum, and one of the six (not the prior five) JUDGMENT triggers whose
  answers are read back via `answerFor()`. Any code or doctrine still asserting "seven" or "five"
  triggers is stale (this run's own `conventions.md` still says seven/five as an artifact of when
  it was written before the run started, per s5's deferred finding — it was not corrected by this
  run and should be treated as informational context, not a live contract).
- A new `replan-recheck` observability event type, emitted whenever a council-objection replan is
  re-checked; it is not yet in `run_state.py`'s `DECISION_EVENTS` list, so it does not render into
  `decisions-log.md` today (§3).
- No new CI gate or coverage floor was added; existing floors (`run_state.py` 95, `run_metrics.py`
  93, `quality_gate.py` 86, total 90) were maintained without weakening throughout.

Full machine-readable run metrics — event-type counts, per-wave agent/token counts, quality-gate
and review counters, and performance timings — are at
`docs/spec-loop/20260828-refactor-escalation/metrics.json`.
