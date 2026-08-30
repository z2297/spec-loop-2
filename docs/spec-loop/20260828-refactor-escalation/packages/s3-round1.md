# Review package: b5e39c9da968dfab632d7ffcf50e0ca88b4bea7b..c0fc6f9  (context: -U5)

## Commits
c0fc6f9 docs(spec-loop): document the plan-time refactor-radius ceiling and its event
d430fe2 feat(spec-loop): render refactor-radius evaluations into the decisions log
effd994 feat(spec-loop): halt at plan time and ask when a declared rewrite is over the ceiling
d1627d7 feat(spec-loop): record every refactor-radius evaluation, no-fire included
f87962b test(spec-loop): harness fixtures for the plan-time refactor radius
c51cdc9 feat(spec-loop): declare a plan-time refactor radius on PLAN_RESULT
996ec96 feat(spec-loop): judge a declared refactor radius in JS, never by coercion

## Files changed
 .github/workflows/validate.yml                     |   9 +-
 CHANGELOG.md                                       |  16 ++
 plugins/spec-loop/commands/spec-loop.md            |  11 +-
 plugins/spec-loop/references/run-state-v2.md       |  17 +-
 plugins/spec-loop/scripts/run_state.py             |   6 +-
 plugins/spec-loop/scripts/slice_wave_harness.mjs   |  33 +++
 .../spec-loop/scripts/slice_wave_radius.test.mjs   | 166 ++++++++++++
 plugins/spec-loop/scripts/test_run_state.py        |  17 ++
 .../scripts/test_slice_wave_contract_radius.py     | 301 +++++++++++++++++++++
 plugins/spec-loop/workflows/slice-wave.workflow.js | 168 +++++++++++-
 10 files changed, 732 insertions(+), 12 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
".github/workflows/validate.yml": [
[
71,
74
],
[
81,
82
]
],
"CHANGELOG.md": [
[
9,
24
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
]
],
"plugins/spec-loop/references/run-state-v2.md": [
[
153,
154
],
[
185,
198
]
],
"plugins/spec-loop/scripts/run_state.py": [
[
86,
88
],
[
91,
91
]
],
"plugins/spec-loop/scripts/slice_wave_harness.mjs": [
[
198,
230
]
],
"plugins/spec-loop/scripts/slice_wave_radius.test.mjs": [
[
1,
166
]
],
"plugins/spec-loop/scripts/test_run_state.py": [
[
825,
830
],
[
1052,
1062
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_radius.py": [
[
1,
301
]
],
"plugins/spec-loop/workflows/slice-wave.workflow.js": [
[
33,
33
],
[
65,
72
],
[
216,
305
],
[
462,
463
],
[
656,
718
],
[
726,
727
]
]
}
```

## Diff
diff --git a/.github/workflows/validate.yml b/.github/workflows/validate.yml
index fcec2d9..b0a8d50 100644
--- a/.github/workflows/validate.yml
+++ b/.github/workflows/validate.yml
@@ -66,19 +66,22 @@ jobs:
         # gates, both fail closed, mirroring the client JS step: exit status,
         # and a minimum TAP count so an emptied file cannot pass silently.
         # Scope: deterministic control flow only. The real Workflow-host seam
         # is NOT covered here — see the test file's own honest-limit header.
         run: |
-          out=$(node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs 2>&1)
+          # Two modules now: the second covers the plan-time refactor-radius gate, split out
+          # because the first sits at the 300-line class_lines ceiling.
+          out=$(node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs \
+                            plugins/spec-loop/scripts/slice_wave_radius.test.mjs 2>&1)
           rc=$?
           echo "$out"
           if [ "$rc" -ne 0 ]; then
             echo "FAIL: wave harness exited non-zero (rc=$rc)"; exit "$rc"
           fi
           ran=$(printf '%s\n' "$out" | sed -n 's/^# tests \([0-9][0-9]*\).*/\1/p')
-          if [ "${ran:-0}" -lt 14 ]; then
-            echo "FAIL: only ${ran:-0} wave harness tests ran (expected >= 14)"; exit 1
+          if [ "${ran:-0}" -lt 45 ]; then
+            echo "FAIL: only ${ran:-0} wave harness tests ran (expected >= 45)"; exit 1
           fi
 
       - name: Install Claude Code CLI
         run: npm install -g @anthropic-ai/claude-code
 
diff --git a/CHANGELOG.md b/CHANGELOG.md
index cb53571..45c585d 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -4,10 +4,26 @@ All notable changes to the spec-loop plugin are documented here. The format is
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
 
 ## [2.2.2] - 2026-08-28
 ### Added
 - **The quality gate counts branch keywords in code, not in prose.** `quality_gate.py` now
   masks the content of string literals and comments before it scans a source, so a branch word
diff --git a/plugins/spec-loop/commands/spec-loop.md b/plugins/spec-loop/commands/spec-loop.md
index d05cd94..591648b 100644
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
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index ae84e20..41e0675 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -148,11 +148,12 @@ stamps `ts` — workflow scripts have no clock).
 
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
@@ -179,10 +180,24 @@ best-effort):
   override`, and override keys matching no slice of the dispatched wave are announced the
   same way on the wave's first slice. The value is coerced with `Number()`, so a JSON string
   reading as a whole number — `"14"` — is read as the integer 14 and judged against the tier
   default like any other value.
   The discard is therefore visible without waiting on a second cap record.
