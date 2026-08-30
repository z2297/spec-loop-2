# Review package: a7c996b19fd1ce36df97939df3499d300aa26762..spec-loop/20260828-refactor-escalation/s7  (context: -U5)

## Commits
931df1b refactor(workflow): decompose acceptRevisedPlan below both complexity thresholds
991e5c9 fix(workflow): claim a radius suppression only when an answer waived a real breach
2eb0c36 fix(workflow): report an unusable refactor-radius ceiling instead of claiming WITHIN
c77d4cf fix(workflow): only a truthy answer disarms the refactor-scope halt
52967c3 fix(workflow): thread the planner's refactor-radius basis to the human

## Files changed
 plugins/spec-loop/references/run-state-v2.md       |  17 ++-
 .../spec-loop/scripts/slice_wave_radius.test.mjs   | 169 +++++++++++++++++++++
 .../scripts/test_slice_wave_contract_radius.py     |  93 +++++++++++-
 .../scripts/test_slice_wave_contract_replan.py     |  35 +++++
 plugins/spec-loop/workflows/slice-wave.workflow.js | 104 ++++++++++---
 5 files changed, 392 insertions(+), 26 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/references/run-state-v2.md": [
[
187,
190
],
[
192,
193
],
[
201,
207
]
],
"plugins/spec-loop/scripts/slice_wave_radius.test.mjs": [
[
171,
339
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_radius.py": [
[
45,
45
],
[
67,
70
],
[
72,
77
],
[
91,
91
],
[
94,
95
],
[
171,
193
],
[
228,
229
],
[
233,
262
],
[
308,
309
],
[
314,
316
],
[
331,
344
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_replan.py": [
[
59,
66
],
[
158,
184
]
],
"plugins/spec-loop/workflows/slice-wave.workflow.js": [
[
266,
277
],
[
300,
311
],
[
313,
323
],
[
326,
326
],
[
329,
329
],
[
705,
705
],
[
736,
744
],
[
751,
752
],
[
764,
770
],
[
965,
991
],
[
996,
999
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index 41e0675..d70f65d 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -182,22 +182,31 @@ best-effort):
   reading as a whole number — `"14"` — is read as the integer 14 and judged against the tier
   default like any other value.
   The discard is therefore visible without waiting on a second cap record.
 - **`refactor-radius`** payload: `{summary, state, exceeded[], measured{rewrite_ratio,
   touched_existing_files, rewritten_lines}, thresholds{enabled, max_rewrite_ratio,
-  max_touched_existing_files, min_rewritten_lines}|null}`, plus `suppressed_by_answer: true`
-  when a human has already answered this slice's `refactor-scope` escalation. Emitted by
+  max_touched_existing_files, min_rewritten_lines}|null, basis}`, plus `suppressed_by_answer: true`
+  when — and only when — the state is `EXCEEDED` and a truthy human answer to this slice's
+  `refactor-scope` escalation kept it from halting; the key is absent, never `false`, in every
+  other case, so counting it counts real waived halts. Emitted by
   the wave's PLAN stage on EVERY evaluation — `state` is one of `NOT_CONFIGURED`,
-  `DISABLED`, `NOT_MEASURED`, `WITHIN`, `BELOW_FLOOR`, `EXCEEDED`, and only `EXCEEDED`
-  halts. The no-fire cases are emitted precisely because a ceiling that silently declines
+  `DISABLED`, `NO_USABLE_CEILING`, `NOT_MEASURED`, `WITHIN`, `BELOW_FLOOR`, `EXCEEDED`,
+  and only `EXCEEDED` halts. The no-fire cases are emitted precisely because a ceiling that silently declines
   to fire is invisible narrowing: `measured` and `thresholds` are both present in every
   state so a reader never re-derives why nothing happened. `measured` is null-honest —
   an undeclared number is `null`, never `0`, and `0` is a real measurement. The numbers
   are planner-DECLARED: a proxy declared before implementation, not a measured diff, so
   they cannot catch a blowup discovered mid-implementation, and no second,
   post-implementation checkpoint exists. `thresholds` is `null` only when
   `ctx.refactor_radius` was absent or unusable.
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
diff --git a/plugins/spec-loop/scripts/slice_wave_radius.test.mjs b/plugins/spec-loop/scripts/slice_wave_radius.test.mjs
index 74cfa00..60b2016 100644
--- a/plugins/spec-loop/scripts/slice_wave_radius.test.mjs
+++ b/plugins/spec-loop/scripts/slice_wave_radius.test.mjs
@@ -166,5 +166,174 @@ test("the human answer reaches the planner prompt that raised the question", asy
   await runWave(radiusArgs(S1(), RADIUS_DEFAULTS,
     { "s1:refactor-scope": "NARROW-IT-DOWN" }), { agent });
   assert.ok(seen[0].includes("NARROW-IT-DOWN"));
   assert.ok(seen[0].includes('HUMAN ANSWER to your earlier "refactor-scope" escalation'));
 });
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
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_radius.py b/plugins/spec-loop/scripts/test_slice_wave_contract_radius.py
index e4fbafd..8405711 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract_radius.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_radius.py
@@ -40,10 +40,11 @@ RADIUS_NUM = ("const radiusNum = (v) => "
               "(typeof v === 'number' && Number.isFinite(v)) ? v : null")
 RATIO_GUARD = "const over = (v, max) => v !== null && max !== null && v > max"
 FLOOR_GUARD = "m.rewritten_lines !== null && limits.min_rewritten_lines !== null"
 NOT_CONFIGURED = "state: 'NOT_CONFIGURED'"
 NOT_MEASURED = "state: 'NOT_MEASURED'"
+NO_USABLE_CEILING = "state: 'NO_USABLE_CEILING'"
 EXCEEDED = "state: 'EXCEEDED'"
 COERCION_OPERATORS = (">=", "<=")
 
 # The extracted radius block plus a driver that judges each [plan, ctx] pair.
 # %s is the function source, then the JSON case list - the same two-slot shape
@@ -61,11 +62,21 @@ LIMITS = {"enabled": True, "max_rewrite_ratio": 0.5,
           "max_touched_existing_files": 8, "min_rewritten_lines": 150}
 BIG = {"rewrite_ratio": 0.9, "touched_existing_files": 12, "rewritten_lines": 900}
 AT_CEILING = {"rewrite_ratio": 0.5, "touched_existing_files": 8, "rewritten_lines": 900}
 TINY = {"rewrite_ratio": 0.9, "touched_existing_files": 12, "rewritten_lines": 20}
 ZEROED = {"rewrite_ratio": 0, "touched_existing_files": 0, "rewritten_lines": 0}
+NO_CEILINGS = {"enabled": True, "max_rewrite_ratio": None,
+               "max_touched_existing_files": None, "min_rewritten_lines": 150}
+STRING_CEILINGS = {"enabled": True, "max_rewrite_ratio": "0.5",
+                   "max_touched_existing_files": "8", "min_rewritten_lines": 150}
 STRINGY = {"rewrite_ratio": "0.9", "touched_existing_files": "12"}
+RADIUS_BASIS_GUARD = "(typeof radius.basis === 'string' && radius.basis) ? radius.basis : null"
+BASIS_IN_BASE = "basis: radiusBasis(radius)"
+BASIS_IN_EVENT = "basis: verdict.basis,"
+BASIS_TEXT = "counted with git diff --stat against main"
+WITH_BASIS = dict(BIG, basis=BASIS_TEXT)
+BAD_BASIS = dict(BIG, basis=17)
 
 # Expected verdict fragments, hoisted for the same reason: a hanging
 # literal inside a test body is scored as real block nesting by the
 # quality gate's indentation heuristic.
 THREE_NULLS = {"rewrite_ratio": None,
@@ -75,15 +86,15 @@ BOTH_CEILINGS = ["rewrite_ratio", "touched_existing_files"]
 
 
 # ---- the predicate, executed ----
 
 class TestTheRadiusPredicateDecidesAndNotJustExists(WorkflowSourceTestCase):
-    """Six states, none collapsed into another. A substring assertion can
+    """Seven states, none collapsed into another. A substring assertion can
     prove the word NOT_MEASURED appears in the file and nothing about which
     inputs reach it, so this class runs the real helpers under real node and
-    reads the verdicts back: absence, disablement, an unmeasured plan, a plan
-    exactly at its ceiling, a breach, and a breach under the noise floor."""
+    reads the verdicts back: absence, disablement, an unusable ceiling, an
+    unmeasured plan, a plan at its ceiling, a breach, and a noise-floor one."""
 
     def radius_status(self, cases):
         """refactorRadiusStatus() applied to each [plan, ctx] pair by node."""
         node = shutil.which("node")
         if not node:
@@ -155,10 +166,33 @@ class TestTheRadiusPredicateDecidesAndNotJustExists(WorkflowSourceTestCase):
         # The floor can only silence a fire it can prove is noise. A missing
         # rewritten_lines proves nothing, so the measured ratio breach stands.
         got = self.radius_status([[{"rewrite_ratio": 0.9}, LIMITS]])
         self.assertEqual(got[0]["state"], "EXCEEDED")
 
+    def test_a_configured_block_with_no_usable_ceiling_is_its_own_state(self):
+        # WITHIN used to claim "every declared number is at or under its
+        # ceiling", which no comparison supported: a silent no-op that passed.
+        got = self.radius_status([[BIG, NO_CEILINGS], [BIG, STRING_CEILINGS]])
+        self.assertEqual([g["state"] for g in got], ["NO_USABLE_CEILING"] * 2)
+        self.assertEqual([g["exceeded"] for g in got], [[], []])
+
+    def test_an_unusable_ceiling_is_reported_before_an_unmeasured_plan(self):
+        # A mistyped ceiling is an operator-config defect, and blaming the
+        # planner for it would leave the real defect invisible.
+        got = self.radius_status([[None, NO_CEILINGS]])
+        self.assertEqual(got[0]["state"], "NO_USABLE_CEILING")
+
+    def test_one_usable_ceiling_of_the_two_still_judges_the_plan(self):
+        # The second pair also pins that a ceiling of 0 is a real, if severe,
+        # ceiling: a falsy usability test would read it as no ceiling at all.
+        one = dict(NO_CEILINGS, max_touched_existing_files=8)
+        zero = dict(NO_CEILINGS, max_rewrite_ratio=0)
+        got = self.radius_status([[BIG, one], [BIG, zero]])
+        self.assertEqual([g["state"] for g in got], ["EXCEEDED"] * 2)
+        self.assertEqual(got[0]["exceeded"], ["touched_existing_files"])
+        self.assertEqual(got[1]["exceeded"], ["rewrite_ratio"])
+
     def test_every_verdict_carries_the_thresholds_it_compared_against(self):
         # A threshold that silently declines to fire is a permanent invisible
         # narrowing, so the no-fire and not-measured verdicts carry the
         # ceilings too - a reader never has to re-derive why nothing happened.
         got = self.radius_status([[BIG, LIMITS], [ZEROED, LIMITS], [None, LIMITS]])
@@ -189,15 +223,45 @@ class TestNoRadiusComparisonIsReachedByCoercion(WorkflowSourceTestCase):
         self.assertIn(FLOOR_GUARD, self.region())
 
     def test_a_number_is_type_checked_before_it_is_ever_a_measurement(self):
         self.assertIn(RADIUS_NUM, self.region())
 
-    def test_the_three_no_fire_states_exist_as_their_own_named_branches(self):
-        for marker in (NOT_CONFIGURED, NOT_MEASURED, EXCEEDED):
+    def test_the_four_no_fire_states_exist_as_their_own_named_branches(self):
+        for marker in (NOT_CONFIGURED, NO_USABLE_CEILING, NOT_MEASURED, EXCEEDED):
             self.assertIn(marker, self.region())
 
 
+# ---- the planner's basis reaches the human ----
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
+        got = TestTheRadiusPredicateDecidesAndNotJustExists.radius_status(
+            self, [[WITH_BASIS, LIMITS], [BIG, LIMITS], [BAD_BASIS, LIMITS]])
+        self.assertEqual(got[0]["basis"], BASIS_TEXT)
+        self.assertIsNone(got[1]["basis"])
+        self.assertIsNone(got[2]["basis"])
+        self.assertNotIn("basis", got[0]["measured"])
+
+    def test_the_basis_changes_no_state_and_no_exceeded_list(self):
+        got = TestTheRadiusPredicateDecidesAndNotJustExists.radius_status(
+            self, [[WITH_BASIS, LIMITS], [BIG, LIMITS]])
+        self.assertEqual(got[0]["state"], got[1]["state"])
+        self.assertEqual(got[0]["exceeded"], got[1]["exceeded"])
+
+
 # ---- the declared block on PLAN_RESULT, and the planner instruction ----
 
 PLAN_REQUIRED = "required: ['status'],"
 RADIUS_SCHEMA = "refactor_radius: { type: 'object', additionalProperties: false"
 RADIUS_RATIO_TYPE = "rewrite_ratio: { type: ['number', 'null'] }"
@@ -239,14 +303,19 @@ class TestThePlannerDeclaresNumbersAndTheWorkflowJudgesThem(WorkflowSourceTestCa
 GATE_CALL = "const radius = refactorRadiusGate(slice, state, plan)"
 GATE_STOP = "if (radius) return { stop: escalated(slice, state, radius) }"
 GATE_TRIGGER = "return esc(slice, 'refactor-scope', refactorAsk(slice, verdict))"
 GATE_SUPPRESSION = "if (verdict.state !== 'EXCEEDED' || answered) return null"
 GATE_ALWAYS_EMITS = "state.events.push(radiusEvent(slice, verdict, answered))"
+GATE_ANSWERED = "const answered = !!latestAnswer(slice.id, 'refactor-scope')"
+GATE_KEY_COUNT = "answerKeysFor(slice.id, 'refactor-scope').length"
 STAGE_PLAN_START = "async function stagePlan(slice, state) {"
 STAGE_PLAN_END = "// Stage C helpers"
 GATE_FN_START = "function refactorRadiusGate(slice, state, plan) {"
 GATE_FN_END = "\n}\n"
+SUPPRESSED_GUARD = "const suppressed = answered && verdict.state === 'EXCEEDED'"
+SUPPRESSED_SPREAD = "...(suppressed ? { suppressed_by_answer: true } : {}),"
+EVENT_FN_START = "function radiusEvent(slice, verdict, answered) {"
 
 
 class TestOnlyAMeasuredBreachHaltsAndOnlyAtPlanTime(WorkflowSourceTestCase):
     """The event push precedes the halt decision in source order, so no
     return path can skip it; and the halt is raised from stagePlan and
@@ -257,10 +326,24 @@ class TestOnlyAMeasuredBreachHaltsAndOnlyAtPlanTime(WorkflowSourceTestCase):
         self.assertLess(body.index(GATE_ALWAYS_EMITS), body.index(GATE_SUPPRESSION))
 
     def test_only_the_exceeded_state_and_only_an_unanswered_slice_halts(self):
         self.assertIn(GATE_SUPPRESSION, self.src)
 
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
     def test_the_record_is_minted_with_the_refactor_scope_trigger(self):
         self.assertIn(GATE_TRIGGER, self.src)
 
     def test_the_gate_is_called_from_the_plan_stage_and_from_nowhere_else(self):
         self.assertIn(GATE_CALL, self.between(STAGE_PLAN_START, STAGE_PLAN_END))
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_replan.py b/plugins/spec-loop/scripts/test_slice_wave_contract_replan.py
index bdb3ccd..376789b 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract_replan.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_replan.py
@@ -54,10 +54,18 @@ REPLAN_HANDOFF = "return acceptRevisedPlan(slice, state, { revised, ob, safety }
 RECHECK_EVENT = "type: 'replan-recheck'"
 SAFETY_GUARD = "const flagged = !!(rc.safety && rc.safety.flag === true)"
 ACCEPTED_GUARD = "const accepted = rc.verdict !== 'OBJECT' && !flagged"
 LEAKY_ACCEPT = "revised.status === 'PLANNED'"
 RADIUS_GATE_CALL = "refactorRadiusGate("
+OUTCOME_FN = "function recheckOutcome(rc, ob) {"
+OUTCOME_CALL = "const o = recheckOutcome(rc, ob)"
+STOP_FN = "function recheckStop(slice, state, o, ctx) {"
+STOP_CALL = "return { stop: recheckStop(slice, state, o, ctx) }"
+STOP_SAFETY_FIRST = ("if (o.safetyReason) return "
+                     "safetyRecheckEscalation(slice, state, o.safetyReason)")
+STOP_FALLBACK = ("return councilObjectionEscalation(slice, state, "
+                 "objectionSource(o.rc, ctx.ob), o.flagged || ctx.safety)")
 
 
 # ---- the three optional-read guards ----
 class TestTheLastOptionalReadsAreGuarded(WorkflowSourceTestCase):
     """Each of the three reads that PLAN_RESULT/FIX_RESULT never promised now
@@ -145,7 +153,34 @@ class TestTheRadiusGateIsNotReRunOnARevision(WorkflowSourceTestCase):
 
     def test_the_acceptance_helper_does_not_call_the_radius_gate(self):
         self.assertNotIn(RADIUS_GATE_CALL, self.between(ACCEPT_FN, ACCEPT_END))
 
 
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
 if __name__ == "__main__":  # pragma: no cover
     unittest.main()
diff --git a/plugins/spec-loop/workflows/slice-wave.workflow.js b/plugins/spec-loop/workflows/slice-wave.workflow.js
index b601846..ab028da 100644
--- a/plugins/spec-loop/workflows/slice-wave.workflow.js
+++ b/plugins/spec-loop/workflows/slice-wave.workflow.js
@@ -261,10 +261,22 @@ function radiusNumbers(radius) {
     touched_existing_files: radiusNum(radius.touched_existing_files),
     rewritten_lines: radiusNum(radius.rewritten_lines),
   }
 }
 
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
 // Which measured metrics sit ABOVE their ceiling. Both sides are checked for
 // null before the one comparison, so no comparison is ever reached by
 // coercion. Strictly greater-than: both settings are MAXIMA, so a plan
 // exactly at max_touched_existing_files: 8 is at the ceiling, not over it.
 // (PURE)
@@ -283,21 +295,40 @@ function radiusBreaches(m, limits) {
 function radiusBelowFloor(m, limits) {
   const known = m.rewritten_lines !== null && limits.min_rewritten_lines !== null
   return known && m.rewritten_lines < limits.min_rewritten_lines
 }
 
-// Six states, none collapsed into another, and only EXCEEDED halts anything.
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
 // The two halves of this check have opposite answers on purpose: a
-// measurement that is missing, unconfigured or disabled FAILS OPEN (proceed,
-// and the caller records it loudly), while a measurement that succeeded and
-// is over its ceiling FAILS CLOSED (halt and ask). Collapsing them would
-// either halt every run with an old controller or halt none of them. (PURE)
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
 function refactorRadiusStatus(radius, limits) {
   const measured = radiusNumbers(radius)
-  const base = { measured, thresholds: limits, exceeded: [] }
+  const base = { measured, basis: radiusBasis(radius), thresholds: limits, exceeded: [] }
   if (!limits) return { ...base, thresholds: null, state: 'NOT_CONFIGURED', reason: 'ctx.refactor_radius is absent or is not an object, so no ceiling was compared' }
   if (!limits.enabled) return { ...base, state: 'DISABLED', reason: 'refactor_radius.enabled is false in the effective gate config' }
+  if (radiusNoCeiling(limits)) return { ...base, state: 'NO_USABLE_CEILING', reason: 'refactor_radius is configured and enabled but neither ceiling is a usable number, so nothing was compared' }
   if (measured.rewrite_ratio === null && measured.touched_existing_files === null) return { ...base, state: 'NOT_MEASURED', reason: 'the plan declared no usable refactor-radius number' }
   const exceeded = radiusBreaches(measured, limits)
   if (!exceeded.length) return { ...base, state: 'WITHIN', reason: 'every declared number is at or under its ceiling' }
   if (radiusBelowFloor(measured, limits)) return { ...base, exceeded, state: 'BELOW_FLOOR', reason: `over a ceiling but under the ${limits.min_rewritten_lines}-line noise floor` }
   return { ...base, exceeded, state: 'EXCEEDED', reason: `declared rewrite of existing code is over the configured ceiling (${exceeded.join(', ')})` }
@@ -669,11 +700,11 @@ function doneResult(slice, state, status, extra) {
 
 // One line of copy naming every number on both sides of the comparison. A
 // human answering this needs the measurements AND the ceilings they were
 // judged against in the record itself, not a pointer to a config file they
 // would have to resolve by hand. (PURE)
-const radiusPhrase = (v) => `declared rewrite ratio ${v.measured.rewrite_ratio}, touched existing files ${v.measured.touched_existing_files}, rewritten lines ${v.measured.rewritten_lines}; ceilings ${v.thresholds.max_rewrite_ratio} ratio / ${v.thresholds.max_touched_existing_files} files, noise floor ${v.thresholds.min_rewritten_lines} lines`
+const radiusPhrase = (v) => `declared rewrite ratio ${v.measured.rewrite_ratio}, touched existing files ${v.measured.touched_existing_files}, rewritten lines ${v.measured.rewritten_lines}; ceilings ${v.thresholds.max_rewrite_ratio} ratio / ${v.thresholds.max_touched_existing_files} files, noise floor ${v.thresholds.min_rewritten_lines} lines; the planner counted this as: ${v.basis === null ? 'not stated' : v.basis}`
 
 // The trade-off ask. Three options because a yes/no would leave a human who
 // wants neither with nothing to pick, and because each of the three costs
 // something different: narrowing leaves existing structure uncleaned,
 // approving buys a large diff for one reviewer with no second measurement
@@ -700,17 +731,27 @@ function refactorAsk(slice, verdict) {
 // compared against, in every state, and a reader never has to re-derive why
 // nothing happened. `summary` is the FIRST key because run_state.py's
 // decisions-log renderer reads the first text-ish field of a payload
 // (SUMMARY_TEXT_KEYS), so the line is prose rather than a JSON blob. (PURE)
 function radiusEvent(slice, verdict, answered) {
+  // A suppression is a fire that did NOT happen. The flag used to be set from
+  // `answered` alone, so an ordinary post-answer success — the human says
+  // narrow it, the planner narrows, the verdict comes back WITHIN — emitted an
+  // event claiming a suppression that never occurred, and anyone auditing
+  // which halts a human had waived would have counted it. Only EXCEEDED can be
+  // suppressed, because only EXCEEDED halts. The key stays ABSENT rather than
+  // false when nothing was suppressed: `false` would be an explicit claim
+  // about a state in which suppression is not even possible.
+  const suppressed = answered && verdict.state === 'EXCEEDED'
   return {
     scope: slice.id, type: 'refactor-radius',
     payload: {
       summary: `refactor radius ${verdict.state}: ${verdict.reason}`,
       state: verdict.state, exceeded: verdict.exceeded,
       measured: verdict.measured, thresholds: verdict.thresholds,
-      ...(answered ? { suppressed_by_answer: true } : {}),
+      basis: verdict.basis,
+      ...(suppressed ? { suppressed_by_answer: true } : {}),
     },
   }
 }
 
 // Fail OPEN on absence, CLOSED on a measured breach — the two halves have
@@ -718,11 +759,17 @@ function radiusEvent(slice, verdict, answered) {
 // this runs ONCE, on the plan the planner returned, so a replan after a
 // council OBJECT is not re-evaluated; and the numbers are pre-execution
 // declarations, so a blowup discovered mid-implementation is invisible here.
 function refactorRadiusGate(slice, state, plan) {
   const verdict = refactorRadiusStatus(plan.refactor_radius, refactorLimits(CTX))
-  const answered = answerKeysFor(slice.id, 'refactor-scope').length > 0
+  // A truthy ANSWER, not the presence of an answer KEY. The same map reaches
+  // the planner through answerFor()/latestAnswer(), which both require a
+  // truthy value, so an empty or null entry used to disarm this halt
+  // permanently for the slice while injecting nothing into the prompt the
+  // halt exists to change — the question disappeared and the answer never
+  // arrived. This is the shape resolveCouncilObjection already uses.
+  const answered = !!latestAnswer(slice.id, 'refactor-scope')
   state.events.push(radiusEvent(slice, verdict, answered))
   // Answered means the human already ruled on this slice's radius. Raising
   // the same question again would deadlock the slice at the same stage
   // forever, so the verdict stays EXCEEDED in the event (with
   // suppressed_by_answer) and the slice proceeds.
@@ -913,22 +960,45 @@ async function recritiqueRevisedPlan(slice, state, plan) {
   const v = await dispatch(slice, state, 'critic:replan', criticPrompt(slice, plan, null),
     { agentType: 'spec-loop:plan-critic', schema: CRITIQUE, effort: 'high' })
   return v || failClosedCritique()
 }
 
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
 async function acceptRevisedPlan(slice, state, ctx) {
   const { revised, ob, safety } = ctx
   if (!isRevisedPlan(revised)) return { stop: councilObjectionEscalation(slice, state, ob, safety) }
   const rc = await recritiqueRevisedPlan(slice, state, revised)
-  const flagged = !!(rc.safety && rc.safety.flag === true)
-  const safetyReason = flagged && rc.safety && typeof rc.safety.reason === 'string' ? rc.safety.reason : null
-  const accepted = rc.verdict !== 'OBJECT' && !flagged
-  const reason = accepted ? null : (safetyReason || objectionSource(rc, ob).objection.reason)
-  state.events.push({ scope: slice.id, type: 'replan-recheck', payload: { verdict: rc.verdict, safety: flagged, accepted, reason, safety_reason: safetyReason } })
-  if (accepted) return { plan: revised }
-  if (safetyReason) return { stop: safetyRecheckEscalation(slice, state, safetyReason) }
-  return { stop: councilObjectionEscalation(slice, state, objectionSource(rc, ob), flagged || safety) }
+  const o = recheckOutcome(rc, ob)
+  state.events.push({ scope: slice.id, type: 'replan-recheck', payload: { verdict: rc.verdict, safety: o.flagged, accepted: o.accepted, reason: o.reason, safety_reason: o.safetyReason } })
+  if (o.accepted) return { plan: revised }
+  return { stop: recheckStop(slice, state, o, ctx) }
 }
 
 // The council OBJECT branch: an unanswered fixable objection gets one replan
 // attempt; anything else (safety, unfixable, or a failed replan) escalates.
 // answered → proceed with the existing plan; the answer is already injected
