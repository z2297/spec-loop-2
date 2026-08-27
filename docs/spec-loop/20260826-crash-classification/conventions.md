# Conventions — 20260826-crash-classification

Every agent on this run reads THIS file instead of re-exploring. Facts below marked
**[verified]** were established first-hand by the controller with the command shown.

## Repo identity

`spec-loop-2` is the source of the `spec-loop` Claude Code plugin. The code under
`plugins/spec-loop/` IS the loop machinery. This run edits that machinery.

**Self-modification guard [verified]:** `plugin_root` for every wave is pinned to the
installed cache `/Users/zachmcmurry/.claude/plugins/cache/spec-loop/spec-loop/2.2.0/`,
which is byte-identical to the pre-run repo
(`diff -rq` → only `.in_use` and `__pycache__` differ). Slices therefore execute a frozen
2.2.0 snapshot while editing the repo copy. Consequence: **nothing this run ships in
`slice-wave.workflow.js` is executed by this run.** It is covered only by source-text
contract tests, which prove a construct is present and cannot prove it behaves.

## Test / build command — SIX SEGMENTS, each its own tool call

Never run these as one command; a monolithic invocation near the 10-minute tool ceiling
gets killed and reads as a false red. Run each as a separate Bash call, from the repo root:

```
python3 scripts/validate_marketplace.py .
python3 -m unittest discover -s scripts -p "test_*.py"
python3 -m unittest discover -s plugins/spec-loop/scripts -p "test_*.py"
python3 scripts/measure_coverage.py
node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs
claude plugin validate .
```

**Baseline on `main` @ `8d0e2c1` [verified] — all six GREEN, ~50s total:**

| segment | result |
|---|---|
| marketplace validation | `OK: marketplace and all plugins valid (.)` |
| `scripts/` unittests | `Ran 106 tests` → `OK` (17.9s) |
| `plugins/spec-loop/scripts/` unittests | `Ran 1133 tests` → `OK` (16.5s) |
| coverage | `PASS: all per-file and total floors met`, TOTAL **96.7%** (5972/6173) |
| Node dashboard-asset tests | 48 tests, 48 pass, 0 fail |
| `claude plugin validate .` | `✔ Validation passed` |

Segment 2 prints CHANGELOG-rolling chatter (`rolled CHANGELOG [Unreleased] -> [1.1.0]`) —
that is release-tooling test fixture noise against a temp dir, **not** a real edit. The
tree stayed clean [verified via `git status --porcelain`]. Do not "fix" it.

## Coverage floors — tight on the two files this run touches most

`python3 scripts/measure_coverage.py` enforces per-file AND total floors. Current
headroom on the files in scope [verified]:

| file | current | floor | headroom |
|---|---|---|---|
| `scripts/run_state.py` | **100.0%** (671/671) | 95% | thin — new lines need tests |
| `scripts/run_metrics.py` | **98.6%** (1303/1321) | 93% | moderate |
| `scripts/quality_gate.py` | 91.7% | 86% | n/a to this run |
| TOTAL | 96.7% | 90% | — |

`run_state.py` is at 100%. Any uncovered line added there drops it immediately. Write the
test with the change, not after.

## HARD CONSTRAINTS this run must respect — all [verified] by direct grep

### 1. The trigger allow-list is TRIPLICATED and validation is FAIL-CLOSED

Three independent hardcoded tuples hold the same six trigger strings:

- `plugins/spec-loop/scripts/run_state.py:67` — `ESCALATION_TRIGGERS`
- `plugins/spec-loop/scripts/run_metrics.py:119` — `ESCALATION_TRIGGERS`
- `plugins/spec-loop/scripts/dashboard_server.py:149` — `ESCALATION_TRIGGERS`

plus the JSON-schema enum at `plugins/spec-loop/workflows/slice-wave.workflow.js:40`.

`run_state.py:204` rejects an unknown trigger:

```python
if record.get("trigger") not in ESCALATION_TRIGGERS:
    errors.append("%s: trigger must be one of %s (found %r)" % ...)
```

`persist-slice` validates fail-closed, so a sidecar carrying a trigger the tuple does not
list is REJECTED and the slice is treated as ESCALATED.

**Therefore: the workflow enum addition and at minimum `run_state.py`'s tuple MUST land in
the SAME slice.** Splitting them leaves an intermediate merge commit at which the loop
cannot persist its own sidecars — a break the test suite would not necessarily catch,
because no runtime path in the suite exercises the new value end-to-end.

