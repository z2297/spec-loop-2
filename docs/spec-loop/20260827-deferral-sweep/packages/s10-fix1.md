# Review package: 39a69c5..597f405  (context: -U5)

## Commits
597f405 fix(quality-gate): trim slice_wave_behaviour.test.mjs comments to clear class_lines

## Files changed
 .../scripts/slice_wave_behaviour.test.mjs          | 49 +++++++---------------
 1 file changed, 15 insertions(+), 34 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs": [
[
2,
5
],
[
10,
11
],
[
25,
25
],
[
29,
30
],
[
90,
90
],
[
151,
151
],
[
174,
175
],
[
210,
211
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs b/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
index db05b29..565ee59 100644
--- a/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
+++ b/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
@@ -1,26 +1,16 @@
 // slice_wave_behaviour.test.mjs — the first EXECUTING test of the wave workflow.
-//
-// HONEST LIMIT, stated plainly: this suite verifies the workflow's
-// DETERMINISTIC CONTROL FLOW ONLY. It drives the file against a mock
-// agent/parallel/log/budget sandbox described by HOST_CONTRACT in
-// slice_wave_harness.mjs. That contract is an ASSUMPTION written down by hand;
-// the repo specifies no host-sandbox contract anywhere. The real Workflow-host
-// seam is therefore NOT exercised here and stays unverified. A green run on
-// this file does not promote any claim to "behaviourally verified against the
-// host" — it says the behaviour asserted below holds against the mock
-// sandbox, and nothing wider.
-//
-// Node BUILT-INS ONLY (node:test + node:assert/strict), matching
-// dashboard_assets/index.test.mjs and the repo's zero-dependency posture.
+// HONEST LIMIT: verifies only the workflow's DETERMINISTIC CONTROL FLOW, against
+// the mock HOST_CONTRACT sandbox in slice_wave_harness.mjs (an ASSUMPTION the repo
+// does not itself specify) — the real Workflow-host seam stays unverified. Node
+// BUILT-INS ONLY (node:test + node:assert/strict), matching the repo's posture.
 
 import test from "node:test";
 import assert from "node:assert/strict";
 import {
-  HOST_CONTRACT, countExportConst, countWrapperName, WRAPPER_NAME,
-  rawSource, wrappedSource, makeWave, runWave, sliceFixture, waveArgs,
-} from "./slice_wave_harness.mjs";
+  HOST_CONTRACT, countExportConst, countWrapperName, WRAPPER_NAME, rawSource,
+  wrappedSource, makeWave, runWave, sliceFixture, waveArgs } from "./slice_wave_harness.mjs";
 
 test("the export-const rewrite matches exactly once", () => {
   assert.equal(countExportConst(rawSource()), 1);
   assert.equal(countExportConst(wrappedSource()), 0);
 });
@@ -30,21 +20,16 @@ test("the wrapped source instantiates as an AsyncFunction", () => {
   assert.equal(typeof wave, "function");
   assert.equal(wave.constructor.name, "AsyncFunction");
 });
 
 test("the assumed host contract is a named artifact marked unverified", () => {
-  assert.deepEqual(
-    Object.keys(HOST_CONTRACT).sort(),
-    ["agent", "budget", "log", "parallel", "verified"],
-  );
+  assert.deepEqual(Object.keys(HOST_CONTRACT).sort(), ["agent", "budget", "log", "parallel", "verified"]);
   assert.equal(HOST_CONTRACT.verified, false);
 });
 
-// The wrapped source only DECLARES the wrapper; makeWave appends a call to it
-// BY NAME. A rename inside slice_wave_contract_base.WRAP_HEAD would otherwise
-// make every behavioural test below assert against undefined. These two tests
-// make that failure land here, in the loader group, with a readable cause.
+// The wrapped source only DECLARES the wrapper; makeWave appends a call to it BY
+// NAME, so a rename in slice_wave_contract_base.WRAP_HEAD lands here, readably.
 test("the wrapper name appears exactly once in the wrapped source", () => {
   assert.equal(WRAPPER_NAME, "__wrap");
   assert.equal(countWrapperName(wrappedSource()), 1);
   assert.equal(countWrapperName(rawSource()), 0);
 });
@@ -100,12 +85,11 @@ test("the guaranteed context ordering leads with the two variable diagnostics",
 
 test("a crash before any dispatch yields the no-stage title", async () => {
   const budget = { total: 1, remaining: () => { throw new Error("NOBUDGET"); } };
   const out = await runWave(ONE_SLICE(), { budget });
   assert.equal(only(out).title, "slice crashed before any agent was dispatched");
-  assert.ok(only(out).context.includes(
-    "none (the crash happened before any agent was dispatched)"));
+  assert.ok(only(out).context.includes("none (the crash happened before any agent was dispatched)"));
 });
 
 const LOST = { parallel: async () => [null] };
 
 // Three-way, matching the crash record's shape: the record offers three
@@ -162,12 +146,11 @@ test("the crash and lost-slice records stay distinguishable after the widening",
   assert.ok(!lost.context.includes("Last stage/role dispatched"));
 });
 
 const FOUR_IDS = ["s1", "s2", "s3", "s4"];
 const FOUR = () => waveArgs(FOUR_IDS.map(sliceFixture));
-// The prompt carries the slice id (planPrompt embeds it), so an agent that
-// throws the prompt's own id back gives each slice a distinguishable failure.
+// The prompt carries the slice id, so an agent throwing it back distinguishes each slice's failure.
 const THROW_LABELLED = {
   agent: async (prompt, opts) => { throw new Error("crash-of-" + opts.label); },
 };
 
 test("every slice in a width-4 wave gets its own result, positionally", async () => {
@@ -186,13 +169,12 @@ test("each escalation id and context is attributed to its own slice", async () =
   assert.deepEqual(recs.map((r) => r.context.startsWith("Error: crash-of-")), [true, true, true, true]);
   FOUR_IDS.forEach((id, i) => assert.ok(recs[i].context.includes("crash-of-" + id + ":plan")));
 });
 
 // ── escalation id rounds (esc/escId) and answer matching (latestAnswer) ──────
-// The round is derived from args.answers, the only channel that survives a
-// re-dispatch, so these tests drive it by handing the wave the answers map a
-// resuming controller would hand it and reading the id the wave actually emits.
+// The round comes from args.answers, so these tests hand the wave an answers map a
+// resuming controller would supply and read the id the wave actually emits.
 
 const CRASH_KEY = "s1:" + CRASH_TRIGGER;
 const withAnswers = (answers) => waveArgs([sliceFixture("s1")], answers);
 
 test("an unanswered slice keeps the bare id, with no round component", async () => {
@@ -223,13 +205,12 @@ test("the same answers map reproduces the same id across dispatches", async () =
 test("an answer to one trigger does not advance another trigger's round", async () => {
   const out = await runWave(withAnswers({ "s1:ambiguity": "do this" }), THROWS);
   assert.equal(only(out).id, CRASH_KEY);
 });
 
-// Answer MATCHING, observed where it is observable: the planner prompt. A
-// round-suffixed id whose answer no longer reaches the prompt is the dead end
-// this slice exists to avoid, so it is pinned by execution, not by inspection.
+// Answer MATCHING, observed where it is observable: the planner prompt. A round-suffixed
+// id whose answer no longer reaches the prompt is pinned here by execution, not inspection.
 const capturePrompts = () => {
   const seen = [];
   return {
     seen,
     agent: async (prompt) => { seen.push(prompt); throw new Error("BOOM"); },
