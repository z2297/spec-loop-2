# Review package: 0d5cda4ec73ed3a9b0f59a3cb0256833f4be6535..2f059d5  (context: -U5)

## Commits
2f059d5 contract tests: whitespace-tolerant trigger prose pins so a rewrap cannot break them
753a54a Polish: restore single array-literal style for runSliceError options
0f6b9b1 slice-wave: keep stageFixLoop/runSliceError under the cognitive-complexity and nesting-depth thresholds
6d37452 fix round: precise round-suffix docs, reduced complexity in merge_escalation_records/esc, and lower nesting in escalation-record tests
f9bf9c7 docs: state the escalation id's round component precisely, and how answers key to it
f43770c run_metrics: state and pin that distinct escalation rounds are distinct records
1c02a88 slice-wave: round-suffixed escalation ids, with the answer lookup moved to match

## Files changed
 CHANGELOG.md                                       |  20 +++-
 plugins/spec-loop/agents/slice-worker-fallback.md  |   3 +-
 plugins/spec-loop/commands/spec-loop.md            |   4 +-
 plugins/spec-loop/references/run-state-v2.md       |   8 +-
 plugins/spec-loop/scripts/run_metrics.py           |  37 ++++---
 .../scripts/slice_wave_behaviour.test.mjs          |  70 +++++++++++++
 .../spec-loop/scripts/slice_wave_contract_base.py  |   2 +-
 plugins/spec-loop/scripts/slice_wave_harness.mjs   |   7 +-
 plugins/spec-loop/scripts/test_run_metrics.py      |  55 +++++++++--
 .../scripts/test_slice_wave_contract_crash.py      |  55 +++++++++--
 plugins/spec-loop/skills/escalation-gate/SKILL.md  |  11 ++-
 plugins/spec-loop/workflows/slice-wave.workflow.js | 110 +++++++++++++++------
 12 files changed, 311 insertions(+), 71 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
