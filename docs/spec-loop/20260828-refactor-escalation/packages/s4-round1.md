# Review package: e5479765c38247df97d5de9571a7f401b8deaff4..4410f8e  (context: -U5)

## Commits
4410f8e docs(spec-loop): correct the fixable_by_replan prose and record the replan re-check
47bc275 test(spec-loop): pin the replan re-check and the three new optional-read guards
8ce17e2 fix(spec-loop): re-critique a plan revised after a council OBJECT before proceeding
3af44f3 fix(spec-loop): guard the three unguarded optional agent-return reads in the wave

## Files changed
 .github/workflows/validate.yml                     |  11 +-
 CHANGELOG.md                                       |  25 ++++
 plugins/spec-loop/agents/guardian.md               |   2 +-
 plugins/spec-loop/agents/plan-critic.md            |   4 +-
 plugins/spec-loop/agents/skeptic.md                |   2 +-
 plugins/spec-loop/agents/slice-worker-fallback.md  |  16 ++-
 .../spec-loop/scripts/slice_wave_contract_base.py  |  17 ++-
 plugins/spec-loop/scripts/slice_wave_harness.mjs   |  84 ++++++++++--
 .../spec-loop/scripts/slice_wave_radius.test.mjs   |   6 +-
 .../spec-loop/scripts/slice_wave_replan.test.mjs   | 137 +++++++++++++++++++
 .../scripts/test_slice_wave_contract_replan.py     | 151 +++++++++++++++++++++
 plugins/spec-loop/workflows/slice-wave.workflow.js | 110 ++++++++++++++-
 12 files changed, 527 insertions(+), 38 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
