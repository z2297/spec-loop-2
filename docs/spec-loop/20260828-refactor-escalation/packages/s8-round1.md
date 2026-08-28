# Review package: 25b7b6c57fa4a67804578f15c25024cf46cfe184..18aaf3f3a732800e560ffea6d1358f61e3c35089  (context: -U5)

## Commits
18aaf3f docs(spec-loop): document WITHIN_PARTIAL and the per-dimension radius coverage keys
6a16f71 spec-loop(20260828-refactor-escalation): executing tests for a partially usable radius ceiling
e2c458d spec-loop(20260828-refactor-escalation): per-dimension radius coverage and WITHIN_PARTIAL

## Files changed
 .github/workflows/validate.yml                     |  9 +-
 plugins/spec-loop/references/run-state-v2.md       | 16 +++-
 .../scripts/slice_wave_radius_partial.test.mjs     | 97 ++++++++++++++++++++++
 .../scripts/test_slice_wave_contract_radius.py     | 57 ++++++++++++-
 plugins/spec-loop/workflows/slice-wave.workflow.js | 71 ++++++++++++++--
 5 files changed, 235 insertions(+), 15 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
".github/workflows/validate.yml": [
[
71,
72
],
[
75,
75
],
[
83,
84
]
],
"plugins/spec-loop/references/run-state-v2.md": [
[
187,
188
],
[
193,
194
],
[
209,
217
]
],
"plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs": [
[
1,
97
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_radius.py": [
[
45,
45
],
[
48,
49
],
[
65,
67
],
[
176,
213
],
[
238,
239
],
[
341,
342
],
[
364,
370
]
],
"plugins/spec-loop/workflows/slice-wave.workflow.js": [
[
311,
362
],
[
374,
379
],
[
383,
384
],
[
390,
392
],
[
763,
763
],
[
809,
809
]
]
}
```

## Diff
diff --git a/.github/workflows/validate.yml b/.github/workflows/validate.yml
index 6188052..c0acadb 100644
--- a/.github/workflows/validate.yml
+++ b/.github/workflows/validate.yml
@@ -66,23 +66,24 @@ jobs:
         # gates, both fail closed, mirroring the client JS step: exit status,
         # and a minimum TAP count so an emptied file cannot pass silently.
         # Scope: deterministic control flow only. The real Workflow-host seam
         # is NOT covered here — see the test file's own honest-limit header.
         run: |
-          # Three modules now: the third covers the optional-read guards and the post-OBJECT
-          # replan re-check, split out because the first sits at the 300-line class_lines ceiling.
+          # Four modules now: the fourth covers a partially usable radius ceiling, split out because
+          # slice_wave_radius.test.mjs sits at the 300-line class_lines ceiling.
           out=$(node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs \
                             plugins/spec-loop/scripts/slice_wave_radius.test.mjs \
+                            plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs \
                             plugins/spec-loop/scripts/slice_wave_replan.test.mjs 2>&1)
           rc=$?
           echo "$out"
           if [ "$rc" -ne 0 ]; then
             echo "FAIL: wave harness exited non-zero (rc=$rc)"; exit "$rc"
           fi
           ran=$(printf '%s\n' "$out" | sed -n 's/^# tests \([0-9][0-9]*\).*/\1/p')
-          if [ "${ran:-0}" -lt 63 ]; then
-            echo "FAIL: only ${ran:-0} wave harness tests ran (expected >= 63)"; exit 1
+          if [ "${ran:-0}" -lt 71 ]; then
+            echo "FAIL: only ${ran:-0} wave harness tests ran (expected >= 71)"; exit 1
           fi
 
       - name: Install Claude Code CLI
         run: npm install -g @anthropic-ai/claude-code
 
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index d70f65d..10fcc6d 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -182,17 +182,18 @@ best-effort):
   reading as a whole number — `"14"` — is read as the integer 14 and judged against the tier
   default like any other value.
   The discard is therefore visible without waiting on a second cap record.
 - **`refactor-radius`** payload: `{summary, state, exceeded[], measured{rewrite_ratio,
   touched_existing_files, rewritten_lines}, thresholds{enabled, max_rewrite_ratio,
-  max_touched_existing_files, min_rewritten_lines}|null, basis}`, plus `suppressed_by_answer: true`
+  max_touched_existing_files, min_rewritten_lines}|null, basis, compared[], skipped[]}`, plus
+  `suppressed_by_answer: true`
   when — and only when — the state is `EXCEEDED` and a truthy human answer to this slice's
   `refactor-scope` escalation kept it from halting; the key is absent, never `false`, in every
   other case, so counting it counts real waived halts. Emitted by
   the wave's PLAN stage on EVERY evaluation — `state` is one of `NOT_CONFIGURED`,