+- **`refactor-radius`** payload: `{summary, state, exceeded[], measured{rewrite_ratio,
+  touched_existing_files, rewritten_lines}, thresholds{enabled, max_rewrite_ratio,
+  max_touched_existing_files, min_rewritten_lines}|null}`, plus `suppressed_by_answer: true`
+  when a human has already answered this slice's `refactor-scope` escalation. Emitted by
+  the wave's PLAN stage on EVERY evaluation — `state` is one of `NOT_CONFIGURED`,
+  `DISABLED`, `NOT_MEASURED`, `WITHIN`, `BELOW_FLOOR`, `EXCEEDED`, and only `EXCEEDED`
+  halts. The no-fire cases are emitted precisely because a ceiling that silently declines
+  to fire is invisible narrowing: `measured` and `thresholds` are both present in every
+  state so a reader never re-derives why nothing happened. `measured` is null-honest —
+  an undeclared number is `null`, never `0`, and `0` is a real measurement. The numbers
+  are planner-DECLARED: a proxy declared before implementation, not a measured diff, so
+  they cannot catch a blowup discovered mid-implementation, and no second,
+  post-implementation checkpoint exists. `thresholds` is `null` only when
+  `ctx.refactor_radius` was absent or unusable.
 - **`wave-collected`** payload carries the per-wave aggregates the workflow
   completion notification reports: `{index, agent_count, subagent_tokens,
   duration_ms}` — the honest wave-level token/duration channel while
   per-dispatch stamps are unavailable. Optional, null-honest.
 - **`council-verdict`** payload carries `safety: bool` — whether the verdict
diff --git a/plugins/spec-loop/scripts/run_state.py b/plugins/spec-loop/scripts/run_state.py
index 6352ec4..95cb03e 100644
--- a/plugins/spec-loop/scripts/run_state.py
+++ b/plugins/spec-loop/scripts/run_state.py
@@ -81,14 +81,16 @@ MIN_SPLIT_CHILDREN = 2
 
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
diff --git a/plugins/spec-loop/scripts/slice_wave_harness.mjs b/plugins/spec-loop/scripts/slice_wave_harness.mjs
index 65f22bb..eefaa7c 100644
--- a/plugins/spec-loop/scripts/slice_wave_harness.mjs
+++ b/plugins/spec-loop/scripts/slice_wave_harness.mjs
@@ -193,10 +193,43 @@ const PIPELINE = {
   "fix:1": { status: "DONE", touched_files: ["a.py"], addressed: ["r0-f1"], refuted: [], commits: { base: "0000000", head: "f1x0000" } },
   "re-review:1": { verdicts: [{ finding_id: "r0-f1", verdict: "ADDRESSED" }], new_breakage: [] },
   "verify:1": VERIFY_PASS,
 };
 
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
 export const PIPELINE_LABELS = Object.keys(PIPELINE).map((role) => "s1:" + role);
 
 // Records the label and the prompt of every dispatch and answers each one with
 // the return above. An unmapped role throws under its own name: a new stage
 // must be mapped here rather than degrading a run into a fail-closed path in