".github/workflows/validate.yml": [
[
71,
72
],
[
74,
75
],
[
82,
83
]
],
"CHANGELOG.md": [
[
26,
50
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
"plugins/spec-loop/agents/slice-worker-fallback.md": [
[
76,
85
]
],
"plugins/spec-loop/scripts/slice_wave_contract_base.py": [
[
21,
28
]
],
"plugins/spec-loop/scripts/slice_wave_harness.mjs": [
[
231,
284
],
[
286,
290
],
[
295,
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
97,
101
]
],
"plugins/spec-loop/scripts/slice_wave_replan.test.mjs": [
[
1,
137
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_replan.py": [
[
1,
151
]
],
"plugins/spec-loop/workflows/slice-wave.workflow.js": [
[
536,
549
],
[
554,
554
],
[
733,
778
],
[
784,
785
],
[
870,
911
],
[
923,
923
]
]
}
```

## Diff
diff --git a/.github/workflows/validate.yml b/.github/workflows/validate.yml
index b0a8d50..6188052 100644
--- a/.github/workflows/validate.yml
+++ b/.github/workflows/validate.yml
@@ -66,22 +66,23 @@ jobs:
         # gates, both fail closed, mirroring the client JS step: exit status,
         # and a minimum TAP count so an emptied file cannot pass silently.
         # Scope: deterministic control flow only. The real Workflow-host seam
         # is NOT covered here — see the test file's own honest-limit header.
         run: |
-          # Two modules now: the second covers the plan-time refactor-radius gate, split out
-          # because the first sits at the 300-line class_lines ceiling.
+          # Three modules now: the third covers the optional-read guards and the post-OBJECT
+          # replan re-check, split out because the first sits at the 300-line class_lines ceiling.
           out=$(node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs \
-                            plugins/spec-loop/scripts/slice_wave_radius.test.mjs 2>&1)
+                            plugins/spec-loop/scripts/slice_wave_radius.test.mjs \
+                            plugins/spec-loop/scripts/slice_wave_replan.test.mjs 2>&1)
           rc=$?
           echo "$out"
           if [ "$rc" -ne 0 ]; then
             echo "FAIL: wave harness exited non-zero (rc=$rc)"; exit "$rc"
           fi
           ran=$(printf '%s\n' "$out" | sed -n 's/^# tests \([0-9][0-9]*\).*/\1/p')
-          if [ "${ran:-0}" -lt 45 ]; then
-            echo "FAIL: only ${ran:-0} wave harness tests ran (expected >= 45)"; exit 1
+          if [ "${ran:-0}" -lt 63 ]; then
+            echo "FAIL: only ${ran:-0} wave harness tests ran (expected >= 63)"; exit 1
           fi
 
       - name: Install Claude Code CLI
         run: npm install -g @anthropic-ai/claude-code
 
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 45c585d..b8eebe8 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -21,10 +21,35 @@ All notable changes to the spec-loop plugin are documented here. The format is
   a planner-declared proxy rather than a measured diff, so this cannot catch a blowup
   discovered mid-implementation; the check runs once, on the first plan, and a post-OBJECT
   replan is not re-evaluated; and a controller that does not thread `ctx.refactor_radius`
   records `NOT_CONFIGURED` and never halts.
 
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
+
 ## [2.2.2] - 2026-08-28
 ### Added
 - **The quality gate counts branch keywords in code, not in prose.** `quality_gate.py` now
   masks the content of string literals and comments before it scans a source, so a branch word
   or an operator character inside a docstring, a comment or a message string no longer inflates
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
diff --git a/plugins/spec-loop/agents/slice-worker-fallback.md b/plugins/spec-loop/agents/slice-worker-fallback.md
index e07b88e..2fff3c2 100644
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
diff --git a/plugins/spec-loop/scripts/slice_wave_contract_base.py b/plugins/spec-loop/scripts/slice_wave_contract_base.py
index 6dff36e..01c6c85 100644
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
diff --git a/plugins/spec-loop/scripts/slice_wave_harness.mjs b/plugins/spec-loop/scripts/slice_wave_harness.mjs
index eefaa7c..bdf6f88 100644
--- a/plugins/spec-loop/scripts/slice_wave_harness.mjs
+++ b/plugins/spec-loop/scripts/slice_wave_harness.mjs
@@ -226,23 +226,87 @@ export const planThenStop = (plan) => ({
     if (String(opts.label).endsWith(":plan")) return plan;
     throw new Error("STOP");
   },
 });
 
-export const PIPELINE_LABELS = Object.keys(PIPELINE).map((role) => "s1:" + role);
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
+
+// Answers a dispatch from `map`, keyed by the role part of the label
+// (`s1:critic:full-council` -> `critic:full-council`). An unmapped role throws,
+// which terminates the slice right after the stage under test; `seen` is the
+// dispatch order, so a test can assert that a stage did or did not run at all.
+// A mapped Error value is thrown instead of returned, and a mapped null is
+// returned as null - the terminal-failure input every caller must fail closed on.
+export function councilSandbox(map) {
+  const seen = [];
+  const agent = async (prompt, opts) => {
+    const label = String(opts.label);
+    const role = label.slice(label.indexOf(":") + 1);
+    seen.push(role);
+    if (!(role in map)) throw new Error("STOP");
+    if (map[role] instanceof Error) throw map[role];
+    return map[role];
+  };
+  return { seen, agent };
+}
 
-// Records the label and the prompt of every dispatch and answers each one with
-// the return above. An unmapped role throws under its own name: a new stage
-// must be mapped here rather than degrading a run into a fail-closed path in
-// silence, which would quietly narrow whatever a test built on this asserts.
-export const fullPipeline = () => {
+// Records the label and the prompt of every dispatch and answers each one from
+// `map`. An unmapped role throws under its own name: a new stage must be mapped
+// rather than degrading a run into a fail-closed path in silence, which would
+// quietly narrow whatever a test built on this asserts.
+function mappedPipeline(map) {
   const seen = [];
   const agent = async (prompt, opts) => {
     const label = String(opts.label);
     const role = label.slice(label.indexOf(":") + 1);
-    const mapped = PIPELINE[role];
-    if (mapped === undefined) throw new Error("slice_wave_harness: no mock return mapped to role " + role);
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
index 345d856..74cfa00 100644
--- a/plugins/spec-loop/scripts/slice_wave_radius.test.mjs
+++ b/plugins/spec-loop/scripts/slice_wave_radius.test.mjs
@@ -92,11 +92,15 @@ test("the payload leads with a human-readable summary for the decisions log", as
   assert.equal(Object.keys(ev.payload)[0], "summary");
   assert.ok(ev.payload.summary.startsWith("refactor radius EXCEEDED"));
 });
 
 test("a SPLIT plan is discarded before the gate and emits no evaluation", async () => {
-  const split = { status: "SPLIT", split: { children: [] } };
+  // Two real children, not an empty array: a childless SPLIT is now itself an
+  // escalation (usableSplit), which would end this slice before the question
+  // under test - whether the radius gate runs on a SPLIT - could be asked.
+  const child = { goal: "half", files: ["a.py"], subsystems: ["x"], internal_deps: [] };
+  const split = { status: "SPLIT", split: { children: [child, child] } };
   const out = await runWave(radiusArgs(S1(), RADIUS_DEFAULTS), planThenStop(split));
   assert.equal(out.results[0].status, "SPLIT");
   assert.equal(radiusEvents(out.results[0]).length, 0);
 });
 
diff --git a/plugins/spec-loop/scripts/slice_wave_replan.test.mjs b/plugins/spec-loop/scripts/slice_wave_replan.test.mjs
new file mode 100644
index 0000000..00803a9
--- /dev/null
+++ b/plugins/spec-loop/scripts/slice_wave_replan.test.mjs
@@ -0,0 +1,137 @@
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
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_replan.py b/plugins/spec-loop/scripts/test_slice_wave_contract_replan.py
new file mode 100644
index 0000000..bdb3ccd
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_replan.py
@@ -0,0 +1,151 @@
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
+if __name__ == "__main__":  # pragma: no cover
+    unittest.main()
diff --git a/plugins/spec-loop/workflows/slice-wave.workflow.js b/plugins/spec-loop/workflows/slice-wave.workflow.js
index 77e859a..15a4160 100644
--- a/plugins/spec-loop/workflows/slice-wave.workflow.js
+++ b/plugins/spec-loop/workflows/slice-wave.workflow.js
@@ -531,15 +531,29 @@ Package for anchor checks: ${CTX.run_dir}/packages/${slice.id}-round${state.revi
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
@@ -714,17 +728,63 @@ function refactorRadiusGate(slice, state, plan) {
   // suppressed_by_answer) and the slice proceeds.
   if (verdict.state !== 'EXCEEDED' || answered) return null
   return esc(slice, 'refactor-scope', refactorAsk(slice, verdict))
 }
 
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
   const radius = refactorRadiusGate(slice, state, plan)
   if (radius) return { stop: escalated(slice, state, radius) }
   return { plan }
 }
 
@@ -805,10 +865,52 @@ function latestAnswer(sliceId, trigger) {
 
 function councilObjectionEscalation(slice, state, ob, safety) {
   return escalated(slice, state, esc(slice, 'council-objection', { title: `${safety ? 'SAFETY — ' : ''}council objects: ${ob.objection.reason.slice(0, 60)}`, context: ob.objection.reason, question: ob.objection.question, options: [{ label: ob.objection.recommendation, detail: 'critic-recommended default', recommended: true }] }))
 }
 
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
+async function acceptRevisedPlan(slice, state, ctx) {
+  const { revised, ob, safety } = ctx
+  if (!isRevisedPlan(revised)) return { stop: councilObjectionEscalation(slice, state, ob, safety) }
+  const rc = await recritiqueRevisedPlan(slice, state, revised)
+  const flagged = !!(rc.safety && rc.safety.flag === true)
+  const accepted = rc.verdict !== 'OBJECT' && !flagged
+  state.events.push({ scope: slice.id, type: 'replan-recheck', payload: { verdict: rc.verdict, safety: flagged, accepted, reason: accepted ? null : objectionSource(rc, ob).objection.reason } })
+  if (accepted) return { plan: revised }
+  return { stop: councilObjectionEscalation(slice, state, objectionSource(rc, ob), flagged || safety) }
+}
+
 // The council OBJECT branch: an unanswered fixable objection gets one replan
 // attempt; anything else (safety, unfixable, or a failed replan) escalates.
 // answered → proceed with the existing plan; the answer is already injected
 // into downstream prompts via answerFor().
 async function resolveCouncilObjection(slice, state, ctx) {
@@ -816,11 +918,11 @@ async function resolveCouncilObjection(slice, state, ctx) {
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