-  `DISABLED`, `NO_USABLE_CEILING`, `NOT_MEASURED`, `WITHIN`, `BELOW_FLOOR`, `EXCEEDED`,
-  and only `EXCEEDED` halts. The no-fire cases are emitted precisely because a ceiling that silently declines
+  `DISABLED`, `NO_USABLE_CEILING`, `NOT_MEASURED`, `WITHIN`, `WITHIN_PARTIAL`, `BELOW_FLOOR`,
+  `EXCEEDED`, and only `EXCEEDED` halts. The no-fire cases are emitted precisely because a ceiling that silently declines
   to fire is invisible narrowing: `measured` and `thresholds` are both present in every
   state so a reader never re-derives why nothing happened. `measured` is null-honest —
   an undeclared number is `null`, never `0`, and `0` is a real measurement. The numbers
   are planner-DECLARED: a proxy declared before implementation, not a measured diff, so
   they cannot catch a blowup discovered mid-implementation, and no second,
@@ -203,10 +204,19 @@ best-effort):
   the number was reached — and no state, threshold or comparison reads it.
   `NO_USABLE_CEILING` means the block was present and enabled but neither `max_rewrite_ratio`
   nor `max_touched_existing_files` survived as a number — a mistyped ceiling. It fails open
   like the other no-fire states, and it is separate from `WITHIN` because a plan cannot be
   "under a ceiling" that was never compared.
+  `compared[]` and `skipped[]` name, per dimension, which DECLARED maxima numbers
+  (`rewrite_ratio`, `touched_existing_files`) were actually judged against a usable ceiling and
+  which were not; a number the plan never declared appears in neither. `WITHIN_PARTIAL` is
+  `NO_USABLE_CEILING`'s per-dimension twin: the block was usable overall — one ceiling survived —
+  but at least one declared number had no ceiling of its own, so nothing compared was over and
+  `WITHIN` would have claimed a comparison that never ran. It fails open exactly like `WITHIN`:
+  an unusable ceiling never causes a halt, it only stops the record claiming a comparison it did
+  not make. HONEST LIMIT: this says which numbers were compared, not whether the declared
+  numbers were true — they remain planner declarations, and no measured diff is taken anywhere.
 - **`wave-collected`** payload carries the per-wave aggregates the workflow
   completion notification reports: `{index, agent_count, subagent_tokens,
   duration_ms}` — the honest wave-level token/duration channel while
   per-dispatch stamps are unavailable. Optional, null-honest.
 - **`council-verdict`** payload carries `safety: bool` — whether the verdict