diff --git a/plugins/spec-loop/scripts/slice_wave_radius.test.mjs b/plugins/spec-loop/scripts/slice_wave_radius.test.mjs
new file mode 100644
index 0000000..345d856
--- /dev/null
+++ b/plugins/spec-loop/scripts/slice_wave_radius.test.mjs
@@ -0,0 +1,166 @@
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
+  const split = { status: "SPLIT", split: { children: [] } };
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
diff --git a/plugins/spec-loop/scripts/test_run_state.py b/plugins/spec-loop/scripts/test_run_state.py
index 8d5855d..a17e2af 100644
--- a/plugins/spec-loop/scripts/test_run_state.py
+++ b/plugins/spec-loop/scripts/test_run_state.py
@@ -820,10 +820,16 @@ class TestDecisionLine(unittest.TestCase):
         payload = {"summary": "use the CSV writer", "over_scope": True}
         line = self.line("decision", payload)
         self.assertIn("DECISION: use the CSV writer", line)
         self.assertNotIn("SCOPE", line)
 
+    def test_refactor_radius_summary(self):
+        self.assertIn("refactor radius EXCEEDED: over the ceiling",
+                      self.line("refactor-radius",
+                                {"summary": "refactor radius EXCEEDED: over the ceiling",
+                                 "state": "EXCEEDED"}))
+
 
 class TestRenderReport(unittest.TestCase):
     def test_done_report(self):
         body = rs.render_report(sidecar())
         self.assertIn("# Slice s1 — DONE", body)
@@ -1041,10 +1047,21 @@ class TestAppendEvent(RunStateTestCase):
         logged = ("DECISION", "DEFERRED", "COUNCIL-VERDICT", "QUALITY-GATE",
                   "INTEGRATION-CHECK", "PHASE5-GATE")
         for marker in logged:
             self.assertIn(marker, body)
 
