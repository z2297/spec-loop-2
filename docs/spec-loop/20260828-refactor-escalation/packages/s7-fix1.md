# Review package: d67cff6e255fc363e93cea410e0d7bc2cff1aae6..40c46d6  (context: -U5)

## Commits
40c46d6 fix(tests): split refactor-radius basis checks out of the 300-line file
931df1b refactor(workflow): decompose acceptRevisedPlan below both complexity thresholds
991e5c9 fix(workflow): claim a radius suppression only when an answer waived a real breach
2eb0c36 fix(workflow): report an unusable refactor-radius ceiling instead of claiming WITHIN
c77d4cf fix(workflow): only a truthy answer disarms the refactor-scope halt
52967c3 fix(workflow): thread the planner's refactor-radius basis to the human
a7c996b spec-loop(20260828-refactor-escalation): merge slice s5 — controller ctx key, planner doctrine, six judgment triggers
af2d125 spec-loop(20260828-refactor-escalation): merge slice s4 — re-critique a replanned plan, guard three optional reads
3e03074 fix(spec-loop): escalate with the re-check's own safety reason, not the stale objection
4410f8e docs(spec-loop): correct the fixable_by_replan prose and record the replan re-check
47bc275 test(spec-loop): pin the replan re-check and the three new optional-read guards
8ce17e2 fix(spec-loop): re-critique a plan revised after a council OBJECT before proceeding
3af44f3 fix(spec-loop): guard the three unguarded optional agent-return reads in the wave
2b48a07 docs(spec-loop): controller doctrine and changelog for the refactor-scope trigger
c558fc5 docs(spec-loop): the slice planner declares its refactor radius as numbers
0e62d95 docs(spec-loop): promote the escalation-gate doctrine to six judgment triggers
e547976 spec-loop(20260828-refactor-escalation): merge slice s3 — plan-time refactor-radius gate, guarded predicate, observability event
64bb2d4 fix(spec-loop): flatten refactor-radius test literals to satisfy nesting_depth gate
c0fc6f9 docs(spec-loop): document the plan-time refactor-radius ceiling and its event
d430fe2 feat(spec-loop): render refactor-radius evaluations into the decisions log
effd994 feat(spec-loop): halt at plan time and ask when a declared rewrite is over the ceiling
d1627d7 feat(spec-loop): record every refactor-radius evaluation, no-fire included
f87962b test(spec-loop): harness fixtures for the plan-time refactor radius
c51cdc9 feat(spec-loop): declare a plan-time refactor radius on PLAN_RESULT
996ec96 feat(spec-loop): judge a declared refactor radius in JS, never by coercion
b5e39c9 spec-loop(20260828-refactor-escalation): merge slice s2 — refactor-scope trigger across all eight enum touchpoints
9cdd225 spec-loop(20260828-refactor-escalation): merge slice s1 — default-on refactor_radius config block, key-wise overlay merge
854fa1d fix(spec-loop): flatten quality-gate test bodies to satisfy nesting_depth gate
4d1a03d feat(spec-loop): make refactor-scope answerable from the plan prompt
3a07ef4 spec-loop(20260828-refactor-escalation): document refactor_radius in the quality-gate command
f522cda feat(spec-loop): add refactor-scope to the escalation trigger enum
bd9c672 spec-loop(20260828-refactor-escalation): merge refactor_radius key-wise across the repo overlay
e0a9fe7 spec-loop(20260828-refactor-escalation): add default-on refactor_radius config block

## Files changed
 .github/workflows/validate.yml                     |  10 +-
 CHANGELOG.md                                       |  55 +++
 plugins/spec-loop/agents/guardian.md               |   2 +-
 plugins/spec-loop/agents/plan-critic.md            |   4 +-
 plugins/spec-loop/agents/skeptic.md                |   2 +-
 plugins/spec-loop/agents/slice-planner.md          |  23 +-
 plugins/spec-loop/agents/slice-worker-fallback.md  |  24 +-
 plugins/spec-loop/commands/quality-gate.md         |  36 +-
 plugins/spec-loop/commands/spec-loop.md            |  24 +-
 plugins/spec-loop/references/run-state-v2.md       |  35 +-
 plugins/spec-loop/scripts/dashboard_server.py      |   2 +-
 plugins/spec-loop/scripts/quality_gate.py          |  60 +++-
 plugins/spec-loop/scripts/run_metrics.py           |   1 +
 plugins/spec-loop/scripts/run_state.py             |  10 +-
 .../spec-loop/scripts/slice_wave_contract_base.py  |  27 +-
 .../scripts/slice_wave_contract_radius_driver.py   |  61 ++++
 plugins/spec-loop/scripts/slice_wave_harness.mjs   | 117 ++++++-
 .../spec-loop/scripts/slice_wave_radius.test.mjs   | 339 +++++++++++++++++++
 .../spec-loop/scripts/slice_wave_replan.test.mjs   | 154 +++++++++
 .../scripts/test_doctrine_refactor_scope.py        | 182 ++++++++++
 plugins/spec-loop/scripts/test_quality_gate.py     | 142 ++++++++
 plugins/spec-loop/scripts/test_run_state.py        |  31 ++
 .../scripts/test_slice_wave_contract_crash.py      |   4 +-
 .../scripts/test_slice_wave_contract_radius.py     | 320 ++++++++++++++++++
 .../test_slice_wave_contract_radius_basis.py       |  69 ++++
 .../scripts/test_slice_wave_contract_replan.py     | 186 ++++++++++
 plugins/spec-loop/skills/escalation-gate/SKILL.md  |  18 +-
 plugins/spec-loop/workflows/slice-wave.workflow.js | 376 ++++++++++++++++++++-
 28 files changed, 2238 insertions(+), 76 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