diff --git a/plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs b/plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs
new file mode 100644
index 0000000..c1c4627
--- /dev/null
+++ b/plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs
@@ -0,0 +1,97 @@
+// slice_wave_radius_partial.test.mjs — a PARTIALLY usable radius ceiling, EXECUTED.
+// One valid ceiling beside one mistyped one is a usable configuration, so it gets
+// past radiusNoCeiling; the declared number on the null side was then reported as
+// being under a ceiling nothing had compared it to. HONEST LIMIT: this drives the
+// workflow's deterministic control flow against the mock sandbox in
+// slice_wave_harness.mjs — the real Workflow-host seam stays unverified, and the
+// numbers are planner-DECLARED, so nothing here proves a diff was that size.
+// A fourth module rather than more cases in slice_wave_radius.test.mjs, which sits
+// at 293 non-blank lines against the quality gate's 300-line class_lines ceiling.
+
+import test from "node:test";
+import assert from "node:assert/strict";
+import {
+  runWave, sliceFixture, radiusArgs, RADIUS_DEFAULTS,
+  planWithRadius, planThenStop } from "./slice_wave_harness.mjs";
+
+const S1 = () => [sliceFixture("s1")];
+// A ratio ceiling that did not survive refactorLimits: null in one config,
+// a mistyped string in the other. Both must behave identically.
+const NO_RATIO_CEILING = { ...RADIUS_DEFAULTS, max_rewrite_ratio: null };
+const STRING_RATIO_CEILING = { ...RADIUS_DEFAULTS, max_rewrite_ratio: "0.5" };
+// The motivating shape: a heavy declared ratio beside a small file count.
+const HEAVY_RATIO = { rewrite_ratio: 0.9, touched_existing_files: 2, rewritten_lines: 900, basis: "b" };
+const SMALL = { rewrite_ratio: 0.1, touched_existing_files: 2, rewritten_lines: 40, basis: "b" };
+const BIG = { rewrite_ratio: 0.9, touched_existing_files: 12, rewritten_lines: 900, basis: "b" };
+const FILES_ONLY = { touched_existing_files: 2, rewritten_lines: 40, basis: "b" };
+
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
+const record = (r) => r.escalations.find((e) => e.trigger === "refactor-scope");
+
+test("a declared ratio with no usable ceiling is never reported as within one", async () => {
+  const ev = await only(HEAVY_RATIO, NO_RATIO_CEILING);
+  assert.equal(ev.payload.state, "WITHIN_PARTIAL");
+  assert.equal(ev.payload.state === "WITHIN", false);
+});
+
+test("the event names which dimensions were compared and which were skipped", async () => {
+  const ev = await only(HEAVY_RATIO, NO_RATIO_CEILING);
+  assert.deepEqual(ev.payload.compared, ["touched_existing_files"]);
+  assert.deepEqual(ev.payload.skipped, ["rewrite_ratio"]);
+});
+
+test("the summary says plainly that the ratio was never compared", async () => {
+  const ev = await only(HEAVY_RATIO, NO_RATIO_CEILING);
+  assert.ok(ev.payload.summary.startsWith("refactor radius WITHIN_PARTIAL"));
+  assert.ok(ev.payload.summary.includes("rewrite_ratio"));
+  assert.ok(ev.payload.summary.includes("no usable ceiling"));
+});
+
+test("a mistyped string ceiling behaves exactly like an absent one", async () => {
+  const ev = await only(HEAVY_RATIO, STRING_RATIO_CEILING);
+  assert.equal(ev.payload.state, "WITHIN_PARTIAL");
+  assert.deepEqual(ev.payload.skipped, ["rewrite_ratio"]);
+});
+
+test("a partial verdict fails open: the slice raises nothing and exceeds nothing", async () => {
+  const result = await evaluate(HEAVY_RATIO, NO_RATIO_CEILING);
+  assert.equal(record(result), undefined);
+  assert.deepEqual(radiusEvents(result)[0].payload.exceeded, []);
+});
+
+test("a fully usable config still records WITHIN with nothing skipped", async () => {
+  const ev = await only(SMALL, RADIUS_DEFAULTS);
+  assert.equal(ev.payload.state, "WITHIN");
+  assert.deepEqual(ev.payload.skipped, []);
+  assert.deepEqual(ev.payload.compared, ["rewrite_ratio", "touched_existing_files"]);
+});
+
+test("a real breach beside an uncompared dimension still halts the slice", async () => {
+  const result = await evaluate(BIG, NO_RATIO_CEILING);
+  const ev = radiusEvents(result)[0];
+  assert.equal(ev.payload.state, "EXCEEDED");
+  assert.deepEqual(ev.payload.skipped, ["rewrite_ratio"]);
+  assert.equal(record(result).trigger, "refactor-scope");
+});
+
+test("the escalation context tells the human what was not compared", async () => {
+  const result = await evaluate(BIG, NO_RATIO_CEILING);
+  assert.ok(record(result).context.includes("not compared for want of a usable ceiling"));
+  assert.ok(record(result).context.includes("rewrite_ratio"));
+});
+
+test("a number the plan never declared is not counted as skipped", async () => {
+  const ev = await only(FILES_ONLY, NO_RATIO_CEILING);
+  assert.equal(ev.payload.state, "WITHIN");
+  assert.deepEqual(ev.payload.skipped, []);
+});
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_radius.py b/plugins/spec-loop/scripts/test_slice_wave_contract_radius.py
index cc17fd3..cd5aa22 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract_radius.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_radius.py
@@ -40,12 +40,15 @@ RADIUS_NUM = ("const radiusNum = (v) => "
 RATIO_GUARD = "const over = (v, max) => v !== null && max !== null && v > max"
 FLOOR_GUARD = "m.rewritten_lines !== null && limits.min_rewritten_lines !== null"
 NOT_CONFIGURED = "state: 'NOT_CONFIGURED'"
 NOT_MEASURED = "state: 'NOT_MEASURED'"
 NO_USABLE_CEILING = "state: 'NO_USABLE_CEILING'"
+WITHIN_PARTIAL = "state: 'WITHIN_PARTIAL'"
 EXCEEDED = "state: 'EXCEEDED'"
 COERCION_OPERATORS = (">=", "<=")
+NAMED_BRANCHES = (NOT_CONFIGURED, NO_USABLE_CEILING, NOT_MEASURED,
+                  WITHIN_PARTIAL, EXCEEDED)
 
 # The shipped defaults, and the declared-radius fixtures each state needs.
 # Module-level because nesting_depth is measured from raw indentation, so a
 # hanging literal inside a test body scores as real block nesting.
 LIMITS = {"enabled": True, "max_rewrite_ratio": 0.5,
@@ -57,10 +60,13 @@ ZEROED = {"rewrite_ratio": 0, "touched_existing_files": 0, "rewritten_lines": 0}
 NO_CEILINGS = {"enabled": True, "max_rewrite_ratio": None,
                "max_touched_existing_files": None, "min_rewritten_lines": 150}
 STRING_CEILINGS = {"enabled": True, "max_rewrite_ratio": "0.5",
                    "max_touched_existing_files": "8", "min_rewritten_lines": 150}
 STRINGY = {"rewrite_ratio": "0.9", "touched_existing_files": "12"}
+ONE_CEILING = dict(LIMITS, max_rewrite_ratio=None)
+PARTIAL = {"rewrite_ratio": 0.9, "touched_existing_files": 2, "rewritten_lines": 40}
+FILES_ONLY_DECLARED = {"touched_existing_files": 2, "rewritten_lines": 40}
 
 # Expected verdict fragments, hoisted for the same reason: a hanging
 # literal inside a test body is scored as real block nesting by the
 # quality gate's indentation heuristic.
 THREE_NULLS = {"rewrite_ratio": None,
@@ -165,10 +171,48 @@ class TestTheRadiusPredicateDecidesAndNotJustExists(WorkflowSourceTestCase):
         for g in got:
             self.assertEqual(g["thresholds"]["max_rewrite_ratio"], 0.5)
             self.assertEqual(g["thresholds"]["max_touched_existing_files"], 8)
             self.assertEqual(g["thresholds"]["min_rewritten_lines"], 150)
 
+    def test_a_declared_number_with_no_usable_ceiling_is_never_within_one(self):
+        # The mirror of NO_USABLE_CEILING: one mistyped ceiling beside one
+        # valid one used to short-circuit on the null side and then report
+        # WITHIN about a ratio no comparison had touched.
+        got = radius_status([[PARTIAL, ONE_CEILING]])
+        self.assertEqual(got[0]["state"], "WITHIN_PARTIAL")
+        self.assertEqual(got[0]["compared"], ["touched_existing_files"])
+        self.assertEqual(got[0]["skipped"], ["rewrite_ratio"])
+
+    def test_the_partial_verdict_names_the_dimension_it_never_compared(self):
+        got = radius_status([[PARTIAL, ONE_CEILING]])
+        self.assertIn("rewrite_ratio", got[0]["reason"])
+        self.assertIn("no usable ceiling", got[0]["reason"])
+
+    def test_a_partial_verdict_fails_open_and_exceeds_nothing(self):
+        got = radius_status([[PARTIAL, ONE_CEILING]])
+        self.assertEqual(got[0]["exceeded"], [])
+        self.assertNotEqual(got[0]["state"], "EXCEEDED")
+
+    def test_a_fully_compared_plan_keeps_todays_within_verdict_exactly(self):
+        got = radius_status([[AT_CEILING, LIMITS], [ZEROED, LIMITS]])
+        self.assertEqual([g["state"] for g in got], ["WITHIN"] * 2)
+        self.assertEqual(got[0]["compared"], BOTH_CEILINGS)
+        self.assertEqual(got[0]["skipped"], [])
+
+    def test_a_breach_beside_an_uncompared_number_still_says_which(self):
+        got = radius_status([[BIG, ONE_CEILING]])
+        self.assertEqual(got[0]["state"], "EXCEEDED")
+        self.assertEqual(got[0]["skipped"], ["rewrite_ratio"])
+        self.assertIn("rewrite_ratio", got[0]["reason"])
+
+    def test_a_number_the_plan_never_declared_is_not_reported_as_skipped(self):
+        # Silence is not a skipped comparison: only a DECLARED number can be
+        # a number that went uncompared.
+        got = radius_status([[FILES_ONLY_DECLARED, LIMITS]])
+        self.assertEqual(got[0]["state"], "WITHIN")
+        self.assertEqual(got[0]["skipped"], [])
+
 
 # ---- the guards, pinned in source ----
 
 class TestNoRadiusComparisonIsReachedByCoercion(WorkflowSourceTestCase):
     """`undefined >= n` is false and `null >= 0` is true, so an absent
@@ -189,12 +233,12 @@ class TestNoRadiusComparisonIsReachedByCoercion(WorkflowSourceTestCase):
         self.assertIn(FLOOR_GUARD, self.region())
 
     def test_a_number_is_type_checked_before_it_is_ever_a_measurement(self):
         self.assertIn(RADIUS_NUM, self.region())
 
-    def test_the_four_no_fire_states_exist_as_their_own_named_branches(self):
-        for marker in (NOT_CONFIGURED, NO_USABLE_CEILING, NOT_MEASURED, EXCEEDED):
+    def test_the_five_no_fire_states_exist_as_their_own_named_branches(self):
+        for marker in NAMED_BRANCHES:
             self.assertIn(marker, self.region())
 
 
 # ---- the declared block on PLAN_RESULT, and the planner instruction ----
 
@@ -292,10 +336,12 @@ class TestOnlyAMeasuredBreachHaltsAndOnlyAtPlanTime(WorkflowSourceTestCase):
 CTX_THREAD = "refactor_radius"
 ONE_DOOR = "--print-config"
 EVENT_IN_LIST = "`refactor-radius`"
 PAYLOAD_BULLET = "**`refactor-radius`** payload"
 PROXY_LIMIT = "a proxy declared before implementation, not a measured diff"
+PARTIAL_STATE_DOC = "`WITHIN_PARTIAL`"
+COVERAGE_KEYS_DOC = "compared[], skipped[]"
 
 
 class TestTheThresholdsReachTheWorkflowOnlyThroughCtx(WorkflowSourceTestCase):
     """The workflow has no fs and no process access by design, so the only
     lawful path for a threshold is --print-config -> the controller command
@@ -313,8 +359,15 @@ class TestTheThresholdsReachTheWorkflowOnlyThroughCtx(WorkflowSourceTestCase):
         self.assertIn(PAYLOAD_BULLET, text)
 
     def test_the_contract_states_the_pre_execution_proxy_limit_plainly(self):
         self.assertIn(PROXY_LIMIT, RUN_STATE_MD.read_text(encoding="utf-8"))
 
+    def test_the_partial_coverage_state_is_documented_in_its_single_home(self):
+        # A state a reader of the event cannot look up is a state that gets
+        # read as a typo for WITHIN.
+        text = RUN_STATE_MD.read_text(encoding="utf-8")
+        self.assertIn(PARTIAL_STATE_DOC, text)
+        self.assertIn(COVERAGE_KEYS_DOC, text)
+
 
 if __name__ == "__main__":  # pragma: no cover
     unittest.main()
diff --git a/plugins/spec-loop/workflows/slice-wave.workflow.js b/plugins/spec-loop/workflows/slice-wave.workflow.js
index ab028da..f120ceb 100644
--- a/plugins/spec-loop/workflows/slice-wave.workflow.js
+++ b/plugins/spec-loop/workflows/slice-wave.workflow.js
@@ -306,11 +306,62 @@ function radiusBelowFloor(m, limits) {
 // refactorRadiusStatus over its cognitive-complexity threshold. (PURE)
 function radiusNoCeiling(limits) {
   return limits.max_rewrite_ratio === null && limits.max_touched_existing_files === null
 }
 
-// Seven states, none collapsed into another, and only EXCEEDED halts anything.
+// The two MAXIMA dimensions paired with the ceiling key each is judged
+// against. A table rather than two more inline conditions, because the
+// coverage split and radiusBreaches must never disagree about which
+// dimensions exist: they used to, and that disagreement was the defect.
+const RADIUS_DIMS = [['rewrite_ratio', 'max_rewrite_ratio'], ['touched_existing_files', 'max_touched_existing_files']]
+
+// A list rendered for a reason sentence, or the word none. An empty join
+// would render "compared: " and read as a truncated sentence rather than as
+// an empty set. Explicit === 0 rather than a falsy length test, to keep the
+// whole block free of decisions reached by coercion. (PURE)
+const radiusList = (xs) => xs.length === 0 ? 'none' : xs.join(', ')
+
+// Per-dimension split of the DECLARED numbers into the ones this evaluation
+// actually compared and the ones it SKIPPED for want of a usable ceiling.
+// radiusNoCeiling only catches the BOTH-null config; one usable ceiling
+// beside one mistyped one let radiusBreaches short-circuit on the null side
+// and the verdict then claimed "every declared number is at or under its
+// ceiling" about a number nothing had compared - the same silent narrowing
+// NO_USABLE_CEILING was added to end, one config away. A ceiling of 0 is a
+// real ceiling, so usability is an explicit radiusNum() !== null and never a
+// falsy test. (PURE)
+function radiusCoverage(m, limits) {
+  const ceiling = (key) => (limits && limits.enabled !== false) ? radiusNum(limits[key]) : null
+  const declared = RADIUS_DIMS.filter((d) => m[d[0]] !== null)
+  return {
+    compared: declared.filter((d) => ceiling(d[1]) !== null).map((d) => d[0]),
+    skipped: declared.filter((d) => ceiling(d[1]) === null).map((d) => d[0]),
+  }
+}
+
+// The sentence fragment naming what was NOT compared, or an empty string
+// when every declared number had a ceiling. Appended to the reason of every
+// state that DID compare something, so a reader of the event never has to
+// re-derive the coverage from `thresholds` by hand. The phrase "no usable
+// ceiling" is deliberate and load-bearing: it is the same wording
+// NO_USABLE_CEILING's own reason uses, so one search finds every record in
+// which a ceiling failed to be a number. (PURE)
+const radiusSkipNote = (cover) => cover.skipped.length === 0 ? '' : ` Not compared, because these declared numbers had no usable ceiling: ${radiusList(cover.skipped)}.`
+
+// The no-breach verdict, split by coverage. WITHIN keeps exactly its old
+// meaning - every declared number was compared, none was over - and
+// WITHIN_PARTIAL is its honest sibling: nothing compared was over, and at
+// least one declared number was never compared at all. Both FAIL OPEN, and
+// only EXCEEDED halts, so this can never turn a WITHIN into a halt: it only
+// stops claiming a comparison that did not happen. (PURE)
+function radiusWithin(cover) {
+  const compared = `compared: ${radiusList(cover.compared)}`
+  if (cover.skipped.length === 0) return { state: 'WITHIN', reason: `every declared number is at or under its ceiling (${compared})` }
+  return { state: 'WITHIN_PARTIAL', reason: `no compared number is over its ceiling (${compared}).${radiusSkipNote(cover)}` }
+}
+
+// Eight states, none collapsed into another, and only EXCEEDED halts anything.
 // The two halves of this check have opposite answers on purpose: a
 // measurement that is missing, unconfigured, unusable or disabled FAILS OPEN
 // (proceed, and the caller records it loudly), while a measurement that
 // succeeded and is over its ceiling FAILS CLOSED (halt and ask). Collapsing
 // them would either halt every run with an old controller or halt none of
@@ -318,22 +369,29 @@ function radiusNoCeiling(limits) {
 // mistyped ceiling is an operator-config defect, and blaming the planner for
 // it would leave the real defect invisible. It is its own state rather than a
 // WITHIN, because "every declared number is at or under its ceiling" is a
 // claim no comparison supported when there is no ceiling to compare against —
 // a mistyped threshold used to report success while silently never firing.
+// WITHIN_PARTIAL is NO_USABLE_CEILING's per-dimension twin, and the last
+// instance of the same defect: a config with one valid ceiling and one
+// mistyped one is USABLE, so it got past radiusNoCeiling, and the declared
+// number on the null side was then reported as being under a ceiling that
+// was never compared. It fails open exactly like WITHIN - an unusable
+// ceiling never causes a halt, it only stops claiming a comparison.
 // (PURE)
 function refactorRadiusStatus(radius, limits) {
   const measured = radiusNumbers(radius)
-  const base = { measured, basis: radiusBasis(radius), thresholds: limits, exceeded: [] }
+  const cover = radiusCoverage(measured, limits)
+  const base = { measured, basis: radiusBasis(radius), thresholds: limits, exceeded: [], compared: cover.compared, skipped: cover.skipped }
   if (!limits) return { ...base, thresholds: null, state: 'NOT_CONFIGURED', reason: 'ctx.refactor_radius is absent or is not an object, so no ceiling was compared' }
   if (!limits.enabled) return { ...base, state: 'DISABLED', reason: 'refactor_radius.enabled is false in the effective gate config' }
   if (radiusNoCeiling(limits)) return { ...base, state: 'NO_USABLE_CEILING', reason: 'refactor_radius is configured and enabled but neither ceiling is a usable number, so nothing was compared' }
   if (measured.rewrite_ratio === null && measured.touched_existing_files === null) return { ...base, state: 'NOT_MEASURED', reason: 'the plan declared no usable refactor-radius number' }
   const exceeded = radiusBreaches(measured, limits)
-  if (!exceeded.length) return { ...base, state: 'WITHIN', reason: 'every declared number is at or under its ceiling' }
-  if (radiusBelowFloor(measured, limits)) return { ...base, exceeded, state: 'BELOW_FLOOR', reason: `over a ceiling but under the ${limits.min_rewritten_lines}-line noise floor` }
-  return { ...base, exceeded, state: 'EXCEEDED', reason: `declared rewrite of existing code is over the configured ceiling (${exceeded.join(', ')})` }
+  if (!exceeded.length) return { ...base, ...radiusWithin(cover) }
+  if (radiusBelowFloor(measured, limits)) return { ...base, exceeded, state: 'BELOW_FLOOR', reason: `over a ceiling but under the ${limits.min_rewritten_lines}-line noise floor.${radiusSkipNote(cover)}` }
+  return { ...base, exceeded, state: 'EXCEEDED', reason: `declared rewrite of existing code is over the configured ceiling (${exceeded.join(', ')}).${radiusSkipNote(cover)}` }
 }
 
 // The panel's over-scope record for the council-verdict payload and the
 // sidecar, or null when no member recorded one (absent ≠ flag:false). A
 // flagged record wins over a clean one; the reason is KEPT — unlike
@@ -700,11 +758,11 @@ function doneResult(slice, state, status, extra) {
 
 // One line of copy naming every number on both sides of the comparison. A
 // human answering this needs the measurements AND the ceilings they were
 // judged against in the record itself, not a pointer to a config file they
 // would have to resolve by hand. (PURE)
-const radiusPhrase = (v) => `declared rewrite ratio ${v.measured.rewrite_ratio}, touched existing files ${v.measured.touched_existing_files}, rewritten lines ${v.measured.rewritten_lines}; ceilings ${v.thresholds.max_rewrite_ratio} ratio / ${v.thresholds.max_touched_existing_files} files, noise floor ${v.thresholds.min_rewritten_lines} lines; the planner counted this as: ${v.basis === null ? 'not stated' : v.basis}`
+const radiusPhrase = (v) => `declared rewrite ratio ${v.measured.rewrite_ratio}, touched existing files ${v.measured.touched_existing_files}, rewritten lines ${v.measured.rewritten_lines}; ceilings ${v.thresholds.max_rewrite_ratio} ratio / ${v.thresholds.max_touched_existing_files} files, noise floor ${v.thresholds.min_rewritten_lines} lines; the planner counted this as: ${v.basis === null ? 'not stated' : v.basis}; compared: ${radiusList(v.compared)}; not compared for want of a usable ceiling: ${radiusList(v.skipped)}`
 
 // The trade-off ask. Three options because a yes/no would leave a human who
 // wants neither with nothing to pick, and because each of the three costs
 // something different: narrowing leaves existing structure uncleaned,
 // approving buys a large diff for one reviewer with no second measurement
@@ -746,10 +804,11 @@ function radiusEvent(slice, verdict, answered) {
     scope: slice.id, type: 'refactor-radius',
     payload: {
       summary: `refactor radius ${verdict.state}: ${verdict.reason}`,
       state: verdict.state, exceeded: verdict.exceeded,
       measured: verdict.measured, thresholds: verdict.thresholds,
+      compared: verdict.compared, skipped: verdict.skipped,
       basis: verdict.basis,
       ...(suppressed ? { suppressed_by_answer: true } : {}),
     },
   }
 }