### 2. Trigger names are SUBSTRING-matched in the legacy path — naming landmine

`run_metrics.py:1692`, in `_legacy_match_triggers` (v1 prose runs):

```python
matched = [t for t in ESCALATION_TRIGGERS if t in lower]
```

Substring containment, not equality. **The new trigger name must not contain, and must not
be contained by, any existing trigger name** (`ambiguity`, `material-assumption`,
`review-block`, `council-objection`, `quality-gate-block`, `budget-exhausted`), or legacy
runs mis-bucket into both. A name like `budget-exhausted-crash` is disqualified on this
ground alone.

`run_metrics.py:450` `_normalize_trigger` is equality-based with a graceful `"other"`
fallback, so unknown triggers there degrade rather than crash.

### 3. Answerability is already settled BY TEST — do not wire `answerFor` for a crash

`answerFor()` `slice-wave.workflow.js:292`, `answerContext()` `:304`. Answers arrive as
`A.answers["<sliceId>:<trigger>"]` (`humanAnswer()` `:539`, documented `:19`).

| trigger | prompt-injected? | site |
|---|---|---|
| `ambiguity` | yes | `:316` |
| `material-assumption` | yes | `:316` |
| `council-objection` | yes | `:323` |
| `review-block` | yes | `:359` |
| `quality-gate-block` | yes | `:384` `answerFor`, `:405` `answerContext` |
| `budget-exhausted` | **no — DELIBERATELY, and pinned by a test** | — |

`slice_wave_contract_base.py:79-81`:

```python
ANSWERABLE_TRIGGERS = (
    "ambiguity", "material-assumption", "review-block",
    "council-objection", "quality-gate-block")
```

`test_slice_wave_contract.py:111` pins that each of those five HAS an `answerFor` site.
`test_slice_wave_contract.py:131` pins that `budget-exhausted` has NONE:

```python
def test_budget_exhausted_is_still_not_injected_anywhere(self):
    # It asks for a resource, not a decision (escalation-gate SKILL.md):
    # there is nothing for a prompt to apply.
    self.assertNotIn("answerFor(slice, 'budget-exhausted')", self.src)
```

**Correction to earlier intake notes:** the KG pattern
`an-escalation-trigger-with-no-answer-injection-path-cannot-be-resolved-by-re-dis`
describes `quality-gate-block` (since fixed via `answerContext`), NOT `budget-exhausted`.
`budget-exhausted`'s missing path is intentional: a resource answer is consumed by the
CONTROLLER (raise the cap, re-dispatch), and there is nothing an agent prompt can "apply".

A crash answer is likewise a controller action — retry / skip / stop the run. **The new
trigger therefore goes in the NON-answerable set, `ANSWERABLE_TRIGGERS` stays at five, and
this run ADDS a mirror of the `:131` test for the new value.** Wiring `answerFor` for a
crash would tell an agent to apply a decision it cannot act on.

### 4. The escalation-gate contract wording is normative and must be updated in step

`plugins/spec-loop/skills/escalation-gate/SKILL.md:72-80` currently reads: "**Two** things
that are deliberately NOT judgment triggers ... `budget-exhausted` (the workflow's guard
emits it when a structural cap is hit — agent cap, stage token floor, lost slice; it asks
for a resource, not a decision) and the council's **over-scope flag** ... There are exactly
five triggers; an over-scope flag is not a sixth."

Read carefully: "five triggers" = five **judgment** triggers (ambiguity,
material-assumption, review-block, council-objection, quality-gate-block).
`budget-exhausted` is the deliberate non-judgment extra. An unclassified crash is likewise
NOT a judgment trigger — it is a machine-failure report. So the coherent shape is: five
judgment triggers + `budget-exhausted` (resource) + the new crash classification, and this
passage becomes "**three** things that are deliberately NOT judgment triggers."

## Corrected premise evidence — read this before believing any 9-hour framing

The previous run `20260825-scope-ceiling` ran 9h28m active (17:11:33Z -> 02:39:19Z).
Controller-measured from its `events.jsonl`:

- **True human answer latency across the whole run: ~35-39 minutes (~6% of 568 min).**
  Per escalation, first-open to FIRST answer: intake council objections 21.5 min (the two
  are concurrent, count once), `s1:quality-gate-block` 16.2 min,
  `s2:budget-exhausted` **1.1 min**, `s3:budget-exhausted` **0.6 min**.