25,
40
]
],
"plugins/spec-loop/agents/slice-worker-fallback.md": [
[
155,
156
]
],
"plugins/spec-loop/commands/spec-loop.md": [
[
131,
133
]
],
"plugins/spec-loop/references/run-state-v2.md": [
[
100,
106
]
],
"plugins/spec-loop/scripts/run_metrics.py": [
[
455,
460
],
[
467,
467
],
[
471,
487
]
],
"plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs": [
[
183,
252
]
],
"plugins/spec-loop/scripts/slice_wave_contract_base.py": [
[
179,
179
]
],
"plugins/spec-loop/scripts/slice_wave_harness.mjs": [
[
124,
127
],
[
129,
129
]
],
"plugins/spec-loop/scripts/test_run_metrics.py": [
[
344,
354
],
[
510,
513
],
[
521,
554
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_crash.py": [
[
42,
52
],
[
192,
195
],
[
198,
198
],
[
292,
300
],
[
305,
309
],
[
313,
327
]
],
"plugins/spec-loop/skills/escalation-gate/SKILL.md": [
[
145,
148
],
[
164,
166
]
],
"plugins/spec-loop/workflows/slice-wave.workflow.js": [
[
19,
22
],
[
257,
289
],
[
291,
291
],
[
327,
327
],
[
339,
339
],
[
459,
459
],
[
461,
461
],
[
515,
515
],
[
517,
517
],
[
581,
595
],
[
597,
597
],
[
606,
606
],
[
685,
685
],
[
710,
710
],
[
807,
807
],
[
827,
827
],
[
862,
862
],
[
880,
880
],
[
940,
947
],
[
969,
973
],
[
975,
976
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index af1322a..e8cab4a 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -20,14 +20,26 @@ All notable changes to the spec-loop plugin are documented here. The format is
   sections. Two behaviours are deliberately unchanged: `run_state.open_escalations()` still lists
   every status-OPEN escalation, so de-duplicating the page never silences the human gate, and a
   matching re-emit that carries no answer leaves an already-answered section untouched rather
   than resetting it. `answer_escalation` now writes into the last section for an id that is still
   marked `(status: OPEN)`, which is a no-op for an id owning a single section and stops the second
-  round's answer landing under the first round's question. Escalation ids still carry no round
-  component, so two rounds of one id remain distinguishable on the page only by their rendered
-  question and context, or — where those render identically — by the identity fingerprint comment
-  alone.
+  round's answer landing under the first round's question. Escalation ids now carry a round
+  component from the second round onward (see below), so two rounds are two ids; the identity
+  fingerprint stays load-bearing because it also covers records this workflow did not write and
+  rounds whose id is shared.
+- **Two escalations of one trigger in one slice no longer collide on a single id.** `esc()`
+  (`workflows/slice-wave.workflow.js`) now builds the id through `escId`, which appends the
+  `:<round>` component the `EscalationRecord` contract already documented: round 1 keeps the
+  bare `<slice-id>:<trigger>`, and every later round is suffixed. The round is counted from the
+  answers already recorded for that slice and trigger — the one counter that survives a
+  re-dispatch — so an id is stable across resumes and the same `answers` map always reproduces
+  it. Answer lookup moved with the scheme: `latestAnswer` matches the whole key family and
+  returns the newest answered round, so an answer keyed without a round still matches and no
+  judgment trigger becomes unanswerable. The planner-`ESCALATE` branch no longer overwrites the
+  id it was handed. `run_metrics.merge_escalation_records` needed no logic change — it keys on
+  the whole id, so distinct rounds were already distinct records and are now pinned by test —
+  and its docstring says so.
 
 ## [2.2.1] - 2026-08-27
 ### Added
 - **`internal-error` escalation trigger** — a seventh `EscalationRecord.trigger` value for machine
   failure, one string covering both shapes of it: an unhandled exception that aborted a slice
diff --git a/plugins/spec-loop/agents/slice-worker-fallback.md b/plugins/spec-loop/agents/slice-worker-fallback.md
index 564e1e9..706fd00 100644
--- a/plugins/spec-loop/agents/slice-worker-fallback.md
+++ b/plugins/spec-loop/agents/slice-worker-fallback.md
@@ -150,11 +150,12 @@ trusts the sidecar over anything you say, and an invalid one makes this slice un
 regardless of how the work went.
 
 ## Escalations
 
 Every escalation is an EscalationRecord in `escalations[]`: stable id `<slice-id>:<trigger>`,
-one of the seven triggers (`ambiguity`, `material-assumption`, `review-block`,
+plus `:<round>` from the second round of that trigger in that slice onward, one of the seven
+triggers (`ambiguity`, `material-assumption`, `review-block`,
 `council-objection`, `quality-gate-block`, `budget-exhausted`, `internal-error`), the context,
 the precise question, options with one marked `recommended`, and `if_unanswered`.
 Proceed-and-log stays the default — surface only genuine ambiguity or a material assumption
 touching behavior, public contracts, persisted data, security, or an external integration. A
 slice with any open escalation returns `ESCALATED`. `budget-exhausted` is only for the tier
diff --git a/plugins/spec-loop/commands/spec-loop.md b/plugins/spec-loop/commands/spec-loop.md
index 5e874cd..01f83f9 100644
--- a/plugins/spec-loop/commands/spec-loop.md
+++ b/plugins/spec-loop/commands/spec-loop.md
@@ -126,11 +126,13 @@ deadlock is itself an escalation):
    complete and the wave collected.
 7. **Escalations**: gather `run_state.py open-escalations`. For each, run the
    `escalation-gate` precedent check (prior runs' answered escalations + runbook decision
    summaries); squarely-resolved → answer it yourself with a `decision` event citing the
    precedent. Everything else: ONE `AskUserQuestion` round for ALL open escalations
-   (recommended defaults first). Write answers back (`escalation-answered` events), then
+   (recommended defaults first). Write answers back (`escalation-answered` events), keying
+   each answer by the escalation's `id` verbatim — a round-suffixed id keeps its suffix in
+   the `answers` map, and the wave reads the newest answered round — then
    **re-dispatch the wave with ONLY its non-terminal slices** — filter `slices` to the ones
    whose sidecars are not DONE/SPLIT (merged work never re-enters a wave; its worktree is
    already gone) — same `ctx`, `answers` filled in, and `resumeFromRunId: <wf_id>` so the
    escalated slices' completed stages replay from the journal where the cache holds. Never
    rely on replay to make a terminal slice free: a cache miss re-runs it live against a
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index 851eb00..05b7e2b 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -95,11 +95,17 @@ prose about the slice.
 
 ## `EscalationRecord` (embedded in sidecars; rendered into `escalations.md`)
 
 ```jsonc
 {
-  "id": "s1:review-block",     // "<slice-id>:<trigger>[:<round>]" — stable across resumes
+  "id": "s1:review-block",     // "<slice-id>:<trigger>", plus ":<round>" from the second
+                                // round of that trigger in that slice onward (escId).
+                                // Stable across resumes: the round counts the answers
+                                // already recorded for the slice+trigger, so the same
+                                // answers map reproduces the same id. Answers are keyed
+                                // by this id verbatim; latestAnswer reads the newest
+                                // answered round back into the resumed prompts.
   "trigger": "ambiguity | material-assumption | review-block | council-objection | quality-gate-block | budget-exhausted | internal-error",
   "title": "<short title>",
   "context": "<what the loop was doing and why it cannot decide>",
   "question": "<the precise question>",
   "options": [{ "label": "...", "detail": "...", "recommended": true }],
diff --git a/plugins/spec-loop/scripts/run_metrics.py b/plugins/spec-loop/scripts/run_metrics.py
index 737db91..b4d17e3 100644
--- a/plugins/spec-loop/scripts/run_metrics.py
+++ b/plugins/spec-loop/scripts/run_metrics.py
@@ -450,32 +450,43 @@ def _normalize_trigger(value):
     lowered = value.strip().lower()
     return lowered if lowered in ESCALATION_TRIGGERS else "other"
 
 
 def merge_escalation_records(from_events, from_sidecars):
-    """Union the two escalation channels by id, events winning on conflict.
+    """Union the two escalation channels by the whole id, events winning on conflict.
+
+    The id carries a round component from the second escalation of one trigger in
+    one slice onward (``escId`` in slice-wave.workflow.js), so two rounds are two
+    ids and stay two records here; only a genuine re-emit of one round, seen in
+    both channels, merges.
 
     Sidecars are authoritative about a slice, but a run that escalated at
     intake has no sidecar at all, and an interrupted run may have events with
     no persisted sidecar yet — so neither channel alone is complete."""
     merged, order = {}, []
     for record in list(from_sidecars) + list(from_events):
-        key = record["id"]
-        if key not in merged:
-            order.append(key)
-            merged[key] = dict(record)
-            continue
-        existing = merged[key]
-        answered = "ANSWERED" in (existing["status"], record["status"])
-        existing.update({k: v for k, v in record.items() if v is not None})
-        # An answer recorded in either channel happened; a channel that only
-        # saw the open must not walk the escalation back to OPEN.
-        if answered:
-            existing["status"] = "ANSWERED"
+        _fold_escalation_record_into(merged, order, record)
     return [merged[key] for key in order]
 
 
+def _fold_escalation_record_into(merged, order, record):
+    """Fold one escalation record into the accumulating ``merged``/``order``
+    pair, in place. A key seen for the first time is recorded verbatim and
+    its arrival order preserved; a repeat key is unioned onto the existing
+    entry, non-``None`` fields winning, with an answer recorded in either
+    channel never walked back to OPEN by the other."""
+    key = record["id"]
+    if key not in merged:
+        order.append(key)
+        merged[key] = dict(record)
+        return
+    existing = merged[key]
+    answered = "ANSWERED" in (existing["status"], record["status"])
+    existing.update({k: v for k, v in record.items() if v is not None})
+    existing["status"] = "ANSWERED" if answered else existing["status"]
+
+
 # ==========================================================================
 # pure core — dag.json / sidecars / runbook.md
 # ==========================================================================
 
 def parse_dag(obj):
diff --git a/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs b/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
index 5741e8e..2f07e57 100644
--- a/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
+++ b/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
@@ -178,5 +178,75 @@ test("each escalation id and context is attributed to its own slice", async () =
   const recs = out.results.map((r) => r.escalations[0]);
   assert.deepEqual(recs.map((r) => r.id), FOUR_IDS.map((i) => i + ":" + CRASH_TRIGGER));
   assert.deepEqual(recs.map((r) => r.context.startsWith("Error: crash-of-")), [true, true, true, true]);
   FOUR_IDS.forEach((id, i) => assert.ok(recs[i].context.includes("crash-of-" + id + ":plan")));
 });
+
+// ── escalation id rounds (esc/escId) and answer matching (latestAnswer) ──────
+// The round is derived from args.answers, the only channel that survives a
+// re-dispatch, so these tests drive it by handing the wave the answers map a
+// resuming controller would hand it and reading the id the wave actually emits.
+
+const CRASH_KEY = "s1:" + CRASH_TRIGGER;
+const withAnswers = (answers) => waveArgs([sliceFixture("s1")], answers);
+
+test("an unanswered slice keeps the bare id, with no round component", async () => {
+  const out = await runWave(withAnswers({}), THROWS);
+  assert.equal(only(out).id, CRASH_KEY);
+});
+
+test("a second dispatch after an answer to round one raises round two", async () => {
+  const out = await runWave(withAnswers({ [CRASH_KEY]: "retry it" }), THROWS);
+  assert.equal(only(out).id, CRASH_KEY + ":2");
+  assert.equal(only(out).trigger, CRASH_TRIGGER);
+});
+
+test("a third round follows the bare and the round-two answers", async () => {
+  const answers = { [CRASH_KEY]: "retry it", [CRASH_KEY + ":2"]: "retry again" };
+  const out = await runWave(withAnswers(answers), THROWS);
+  assert.equal(only(out).id, CRASH_KEY + ":3");
+});
+
+test("the same answers map reproduces the same id across dispatches", async () => {
+  const answers = { [CRASH_KEY]: "retry it" };
+  const first = await runWave(withAnswers(answers), THROWS);
+  const second = await runWave(withAnswers(answers), THROWS);
+  assert.equal(only(first).id, only(second).id);
+  assert.equal(only(second).id, CRASH_KEY + ":2");
+});
+
+test("an answer to one trigger does not advance another trigger's round", async () => {
+  const out = await runWave(withAnswers({ "s1:ambiguity": "do this" }), THROWS);
+  assert.equal(only(out).id, CRASH_KEY);
+});
+
+// Answer MATCHING, observed where it is observable: the planner prompt. A
+// round-suffixed id whose answer no longer reaches the prompt is the dead end
+// this slice exists to avoid, so it is pinned by execution, not by inspection.
+const capturePrompts = () => {
+  const seen = [];
+  return {
+    seen,
+    agent: async (prompt) => { seen.push(prompt); throw new Error("BOOM"); },
+  };
+};
+
+test("an answer keyed without a round still reaches the prompt", async () => {
+  const cap = capturePrompts();
+  await runWave(withAnswers({ "s1:ambiguity": "ANSWER-ONE" }), { agent: cap.agent });
+  assert.ok(cap.seen[0].includes("ANSWER-ONE"));
+  assert.ok(cap.seen[0].includes('HUMAN ANSWER to your earlier "ambiguity" escalation'));
+});
+
+test("an answer keyed with a round reaches the prompt too", async () => {
+  const cap = capturePrompts();
+  await runWave(withAnswers({ "s1:ambiguity:2": "ANSWER-TWO" }), { agent: cap.agent });
+  assert.ok(cap.seen[0].includes("ANSWER-TWO"));
+});
+
+test("the newest answered round wins with several rounds answered", async () => {
+  const cap = capturePrompts();
+  const answers = { "s1:ambiguity": "ANSWER-ONE", "s1:ambiguity:2": "ANSWER-TWO" };
+  await runWave(withAnswers(answers), { agent: cap.agent });
+  assert.ok(cap.seen[0].includes("ANSWER-TWO"));
+  assert.ok(!cap.seen[0].includes("ANSWER-ONE"));
+});
diff --git a/plugins/spec-loop/scripts/slice_wave_contract_base.py b/plugins/spec-loop/scripts/slice_wave_contract_base.py
index 9b5ddea..5895b59 100644
--- a/plugins/spec-loop/scripts/slice_wave_contract_base.py
+++ b/plugins/spec-loop/scripts/slice_wave_contract_base.py
@@ -174,11 +174,11 @@ CRASH_STAGE_CAVEAT = "so a starting point, not a culprit"
 # The mirror-image overclaim this module now forbids: asserting "bug, NOT a
 # budget limit" is as unprovable as the old "budget" assertion it replaced.
 CRASH_CAUSE_OVERCLAIM = "This is a loop or agent-contract bug"
 CRASH_BUDGET_DENIAL_OVERCLAIM = "NOT a cap or budget limit"
 GUARD_BUDGET_TRIGGER = "esc(slice, 'budget-exhausted',"
-SLICE_LOST_RECORD = "esc(A.slices[i], 'internal-error', 'slice lost',"
+SLICE_LOST_RECORD = "esc(A.slices[i], 'internal-error', {\n    title: 'slice lost',"
 # Third instance of the same overclaim pattern: a thunk resolved to null
 # proves nothing about the cause, so the lost-slice record must not deny one.
 SLICE_LOST_CAUSE_DENIAL = "Not a resource limit."
 # Fifth instance, and the sibling of CRASH_GUARD_ORIGIN_OVERCLAIM above: a
 # guard "firing" asserts its CHECK never ran, which neither record can know.
diff --git a/plugins/spec-loop/scripts/slice_wave_harness.mjs b/plugins/spec-loop/scripts/slice_wave_harness.mjs
index fe7583d..3d58272 100644
--- a/plugins/spec-loop/scripts/slice_wave_harness.mjs
+++ b/plugins/spec-loop/scripts/slice_wave_harness.mjs
@@ -119,13 +119,16 @@ export function sliceFixture(id) {
     deps: [], risk_tier: 1, depth: 0, parent: null,
     branch: "spec-loop/t/" + id, base_sha: "0000000", worktree: "/tmp/wt/" + id,
   };
 }
 
-export function waveArgs(slices) {
+// `answers` is the controller's resume channel, keyed by escalation id. It is a
+// parameter so a test can drive the round the workflow computes from it, rather
+// than asserting the id scheme against a copy of the rule.
+export function waveArgs(slices, answers) {
   return {
-    run_id: "20260827-harness", wave_index: 0, slices, answers: {},
+    run_id: "20260827-harness", wave_index: 0, slices, answers: answers || {},
     ctx: {
       run_dir: "/tmp/run", plugin_root: "/tmp/plugin", base_ref: "main",
       test_command: "true", conventions_path: "/tmp/run/conventions.md",
       shared_constraints: ["none"], tier3_surfaces: [],
       quality_gate_cmd: "true", models: { reviewer: "inherit" },
diff --git a/plugins/spec-loop/scripts/test_run_metrics.py b/plugins/spec-loop/scripts/test_run_metrics.py
index f397e73..5ba913e 100644
--- a/plugins/spec-loop/scripts/test_run_metrics.py
+++ b/plugins/spec-loop/scripts/test_run_metrics.py
@@ -339,10 +339,21 @@ def _events_without(*payload_keys):
         dict(obj, payload={k: v for k, v in obj["payload"].items()
                            if k not in dropped}))
         for obj in V2_EVENT_OBJECTS)
 
 
+def _escalation_record(**overrides):
+    """One escalation record as `merge_escalation_records` consumes it, with
+    the fields a round-2 `s1:internal-error` record shares held as defaults so
+    a test states only what makes it distinct."""
+    record = {"id": "s1:internal-error", "scope": "s1", "trigger": "internal-error",
+              "title": None, "status": "OPEN", "opened": "2026-07-30T10:00:00Z",
+              "answered_at": None}
+    record.update(overrides)
+    return record
+
+
 # ---------------------------------------------------------------------------
 # events.jsonl parsing
 # ---------------------------------------------------------------------------
 
 class EventsParseTests(unittest.TestCase):
@@ -494,23 +505,55 @@ class EscalationPairingTests(unittest.TestCase):
         self.assertEqual(metrics["safety"]["escalations"]["total"], 2)
         self.assertEqual(metrics["safety"]["escalations"]["basis"],
                          rm.BASIS_BOTH)
 
     def test_sidecar_answer_survives_an_events_channel_that_only_opened(self):
-        from_events = [{"id": "s1:x", "scope": "s1", "trigger": "ambiguity",
-                        "title": None, "status": "OPEN",
-                        "opened": "2026-07-30T10:00:00Z", "answered_at": None}]
-        from_sidecars = [{"id": "s1:x", "scope": "s1", "trigger": None,
-                          "title": "t", "status": "ANSWERED", "opened": None,
-                          "answered_at": "2026-07-30T10:05:00Z"}]
+        from_events = [_escalation_record(id="s1:x", trigger="ambiguity", title=None)]
+        from_sidecars = [_escalation_record(
+            id="s1:x", trigger=None, title="t", status="ANSWERED", opened=None,
+            answered_at="2026-07-30T10:05:00Z")]
         merged = rm.merge_escalation_records(from_events, from_sidecars)
         self.assertEqual(len(merged), 1)
         self.assertEqual(merged[0]["status"], "ANSWERED")
         self.assertEqual(merged[0]["answered_at"], "2026-07-30T10:05:00Z")
         self.assertEqual(merged[0]["opened"], "2026-07-30T10:00:00Z")
         self.assertEqual(merged[0]["trigger"], "ambiguity")
 
+    def test_two_rounds_of_one_trigger_stay_two_records(self):
+        first_id, second_id = "s1:internal-error", "s1:internal-error:2"
+        first = _escalation_record(
+            id=first_id, title="round one", status="ANSWERED",
+            answered_at="2026-07-30T10:05:00Z")
+        second = _escalation_record(
+            id=second_id, title="round two", status="OPEN", answered_at=None)
+        merged = rm.merge_escalation_records([], [first, second])
+        ids = [r["id"] for r in merged]
+        titles = [r["title"] for r in merged]
+        statuses = [r["status"] for r in merged]
+        self.assertEqual(ids, [first_id, second_id])
+        self.assertEqual(titles, ["round one", "round two"])
+        self.assertEqual(statuses, ["ANSWERED", "OPEN"])
+
+    def test_one_round_seen_in_both_channels_stays_one_record(self):
+        round_id = "s1:internal-error:2"
+        events = [_escalation_record(id=round_id, title=None, status="OPEN")]
+        sidecars = [_escalation_record(
+            id=round_id, trigger=None, title="round two", status="ANSWERED",
+            opened=None, answered_at="2026-07-30T10:05:00Z")]
+        merged = rm.merge_escalation_records(events, sidecars)
+        self.assertEqual(len(merged), 1)
+        self.assertEqual(merged[0]["status"], "ANSWERED")
+        self.assertEqual(merged[0]["title"], "round two")
+
+    def test_scope_survives_a_round_suffixed_id(self):
+        parsed = rm._parse_embedded_escalations(
+            [{"id": "s1:internal-error:2", "trigger": "internal-error",
+              "title": "round two", "status": "OPEN"}])
+        self.assertEqual(len(parsed), 1)
+        self.assertEqual(parsed[0]["scope"], "s1")
+        self.assertEqual(parsed[0]["id"], "s1:internal-error:2")
+
 
 # ---------------------------------------------------------------------------
 # dag.json / sidecar / runbook parsing
 # ---------------------------------------------------------------------------
 
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py b/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
index 517f7de..11aa888 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
@@ -37,10 +37,21 @@ from slice_wave_contract_base import (
     STATE_STAGE_INIT, TRIGGER_ENUM_LINE, TRIGGER_PROSE_LEAD,
     TRIGGER_UNION_PREFIX,
     WorkflowSourceTestCase,
 )
 
+def collapsed(text):
+    """Runs of whitespace become a single space.
+
+    A hard-wrap of markdown prose splits a pinned literal across a
+    newline and drops its match count to zero. Both sides of every
+    prose match below pass through here, so line breaks stay invisible
+    to the pin and the prose stays free to rewrap.
+    """
+    return re.sub(r"\s+", " ", text)
+
+
 # A real crash message from run 20260825-scope-ceiling, and the LONGEST stage
 # text the fallback can interpolate (the no-dispatch phrase, longer than any
 # role name), so the render check below measures the worst realistic case.
 SAMPLE_MESSAGE = "Cannot read properties of undefined (reading 'head')"
 LONGEST_STAGE = "none (the crash happened before any agent was dispatched)"
@@ -176,14 +187,17 @@ class TestCrashesAreClassifiedAsInternalError(WorkflowSourceTestCase):
         prose_at = fallback.index(CRASH_CLASSIFICATION_SENTENCE)
         self.assertLess(error_at, stage_at)
         self.assertLess(stage_at, prose_at)
 
     def crash_context(self):
-        """The shipped context template literal, backticks stripped."""
+        r"""The shipped context template literal, backticks stripped. The
+        literal is its own statement (`const context = \`...\``), so its
+        closing backtick is followed by a newline, not the trailing comma an
+        inline call argument would carry."""
         fallback = self.crash_fallback()
         start = fallback.index(CRASH_ERROR_FIRST)
-        return fallback[start + 1:fallback.index("`,", start)]
+        return fallback[start + 1:fallback.index("`\n", start)]
 
     def rendered_crash_context(self, message, stage_text):
         """The `- Context:` line escalations.md actually receives, produced by
         the REAL run_state.render_escalation(). Re-implementing its collapse
         and truncate here protected nothing: the copy sliced unconditionally
@@ -273,23 +287,44 @@ class TestTheTriggerEnumAgreesAcrossAllSixHomes(WorkflowSourceTestCase):
             self.triggers())
 
     def test_the_fallback_agent_prose_lists_exactly_those_triggers(self):
         # The escalation section of the slice-worker fallback agent is the
         # enumeration a worker reads before it names a trigger. Located by
-        # TRIGGER_PROSE_LEAD, whose own count word is pinned by the literal.
-        text = FALLBACK_MD.read_text(encoding="utf-8")
-        self.assertEqual(text.count(TRIGGER_PROSE_LEAD), 1)
-        listed = text.split(TRIGGER_PROSE_LEAD, 1)[1].split(")", 1)[0]
-        self.assertEqual(tuple(re.findall(r"`([^`]+)`", listed)), self.triggers())
+        # TRIGGER_PROSE_LEAD, whose own count word is pinned by the
+        # literal. Both sides are whitespace-collapsed, so a rewrap of the
+        # sentence leaves the pin intact.
+        text = collapsed(FALLBACK_MD.read_text(encoding="utf-8"))
+        lead = collapsed(TRIGGER_PROSE_LEAD)
+        self.assertEqual(text.count(lead), 1)
+        listed = text.split(lead, 1)[1].split(")", 1)[0]
+        self.assertEqual(tuple(re.findall(r"`([^`]+)`", listed)),
+            self.triggers())
 
     def test_the_contract_reference_union_lists_exactly_those_triggers(self):
         # references/run-state-v2.md is the authoritative shape doc for the
         # EscalationRecord; its trigger field is a pipe-separated union.
-        text = RUN_STATE_MD.read_text(encoding="utf-8")
-        self.assertEqual(text.count(TRIGGER_UNION_PREFIX), 1)
-        union = text.split(TRIGGER_UNION_PREFIX, 1)[1].split('"', 1)[0]
+        # Whitespace-collapsed on both sides, same as the pin above.
+        text = collapsed(RUN_STATE_MD.read_text(encoding="utf-8"))
+        prefix = collapsed(TRIGGER_UNION_PREFIX)
+        self.assertEqual(text.count(prefix), 1)
+        union = text.split(prefix, 1)[1].split('"', 1)[0]
         self.assertEqual(tuple(part.strip() for part in union.split("|")),
             self.triggers())
 
+    def test_the_prose_pin_survives_a_hard_wrap_of_the_fallback_sentence(self):
+        # Every space becomes a line break: the harshest rewrap there is.
+        rewrapped = FALLBACK_MD.read_text(encoding="utf-8").replace(" ", "\n")
+        self.assertEqual(
+            collapsed(rewrapped).count(collapsed(TRIGGER_PROSE_LEAD)), 1)
+
+    def test_the_union_pin_survives_a_hard_wrap_of_the_contract_line(self):
+        rewrapped = RUN_STATE_MD.read_text(encoding="utf-8").replace(" ", "\n")
+        text = collapsed(rewrapped)
+        prefix = collapsed(TRIGGER_UNION_PREFIX)
+        self.assertEqual(text.count(prefix), 1)
+        union = text.split(prefix, 1)[1].split('"', 1)[0]
+        self.assertEqual(tuple(p.strip() for p in union.split("|")),
+            self.triggers())
+
 
 if __name__ == "__main__":  # pragma: no cover
     unittest.main()
diff --git a/plugins/spec-loop/skills/escalation-gate/SKILL.md b/plugins/spec-loop/skills/escalation-gate/SKILL.md
index 600c373..5dc505d 100644
--- a/plugins/spec-loop/skills/escalation-gate/SKILL.md
+++ b/plugins/spec-loop/skills/escalation-gate/SKILL.md
@@ -140,12 +140,14 @@ human, so:
    `parallel()` keeps every independent slice running.
 2. The controller collects **all** open records at the **wave boundary**
    (`run_state.py open-escalations`), runs the precedent check on each, and surfaces everything that
    survives as ONE `AskUserQuestion` round — recommended default first.
 3. Answers are written back (`escalation-answered` events) and the wave is re-dispatched with
-   `answers["<slice-id>:<trigger>"]` filled in; completed stages replay from the workflow journal,
-   so only the answered stage runs live.
+   the answer keyed by the escalation's `id` verbatim (`answers["<slice-id>:<trigger>"]`, or
+   `answers["<slice-id>:<trigger>:<round>"]` from the second round of that trigger onward)
+   filled in; completed stages replay from the workflow journal, so only the answered stage
+   runs live.
 
 The wave boundary is the only seam where a human is asked anything — unchanged from v1; only the
 transport moved from prose files to structured returns.
 
 ## The escalation record