".github/workflows/validate.yml": [
[
71,
75
],
[
82,
83
]
],
"CHANGELOG.md": [
[
9,
63
]
],
"plugins/spec-loop/agents/guardian.md": [
[
70,
70
]
],
"plugins/spec-loop/agents/plan-critic.md": [
[
65,
67
]
],
"plugins/spec-loop/agents/skeptic.md": [
[
73,
73
]
],
"plugins/spec-loop/agents/slice-planner.md": [
[
3,
3
],
[
87,
107
]
],
"plugins/spec-loop/agents/slice-worker-fallback.md": [
[
76,
85
],
[
159,
159
],
[
161,
162
],
[
178,
180
]
],
"plugins/spec-loop/commands/quality-gate.md": [
[
21,
22
],
[
42,
42
],
[
53,
63
],
[
86,
91
],
[
102,
107
],
[
127,
131
]
],
"plugins/spec-loop/commands/spec-loop.md": [
[
86,
88
],
[
90,
93
],
[
164,
174
],
[
215,
215
]
],
"plugins/spec-loop/references/run-state-v2.md": [
[
107,
107
],
[
131,
137
],
[
153,
154
],
[
185,
207
]
],
"plugins/spec-loop/scripts/dashboard_server.py": [
[
150,
150
]
],
"plugins/spec-loop/scripts/quality_gate.py": [
[
19,
24
],
[
83,
95
],
[
227,
242
],
[
249,
255
],
[
270,
276
],
[
281,
282
],
[
286,
286
]
],
"plugins/spec-loop/scripts/run_metrics.py": [
[
125,
125
]
],
"plugins/spec-loop/scripts/run_state.py": [
[
74,
75
],
[
86,
88
],
[
91,
91
]
],
"plugins/spec-loop/scripts/slice_wave_contract_base.py": [
[
21,
28
],
[
100,
100
],
[
113,
115
],
[
117,
117
]
],
"plugins/spec-loop/scripts/slice_wave_contract_radius_driver.py": [
[
1,
61
]
],
"plugins/spec-loop/scripts/slice_wave_harness.mjs": [
[
198,
265
],
[
267,
273
],
[
278,
295
],
[
297,
297
],
[
300,
312
]
],
"plugins/spec-loop/scripts/slice_wave_radius.test.mjs": [
[
1,
339
]
],
"plugins/spec-loop/scripts/slice_wave_replan.test.mjs": [
[
1,
154
]
],
"plugins/spec-loop/scripts/test_doctrine_refactor_scope.py": [
[
1,
182
]
],
"plugins/spec-loop/scripts/test_quality_gate.py": [
[
205,
226
],
[
356,
392
],
[
442,
489
],
[
510,
544
]
],
"plugins/spec-loop/scripts/test_run_state.py": [
[
221,
231
],
[
825,
830
],
[
1052,
1065
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_crash.py": [
[
279,
281
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_radius.py": [
[
1,
320
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_radius_basis.py": [
[
1,
69
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_replan.py": [
[
1,
186
]
],
"plugins/spec-loop/skills/escalation-gate/SKILL.md": [
[
50,
50
],
[
68,
74
],
[
99,
103
],
[
129,
129
]
],
"plugins/spec-loop/workflows/slice-wave.workflow.js": [
[
33,
33
],
[
50,
50
],
[
65,
72
],
[
216,
336
],
[
480,
485
],
[
493,
494
],
[
567,
580
],
[
585,
585
],
[
701,
825
],
[
831,
834
],
[
917,
1001
],
[
1013,
1013
]
]
}
```

## Diff
diff --git a/.github/workflows/validate.yml b/.github/workflows/validate.yml
index fcec2d9..6188052 100644
--- a/.github/workflows/validate.yml
+++ b/.github/workflows/validate.yml
@@ -66,19 +66,23 @@ jobs:
         # gates, both fail closed, mirroring the client JS step: exit status,
         # and a minimum TAP count so an emptied file cannot pass silently.
         # Scope: deterministic control flow only. The real Workflow-host seam
         # is NOT covered here — see the test file's own honest-limit header.
         run: |
-          out=$(node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs 2>&1)
+          # Three modules now: the third covers the optional-read guards and the post-OBJECT
+          # replan re-check, split out because the first sits at the 300-line class_lines ceiling.
+          out=$(node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs \
+                            plugins/spec-loop/scripts/slice_wave_radius.test.mjs \
+                            plugins/spec-loop/scripts/slice_wave_replan.test.mjs 2>&1)
           rc=$?
           echo "$out"
           if [ "$rc" -ne 0 ]; then
             echo "FAIL: wave harness exited non-zero (rc=$rc)"; exit "$rc"
           fi
           ran=$(printf '%s\n' "$out" | sed -n 's/^# tests \([0-9][0-9]*\).*/\1/p')
-          if [ "${ran:-0}" -lt 14 ]; then
-            echo "FAIL: only ${ran:-0} wave harness tests ran (expected >= 14)"; exit 1
+          if [ "${ran:-0}" -lt 63 ]; then
+            echo "FAIL: only ${ran:-0} wave harness tests ran (expected >= 63)"; exit 1
           fi
 
       - name: Install Claude Code CLI
         run: npm install -g @anthropic-ai/claude-code
 
diff --git a/CHANGELOG.md b/CHANGELOG.md
index cb53571..e888418 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -4,10 +4,65 @@ All notable changes to the spec-loop plugin are documented here. The format is
 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
 [SemVer](https://semver.org/). History before 2.0.0 lives in the
 [v1 repository](https://github.com/z2297/spec-loop).
 
 ## [Unreleased]
+### Added
+- **The wave workflow now halts a slice at PLAN time when its plan declares a rewrite of
+  existing code larger than the run's configured ceiling.** `slice-wave.workflow.js` gains
+  an optional `refactor_radius` block on `PLAN_RESULT` that the planner fills with declared
+  numbers, a pure `refactorRadiusStatus()` predicate that judges them in JS — mirroring
+  `qualityStatus()`, with every comparison behind an explicit null guard because
+  `undefined >= n` is false and `null >= 0` is true — and a `refactor-scope` escalation
+  offering three trade-offs (narrow, approve, carve out) when a measured number exceeds a
+  ceiling. Thresholds arrive only through `ctx.refactor_radius`, resolved by the controller
+  from `quality_gate.py --print-config`. Every evaluation emits a `refactor-radius` event
+  carrying both the measured numbers and the thresholds compared, including the no-fire and
+  not-measured cases, and it renders into `decisions-log.md`. Honest limits: the numbers are
+  a planner-declared proxy rather than a measured diff, so this cannot catch a blowup
+  discovered mid-implementation; the check runs once, on the first plan, and a post-OBJECT
+  replan is not re-evaluated; and a controller that does not thread `ctx.refactor_radius`
+  records `NOT_CONFIGURED` and never halts.
+
+### Changed
+- **The autonomy contract now names six judgment triggers instead of five.**
+  `skills/escalation-gate/SKILL.md` adds `refactor-scope` as the sixth SURFACE trigger and
+  describes it accurately as the only one raised by the workflow's own arithmetic, at plan
+  time, on a measured breach; the same file keeps its separate, unchanged point that the
+  council's `over_scope` flag is a record that decides nothing and is still not a trigger.
+  `agents/slice-planner.md` gains the doctrine for declaring `rewrite_ratio`,
+  `touched_existing_files`, `rewritten_lines` and `basis` — numbers only, never a verdict, and
+  omitted rather than guessed as a zero — and `commands/spec-loop.md` applies the six-trigger
+  test and states how a `refactor-scope` answer is threaded back. Honest limits: this change is
+  prose and its new tests are substring assertions over that prose, so they prove the doctrine
+  is present and its five-trigger predecessor is gone, and nothing about whether an agent obeys
+  it; no runtime behaviour changes here, and the five-trigger sentences in `README.md` and
+  `references/risk-tiers.md` are not touched by this change.
+### Fixed
+- **A council objection resolved by a replan no longer passes on the revision's status
+  alone.** `slice-wave.workflow.js` used to accept a post-`OBJECT` revision whenever it came
+  back `PLANNED`, so one silent retry absorbed the objection: nobody re-read the plan the
+  council had rejected and the human never saw it, while the doctrine described the mechanism
+  as blocking. `acceptRevisedPlan()` now sends the revision back to one `plan-critic` seat
+  (`critic:replan`), records a `replan-recheck` event carrying the verdict and the reason, and
+  escalates `council-objection` on a second objection, a fresh safety flag, or an unreadable
+  re-critique. Honest limits: the re-check is a SINGLE seat, not the original panel, so a
+  tier-3 objection raised by `guardian` or `skeptic` is re-checked by `plan-critic` alone; it
+  runs once, because `state.replanned` already vetoes a second replan; and the plan-time
+  refactor-radius ceiling is deliberately NOT re-measured on the revised plan.
+- **The last three unguarded optional agent-return reads in the wave are guarded.**
+  `PLAN_RESULT.required` is `['status']` only and `FIX_RESULT.commits` is optional, so
+  `fix.commits.base` (which threw during wave 1 of run 20260828 and was mislabelled a
+  `budget-exhausted` escalation, losing the wave), `plan.escalation.trigger` and the
+  `plan.split` pass-through were each one absent object away from aborting a whole wave.
+  `fixCommits()` falls back to the slice's own shas, `planEscalation()` substitutes a usable
+  record so the slice pauses instead of crashing, and `usableSplit()` escalates a childless
+  SPLIT at the cause instead of writing a sidecar the validator rejects a stage later.
+  `slice_wave_contract_base.py`'s docstring, which recorded two of these as deliberately
+  unfixed, is corrected. Honest limit: the trigger guard is a TYPE check, so an unrecognized
+  trigger string still fails `validate_escalation` downstream exactly as it does today, and
+  the catch-all that mislabels a `TypeError` as `budget-exhausted` is unchanged.
 
 ## [2.2.2] - 2026-08-28
 ### Added
 - **The quality gate counts branch keywords in code, not in prose.** `quality_gate.py` now
   masks the content of string literals and comments before it scans a source, so a branch word
diff --git a/plugins/spec-loop/agents/guardian.md b/plugins/spec-loop/agents/guardian.md
index 5d425a3..85cc30e 100644
--- a/plugins/spec-loop/agents/guardian.md
+++ b/plugins/spec-loop/agents/guardian.md
@@ -65,11 +65,11 @@ Same contract as plan-critic, with risk findings only.
   your flag on the slice that has real risk.
 - **ENDORSE_WITH_CONCERNS** — risks worth hardening that do not block: a defensive log line,
   one more edge-case test. Each concern carries a `disposition_hint` of `fold` (cheap, do it
   now) or `defer` (real but out of scope — logged as DEFERRED, never silently dropped).
 - **OBJECT, unmarked** — a serious but non-catastrophic risk that should block until addressed:
-  a risky path with no test, validation in the wrong layer. Set `fixableByReplan: true` when
+  a risky path with no test, validation in the wrong layer. Set `fixable_by_replan: true` when
   one planner revision would resolve it without a human.
 - **OBJECT with `safety.flag: true` and its reason** — irreversible data loss, a security hole,
   a broken public contract, or anything that could silently change observable behavior,
   persisted data, or security posture. Flag it only when the risk is genuine, and always when
   it is genuine.
diff --git a/plugins/spec-loop/agents/plan-critic.md b/plugins/spec-loop/agents/plan-critic.md
index 1a96ab2..c67ffb7 100644
--- a/plugins/spec-loop/agents/plan-critic.md
+++ b/plugins/spec-loop/agents/plan-critic.md
@@ -60,11 +60,13 @@ plan before execution).
 - **ENDORSE_WITH_CONCERNS** — proceed, folding these in. Each concern carries a
   `disposition_hint`: `fold` (cheap, do it now) or `defer` (real but out of scope — logged
   as DEFERRED, never silently dropped).
 - **OBJECT** — do not execute as planned. State the precise objection, the question a human
   would need to answer (the workflow escalates it verbatim), a recommended default, and
-  `fixableByReplan: true` when one planner revision pass would resolve it without a human.
+  `fixable_by_replan: true` when one planner revision pass would resolve it without a human.
+  The revision does not pass unchallenged: it comes back to one plan-critic seat for a fresh
+  verdict, and a second `OBJECT` escalates to a human.
 
 Calibration: you are the only challenge at default tiers — a rubber stamp wastes your
 dispatch, but objection theater burns human attention that escalation-gate exists to
 protect. Object when a reasonable reviewer would reject the work over it; fold everything
 smaller into concerns.
diff --git a/plugins/spec-loop/agents/skeptic.md b/plugins/spec-loop/agents/skeptic.md
index 78a8df5..99802d6 100644
--- a/plugins/spec-loop/agents/skeptic.md
+++ b/plugins/spec-loop/agents/skeptic.md
@@ -68,11 +68,11 @@ Same contract as plan-critic, with premise findings only.
   or `defer` (real but out of scope — logged as DEFERRED, never silently dropped).
 - **OBJECT** — the premise is genuinely unsound: the wrong problem, an ambiguity that
   materially changes scope, or a missing success criterion that makes "done" undefinable. The
   bar is whether a reasonable person would refuse to start until it is answered. State the
   precise question a human would need to answer (the workflow escalates it verbatim), a
-  recommended default, and `fixableByReplan: true` when one planner revision would resolve it
+  recommended default, and `fixable_by_replan: true` when one planner revision would resolve it
   without a human.
 - **`over_scope`** — an optional record-only field on the shared verdict contract, owned by
   plan-critic's scope lane. Scope is not your lane: leave it absent. Absent means "no scope
   judgement was recorded" and is not read as `flag: false`, so omitting it costs nothing and
   asserts nothing. A premise finding that also happens to be out of scope is still reported
diff --git a/plugins/spec-loop/agents/slice-planner.md b/plugins/spec-loop/agents/slice-planner.md
index 116d0ad..9ac2ed3 100644
--- a/plugins/spec-loop/agents/slice-planner.md
+++ b/plugins/spec-loop/agents/slice-planner.md
@@ -1,8 +1,8 @@
 ---
 name: slice-planner
-description: "Turns ONE slice goal into a small, bite-sized, TDD, no-placeholder plan a zero-context engineer could execute — each task carrying exact files, test-first steps, a verification command, and a model lane (transcribe|standard|judgment). Owns the right-size gate: a slice that bundles 2+ independently shippable changes returns SPLIT instead of a plan. Dispatched by the slice-wave workflow and by slice-worker-fallback; writes the plan file and nothing else."
+description: "Turns ONE slice goal into a small, bite-sized, TDD, no-placeholder plan a zero-context engineer could execute — each task carrying exact files, test-first steps, a verification command, and a model lane (transcribe|standard|judgment). Owns the right-size gate: a slice that bundles 2+ independently shippable changes returns SPLIT instead of a plan. Declares the plan's refactor radius as numbers for the workflow to judge against the run's ceiling, never as its own verdict. Dispatched by the slice-wave workflow and by slice-worker-fallback; writes the plan file and nothing else."
 tools: Read, Write, Bash, Grep, Glob
 model: inherit
 color: blue
 ---
 
@@ -82,10 +82,31 @@ to Task N" (repeat it — tasks are read out of order); a step that says what to
 showing how; a reference to a type or function no task defines. Before returning, re-read the
 plan against the slice goal with fresh eyes: every part of the goal maps to a task, no
 placeholder survived, and later tasks' signatures match what earlier tasks produce. Fix what
 you find inline.
 
+## Declaring the refactor radius
+
+With the plan you also return three numbers describing how much EXISTING code your final task
+list rewrites: `rewrite_ratio` — existing lines your tasks rewrite or delete ÷ total lines the
+plan changes; `touched_existing_files` — how many pre-existing files your tasks modify;
+`rewritten_lines` — the absolute count of existing lines rewritten or deleted; plus `basis`, one
+sentence naming how you counted. Count from the task list once it is final, not from the goal:
+a `Create:` file contributes to the denominator only, a `Modify:` file is the existing side.
+
+Report numbers, never a verdict. The workflow judges them against the run's configured ceiling
+and, on a measured breach and only then, raises a `refactor-scope` escalation asking the human to
+narrow the slice, approve the rewrite, or carve the refactor into its own slice. Deciding for
+yourself that a large rewrite is fine — or shading a number toward the ceiling — removes the
+human's one pre-execution look at it.
+
+Omit any number you genuinely cannot estimate rather than guessing. An absent number is read as
+unmeasured and never as a zero; an invented zero reads as a measured "no rewrite at all" and
+silently disarms the ceiling. If your dispatch prompt already carries a human answer to an
+earlier `refactor-scope` escalation for this slice, that question is already settled: plan to it
+and do not re-raise the question.
+
 ## Escalation
 
 Proceed-and-log is the default: anything determinable from the goal, the codebase, or the
 conventions is yours to decide, and trivial reversible choices (naming, fixture details,
 helper placement) never warrant a human. `ESCALATE` only for genuine ambiguity — two valid
diff --git a/plugins/spec-loop/agents/slice-worker-fallback.md b/plugins/spec-loop/agents/slice-worker-fallback.md
index 706fd00..2fff3c2 100644
--- a/plugins/spec-loop/agents/slice-worker-fallback.md
+++ b/plugins/spec-loop/agents/slice-worker-fallback.md
@@ -71,16 +71,20 @@ yourself before executing it.
 
 **2 — Critique (Tier 2+).** At Tier 1, skip it and record `critique.verdict: "SKIPPED"`. At
 Tier 2 and above, dispatch the composition your tier table names — one `plan-critic`, joined
 by `guardian` at Tier 3 (same message, one shared context packet placed identically at the top
 of each prompt).
-- `OBJECT` with `fixableByReplan: true` → one replan pass through `slice-planner` with the
-  objection attached, then proceed on the revised plan. Once the plan proceeds, record the
-  ORIGINAL panel's `defer`-hinted concerns exactly as the `ENDORSE_WITH_CONCERNS` bullet below
-  does — one `deferred` event per concern, same payload shape, plus the bare boolean
-  `over_scope: true` when its raising member set `over_scope.flag` — the replan does not
-  discard them. That is your single replan.
+- `OBJECT` with `fixable_by_replan: true` → one replan pass through `slice-planner` with the
+  objection attached. The revision is NOT accepted on its status: it goes back to one
+  `plan-critic` seat for a fresh verdict, and only a non-`OBJECT` verdict with no safety flag
+  proceeds — anything else records a `council-objection` escalation. Honest limits: that
+  re-check is a single seat, not the original panel, and the plan-time refactor-radius ceiling
+  is not re-measured on the revision. Once the plan proceeds, record the ORIGINAL panel's
+  `defer`-hinted concerns exactly as the `ENDORSE_WITH_CONCERNS` bullet below does — one
+  `deferred` event per concern, same payload shape, plus the bare boolean `over_scope: true`
+  when its raising member set `over_scope.flag` — the replan does not discard them. That is
+  your single replan.
 - `OBJECT` otherwise, or any `safety.flag` → do not execute. Record a `council-objection`
   escalation with the critic's question and recommended default; return `ESCALATED`.
 - `ENDORSE_WITH_CONCERNS` → fold the `fold` concerns into the plan; for EACH `defer`
   concern append one `deferred` event with payload `{summary: <the concern text>, source:
   "plan-critique"}`, plus the bare boolean `over_scope: true` when the flagging member set
@@ -150,13 +154,14 @@ trusts the sidecar over anything you say, and an invalid one makes this slice un
 regardless of how the work went.
 
 ## Escalations
 
 Every escalation is an EscalationRecord in `escalations[]`: stable id `<slice-id>:<trigger>`,
-plus `:<round>` from the second round of that trigger in that slice onward, one of the seven
+plus `:<round>` from the second round of that trigger in that slice onward, one of the eight
 triggers (`ambiguity`, `material-assumption`, `review-block`,
-`council-objection`, `quality-gate-block`, `budget-exhausted`, `internal-error`), the context,
+`council-objection`, `quality-gate-block`, `refactor-scope`, `budget-exhausted`,
+`internal-error`), the context,
 the precise question, options with one marked `recommended`, and `if_unanswered`.
 Proceed-and-log stays the default — surface only genuine ambiguity or a material assumption
 touching behavior, public contracts, persisted data, security, or an external integration. A
 slice with any open escalation returns `ESCALATED`. `budget-exhausted` is only for the tier
 agent cap or the per-stage token floor (see Loop bounds), never for a spent loop bound.
@@ -168,10 +173,13 @@ identically; `ambiguity` is answerable and `internal-error` deliberately is not,
 mislabelling one costs the human the ability to answer it. An `internal-error` context
 carries the real error text and names the stage/role you were actually running when it
 aborted: you drive every stage serially, so unlike the workflow you DO know which one it was
 — say it. Hedge only for a failure inside step 4's concurrent review ∥ quality-gate message,
 where either dispatch may be the one that died; there, name both and say which is unclear.
+`refactor-scope` is raised only by the workflow itself at plan time, when the plan's own
+declared refactor-to-feature ratio crosses the configured threshold; you never mint one, and
+you never use it for a refactor you merely think is large.
 
 ## Return
 
 Statuses: `DONE` · `SPLIT` · `ESCALATED` · `FAILED`. Return a summary of **≤15 lines** —
 status, branch, `base..head`, critique verdict, tasks completed, review outcome (confirmed /
diff --git a/plugins/spec-loop/commands/quality-gate.md b/plugins/spec-loop/commands/quality-gate.md
index a1ae3b5..4335c5d 100644
--- a/plugins/spec-loop/commands/quality-gate.md
+++ b/plugins/spec-loop/commands/quality-gate.md
@@ -16,11 +16,12 @@ the config and never measures code or triggers slice work.
 
 ## Steps
 
 1. **Locate / read current config.** If `~/.claude/spec-loop-2/quality-gate.json`
    exists, show its current values (thresholds, `measurement`, `enabled`, `custom_gates`,
-   `tier3_surfaces`, `models`) and stop here unless the user wants changes. If not, this
+   `tier3_surfaces`, `models`, `refactor_radius`) and stop here unless the user wants
+   changes. If not, this
    is first-time setup — and if `~/.claude/spec-loop/quality-gate.json` (spec-loop v1)
    exists, offer **import** as the first option of the step-2 question:
    - **Import from v1** — read the v1 file and carry `enabled`, `measurement`,
      `thresholds`, and `custom_gates` over verbatim; drop `refactor_attempts` (see the
      migration note in step 5) and fill the v2-only keys with the defaults below. Never
@@ -36,21 +37,32 @@ the config and never measures code or triggers slice work.
      nesting_depth 4, class_lines 400, crap 40`
    - **Customize** — walk the thresholds in batches (≤4 questions per round),
      recommended value first, "Other" for exact numbers; also ask `enabled` (default
      true). Do not offer a fix-round or `refactor_attempts` question: v2's wave workflow
      caps fix rounds itself (step 5).
-3. **The two v2 knobs** (one batched round, recommended value first):
+3. **The three v2 knobs** (one batched round, recommended value first):
    - **`tier3_surfaces`** — globs whose presence in a slice's diff deterministically
      promotes that slice's *review* tier to 3 (two-reviewer panel, session model on the
      correctness lane), regardless of the tier the controller assigned. Default
      `["**/auth/**", "**/migrations/**", "**/*.sql", "**/security/**"]`; offer the
      default, "add to it", or a replacement list. This is a review-depth control, not a
      threshold — it never changes what the gate measures.
    - **`models.reviewer`** — `"sonnet"` (default: reviews at risk tier 1–2 run on
      Sonnet) or `"inherit"` (promote them to the session model — stronger reviews, more
      cost). Tier 3 always runs the panel with the session model, so this knob only
      moves the default tiers.
+   - **`refactor_radius`** — the plan-time ceiling on how much EXISTING code one slice
+     may declare it will rewrite. Ships **on**: `{ "enabled": true, "max_rewrite_ratio":
+     0.5, "max_touched_existing_files": 8, "min_rewritten_lines": 150 }`. `max_rewrite_ratio`
+     is declared rewritten-existing-lines ÷ total declared changed lines;
+     `max_touched_existing_files` counts pre-existing files the plan says it will modify;
+     `min_rewritten_lines` is a noise floor below which the check does not fire at all, so a
+     high ratio over a dozen lines is never a halt. Offer the defaults, "tune the numbers",
+     or `enabled: false`. These are **declared** numbers, a proxy the planner states before
+     implementation — not a measured diff — so they cannot catch a blowup discovered
+     mid-implementation. A missing or non-numeric value is a "not measured" state and never
+     a zero.
 4. **Custom gates.** Offer **metric gates only** — `{ "name", "metric", "threshold" }`,
    evaluated by `quality_gate.py` against the measured values, and genuinely blocking.
    **v2.0.0 does not execute command-form gates** (`{ "name", "command", "pass_when" }`):
    the schema still accepts them and the script lists them under `skipped` as
    command-form, but nothing runs them — executing them is a roadmap item. Never offer to
@@ -69,20 +81,32 @@ the config and never measures code or triggers slice work.
        "parameter_count": 4,
        "nesting_depth": 3,
        "class_lines": 300,
        "crap_score": 30
      },
+     "refactor_radius": {
+       "enabled": true,
+       "max_rewrite_ratio": 0.5,
+       "max_touched_existing_files": 8,
+       "min_rewritten_lines": 150
+     },
      "tier3_surfaces": ["**/auth/**", "**/migrations/**", "**/*.sql", "**/security/**"],
      "models": { "reviewer": "sonnet" },
      "custom_gates": []
    }
    ```
    `measurement: "hybrid"` = real analyzer when installed, else clearly-labelled
    heuristics; `crap_score` is skipped with a note when no coverage report exists.
    `quality_gate.py` measures against `enabled`, `thresholds`, and `custom_gates`, and
    passes every other key (`tier3_surfaces`, `models`, `measurement`, …) straight through
    to `--print-config`, which is how the controller reads them — one file, one door.
+   `refactor_radius` is one of those pass-through keys with one difference: the script
+   normalizes it against its shipped defaults, so `--print-config` always reports all four
+   of its keys even when the file names none or only one. The script never evaluates the
+   block — it is the plan stage's pre-execution ceiling, and a `refactor_radius` value that
+   is present but not a JSON object is a hard error (exit 2), never a silently ignored
+   setting.
 
    **Migration from v1:** `refactor_attempts` is gone. v1 used it to bound the refactor
    loop; v2's wave workflow caps a slice at 2 fix rounds and then escalates, so the key
    would have been decoration. An imported v1 config may still carry it — harmless, and
    dropping it on write is correct. Say so when importing, so nobody expects a raised
@@ -98,13 +122,15 @@ keys it changes. The merge is `quality_gate.py`'s own, not something a caller re
 ```
 python3 quality_gate.py --config ~/.claude/spec-loop-2/quality-gate.json \
                         --overlay .spec-loop/quality-gate.json --print-config
 ```
 
-`--overlay` deep-merges over `--config` — `thresholds` keys override, `tier3_surfaces`
-**unions** (an overlay extends the surface list, it can never remove a surface),
-`custom_gates` concatenate, every other key overrides — and the provenance is always
+`--overlay` deep-merges over `--config` — `thresholds` keys override, `refactor_radius`
+keys override **key-wise** (a repo that tunes one radius number keeps the global block's
+other keys; a wholesale replacement would silently hand it defaults it never chose),
+`tier3_surfaces` **unions** (an overlay extends the surface list, it can never remove a
+surface), `custom_gates` concatenate, every other key overrides — and the provenance is always
 reported: `loaded+overlay`, or `defaults+overlay` when no global config exists, in the
 measurement report's `config` field and in `--print-config`'s `source` field. So a reader
 can always tell an overlay was in play. `--print-config` prints the effective merged
 config as JSON and exits 0: that is the single door through which the controller
 reads `tier3_surfaces` and `models` before building the wave args, and the same
diff --git a/plugins/spec-loop/commands/spec-loop.md b/plugins/spec-loop/commands/spec-loop.md
index d05cd94..0ab88ce 100644
--- a/plugins/spec-loop/commands/spec-loop.md
+++ b/plugins/spec-loop/commands/spec-loop.md
@@ -81,15 +81,18 @@ deadlock is itself an escalation):
 2. **Prepare** `worktrees.py prepare --slices <ids> --base-ref <branch> --run-id <run-id>`;
    record each slice's `base_sha` (`git rev-parse <branch>`).
 3. **Dispatch**: resolve the effective gate config once through the one door —
    `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/quality_gate.py" --print-config --config
    ~/.claude/spec-loop-2/quality-gate.json --overlay .spec-loop/quality-gate.json` — and
-   take `tier3_surfaces` and `models` from it. Build the wave args object exactly as
-   `slice-wave.workflow.js` documents — `{run_id, wave_index, ctx: {run_dir (absolute),
-   plugin_root, base_ref, test_command, conventions_path, shared_constraints,
+   take `tier3_surfaces`, `models` and `refactor_radius` from it. Build the wave args object
+   exactly as `slice-wave.workflow.js` documents — `{run_id, wave_index, ctx: {run_dir
+   (absolute), plugin_root, base_ref, test_command, conventions_path, shared_constraints,
    scope_ceiling (dag.json's run-level list, verbatim; omit or pass [] when the run has
-   none — the workflow puts it in every agent packet), tier3_surfaces, quality_gate_cmd
+   none — the workflow puts it in every agent packet), tier3_surfaces,
+   refactor_radius (the merged block verbatim from --print-config; the workflow has no
+   filesystem access, so this is the ONLY way its plan-time ceiling is configured — omit it
+   and the wave records NOT_CONFIGURED and never halts), quality_gate_cmd
    ("python3 <plugin_root>/scripts/quality_gate.py --config <global> --overlay <repo
    overlay>" — the same two paths, so agents measure against the merged bar), models,
    thorough, polish}, slices: [{id, goal, files, subsystems, risk_tier, depth, worktree,
    branch, base_sha, kg_snippet}] (per-slice only —
    the scope ceiling is run-level and travels in ctx, never duplicated here),
@@ -156,10 +159,21 @@ deadlock is itself an escalation):
    raises — a value at or below the tier default is discarded by the wave, so it is no
    route to a tighter bound either. The TOKEN-FLOOR variant ("token budget exhausted")
    has no such lever: its resource is the wave budget the host supplies, and no args
    field in this contract changes the stage floor.
 
+   A `refactor-scope` record is the one trigger the wave raises from its own arithmetic
+   rather than from an agent's judgment: the plan stage compared the planner's declared
+   rewrite numbers against `ctx.refactor_radius` and stopped the slice before any
+   implementation dispatch. Write the answer back like any other, keyed
+   `answers["<slice-id>:refactor-scope"]` verbatim; the wave injects it into the
+   re-dispatched plan prompt and stops raising the halt for that slice. Answering it is the
+   only thing that unblocks the slice — re-dispatching without the answer recomputes the same
+   breach and stops again, and the ceiling itself is operator config, so there is no other
+   lever. Narrowing the slice instead is your call to make explicit: the wave does not split a
+   refactor out on its own.
+
    Then **re-dispatch the wave with ONLY its non-terminal slices** — filter `slices` to the ones
    whose sidecars are not DONE/SPLIT (merged work never re-enters a wave; its worktree is
    already gone) — same `ctx`, `answers` filled in, and `resumeFromRunId: <wf_id>` so the
    escalated slices' completed stages replay from the journal where the cache holds. Never
    rely on replay to make a terminal slice free: a cache miss re-runs it live against a
@@ -196,11 +210,11 @@ with `resumeFromRunId`, fresh invocation otherwise. All slices terminal → stra
 Phase 5 (regenerating `runbook.md` is safe).
 
 ## Escalation discipline
 
 You are the only layer that can ask the human. Never ask mid-wave, never one-at-a-time;
-apply the `escalation-gate` five-trigger test and precedent check to every candidate
+apply the `escalation-gate` six-trigger test and precedent check to every candidate
 question, including your own. Announce every question you do ask: immediately before ANY
 `AskUserQuestion` (escalation rounds, the publish prompt), fire a best-effort desktop alert —
 `printf '\a'; command -v osascript >/dev/null 2>&1 && osascript -e 'display notification
 "spec-loop run needs a decision" with title "spec-loop"' || true` — so an unattended run is
 never silently parked (a finished run once waited 7.6 hours at the publish prompt). An alert
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index 7cbad95..d70f65d 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -102,11 +102,11 @@ prose about the slice.
                                 // Stable across resumes: the round counts the answers
                                 // already recorded for the slice+trigger, so the same
                                 // answers map reproduces the same id. Answers are keyed
                                 // by this id verbatim; latestAnswer reads the newest
                                 // answered round back into the resumed prompts.
-  "trigger": "ambiguity | material-assumption | review-block | council-objection | quality-gate-block | budget-exhausted | internal-error",
+  "trigger": "ambiguity | material-assumption | review-block | council-objection | quality-gate-block | refactor-scope | budget-exhausted | internal-error",
   "title": "<short title>",
   "context": "<what the loop was doing and why it cannot decide>",
   "question": "<the precise question>",
   "options": [{ "label": "...", "detail": "...", "recommended": true }],
   "if_unanswered": "pause this slice; continue all independent slices",
@@ -126,10 +126,17 @@ at all — either of which may itself have a host- or agent-layer cause (e.g. a
 call on a hard token or rate limit) that the record does not pretend to rule out. It is not
 a catch-all for every other failure: a failure the loop can name keeps the trigger that
 names it, so a spent replan stays `council-objection` and a blocked task — including a task
 dispatch that returned no result — stays `ambiguity`. Neither is a judgment trigger.
 
+`refactor-scope` is the one trigger the workflow raises on its own arithmetic rather than on
+an agent's judgment: at plan time, when the plan's declared refactor-to-feature ratio exceeds
+the configured threshold. It IS a judgment trigger — its answer is injected back into the
+plan prompt — because the only useful answer is a human trade-off between shipping the
+refactor with the feature and splitting it out. An absent or unmeasured ratio never raises
+it: not-measured proceeds and is recorded as null.
+
 ## `events.jsonl` — the machine channel
 
 Append-only, one JSON object per line, written only by the controller
 (`run_state.py` appends; workflow returns carry the payloads; the controller
 stamps `ts` — workflow scripts have no clock).
@@ -141,11 +148,12 @@ stamps `ts` — workflow scripts have no clock).
 
 Event types (extensible; consumers ignore unknown types): `run-created`,
 `baseline`, `council-verdict`, `decision`, `deferred`, `escalation-opened`,
 `escalation-answered`, `wave-dispatched`, `wave-collected`, `slice-merged`,
 `integration-check`, `split-ingested`, `quality-gate`, `review-summary`,
-`agent-dispatch`, `phase5-gate`, `publish-choice`, `agent-cap-override`.
+`agent-dispatch`, `phase5-gate`, `publish-choice`, `agent-cap-override`,
+`refactor-radius`.
 
 Pinned payload facts (consumers rely on these; everything else is
 best-effort):
 
 - **`ts` is a collection stamp, not a duration source.** The controller
@@ -172,10 +180,33 @@ best-effort):
   override`, and override keys matching no slice of the dispatched wave are announced the
   same way on the wave's first slice. The value is coerced with `Number()`, so a JSON string
   reading as a whole number — `"14"` — is read as the integer 14 and judged against the tier
   default like any other value.
   The discard is therefore visible without waiting on a second cap record.
+- **`refactor-radius`** payload: `{summary, state, exceeded[], measured{rewrite_ratio,
+  touched_existing_files, rewritten_lines}, thresholds{enabled, max_rewrite_ratio,
+  max_touched_existing_files, min_rewritten_lines}|null, basis}`, plus `suppressed_by_answer: true`
+  when — and only when — the state is `EXCEEDED` and a truthy human answer to this slice's
+  `refactor-scope` escalation kept it from halting; the key is absent, never `false`, in every
+  other case, so counting it counts real waived halts. Emitted by
+  the wave's PLAN stage on EVERY evaluation — `state` is one of `NOT_CONFIGURED`,
+  `DISABLED`, `NO_USABLE_CEILING`, `NOT_MEASURED`, `WITHIN`, `BELOW_FLOOR`, `EXCEEDED`,
+  and only `EXCEEDED` halts. The no-fire cases are emitted precisely because a ceiling that silently declines
+  to fire is invisible narrowing: `measured` and `thresholds` are both present in every
+  state so a reader never re-derives why nothing happened. `measured` is null-honest —
+  an undeclared number is `null`, never `0`, and `0` is a real measurement. The numbers
+  are planner-DECLARED: a proxy declared before implementation, not a measured diff, so
+  they cannot catch a blowup discovered mid-implementation, and no second,
+  post-implementation checkpoint exists. `thresholds` is `null` only when
+  `ctx.refactor_radius` was absent or unusable.
+  `basis` is the planner's own one-sentence account of how it counted, or `null` when it
+  stated none: it is DISPLAY-ONLY — carried so a human weighing the trade-off can see how
+  the number was reached — and no state, threshold or comparison reads it.
+  `NO_USABLE_CEILING` means the block was present and enabled but neither `max_rewrite_ratio`
+  nor `max_touched_existing_files` survived as a number — a mistyped ceiling. It fails open
+  like the other no-fire states, and it is separate from `WITHIN` because a plan cannot be
+  "under a ceiling" that was never compared.
 - **`wave-collected`** payload carries the per-wave aggregates the workflow
   completion notification reports: `{index, agent_count, subagent_tokens,
   duration_ms}` — the honest wave-level token/duration channel while
   per-dispatch stamps are unavailable. Optional, null-honest.
 - **`council-verdict`** payload carries `safety: bool` — whether the verdict
diff --git a/plugins/spec-loop/scripts/dashboard_server.py b/plugins/spec-loop/scripts/dashboard_server.py
index ec8e994..5f54cd7 100644
--- a/plugins/spec-loop/scripts/dashboard_server.py
+++ b/plugins/spec-loop/scripts/dashboard_server.py
@@ -145,11 +145,11 @@ RECORDED_WAVE_STATUSES = ("dispatched", "collected")
 PROJECTED = "projected"
 
 # The EscalationRecord triggers (run-state-v2.md). Used both to validate a
 # record's own ``trigger`` field and to read the trigger an escalation id encodes.
 ESCALATION_TRIGGERS = ("ambiguity", "material-assumption", "review-block",
-                       "council-objection", "quality-gate-block",
+                       "council-objection", "quality-gate-block", "refactor-scope",
                        "budget-exhausted", "internal-error")
 
 # Labels meaning "the sidecar recorded a terminal outcome that the controller has
 # not yet written back into dag.json, and which WILL clear on its own" — a DONE
 # slice awaiting its serial merge, a SPLIT awaiting child ingestion. Neither is
diff --git a/plugins/spec-loop/scripts/quality_gate.py b/plugins/spec-loop/scripts/quality_gate.py
index cdabc03..a60f537 100644
--- a/plugins/spec-loop/scripts/quality_gate.py
+++ b/plugins/spec-loop/scripts/quality_gate.py
@@ -14,13 +14,16 @@ Pipeline:
   1. Changed-code discovery -- `git diff --unified=0 <base>..<head>` in
      --repo-dir; parse_diff() (a PURE function) turns the hunk headers into
      {file: [(start, end), ...]} added/modified line ranges. Deleted files and
      binary hunks are skipped so only surviving, changed code is measured.
   2. Config -- read the JSON config (schema in commands/quality-gate.md). A
-     missing file falls back to DEFAULT_THRESHOLDS and records
-     "config": "defaults"; `enabled: false` short-circuits to
-     {"skipped": "gate disabled"} and exit 0.
+     missing file falls back to DEFAULT_THRESHOLDS + DEFAULT_REFACTOR_RADIUS
+     and records "config": "defaults"; `enabled: false` short-circuits to
+     {"skipped": "gate disabled"} and exit 0. `refactor_radius` is carried
+     through as configuration only -- this script never evaluates it; it is the
+     plan stage's pre-execution ceiling, read by the controller through
+     --print-config.
   3. Backends -- detected via shutil.which (never installed). `lizard`
      (multi-language) is preferred for CCN / NLOC / parameter count / function
      spans; for .py files, `radon cc -j` is used when lizard is absent. A
      function is measured only when its line span intersects a changed range.
   4. Builtin heuristic -- for any changed file no backend covers, a pure-stdlib
@@ -75,10 +78,23 @@ DEFAULT_THRESHOLDS = {
     "nesting_depth": 3,
     "class_lines": 300,
     "crap_score": 30,
 }
 
+# The planner-declared refactor-radius proxy. These are NOT measured metrics:
+# they are the ceiling the plan stage declares it will stay under, checked
+# before implementation effort is spent. Shipped default-ON with deliberately
+# conservative numbers -- a checkpoint that fires on an ordinary slice would be
+# trained away within a run, so the floor (min_rewritten_lines) exists to keep
+# small slices entirely out of the check rather than to soften its answer.
+DEFAULT_REFACTOR_RADIUS = {
+    "enabled": True,
+    "max_rewrite_ratio": 0.5,
+    "max_touched_existing_files": 8,
+    "min_rewritten_lines": 150,
+}
+
 # Metrics measured per changed function (as opposed to per file/class).
 _FUNCTION_METRICS = (
     "cyclomatic_complexity",
     "cognitive_complexity",
     "method_lines",
@@ -206,21 +222,39 @@ def _read_config_object(path, what):
     if not isinstance(raw, dict):
         raise GateError(f"{what} {path!r} must be a JSON object")
     return raw
 
 
+def _radius_object(value, what):
+    """Coerce a raw `refactor_radius` config value to a plain dict. (PURE)
+
+    An absent block yields {} so the defaults stand. A PRESENT non-object is a
+    hard error rather than a silently ignored value: dropping a list or a bare
+    number here would leave the operator believing they had set a ceiling they
+    had not, which is exactly the silent-exclusion failure this block exists to
+    avoid.
+    """
+    if value is None:
+        return {}
+    if not isinstance(value, dict):
+        raise GateError(f"{what} key 'refactor_radius' must be a JSON object")
+    return dict(value)
+
+
 def load_config(path, overlay_path=None):
     """Load the gate config, returning (config_dict, source). source is
     "defaults", "loaded", or "loaded+overlay". A missing file (or None path)
     yields the documented defaults.
 
     The per-repo overlay (committed `.spec-loop/quality-gate.json`) deep-merges
-    over the global config: threshold keys override, `tier3_surfaces` unions
-    (the overlay extends, it cannot remove a surface), `custom_gates` concat,
-    other keys override. Both files predate the run — the guard hook denies
-    writes to either while a run is active — so any loosening in an overlay is
-    a deliberate, committed human choice, visible in review.
+    over the global config: threshold keys override, `refactor_radius` keys
+    override KEY-WISE (tuning one number never drops its siblings),
+    `tier3_surfaces` unions (the overlay extends, it cannot remove a surface),
+    `custom_gates` concat, other keys override. Both files predate the run —
+    the guard hook denies writes to either while a run is active — so any
+    loosening in an overlay is a deliberate, committed human choice, visible
+    in review.
     """
     raw = {} if not path or not os.path.exists(path) else _read_config_object(path, "config")
     source = "defaults" if not raw else "loaded"
     if overlay_path and os.path.exists(overlay_path):
         overlay = _read_config_object(overlay_path, "overlay")
@@ -231,17 +265,27 @@ def load_config(path, overlay_path=None):
         merged["thresholds"] = merged_thresholds
         merged["custom_gates"] = (raw.get("custom_gates") or []) + (overlay.get("custom_gates") or [])
         merged["tier3_surfaces"] = sorted(
             set(raw.get("tier3_surfaces") or []) | set(overlay.get("tier3_surfaces") or [])
         )
+        # refactor_radius merges KEY-WISE, like thresholds and unlike the
+        # dict.update() fall-through above. A repo overlay that tunes one number
+        # would otherwise replace the whole block and silently drop the other
+        # three keys, handing the operator defaults they never chose.
+        merged_radius = _radius_object(raw.get("refactor_radius"), "config")
+        merged_radius.update(_radius_object(overlay.get("refactor_radius"), "overlay"))
+        merged["refactor_radius"] = merged_radius
         raw = merged
         source = ("loaded+overlay" if source == "loaded" else "defaults+overlay")
     thresholds = dict(DEFAULT_THRESHOLDS)
     thresholds.update(raw.get("thresholds") or {})
+    refactor_radius = dict(DEFAULT_REFACTOR_RADIUS)
+    refactor_radius.update(_radius_object(raw.get("refactor_radius"), "config"))
     config = {
         "enabled": raw.get("enabled", True),
         "thresholds": thresholds,
+        "refactor_radius": refactor_radius,
         "custom_gates": raw.get("custom_gates") or [],
     }
     # Pass through controller-consumed keys (tier3_surfaces, models, …) so
     # --print-config is the one door to the effective configuration.
     for key, value in raw.items():
diff --git a/plugins/spec-loop/scripts/run_metrics.py b/plugins/spec-loop/scripts/run_metrics.py
index b4d17e3..4dc8d04 100644
--- a/plugins/spec-loop/scripts/run_metrics.py
+++ b/plugins/spec-loop/scripts/run_metrics.py
@@ -120,10 +120,11 @@ ESCALATION_TRIGGERS = (
     "ambiguity",
     "material-assumption",
     "review-block",
     "council-objection",
     "quality-gate-block",
+    "refactor-scope",
     "budget-exhausted",
     "internal-error",
 )
 REVERSIBILITY_BUCKETS = ("trivial", "moderate", "high", "n/a")
 GATE_RESULTS = ("PASS", "FAIL", "SKIPPED")
diff --git a/plugins/spec-loop/scripts/run_state.py b/plugins/spec-loop/scripts/run_state.py
index 5db0311..95cb03e 100644
--- a/plugins/spec-loop/scripts/run_state.py
+++ b/plugins/spec-loop/scripts/run_state.py
@@ -69,26 +69,28 @@ import tempfile
 SCHEMA_VERSION = 2
 SLICE_RESULT_STATUSES = ("DONE", "SPLIT", "ESCALATED", "FAILED")
 QUALITY_STATUSES = ("PASS", "FAIL", "SKIPPED")
 VERDICTS = ("ENDORSE", "ENDORSE_WITH_CONCERNS", "OBJECT", "SKIPPED")
 ESCALATION_TRIGGERS = ("ambiguity", "material-assumption", "review-block",
-                       "council-objection", "quality-gate-block", "budget-exhausted",
-                       "internal-error")
+                       "council-objection", "quality-gate-block", "refactor-scope",
+                       "budget-exhausted", "internal-error")
 ESCALATION_STATUSES = ("OPEN", "ANSWERED")
 RISK_TIERS = (1, 2, 3)
 # Matches dag.py: references/split-ingestion.md calls a one-child split a
 # malformed proposal, so a SPLIT sidecar proposing one is refused here too.
 MIN_SPLIT_CHILDREN = 2
 
 EVENTS_FILE = "events.jsonl"
 DECISIONS_LOG = "decisions-log.md"
 ESCALATIONS_MD = "escalations.md"
 
-# Event types whose payload is also rendered for humans.
+# Event types whose payload is also rendered for humans. refactor-radius is
+# here for its NO-FIRE cases as much as its halts: a ceiling that silently
+# declines to fire is invisible narrowing.
 ESCALATION_EVENTS = ("escalation-opened", "escalation-answered")
 DECISION_EVENTS = ("decision", "deferred", "council-verdict", "quality-gate",
-                   "integration-check", "phase5-gate")
+                   "integration-check", "phase5-gate", "refactor-radius")
 
 DECISIONS_HEADER = ("# Decisions log\n\n"
                     "Rendered from the run's events; append-only, and nothing "
                     "parses it back.\n\n")
 ESCALATIONS_HEADER = ("# Escalations\n\n"
diff --git a/plugins/spec-loop/scripts/slice_wave_contract_base.py b/plugins/spec-loop/scripts/slice_wave_contract_base.py
index 5895b59..01c6c85 100644
--- a/plugins/spec-loop/scripts/slice_wave_contract_base.py
+++ b/plugins/spec-loop/scripts/slice_wave_contract_base.py
@@ -16,19 +16,18 @@ handful of source facts whose loss is a known, observed outage - the
 null-guards on TASK_RESULT.commits and its sibling optional arrays, the
 type-safe read of CTX.scope_ceiling, the answer-injection sites, and the
 record-only isolation of the over-scope flag from the four control-flow
 branches, and the ONE-durable-record-per-defer-hinted-concern guarantee.
 
-This module (and its importers) do NOT claim every optional agent-return
-field is guarded. Two known instances of the same defect class remain
-unguarded BY DECISION, deferred and logged by this run's own council rather
-than fixed here: `plan.escalation.trigger` is read unguarded on the
-ESCALATE branch (`PLAN_RESULT.required` is `['status']` only), and
-`plan.split` is passed through as `undefined` on a SPLIT return that
-carries no `split` object. Fixing either would exceed this task's scope
-router; these modules pin what actually exists, not what a docstring would
-prefer existed.
+The two instances this docstring used to record as deliberately unguarded -
+`plan.escalation.trigger` on the ESCALATE branch and the `plan.split`
+pass-through on SPLIT - are now guarded, together with the `fix.commits.base`
+read that aborted a wave of run 20260828; `test_slice_wave_contract_replan.py`
+pins all three and asserts the raw reads are gone. What these modules still do
+NOT claim is exhaustiveness: they pin the reads that have failed in
+production, not every optional field in every schema, and no static check here
+enumerates the rest.
 
 These are source-text assertions. They prove a guard is present; they
 cannot prove it behaves. Any change to the workflow that trips one of them
 is either a regression or an intentional contract change that belongs in
 one of the importing modules too.
@@ -96,11 +95,11 @@ GATE_ANSWER = "answerFor(slice, 'quality-gate-block')"
 GATE_ANSWER_CONTEXT = "answerContext(slice, 'quality-gate-block')"
 ANSWER_CONTEXT_START = "const answerContext = (slice, trigger) => {"
 ANSWER_CONTEXT_END = "\n}\n"
 ANSWERABLE_TRIGGERS = (
     "ambiguity", "material-assumption", "review-block",
-    "council-objection", "quality-gate-block")
+    "council-objection", "quality-gate-block", "refactor-scope")
 CRITIQUE_REQUIRED = "required: ['verdict', 'safety', 'concerns']"
 FAIL_CLOSED_DEFAULT = "unreadable critic verdict (fail closed)"
 OVER_SCOPE_DEFAULT = "over_scope: null"
 OVER_SCOPE_SCHEMA = "over_scope: { type: 'object'"
 CRITIQUE_ROLLUP = "state.critique = { verdict:"
@@ -109,15 +108,15 @@ OBJECTION_SELECTION = "ob: (safety || objections[0])"
 REPLAN_VETO = "if (safety || !ob.fixable_by_replan || state.replanned)"
 FINDING_CATEGORIES = "category: { enum: ["
 # The trigger enum has six homes: this line, the ESCALATION_TRIGGERS tuple in
 # run_state.py, run_metrics.py and dashboard_server.py, and two PROSE
 # enumerations - the fallback agent's escalation section and the run-state
-# contract reference - located by the two locator constants below. Earlier
-# this comment said five and then listed four; the guard that names it now
-# asserts over all six.
+# contract reference - located by the two locator constants below. Earlier this
+# comment said five and then listed four; the guard that names it now asserts
+# over all six homes, and the enum they carry is now eight values wide.
 TRIGGER_ENUM_LINE = "trigger: { enum: ["
-TRIGGER_PROSE_LEAD = "one of the seven triggers ("
+TRIGGER_PROSE_LEAD = "one of the eight triggers ("
 TRIGGER_UNION_PREFIX = '"trigger": "'
 FALLBACK_MD = Path(__file__).resolve().parents[1] / "agents" / "slice-worker-fallback.md"
 RUN_STATE_MD = Path(__file__).resolve().parents[1] / "references" / "run-state-v2.md"
 COUNCIL_VERDICT_EVENT = "type: 'council-verdict'"
 SCOPE_HELPER = "function scopeRecord("
diff --git a/plugins/spec-loop/scripts/slice_wave_contract_radius_driver.py b/plugins/spec-loop/scripts/slice_wave_contract_radius_driver.py
new file mode 100644
index 0000000..a1d9824
--- /dev/null
+++ b/plugins/spec-loop/scripts/slice_wave_contract_radius_driver.py
@@ -0,0 +1,61 @@
+"""Shared node driver for the refactor-radius contract checks.
+
+Split out of test_slice_wave_contract_radius.py so that
+test_slice_wave_contract_radius_basis.py can execute
+`refactorRadiusStatus()` too, without importing a TestCase class from one
+test module into another - unittest discovery would then collect and run
+that class's tests twice. This module carries no `test_*` method itself, so
+`unittest discover -p 'test_*.py'` never collects it directly.
+
+Usage: imported by test_slice_wave_contract_radius.py and
+test_slice_wave_contract_radius_basis.py; not runnable on its own.
+"""
+
+import json
+import os
+import shutil
+import subprocess
+import tempfile
+import unittest
+
+from slice_wave_contract_base import SOURCE
+
+RADIUS_START = "const RADIUS_NULL ="
+RADIUS_END = "function scopeRecord("
+
+# The extracted radius block plus a driver that judges each [plan, ctx] pair.
+# %s is the function source, then the JSON case list - the same two-slot shape
+# SCOPE_DRIVER uses in slice_wave_contract_base.py.
+RADIUS_DRIVER = """%s
+const cases = %s
+const run = (c) => refactorRadiusStatus(c[0], refactorLimits({ refactor_radius: c[1] }))
+console.log(JSON.stringify(cases.map(run)))
+"""
+
+
+def radius_region():
+    """The refactorRadiusStatus()/refactorLimits() source, straight from
+    the workflow file (not from a TestCase's cached `self.src`)."""
+    start = SOURCE.find(RADIUS_START)
+    end = SOURCE.find(RADIUS_END, start + 1)
+    assert start != -1 and end != -1, "missing radius anchor"
+    return SOURCE[start:end]
+
+
+def radius_status(cases):
+    """refactorRadiusStatus() applied to each [plan, ctx] pair by real node."""
+    node = shutil.which("node")
+    if not node:
+        raise unittest.SkipTest("node is not available on this machine")
+    fd, path = tempfile.mkstemp(suffix=".mjs")
+    try:
+        with os.fdopen(fd, "w") as fh:
+            fh.write(RADIUS_DRIVER % (radius_region(), json.dumps(cases)))
+        proc = subprocess.run(
+            [node, path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
+        out = proc.stdout.decode()
+        if proc.returncode != 0:
+            raise AssertionError("node failed:\n%s" % (out,))
+        return json.loads(out)
+    finally:
+        os.unlink(path)
diff --git a/plugins/spec-loop/scripts/slice_wave_harness.mjs b/plugins/spec-loop/scripts/slice_wave_harness.mjs
index 65f22bb..bdf6f88 100644
--- a/plugins/spec-loop/scripts/slice_wave_harness.mjs
+++ b/plugins/spec-loop/scripts/slice_wave_harness.mjs
@@ -193,23 +193,120 @@ const PIPELINE = {
   "fix:1": { status: "DONE", touched_files: ["a.py"], addressed: ["r0-f1"], refuted: [], commits: { base: "0000000", head: "f1x0000" } },
   "re-review:1": { verdicts: [{ finding_id: "r0-f1", verdict: "ADDRESSED" }], new_breakage: [] },
   "verify:1": VERIFY_PASS,
 };
 
-export const PIPELINE_LABELS = Object.keys(PIPELINE).map((role) => "s1:" + role);
+// ── Refactor-radius fixtures ──────────────────────────────────────────────
+// The radius thresholds reach the workflow ONLY through ctx, and `extra`
+// above merges TOP-LEVEL wave args, so a ctx-level knob needs its own
+// builder. It reuses waveArgs rather than hand-building a second args shape,
+// so the two cannot drift.
+export const RADIUS_DEFAULTS = {
+  enabled: true, max_rewrite_ratio: 0.5,
+  max_touched_existing_files: 8, min_rewritten_lines: 150,
+};
+
+export function radiusArgs(slices, radius, answers) {
+  const base = waveArgs(slices, answers);
+  return { ...base, ctx: { ...base.ctx, refactor_radius: radius } };
+}
+
+// `undefined` means the planner returned no block at all — a DIFFERENT input
+// from a block of zeros, and the two must stay tellable apart end to end.
+export const planWithRadius = (radius) => ({
+  status: "PLANNED", plan_path: "/tmp/plan.md",
+  tasks: [{ id: "t1", title: "task t1", lane: "standard", files: ["a.py"] }],
+  ...(radius === undefined ? {} : { refactor_radius: radius }),
+});
+
+// Runs the plan stage for real, then makes the NEXT dispatch throw so the
+// slice terminates right after the gate under test. state.events survives on
+// the crash record's result, which is what the radius tests read.
+export const planThenStop = (plan) => ({
+  agent: async (prompt, opts) => {
+    if (String(opts.label).endsWith(":plan")) return plan;
+    throw new Error("STOP");
+  },
+});
+
+// ── Plan-status and council fixtures ──────────────────────────────────────
+// Every value below is a SCHEMA-LEGAL agent return. PLAN_RESULT.required is
+// ['status'] only, so SPLIT_EMPTY and ESCALATE_BARE are legal returns the
+// workflow must survive, not malformed junk - that is the whole point of
+// having them here rather than hand-built in a test body.
+const CHILD = { goal: "half", files: ["a.py"], subsystems: ["x"], internal_deps: [] };
+export const ONE_TASK_PLANNED = ONE_TASK_PLAN;
+export const SPLIT_OK = { status: "SPLIT", split: { children: [CHILD, CHILD] } };
+export const SPLIT_EMPTY = { status: "SPLIT" };
+export const ESCALATE_BARE = { status: "ESCALATE" };
+export const ESCALATE_FULL = {
+  status: "ESCALATE",
+  escalation: {
+    trigger: "material-assumption", title: "which store", context: "two stores",
+    question: "which one?", options: [{ label: "the first", detail: "d" }],
+  },
+};
+
+// ── Council OBJECT / replan fixtures ──────────────────────────
+// The reasons differ by design: a test asserts WHICH objection reached the
+// human, and two identical strings would pass that assertion by accident.
+export const OBJECTION_FIXABLE = {
+  verdict: "OBJECT", safety: { flag: false, reason: null }, concerns: [],
+  fixable_by_replan: true,
+  objection: { reason: "the plan skips the migration test", question: "Replan or accept?", recommendation: "add the migration test" },
+};
+export const RECHECK_CLEAN = { verdict: "ENDORSE", safety: { flag: false, reason: null }, concerns: [] };
+export const RECHECK_OBJECT = {
+  verdict: "OBJECT", safety: { flag: false, reason: null }, concerns: [],
+  fixable_by_replan: true,
+  objection: { reason: "the revision still skips the migration test", question: "Accept it, or drop the slice?", recommendation: "escalate to a human" },
+};
+export const RECHECK_SAFETY = {
+  verdict: "ENDORSE", safety: { flag: true, reason: "the revision drops the pre-migration backup" }, concerns: [],
+};
 
-// Records the label and the prompt of every dispatch and answers each one with
-// the return above. An unmapped role throws under its own name: a new stage
-// must be mapped here rather than degrading a run into a fail-closed path in
-// silence, which would quietly narrow whatever a test built on this asserts.
-export const fullPipeline = () => {
+// Answers a dispatch from `map`, keyed by the role part of the label
+// (`s1:critic:full-council` -> `critic:full-council`). An unmapped role throws,
+// which terminates the slice right after the stage under test; `seen` is the
+// dispatch order, so a test can assert that a stage did or did not run at all.
+// A mapped Error value is thrown instead of returned, and a mapped null is
+// returned as null - the terminal-failure input every caller must fail closed on.
+export function councilSandbox(map) {
   const seen = [];
   const agent = async (prompt, opts) => {
     const label = String(opts.label);
     const role = label.slice(label.indexOf(":") + 1);
-    const mapped = PIPELINE[role];
-    if (mapped === undefined) throw new Error("slice_wave_harness: no mock return mapped to role " + role);
+    seen.push(role);
+    if (!(role in map)) throw new Error("STOP");
+    if (map[role] instanceof Error) throw map[role];
+    return map[role];
+  };
+  return { seen, agent };
+}
+
+// Records the label and the prompt of every dispatch and answers each one from
+// `map`. An unmapped role throws under its own name: a new stage must be mapped
+// rather than degrading a run into a fail-closed path in silence, which would
+// quietly narrow whatever a test built on this asserts.
+function mappedPipeline(map) {
+  const seen = [];
+  const agent = async (prompt, opts) => {
+    const label = String(opts.label);
+    const role = label.slice(label.indexOf(":") + 1);
+    if (!(role in map)) throw new Error("slice_wave_harness: no mock return mapped to role " + role);
     seen.push({ label, prompt });
-    return mapped;
+    return map[role];
   };
   return { seen, agent };
-};
+}
+
+// fullPipeline() with individual roles swapped out, so a test can drive ONE
+// deviant return through an otherwise complete slice without rebuilding the map.
+export function pipelineWith(overrides) {
+  return mappedPipeline({ ...PIPELINE, ...overrides });
+}
+
+export const PIPELINE_LABELS = Object.keys(PIPELINE).map((role) => "s1:" + role);
+
+// Every role of the eight-dispatch pipeline mocked, with nothing swapped out.
+// One shared mock body with pipelineWith() above, so the two cannot drift.
+export const fullPipeline = () => mappedPipeline(PIPELINE);
diff --git a/plugins/spec-loop/scripts/slice_wave_radius.test.mjs b/plugins/spec-loop/scripts/slice_wave_radius.test.mjs
new file mode 100644
index 0000000..60b2016
--- /dev/null
+++ b/plugins/spec-loop/scripts/slice_wave_radius.test.mjs
@@ -0,0 +1,339 @@
+// slice_wave_radius.test.mjs — the plan-time refactor-radius ceiling, EXECUTED.
+// HONEST LIMIT: this drives the workflow's deterministic control flow against the
+// mock sandbox in slice_wave_harness.mjs; the real Workflow-host seam stays
+// unverified, and the numbers under test are DECLARED by the planner, so nothing
+// here proves a diff was actually that size. Split out of
+// slice_wave_behaviour.test.mjs because that module sits at the quality gate's
+// 300-non-blank-line class_lines ceiling.
+
+import test from "node:test";
+import assert from "node:assert/strict";
+import {
+  runWave, sliceFixture, radiusArgs, RADIUS_DEFAULTS,
+  planWithRadius, planThenStop } from "./slice_wave_harness.mjs";
+
+const S1 = () => [sliceFixture("s1")];
+const BIG = { rewrite_ratio: 0.9, touched_existing_files: 12, rewritten_lines: 900, basis: "counted by hand" };
+const SMALL = { rewrite_ratio: 0.1, touched_existing_files: 2, rewritten_lines: 40, basis: "counted by hand" };
+const AT_CEILING = { rewrite_ratio: 0.5, touched_existing_files: 8, rewritten_lines: 900, basis: "b" };
+const TINY = { rewrite_ratio: 0.9, touched_existing_files: 12, rewritten_lines: 20, basis: "b" };
+const ZEROED = { rewrite_ratio: 0, touched_existing_files: 0, rewritten_lines: 0, basis: "b" };
+
+// One run of a slice whose plan declares `radius`, under gate config `limits`.
+const evaluate = async (radius, limits, answers) => {
+  const out = await runWave(radiusArgs(S1(), limits, answers),
+                            planThenStop(planWithRadius(radius)));
+  return out.results[0];
+};
+const radiusEvents = (r) => r.events.filter((e) => e.type === "refactor-radius");
+const only = async (radius, limits, answers) => {
+  const events = radiusEvents(await evaluate(radius, limits, answers));
+  assert.equal(events.length, 1);
+  return events[0];
+};
+
+test("a within-ceiling plan still emits exactly one evaluation event", async () => {
+  const ev = await only(SMALL, RADIUS_DEFAULTS);
+  assert.equal(ev.scope, "s1");
+  assert.equal(ev.payload.state, "WITHIN");
+  assert.deepEqual(ev.payload.exceeded, []);
+});
+
+test("the no-fire event carries the numbers AND the thresholds compared", async () => {
+  const ev = await only(SMALL, RADIUS_DEFAULTS);
+  assert.equal(ev.payload.measured.rewrite_ratio, 0.1);
+  assert.equal(ev.payload.measured.touched_existing_files, 2);
+  assert.equal(ev.payload.measured.rewritten_lines, 40);
+  assert.equal(ev.payload.thresholds.max_rewrite_ratio, 0.5);
+  assert.equal(ev.payload.thresholds.max_touched_existing_files, 8);
+  assert.equal(ev.payload.thresholds.min_rewritten_lines, 150);
+});
+
+test("an unmeasured plan records three nulls and never a zero", async () => {
+  const ev = await only(undefined, RADIUS_DEFAULTS);
+  assert.equal(ev.payload.state, "NOT_MEASURED");
+  assert.deepEqual(ev.payload.measured,
+    { rewrite_ratio: null, touched_existing_files: null, rewritten_lines: null });
+});
+
+test("declared zeros are recorded as zeros and stay a measurement", async () => {
+  const ev = await only(ZEROED, RADIUS_DEFAULTS);
+  assert.equal(ev.payload.state, "WITHIN");
+  assert.equal(ev.payload.measured.rewrite_ratio, 0);
+});
+
+test("an unconfigured ctx records the absence with null thresholds", async () => {
+  const ev = await only(BIG, undefined);
+  assert.equal(ev.payload.state, "NOT_CONFIGURED");
+  assert.equal(ev.payload.thresholds, null);
+});
+
+test("a disabled block records the evaluation it declined to make", async () => {
+  const ev = await only(BIG, { ...RADIUS_DEFAULTS, enabled: false });
+  assert.equal(ev.payload.state, "DISABLED");
+  assert.equal(ev.payload.measured.rewrite_ratio, 0.9);
+});
+
+test("a plan exactly at both ceilings records WITHIN, not a breach", async () => {
+  const ev = await only(AT_CEILING, RADIUS_DEFAULTS);
+  assert.equal(ev.payload.state, "WITHIN");
+});
+
+test("a breach under the noise floor is recorded and does not halt", async () => {
+  const result = await evaluate(TINY, RADIUS_DEFAULTS);
+  const ev = radiusEvents(result)[0];
+  assert.equal(ev.payload.state, "BELOW_FLOOR");
+  assert.deepEqual(ev.payload.exceeded, ["rewrite_ratio", "touched_existing_files"]);
+  assert.equal(result.escalations.filter((e) => e.trigger === "refactor-scope").length, 0);
+});
+
+test("the payload leads with a human-readable summary for the decisions log", async () => {
+  const ev = await only(BIG, RADIUS_DEFAULTS);
+  assert.equal(Object.keys(ev.payload)[0], "summary");
+  assert.ok(ev.payload.summary.startsWith("refactor radius EXCEEDED"));
+});
+
+test("a SPLIT plan is discarded before the gate and emits no evaluation", async () => {
+  // Two real children, not an empty array: a childless SPLIT is now itself an
+  // escalation (usableSplit), which would end this slice before the question
+  // under test - whether the radius gate runs on a SPLIT - could be asked.
+  const child = { goal: "half", files: ["a.py"], subsystems: ["x"], internal_deps: [] };
+  const split = { status: "SPLIT", split: { children: [child, child] } };
+  const out = await runWave(radiusArgs(S1(), RADIUS_DEFAULTS), planThenStop(split));
+  assert.equal(out.results[0].status, "SPLIT");
+  assert.equal(radiusEvents(out.results[0]).length, 0);
+});
+
+// ── the halt itself ───────────────────────────────────────────────────────
+const OPTION_LABELS = [
+  "Narrow the plan to the smallest change that meets the goal",
+  "Approve the rewrite as planned",
+  "Carve the rewrite out into its own slice",
+];
+const record = (r) => r.escalations.find((e) => e.trigger === "refactor-scope");
+
+test("a measured breach halts the slice at plan time with the new trigger", async () => {
+  const result = await evaluate(BIG, RADIUS_DEFAULTS);
+  assert.equal(result.status, "ESCALATED");
+  assert.equal(result.tasks_completed, 0);
+  assert.equal(record(result).id, "s1:refactor-scope");
+  assert.equal(record(result).status, "OPEN");
+  assert.equal(radiusEvents(result)[0].payload.state, "EXCEEDED");
+});
+
+test("the halt happens before any implementation dispatch is spent", async () => {
+  // planThenStop throws on every non-plan dispatch: reaching the critique
+  // stage would surface as an internal-error record instead of this one.
+  const result = await evaluate(BIG, RADIUS_DEFAULTS);
+  assert.equal(result.escalations.length, 1);
+  assert.equal(result.agents_used, 1);
+});
+
+test("the record offers the three trade-offs, narrowing recommended", async () => {
+  const rec = record(await evaluate(BIG, RADIUS_DEFAULTS));
+  assert.deepEqual(rec.options.map((o) => o.label), OPTION_LABELS);
+  assert.equal(rec.options[0].recommended, true);
+  assert.equal(rec.options[1].recommended, undefined);
+  assert.equal(rec.options[2].recommended, undefined);
+  rec.options.forEach((o) => assert.ok(o.detail.includes("CONTROLLER")));
+});
+
+test("the context states the numbers, the ceilings and the proxy limit", async () => {
+  const rec = record(await evaluate(BIG, RADIUS_DEFAULTS));
+  assert.ok(rec.context.includes("0.9"));
+  assert.ok(rec.context.includes("0.5"));
+  assert.ok(rec.context.includes("12"));
+  assert.ok(rec.context.includes("not a measured diff"));
+  assert.ok(rec.title.includes("rewrite_ratio"));
+});
+
+test("an answered slice proceeds instead of re-raising the same question", async () => {
+  const answers = { "s1:refactor-scope": "approved, go ahead" };
+  const result = await evaluate(BIG, RADIUS_DEFAULTS, answers);
+  assert.equal(record(result), undefined);
+  assert.equal(radiusEvents(result)[0].payload.state, "EXCEEDED");
+  assert.equal(radiusEvents(result)[0].payload.suppressed_by_answer, true);
+});
+
+test("a no-fire evaluation is never marked as suppressed by an answer", async () => {
+  const ev = await only(SMALL, RADIUS_DEFAULTS);
+  assert.equal(ev.payload.suppressed_by_answer, undefined);
+});
+
+test("the human answer reaches the planner prompt that raised the question", async () => {
+  const seen = [];
+  const agent = async (prompt) => { seen.push(prompt); throw new Error("STOP"); };
+  await runWave(radiusArgs(S1(), RADIUS_DEFAULTS,
+    { "s1:refactor-scope": "NARROW-IT-DOWN" }), { agent });
+  assert.ok(seen[0].includes("NARROW-IT-DOWN"));
+  assert.ok(seen[0].includes('HUMAN ANSWER to your earlier "refactor-scope" escalation'));
+});
+
+// ── the planner's basis, display-only ─────────────────────────────────────
+// `basis` is the planner's one-sentence account of HOW it counted. The human
+// weighing "approve / narrow / carve out" cannot weigh a number whose
+// derivation is invisible, so it must reach both the event and the record.
+// It is DISPLAY-ONLY: no verdict may move on it, which is why the two tests
+// below pin the same state with and without it.
+const BASIS_TEXT = "counted with git diff --stat against main";
+const WITH_BASIS = { ...BIG, basis: BASIS_TEXT };
+const NO_BASIS = { rewrite_ratio: 0.9, touched_existing_files: 12, rewritten_lines: 900 };
+
+test("the radius event carries the planner's basis sentence verbatim", async () => {
+  const ev = await only(WITH_BASIS, RADIUS_DEFAULTS);
+  assert.equal(ev.payload.basis, BASIS_TEXT);
+});
+
+test("an omitted basis is recorded as null and never as an empty string", async () => {
+  const ev = await only(NO_BASIS, RADIUS_DEFAULTS);
+  assert.equal(ev.payload.basis, null);
+  assert.equal(ev.payload.state, "EXCEEDED");
+});
+
+test("a non-string basis is dropped rather than interpolated into the record", async () => {
+  const ev = await only({ ...BIG, basis: 17 }, RADIUS_DEFAULTS);
+  assert.equal(ev.payload.basis, null);
+});
+
+test("the escalation context tells the human how the planner counted", async () => {
+  const rec = record(await evaluate(WITH_BASIS, RADIUS_DEFAULTS));
+  assert.ok(rec.context.includes(BASIS_TEXT));
+});
+
+test("an unstated basis says so in the record instead of printing null", async () => {
+  const rec = record(await evaluate(NO_BASIS, RADIUS_DEFAULTS));
+  assert.ok(rec.context.includes("not stated"));
+  assert.equal(rec.context.includes("undefined"), false);
+});
+
+test("the basis never moves a verdict: the same numbers reach the same state", async () => {
+  const withB = await only(WITH_BASIS, RADIUS_DEFAULTS);
+  const withoutB = await only(NO_BASIS, RADIUS_DEFAULTS);
+  assert.equal(withB.payload.state, withoutB.payload.state);
+  assert.deepEqual(withB.payload.exceeded, withoutB.payload.exceeded);
+  assert.deepEqual(withB.payload.measured, withoutB.payload.measured);
+});
+
+// ── an answer only counts when it says something ──────────────────────────
+// The same answers map reaches the planner through answerFor/latestAnswer,
+// which both require a TRUTHY value. Gating the halt on KEY presence let an
+// empty or null entry disarm the halt permanently for that slice while
+// injecting nothing into the planner's prompt: the question vanished and the
+// answer never arrived. resolveCouncilObjection's `if (latestAnswer(...))`
+// is the precedent this now matches.
+const EMPTY_ANSWERS = [
+  { "s1:refactor-scope": "" },
+  { "s1:refactor-scope": null },
+];
+
+test("an empty answer value does not disarm the halt", async () => {
+  const result = await evaluate(BIG, RADIUS_DEFAULTS, EMPTY_ANSWERS[0]);
+  assert.equal(result.status, "ESCALATED");
+  assert.equal(record(result).trigger, "refactor-scope");
+});
+
+test("a null answer value does not disarm the halt", async () => {
+  const result = await evaluate(BIG, RADIUS_DEFAULTS, EMPTY_ANSWERS[1]);
+  assert.equal(result.status, "ESCALATED");
+  assert.equal(record(result).trigger, "refactor-scope");
+});
+
+test("an empty answer leaves no suppression claim on the event either", async () => {
+  const result = await evaluate(BIG, RADIUS_DEFAULTS, EMPTY_ANSWERS[0]);
+  assert.equal(radiusEvents(result)[0].payload.suppressed_by_answer, undefined);
+});
+
+test("an empty round-1 answer still lets a real round-2 answer disarm the halt", async () => {
+  // The empty key still counts a ROUND (escRound reads keys, not values), so
+  // the re-raised record is round 2 and its answer is keyed with the suffix.
+  const answers = { "s1:refactor-scope": "", "s1:refactor-scope:2": "approved" };
+  const result = await evaluate(BIG, RADIUS_DEFAULTS, answers);
+  assert.equal(record(result), undefined);
+});
+
+// ── a configured ceiling that cannot be compared ──────────────────────────
+// A mistyped ceiling ("0.5" as a string, or a key spelled wrong) survives
+// refactorLimits as null. WITHIN then claimed "every declared number is at or
+// under its ceiling" — a claim no comparison supported — so the gate reported
+// success while silently never firing again. That is exactly the invisible
+// permanent narrowing this repo's knowledge graph already names.
+const NO_CEILINGS = {
+  enabled: true, max_rewrite_ratio: null,
+  max_touched_existing_files: null, min_rewritten_lines: 150,
+};
+const STRING_CEILINGS = {
+  enabled: true, max_rewrite_ratio: "0.5",
+  max_touched_existing_files: "8", min_rewritten_lines: 150,
+};
+
+test("a configured block with no usable ceiling never claims a plan is within one", async () => {
+  const ev = await only(BIG, NO_CEILINGS);
+  assert.equal(ev.payload.state, "NO_USABLE_CEILING");
+  assert.equal(ev.payload.state === "WITHIN", false);
+});
+
+test("string ceilings are not ceilings and are reported as unusable", async () => {
+  const ev = await only(BIG, STRING_CEILINGS);
+  assert.equal(ev.payload.state, "NO_USABLE_CEILING");
+  assert.equal(ev.payload.thresholds.max_rewrite_ratio, null);
+});
+
+test("the unusable-ceiling summary says plainly that nothing was compared", async () => {
+  const ev = await only(BIG, NO_CEILINGS);
+  assert.ok(ev.payload.summary.startsWith("refactor radius NO_USABLE_CEILING"));
+  assert.ok(ev.payload.summary.includes("nothing was compared"));
+});
+
+test("an unusable ceiling fails open: the slice proceeds and raises nothing", async () => {
+  const result = await evaluate(BIG, NO_CEILINGS);
+  assert.equal(record(result), undefined);
+  assert.deepEqual(radiusEvents(result)[0].payload.exceeded, []);
+});
+
+test("one usable ceiling out of two is still a usable configuration", async () => {
+  const half = { ...RADIUS_DEFAULTS, max_rewrite_ratio: null };
+  const ev = await only(BIG, half);
+  assert.equal(ev.payload.state, "EXCEEDED");
+  assert.deepEqual(ev.payload.exceeded, ["touched_existing_files"]);
+});
+
+test("a missing noise floor alone never makes a ceiling unusable", async () => {
+  const ev = await only(BIG, { ...RADIUS_DEFAULTS, min_rewritten_lines: null });
+  assert.equal(ev.payload.state, "EXCEEDED");
+});
+
+// ── suppression is a fire that did not happen ─────────────────────────────
+// The flag was set from `answered` alone, so an ordinary post-answer success —
+// human says narrow it, planner narrows, verdict WITHIN — emitted an event
+// claiming a suppression that never occurred, and a reader auditing which
+// halts a human had waived would have counted it.
+const APPROVED = { "s1:refactor-scope": "approved, go ahead" };
+
+test("a within-ceiling replan after an answer claims no suppression", async () => {
+  const ev = await only(SMALL, RADIUS_DEFAULTS, APPROVED);
+  assert.equal(ev.payload.state, "WITHIN");
+  assert.equal(ev.payload.suppressed_by_answer, undefined);
+});
+
+test("a below-floor breach after an answer claims no suppression either", async () => {
+  const ev = await only(TINY, RADIUS_DEFAULTS, APPROVED);
+  assert.equal(ev.payload.state, "BELOW_FLOOR");
+  assert.equal(ev.payload.suppressed_by_answer, undefined);
+});
+
+test("an unconfigured evaluation after an answer claims no suppression", async () => {
+  const ev = await only(BIG, undefined, APPROVED);
+  assert.equal(ev.payload.state, "NOT_CONFIGURED");
+  assert.equal(ev.payload.suppressed_by_answer, undefined);
+});
+
+test("only a real breach an answer waived is marked suppressed", async () => {
+  const ev = await only(BIG, RADIUS_DEFAULTS, APPROVED);
+  assert.equal(ev.payload.state, "EXCEEDED");
+  assert.equal(ev.payload.suppressed_by_answer, true);
+});
+
+test("the suppression key is absent rather than false when nothing was suppressed", async () => {
+  const ev = await only(SMALL, RADIUS_DEFAULTS, APPROVED);
+  assert.equal(Object.keys(ev.payload).includes("suppressed_by_answer"), false);
+});
diff --git a/plugins/spec-loop/scripts/slice_wave_replan.test.mjs b/plugins/spec-loop/scripts/slice_wave_replan.test.mjs
new file mode 100644
index 0000000..e6bf432
--- /dev/null
+++ b/plugins/spec-loop/scripts/slice_wave_replan.test.mjs
@@ -0,0 +1,154 @@
+// slice_wave_replan.test.mjs — the guards on optional agent-return fields and the
+// re-check of a plan revised after a council OBJECT, EXECUTED.
+// HONEST LIMITS: this drives deterministic control flow only, against the mock
+// sandbox in slice_wave_harness.mjs; the real Workflow-host seam stays unverified.
+// It does NOT cover the plan-time refactor-radius gate on a revised plan - that
+// re-evaluation is a known, deliberate gap (see the workflow comment on
+// acceptRevisedPlan). Third harness module because slice_wave_behaviour.test.mjs
+// sits at the quality gate's 300-non-blank-line class_lines ceiling.
+
+import test from "node:test";
+import assert from "node:assert/strict";
+import {
+  runWave, waveArgs, sliceFixture, councilSandbox, pipelineWith,
+  ONE_TASK_PLANNED, SPLIT_OK, SPLIT_EMPTY, ESCALATE_BARE, ESCALATE_FULL,
+  OBJECTION_FIXABLE, RECHECK_CLEAN, RECHECK_OBJECT, RECHECK_SAFETY,
+} from "./slice_wave_harness.mjs";
+
+const T1 = () => [sliceFixture("s1", 1)];
+const runPlan = async (planReturn) => {
+  const out = await runWave(waveArgs(T1()), councilSandbox({ plan: planReturn }));
+  return out.results[0];
+};
+
+test("a SPLIT plan carrying children still returns a SPLIT result", async () => {
+  const r = await runPlan(SPLIT_OK);
+  assert.equal(r.status, "SPLIT");
+  assert.equal(r.split.children.length, 2);
+});
+
+test("a SPLIT plan with no split object escalates instead of shipping undefined", async () => {
+  const r = await runPlan(SPLIT_EMPTY);
+  assert.equal(r.status, "ESCALATED");
+  assert.equal(r.escalations.length, 1);
+  assert.equal(r.escalations[0].trigger, "ambiguity");
+  assert.match(r.escalations[0].title, /SPLIT/);
+});
+
+test("an ESCALATE plan with a readable record keeps the planner's own trigger", async () => {
+  const r = await runPlan(ESCALATE_FULL);
+  assert.equal(r.status, "ESCALATED");
+  assert.equal(r.escalations[0].trigger, "material-assumption");
+  assert.equal(r.escalations[0].title, "which store");
+});
+
+test("an ESCALATE plan with no escalation object still produces a usable record", async () => {
+  const r = await runPlan(ESCALATE_BARE);
+  assert.equal(r.status, "ESCALATED");
+  const rec = r.escalations[0];
+  assert.equal(rec.trigger, "ambiguity");
+  assert.equal(typeof rec.title, "string");
+  assert.ok(rec.question.length > 0);
+  assert.ok(rec.options.length > 0);
+});
+
+test("a re-review prompt never interpolates undefined when the fixer omits commits", async () => {
+  const sandbox = pipelineWith({
+    "fix:1": { status: "DONE", touched_files: ["a.py"], addressed: ["r0-f1"], refuted: [] },
+  });
+  await runWave(waveArgs([sliceFixture("s1", 2)]), sandbox);
+  const rr = sandbox.seen.find((d) => d.label === "s1:re-review:1");
+  assert.ok(rr, "the re-review dispatch must still happen");
+  assert.equal(rr.prompt.includes("--base undefined"), false);
+  assert.equal(rr.prompt.includes("--head undefined"), false);
+  assert.match(rr.prompt, /--base 0000000/);
+});
+
+// ── The post-OBJECT replan re-check ───────────────────────────────────────
+// A tier-2 slice runs the critique stage; the council OBJECTs fixably, the
+// planner returns a revision, and the question every test below asks is what
+// the wave does with that revision.
+const T2 = () => [sliceFixture("s1", 2)];
+const objectThenReplan = async (revised, recheck) => {
+  const sandbox = councilSandbox({
+    plan: ONE_TASK_PLANNED,
+    "critic:full-council": OBJECTION_FIXABLE,
+    replan: revised,
+    ...(recheck === undefined ? {} : { "critic:replan": recheck }),
+  });
+  const out = await runWave(waveArgs(T2()), sandbox);
+  return { r: out.results[0], seen: sandbox.seen };
+};
+
+test("a revised plan is re-critiqued before the slice proceeds on it", async () => {
+  const { seen } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_CLEAN);
+  assert.deepEqual(seen.slice(0, 4), ["plan", "critic:full-council", "replan", "critic:replan"]);
+});
+
+test("a clean re-critique lets the slice proceed to its tasks", async () => {
+  const { seen } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_CLEAN);
+  assert.equal(seen[4], "task:t1");
+});
+
+test("a re-critique that OBJECTS escalates instead of proceeding", async () => {
+  const { r, seen } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_OBJECT);
+  assert.equal(r.status, "ESCALATED");
+  assert.equal(r.escalations[0].trigger, "council-objection");
+  assert.equal(seen.includes("task:t1"), false);
+});
+
+test("the escalation carries the reason the REVISION was rejected", async () => {
+  const { r } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_OBJECT);
+  assert.equal(r.escalations[0].context, "the revision still skips the migration test");
+});
+
+test("an unreadable re-critique fails closed into the same escalation", async () => {
+  const { r } = await objectThenReplan(ONE_TASK_PLANNED, null);
+  assert.equal(r.status, "ESCALATED");
+  assert.equal(r.escalations[0].trigger, "council-objection");
+});
+
+test("a safety flag raised only on the re-check still blocks and is titled SAFETY", async () => {
+  const { r } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_SAFETY);
+  assert.equal(r.status, "ESCALATED");
+  assert.match(r.escalations[0].title, /^SAFETY — /);
+});
+
+// RECHECK_SAFETY carries no `objection` block (schema-legal: CRITIQUE only
+// requires verdict/safety/concerns) and its safety reason deliberately differs
+// from OBJECTION_FIXABLE's objection reason, so this catches a silent fallback
+// to the stale, pre-replan objection instead of the re-check's own new risk.
+test("the escalation describes the re-check's OWN safety reason, not the stale original objection", async () => {
+  const { r } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_SAFETY);
+  assert.match(r.escalations[0].title, /the revision drops the pre-migration backup/);
+  assert.equal(r.escalations[0].context, "the revision drops the pre-migration backup");
+  assert.equal(r.escalations[0].context.includes("migration test"), false);
+});
+
+test("a re-check safety reason is carried in the replan-recheck event payload", async () => {
+  const { r } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_SAFETY);
+  const ev = r.events.find((e) => e.type === "replan-recheck");
+  assert.equal(ev.payload.safety_reason, "the revision drops the pre-migration backup");
+});
+
+test("a replan that returns no plan escalates without spending a re-critique", async () => {
+  const { r, seen } = await objectThenReplan(null, RECHECK_CLEAN);
+  assert.equal(r.status, "ESCALATED");
+  assert.equal(seen.includes("critic:replan"), false);
+});
+
+test("a replan that returns ESCALATE is not accepted as a plan", async () => {
+  const { r, seen } = await objectThenReplan(ESCALATE_BARE, RECHECK_CLEAN);
+  assert.equal(r.status, "ESCALATED");
+  assert.equal(seen.includes("critic:replan"), false);
+});
+
+test("every re-check records exactly one replan-recheck event with its verdict", async () => {
+  const { r } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_OBJECT);
+  const evs = r.events.filter((e) => e.type === "replan-recheck");
+  assert.equal(evs.length, 1);
+  assert.equal(evs[0].scope, "s1");
+  assert.equal(evs[0].payload.verdict, "OBJECT");
+  assert.equal(evs[0].payload.safety, false);
+  assert.equal(evs[0].payload.accepted, false);
+});
diff --git a/plugins/spec-loop/scripts/test_doctrine_refactor_scope.py b/plugins/spec-loop/scripts/test_doctrine_refactor_scope.py
new file mode 100644
index 0000000..dedd98d
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_doctrine_refactor_scope.py
@@ -0,0 +1,182 @@
+#!/usr/bin/env python3
+"""Contract checks for the doctrine surfaces of the refactor-scope trigger.
+
+The gate itself is JavaScript and already pinned by
+test_slice_wave_contract_radius.py. This module pins the three PROSE
+surfaces a human or an agent actually reads - the escalation-gate skill,
+the slice-planner agent, and the controller command - against the shipped
+behaviour, because prose is a live plugin surface and drift in it is
+silent. The precedent is TestTheSkillDescribesTheLostSliceAsk in
+test_slice_wave_contract.py, which exists because exactly this drift
+happened once already.
+
+Honest limit: these are substring assertions over collapsed prose. They
+prove a sentence is present and that its superseded form is gone. They
+prove nothing about whether an agent obeys it, and they are not a
+behavioural test of the gate.
+
+A separate module rather than a class in an existing one:
+slice_wave_contract_base.py sits at 299 non-blank lines and
+test_slice_wave_contract_radius.py at 301, both at or over the quality
+gate's 300-line class_lines threshold.
+
+Usage:
+    python3 -m unittest discover -s plugins/spec-loop/scripts \\
+        -p 'test_doctrine_refactor_scope.py'
+"""
+
+import re
+import sys
+import unittest
+from pathlib import Path
+
+sys.path.insert(0, str(Path(__file__).resolve().parent))
+
+from slice_wave_contract_base import COMMAND_MD  # noqa: E402
+
+PLUGIN_ROOT = Path(__file__).resolve().parents[1]
+SKILL_MD = PLUGIN_ROOT / "skills" / "escalation-gate" / "SKILL.md"
+PLANNER_MD = PLUGIN_ROOT / "agents" / "slice-planner.md"
+
+
+def prose(path):
+    """One file's text with every whitespace run collapsed to a space. (PURE)"""
+    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
+
+
+# ---- the escalation-gate skill: six triggers, over-scope still not one ----
+
+SIX_HEADING = "### SURFACE to human (only these six triggers)"
+SIX_COUNT = "There are exactly six JUDGMENT triggers"
+SIX_BAR = "exactly the six triggers above"
+TRIGGER_NAME = "**Refactor scope** (`refactor-scope`)"
+TRIGGER_ARITHMETIC = "raised by the workflow's own arithmetic"
+TRIGGER_MEASURED = "an absent or unmeasured number is never a breach"
+OVER_SCOPE_KEPT = "raises no escalation, changes no verdict, suppresses no split"
+OVER_SCOPE_NOT_ONE = "an over-scope flag is not one of them"
+STALE_FIVE_HEADING = "only these five triggers"
+STALE_FIVE_COUNT = "exactly five JUDGMENT triggers"
+STALE_FIVE_BAR = "exactly the five triggers above"
+STALE_NOT_SIXTH = "an over-scope flag is not a sixth"
+STALE_FIVE_FORMS = (
+    STALE_FIVE_HEADING,
+    STALE_FIVE_COUNT,
+    STALE_FIVE_BAR,
+    STALE_NOT_SIXTH,
+)
+
+
+class TestTheSkillCountsSixJudgmentTriggers(unittest.TestCase):
+    """Three places in this file stated FIVE and one of them explicitly
+    denied a sixth. refactor-scope makes six. The over-scope flag must stay
+    excluded on its own separate grounds - it is a record, not a count."""
+
+    def setUp(self):
+        self.text = prose(SKILL_MD)
+
+    def test_all_three_five_trigger_statements_now_say_six(self):
+        for pin in (SIX_HEADING, SIX_COUNT, SIX_BAR):
+            self.assertIn(pin, self.text)
+
+    def test_no_superseded_five_trigger_sentence_survives(self):
+        for stale in STALE_FIVE_FORMS:
+            self.assertNotIn(stale, self.text)
+
+    def test_the_sixth_trigger_is_named_and_described_as_arithmetic(self):
+        self.assertIn(TRIGGER_NAME, self.text)
+        self.assertIn(TRIGGER_ARITHMETIC, self.text)
+
+    def test_the_sixth_trigger_fires_only_on_a_measured_breach(self):
+        self.assertIn(TRIGGER_MEASURED, self.text)
+
+    def test_the_over_scope_flag_is_still_a_record_and_still_not_a_trigger(self):
+        self.assertIn(OVER_SCOPE_KEPT, self.text)
+        self.assertIn(OVER_SCOPE_NOT_ONE, self.text)
+
+
+# ---- the planner agent: declares numbers, never a verdict ----
+
+PLANNER_SECTION = "## Declaring the refactor radius"
+PLANNER_THREE = "`rewrite_ratio`"
+PLANNER_FILES = "`touched_existing_files`"
+PLANNER_LINES = "`rewritten_lines`"
+PLANNER_BASIS = "`basis`"
+PLANNER_NO_VERDICT = "Report numbers, never a verdict"
+PLANNER_NO_ZERO = "Omit any number you genuinely cannot estimate rather than guessing"
+PLANNER_ABSENT = "An absent number is read as unmeasured and never as a zero"
+PLANNER_ANSWER = "already settled: plan to it and do not re-raise the question"
+PLANNER_LAST_TWO = ("## Statuses", "## Untrusted-data guard")
+
+
+class TestThePlannerIsToldToDeclareItsOwnRadius(unittest.TestCase):
+    """The workflow asks for these numbers in its dispatch prompt, but the
+    agent's own doctrine is what a planner reads when it decides HOW to
+    count them - and an invented zero reads as a measured 'no rewrite',
+    which silently disarms the ceiling."""
+
+    def setUp(self):
+        self.text = prose(PLANNER_MD)
+
+    def test_the_agent_has_a_section_naming_all_four_declared_fields(self):
+        self.assertIn(PLANNER_SECTION, self.text)
+        for field in (PLANNER_THREE, PLANNER_FILES, PLANNER_LINES, PLANNER_BASIS):
+            self.assertIn(field, self.text)
+
+    def test_the_planner_is_forbidden_from_reaching_its_own_verdict(self):
+        self.assertIn(PLANNER_NO_VERDICT, self.text)
+
+    def test_an_unknown_is_omitted_and_never_guessed_as_a_zero(self):
+        self.assertIn(PLANNER_NO_ZERO, self.text)
+        self.assertIn(PLANNER_ABSENT, self.text)
+
+    def test_an_answered_refactor_scope_question_is_not_re_raised(self):
+        self.assertIn(PLANNER_ANSWER, self.text)
+
+    def test_the_agent_body_keeps_its_two_mandatory_closing_sections_last(self):
+        raw = PLANNER_MD.read_text(encoding="utf-8")
+        statuses, guard = (raw.index(h) for h in PLANNER_LAST_TWO)
+        self.assertLess(raw.index(PLANNER_SECTION), statuses)
+        self.assertLess(statuses, guard)
+
+    def test_the_agent_file_still_carries_no_json_schema_block(self):
+        self.assertEqual(PLANNER_MD.read_text(encoding="utf-8").count("```json"), 0)
+
+
+# ---- the controller command: six triggers, and the answer's one route ----
+
+CMD_SIX = "`escalation-gate` six-trigger test"
+CMD_STALE_FIVE = "`escalation-gate` five-trigger test"
+CMD_ANSWER_KEY = '`answers["<slice-id>:refactor-scope"]`'
+CMD_ARITHMETIC = "the one trigger the wave raises from its own arithmetic"
+CMD_NO_OTHER_LEVER = "there is no other lever"
+CMD_CTX_KEY = "refactor_radius (the merged block verbatim from --print-config"
+CMD_ONE_DOOR = "--print-config"
+
+
+class TestTheControllerCarriesTheSixthTriggerEndToEnd(unittest.TestCase):
+    """The controller is the only layer that can ask a human, so its own
+    trigger count is load-bearing; and refactor-scope is the only trigger
+    whose answer is the sole thing that unblocks the slice, since no
+    re-dispatch clears a breach the arithmetic will just recompute."""
+
+    def setUp(self):
+        self.text = prose(COMMAND_MD)
+
+    def test_the_controller_applies_the_six_trigger_test(self):
+        self.assertIn(CMD_SIX, self.text)
+        self.assertNotIn(CMD_STALE_FIVE, self.text)
+
+    def test_the_answer_is_keyed_by_the_refactor_scope_id_verbatim(self):
+        self.assertIn(CMD_ANSWER_KEY, self.text)
+
+    def test_the_command_names_the_trigger_as_the_workflows_own_arithmetic(self):
+        self.assertIn(CMD_ARITHMETIC, self.text)
+        self.assertIn(CMD_NO_OTHER_LEVER, self.text)
+
+    def test_the_ctx_key_still_travels_from_the_one_config_door(self):
+        self.assertIn(CMD_ONE_DOOR, self.text)
+        self.assertIn(CMD_CTX_KEY, self.text)
+
+
+if __name__ == "__main__":  # pragma: no cover
+    unittest.main()
diff --git a/plugins/spec-loop/scripts/test_quality_gate.py b/plugins/spec-loop/scripts/test_quality_gate.py
index 4cab26d..1b72581 100644
--- a/plugins/spec-loop/scripts/test_quality_gate.py
+++ b/plugins/spec-loop/scripts/test_quality_gate.py
@@ -200,10 +200,32 @@ def longer_scan(text, lang):
     so the caller's line count no longer matches its input. Named at module
     level for the same paren-alignment reason as `unmasked`."""
     return text + "\nextra"
 
 
+# refactor_radius config fixtures. A multi-line dict literal passed inline to
+# a helper call forces a deep hanging indent when the continuation aligns with
+# the opening brace, and the gate's nesting-depth heuristic reads that
+# indentation as block nesting -- so these live at module level for the same
+# reason as the fixtures above.
+OVERLAY_SIBLINGS_BASE_RADIUS = {
+    "refactor_radius": {
+        "enabled": True,
+        "max_rewrite_ratio": 0.4,
+        "max_touched_existing_files": 6,
+        "min_rewritten_lines": 120,
+    },
+}
+
+OVERLAY_SIBLINGS_EXPECTED_RADIUS = {
+    "enabled": True,
+    "max_rewrite_ratio": 0.3,
+    "max_touched_existing_files": 6,
+    "min_rewritten_lines": 120,
+}
+
+
 # --------------------------------------------------------------------------
 # parse_diff — pure, embedded fixtures
 # --------------------------------------------------------------------------
 
 class TestParseDiff(unittest.TestCase):
@@ -329,10 +351,47 @@ class TestLoadConfig(unittest.TestCase):
             path = fh.name
         self.addCleanup(os.unlink, path)
         with self.assertRaises(qg.GateError):
             qg.load_config(path)
 
+    def test_defaults_carry_the_full_default_on_refactor_radius_block(self):
+        cfg, src = qg.load_config(None)
+        self.assertEqual(src, "defaults")
+        self.assertEqual(cfg["refactor_radius"], qg.DEFAULT_REFACTOR_RADIUS)
+        self.assertTrue(cfg["refactor_radius"]["enabled"])
+
+    def test_a_partial_refactor_radius_block_keeps_its_unmentioned_sibling_keys(self):
+        path = self._tmp_json({"refactor_radius": {"max_rewrite_ratio": 0.25}})
+        cfg, _ = qg.load_config(path)
+        radius = cfg["refactor_radius"]
+        default = qg.DEFAULT_REFACTOR_RADIUS
+        self.assertEqual(radius["max_rewrite_ratio"], 0.25)
+        self.assertEqual(
+            radius["max_touched_existing_files"],
+            default["max_touched_existing_files"])
+        self.assertEqual(
+            radius["min_rewritten_lines"], default["min_rewritten_lines"])
+        self.assertTrue(radius["enabled"])
+
+    def test_a_refactor_radius_block_can_be_switched_off_by_the_operator(self):
+        path = self._tmp_json({"refactor_radius": {"enabled": False}})
+        cfg, _ = qg.load_config(path)
+        radius = cfg["refactor_radius"]
+        self.assertFalse(radius["enabled"])
+        self.assertEqual(
+            radius["max_rewrite_ratio"],
+            qg.DEFAULT_REFACTOR_RADIUS["max_rewrite_ratio"])
+
+    def test_a_non_object_refactor_radius_in_the_config_is_a_hard_error(self):
+        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
+            json.dump({"refactor_radius": [0.5]}, fh)
+            path = fh.name
+        self.addCleanup(os.unlink, path)
+        with self.assertRaises(qg.GateError) as ctx:
+            qg.load_config(path)
+        self.assertIn("refactor_radius", str(ctx.exception))
+
     def _tmp_json(self, obj):
         with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
             json.dump(obj, fh)
         self.addCleanup(os.unlink, fh.name)
         return fh.name
@@ -378,10 +437,58 @@ class TestLoadConfig(unittest.TestCase):
             fh.write("{not json")
         self.addCleanup(os.unlink, fh.name)
         with self.assertRaises(qg.GateError):
             qg.load_config(base, fh.name)
 
+    def test_an_overlay_tuning_one_radius_number_does_not_drop_its_siblings(self):
+        base = self._tmp_json(OVERLAY_SIBLINGS_BASE_RADIUS)
+        overlay = self._tmp_json({"refactor_radius": {"max_rewrite_ratio": 0.3}})
+        cfg, src = qg.load_config(base, overlay)
+        self.assertEqual(src, "loaded+overlay")
+        self.assertEqual(cfg["refactor_radius"], OVERLAY_SIBLINGS_EXPECTED_RADIUS)
+
+    def test_an_overlay_radius_key_over_a_global_without_the_block_keeps_defaults(self):
+        base = self._tmp_json({"thresholds": {"method_lines": 40}})
+        overlay = self._tmp_json({"refactor_radius": {"max_touched_existing_files": 4}})
+        cfg, _ = qg.load_config(base, overlay)
+        radius = cfg["refactor_radius"]
+        default = qg.DEFAULT_REFACTOR_RADIUS
+        self.assertEqual(radius["max_touched_existing_files"], 4)
+        self.assertEqual(radius["max_rewrite_ratio"], default["max_rewrite_ratio"])
+        self.assertEqual(radius["min_rewritten_lines"], default["min_rewritten_lines"])
+
+    def test_a_non_object_refactor_radius_in_the_overlay_is_a_hard_error(self):
+        base = self._tmp_json({"refactor_radius": {"max_rewrite_ratio": 0.4}})
+        overlay = self._tmp_json({"refactor_radius": 0.9})
+        with self.assertRaises(qg.GateError) as ctx:
+            qg.load_config(base, overlay)
+        self.assertIn("refactor_radius", str(ctx.exception))
+
+    def test_a_non_object_refactor_radius_in_the_base_is_a_hard_error_under_an_overlay(self):
+        base = self._tmp_json({"refactor_radius": ["nope"]})
+        overlay = self._tmp_json({"thresholds": {"method_lines": 40}})
+        with self.assertRaises(qg.GateError):
+            qg.load_config(base, overlay)
+
+    def test_print_config_surfaces_the_merged_refactor_radius_block(self):
+        base = self._tmp_json({"refactor_radius": {"max_touched_existing_files": 6}})
+        overlay = self._tmp_json({"refactor_radius": {"max_rewrite_ratio": 0.3}})
+        proc = subprocess.run(
+            [sys.executable, os.path.join(os.path.dirname(__file__), "quality_gate.py"),
+             "--config", base, "--overlay", overlay, "--print-config"],
+            capture_output=True, text=True,
+        )
+        self.assertEqual(proc.returncode, 0, proc.stderr)
+        out = json.loads(proc.stdout)
+        self.assertEqual(out["source"], "loaded+overlay")
+        self.assertEqual(out["config"]["refactor_radius"], {
+            "enabled": True,
+            "max_rewrite_ratio": 0.3,
+            "max_touched_existing_files": 6,
+            "min_rewritten_lines": qg.DEFAULT_REFACTOR_RADIUS["min_rewritten_lines"],
+        })
+
     def test_print_config_cli(self):
         base = self._tmp_json({"tier3_surfaces": ["**/auth/**"]})
         proc = subprocess.run(
             [sys.executable, os.path.join(os.path.dirname(__file__), "quality_gate.py"),
              "--config", base, "--print-config"],
@@ -398,10 +505,45 @@ class TestLoadConfig(unittest.TestCase):
             capture_output=True, text=True,
         )
         self.assertEqual(proc.returncode, 2)
 
 
+# --------------------------------------------------------------------------
+# Command-doc single-home pin. commands/quality-gate.md is the ONE operator-
+# facing home of the config schema; when it and the defaults disagree, one of
+# them is wrong, and this catches the drift in the same suite that owns the
+# defaults.
+# --------------------------------------------------------------------------
+
+COMMAND_DOC = (Path(__file__).resolve().parents[1] / "commands" / "quality-gate.md")
+
+
+class TestCommandDocDocumentsRefactorRadius(unittest.TestCase):
+    def setUp(self):
+        self.doc = COMMAND_DOC.read_text(encoding="utf-8")
+
+    def test_every_refactor_radius_key_is_named_in_the_command_doc(self):
+        for key in qg.DEFAULT_REFACTOR_RADIUS:
+            with self.subTest(key=key):
+                self.assertIn(key, self.doc)
+
+    def test_the_step_one_key_list_names_the_block(self):
+        step_one = self.doc.split("2. **Choose a quality level**")[0]
+        self.assertIn("refactor_radius", step_one)
+
+    def test_the_written_schema_carries_the_shipped_default_numbers(self):
+        schema = self.doc.split("```json")[1].split("```")[0]
+        self.assertIn('"refactor_radius"', schema)
+        for key, value in qg.DEFAULT_REFACTOR_RADIUS.items():
+            with self.subTest(key=key):
+                literal = {True: "true", False: "false"}.get(value, str(value))
+                self.assertIn(f'"{key}": {literal}', schema)
+
+    def test_the_doc_states_the_block_is_a_declared_proxy_not_a_measured_diff(self):
+        self.assertIn("proxy", self.doc.lower())
+
+
 # --------------------------------------------------------------------------
 # Pure metric primitives
 # --------------------------------------------------------------------------
 
 class TestCountParams(unittest.TestCase):
diff --git a/plugins/spec-loop/scripts/test_run_state.py b/plugins/spec-loop/scripts/test_run_state.py
index de179ec..b3dbfdb 100644
--- a/plugins/spec-loop/scripts/test_run_state.py
+++ b/plugins/spec-loop/scripts/test_run_state.py
@@ -216,10 +216,21 @@ class TestValidateSidecar(unittest.TestCase):
         # unlisted value would falsely fail the sidecar.
         body = sidecar("ESCALATED", escalations=[
             escalation(id="s1:internal-error", trigger="internal-error")])
         self.assertValid(body)
 
+    def test_escalation_trigger_accepts_refactor_scope(self):
+        # The plan-time refactor-scope checkpoint writes a real
+        # EscalationRecord, and validate_escalation runs BEFORE
+        # persist_slice writes anything: a value missing from
+        # ESCALATION_TRIGGERS would cost the slice its sidecar, its
+        # events and its report rather than mislabelling one field.
+        # This drives the membership check, it does not re-list the tuple.
+        body = sidecar("ESCALATED", escalations=[
+            escalation(id="s1:refactor-scope", trigger="refactor-scope")])
+        self.assertValid(body)
+
     def test_escalation_trigger_still_rejects_a_bogus_value(self):
         body = sidecar("ESCALATED", escalations=[escalation(trigger="kaboom")])
         self.assertMentions(body, "trigger")
 
     def test_escalation_needs_options(self):
@@ -809,10 +820,16 @@ class TestDecisionLine(unittest.TestCase):
         payload = {"summary": "use the CSV writer", "over_scope": True}
         line = self.line("decision", payload)
         self.assertIn("DECISION: use the CSV writer", line)
         self.assertNotIn("SCOPE", line)
 
+    def test_refactor_radius_summary(self):
+        summary = "refactor radius EXCEEDED: over the ceiling"
+        payload = {"summary": summary, "state": "EXCEEDED"}
+        line = self.line("refactor-radius", payload)
+        self.assertIn(summary, line)
+
 
 class TestRenderReport(unittest.TestCase):
     def test_done_report(self):
         body = rs.render_report(sidecar())
         self.assertIn("# Slice s1 — DONE", body)
@@ -1030,10 +1047,24 @@ class TestAppendEvent(RunStateTestCase):
         logged = ("DECISION", "DEFERRED", "COUNCIL-VERDICT", "QUALITY-GATE",
                   "INTEGRATION-CHECK", "PHASE5-GATE")
         for marker in logged:
             self.assertIn(marker, body)
 
+    def test_a_refactor_radius_event_renders_a_log_line(self):
+        # A threshold that declines to fire is the silent-exclusion defect
+        # this event exists to prevent, so the NO-FIRE case has to reach the
+        # human surface too, not only the machine-readable events.jsonl.
+        summary = (
+            "refactor radius WITHIN: every declared number "
+            "is at or under its ceiling"
+        )
+        payload = {"summary": summary, "state": "WITHIN"}
+        event = rs.build_event(TS, "s1", "refactor-radius", payload)
+        rs.append_event(self.run_dir, event)
+        body = self.read("decisions-log.md")
+        self.assertIn("REFACTOR-RADIUS: refactor radius WITHIN", body)
+
     def test_escalation_opened_writes_a_full_entry(self):
         event = rs.build_event(TS, "s1", "escalation-opened", escalation())
         rs.append_event(self.run_dir, event)
         body = self.read("escalations.md")
         self.assertIn("# Escalations", body)
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py b/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
index cb8dd55..d71a3d5 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
@@ -274,11 +274,13 @@ class TestTheTriggerEnumAgreesAcrossAllSixHomes(WorkflowSourceTestCase):
     anything and raises on an unrecognised trigger, so a value missing from one
     tuple costs an affected slice its sidecar, its events and its report - not
     a mislabelled field. A one-home edit would otherwise stay fully green. The
     two prose homes are pinned here too: a doc that lists a stale set of
     triggers is what a worker agent reads before it builds a record, so a
-    drifted enumeration produces exactly that rejected write."""
+    drifted enumeration produces exactly that rejected write. The enum is
+    eight values wide as of the refactor-scope trigger; the six homes and the
+    order-sensitivity of this comparison are unchanged."""
 
     def triggers(self):
         return run_state.ESCALATION_TRIGGERS
 
     def test_the_three_python_tuples_are_identical(self):
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_radius.py b/plugins/spec-loop/scripts/test_slice_wave_contract_radius.py
new file mode 100644
index 0000000..cc17fd3
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_radius.py
@@ -0,0 +1,320 @@
+#!/usr/bin/env python3
+"""Contract checks for the plan-time refactor-radius ceiling.
+
+Two layers, both here. The first pins SOURCE TEXT: that every threshold
+comparison in the radius block is reached only after an explicit `!== null`
+guard, because `undefined >= n` is false and `null >= 0` is true and a
+comparison reached by coercion decides halts by accident. The second layer
+EXECUTES `refactorRadiusStatus()` under real node through the same
+extract-and-drive pattern `TestScopeRecordBehavesAndNotJustExists` uses in
+test_slice_wave_contract.py, because a substring assertion proves a guard is
+present and nothing at all about what it decides.
+
+A fourth `test_slice_wave_contract*.py` module rather than a class in an
+existing one: `slice_wave_contract_base.py` sits at 298 non-blank lines and
+the quality gate's `class_lines` threshold is 300 whole-file non-blank lines,
+so every constant below is module-local by necessity as well as by the
+snippet-as-named-constant rule. The `basis`-field checks live in a fifth
+module, test_slice_wave_contract_radius_basis.py, for the same reason: this
+file crossed 300 non-blank lines once that class was added here, and the
+shared node driver moved to slice_wave_contract_radius_driver.py so both
+files can execute refactorRadiusStatus() without one importing a TestCase
+out of the other.
+
+Usage:
+    python3 -m unittest discover -s plugins/spec-loop/scripts \\
+        -p 'test_slice_wave_contract_radius.py'
+"""
+
+import sys
+import unittest
+from pathlib import Path
+
+sys.path.insert(0, str(Path(__file__).resolve().parent))
+
+from slice_wave_contract_base import COMMAND_MD, RUN_STATE_MD, WorkflowSourceTestCase  # noqa: E402
+from slice_wave_contract_radius_driver import RADIUS_START, RADIUS_END, radius_status  # noqa: E402
+
+RADIUS_NUM = ("const radiusNum = (v) => "
+              "(typeof v === 'number' && Number.isFinite(v)) ? v : null")
+RATIO_GUARD = "const over = (v, max) => v !== null && max !== null && v > max"
+FLOOR_GUARD = "m.rewritten_lines !== null && limits.min_rewritten_lines !== null"
+NOT_CONFIGURED = "state: 'NOT_CONFIGURED'"
+NOT_MEASURED = "state: 'NOT_MEASURED'"
+NO_USABLE_CEILING = "state: 'NO_USABLE_CEILING'"
+EXCEEDED = "state: 'EXCEEDED'"
+COERCION_OPERATORS = (">=", "<=")
+
+# The shipped defaults, and the declared-radius fixtures each state needs.
+# Module-level because nesting_depth is measured from raw indentation, so a
+# hanging literal inside a test body scores as real block nesting.
+LIMITS = {"enabled": True, "max_rewrite_ratio": 0.5,
+          "max_touched_existing_files": 8, "min_rewritten_lines": 150}
+BIG = {"rewrite_ratio": 0.9, "touched_existing_files": 12, "rewritten_lines": 900}
+AT_CEILING = {"rewrite_ratio": 0.5, "touched_existing_files": 8, "rewritten_lines": 900}
+TINY = {"rewrite_ratio": 0.9, "touched_existing_files": 12, "rewritten_lines": 20}
+ZEROED = {"rewrite_ratio": 0, "touched_existing_files": 0, "rewritten_lines": 0}
+NO_CEILINGS = {"enabled": True, "max_rewrite_ratio": None,
+               "max_touched_existing_files": None, "min_rewritten_lines": 150}
+STRING_CEILINGS = {"enabled": True, "max_rewrite_ratio": "0.5",
+                   "max_touched_existing_files": "8", "min_rewritten_lines": 150}
+STRINGY = {"rewrite_ratio": "0.9", "touched_existing_files": "12"}
+
+# Expected verdict fragments, hoisted for the same reason: a hanging
+# literal inside a test body is scored as real block nesting by the
+# quality gate's indentation heuristic.
+THREE_NULLS = {"rewrite_ratio": None,
+               "touched_existing_files": None,
+               "rewritten_lines": None}
+BOTH_CEILINGS = ["rewrite_ratio", "touched_existing_files"]
+
+
+# ---- the predicate, executed ----
+
+class TestTheRadiusPredicateDecidesAndNotJustExists(WorkflowSourceTestCase):
+    """Seven states, none collapsed into another. A substring assertion can
+    prove the word NOT_MEASURED appears in the file and nothing about which
+    inputs reach it, so this class runs the real helpers under real node and
+    reads the verdicts back: absence, disablement, an unusable ceiling, an
+    unmeasured plan, a plan at its ceiling, a breach, and a noise-floor one."""
+
+    def test_an_absent_ctx_block_is_not_configured_and_compares_nothing(self):
+        # In order: no block at all, a string where an object belongs, and an
+        # array. None of the three is a ceiling, and guessing the shipped
+        # defaults here would give the repo two sources of truth for a number
+        # the operator is invited to tune.
+        got = radius_status([[BIG, None], [BIG, "0.5"], [BIG, [0.5]]])
+        self.assertEqual([g["state"] for g in got], ["NOT_CONFIGURED"] * 3)
+        self.assertEqual([g["thresholds"] for g in got], [None, None, None])
+        self.assertEqual([g["exceeded"] for g in got], [[], [], []])
+
+    def test_a_disabled_block_never_fires_however_large_the_numbers(self):
+        got = radius_status([[BIG, dict(LIMITS, enabled=False)]])
+        self.assertEqual(got[0]["state"], "DISABLED")
+
+    def test_an_absent_plan_block_is_not_measured_with_three_explicit_nulls(self):
+        # PLAN_RESULT.required is ['status'] only, so all three reads are
+        # optional-field reads: absent, empty and array-shaped all land on the
+        # same fail-open state rather than throwing or inventing a zero.
+        got = radius_status([[None, LIMITS], [{}, LIMITS], [[1], LIMITS]])
+        self.assertEqual([g["state"] for g in got], ["NOT_MEASURED"] * 3)
+        self.assertEqual(got[0]["measured"], THREE_NULLS)
+
+    def test_declared_zeros_are_a_measurement_and_never_read_as_absence(self):
+        got = radius_status([[ZEROED, LIMITS]])
+        self.assertEqual(got[0]["state"], "WITHIN")
+        self.assertEqual(got[0]["measured"]["rewrite_ratio"], 0)
+
+    def test_string_numbers_are_not_measurements_and_are_never_coerced(self):
+        got = radius_status([[STRINGY, LIMITS]])
+        self.assertEqual(got[0]["state"], "NOT_MEASURED")
+        self.assertIsNone(got[0]["measured"]["rewrite_ratio"])
+
+    def test_a_plan_exactly_at_both_ceilings_is_within_and_does_not_halt(self):
+        got = radius_status([[AT_CEILING, LIMITS]])
+        self.assertEqual(got[0]["state"], "WITHIN")
+
+    def test_each_ceiling_is_breached_on_its_own_and_is_named_in_exceeded(self):
+        ratio = {"rewrite_ratio": 0.9, "rewritten_lines": 900}
+        files = {"touched_existing_files": 12, "rewritten_lines": 900}
+        got = radius_status([[ratio, LIMITS], [files, LIMITS]])
+        self.assertEqual([g["state"] for g in got], ["EXCEEDED", "EXCEEDED"])
+        self.assertEqual(got[0]["exceeded"], ["rewrite_ratio"])
+        self.assertEqual(got[1]["exceeded"], ["touched_existing_files"])
+
+    def test_the_noise_floor_suppresses_a_breach_but_keeps_the_numbers(self):
+        got = radius_status([[TINY, LIMITS]])
+        self.assertEqual(got[0]["state"], "BELOW_FLOOR")
+        self.assertEqual(got[0]["exceeded"], BOTH_CEILINGS)
+        self.assertEqual(got[0]["measured"]["rewritten_lines"], 20)
+
+    def test_an_unmeasured_line_count_does_not_suppress_a_measured_breach(self):
+        # The floor can only silence a fire it can prove is noise. A missing
+        # rewritten_lines proves nothing, so the measured ratio breach stands.
+        got = radius_status([[{"rewrite_ratio": 0.9}, LIMITS]])
+        self.assertEqual(got[0]["state"], "EXCEEDED")
+
+    def test_a_configured_block_with_no_usable_ceiling_is_its_own_state(self):
+        # WITHIN used to claim "every declared number is at or under its
+        # ceiling", which no comparison supported: a silent no-op that passed.
+        got = radius_status([[BIG, NO_CEILINGS], [BIG, STRING_CEILINGS]])
+        self.assertEqual([g["state"] for g in got], ["NO_USABLE_CEILING"] * 2)
+        self.assertEqual([g["exceeded"] for g in got], [[], []])
+
+    def test_an_unusable_ceiling_is_reported_before_an_unmeasured_plan(self):
+        # A mistyped ceiling is an operator-config defect, and blaming the
+        # planner for it would leave the real defect invisible.
+        got = radius_status([[None, NO_CEILINGS]])
+        self.assertEqual(got[0]["state"], "NO_USABLE_CEILING")
+
+    def test_one_usable_ceiling_of_the_two_still_judges_the_plan(self):
+        # The second pair also pins that a ceiling of 0 is a real, if severe,
+        # ceiling: a falsy usability test would read it as no ceiling at all.
+        one = dict(NO_CEILINGS, max_touched_existing_files=8)
+        zero = dict(NO_CEILINGS, max_rewrite_ratio=0)
+        got = radius_status([[BIG, one], [BIG, zero]])
+        self.assertEqual([g["state"] for g in got], ["EXCEEDED"] * 2)
+        self.assertEqual(got[0]["exceeded"], ["touched_existing_files"])
+        self.assertEqual(got[1]["exceeded"], ["rewrite_ratio"])
+
+    def test_every_verdict_carries_the_thresholds_it_compared_against(self):
+        # A threshold that silently declines to fire is a permanent invisible
+        # narrowing, so the no-fire and not-measured verdicts carry the
+        # ceilings too - a reader never has to re-derive why nothing happened.
+        got = radius_status([[BIG, LIMITS], [ZEROED, LIMITS], [None, LIMITS]])
+        for g in got:
+            self.assertEqual(g["thresholds"]["max_rewrite_ratio"], 0.5)
+            self.assertEqual(g["thresholds"]["max_touched_existing_files"], 8)
+            self.assertEqual(g["thresholds"]["min_rewritten_lines"], 150)
+
+
+# ---- the guards, pinned in source ----
+
+class TestNoRadiusComparisonIsReachedByCoercion(WorkflowSourceTestCase):
+    """`undefined >= n` is false and `null >= 0` is true, so an absent
+    measurement compared directly against a threshold produces a verdict
+    with no explicit branch. The whole block is therefore forbidden the
+    `>=`/`<=` operators outright, and both comparison sites are pinned to
+    guards that test BOTH sides for null first."""
+
+    def region(self):
+        return self.between(RADIUS_START, RADIUS_END)
+
+    def test_the_radius_block_uses_no_coercion_friendly_operator_at_all(self):
+        for op in COERCION_OPERATORS:
+            self.assertNotIn(op, self.region())
+
+    def test_both_comparisons_guard_both_sides_for_null_first(self):
+        self.assertIn(RATIO_GUARD, self.region())
+        self.assertIn(FLOOR_GUARD, self.region())
+
+    def test_a_number_is_type_checked_before_it_is_ever_a_measurement(self):
+        self.assertIn(RADIUS_NUM, self.region())
+
+    def test_the_four_no_fire_states_exist_as_their_own_named_branches(self):
+        for marker in (NOT_CONFIGURED, NO_USABLE_CEILING, NOT_MEASURED, EXCEEDED):
+            self.assertIn(marker, self.region())
+
+
+# ---- the declared block on PLAN_RESULT, and the planner instruction ----
+
+PLAN_REQUIRED = "required: ['status'],"
+RADIUS_SCHEMA = "refactor_radius: { type: 'object', additionalProperties: false"
+RADIUS_RATIO_TYPE = "rewrite_ratio: { type: ['number', 'null'] }"
+PROMPT_ASK = "Also return refactor_radius: your DECLARED estimate"
+PROMPT_NO_ZERO = "omit it rather than guessing a zero"
+PROMPT_JUDGE = "the workflow judges them against the run's ceiling"
+CTX_FIELD = "refactor_radius{enabled,max_rewrite_ratio"
+PLAN_PROMPT_START = "function planPrompt(slice) {"
+PLAN_PROMPT_END = "function criticPrompt("
+
+
+class TestThePlannerDeclaresNumbersAndTheWorkflowJudgesThem(WorkflowSourceTestCase):
+    """The planner is an ACTOR that reports numbers; the verdict is JS's.
+    The field stays optional because absence must remain a different claim
+    from zero all the way from the schema to the event payload."""
+
+    def test_the_schema_carries_an_optional_refactor_radius_block(self):
+        self.assertIn(RADIUS_SCHEMA, self.src)
+        self.assertIn(RADIUS_RATIO_TYPE, self.src)
+
+    def test_plan_result_still_requires_status_and_nothing_else(self):
+        self.assertIn(PLAN_REQUIRED, self.src)
+        self.assertNotIn("required: ['status', 'refactor_radius']", self.src)
+
+    def test_the_plan_prompt_asks_for_the_numbers_without_asking_for_a_verdict(self):
+        prompt = self.between(PLAN_PROMPT_START, PLAN_PROMPT_END)
+        self.assertIn(PROMPT_ASK, prompt)
+        self.assertIn(PROMPT_JUDGE, prompt)
+
+    def test_the_plan_prompt_forbids_inventing_a_zero_for_an_unknown(self):
+        self.assertIn(PROMPT_NO_ZERO, self.between(PLAN_PROMPT_START, PLAN_PROMPT_END))
+
+    def test_the_ctx_field_list_names_refactor_radius_as_the_one_channel(self):
+        self.assertIn(CTX_FIELD, self.line_containing("const CTX = A.ctx"))
+
+
+# ---- the halt: only a measured breach, only at plan time ----
+
+GATE_CALL = "const radius = refactorRadiusGate(slice, state, plan)"
+GATE_STOP = "if (radius) return { stop: escalated(slice, state, radius) }"
+GATE_TRIGGER = "return esc(slice, 'refactor-scope', refactorAsk(slice, verdict))"
+GATE_SUPPRESSION = "if (verdict.state !== 'EXCEEDED' || answered) return null"
+GATE_ALWAYS_EMITS = "state.events.push(radiusEvent(slice, verdict, answered))"
+GATE_ANSWERED = "const answered = !!latestAnswer(slice.id, 'refactor-scope')"
+GATE_KEY_COUNT = "answerKeysFor(slice.id, 'refactor-scope').length"
+STAGE_PLAN_START = "async function stagePlan(slice, state) {"
+STAGE_PLAN_END = "// Stage C helpers"
+GATE_FN_START = "function refactorRadiusGate(slice, state, plan) {"
+GATE_FN_END = "\n}\n"
+SUPPRESSED_GUARD = "const suppressed = answered && verdict.state === 'EXCEEDED'"
+SUPPRESSED_SPREAD = "...(suppressed ? { suppressed_by_answer: true } : {}),"
+EVENT_FN_START = "function radiusEvent(slice, verdict, answered) {"
+
+
+class TestOnlyAMeasuredBreachHaltsAndOnlyAtPlanTime(WorkflowSourceTestCase):
+    """The event push precedes the halt decision in source order, so no
+    return path can skip it; and the halt is raised from stagePlan and
+    nowhere else, before a single implementation dispatch is spent."""
+
+    def test_the_event_is_pushed_before_any_halt_decision_is_taken(self):
+        body = self.between(GATE_FN_START, GATE_FN_END)
+        self.assertLess(body.index(GATE_ALWAYS_EMITS), body.index(GATE_SUPPRESSION))
+
+    def test_only_the_exceeded_state_and_only_an_unanswered_slice_halts(self):
+        self.assertIn(GATE_SUPPRESSION, self.src)
+
+    def test_the_halt_is_disarmed_by_a_truthy_answer_and_not_by_a_key(self):
+        self.assertIn(GATE_ANSWERED, self.between(GATE_FN_START, GATE_FN_END))
+
+    def test_no_answer_key_count_decides_anything_in_the_gate(self):
+        self.assertNotIn(GATE_KEY_COUNT, self.src)
+
+    def test_a_suppression_is_only_claimed_for_a_breach_an_answer_waived(self):
+        body = self.between(EVENT_FN_START, GATE_FN_END)
+        self.assertIn(SUPPRESSED_GUARD, body)
+        self.assertIn(SUPPRESSED_SPREAD, body)
+
+    def test_no_suppression_flag_is_set_from_answeredness_alone(self):
+        self.assertNotIn("...(answered ? { suppressed_by_answer: true } : {})", self.src)
+
+    def test_the_record_is_minted_with_the_refactor_scope_trigger(self):
+        self.assertIn(GATE_TRIGGER, self.src)
+
+    def test_the_gate_is_called_from_the_plan_stage_and_from_nowhere_else(self):
+        self.assertIn(GATE_CALL, self.between(STAGE_PLAN_START, STAGE_PLAN_END))
+        self.assertIn(GATE_STOP, self.between(STAGE_PLAN_START, STAGE_PLAN_END))
+        self.assertEqual(self.src.count("refactorRadiusGate("), 2)
+
+
+# ---- the controller thread: ctx is the only lawful door ----
+
+CTX_THREAD = "refactor_radius"
+ONE_DOOR = "--print-config"
+EVENT_IN_LIST = "`refactor-radius`"
+PAYLOAD_BULLET = "**`refactor-radius`** payload"
+PROXY_LIMIT = "a proxy declared before implementation, not a measured diff"
+
+
+class TestTheThresholdsReachTheWorkflowOnlyThroughCtx(WorkflowSourceTestCase):
+    """The workflow has no fs and no process access by design, so the only
+    lawful path for a threshold is --print-config -> the controller command
+    -> ctx. If the command stops threading it, every installation silently
+    evaluates NOT_CONFIGURED and the ceiling never fires again."""
+
+    def test_the_controller_takes_the_block_from_the_one_config_door(self):
+        text = COMMAND_MD.read_text(encoding="utf-8")
+        self.assertIn(ONE_DOOR, text)
+        self.assertIn(CTX_THREAD, text)
+
+    def test_the_event_type_is_listed_in_its_single_home(self):
+        text = RUN_STATE_MD.read_text(encoding="utf-8")
+        self.assertIn(EVENT_IN_LIST, text)
+        self.assertIn(PAYLOAD_BULLET, text)
+
+    def test_the_contract_states_the_pre_execution_proxy_limit_plainly(self):
+        self.assertIn(PROXY_LIMIT, RUN_STATE_MD.read_text(encoding="utf-8"))
+
+
+if __name__ == "__main__":  # pragma: no cover
+    unittest.main()
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_radius_basis.py b/plugins/spec-loop/scripts/test_slice_wave_contract_radius_basis.py
new file mode 100644
index 0000000..2b00267
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_radius_basis.py
@@ -0,0 +1,69 @@
+#!/usr/bin/env python3
+"""Contract checks for the refactor-radius `basis` field.
+
+Split out of test_slice_wave_contract_radius.py, which crossed the quality
+gate's 300-non-blank-line class_lines threshold once this class was added.
+The planner declares HOW it counted (`basis`); a human weighing approve /
+narrow / carve-out cannot weigh a number whose derivation is invisible. The
+field is display-only, so these tests pin that it travels from the verdict
+to the event AND that it changes no verdict at all.
+
+Uses the same node driver as test_slice_wave_contract_radius.py, imported
+from slice_wave_contract_radius_driver rather than from that module's
+TestCase directly - importing a TestCase class into a second module makes
+`unittest discover` collect and run its tests twice.
+
+Usage:
+    python3 -m unittest discover -s plugins/spec-loop/scripts \\
+        -p 'test_slice_wave_contract_radius_basis.py'
+"""
+
+import sys
+import unittest
+from pathlib import Path
+
+sys.path.insert(0, str(Path(__file__).resolve().parent))
+
+from slice_wave_contract_base import WorkflowSourceTestCase  # noqa: E402
+from slice_wave_contract_radius_driver import (  # noqa: E402
+    RADIUS_START, RADIUS_END, radius_status)
+
+BIG = {"rewrite_ratio": 0.9, "touched_existing_files": 12, "rewritten_lines": 900}
+LIMITS = {"enabled": True, "max_rewrite_ratio": 0.5,
+          "max_touched_existing_files": 8, "min_rewritten_lines": 150}
+RADIUS_BASIS_GUARD = "(typeof radius.basis === 'string' && radius.basis) ? radius.basis : null"
+BASIS_IN_BASE = "basis: radiusBasis(radius)"
+BASIS_IN_EVENT = "basis: verdict.basis,"
+BASIS_TEXT = "counted with git diff --stat against main"
+WITH_BASIS = dict(BIG, basis=BASIS_TEXT)
+BAD_BASIS = dict(BIG, basis=17)
+
+
+class TestTheBasisReachesTheHumanAndDecidesNothing(WorkflowSourceTestCase):
+    """The planner declares HOW it counted; a human weighing approve /
+    narrow / carve-out cannot weigh a number whose derivation is invisible.
+    The field is display-only, so these tests pin that it travels AND that
+    the verdict is identical with and without it."""
+
+    def test_the_basis_is_carried_on_the_verdict_and_out_to_the_event(self):
+        self.assertIn(BASIS_IN_BASE, self.between(RADIUS_START, RADIUS_END))
+        self.assertIn(BASIS_IN_EVENT, self.src)
+
+    def test_only_a_non_empty_string_is_accepted_as_a_basis(self):
+        self.assertIn(RADIUS_BASIS_GUARD, self.between(RADIUS_START, RADIUS_END))
+
+    def test_the_basis_travels_beside_measured_and_never_inside_it(self):
+        got = radius_status([[WITH_BASIS, LIMITS], [BIG, LIMITS], [BAD_BASIS, LIMITS]])
+        self.assertEqual(got[0]["basis"], BASIS_TEXT)
+        self.assertIsNone(got[1]["basis"])
+        self.assertIsNone(got[2]["basis"])
+        self.assertNotIn("basis", got[0]["measured"])
+
+    def test_the_basis_changes_no_state_and_no_exceeded_list(self):
+        got = radius_status([[WITH_BASIS, LIMITS], [BIG, LIMITS]])
+        self.assertEqual(got[0]["state"], got[1]["state"])
+        self.assertEqual(got[0]["exceeded"], got[1]["exceeded"])
+
+
+if __name__ == "__main__":  # pragma: no cover
+    unittest.main()
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_replan.py b/plugins/spec-loop/scripts/test_slice_wave_contract_replan.py
new file mode 100644
index 0000000..376789b
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_replan.py
@@ -0,0 +1,186 @@
+#!/usr/bin/env python3
+"""Contract checks for the post-OBJECT replan re-check and the last three
+unguarded optional agent-return reads.
+
+Two facts this pins that a behavioural test cannot: that the re-check sits on
+the ONLY path out of a replan (a future edit adding a second `return { plan:
+revised }` would restore the leak while every behavioural test still passed),
+and that each guard reaches its comparison through an explicit null/type test
+rather than by coercion.
+
+A fifth `test_slice_wave_contract*.py` module rather than a class in an
+existing one: `slice_wave_contract_base.py` is at 299 non-blank lines and its
+four current importers are at 240-292, against a whole-file `class_lines`
+threshold of 300. Every pinned snippet below is a module-level constant, not a
+literal in a test body, because quality_gate.py's metrics are line-based and a
+`&&` inside a string literal scores as real branching.
+
+Usage:
+    python3 -m unittest discover -s plugins/spec-loop/scripts \\
+        -p 'test_slice_wave_contract_replan.py'
+"""
+
+import sys
+import unittest
+from pathlib import Path
+
+sys.path.insert(0, str(Path(__file__).resolve().parent))
+
+from slice_wave_contract_base import WorkflowSourceTestCase  # noqa: E402
+
+FIX_COMMITS = ("const fixCommits = (fix) => "
+               "(fix && typeof fix.commits === 'object' && fix.commits) ? fix.commits : {}")
+USABLE_SPLIT = ("const usableSplit = (s) => !!s && typeof s === 'object' "
+                "&& Array.isArray(s.children) && s.children.length > 0")
+IS_REVISED = ("const isRevisedPlan = (r) => !!r && typeof r === 'object' "
+              "&& r.status === 'PLANNED'")
+OBJECTION_SOURCE = ("const objectionSource = (v, fallback) => "
+                    "(v && v.objection && typeof v.objection.reason === 'string') ? v : fallback")
+PLAN_ESCALATION = "function planEscalation(slice, plan) {"
+GUARDED_ESC_LOCAL = ("const e = (plan.escalation && typeof plan.escalation === 'object') "
+                     "? plan.escalation : {}")
+GUARDED_TRIGGER = ("const trigger = (typeof e.trigger === 'string' && e.trigger) "
+                   "? e.trigger : 'ambiguity'")
+SPLIT_BRANCH = "if (plan.status === 'SPLIT') return { stop: splitResult(slice, state, plan) }"
+ESC_BRANCH = ("if (plan.status === 'ESCALATE') return "
+              "{ stop: escalated(slice, state, planEscalation(slice, plan)) }")
+RECRITIQUE_FN = "async function recritiqueRevisedPlan(slice, state, plan) {"
+RECRITIQUE_ROLE = "'critic:replan'"
+RECRITIQUE_AGENT = "agentType: 'spec-loop:plan-critic', schema: CRITIQUE"
+FAIL_CLOSED_RECHECK = "return v || failClosedCritique()"
+ACCEPT_FN = "async function acceptRevisedPlan(slice, state, ctx) {"
+ACCEPT_END = "\n}\n"
+REPLAN_HANDOFF = "return acceptRevisedPlan(slice, state, { revised, ob, safety })"
+RECHECK_EVENT = "type: 'replan-recheck'"
+SAFETY_GUARD = "const flagged = !!(rc.safety && rc.safety.flag === true)"
+ACCEPTED_GUARD = "const accepted = rc.verdict !== 'OBJECT' && !flagged"
+LEAKY_ACCEPT = "revised.status === 'PLANNED'"
+RADIUS_GATE_CALL = "refactorRadiusGate("
+OUTCOME_FN = "function recheckOutcome(rc, ob) {"
+OUTCOME_CALL = "const o = recheckOutcome(rc, ob)"
+STOP_FN = "function recheckStop(slice, state, o, ctx) {"
+STOP_CALL = "return { stop: recheckStop(slice, state, o, ctx) }"
+STOP_SAFETY_FIRST = ("if (o.safetyReason) return "
+                     "safetyRecheckEscalation(slice, state, o.safetyReason)")
+STOP_FALLBACK = ("return councilObjectionEscalation(slice, state, "
+                 "objectionSource(o.rc, ctx.ob), o.flagged || ctx.safety)")
+
+
+# ---- the three optional-read guards ----
+class TestTheLastOptionalReadsAreGuarded(WorkflowSourceTestCase):
+    """Each of the three reads that PLAN_RESULT/FIX_RESULT never promised now
+    runs through a type guard, and the raw read is gone from the file."""
+
+    def test_the_fix_result_commits_read_goes_through_a_type_guard(self):
+        self.assertIn(FIX_COMMITS, self.src)
+
+    def test_no_bare_fix_commits_base_read_survives_anywhere(self):
+        self.assertNotIn("fix.commits.base", self.src)
+
+    def test_the_split_branch_routes_through_the_usable_split_predicate(self):
+        self.assertIn(USABLE_SPLIT, self.src)
+        self.assertIn(SPLIT_BRANCH, self.src)
+
+    def test_the_escalate_branch_never_reads_the_trigger_off_a_bare_plan(self):
+        self.assertIn(ESC_BRANCH, self.src)
+        self.assertNotIn("plan.escalation.trigger", self.src)
+
+    def test_the_planner_escalation_builder_guards_the_object_then_the_field(self):
+        body = self.between(PLAN_ESCALATION, "\n}\n")
+        self.assertIn(GUARDED_ESC_LOCAL, body)
+        self.assertIn(GUARDED_TRIGGER, body)
+        self.assertLess(body.index(GUARDED_ESC_LOCAL), body.index(GUARDED_TRIGGER))
+
+
+# ---- the re-check on the replan path ----
+class TestARevisedPlanIsRecheckedAndNotAcceptedOnStatus(WorkflowSourceTestCase):
+    """The leak this closes: a well-formed revision used to be accepted on
+    `status === 'PLANNED'` alone, so one silent retry absorbed the objection."""
+
+    def test_the_replan_dispatch_hands_off_to_the_acceptance_helper(self):
+        self.assertIn(REPLAN_HANDOFF, self.src)
+
+    def test_no_status_only_acceptance_of_a_revision_survives(self):
+        self.assertNotIn(LEAKY_ACCEPT, self.src)
+
+    def test_the_recheck_dispatches_one_plan_critic_seat_on_the_revision(self):
+        body = self.between(RECRITIQUE_FN, "\n}\n")
+        self.assertIn(RECRITIQUE_ROLE, body)
+        self.assertIn(RECRITIQUE_AGENT, body)
+
+    def test_an_unreadable_recheck_falls_back_to_the_fail_closed_verdict(self):
+        self.assertIn(FAIL_CLOSED_RECHECK, self.between(RECRITIQUE_FN, "\n}\n"))
+
+    def test_the_acceptance_helper_has_exactly_one_proceed_return(self):
+        body = self.between(ACCEPT_FN, ACCEPT_END)
+        self.assertEqual(body.count("return { plan: revised }"), 1)
+
+    def test_the_only_proceed_return_is_reached_after_the_recheck(self):
+        body = self.between(ACCEPT_FN, ACCEPT_END)
+        self.assertLess(body.index("recritiqueRevisedPlan("), body.index("return { plan: revised }"))
+
+    def test_the_recheck_records_one_event_naming_the_verdict_it_reached(self):
+        self.assertIn(RECHECK_EVENT, self.between(ACCEPT_FN, ACCEPT_END))
+
+
+# ---- no verdict by coercion ----
+class TestNoAcceptanceIsReachedByCoercion(WorkflowSourceTestCase):
+    """Every acceptance predicate compares an explicitly typed value: a plan is
+    a plan only on the literal status string, and a safety flag counts only on
+    a literal `true`."""
+
+    def test_a_revision_is_a_plan_only_on_an_explicit_object_and_status_test(self):
+        self.assertIn(IS_REVISED, self.src)
+
+    def test_the_recheck_safety_flag_is_compared_to_a_literal_true(self):
+        self.assertIn(SAFETY_GUARD, self.src)
+
+    def test_acceptance_names_both_halves_and_neither_is_truthiness(self):
+        self.assertIn(ACCEPTED_GUARD, self.src)
+
+    def test_the_objection_carried_to_the_human_guards_the_optional_block(self):
+        self.assertIn(OBJECTION_SOURCE, self.src)
+
+
+# ---- the honest limit ----
+class TestTheRadiusGateIsNotReRunOnARevision(WorkflowSourceTestCase):
+    """A deliberate, logged gap this run does NOT close: the plan-time refactor
+    radius is evaluated once, in stagePlan, and a revision is not re-measured.
+    Pinned so that closing it later is a visible decision, not a drift."""
+
+    def test_the_radius_gate_is_called_from_exactly_one_place(self):
+        self.assertEqual(self.src.count(RADIUS_GATE_CALL), 2)  # definition + one call
+
+    def test_the_acceptance_helper_does_not_call_the_radius_gate(self):
+        self.assertNotIn(RADIUS_GATE_CALL, self.between(ACCEPT_FN, ACCEPT_END))
+
+
+# ---- the acceptance path, decomposed ----
+class TestTheAcceptanceHelperDelegatesItsJudgements(WorkflowSourceTestCase):
+    """acceptRevisedPlan carried the whole post-OBJECT decision — plan-shape,
+    safety, acceptance, reason selection and two escalation shapes — at
+    cyclomatic 12 / cognitive 22 against thresholds of 10 and 15. The verdict
+    arithmetic now lives in one PURE helper and the two escalation shapes in
+    another, so each is separately readable and separately reviewable. This
+    is a decomposition, not a behaviour change: slice_wave_replan.test.mjs is
+    unchanged and still green."""
+
+    def test_the_outcome_of_a_recheck_is_computed_by_one_named_helper(self):
+        self.assertIn(OUTCOME_FN, self.src)
+        self.assertIn(OUTCOME_CALL, self.between(ACCEPT_FN, ACCEPT_END))
+
+    def test_the_two_escalation_shapes_are_chosen_by_one_named_helper(self):
+        self.assertIn(STOP_FN, self.src)
+        self.assertIn(STOP_CALL, self.between(ACCEPT_FN, ACCEPT_END))
+
+    def test_the_recheck_safety_reason_still_wins_over_the_stale_objection(self):
+        body = self.between(STOP_FN, ACCEPT_END)
+        self.assertIn(STOP_SAFETY_FIRST, body)
+        self.assertIn(STOP_FALLBACK, body)
+
+    def test_the_acceptance_helper_still_records_the_event_itself(self):
+        self.assertIn(RECHECK_EVENT, self.between(ACCEPT_FN, ACCEPT_END))
+
+
+if __name__ == "__main__":  # pragma: no cover
+    unittest.main()
diff --git a/plugins/spec-loop/skills/escalation-gate/SKILL.md b/plugins/spec-loop/skills/escalation-gate/SKILL.md
index 410f703..f74c17a 100644
--- a/plugins/spec-loop/skills/escalation-gate/SKILL.md
+++ b/plugins/spec-loop/skills/escalation-gate/SKILL.md
@@ -45,11 +45,11 @@ The record is one `decision` event, payload
 (`run_state.py append-event --type decision`, stamped with its clock), or pushed onto a stage's
 `events[]` for the controller to stamp at collection (workflow scripts have no clock).
 `decisions-log.md` is *rendered* from those events: never hand-write an entry, and never rely on its
 wording — v2 pins no line grammar.
 
-### SURFACE to human (only these five triggers)
+### SURFACE to human (only these six triggers)
 
 Do not act. Return an `EscalationRecord` and let the controller batch it:
 
 1. **Genuine ambiguity** — there are ≥2 valid interpretations that materially change scope or
    behavior, and the codebase/spec cannot resolve which is intended.
@@ -63,10 +63,17 @@ Do not act. Return an `EscalationRecord` and let the controller batch it:
    hole, broken public contract). Lesser concerns (ENDORSE_WITH_CONCERNS, minority non-safety
    objections) are folded into the plan and logged — they do **not** surface.
 5. **Unfixable quality-gate block** — the quality gate's metrics still exceed the configured
    thresholds after the fix loop's behavior-preserving refactors. Thresholds are never weakened
    to avoid this.
+6. **Refactor scope** (`refactor-scope`) — the plan a slice just produced declares a rewrite of
+   existing code larger than the run's configured ceiling (`ctx.refactor_radius`). This is the one
+   trigger raised by the workflow's own arithmetic on planner-declared numbers rather than by an
+   agent's judgment, and it is raised at plan time, before a single implementation dispatch is
+   spent. It asks the human to narrow the slice, approve the rewrite, or carve the refactor out.
+   It fires only on a MEASURED breach: an absent or unmeasured number is never a breach, and no
+   number is ever inferred to be zero.
 
 When uncertain whether something is "material": if a reasonable reviewer could reject the slice
 over it, it is material → surface it.
 
 The enum lives in `slice-wave.workflow.js` (`ESCALATION.trigger`). Three things that are
@@ -87,12 +94,15 @@ passes to `esc`, alongside the one `runSliceError` already passed. What still se
 is the evidence and the ask: the exception record carries the exception text and the last
 stage/role dispatched and asks which of the three to take, while the lost-slice record carries
 neither and asks the same three-way question with its own tail, ending "or stop the run to investigate the silent failure"),
 and the council's **over-scope flag** (`critique.over_scope.flag`). The flag is a record: it is
 carried into the `council-verdict` payload and the slice sidecar with its reason, and it raises no
-escalation, changes no verdict, suppresses no split, and blocks nothing. There are exactly five
-JUDGMENT triggers; an over-scope flag is not a sixth.
+escalation, changes no verdict, suppresses no split, and blocks nothing. There are exactly six
+JUDGMENT triggers, and the sixth is `refactor-scope` — a threshold comparison the workflow performs
+on itself, which is why it belongs on the list even though no agent asked for it. Still, an
+over-scope flag is not one of them, and not because of the count: it stays a record because it
+decides nothing.
 
 ### Precedent check (before returning any SURFACE escalation)
 
 Prior runs' human answers are settled decisions — check them before asking a question the human
 may have already answered. Search prior runs (excluding this one): answered escalation records
@@ -114,11 +124,11 @@ on the text, never on a pinned format.
 The controller repeats this check over every open record at the wave boundary.
 
 ### Not triggers (autonomous by design)
 
 Three things that look like stopping points but are handled by the loop itself, keeping the bar at
-exactly the five triggers above:
+exactly the six triggers above:
 
 - **Slice split.** A slice that turns out to be two-or-more independently shippable changes
   returns `SPLIT`; the controller grafts the children into the DAG (`dag.py ingest-split`) —
   logged, no human contact. Only a proposal that is malformed or already at the depth cap falls
   back to a trigger above (see `references/split-ingestion.md`).
diff --git a/plugins/spec-loop/workflows/slice-wave.workflow.js b/plugins/spec-loop/workflows/slice-wave.workflow.js
index bca6bc5..ab028da 100644
--- a/plugins/spec-loop/workflows/slice-wave.workflow.js
+++ b/plugins/spec-loop/workflows/slice-wave.workflow.js
@@ -28,11 +28,11 @@ export const meta = {
 // ─────────────────────────────────────────────────────────────────────────────
 
 // Tolerate stringified args: some harness paths deliver the args value
 // JSON-encoded even when the caller passed an object (verified 2026-07-30).
 const A = typeof args === 'string' ? JSON.parse(args) : args
-const CTX = A.ctx // {run_dir, plugin_root, base_ref, test_command, conventions_path, shared_constraints[], scope_ceiling[] (optional), tier3_surfaces[], quality_gate_cmd, models{reviewer}, thorough, polish}
+const CTX = A.ctx // {run_dir, plugin_root, base_ref, test_command, conventions_path, shared_constraints[], scope_ceiling[] (optional), tier3_surfaces[], refactor_radius{enabled,max_rewrite_ratio,max_touched_existing_files,min_rewritten_lines} (optional), quality_gate_cmd, models{reviewer}, thorough, polish}
 
 const CAPS = { 1: 10, 2: 18, 3: 32 }
 const MAX_FIX_ROUNDS = 2
 const BUDGET_STAGE_FLOOR = 60_000 // skip-and-escalate below this remaining budget
 
@@ -45,11 +45,11 @@ const CAP_OVERRIDES = A.agent_cap_overrides || {}
 // ── Schemas ──────────────────────────────────────────────────────────────────
 
 const ESCALATION = {
   type: 'object', additionalProperties: false,
   properties: {
-    trigger: { enum: ['ambiguity', 'material-assumption', 'review-block', 'council-objection', 'quality-gate-block', 'budget-exhausted', 'internal-error'] },
+    trigger: { enum: ['ambiguity', 'material-assumption', 'review-block', 'council-objection', 'quality-gate-block', 'refactor-scope', 'budget-exhausted', 'internal-error'] },
     title: { type: 'string' }, context: { type: 'string' }, question: { type: 'string' },
     options: { type: 'array', items: { type: 'object', additionalProperties: false, properties: { label: { type: 'string' }, detail: { type: 'string' }, recommended: { type: 'boolean' } }, required: ['label', 'detail'] } },
   },
   required: ['trigger', 'title', 'context', 'question', 'options'],
 }
@@ -60,10 +60,18 @@ const PLAN_RESULT = {
     status: { enum: ['PLANNED', 'SPLIT', 'ESCALATE'] },
     plan_path: { type: 'string' },
     tasks: { type: 'array', maxItems: 10, items: { type: 'object', additionalProperties: false, properties: { id: { type: 'string' }, title: { type: 'string' }, lane: { enum: ['transcribe', 'standard', 'judgment'] }, files: { type: 'array', items: { type: 'string' } } }, required: ['id', 'title', 'lane', 'files'] } },
     split: { type: 'object', additionalProperties: false, properties: { children: { type: 'array', minItems: 2, items: { type: 'object', additionalProperties: false, properties: { goal: { type: 'string' }, files: { type: 'array', items: { type: 'string' } }, subsystems: { type: 'array', items: { type: 'string' } }, internal_deps: { type: 'array', items: { type: 'integer' } } }, required: ['goal', 'files', 'subsystems', 'internal_deps'] } } }, required: ['children'] },
     escalation: ESCALATION,
+    // OPTIONAL, and deliberately absent from `required` below: an absent block
+    // means "the planner declared no estimate", which is a different claim
+    // from a zero ratio. Every read of it runs through radiusNumbers(), which
+    // guards each field individually — PLAN_RESULT.required is ['status']
+    // only, and an unguarded optional read here aborted a whole wave of this
+    // run. `basis` is the planner's one-sentence account of how it counted,
+    // carried for a human reading the escalation and never parsed.
+    refactor_radius: { type: 'object', additionalProperties: false, properties: { rewrite_ratio: { type: ['number', 'null'] }, touched_existing_files: { type: ['integer', 'null'] }, rewritten_lines: { type: ['integer', 'null'] }, basis: { type: 'string' } } },
   },
   required: ['status'],
 }
 
 const CRITIQUE = {
@@ -203,10 +211,131 @@ function qualityStatus(q) {
   if (!q) return 'FAIL'
   if ((q.violations || []).length) return 'FAIL'
   return q.summary_pass === true ? 'PASS' : 'FAIL'
 }
 
+// ── Refactor radius: the plan-time ceiling on churn to EXISTING code ────────
+//
+// The second instance of qualityStatus()'s pattern: the PLANNER reports
+// numbers, this file judges them. The numbers are DECLARED before any
+// implementation runs, which is the whole point (the incident that motivated
+// this was "it asked, but too late") and also its honest limit: a declared
+// ratio is a PROXY, not a measured diff, and it cannot catch a blowup
+// discovered mid-implementation. No second, post-implementation measurement
+// exists — that was deliberately deferred, not forgotten.
+const RADIUS_NULL = { rewrite_ratio: null, touched_existing_files: null, rewritten_lines: null }
+
+// A real finite number, or null. Deliberately NOT Number(v): a string "0.9"
+// from a sloppy return is not a measurement, and coercing it would let a
+// typo halt or fail to halt an installation. NaN and Infinity are not
+// measurements either. (PURE)
+const radiusNum = (v) => (typeof v === 'number' && Number.isFinite(v)) ? v : null
+
+// Type-tolerant read of ctx.refactor_radius — the ONLY channel by which a
+// threshold reaches this file. The workflow has no fs and no process access
+// by design; the controller resolves the effective config once through
+// quality_gate.py --print-config and threads this block into ctx, the same
+// path tier3_surfaces takes. Anything that is not a plain object is "not
+// configured" rather than a guessed default: hardcoding the shipped numbers
+// here would give the repo two sources of truth for a value the operator is
+// invited to tune, and the two would drift in silence. (PURE)
+function refactorLimits(ctx) {
+  const raw = ctx.refactor_radius
+  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
+  return {
+    enabled: raw.enabled !== false,
+    max_rewrite_ratio: radiusNum(raw.max_rewrite_ratio),
+    max_touched_existing_files: radiusNum(raw.max_touched_existing_files),
+    min_rewritten_lines: radiusNum(raw.min_rewritten_lines),
+  }
+}
+
+// The plan's OPTIONAL refactor_radius block normalised to three explicit
+// nulls. PLAN_RESULT.required is ['status'] only, so every field here is an
+// optional agent-return read — the defect class that aborted a whole wave of
+// this very run. Absent stays null and NEVER becomes 0: a 0 ratio is a claim
+// that nothing is rewritten, which is not what silence means. (PURE)
+function radiusNumbers(radius) {
+  if (!radius || typeof radius !== 'object' || Array.isArray(radius)) return { ...RADIUS_NULL }
+  return {
+    rewrite_ratio: radiusNum(radius.rewrite_ratio),
+    touched_existing_files: radiusNum(radius.touched_existing_files),
+    rewritten_lines: radiusNum(radius.rewritten_lines),
+  }
+}
+
+// The planner's one-sentence account of how it counted, or null. DISPLAY-ONLY
+// and deliberately kept OUT of `measured`: no comparison, threshold or state
+// reads it, and `measured` is the object two test layers deep-equal against
+// three numeric nulls. A non-string is dropped rather than stringified,
+// because "17" as a basis sentence is worse than an honest absence — the
+// whole point of the field is that a human weighing the trade-off can see HOW
+// the number was reached. (PURE)
+const radiusBasis = (radius) => {
+  if (!radius || typeof radius !== 'object' || Array.isArray(radius)) return null
+  return (typeof radius.basis === 'string' && radius.basis) ? radius.basis : null
+}
+
+// Which measured metrics sit ABOVE their ceiling. Both sides are checked for
+// null before the one comparison, so no comparison is ever reached by
+// coercion. Strictly greater-than: both settings are MAXIMA, so a plan
+// exactly at max_touched_existing_files: 8 is at the ceiling, not over it.
+// (PURE)
+function radiusBreaches(m, limits) {
+  const over = (v, max) => v !== null && max !== null && v > max
+  const out = []
+  if (over(m.rewrite_ratio, limits.max_rewrite_ratio)) out.push('rewrite_ratio')
+  if (over(m.touched_existing_files, limits.max_touched_existing_files)) out.push('touched_existing_files')
+  return out
+}
+
+// The noise floor. It can only SUPPRESS a fire, never cause one, and it
+// applies only when BOTH the declared line count and the configured floor
+// are real numbers: an unmeasured rewritten_lines cannot be read as "small",
+// so a measured breach beside it still stands. (PURE)
+function radiusBelowFloor(m, limits) {
+  const known = m.rewritten_lines !== null && limits.min_rewritten_lines !== null
+  return known && m.rewritten_lines < limits.min_rewritten_lines
+}
+
+// Whether an enabled block carries NO comparable ceiling at all. Only the two
+// MAXIMA count: min_rewritten_lines can only suppress a fire, never cause one,
+// so its absence never makes a configuration unusable. An explicit === null on
+// each side rather than a falsy test, because a ceiling of 0 is a real, if
+// severe, ceiling. Its own named predicate rather than an inline condition,
+// like radiusBreaches and radiusBelowFloor beside it: inlined, the branch took
+// refactorRadiusStatus over its cognitive-complexity threshold. (PURE)
+function radiusNoCeiling(limits) {
+  return limits.max_rewrite_ratio === null && limits.max_touched_existing_files === null
+}
+
+// Seven states, none collapsed into another, and only EXCEEDED halts anything.
+// The two halves of this check have opposite answers on purpose: a
+// measurement that is missing, unconfigured, unusable or disabled FAILS OPEN
+// (proceed, and the caller records it loudly), while a measurement that
+// succeeded and is over its ceiling FAILS CLOSED (halt and ask). Collapsing
+// them would either halt every run with an old controller or halt none of
+// them. NO_USABLE_CEILING is checked BEFORE NOT_MEASURED deliberately: a
+// mistyped ceiling is an operator-config defect, and blaming the planner for
+// it would leave the real defect invisible. It is its own state rather than a
+// WITHIN, because "every declared number is at or under its ceiling" is a
+// claim no comparison supported when there is no ceiling to compare against —
+// a mistyped threshold used to report success while silently never firing.
+// (PURE)
+function refactorRadiusStatus(radius, limits) {
+  const measured = radiusNumbers(radius)
+  const base = { measured, basis: radiusBasis(radius), thresholds: limits, exceeded: [] }
+  if (!limits) return { ...base, thresholds: null, state: 'NOT_CONFIGURED', reason: 'ctx.refactor_radius is absent or is not an object, so no ceiling was compared' }
+  if (!limits.enabled) return { ...base, state: 'DISABLED', reason: 'refactor_radius.enabled is false in the effective gate config' }
+  if (radiusNoCeiling(limits)) return { ...base, state: 'NO_USABLE_CEILING', reason: 'refactor_radius is configured and enabled but neither ceiling is a usable number, so nothing was compared' }
+  if (measured.rewrite_ratio === null && measured.touched_existing_files === null) return { ...base, state: 'NOT_MEASURED', reason: 'the plan declared no usable refactor-radius number' }
+  const exceeded = radiusBreaches(measured, limits)
+  if (!exceeded.length) return { ...base, state: 'WITHIN', reason: 'every declared number is at or under its ceiling' }
+  if (radiusBelowFloor(measured, limits)) return { ...base, exceeded, state: 'BELOW_FLOOR', reason: `over a ceiling but under the ${limits.min_rewritten_lines}-line noise floor` }
+  return { ...base, exceeded, state: 'EXCEEDED', reason: `declared rewrite of existing code is over the configured ceiling (${exceeded.join(', ')})` }
+}
+
 // The panel's over-scope record for the council-verdict payload and the
 // sidecar, or null when no member recorded one (absent ≠ flag:false). A
 // flagged record wins over a clean one; the reason is KEPT — unlike
 // safety.reason, which is dropped at the source and recorded nowhere.
 // RECORD-ONLY: no caller may branch on this result. (PURE)
@@ -346,18 +475,25 @@ const answerFor = (slice, trigger) => {
 const answerContext = (slice, trigger) => {
   const a = latestAnswer(slice.id, trigger)
   return a ? `\nHUMAN ANSWER on the earlier "${trigger}" escalation, for context only — it does NOT change what you report: the suite result and quality.summary_pass/violations stay verbatim from the real output: ${a}` : ''
 }
 
+// refactor-scope is raised by the plan stage, so its answer is read back HERE and nowhere
+// else: a trigger whose answer never re-enters the prompt of the stage that raised it is
+// structurally unanswerable by re-dispatch and the human's answer is silently discarded
+// (the quality-gate-block outage this file already carries). The planner is an actor, not a
+// transcriber, so this is answerFor (an instruction) rather than answerContext. replanPrompt
+// interpolates planPrompt(slice), so it inherits the read-back and must not repeat the call.
 function planPrompt(slice) {
   return `${packet(slice)}
 
 Plan slice ${slice.id} of run ${A.run_id}: ${slice.goal}
 Named files: ${slice.files.join(', ') || '(none named)'} · Subsystems: ${slice.subsystems.join(', ') || '—'}
 Risk tier: ${slice.risk_tier} · Split depth: ${slice.depth} (split allowed only below depth 2)
 Write the plan to exactly: ${CTX.run_dir}/plans/${slice.id}.md
-Test/build command for verification steps: ${CTX.test_command}${answerFor(slice, 'ambiguity')}${answerFor(slice, 'material-assumption')}`
+Test/build command for verification steps: ${CTX.test_command}
+Also return refactor_radius: your DECLARED estimate of how much EXISTING code this plan rewrites — {rewrite_ratio: existing lines your tasks rewrite or delete ÷ total lines the plan changes, touched_existing_files: how many pre-existing files your tasks modify, rewritten_lines: the absolute count of existing lines rewritten or deleted, basis: one sentence on how you counted}. Report the numbers only, never a verdict: the workflow judges them against the run's ceiling. If you genuinely cannot estimate one, omit it rather than guessing a zero.${answerFor(slice, 'ambiguity')}${answerFor(slice, 'material-assumption')}${answerFor(slice, 'refactor-scope')}`
 }
 
 function criticPrompt(slice, plan, role) {
   return `${packet(slice)}
 
@@ -426,15 +562,29 @@ Package for anchor checks: ${CTX.run_dir}/packages/${slice.id}-round${state.revi
 Covering tests + commit when done.${answerFor(slice, 'quality-gate-block')}
 Findings:
 ${JSON.stringify(findings, null, 1)}`
 }
 
+// FIX_RESULT.commits is optional (`required` is status/touched_files/addressed/
+// refuted), so reading `base` straight off `fix.commits` dereferences an object
+// that need not exist. It threw exactly that way during wave 1 of run 20260828
+// (the raw read is spelled out nowhere in this file on purpose: a contract test
+// pins its absence by source text) and the catch-all mislabelled the TypeError
+// as budget-exhausted, losing the whole wave. Same type tolerance as
+// scopeCeilingList: an object passes through, anything else becomes {} and the
+// caller falls back to the shas the slice already holds.
+// HONEST LIMIT: those fallback shas are the slice's own base/head, so a package
+// built from them can be WIDER than the fix round's own diff. That is
+// deliberate — a wider real package beats a `--base undefined` command that
+// cannot run at all.
+const fixCommits = (fix) => (fix && typeof fix.commits === 'object' && fix.commits) ? fix.commits : {}
+
 function reReviewPrompt(slice, state, findings, fix) {
   return `${packet(slice)}
 
 Re-review after a fix round for slice ${slice.id}. Build the fix-only package:
-  ${packageCmd(slice, fix.commits.base, fix.commits.head, `fix${state.review.fix_rounds}`)}
+  ${packageCmd(slice, fixCommits(fix).base || state.commits.base, fixCommits(fix).head || state.commits.head, `fix${state.review.fix_rounds}`)}
 Prior blocking findings (verdict each): ${JSON.stringify(findings, null, 1)}
 Fixer refutations to adjudicate: ${JSON.stringify(fix.refuted, null, 1)}`
 }
 
 function verifyPrompt(slice, state) {
@@ -546,17 +696,144 @@ function doneResult(slice, state, status, extra) {
     tests: state.tests, quality: state.quality, escalations: state.escalations,
     agents_used: state.agentsUsed, wave: A.wave_index, events: state.events, ...extra,
   }
 }
 
+// One line of copy naming every number on both sides of the comparison. A
+// human answering this needs the measurements AND the ceilings they were
+// judged against in the record itself, not a pointer to a config file they
+// would have to resolve by hand. (PURE)
+const radiusPhrase = (v) => `declared rewrite ratio ${v.measured.rewrite_ratio}, touched existing files ${v.measured.touched_existing_files}, rewritten lines ${v.measured.rewritten_lines}; ceilings ${v.thresholds.max_rewrite_ratio} ratio / ${v.thresholds.max_touched_existing_files} files, noise floor ${v.thresholds.min_rewritten_lines} lines; the planner counted this as: ${v.basis === null ? 'not stated' : v.basis}`
+
+// The trade-off ask. Three options because a yes/no would leave a human who
+// wants neither with nothing to pick, and because each of the three costs
+// something different: narrowing leaves existing structure uncleaned,
+// approving buys a large diff for one reviewer with no second measurement
+// after implementation, and carving out defers the work to a slice a human
+// must schedule. Each detail names the CONTROLLER as what applies it — the
+// loop narrows, approves and splits nothing by itself. (PURE)
+function refactorAsk(slice, verdict) {
+  return {
+    title: `plan for ${slice.id} declares a heavy rewrite of existing code (${verdict.exceeded.join(', ')})`,
+    context: `The plan is written and NOT implemented — this fires before implementation effort is spent. ${radiusPhrase(verdict)}. These are numbers the PLANNER DECLARED: a pre-execution proxy, not a measured diff, so they can be wrong in either direction and cannot catch a blowup discovered mid-implementation. Goal: ${slice.goal}`,
+    question: 'Approve the rewrite as planned, narrow the plan to the smallest change that meets the goal, or carve the rewrite out into its own slice?',
+    options: [
+      { label: 'Narrow the plan to the smallest change that meets the goal', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: put the instruction in args.answers under this record id and re-dispatch the wave — the planner reads it back in its own prompt and replans against it. Trade-off: existing structure this rewrite would have cleaned up stays as it is.', recommended: true },
+      { label: 'Approve the rewrite as planned', detail: 'The CONTROLLER must act on this at the next dispatch: answer this record with the approval and re-dispatch. The same plan proceeds and this check does not raise again for this slice. Trade-off: one reviewer judges a large diff in one slice, and no second measurement runs after implementation.' },
+      { label: 'Carve the rewrite out into its own slice', detail: 'The CONTROLLER must act on this at the next dispatch: re-plan the run so the rewrite is a slice of its own, then re-dispatch. The loop splits nothing by itself — it never turns a refactor into its own slice without this answer.' },
+    ],
+  }
+}
+
+// Every evaluation is recorded, including the ones that decline to fire. A
+// threshold that silently declines is a permanent invisible narrowing — the
+// exact silent-exclusion defect this repo's knowledge graph already names —
+// so the payload carries the measured numbers AND the thresholds they were
+// compared against, in every state, and a reader never has to re-derive why
+// nothing happened. `summary` is the FIRST key because run_state.py's
+// decisions-log renderer reads the first text-ish field of a payload
+// (SUMMARY_TEXT_KEYS), so the line is prose rather than a JSON blob. (PURE)
+function radiusEvent(slice, verdict, answered) {
+  // A suppression is a fire that did NOT happen. The flag used to be set from
+  // `answered` alone, so an ordinary post-answer success — the human says
+  // narrow it, the planner narrows, the verdict comes back WITHIN — emitted an
+  // event claiming a suppression that never occurred, and anyone auditing
+  // which halts a human had waived would have counted it. Only EXCEEDED can be
+  // suppressed, because only EXCEEDED halts. The key stays ABSENT rather than
+  // false when nothing was suppressed: `false` would be an explicit claim
+  // about a state in which suppression is not even possible.
+  const suppressed = answered && verdict.state === 'EXCEEDED'
+  return {
+    scope: slice.id, type: 'refactor-radius',
+    payload: {
+      summary: `refactor radius ${verdict.state}: ${verdict.reason}`,
+      state: verdict.state, exceeded: verdict.exceeded,
+      measured: verdict.measured, thresholds: verdict.thresholds,
+      basis: verdict.basis,
+      ...(suppressed ? { suppressed_by_answer: true } : {}),
+    },
+  }
+}
+
+// Fail OPEN on absence, CLOSED on a measured breach — the two halves have
+// opposite answers and are never collapsed. HONEST LIMITS, both deliberate:
+// this runs ONCE, on the plan the planner returned, so a replan after a
+// council OBJECT is not re-evaluated; and the numbers are pre-execution
+// declarations, so a blowup discovered mid-implementation is invisible here.
+function refactorRadiusGate(slice, state, plan) {
+  const verdict = refactorRadiusStatus(plan.refactor_radius, refactorLimits(CTX))
+  // A truthy ANSWER, not the presence of an answer KEY. The same map reaches
+  // the planner through answerFor()/latestAnswer(), which both require a
+  // truthy value, so an empty or null entry used to disarm this halt
+  // permanently for the slice while injecting nothing into the prompt the
+  // halt exists to change — the question disappeared and the answer never
+  // arrived. This is the shape resolveCouncilObjection already uses.
+  const answered = !!latestAnswer(slice.id, 'refactor-scope')
+  state.events.push(radiusEvent(slice, verdict, answered))
+  // Answered means the human already ruled on this slice's radius. Raising
+  // the same question again would deadlock the slice at the same stage
+  // forever, so the verdict stays EXCEEDED in the event (with
+  // suppressed_by_answer) and the slice proceeds.
+  if (verdict.state !== 'EXCEEDED' || answered) return null
+  return esc(slice, 'refactor-scope', refactorAsk(slice, verdict))
+}
+
+// PLAN_RESULT.required is ['status'] only, so both branches below read a field
+// the schema never promised. Neither read is guarded upstream, and this exact
+// defect class has aborted a whole wave of this repo twice.
+
+// A split with no children array is schema-legal and unusable: passing it
+// through produced a sidecar that run_state.py's validator rejects one stage
+// later, far from the cause. Fail closed HERE instead. (PURE)
+const usableSplit = (s) => !!s && typeof s === 'object' && Array.isArray(s.children) && s.children.length > 0
+
+function splitResult(slice, state, plan) {
+  if (usableSplit(plan.split)) return doneResult(slice, state, 'SPLIT', { split: plan.split })
+  return escalated(slice, state, esc(slice, 'ambiguity', { title: 'planner returned SPLIT with no usable split object', context: 'The planner returned status SPLIT but no `split.children`. That is schema-legal (PLAN_RESULT requires only `status`) and unusable: passing it through writes a sidecar the run-state validator rejects one stage later. The slice is paused here, at the cause.', question: 'Re-dispatch the planner for this slice, split it by hand, or drop it?', options: [] }))
+}
+
+// One optional string field of an escalation record, or the substitute copy.
+// Every one of the four fields below needs the identical explicit type test,
+// and inlining it four times put planEscalation over the gate's
+// cyclomatic/cognitive thresholds for no gain in clarity. An empty string is
+// NOT a readable field: it would render as a blank line in the human's
+// decisions log, so it takes the fallback too. (PURE)
+const escText = (v, fallback) => (typeof v === 'string' && v) ? v : fallback
+
+// The substitute copy for a planner that escalated without saying anything.
+// Module-level so planEscalation stays a short list of guarded reads.
+const BARE_ESCALATION = {
+  title: 'planner escalated without a readable escalation record',
+  context: 'The planner returned status ESCALATE with no usable escalation object. The wave substituted this record so the slice pauses for a human instead of crashing the wave with a TypeError.',
+  question: 'The planner escalated without saying what it needs. Re-dispatch the planner, answer the slice goal directly, or drop the slice?',
+}
+
+// The trigger is TYPE-guarded, not enum-guarded: an unrecognized non-empty
+// string still passes through and will fail run_state.py's validate_escalation
+// downstream, exactly as it does today. Widening this to an enum check would
+// need a second copy of the enum in this file, and that enum has eight homes
+// already. Stated as a limit rather than silently half-fixed.
+function planEscalation(slice, plan) {
+  const e = (plan.escalation && typeof plan.escalation === 'object') ? plan.escalation : {}
+  const trigger = (typeof e.trigger === 'string' && e.trigger) ? e.trigger : 'ambiguity'
+  return esc(slice, trigger, {
+    title: escText(e.title, BARE_ESCALATION.title),
+    context: escText(e.context, BARE_ESCALATION.context),
+    question: escText(e.question, BARE_ESCALATION.question),
+    options: Array.isArray(e.options) ? e.options : [],
+  })
+}
+
 // Stage P — plan (+ right-size gate inside the planner)
 async function stagePlan(slice, state) {
   const plan = await dispatch(slice, state, 'plan', planPrompt(slice),
     { agentType: 'spec-loop:slice-planner', schema: PLAN_RESULT, effort: 'low' })
   if (!plan) return { stop: escalated(slice, state, esc(slice, 'ambiguity', { title: 'planner returned no result', context: 'The planner dispatch failed terminally.', question: 'Retry the slice, or drop it?', options: [] })) }
-  if (plan.status === 'SPLIT') return { stop: doneResult(slice, state, 'SPLIT', { split: plan.split }) }
-  if (plan.status === 'ESCALATE') return { stop: escalated(slice, state, esc(slice, plan.escalation.trigger, plan.escalation)) }
+  if (plan.status === 'SPLIT') return { stop: splitResult(slice, state, plan) }
+  if (plan.status === 'ESCALATE') return { stop: escalated(slice, state, planEscalation(slice, plan)) }
+  const radius = refactorRadiusGate(slice, state, plan)
+  if (radius) return { stop: escalated(slice, state, radius) }
   return { plan }
 }
 
 // Stage C helpers — panel selection, verdict rollup, and the OBJECT branch.
 // Each helper below is kept single-purpose and small on its own terms (own
@@ -635,10 +912,95 @@ function latestAnswer(sliceId, trigger) {
 
 function councilObjectionEscalation(slice, state, ob, safety) {
   return escalated(slice, state, esc(slice, 'council-objection', { title: `${safety ? 'SAFETY — ' : ''}council objects: ${ob.objection.reason.slice(0, 60)}`, context: ob.objection.reason, question: ob.objection.question, options: [{ label: ob.objection.recommendation, detail: 'critic-recommended default', recommended: true }] }))
 }
 
+// The re-check itself is a CRITIQUE, not an objection: `objection` is optional
+// on that schema (required is verdict/safety/concerns), so a re-check that
+// flags a NEW safety risk on a clean ENDORSE verdict — RECHECK_SAFETY's exact
+// shape — carries no `objection` block at all. Falling back to the ORIGINAL
+// council objection in that case would describe the wrong risk to the human:
+// the concern the revision was written to fix, not the one the re-check just
+// raised. This builds the escalation straight from the re-check's own
+// `safety.reason` so that text — otherwise written nowhere — reaches the
+// human and the events log. (PURE)
+function safetyRecheckEscalation(slice, state, reason) {
+  return escalated(slice, state, esc(slice, 'council-objection', {
+    title: `SAFETY — re-check flags: ${reason.slice(0, 60)}`,
+    context: reason,
+    question: 'The revised plan raises a new safety risk. Accept it, revise by hand, or drop the slice?',
+  }))
+}
+
+// A revision is a REMEDY CLAIM, not a remedy. Accepting `status: 'PLANNED'` on
+// its own meant one silent retry absorbed the objection: nobody ever re-read
+// the plan the council rejected, so a well-formed revision that fixed nothing
+// reached implementation and the objection never reached the human, while the
+// doctrine described the mechanism as blocking. The revision therefore goes
+// back to ONE plan-critic seat and only a non-OBJECT, non-safety verdict
+// proceeds. HONEST LIMITS, all deliberate: the re-check is a single
+// full-council seat, NOT the original panel (guardian and skeptic do not
+// re-run, so a tier-3 objection is re-checked by one member); it happens once,
+// because state.replanned already vetoes a second replan; and the plan-time
+// refactor-radius gate is NOT re-evaluated on the revised plan - that remains
+// this run's logged, deliberate gap and would mean raising the trigger from a
+// stage other than plan.
+
+// Explicit null/type guards before any comparison: null, a non-object, or any
+// status other than the literal 'PLANNED' is not a plan, and no truthiness
+// shortcut gets to decide that. (PURE)
+const isRevisedPlan = (r) => !!r && typeof r === 'object' && r.status === 'PLANNED'
+
+// The human needs the reason the REVISION was rejected. `objection` is optional
+// on CRITIQUE (required is verdict/safety/concerns), so a verdict without a
+// readable one falls back to the original objection rather than throwing the
+// same class of TypeError this file is closing elsewhere. (PURE)
+const objectionSource = (v, fallback) => (v && v.objection && typeof v.objection.reason === 'string') ? v : fallback
+
+async function recritiqueRevisedPlan(slice, state, plan) {
+  const v = await dispatch(slice, state, 'critic:replan', criticPrompt(slice, plan, null),
+    { agentType: 'spec-loop:plan-critic', schema: CRITIQUE, effort: 'high' })
+  return v || failClosedCritique()
+}
+
+// The five judgements a re-check produces, computed once in one place: was a
+// safety flag raised, is there a readable reason for it, does the revision
+// proceed, and which reason does the human get. Split out of
+// acceptRevisedPlan, which carried all of it plus two escalation shapes at
+// cyclomatic 12 / cognitive 22 against thresholds of 10 and 15 — a function a
+// reviewer had to hold entirely in their head to check any one of its
+// branches. `rc` travels back out in the result so the caller never has to
+// pass both the outcome and the critique to the next helper. (PURE)
+function recheckOutcome(rc, ob) {
+  const flagged = !!(rc.safety && rc.safety.flag === true)
+  const safetyReason = flagged && typeof rc.safety.reason === 'string' ? rc.safety.reason : null
+  const accepted = rc.verdict !== 'OBJECT' && !flagged
+  const reason = accepted ? null : (safetyReason || objectionSource(rc, ob).objection.reason)
+  return { rc, flagged, safetyReason, accepted, reason }
+}
+
+// Which of the two escalation shapes a rejected revision gets. The re-check's
+// OWN safety reason wins whenever it exists, because falling back to the
+// original council objection would describe the wrong risk to the human: the
+// concern the revision was written to fix, not the one the re-check just
+// raised. `o` and `ctx` travel as objects because parameter_count's threshold
+// is 4 and this decision genuinely needs five values.
+function recheckStop(slice, state, o, ctx) {
+  if (o.safetyReason) return safetyRecheckEscalation(slice, state, o.safetyReason)
+  return councilObjectionEscalation(slice, state, objectionSource(o.rc, ctx.ob), o.flagged || ctx.safety)
+}
+
+async function acceptRevisedPlan(slice, state, ctx) {
+  const { revised, ob, safety } = ctx
+  if (!isRevisedPlan(revised)) return { stop: councilObjectionEscalation(slice, state, ob, safety) }
+  const rc = await recritiqueRevisedPlan(slice, state, revised)
+  const o = recheckOutcome(rc, ob)
+  state.events.push({ scope: slice.id, type: 'replan-recheck', payload: { verdict: rc.verdict, safety: o.flagged, accepted: o.accepted, reason: o.reason, safety_reason: o.safetyReason } })
+  if (o.accepted) return { plan: revised }
+  return { stop: recheckStop(slice, state, o, ctx) }
+}
+
 // The council OBJECT branch: an unanswered fixable objection gets one replan
 // attempt; anything else (safety, unfixable, or a failed replan) escalates.
 // answered → proceed with the existing plan; the answer is already injected
 // into downstream prompts via answerFor().
 async function resolveCouncilObjection(slice, state, ctx) {
@@ -646,11 +1008,11 @@ async function resolveCouncilObjection(slice, state, ctx) {
   if (latestAnswer(slice.id, 'council-objection')) return { plan }
   if (safety || !ob.fixable_by_replan || state.replanned) return { stop: councilObjectionEscalation(slice, state, ob, safety) }
   state.replanned = true
   const revised = await dispatch(slice, state, 'replan', replanPrompt(slice, plan, ob),
     { agentType: 'spec-loop:slice-planner', schema: PLAN_RESULT, effort: 'low' })
-  return (revised && revised.status === 'PLANNED') ? { plan: revised } : { stop: councilObjectionEscalation(slice, state, ob, safety) }
+  return acceptRevisedPlan(slice, state, { revised, ob, safety })
 }
 
 // Resolves an OBJECT verdict and records deferrals only if the resolution
 // actually lets the plan proceed (see the comment on recordDeferrals above)
 // — pulled out of stageCritique so that one extra branch is not counted