- An earlier controller draft reported 85 min and 76 min for the two crash escalations.
  That was WRONG: the duplicate-escalation-render bug gives each id two
  `escalation-answered` events, and reading the LAST one inflates the latency. The 85/76
  min figures are the gap to a bookkeeping RE-answer, not to the human's real answer.
- The 85 and 76 minute windows were real elapsed time, but they were **controller
  diagnosis and recovery**: realising a "budget/cap" escalation was actually an unguarded
  `r.commits.head` read throwing a `TypeError`, patching the persisted script copy, and
  resuming from the journal.

**Therefore: the cost of the mislabelling is misdirected DIAGNOSIS, not human waiting.**
The high-value part of this change is a crash record diagnostic enough that the controller
recovers fast — the failing stage/role plus the real exception — not the rename by itself.
Do not justify any part of this run with "it saves the human 161 minutes." It does not.

## Existing prior-run behavior to preserve

`docs/spec-loop/20260825-scope-ceiling/` is a completed run on disk. Its `events.jsonl`
(144 events) and four sidecars contain `budget-exhausted` escalation records. Because
`budget-exhausted` REMAINS in the enum (its meaning narrows; the string does not go away),
those artifacts keep validating. Do not remove the value.

## Prior-run knowledge that applies to this change

- `an-optional-schema-field-read-unguarded-aborts-the-whole-pipeline` — "a catch-all wrapper
  then reports the resulting TypeError as whatever it is written to assume (a budget or
  resource limit), sending the diagnosis in exactly the wrong direction." This run fixes the
  wrapper, not the read. Two tells a "resource limit" is really a crash: the context is a
  runtime error string rather than a count, and the work is all present on disk.
- `a-per-run-patch-to-generated-orchestration-does-not-survive-a-new-dispatch` — dispatching
  a wave by workflow NAME pulls a clean copy from the installed cache, discarding any patch
  made to a prior wave's persisted script copy. Controller discipline, not slice work.
- `write-docs-from-shipped-code-never-from-the-plan` — a documentation slice must source
  from shipped code; a long run's own planning artifacts go stale mid-flight.
- `a-behavior-fix-must-sweep-every-comment-asserting-the-old-behavior` — comments outside a
  slice's file list keep asserting the old behavior and reproduce the defect class. The
  workflow has an explanatory comment block at `slice-wave.workflow.js:637` that describes
  the catch-all relabelling as current behavior; it must be swept.
- `verify-the-artifact-not-the-agents-self-report` — treat a slice's own PASS/commit report
  as a claim to verify.

## Style

- `slice-wave.workflow.js` is **plain JavaScript, not TypeScript**. No type annotations, no
  interfaces, no generics. Workflow scripts additionally may NOT call `Date.now()`,
  `Math.random()`, or argless `new Date()` — they break resume. Timestamps come from the
  controller.
- Python is `unittest` (not pytest), stdlib only.

## Workflow anatomy — controller-verified by direct read (2026-08-26)

The `explore-workflow` agent was dispatched for this and returned only idle pings; the
controller stopped it and read the file directly. Everything below is first-hand.

### THREE meanings currently share `budget-exhausted`, not two

| # | meaning | site | reached how |
|---|---|---|---|
| 1 | **Structural resource limit** — agent cap / token stage floor | `:425`, `:427` in `guard()` | thrown as `{escRecord}`, so it is a *classified* throw |
| 2 | **Caught unclassified exception** — any JS error from any stage | `:856` in `runSliceError()` | the `catch` in `runSlice()` `:859-866`; the `e.escRecord` branch passes classified ones through, the fallback relabels everything else |
| 3 | **Terminal slice death** — the slice function returned nothing | `:878` in the wave entry | `parallel()` resolved that thunk to `null`; this is OUTSIDE `runSlice`'s try/catch |

Case 3 is a genuinely third thing: not a resource limit and not a caught crash, but the
slice process dying with no result at all. The title is already honest (`slice lost`) but
the trigger is not. Decomposition must decide whether cases 2 and 3 need ONE new
classification or TWO. That is an intake-council question, not a silent choice.

### Stage order — `runStages()` at `:833`

Flat sequence, each stage returning `{stop}` (terminal) or data:

1. `stagePlan` `:474` (P)
2. `stageCritique` `:575` (C)
3. `stageTasks` `:649` (T) — then `maybePromoteTier` `:662`
4. `stageReviewGate` `:690` (R)
5. `stageFixLoop` `:765` (V-F)
6. `maybePolish` `:782` (S)
7. `stageVerify` `:820` (Z)

`runSlice` `:859` wraps the WHOLE sequence in ONE try/catch, so the catch cannot tell which
stage threw.

### `state` has NO current-stage field — [verified]

`initSliceState()` `:450-461` returns exactly:

```js
{ agentsUsed, events, escalations, review_tier, critique, commits,
  tasksCompleted, implConcerns, deferred, review, tests, quality }
```

There is no `stage` / `currentStage` / `phase` key. **Requirement 3 of the request (say
WHICH stage crashed) therefore requires adding one**, set at each stage boundary in
`runStages` (or inside `dispatch`, which already knows the `role`). `dispatch()` `:430`
receives a `role` string and pushes an `agent-dispatch` event with it — the cheapest honest
signal for "what was in flight" is the last dispatched role, already available.

### `esc()` id has no round suffix — `:255`

```js
id: `${slice.id}:${trigger}`
```

The run-state contract documents `"<slice-id>:<trigger>[:<round>]"` but this builder never
emits a round. Consequence for this run: two crashes in the same slice collide on one id,
which is also how `answerFor` matches an answer back (`humanAnswer(\`${slice.id}:${trigger}\`)`,
`:539`). Do NOT "fix" the id scheme — answer matching depends on it, and the request's
scope ceiling excludes escalation-system redesign. Note it, do not touch it.

### `escalated()` `:265` and `doneResult()` `:462`

Both build the schema-2 sidecar. `escalated()` pushes the record onto `state.escalations`
first, so every escalation raised during a slice travels out even if a later one wins.

### Loop bounds — `:16-17` and `:31-33`

`replan ≤1`, `task retry ≤1`, `fix rounds ≤2` (`MAX_FIX_ROUNDS`, `:32`), `debug-fix ≤1`;
`CAPS = {1:10, 2:18, 3:32}` (`:31`); `BUDGET_STAGE_FLOOR = 60_000` (`:33`).

### The stale comment that must be swept

`:637-646` is an explanatory comment block ending: "Reading it unguarded threw a TypeError
that the catch-all below re-labelled as a budget-exhausted 'wave interrupted' — run
20260825-scope-ceiling lost a wave to it after all five tasks had already committed."
After this change the catch-all no longer emits `budget-exhausted`, so that sentence
becomes false. Sweep it (KG pattern
`a-behavior-fix-must-sweep-every-comment-asserting-the-old-behavior`).

## Complete consumer inventory — controller-verified (2026-08-26)

The `explore-consumers` agent also returned only idle pings and was stopped; this inventory
is first-hand. **This is the definitive change surface. Work from it.**

### Code — must change

| file:line | what | note |
|---|---|---|
| `workflows/slice-wave.workflow.js:40` | `ESCALATION.trigger` JSON-schema enum | the source of truth |
| `workflows/slice-wave.workflow.js:856` | `runSliceError()` catch-all fallback | the bug |
| `workflows/slice-wave.workflow.js:878` | wave-entry "slice lost" record | third conflated meaning |
| `workflows/slice-wave.workflow.js:450` | `initSliceState()` | add a stage/role field if naming the failing stage |
| `workflows/slice-wave.workflow.js:637-646` | stale comment asserting old behavior | sweep |
| `scripts/run_state.py:67` | `ESCALATION_TRIGGERS` tuple | **fail-closed** via `:204` |
| `scripts/run_metrics.py:119-126` | `ESCALATION_TRIGGERS` tuple | feeds `by_trigger` bucketing |
| `scripts/dashboard_server.py:149-151` | `ESCALATION_TRIGGERS` tuple | used at `:1017` and `:1047` |

`dashboard_server.py:1017` — `_enum_or_none(record.get("trigger"), ESCALATION_TRIGGERS)`:
an unlisted trigger becomes `None`. `dashboard_server.py:1047` —
`if len(parts) >= 2 and parts[1] in ESCALATION_TRIGGERS`: the tuple gates parsing the
trigger out of the escalation **id**, so an unlisted value breaks id parsing too.

### Code — verified to need NO change