@@ -157,12 +159,13 @@ rendered from the records. Two rules the shape cannot enforce:
 - **Always include a recommended default.** Make the human's decision as cheap as possible
   (confirm vs. redirect). A record whose options are all equally weighted is unfinished.
 - **`context` explains why the loop cannot decide**, not merely what happened — the human reads it
   cold, alongside other questions.
 
-The `id` is `<slice-id>:<trigger>`, stable across resumes: that stability is what lets an answer be
-injected back into exactly the stage that raised it.
+The `id` is `<slice-id>:<trigger>`, plus `:<round>` from the second round of that trigger in that
+slice onward, stable across resumes: that stability is what lets an answer be injected back into
+exactly the stage that raised it.
 
 ## Violations of the contract
 
 - Asking the human something resolvable from the codebase, a convention, or a prior run's answered
   escalation (run the precedent check first).
diff --git a/plugins/spec-loop/workflows/slice-wave.workflow.js b/plugins/spec-loop/workflows/slice-wave.workflow.js
index 73c7eec..126658f 100644
--- a/plugins/spec-loop/workflows/slice-wave.workflow.js
+++ b/plugins/spec-loop/workflows/slice-wave.workflow.js
@@ -14,12 +14,14 @@ export const meta = {
 //
 // Hard rules this file owns (single home):
 //   - loop bounds: replan ≤1, task retry ≤1, fix rounds ≤2, debug-fix ≤1
 //   - per-slice agent caps by review tier: 10 / 18 / 32
 //   - fail-closed synthesis: an unusable agent return is never an approval
-//   - answers injection: args.answers["<sliceId>:<trigger>"] resumes an
-//     escalated stage; unchanged stages replay from the journal cache
+//   - answers injection: args.answers["<sliceId>:<trigger>"], or
+//     ["<sliceId>:<trigger>:<round>"] from the second round on, resumes an
+//     escalated stage (escId writes the id, latestAnswer reads it back);
+//     unchanged stages replay from the journal cache
 //
 // The controller stamps timestamps and persists results (run_state.py) —
 // this script has no clock and no filesystem, by design.
 // ─────────────────────────────────────────────────────────────────────────────
 
@@ -250,13 +252,45 @@ function scopeCeilingList(ctx) {
   if (Array.isArray(raw)) return raw
   if (typeof raw === 'string' && raw) return [raw]
   return []
 }
 
-function esc(slice, trigger, title, context, question, options) {
+// Answer keys belonging to one slice+trigger: the bare "<slice-id>:<trigger>"
+// plus every round-suffixed sibling of it. Triggers are a closed enum and the
+// base always ends with the whole trigger, so no trigger's family can absorb
+// another's key. (PURE over A.answers)
+function answerKeysFor(sliceId, trigger) {
+  const base = `${sliceId}:${trigger}`
+  return Object.keys(A.answers || {}).filter(k => k === base || k.startsWith(`${base}:`))
+}
+
+// Which round this dispatch is raising. A round is one DISPATCH of the slice:
+// escalated() is terminal, so a slice raises at most one record per dispatch and
+// an in-memory counter would reset to 1 on every re-dispatch and collide again.
+// The controller keys each answer by the escalation id it answers, so the number
+// of answered rounds already in args.answers is the one counter that survives a
+// resume unchanged — the same answers map always reproduces the same id. Round 1
+// keeps the bare id, so every id and answer key written before the round suffix
+// existed still matches. (PURE)
+function escRound(sliceId, trigger) {
+  return answerKeysFor(sliceId, trigger).length + 1
+}
+
+function escId(sliceId, trigger) {
+  const round = escRound(sliceId, trigger)
+  const base = `${sliceId}:${trigger}`
+  return round === 1 ? base : `${base}:${round}`
+}
+
+// `content` is `{title, context, question, options}`, grouped into one
+// parameter object because those four always travel together (one prompt's
+// worth of copy) while `slice` and `trigger` each drive a different part of
+// the id.
+function esc(slice, trigger, content) {
+  const { title, context, question, options } = content
   return {
-    id: `${slice.id}:${trigger}`,
+    id: escId(slice.id, trigger),
     trigger, title, context, question,
     options: options && options.length ? options : [{ label: 'Proceed with the recommended default', detail: context, recommended: true }],
     if_unanswered: 'pause this slice; continue all independent slices',
     status: 'OPEN',
   }
@@ -288,11 +322,11 @@ const packet = (slice) => [
     : '',
   slice.kg_snippet ? `Prior knowledge (graph context):\n${slice.kg_snippet}` : '',
 ].filter(Boolean).join('\n')
 
 const answerFor = (slice, trigger) => {
-  const a = humanAnswer(`${slice.id}:${trigger}`)
+  const a = latestAnswer(slice.id, trigger)
   return a ? `\nHUMAN ANSWER to your earlier "${trigger}" escalation (apply it, do not re-raise): ${a}` : ''
 }
 
 // A context-only sibling of answerFor(), for dispatches to a transcription-
 // only reporter (spec-loop:verifier — "you never return a PASS/FAIL label",
@@ -300,11 +334,11 @@ const answerFor = (slice, trigger) => {
 // the residual violations", but a reporter has no lawful way to "apply" that
 // beyond mis-transcribing the gate's real output as a pass. This carries the
 // answer for a human resuming the escalation to see in the transcript
 // without instructing the reporter to change what it reports.
 const answerContext = (slice, trigger) => {
-  const a = humanAnswer(`${slice.id}:${trigger}`)
+  const a = latestAnswer(slice.id, trigger)
   return a ? `\nHUMAN ANSWER on the earlier "${trigger}" escalation, for context only — it does NOT change what you report: the suite result and quality.summary_pass/violations stay verbatim from the real output: ${a}` : ''
 }
 
 function planPrompt(slice) {
   return `${packet(slice)}
@@ -420,13 +454,13 @@ Polish the diff ${state.commits.base}..HEAD in the worktree: behavior-preserving
 
 // ── Guarded dispatch ─────────────────────────────────────────────────────────
 
 function guard(slice, state) {
   if (state.agentsUsed >= CAPS[state.review_tier])
-    throw { escRecord: esc(slice, 'budget-exhausted', `agent cap reached (${CAPS[state.review_tier]})`, `Slice used ${state.agentsUsed} agents (tier ${state.review_tier} cap).`, 'Raise the cap and resume, accept the slice as-is, or drop it?', []) }
+    throw { escRecord: esc(slice, 'budget-exhausted', { title: `agent cap reached (${CAPS[state.review_tier]})`, context: `Slice used ${state.agentsUsed} agents (tier ${state.review_tier} cap).`, question: 'Raise the cap and resume, accept the slice as-is, or drop it?', options: [] }) }
   if (budget.total && budget.remaining() < BUDGET_STAGE_FLOOR)
-    throw { escRecord: esc(slice, 'budget-exhausted', 'token budget exhausted', `Wave budget remaining ${Math.round(budget.remaining() / 1000)}k is below the ${BUDGET_STAGE_FLOOR / 1000}k stage floor.`, 'Raise the budget and resume, accept committed work as-is, or drop the slice?', []) }
+    throw { escRecord: esc(slice, 'budget-exhausted', { title: 'token budget exhausted', context: `Wave budget remaining ${Math.round(budget.remaining() / 1000)}k is below the ${BUDGET_STAGE_FLOOR / 1000}k stage floor.`, question: 'Raise the budget and resume, accept committed work as-is, or drop the slice?', options: [] }) }
 }
 
 async function dispatch(slice, state, role, prompt, opts) {
   guard(slice, state)
   // Last dispatch STARTED, not a per-throw stage: never cleared, and
@@ -476,13 +510,13 @@ function doneResult(slice, state, status, extra) {
 
 // Stage P — plan (+ right-size gate inside the planner)
 async function stagePlan(slice, state) {
   const plan = await dispatch(slice, state, 'plan', planPrompt(slice),
     { agentType: 'spec-loop:slice-planner', schema: PLAN_RESULT, effort: 'low' })
-  if (!plan) return { stop: escalated(slice, state, esc(slice, 'ambiguity', 'planner returned no result', 'The planner dispatch failed terminally.', 'Retry the slice, or drop it?', [])) }
+  if (!plan) return { stop: escalated(slice, state, esc(slice, 'ambiguity', { title: 'planner returned no result', context: 'The planner dispatch failed terminally.', question: 'Retry the slice, or drop it?', options: [] })) }
   if (plan.status === 'SPLIT') return { stop: doneResult(slice, state, 'SPLIT', { split: plan.split }) }
-  if (plan.status === 'ESCALATE') return { stop: escalated(slice, state, { ...esc(slice, plan.escalation.trigger, plan.escalation.title, plan.escalation.context, plan.escalation.question, plan.escalation.options), id: `${slice.id}:${plan.escalation.trigger}` }) }
+  if (plan.status === 'ESCALATE') return { stop: escalated(slice, state, esc(slice, plan.escalation.trigger, plan.escalation)) }
   return { plan }
 }
 
 // Stage C helpers — panel selection, verdict rollup, and the OBJECT branch.
 // Each helper below is kept single-purpose and small on its own terms (own
@@ -542,21 +576,36 @@ function recordCouncilVerdict(slice, state, ctx) {
 
 function humanAnswer(id) {
   return (A.answers || {})[id]
 }
 
+// The answer to the NEWEST answered round of one slice+trigger. The controller
+// keys an answer by the escalation id it answers, so round 2's answer arrives
+// under "<slice-id>:<trigger>:2", and an answer written before the suffix
+// existed is keyed bare. Both are matched here, deliberately: dropping the bare
+// key would make every previously written answer unfindable, and the answer to
+// round N is exactly the context the dispatch that raises round N+1 needs. An
+// unparsable suffix ranks as round 1 rather than being dropped. (PURE)
+function latestAnswer(sliceId, trigger) {
+  const base = `${sliceId}:${trigger}`
+  const rank = (key) => Number(key.slice(base.length + 1)) || 1
+  const keys = answerKeysFor(sliceId, trigger).sort((a, b) => rank(a) - rank(b))
+  const newest = keys[keys.length - 1]
+  return newest === undefined ? undefined : humanAnswer(newest)
+}
+
 function councilObjectionEscalation(slice, state, ob, safety) {
-  return escalated(slice, state, esc(slice, 'council-objection', `${safety ? 'SAFETY — ' : ''}council objects: ${ob.objection.reason.slice(0, 60)}`, ob.objection.reason, ob.objection.question, [{ label: ob.objection.recommendation, detail: 'critic-recommended default', recommended: true }]))
+  return escalated(slice, state, esc(slice, 'council-objection', { title: `${safety ? 'SAFETY — ' : ''}council objects: ${ob.objection.reason.slice(0, 60)}`, context: ob.objection.reason, question: ob.objection.question, options: [{ label: ob.objection.recommendation, detail: 'critic-recommended default', recommended: true }] }))
 }
 
 // The council OBJECT branch: an unanswered fixable objection gets one replan
 // attempt; anything else (safety, unfixable, or a failed replan) escalates.
 // answered → proceed with the existing plan; the answer is already injected
 // into downstream prompts via answerFor().
 async function resolveCouncilObjection(slice, state, ctx) {
   const { plan, ob, safety } = ctx
-  if (humanAnswer(`${slice.id}:council-objection`)) return { plan }
+  if (latestAnswer(slice.id, 'council-objection')) return { plan }
   if (safety || !ob.fixable_by_replan || state.replanned) return { stop: councilObjectionEscalation(slice, state, ob, safety) }
   state.replanned = true
   const revised = await dispatch(slice, state, 'replan', replanPrompt(slice, plan, ob),
     { agentType: 'spec-loop:slice-planner', schema: PLAN_RESULT, effort: 'low' })
   return (revised && revised.status === 'PLANNED') ? { plan: revised } : { stop: councilObjectionEscalation(slice, state, ob, safety) }
@@ -631,11 +680,11 @@ async function attemptTask(slice, state, plan, task) {
 }
 
 async function runTask(slice, state, plan, task) {
   const r = await attemptTask(slice, state, plan, task)
   if (taskNeedsRetry(r))
-    return { stop: escalated(slice, state, esc(slice, 'ambiguity', `task ${task.id} blocked`, taskBlockReason(r), `Task "${task.title}" cannot proceed. How should it resolve?`, [])) }
+    return { stop: escalated(slice, state, esc(slice, 'ambiguity', { title: `task ${task.id} blocked`, context: taskBlockReason(r), question: `Task "${task.title}" cannot proceed. How should it resolve?`, options: [] })) }
   state.tasksCompleted++
   // TASK_RESULT requires only status/touched_files/concerns/deviations, so a
   // task that legitimately changed nothing returns DONE with `commits`
   // absent. Reading it unguarded threw a TypeError that would now be
   // classified as an 'internal-error' by the catch-all; run 20260825-scope-
@@ -656,11 +705,11 @@ async function stageTasks(slice, state, plan) {
     const r = await runTask(slice, state, plan, task)
     if (r.stop) return { stop: r.stop }
     touched.push(...r.touched)
   }
   if (!state.commits.head)
-    return { stop: escalated(slice, state, esc(slice, 'ambiguity', 'plan produced no commits', 'All tasks completed but no commit was recorded.', 'Drop the slice or retry?', [])) }
+    return { stop: escalated(slice, state, esc(slice, 'ambiguity', { title: 'plan produced no commits', context: 'All tasks completed but no commit was recorded.', question: 'Drop the slice or retry?', options: [] })) }
   return { touched }
 }
 
 // Deterministic tier promotion: implementation touched a Tier-3 surface
 function maybePromoteTier(slice, state, touched) {
@@ -753,11 +802,11 @@ async function runFixRound(slice, state, ctx) {
   if (!open.length) return { open }
   state.review.confirmed = open.length
   state.review.fix_rounds = round + 1
   const fix = await dispatchFix(slice, state, { plan, open, round })
   if (!fix || fix.status === 'BLOCKED')
-    return { stop: escalated(slice, state, esc(slice, 'review-block', 'fix agent blocked', fixBlockerReason(fix), 'Blocking findings cannot be fixed automatically. Accept, guide, or drop?', [])) }
+    return { stop: escalated(slice, state, esc(slice, 'review-block', { title: 'fix agent blocked', context: fixBlockerReason(fix), question: 'Blocking findings cannot be fixed automatically. Accept, guide, or drop?', options: [] })) }
   if (fix.commits && fix.commits.head) state.commits.head = fix.commits.head
   const rr = await dispatch(slice, state, `re-review:${round + 1}`, reReviewPrompt(slice, state, open, fix),
     { agentType: 'spec-loop:re-reviewer', schema: REREVIEW_RESULT, model: 'sonnet', effort: 'low' })
   if (!rr) return { open } // fail closed: findings stay open into the next round / escalation
   state.review.refuted += rr.verdicts.filter(x => x.verdict === 'REFUTATION_ACCEPTED').length
@@ -773,12 +822,11 @@ async function stageFixLoop(slice, state, ctx) {
   for (let round = 0; open.length && round < MAX_FIX_ROUNDS; round++) {
     const res = await runFixRound(slice, state, { plan, review, open, round, bar })
     if (res.stop) return { stop: res.stop }
     open = res.open
   }
-  if (open.length)
-    return { stop: escalated(slice, state, esc(slice, open.some(f => f.category === 'quality-gate') ? 'quality-gate-block' : 'review-block', `${open.length} blocking finding(s) unresolved after ${MAX_FIX_ROUNDS} fix rounds`, open.map(f => `${f.severity} ${f.file}:${f.line} — ${f.claim}`).join('\n'), 'Accept the residual findings, provide guidance, or drop the slice?', [])) }
+  if (open.length) return { stop: escalated(slice, state, esc(slice, open.some(f => f.category === 'quality-gate') ? 'quality-gate-block' : 'review-block', { title: `${open.length} blocking finding(s) unresolved after ${MAX_FIX_ROUNDS} fix rounds`, context: open.map(f => `${f.severity} ${f.file}:${f.line} — ${f.claim}`).join('\n'), question: 'Accept the residual findings, provide guidance, or drop the slice?', options: [] })) }
   state.review.residual = review.findings.filter(f => !blocking([f], bar).length).map(f => `${f.severity}: ${f.claim}`).slice(0, 10)
   state.events.push({ scope: slice.id, type: 'review-summary', payload: { findings: review.findings.length, confirmed: state.review.confirmed, refuted: state.review.refuted, fix_rounds: state.review.fix_rounds, reviewers: state.reviewersCount } })
   return {}
 }
 
@@ -809,11 +857,11 @@ function markVerifiedDone(slice, state, v) {
 function verificationFailedEscalation(slice, state, v) {
   const trigger = verifySuiteFailed(v) ? 'review-block' : 'quality-gate-block'
   const detail = v
     ? `suite: ${v.suite.summary}; quality: ${qualityStatus(v.quality)} (summary_pass=${String(v.quality.summary_pass)}${v.quality.detail ? ` — ${v.quality.detail}` : ''})`
     : 'verifier dispatch failed terminally'
-  return escalated(slice, state, esc(slice, trigger, 'verification failed', detail, 'Verification cannot pass automatically. Guide, accept, or drop?', []))
+  return escalated(slice, state, esc(slice, trigger, { title: 'verification failed', context: detail, question: 'Verification cannot pass automatically. Guide, accept, or drop?', options: [] }))
 }
 
 async function runDebugFix(slice, state, plan, v) {
   const df = await dispatch(slice, state, 'debug-fix', debugFixPrompt(slice, plan, state, v),
     { agentType: 'spec-loop:implementer', schema: FIX_RESULT, model: 'inherit', effort: 'high' })
@@ -827,11 +875,11 @@ async function stageVerify(slice, state, plan) {
       { agentType: 'spec-loop:verifier', schema: VERIFY_RESULT, model: 'haiku', effort: 'low' })
     if (verifyPassed(v)) return markVerifiedDone(slice, state, v)
     if (attempt === 0 && verifySuiteFailed(v)) { await runDebugFix(slice, state, plan, v); continue }
     return verificationFailedEscalation(slice, state, v)
   }
-  return escalated(slice, state, esc(slice, 'review-block', 'verification loop exhausted', 'unreachable', 'Guide, accept, or drop?', []))
+  return escalated(slice, state, esc(slice, 'review-block', { title: 'verification loop exhausted', context: 'unreachable', question: 'Guide, accept, or drop?', options: [] }))
 }
 
 // The seven-stage sequence, unwrapped from the try/catch below so its own
 // early-return checks aren't weighted by an extra level of nesting.
 async function runStages(slice, state) {
@@ -887,16 +935,18 @@ async function runStages(slice, state) {
 function runSliceError(slice, state, e) {
   if (e && e.escRecord) return escalated(slice, state, e.escRecord)
   const stage = state.stage
   const stageText = stage || 'none (the crash happened before any agent was dispatched)'
   const title = stage ? `slice crashed after ${stage}` : 'slice crashed before any agent was dispatched'
-  return escalated(slice, state, esc(slice, 'internal-error', title,
-    `Error: ${String((e && e.message) || e)}. Last stage/role dispatched before the failure: ${stageText} — the most recent dispatch, not a per-throw stage, so a starting point, not a culprit. Cause unknown: neither structural guard raised its escalation record, and that is all the check one line above proves — the stage token floor calls budget.remaining() itself, so a throw from inside a guard reaches here with no record either. It may be a loop or agent-contract bug, and it may equally be a host- or agent-layer resource failure (a rejected agent call on a hard token or rate limit, say) — the exception text above is the evidence, not this classification. state.stage is never cleared and concurrent fan-outs overwrite it, so the failure may also have happened after that role finished, or in a sibling of it. ${state.tasksCompleted} task(s) had already completed and any committed work is on the branch.`,
-    'Retry this slice, skip it and continue the run, or stop the run to diagnose the exception?',
-    [{ label: 'Retry this slice', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice, keeping the committed work on its branch.', recommended: true },
-     { label: 'Skip this slice', detail: 'The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and dispatch only the independent slices. Nothing in the loop enforces a skip — the default re-dispatch procedure would retry it.' },
-     { label: 'Stop the run', detail: 'The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so the exception can be diagnosed before more agents are spent. Nothing in the loop stops the run by itself.' }]))
+  const context = `Error: ${String((e && e.message) || e)}. Last stage/role dispatched before the failure: ${stageText} — the most recent dispatch, not a per-throw stage, so a starting point, not a culprit. Cause unknown: neither structural guard raised its escalation record, and that is all the check one line above proves — the stage token floor calls budget.remaining() itself, so a throw from inside a guard reaches here with no record either. It may be a loop or agent-contract bug, and it may equally be a host- or agent-layer resource failure (a rejected agent call on a hard token or rate limit, say) — the exception text above is the evidence, not this classification. state.stage is never cleared and concurrent fan-outs overwrite it, so the failure may also have happened after that role finished, or in a sibling of it. ${state.tasksCompleted} task(s) had already completed and any committed work is on the branch.`
+  const question = 'Retry this slice, skip it and continue the run, or stop the run to diagnose the exception?'
+  const options = [
+    { label: 'Retry this slice', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice, keeping the committed work on its branch.', recommended: true },
+    { label: 'Skip this slice', detail: 'The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and dispatch only the independent slices. Nothing in the loop enforces a skip — the default re-dispatch procedure would retry it.' },
+    { label: 'Stop the run', detail: 'The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so the exception can be diagnosed before more agents are spent. Nothing in the loop stops the run by itself.' },
+  ]
+  return escalated(slice, state, esc(slice, 'internal-error', { title, context, question, options }))
 }
 
 async function runSlice(slice) {
   const state = initSliceState(slice)
   try {
@@ -914,13 +964,17 @@ const out = results.map((r, i) => r || {
   schema_version: 2, id: A.slices[i].id, status: 'ESCALATED', branch: A.slices[i].branch,
   commits: { base: A.slices[i].base_sha, head: null }, risk_tier: A.slices[i].risk_tier,
   review_tier: A.slices[i].risk_tier, critique: { verdict: 'SKIPPED', concerns: 0 },
   tasks_completed: 0, review: { confirmed: 0, refuted: 0, evidence_failed: 0, fix_rounds: 0, residual: [] },
   tests: null, quality: { status: 'SKIPPED', detail: 'slice never ran' },
-  escalations: [esc(A.slices[i], 'internal-error', 'slice lost', 'The slice function returned no result (terminal failure) — it died outside runSlice\'s try/catch. Neither structural guard raised its escalation record — each raises budget-exhausted with an escRecord runSlice would have returned — and that is all a null result proves, not that no guard check ran. A host- or agent-layer resource failure dies the same silent way, so the cause is unknown here.', 'Re-run the wave to retry this slice?',
-    [{ label: 'Retry this slice', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice. No result came back, so this record carries no exception text to diagnose and no record of committed work — inspect the slice branch before the retry, which starts from its base.', recommended: true },
+  escalations: [esc(A.slices[i], 'internal-error', {
+    title: 'slice lost',
+    context: 'The slice function returned no result (terminal failure) — it died outside runSlice\'s try/catch. Neither structural guard raised its escalation record — each raises budget-exhausted with an escRecord runSlice would have returned — and that is all a null result proves, not that no guard check ran. A host- or agent-layer resource failure dies the same silent way, so the cause is unknown here.',
+    question: 'Re-run the wave to retry this slice?',
+    options: [{ label: 'Retry this slice', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice. No result came back, so this record carries no exception text to diagnose and no record of committed work — inspect the slice branch before the retry, which starts from its base.', recommended: true },
      { label: 'Skip this slice', detail: 'The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and dispatch only the independent slices. Nothing in the loop enforces a skip — the default re-dispatch procedure would retry it.' },
-     { label: 'Stop the run', detail: 'The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so a silent host- or agent-layer failure can be investigated before more agents are spent. Nothing in the loop stops the run by itself.' }])],
+     { label: 'Stop the run', detail: 'The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so a silent host- or agent-layer failure can be investigated before more agents are spent. Nothing in the loop stops the run by itself.' }],
+  })],
   agents_used: 0, wave: A.wave_index, events: [],
 })
 log(`wave ${A.wave_index} collected: ${out.map(r => `${r.id}=${r.status}`).join(' ')}`)
 return { run_id: A.run_id, wave_index: A.wave_index, results: out }