+    def test_a_refactor_radius_event_renders_a_log_line(self):
+        # A threshold that declines to fire is the silent-exclusion defect
+        # this event exists to prevent, so the NO-FIRE case has to reach the
+        # human surface too, not only the machine-readable events.jsonl.
+        payload = {"summary": "refactor radius WITHIN: every declared number "
+                              "is at or under its ceiling", "state": "WITHIN"}
+        event = rs.build_event(TS, "s1", "refactor-radius", payload)
+        rs.append_event(self.run_dir, event)
+        self.assertIn("REFACTOR-RADIUS: refactor radius WITHIN",
+                     self.read("decisions-log.md"))
+
     def test_escalation_opened_writes_a_full_entry(self):
         event = rs.build_event(TS, "s1", "escalation-opened", escalation())
         rs.append_event(self.run_dir, event)
         body = self.read("escalations.md")
         self.assertIn("# Escalations", body)
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_radius.py b/plugins/spec-loop/scripts/test_slice_wave_contract_radius.py
new file mode 100644
index 0000000..e4fbafd
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_radius.py
@@ -0,0 +1,301 @@
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
+existing one: `slice_wave_contract_base.py` sits at 299 non-blank lines and
+the quality gate's `class_lines` threshold is 300 whole-file non-blank lines,
+so every constant below is module-local by necessity as well as by the
+snippet-as-named-constant rule.
+
+Usage:
+    python3 -m unittest discover -s plugins/spec-loop/scripts \\
+        -p 'test_slice_wave_contract_radius.py'
+"""
+
+import json
+import os
+import shutil
+import subprocess
+import sys
+import tempfile
+import unittest
+from pathlib import Path
+
+sys.path.insert(0, str(Path(__file__).resolve().parent))
+
+from slice_wave_contract_base import COMMAND_MD, RUN_STATE_MD, WorkflowSourceTestCase  # noqa: E402
+
+RADIUS_START = "const RADIUS_NULL ="
+RADIUS_END = "function scopeRecord("
+RADIUS_NUM = ("const radiusNum = (v) => "
+              "(typeof v === 'number' && Number.isFinite(v)) ? v : null")
+RATIO_GUARD = "const over = (v, max) => v !== null && max !== null && v > max"
+FLOOR_GUARD = "m.rewritten_lines !== null && limits.min_rewritten_lines !== null"
+NOT_CONFIGURED = "state: 'NOT_CONFIGURED'"
+NOT_MEASURED = "state: 'NOT_MEASURED'"
+EXCEEDED = "state: 'EXCEEDED'"
+COERCION_OPERATORS = (">=", "<=")
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
+# The shipped defaults, and the declared-radius fixtures each state needs.
+# Module-level because nesting_depth is measured from raw indentation, so a
+# hanging literal inside a test body scores as real block nesting.
+LIMITS = {"enabled": True, "max_rewrite_ratio": 0.5,
+          "max_touched_existing_files": 8, "min_rewritten_lines": 150}
+BIG = {"rewrite_ratio": 0.9, "touched_existing_files": 12, "rewritten_lines": 900}
+AT_CEILING = {"rewrite_ratio": 0.5, "touched_existing_files": 8, "rewritten_lines": 900}
+TINY = {"rewrite_ratio": 0.9, "touched_existing_files": 12, "rewritten_lines": 20}
+ZEROED = {"rewrite_ratio": 0, "touched_existing_files": 0, "rewritten_lines": 0}
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
+    """Six states, none collapsed into another. A substring assertion can
+    prove the word NOT_MEASURED appears in the file and nothing about which
+    inputs reach it, so this class runs the real helpers under real node and
+    reads the verdicts back: absence, disablement, an unmeasured plan, a plan
+    exactly at its ceiling, a breach, and a breach under the noise floor."""
+
+    def radius_status(self, cases):
+        """refactorRadiusStatus() applied to each [plan, ctx] pair by node."""
+        node = shutil.which("node")
+        if not node:
+            self.skipTest("node is not available on this machine")
+        source = self.between(RADIUS_START, RADIUS_END)
+        fd, path = tempfile.mkstemp(suffix=".mjs")
+        try:
+            with os.fdopen(fd, "w") as fh:
+                fh.write(RADIUS_DRIVER % (source, json.dumps(cases)))
+            proc = subprocess.run(
+                [node, path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
+            out = proc.stdout.decode()
+            self.assertEqual(proc.returncode, 0, "node failed:\n%s" % (out,))
+            return json.loads(out)
+        finally:
+            os.unlink(path)
+
+    def test_an_absent_ctx_block_is_not_configured_and_compares_nothing(self):
+        # In order: no block at all, a string where an object belongs, and an
+        # array. None of the three is a ceiling, and guessing the shipped
+        # defaults here would give the repo two sources of truth for a number
+        # the operator is invited to tune.
+        got = self.radius_status([[BIG, None], [BIG, "0.5"], [BIG, [0.5]]])
+        self.assertEqual([g["state"] for g in got], ["NOT_CONFIGURED"] * 3)
+        self.assertEqual([g["thresholds"] for g in got], [None, None, None])
+        self.assertEqual([g["exceeded"] for g in got], [[], [], []])
+
+    def test_a_disabled_block_never_fires_however_large_the_numbers(self):
+        got = self.radius_status([[BIG, dict(LIMITS, enabled=False)]])
+        self.assertEqual(got[0]["state"], "DISABLED")
+
+    def test_an_absent_plan_block_is_not_measured_with_three_explicit_nulls(self):
+        # PLAN_RESULT.required is ['status'] only, so all three reads are
+        # optional-field reads: absent, empty and array-shaped all land on the
+        # same fail-open state rather than throwing or inventing a zero.
+        got = self.radius_status([[None, LIMITS], [{}, LIMITS], [[1], LIMITS]])
+        self.assertEqual([g["state"] for g in got], ["NOT_MEASURED"] * 3)
+        self.assertEqual(got[0]["measured"], THREE_NULLS)
+
+    def test_declared_zeros_are_a_measurement_and_never_read_as_absence(self):
+        got = self.radius_status([[ZEROED, LIMITS]])
+        self.assertEqual(got[0]["state"], "WITHIN")
+        self.assertEqual(got[0]["measured"]["rewrite_ratio"], 0)
+
+    def test_string_numbers_are_not_measurements_and_are_never_coerced(self):
+        got = self.radius_status([[STRINGY, LIMITS]])
+        self.assertEqual(got[0]["state"], "NOT_MEASURED")
+        self.assertIsNone(got[0]["measured"]["rewrite_ratio"])
+
+    def test_a_plan_exactly_at_both_ceilings_is_within_and_does_not_halt(self):
+        got = self.radius_status([[AT_CEILING, LIMITS]])
+        self.assertEqual(got[0]["state"], "WITHIN")
+
+    def test_each_ceiling_is_breached_on_its_own_and_is_named_in_exceeded(self):
+        ratio = {"rewrite_ratio": 0.9, "rewritten_lines": 900}
+        files = {"touched_existing_files": 12, "rewritten_lines": 900}
+        got = self.radius_status([[ratio, LIMITS], [files, LIMITS]])
+        self.assertEqual([g["state"] for g in got], ["EXCEEDED", "EXCEEDED"])
+        self.assertEqual(got[0]["exceeded"], ["rewrite_ratio"])
+        self.assertEqual(got[1]["exceeded"], ["touched_existing_files"])
+
+    def test_the_noise_floor_suppresses_a_breach_but_keeps_the_numbers(self):
+        got = self.radius_status([[TINY, LIMITS]])
+        self.assertEqual(got[0]["state"], "BELOW_FLOOR")
+        self.assertEqual(got[0]["exceeded"], BOTH_CEILINGS)
+        self.assertEqual(got[0]["measured"]["rewritten_lines"], 20)
+
+    def test_an_unmeasured_line_count_does_not_suppress_a_measured_breach(self):
+        # The floor can only silence a fire it can prove is noise. A missing
+        # rewritten_lines proves nothing, so the measured ratio breach stands.
+        got = self.radius_status([[{"rewrite_ratio": 0.9}, LIMITS]])
+        self.assertEqual(got[0]["state"], "EXCEEDED")
+
+    def test_every_verdict_carries_the_thresholds_it_compared_against(self):
+        # A threshold that silently declines to fire is a permanent invisible
+        # narrowing, so the no-fire and not-measured verdicts carry the
+        # ceilings too - a reader never has to re-derive why nothing happened.
+        got = self.radius_status([[BIG, LIMITS], [ZEROED, LIMITS], [None, LIMITS]])
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
+    def test_the_three_no_fire_states_exist_as_their_own_named_branches(self):
+        for marker in (NOT_CONFIGURED, NOT_MEASURED, EXCEEDED):
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
+STAGE_PLAN_START = "async function stagePlan(slice, state) {"
+STAGE_PLAN_END = "// Stage C helpers"
+GATE_FN_START = "function refactorRadiusGate(slice, state, plan) {"
+GATE_FN_END = "\n}\n"
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
diff --git a/plugins/spec-loop/workflows/slice-wave.workflow.js b/plugins/spec-loop/workflows/slice-wave.workflow.js
index 6672097..77e859a 100644
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
@@ -203,10 +211,100 @@ function qualityStatus(q) {
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
+// Six states, none collapsed into another, and only EXCEEDED halts anything.
+// The two halves of this check have opposite answers on purpose: a
+// measurement that is missing, unconfigured or disabled FAILS OPEN (proceed,
+// and the caller records it loudly), while a measurement that succeeded and
+// is over its ceiling FAILS CLOSED (halt and ask). Collapsing them would
+// either halt every run with an old controller or halt none of them. (PURE)
+function refactorRadiusStatus(radius, limits) {
+  const measured = radiusNumbers(radius)
+  const base = { measured, thresholds: limits, exceeded: [] }
+  if (!limits) return { ...base, thresholds: null, state: 'NOT_CONFIGURED', reason: 'ctx.refactor_radius is absent or is not an object, so no ceiling was compared' }
+  if (!limits.enabled) return { ...base, state: 'DISABLED', reason: 'refactor_radius.enabled is false in the effective gate config' }
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
@@ -359,11 +457,12 @@ function planPrompt(slice) {
 
 Plan slice ${slice.id} of run ${A.run_id}: ${slice.goal}
 Named files: ${slice.files.join(', ') || '(none named)'} · Subsystems: ${slice.subsystems.join(', ') || '—'}
 Risk tier: ${slice.risk_tier} · Split depth: ${slice.depth} (split allowed only below depth 2)
 Write the plan to exactly: ${CTX.run_dir}/plans/${slice.id}.md
-Test/build command for verification steps: ${CTX.test_command}${answerFor(slice, 'ambiguity')}${answerFor(slice, 'material-assumption')}${answerFor(slice, 'refactor-scope')}`
+Test/build command for verification steps: ${CTX.test_command}
+Also return refactor_radius: your DECLARED estimate of how much EXISTING code this plan rewrites — {rewrite_ratio: existing lines your tasks rewrite or delete ÷ total lines the plan changes, touched_existing_files: how many pre-existing files your tasks modify, rewritten_lines: the absolute count of existing lines rewritten or deleted, basis: one sentence on how you counted}. Report the numbers only, never a verdict: the workflow judges them against the run's ceiling. If you genuinely cannot estimate one, omit it rather than guessing a zero.${answerFor(slice, 'ambiguity')}${answerFor(slice, 'material-assumption')}${answerFor(slice, 'refactor-scope')}`
 }
 
 function criticPrompt(slice, plan, role) {
   return `${packet(slice)}
 
@@ -552,17 +651,82 @@ function doneResult(slice, state, status, extra) {
     tests: state.tests, quality: state.quality, escalations: state.escalations,
     agents_used: state.agentsUsed, wave: A.wave_index, events: state.events, ...extra,
   }
 }
 
+// One line of copy naming every number on both sides of the comparison. A
+// human answering this needs the measurements AND the ceilings they were
+// judged against in the record itself, not a pointer to a config file they
+// would have to resolve by hand. (PURE)
+const radiusPhrase = (v) => `declared rewrite ratio ${v.measured.rewrite_ratio}, touched existing files ${v.measured.touched_existing_files}, rewritten lines ${v.measured.rewritten_lines}; ceilings ${v.thresholds.max_rewrite_ratio} ratio / ${v.thresholds.max_touched_existing_files} files, noise floor ${v.thresholds.min_rewritten_lines} lines`
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
+  return {
+    scope: slice.id, type: 'refactor-radius',
+    payload: {
+      summary: `refactor radius ${verdict.state}: ${verdict.reason}`,
+      state: verdict.state, exceeded: verdict.exceeded,
+      measured: verdict.measured, thresholds: verdict.thresholds,
+      ...(answered ? { suppressed_by_answer: true } : {}),
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
+  const answered = answerKeysFor(slice.id, 'refactor-scope').length > 0
+  state.events.push(radiusEvent(slice, verdict, answered))
+  // Answered means the human already ruled on this slice's radius. Raising
+  // the same question again would deadlock the slice at the same stage
+  // forever, so the verdict stays EXCEEDED in the event (with
+  // suppressed_by_answer) and the slice proceeds.
+  if (verdict.state !== 'EXCEEDED' || answered) return null
+  return esc(slice, 'refactor-scope', refactorAsk(slice, verdict))
+}
+
 // Stage P — plan (+ right-size gate inside the planner)
 async function stagePlan(slice, state) {
   const plan = await dispatch(slice, state, 'plan', planPrompt(slice),
     { agentType: 'spec-loop:slice-planner', schema: PLAN_RESULT, effort: 'low' })
   if (!plan) return { stop: escalated(slice, state, esc(slice, 'ambiguity', { title: 'planner returned no result', context: 'The planner dispatch failed terminally.', question: 'Retry the slice, or drop it?', options: [] })) }
   if (plan.status === 'SPLIT') return { stop: doneResult(slice, state, 'SPLIT', { split: plan.split }) }
   if (plan.status === 'ESCALATE') return { stop: escalated(slice, state, esc(slice, plan.escalation.trigger, plan.escalation)) }
+  const radius = refactorRadiusGate(slice, state, plan)
+  if (radius) return { stop: escalated(slice, state, radius) }
   return { plan }
 }
 
 // Stage C helpers — panel selection, verdict rollup, and the OBJECT branch.
 // Each helper below is kept single-purpose and small on its own terms (own