- `scripts/dashboard_assets/index.html:769` renders generically:
  `box.appendChild(el("div", {cls:"trigger", text:"trigger: " + e.trigger}))`. No hardcoded
  label/colour/icon list in the front end. `index.html:123` styles `.esc .trigger` generically.
- `scripts/run_metrics.py:450` `_normalize_trigger` degrades unknown values to `"other"`
  (equality-based, safe).

### Tests — must change or extend

| file:line | assertion | impact |
|---|---|---|
| `test_slice_wave_contract.py:61-62` | docstring describing the catch-all relabel as current behavior | becomes false; update |
| `test_slice_wave_contract.py:111` | every `ANSWERABLE_TRIGGERS` member has an `answerFor` site | leave green; do not add the new trigger to `ANSWERABLE_TRIGGERS` |
| `test_slice_wave_contract.py:131` | `budget-exhausted` has NO `answerFor` site | keep, and ADD a mirror for the new trigger |
| `slice_wave_contract_base.py:79-81` | `ANSWERABLE_TRIGGERS` = the five judgment triggers | unchanged |
| `test_dashboard_server.py:1235,1238,1245` | fixtures using id `s1:budget-exhausted:2` and trigger `budget-exhausted` | must keep passing — `budget-exhausted` stays in every tuple |

Note `test_dashboard_server.py:1235` exercises the `<slice>:<trigger>:<round>` id form even
though `esc()` never emits a round — the parser supports it; do not "simplify" that away.

Contract-test module discipline: `test_slice_wave_contract.py` and
`test_slice_wave_contract_scope.py` were split **purely to keep each module's whole-file
`class_lines` under the 300 threshold** (see the module docstring, `:8-11`). New contract
tests must respect that — adding bulk to the wrong module re-breaks the gate. Snippets are
named constants in `slice_wave_contract_base.py`; follow that pattern, do not inline string
literals in assertions.

### Docs / contracts — must change

| file:line | content |
|---|---|
| `references/run-state-v2.md:101` | the pipe-separated trigger enum — schema single-home |
| `skills/escalation-gate/SKILL.md:72-80` | "**Two** things that are deliberately NOT judgment triggers"; "exactly five triggers" |
| `agents/slice-worker-fallback.md:146` | parenthetical enumerating all six triggers |
| `agents/slice-worker-fallback.md:46` | "Hitting a cap or a bound with work outstanding is a `budget-exhausted`" — inline-mode twin behavior |
| `references/risk-tiers.md:88` | describes the per-slice `budget-exhausted` record |
| `references/migration-from-v1.md:64` | "That report arrives as a `budget-exhausted` escalation — a mechanical..." |

`agents/slice-worker-fallback.md` is NOT merely docs: it is the behavioral spec for the
inline-mode twin that runs when the Workflow tool is unavailable. It must classify
identically to the JS, or inline runs keep the old defect.

## Backward compatibility — safe [verified]

`docs/spec-loop/20260825-scope-ceiling/` (144 events, 4 sidecars) carries
`budget-exhausted` records. Because this change NARROWS the meaning of an existing string
rather than removing it, that run keeps validating and rendering. **Never remove
`budget-exhausted` from any tuple or enum.**

## Executable back-compat baseline — capture BEFORE, compare AFTER [verified 2026-08-26]

Do not merely assert the historical run still works. These three commands were run on the
pre-change tree (`main` @ `8d0e2c1`) and MUST produce byte-identical output afterwards.
`P=~/.claude/plugins/cache/spec-loop/spec-loop/2.2.0/scripts` — note: run them against the
REPO copy of the scripts once the change lands, not the frozen cache, or the check is
vacuous.

```
python3 $P/dag.py validate --run-dir docs/spec-loop/20260825-scope-ceiling
  -> {"ok": true, "errors": []}

python3 $P/run_state.py open-escalations --run-dir docs/spec-loop/20260825-scope-ceiling
  -> []

python3 $P/run_metrics.py compute docs/spec-loop/20260825-scope-ceiling
  -> safety.escalations.by_trigger ==
     {"budget-exhausted": 2, "council-objection": 2,
      "material-assumption": 1, "quality-gate-block": 2}
```

The `by_trigger` map is the sharpest check: it proves `budget-exhausted` still buckets as
itself (not silently demoted to `"other"` by `_normalize_trigger` `run_metrics.py:450`) and
that no historical record got re-classified.
