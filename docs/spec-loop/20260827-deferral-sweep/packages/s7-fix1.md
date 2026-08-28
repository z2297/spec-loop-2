# Review package: c678174..4d152414f86c80d186f17265d40286ff946a8f8a  (context: -U5)

## Commits
4d15241 fix: retract the lost-slice retry detail's cause claim; correct the contract module's docstring after GENERIC_OPTION was deleted
55085b0 docs(escalation-gate): both internal-error records now offer the three controller-named options
24c9a86 test: pin that the crash and lost-slice records stay distinguishable
9fcfc01 escalation: lost-slice record carries the three controller-named options

## Files changed
 .../scripts/slice_wave_behaviour.test.mjs          | 43 ++++++++++++++++------
 .../spec-loop/scripts/slice_wave_contract_base.py  | 20 ++++++----
 plugins/spec-loop/skills/escalation-gate/SKILL.md  | 10 +++--
 plugins/spec-loop/workflows/slice-wave.workflow.js |  5 ++-
 4 files changed, 55 insertions(+), 23 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs": [
[
108,
108
],
[
123,
129
],
[
131,
131
],
[
133,
156
]
],
"plugins/spec-loop/scripts/slice_wave_contract_base.py": [
[
37,
48
]
],
"plugins/spec-loop/skills/escalation-gate/SKILL.md": [
[
83,
89
]
],
"plugins/spec-loop/workflows/slice-wave.workflow.js": [
[
919,
922
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs b/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
index 58bedb8..5741e8e 100644
--- a/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
+++ b/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
@@ -104,11 +104,10 @@ test("a crash before any dispatch yields the no-stage title", async () => {
   assert.equal(only(out).title, "slice crashed before any agent was dispatched");
   assert.ok(only(out).context.includes(
     "none (the crash happened before any agent was dispatched)"));
 });
 
-const GENERIC_OPTION = "Proceed with the recommended default";
 const LOST = { parallel: async () => [null] };
 
 test("a lost slice escalates with the same trigger and its own title", async () => {
   const out = await runWave(ONE_SLICE(), LOST);
   assert.equal(out.results[0].status, "ESCALATED");
@@ -119,22 +118,44 @@ test("a lost slice escalates with the same trigger and its own title", async ()
   assert.equal(only(out).trigger, CRASH_TRIGGER);
   assert.equal(only(out).title, "slice lost");
   assert.ok(only(out).question.startsWith("Re-run the wave to retry this slice"));
 });
 
-// PINS CURRENT BEHAVIOUR, with an open question standing against it.
-// controller-verified-evidence.md section 2 records that widening the
-// lost-slice record to the same three labels as the crash record "may be the
-// better fix at the same cost" and is a live question standing before the human. A future
-// widening should read as "update this pinned expectation", never as a
-// regression.
-test("the lost-slice record gets ONE substituted generic option", async () => {
+// The lost-slice record used to rely on esc()'s empty-array substitution, which
+// yields ONE option labelled "Proceed with the recommended default" whose detail
+// repeats the whole context. The human ruled that widening this record to the same
+// three controller-named labels as the crash record is the fix. The record's own
+// question stays binary on purpose, so this test pins the OPTION SET by execution
+// and claims nothing about the ask.
+test("the lost-slice record carries the same three controller-named options", async () => {
   const rec = only(await runWave(ONE_SLICE(), LOST));
-  assert.equal(rec.options.length, 1);
-  assert.equal(rec.options[0].label, GENERIC_OPTION);
+  assert.deepEqual(rec.options.map((o) => o.label), RECORD_OPTIONS);
   assert.equal(rec.options[0].recommended, true);
-  assert.equal(rec.options[0].detail, rec.context);
+  assert.equal(rec.options[1].recommended, undefined);
+  assert.equal(rec.options[2].recommended, undefined);
+  rec.options.forEach((o) => assert.notEqual(o.detail, rec.context));
+  rec.options.forEach((o) => assert.ok(o.detail.includes("CONTROLLER")));
+});
+
+// The two internal-error records now share the trigger, the id shape and the three
+// option labels. What still separates them is the evidence and the ask: the crash
+// record carries exception text plus a stage attribution and asks which of the three
+// to take; the lost-slice record carries neither and asks the binary re-run question.
+// A future edit that collapses them into one indistinguishable record fails here.
+test("the crash and lost-slice records stay distinguishable after the widening", async () => {
+  const crash = only(await runWave(ONE_SLICE(), THROWS));
+  const lost = only(await runWave(ONE_SLICE(), LOST));
+  assert.equal(crash.trigger, lost.trigger);
+  assert.deepEqual(crash.options.map((o) => o.label), RECORD_OPTIONS);
+  assert.deepEqual(lost.options.map((o) => o.label), RECORD_OPTIONS);
+  assert.notEqual(crash.title, lost.title);
+  assert.equal(lost.title, "slice lost");
+  assert.notEqual(crash.context, lost.context);
+  assert.notEqual(crash.question, lost.question);
+  assert.ok(crash.context.startsWith("Error: BOOM."));
+  assert.ok(!lost.context.startsWith("Error:"));
+  assert.ok(!lost.context.includes("Last stage/role dispatched"));
 });
 
 const FOUR_IDS = ["s1", "s2", "s3", "s4"];
 const FOUR = () => waveArgs(FOUR_IDS.map(sliceFixture));
 // The prompt carries the slice id (planPrompt embeds it), so an agent that
diff --git a/plugins/spec-loop/scripts/slice_wave_contract_base.py b/plugins/spec-loop/scripts/slice_wave_contract_base.py
index 73c2fe4..aff3495 100644
--- a/plugins/spec-loop/scripts/slice_wave_contract_base.py
+++ b/plugins/spec-loop/scripts/slice_wave_contract_base.py
@@ -32,18 +32,22 @@ These are source-text assertions. They prove a guard is present; they
 cannot prove it behaves. Any change to the workflow that trips one of them
 is either a regression or an intentional contract change that belongs in
 one of the importing modules too.
 Companion lane: slice_wave_behaviour.test.mjs executes the workflow in a mock
 sandbox and pins the runtime record shapes it produces there, including the
-crash record's three option labels and the lost-slice record's one substituted
-label. It carries its own honest-limit header stating that it covers
-deterministic control flow only. The three crash labels therefore live in three
-non-historical places: the workflow itself, the CRASH_OPTION_RETRY /
-CRASH_OPTION_SKIP / CRASH_OPTION_STOP constants below, and RECORD_OPTIONS in
-that module. The substituted lost-slice label lives in two: the workflow's
-esc() default and GENERIC_OPTION in that module. A label change must move every
-one of them.
+crash record's three option labels and, now that the lost-slice record was
+widened to the same three controller-named labels, its option labels too. It
+carries its own honest-limit header stating that it covers deterministic
+control flow only. The three labels therefore live in three non-historical
+places, shared by both records: the workflow itself, spelling the three
+option details out at two call sites, runSliceError and the wave-entry
+fallback; the CRASH_OPTION_RETRY / CRASH_OPTION_SKIP / CRASH_OPTION_STOP
+constants below, scoped to the crash source text; and RECORD_OPTIONS in that
+module, pinning the runtime labels of both records. esc()'s single generic
+substitution remains live across its other empty-array call sites, but no
+harness constant pins that label anymore. A label change must move every one of
+them.
 
 Every pinned JS snippet is a module-level constant rather than a literal in
 a test body, and continuation lines use a 4-space hanging indent. Both are
 deliberate: quality_gate.py's heuristics are line-based, so a `&&` or an `if`
 inside a string literal scores as real branching (cognitive_complexity) and a
diff --git a/plugins/spec-loop/skills/escalation-gate/SKILL.md b/plugins/spec-loop/skills/escalation-gate/SKILL.md
index 602dd4d..600c373 100644
--- a/plugins/spec-loop/skills/escalation-gate/SKILL.md
+++ b/plugins/spec-loop/skills/escalation-gate/SKILL.md
@@ -78,13 +78,17 @@ record from `runSliceError` carries the real exception text together with the la
 dispatched before the failure, which is the most recent dispatch rather than a per-throw stage,
 and its context says exactly that about itself. The lost-slice record carries neither, having
 nothing to carry, and its context does not announce the gap: it states only that a null result
 proves nothing about which guard ran. Read that absence as absence, not as a claim about the
 cause. The trigger reports a machine failure and is never answerable by re-dispatching an agent,
-so only a human or the controller resolves it — and only the exception record spells the choice
-out as three options, retry the slice, skip it, or stop the run; the lost-slice record asks one
-question, whether to re-run the wave, and carries a single generic recommended-default option),
+so only a human or the controller resolves it. Both records now offer the same three
+controller-named options, retry the slice, skip it, or stop the run, each detail naming the
+CONTROLLER as what applies it — matched to the `options` argument the wave-entry fallback
+passes to `esc`, alongside the one `runSliceError` already passed. What still separates the two
+is the evidence and the ask: the exception record carries the exception text and the last
+stage/role dispatched and asks which of the three to take, while the lost-slice record carries
+neither and asks only whether to re-run the wave),
 and the council's **over-scope flag** (`critique.over_scope.flag`). The flag is a record: it is
 carried into the `council-verdict` payload and the slice sidecar with its reason, and it raises no
 escalation, changes no verdict, suppresses no split, and blocks nothing. There are exactly five
 JUDGMENT triggers; an over-scope flag is not a sixth.
 
diff --git a/plugins/spec-loop/workflows/slice-wave.workflow.js b/plugins/spec-loop/workflows/slice-wave.workflow.js
index f30341c..73c7eec 100644
--- a/plugins/spec-loop/workflows/slice-wave.workflow.js
+++ b/plugins/spec-loop/workflows/slice-wave.workflow.js
@@ -914,10 +914,13 @@ const out = results.map((r, i) => r || {
   schema_version: 2, id: A.slices[i].id, status: 'ESCALATED', branch: A.slices[i].branch,
   commits: { base: A.slices[i].base_sha, head: null }, risk_tier: A.slices[i].risk_tier,
   review_tier: A.slices[i].risk_tier, critique: { verdict: 'SKIPPED', concerns: 0 },
   tasks_completed: 0, review: { confirmed: 0, refuted: 0, evidence_failed: 0, fix_rounds: 0, residual: [] },
   tests: null, quality: { status: 'SKIPPED', detail: 'slice never ran' },
-  escalations: [esc(A.slices[i], 'internal-error', 'slice lost', 'The slice function returned no result (terminal failure) — it died outside runSlice\'s try/catch. Neither structural guard raised its escalation record — each raises budget-exhausted with an escRecord runSlice would have returned — and that is all a null result proves, not that no guard check ran. A host- or agent-layer resource failure dies the same silent way, so the cause is unknown here.', 'Re-run the wave to retry this slice?', [])],
+  escalations: [esc(A.slices[i], 'internal-error', 'slice lost', 'The slice function returned no result (terminal failure) — it died outside runSlice\'s try/catch. Neither structural guard raised its escalation record — each raises budget-exhausted with an escRecord runSlice would have returned — and that is all a null result proves, not that no guard check ran. A host- or agent-layer resource failure dies the same silent way, so the cause is unknown here.', 'Re-run the wave to retry this slice?',
+    [{ label: 'Retry this slice', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice. No result came back, so this record carries no exception text to diagnose and no record of committed work — inspect the slice branch before the retry, which starts from its base.', recommended: true },
+     { label: 'Skip this slice', detail: 'The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and dispatch only the independent slices. Nothing in the loop enforces a skip — the default re-dispatch procedure would retry it.' },
+     { label: 'Stop the run', detail: 'The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so a silent host- or agent-layer failure can be investigated before more agents are spent. Nothing in the loop stops the run by itself.' }])],
   agents_used: 0, wave: A.wave_index, events: [],
 })
 log(`wave ${A.wave_index} collected: ${out.map(r => `${r.id}=${r.status}`).join(' ')}`)
 return { run_id: A.run_id, wave_index: A.wave_index, results: out }
